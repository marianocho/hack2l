"""O motor: QUEM cobra pela chamada de modelo, isolado do resto do produto.

Ate' 19/08 as tres pecas que falam com a Anthropic construiam o cliente cada uma
por conta propria -- `anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)`, tres
vezes, em `promotores.py`, `advogado.py` e `fontes.py`. Trocar de provedor
significava achar as tres e mante-las de acordo. E' a mesma classe do
`app/api/app` chumbado: valor de infraestrutura espalhado por dentro do codigo
que faz o trabalho.

Aqui existe UM lugar que responde tres perguntas:

    cliente()          com quem eu falo
    modelo(id)         como aquele provedor chama este modelo
    ajusta_chamada()   o que aquele provedor NAO aceita

Tres motores, e a diferenca entre eles nao e' cosmetica:

    anthropic   API direta. Paridade total. Paga com ANTHROPIC_API_KEY.
    aws         Claude Platform on AWS -- operada pela Anthropic sobre infra
                AWS (SigV4, IAM, cobranca via AWS Marketplace). Paridade de
                API no mesmo dia. IDs de modelo sao os de sempre, sem prefixo.
    bedrock     Amazon Bedrock -- operada pela AWS. Servico nativo, e' onde
                credito promocional da AWS costuma valer. Em compensacao o
                conjunto de features e' MENOR, e o que falta e' justo o que
                sustenta o terceiro estado (ver `SEM_NO_BEDROCK`).

🚨 A DEGRADACAO E' DITA EM VOZ ALTA, NUNCA SILENCIOSA.

Este modulo poderia simplesmente remover do kwargs o que o Bedrock recusa e
seguir. Seria o padrao de bug do projeto de novo: a guarda -- aqui, o
`fallbacks="default"` que manda a recusa do classificador para outro modelo em
vez de derrubar a categoria carro-chefe -- some exatamente no motor onde ela nao
existe, e nada avisa. Entao:

  - o que foi removido esta em `Motor.sem`, legivel de fora;
  - `descreve()` entra no pre-voo, ao lado dos scanners, com o mesmo criterio:
    nao e' essencial, mas nao e' invisivel;
  - `advogado._diagnostico_da_recusa` consulta `tem("fallback_de_recusa")`
    antes de culpar rate limit por um fallback que nunca foi armado.

⚠️ AUSENTE NAO E' VAZIO, ERRADO NAO E' AUSENTE -- a mesma doutrina do
`veredito.yml`:

    sem credencial AWS, em `auto`   -> cai para a API direta, e diz que caiu
    sem credencial AWS, FORCADO     -> levanta

O segundo caso e' o que importa. Quem escreveu `VEREDITO_MOTOR=bedrock` esta
gastando credito da AWS de proposito; cair calado para a API direta faturaria a
rodada na conta errada e a rodada pareceria perfeita. Engano do operador nao se
resolve seguindo com metade dele.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic

from . import config as cfg

# --- o que cada motor NAO tem ----------------------------------------------
#
# Conferido contra a matriz de disponibilidade por plataforma, nao de memoria.
# Sao os dois unicos parametros que este produto manda e que o Bedrock recusa;
# `thinking` adaptativo, `effort`, `cache_control` explicito e o streaming do
# tool_runner passam iguais nos tres motores.
#
# 🚫 Nao acrescente aqui nada que "talvez nao funcione". Mascara larga demais e'
# guarda morrendo de EXCESSO: removeria `effort` de rodada que o suporta, e o
# operador aprenderia a ignorar a linha do pre-voo -- que da' no mesmo que ela
# nao existir. Foi o `NAO MEDIDO` do banco, em 17/08.
SEM_NO_BEDROCK = frozenset({"task_budget", "fallback_de_recusa"})

# O que cada capacidade custa quando falta. Texto de operador: vai para o
# pre-voo e para o parecer, e precisa dizer o que MUDA, nao o nome do parametro.
CUSTO = {
    "task_budget": ("o advogado deixa de saber o proprio orcamento e fecha o "
                    "parecer no corte do max_tokens, nao por decisao dele"),
    "fallback_de_recusa": ("recusa do classificador de ciberseguranca vira "
                           "INCONCLUSIVO direto, sem segunda tentativa em "
                           "outro modelo -- e ciberseguranca e' a categoria "
                           "carro-chefe deste produto"),
    "tool_runner": ("o advogado NAO RODA: o loop pensa -> ferramenta -> decide "
                    "e' o `tool_runner` do SDK, e o cliente legado do Bedrock "
                    "nao o expoe. Sem ele nao ha' quem TESTE a acusacao"),
}

# Toda capacidade que ALGUM motor pode perder -- nao so' as que o Bedrock recusa
# por parametro. `tool_runner` entra aqui e nao em `SEM_NO_BEDROCK` porque nao e'
# propriedade do Bedrock: e' propriedade do CLIENTE LEGADO dele, ligado pela
# escotilha `VEREDITO_BEDROCK_LEGADO`. Enfia-la na constante faria todo Bedrock
# declarar uma perda que o caminho padrao nao tem -- guarda morrendo de excesso.
#
# ⚠️ `perdas()` procura o nome em `CUSTO`; nome sem texto sai do pre-voo como
# rotulo cru e o operador nao fica sabendo o que muda. O teste amarra as duas.
CAPACIDADES = SEM_NO_BEDROCK | {"tool_runner"}

# Betas que so existem no primeiro-parte. Casadas com a capacidade que as pede:
# tirar a capacidade e deixar a beta gera 400, e foi assim que a mascara quebrou
# na primeira tentativa.
_BETA_DE = {
    "task_budget": "task-budgets-2026-03-13",
    "fallback_de_recusa": "server-side-fallback-2026-07-01",
}


@dataclass(frozen=True)
class Motor:
    nome: str
    rotulo: str
    detalhe: str
    sem: frozenset[str] = field(default_factory=frozenset)
    prefixo_de_modelo: str = ""

    def tem(self, capacidade: str) -> bool:
        return capacidade not in self.sem

    def perdas(self) -> list[str]:
        """O que este motor nao faz, em frase de operador. Vazio e' resposta."""
        return [f"{c}: {CUSTO[c]}" for c in sorted(self.sem) if c in CUSTO]


# --- resolucao de credencial ------------------------------------------------

def _ha_sinal_aws() -> bool:
    """Existe QUALQUER indicio de AWS no ambiente? Sem rede, em microssegundos.

    🚨 Este atalho existe por um motivo concreto: `boto3.Session().get_credentials()`
    percorre a cadeia inteira e, numa maquina que nao e' EC2, o ultimo elo e' o
    IMDS -- uma conexao para 169.254.169.254 que so morre no timeout. Numa
    maquina de dev sem AWS nenhuma, deixar a deteccao automatica cair ali
    colocaria um passo de rede no caminho de TODA rodada, inclusive as que nunca
    quiseram AWS.

    Entao: sem nenhum sinal barato, nem chamamos o boto3. Com sinal, chamamos --
    ai' ha' motivo para acreditar que a cadeia resolve, e o custo se justifica.

    ⚠️ Isto NAO decide o motor. Ele so decide se vale a pena perguntar ao boto3.
    Quem decide e' `_resolve_credenciais`, e no modo forcado ela roda sempre.
    """
    if any(os.getenv(v) for v in (
            "AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_DEFAULT_PROFILE",
            "AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI")):
        return True
    cred = os.getenv("AWS_SHARED_CREDENTIALS_FILE") or os.path.expanduser(
        "~/.aws/credentials")
    return os.path.exists(cred) or os.path.exists(os.path.expanduser("~/.aws/config"))


def _resolve_credenciais() -> tuple[bool, str, str | None]:
    """(tem credencial, o porque, regiao). Ponto de injecao dos testes.

    Devolve a CAUSA junto, sempre. "sem credencial AWS" manda quem le abrir o
    codigo para descobrir se faltava boto3, chave ou regiao -- e as tres tem
    consertos diferentes. Mesma licao do `NAO RODOU -- {e}` dos scanners.
    """
    try:
        import boto3
    except ImportError:
        return False, "boto3 nao instalado (pip install boto3)", None

    try:
        perfil = os.getenv("AWS_PROFILE") or os.getenv("AWS_DEFAULT_PROFILE")
        sessao = boto3.Session(profile_name=perfil) if perfil else boto3.Session()
        cred = sessao.get_credentials()
        regiao = (sessao.region_name or os.getenv("AWS_REGION")
                  or os.getenv("AWS_DEFAULT_REGION"))
    except Exception as e:
        return False, f"boto3 nao resolveu a sessao: {type(e).__name__}: {e}", None

    if cred is None:
        return False, "a cadeia de credenciais do boto3 nao resolveu nada", regiao
    if not regiao:
        # Regiao nao e' detalhe: o AnthropicAWS levanta na construcao sem ela, e
        # o Bedrock cairia num padrao que pode nem ter o modelo habilitado.
        return False, ("credencial AWS existe, mas AWS_REGION nao esta definida "
                       "-- nenhum dos dois clientes AWS tem padrao seguro"), None
    return True, f"credencial AWS via {cred.method}, regiao {regiao}", regiao


# --- os tres motores --------------------------------------------------------

def _escolhe() -> Motor:
    """Precedencia: variavel de ambiente > deteccao. A mesma do veredito.yml.

    ⚠️ Le o ambiente AGORA, nao no import. O motor e' decidido por rodada, e uma
    constante de modulo tornaria a escolha intestavel e imune a
    `VEREDITO_MOTOR=bedrock py -3.12 -m veredito.orquestrador` -- que e'
    exatamente o uso pontual que a precedencia existe para servir.
    """
    pedido = (os.getenv("VEREDITO_MOTOR") or "auto").strip().lower()
    if pedido not in ("auto", "anthropic", "aws", "bedrock"):
        raise ValueError(
            f"VEREDITO_MOTOR={pedido!r} nao existe. "
            f"Use auto, anthropic, aws ou bedrock.")

    if pedido == "anthropic":
        return _anthropic("VEREDITO_MOTOR=anthropic")

    if pedido in ("aws", "bedrock"):
        # 🚨 FORCADO: aqui nao ha' fallback. Ver o cabecalho do modulo.
        ok, porque, regiao = _resolve_credenciais()
        if not ok:
            raise RuntimeError(
                f"VEREDITO_MOTOR={pedido} foi pedido e nao ha' credencial AWS "
                f"utilizavel: {porque}.\n"
                f"Cair para a API direta aqui faturaria a rodada na conta "
                f"errada em silencio. Configure a credencial, ou peca "
                f"VEREDITO_MOTOR=anthropic de proposito.")
        return _aws(porque, regiao) if pedido == "aws" else _bedrock(porque, regiao)

    # auto
    if not _ha_sinal_aws():
        return _anthropic("nenhum sinal de AWS no ambiente")
    ok, porque, regiao = _resolve_credenciais()
    if not ok:
        return _anthropic(f"AWS indisponivel, seguindo pela API direta -- {porque}")
    return _bedrock(porque, regiao)


def _anthropic(porque: str) -> Motor:
    return Motor("anthropic", "API direta da Anthropic", porque)


def _aws(porque: str, regiao: str | None) -> Motor:
    return Motor("aws", f"Claude Platform on AWS ({regiao})", porque)


def _legado_pedido() -> bool:
    """A escotilha do caminho legado, lida em UM lugar so'.

    ⚠️ Ela decide duas coisas -- qual cliente construir e o que o motor perde --
    e as duas precisam concordar. Ler a variavel nos dois lugares e' a "chave em
    dois lugares" que ja' custou quatro tentativas neste projeto.
    """
    return (os.getenv("VEREDITO_BEDROCK_LEGADO") or "").strip().lower() in (
        "1", "true", "sim")


def _bedrock(porque: str, regiao: str | None) -> Motor:
    # 🚨 MEDIDO em 20/08, construindo os dois clientes: o legado
    # (`AnthropicBedrock`) NAO tem `beta.messages.tool_runner` -- o
    # `lib/bedrock/_beta_messages.Messages` define `create` e mais nada. O
    # Mantle tem, porque o `MantleBeta.messages` devolve a classe de primeira
    # parte. O docstring de `_fab_bedrock` tratava o legado como alternativa
    # equivalente, e ele nao e': a escotilha derrubaria o advogado com
    # AttributeError em TODA acusacao, e o `try` de `julga` converteria cada uma
    # em INCONCLUSIVO opaco. A categoria carro-chefe se esvaziando sozinha, com
    # cara de rigor -- o desfecho exato que o terceiro estado existe para evitar.
    sem = set(SEM_NO_BEDROCK)
    if _legado_pedido():
        sem.add("tool_runner")
    return Motor("bedrock", f"Amazon Bedrock ({regiao})", porque,
                 sem=frozenset(sem), prefixo_de_modelo="anthropic.")


_ATIVO: Motor | None = None


def ativo() -> Motor:
    """O motor desta rodada. Resolvido uma vez, para nao oscilar no meio."""
    global _ATIVO
    if _ATIVO is None:
        _ATIVO = _escolhe()
    return _ATIVO


def esquece() -> None:
    """Descarta a resolucao. Para os testes e para quem troca de motor no mesmo
    processo -- `roda_bancada` roda varios PRs em sequencia."""
    global _ATIVO
    _ATIVO = None


# --- o cliente --------------------------------------------------------------
#
# Ponto de injecao dos testes: trocar aqui evita construir cliente de verdade,
# que le credencial do disco e resolve endpoint.
def _fab_anthropic():
    return anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)


def _fab_aws():
    # `workspace_id` e regiao nao tem padrao: o cliente levanta na construcao se
    # faltarem, o que e' melhor que descobrir no meio da rodada.
    return anthropic.AnthropicAWS(
        workspace_id=os.getenv("ANTHROPIC_AWS_WORKSPACE_ID") or None)


def _fab_bedrock():
    # Mantle e' o endpoint Messages do Bedrock -- mesma superficie do cliente de
    # sempre, `beta.messages.tool_runner` incluso. O `AnthropicBedrock` sem
    # Mantle e' o caminho legado por InvokeModel; fica atras de uma escotilha
    # porque nem toda conta tem o Mantle habilitado.
    #
    # 🚫 E o legado NAO e' equivalente: ele nao expoe `tool_runner`, entao o
    # advogado nao roda nele. Quem perde o que esta em `_bedrock`, e o pre-voo
    # reprova antes de a rodada gastar -- ver `descreve`.
    if _legado_pedido():
        return anthropic.AnthropicBedrock()
    return anthropic.AnthropicBedrockMantle()


_FABRICAS = {
    "anthropic": _fab_anthropic,
    "aws": _fab_aws,
    "bedrock": _fab_bedrock,
}


def cliente():
    """O cliente do motor ativo. Mesma superficie nos tres -- e' o ponto todo.

    🚫 Nao escrevemos um wrapper boto3 a mao por cima do bedrock-runtime. O
    `tool_runner` E' o advogado: o loop pensa -> ferramenta -> resultado ->
    decide, com streaming, retry e as definicoes de ferramenta do SDK.
    Reimplementa-lo para trocar quem fatura seria bifurcar a unica peca do
    produto que e' agente de verdade, e passar a manter duas versoes dela. Os
    clientes de Bedrock/AWS do proprio SDK assinam com SigV4 pelo boto3 e expoem
    `beta.messages.tool_runner` igual -- o adaptador que a arquitetura pede ja'
    vem pronto, e o boto3 entra onde ele e' de fato bom: resolver credencial.
    """
    return _FABRICAS[ativo().nome]()


# --- traducao e mascara -----------------------------------------------------

def modelo(id_: str) -> str:
    """O id do modelo como ESTE motor o chama.

    ⚠️ Passa batido em quem ja' tem prefixo de provedor. Perfil de inferencia
    (`us.anthropic....`) e' id legitimo do Bedrock, e prefixar de novo geraria
    `anthropic.us.anthropic....` -- um 404 que se le como "modelo nao habilitado
    na conta" e manda o operador procurar no console errado.
    """
    m = ativo()
    if not m.prefixo_de_modelo:
        return id_
    if id_.startswith(m.prefixo_de_modelo) or ".anthropic." in id_:
        return id_
    return m.prefixo_de_modelo + id_


def ajusta_chamada(**kw) -> dict:
    """Os kwargs da chamada, adaptados ao motor ativo.

    Faz duas coisas e nenhuma a mais: traduz o `model` e remove o que este motor
    recusa. Nao acrescenta parametro, nao troca valor de parametro que o motor
    aceita -- mascara que "melhora" a chamada esconde o que o codigo pediu.
    """
    m = ativo()
    kw = dict(kw)

    if "model" in kw:
        kw["model"] = modelo(kw["model"])

    betas = list(kw.get("betas") or [])

    if not m.tem("task_budget"):
        oc = kw.get("output_config")
        if isinstance(oc, dict) and "task_budget" in oc:
            oc = {k: v for k, v in oc.items() if k != "task_budget"}
            # 🚫 `effort` continua. Ele e' suportado no Bedrock, e remover junto
            # seria a mascara comendo o que nao e' dela.
            if oc:
                kw["output_config"] = oc
            else:
                kw.pop("output_config")
        betas = [b for b in betas if b != _BETA_DE["task_budget"]]

    if not m.tem("fallback_de_recusa"):
        kw.pop("fallbacks", None)
        betas = [b for b in betas if b != _BETA_DE["fallback_de_recusa"]]

    # Lista de betas vazia nao e' o mesmo que ausente em todo SDK; e mandar
    # `betas=[]` documenta mal a chamada.
    if betas:
        kw["betas"] = betas
    else:
        kw.pop("betas", None)
    return kw


# --- o que o pre-voo mostra -------------------------------------------------

def descreve() -> dict:
    """Bloco do pre-voo, no formato das outras sondas.

    `ok` NAO e' "tem AWS". E' "ha' um motor utilizavel" -- que na API direta
    exige a chave. Motor e' pre-requisito de qualquer chamada, entao aqui `ok`
    falso significa que a rodada nao tem como comecar.
    """
    try:
        m = ativo()
    except Exception as e:
        return {"motor": {"ok": False, "detalhe": f"{type(e).__name__}: {e}"}}

    cabeca = f"{m.rotulo} -- {m.detalhe}"
    if m.nome == "anthropic" and not cfg.ANTHROPIC_API_KEY:
        return {"motor": {"ok": False,
                          "detalhe": f"{cabeca}; e ANTHROPIC_API_KEY esta vazia"}}

    # 🚨 Perder `task_budget` ou `fallback_de_recusa` DEGRADA a rodada, e o
    # operador decide se aceita. Perder `tool_runner` nao degrada: cancela. Sem
    # ele nao ha' advogado, e sem advogado nada e' testado -- restaria o
    # promotor acusando e ninguem verificando, que e' o produto ao contrario.
    # Por isso esta perda reprova o pre-voo em vez de virar mais uma linha de
    # aviso: alarme que so' informa, num caso que nao tem como dar certo,
    # ensina a seguir em frente.
    if not m.tem("tool_runner"):
        return {"motor": {"ok": False, "detalhe": (
            f"{cabeca}; o cliente legado do Bedrock nao expoe tool_runner, "
            f"entao o advogado nao roda. Tire VEREDITO_BEDROCK_LEGADO para usar "
            f"o Mantle, ou peca VEREDITO_MOTOR=aws/anthropic")}}

    return {"motor": {"ok": True,
                      "detalhe": " | ".join([cabeca] + [f"SEM {p}" for p in m.perdas()])}}
