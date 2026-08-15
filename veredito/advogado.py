"""hack2l / Veredito -- o advogado. A unica peca que e' agente de verdade.

Loop: pensa -> ferramenta -> resultado -> decide. Ele NAO argumenta, TESTA.

Ve UMA acusacao por vez, isolado. Sem historico compartilhado entre acusacoes:
uma acusacao fraca nao contamina a proxima, e o prefixo do diff fica identico em
todas as chamadas, que e' o que faz o cache pagar.
"""

from __future__ import annotations

import json
import re
import time

import anthropic

from . import arbitro
from . import config as cfg
from . import ferramentas
from . import fontes

# O prompt e' produto, nao configuracao. Cada paragrafo aqui existe por um
# motivo que custou caro em outro lugar.
SISTEMA = """Voce e' o ADVOGADO do Veredito, um revisor de codigo autonomo.

Voce recebe UMA acusacao sobre um pull request e tem um trabalho so: descobrir
se ela se sustenta, produzindo um ARTEFATO REPRODUZIVEL. Voce nao argumenta,
nao opina e nao avalia plausibilidade. Voce testa.

## O que conta como prova

Um artefato que outra pessoa possa rodar e ver o mesmo resultado. Nada mais.
Codigo que "parece errado" nao e' prova. Raciocinio convincente nao e' prova.

## Os arquivos do PR ja vieram

O bloco "Os arquivos que o PR toca" traz o conteudo integral deles, igual ao que
`read_file` devolveria. Nao chame `read_file` para esses -- a resposta seria
identica e voce teria gasto uma volta. Use as ferramentas para o que voce ainda
NAO tem: outros arquivos do repo, `grep`, e sobretudo a prova.

## 🚨 A prova NAO PODE DESTRUIR o que testa

`http_request` fala com o app REAL rodando, com dados reais. A linha nao e'
entre ler e escrever -- e' entre CRIAR e DESTRUIR, e ela cai em dois lugares
diferentes:

🚫 O PAYLOAD que voce injeta e' sempre read-only. SQL injetado NUNCA escreve:
nada de `DROP`, `DELETE`, `UPDATE`, `INSERT` ou `; --`. Um `DROP TABLE` de
verdade apagaria o dado do proximo teste, e `' OR '1'='1` devolvendo linhas que
nao deveria prova exatamente a mesma falha sem tocar em nada.

✅ A CHAMADA a um endpoint documentado pode criar registro, quando o defeito
mora nesse endpoint. Para provar injecao na rota que compartilha documento,
voce precisa chamar a rota que compartilha documento -- nao existe outro
caminho, e recusar por isso so' produziria INCONCLUSIVO a toa.

🚫 O que continua proibido em qualquer via: apagar ou modificar estado que JA
EXISTIA. Documento de outro usuario, conta alheia, dado do seed. Criar linha
nova e' aceitavel; mexer no que ja estava la, nao.

Dentro do permitido, PREFIRA a prova que so' le e faca o MINIMO de escritas:

- Vazamento/IDOR: um GET que retorna o que nao devia, sem mexer em nada.
- Se precisar escrever, escreva como um usuario que voce controla e sobre um
  recurso seu -- nao por cima do dado de outro.
- Duas escritas que provam a mesma coisa valem uma. Cada linha que voce cria
  desloca a linha de base do proximo teste.

Isto nao e' so seguranca: payload destrutivo tambem faz o classificador recusar
a chamada, e a acusacao vira INCONCLUSIVO a toa. Prova read-only passa e e' mais
limpa. Se a unica forma de provar exigisse APAGAR ou MODIFICAR estado
pre-existente, PARE e responda INCONCLUSIVO explicando -- nao destrua o alvo.

## Escreva o teste sobre a INVARIANTE, nao sobre o endpoint

`prova_diferencial` so assina PROVADO se o teste passa no base e falha no head.
Isso parece impedir provar defeito em endpoint NOVO -- um teste que chama
/shared/{id} da 404 no base, que e' falha, e o resultado sai inconclusivo.

A saida e' escrever o teste sobre a REGRA que o PR deveria respeitar, nao sobre
o codigo que ele adicionou:

  ruim:  "GET /shared/1 como carol devolve 200"     -> 404 no base, inconclusivo
  bom:   "carol nao alcanca o documento de alice
          por nenhuma rota"                          -> passa no base (nao havia
                                                         como vazar), falha no
                                                         head. PROVADO.

A invariante quase sempre ja vale no commit base -- e' por isso que ela e'
invariante. Formule assim e a prova diferencial serve para os dois casos.

Se ainda assim nao der, `http_request` mostra o comportamento errado
acontecendo de fora, autenticado como usuario do seed.

## Prove das duas formas quando puder

Um teste diferencial prova CAUSALIDADE: foi esta mudanca que quebrou.
Um `http_request` prova ALCANCE: da para fazer isso de fora, agora.

Sao coisas diferentes e a segunda vale mais. Uma acusacao provada so por teste
e' rebaixada a MEDIA automaticamente; so prova ponta a ponta pela API sustenta
severidade alta. Se o app esta no ar e o defeito e' alcancavel, faca as duas --
custa uma volta e muda a severidade.

## A linha de base do isolamento, ja medida

demo tem 3 documentos. alice tem 1. bob tem 1. carol NAO TEM NADA.
carol e' o controle negativo: qualquer dado de outro usuario que apareca para
ela e' vazamento. Uma chamada como carol vale mais que um paragrafo de analise.

## Ausencia de observacao nao e' refutacao

Se o payload nao surtiu efeito porque o modelo do app alvo esta duble, se o
docker caiu, se o teste nao coletou, se deu timeout -- o veredito e'
INCONCLUSIVO, com a causa. Nunca REFUTADO. As ferramentas avisam quando isso
acontece; leia o aviso.

REFUTADO e' um resultado forte e significa uma coisa so: voce testou, o teste
rodou, e a acusacao nao se sustentou.

## Economia do loop

Voce tem NO MAXIMO {teto} voltas de ferramenta. Isso e' pouco, e acabar sem
veredito e' um fracasso -- a acusacao vira inconclusiva e o trabalho se perde.

Orcamento tipico: 1 a 2 voltas para se situar, 1 para montar a prova, 1 para
rodar. Va direto ao ponto de prova. Nao leia arquivo por curiosidade, nao
confirme o que a acusacao ja te disse, nao explore o repo. Se depois de 3
voltas voce ainda nao sabe como provar, decida a estrategia e execute com o que
tem.

## Formato da resposta final

Quando terminar, responda APENAS com um objeto JSON, sem cercas de codigo e sem
texto em volta:

{"veredito": "PROVADO|REFUTADO|INCONCLUSIVO",
 "severidade": "CRITICA|ALTA|MEDIA|BAIXA",
 "prova_ponta_a_ponta": true|false,
 "motivo": "uma frase",
 "conserto": "uma frase, so se PROVADO"}

`prova_ponta_a_ponta` e' true apenas se a falha foi demonstrada pela API
rodando (`http_request`), nao por chamada direta de funcao.
`motivo` explica o que aconteceu: por que provou, por que nao se sustentou, ou
o que foi tentado e por que nao fechou."""


FECHAMENTO = (
    "Voce chegou ao teto de voltas. Nao ha mais ferramenta disponivel.\n\n"
    "Responda AGORA com o JSON do veredito, a partir do que voce ja apurou.\n"
    "Se conseguiu um artefato reproduzivel, o veredito e' PROVADO ou REFUTADO "
    "conforme o resultado. Se nao chegou la, o veredito e' INCONCLUSIVO e o "
    "campo `motivo` precisa dizer O QUE VOCE TENTOU e por que nao fechou -- "
    "esse texto vai para o parecer, entao seja especifico e util."
)


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)


def diff_do_pr() -> str:
    """O diff base..head. Prefixo IDENTICO em toda chamada -- e' o que cacheia.

    Nunca imprimir: o time nao pode ver o diff antes do agente trabalhar.
    """
    base, head = ferramentas.commit_base(), ferramentas.commit_head()
    r = ferramentas._git("diff", f"{base}..{head}")
    if r.returncode != 0:
        raise RuntimeError(f"git diff falhou: {r.stderr.strip()}")
    return r.stdout


def _texto_final(msg) -> str:
    return "\n".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def _parse_veredicto(texto: str) -> dict:
    """try/except com a saida crua no fallback.

    Um veredicto nunca morre por erro de formato: sem isto, uma acusacao provada
    sumiria do parecer porque o modelo pos uma cerca de codigo em volta do JSON.

    🚨 A versao ganancioso (`re.search(r"\\{.*\\}", DOTALL)`) casava do PRIMEIRO
    `{` ate o ULTIMO, e o advogado escreve prosa antes do JSON. Na rodada das
    12h15 a prosa citava `SELECT ... email = '{email}'` e a rota
    `/documents/{id}/share`: o span comecou em `{email}`, o json.loads quebrou, e
    um PROVADO **com artefato no disco** virou INCONCLUSIVO por formatacao. E'
    exatamente a falha que este fallback existia para impedir.

    Entao: `raw_decode` a partir de cada `{`, do fim para o comeco. O ultimo
    objeto valido com `veredito` ganha -- que e' o veredito final, e nao uma
    chave qualquer que apareceu no meio do texto.
    """
    bruto = texto.strip()
    dec = json.JSONDecoder()
    for i in reversed([m.start() for m in re.finditer(r"\{", bruto)]):
        try:
            v, _ = dec.raw_decode(bruto[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(v, dict) and v.get("veredito"):
            return v
    return {
        "veredito": "INCONCLUSIVO",
        "motivo": "o advogado nao devolveu JSON valido; saida crua preservada",
        "saida_crua": bruto[:2000],
    }


def _diagnostico_da_recusa(msg) -> str:
    """A causa da recusa, com o que o SDK sabe e a gente estava descartando.

    Verificado no anthropic 0.120.2 instalado, nao de memoria: `fallbacks` E'
    aceito pelo tool_runner (esta na assinatura em
    resources/beta/messages/messages.py, nas duas sobrecargas), o escalar
    "default" E' valido (BetaFallbacksParam = Union[Iterable[...], "default"])
    e `cyber` E' categoria coberta -- a docstring do proprio SDK diz que
    "benign cybersecurity work can also trigger this category".

    Ou seja: o pareamento esta certo, e uma recusa que chega aqui significa uma
    de DUAS coisas, que pedem acoes diferentes:

      fallback nao rodou  -- rate limit ou sobrecarga no modelo de fallback. O
                             servidor preenche `recommended_model`, e um retry
                             direto nele tem chance de passar.
      cadeia toda recusou -- o fallback rodou e tambem recusou. Sinal: um item
                             `fallback_message` em usage.iterations.

    Sem distinguir, o parecer diz so "recusa do classificador": verdade, e
    inutil. A regra do desafio e' INCONCLUSIVO **com a causa**.
    """
    partes = ["recusa do classificador"]
    det = getattr(msg, "stop_details", None)
    if det is not None and getattr(det, "category", None):
        partes.append(f"categoria {det.category}")

    recomendado = getattr(det, "recommended_model", None) if det is not None else None

    # TRES sinais, porque cada um sozinho tem um buraco -- e o nosso caminho e'
    # streaming, onde o primeiro nao aparece.
    #
    #   usage.iterations  -- o "served-by" canonico. Medido em 08/08 13h25: NAO
    #                        veio na recusa pelo tool_runner com stream=True.
    #   bloco `fallback`  -- em streaming a troca chega como content_block comum,
    #                        marcando o ponto de virada. E' o sinal do stream.
    #   msg.model         -- se quem respondeu nao e' quem pedimos, alguem mais
    #                        rodou. Pega o caso sticky, que nao emite bloco.
    iteracoes = getattr(getattr(msg, "usage", None), "iterations", None) or []
    conteudo = getattr(msg, "content", None) or []
    servido_por = getattr(msg, "model", None)
    rodou = (
        any(getattr(i, "type", None) == "fallback_message" for i in iteracoes)
        or any(getattr(b, "type", None) == "fallback" for b in conteudo)
        or bool(servido_por and servido_por != cfg.MODEL_ADVOGADO)
    )

    if recomendado:
        partes.append(
            f"o fallback NAO foi tentado (rate limit ou sobrecarga); "
            f"o servidor sugere retry direto em {recomendado}"
        )
    elif rodou:
        quem = f" ({servido_por})" if servido_por else ""
        partes.append(f"o fallback rodou{quem} e tambem recusou -- a cadeia inteira negou")
    else:
        # Terceiro estado aplicado ao proprio diagnostico: nao inventar causa.
        partes.append(
            f"nenhum dos tres sinais de fallback apareceu (servido por "
            f"{servido_por or 'modelo nao informado'}) -- nao da' para afirmar se "
            "a cadeia recusou ou se o fallback nao chegou a ser tentado"
        )
    return " | ".join(partes)


def _soma(uso: dict, u) -> None:
    if not u:
        return
    for campo, chave in (
        ("input_tokens", "tokens_entrada"),
        ("output_tokens", "tokens_saida"),
        ("cache_read_input_tokens", "cache_read"),
        ("cache_creation_input_tokens", "cache_write"),
    ):
        uso[chave] += getattr(u, campo, 0) or 0


def julga(acusacao: dict, diff: str, contexto: str = "") -> dict:
    """Uma acusacao. Devolve o veredicto que o juiz vai ler.

    `contexto` e' o bloco dos arquivos do PR, montado UMA vez pelo orquestrador
    e passado igual para todas as acusacoes -- ele entra no prefixo cacheado.
    Vazio mantem o comportamento anterior, com o advogado lendo por ferramenta.
    """
    id_ = acusacao.get("id", "sem_id")
    ferramentas.define_acusacao(id_)
    inicio = time.time()
    uso = {"tokens_entrada": 0, "tokens_saida": 0, "cache_read": 0, "cache_write": 0}
    v: dict = {
        "id": id_, "veredito": "INCONCLUSIVO", "severidade": "BAIXA",
        "prova_ponta_a_ponta": False, "motivo": "o loop nao chegou a concluir",
        "voltas": 0, "erro": None,
        # Alimentam a R3b do juiz. Sao contagem de OBSERVACAO, nao de tentativa:
        # o advogado ja disse PROVADO com as cinco chamadas falhando.
        "ferramentas_ok": 0, "ferramentas_erro": 0,
    }

    try:
        runner = _cliente().beta.messages.tool_runner(
            model=cfg.MODEL_ADVOGADO,
            max_tokens=cfg.MAX_TOKENS_ADVOGADO,
            # Teto do SDK. O break do for abaixo e' redundante de proposito:
            # advogado que nunca para de pedir ferramenta e' o jeito mais rapido
            # de perder a tarde, e uma so das duas travas ja falhou em teste.
            max_iterations=cfg.MAX_VOLTAS_LOOP,
            # Obrigatorio, nao preferencia: com max_tokens alto o SDK recusa a
            # chamada nao-streaming ("Streaming is required for operations that
            # may take longer than 10 minutes"). E precisamos do max_tokens alto
            # porque no Opus 5 ele cobre raciocinio + resposta somados.
            stream=True,
            thinking={"type": "adaptive"},
            output_config={
                "effort": cfg.EFFORT,
                # O modelo SABE que tem orcamento e fecha o parecer em vez de
                # ser cortado no meio.
                "task_budget": {"type": "tokens", "total": cfg.TASK_BUDGET_TOKENS},
            },
            betas=["task-budgets-2026-03-13", "server-side-fallback-2026-07-01"],
            # Recusa do classificador de ciberseguranca vai para o Opus 4.8
            # sozinha, em vez de derrubar a categoria carro-chefe ao vivo.
            fallbacks="default",
            system=[{"type": "text", "text": SISTEMA.replace("{teto}", str(cfg.MAX_VOLTAS_LOOP)),
                     "cache_control": {"type": "ephemeral"}}],
            tools=ferramentas.TOOLS,
            messages=[{"role": "user", "content": [
                # O diff e os arquivos vem ANTES da acusacao: prefixo identico
                # nas N chamadas, entao o cache le a ~10% em vez de reprocessar
                # tudo. `cache_control` marca o FIM do trecho cacheado, por isso
                # ele fica no ultimo bloco compartilhado -- os arquivos entram
                # DENTRO da fronteira, e a acusacao (que muda) fica fora.
                {"type": "text", "text": f"# Diff do PR sob revisao\n\n{diff}"},
                {"type": "text", "text": contexto or "# (sem bloco de arquivos)",
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": _prompt_da_acusacao(acusacao)},
            ]}],
        )

        ultima = None
        historico: list = []  # espelho da conversa, para o fechamento abaixo
        estourou = False
        blocos = 0   # resultados devolvidos, inclusive os que nem nos alcancaram
        for turno in runner:
            # Com stream=True cada iteracao entrega um stream, nao a mensagem:
            # get_final_message() da a mensagem acumulada daquela volta.
            msg = turno.get_final_message() if hasattr(turno, "get_final_message") else turno
            v["voltas"] += 1
            _soma(uso, getattr(msg, "usage", None))
            ultima = msg

            historico.append({"role": "assistant",
                              "content": _replicavel(msg.content)})
            resposta_tool = runner.generate_tool_call_response()
            if resposta_tool is not None:
                historico.append(resposta_tool)
                blocos += _conta_blocos(resposta_tool)
                # O desfecho e' consolidado DEPOIS do laco, do registro das
                # ferramentas -- aqui so' se conta quantos resultados voltaram.
                _consolida_ferramentas(v, id_, blocos)

            # stop_reason ANTES de content, sempre. Uma recusa vem como HTTP 200
            # com content vazio, e ler content[0] vira IndexError no meio da
            # rodada.
            if getattr(msg, "stop_reason", None) == "refusal":
                v["erro"] = _diagnostico_da_recusa(msg)
                break

            if v["voltas"] >= cfg.MAX_VOLTAS_LOOP:
                estourou = True
                break
            if time.time() - inicio > cfg.TIMEOUT_ACUSACAO_S:
                estourou = True
                v["timeout"] = True
                break

        if estourou:
            # Bater no teto NAO pode custar a peritagem inteira. Uma chamada
            # final SEM ferramentas obriga o veredito a partir do que ele ja
            # descobriu -- e se nao descobriu nada, ele mesmo diz INCONCLUSIVO
            # com o que tentou, que e' o texto que o parecer precisa.
            v["fechamento_forcado"] = True
            try:
                final = _cliente().beta.messages.create(
                    model=cfg.MODEL_ADVOGADO,
                    max_tokens=4000,
                    output_config={"effort": "low"},
                    tool_choice={"type": "none"},
                    # messages.create nao aceita os objetos do @beta_tool, so o
                    # tool_runner aceita. E as definicoes precisam estar aqui de
                    # qualquer forma: o historico contem blocos tool_use, e a
                    # API rejeita historico com tool_use sem as tools declaradas.
                    tools=[t.to_dict() for t in ferramentas.TOOLS],
                    system=SISTEMA.replace("{teto}", str(cfg.MAX_VOLTAS_LOOP)),
                    messages=[*historico, {"role": "user", "content": FECHAMENTO}],
                )
                _soma(uso, getattr(final, "usage", None))
                if getattr(final, "stop_reason", None) == "refusal":
                    v["erro"] = "recusa do classificador no fechamento"
                else:
                    v.update(_parse_veredicto(_texto_final(final)))
                    v["id"] = id_
            except Exception as e:
                v["erro"] = f"fechamento falhou: {type(e).__name__}: {e}"
        elif v["erro"] is None and ultima is not None:
            v.update(_parse_veredicto(_texto_final(ultima)))
            v["id"] = id_

    except Exception as e:
        v["erro"] = f"{type(e).__name__}: {e}"

    if v["erro"]:
        # Falha de execucao nunca e' absolvicao. O juiz aplica a R3 de novo em
        # cima disto -- duas travas, porque esta e' a que mais custa errar.
        v["veredito"] = "INCONCLUSIVO"
        v["motivo"] = v["erro"]

    v.update(uso)
    v["segundos"] = round(time.time() - inicio, 1)
    return v


def sonda_api() -> tuple[bool, str]:
    """A API da Anthropic responde? Uma chamada de 1 token, antes de gastar.

    Mora AQUI e nao em `ferramentas.autoteste` de proposito: `ferramentas.py`
    tem regra de ZERO chamada de LLM, e ela e' arquitetural -- e' o que faz a
    pericia inteira ser conferivel com pytest. Quem fala com a API e' o
    advogado, entao a sonda e' dele.

    🚨 Medido em 14/08: a chave expirou entre uma rodada e outra. O pre-voo
    conferia read_file, grep e http_request -- tudo que NAO custa -- e deixava
    passar a unica coisa que custa. A rodada montou contencao, copiou banco,
    gastou 30s e produziu seis INCONCLUSIVOs de autenticacao. Uma chamada de 1
    token teria dito "chave invalida" no primeiro segundo.

    Devolve (ok, detalhe). Nunca levanta: quem decide abortar e' o orquestrador.
    """
    if not cfg.ANTHROPIC_API_KEY:
        return False, "ANTHROPIC_API_KEY ausente"
    try:
        r = _cliente().messages.create(
            model=cfg.MODEL_PROMOTOR, max_tokens=1,
            messages=[{"role": "user", "content": "ok"}])
        return True, f"{cfg.MODEL_PROMOTOR} respondeu ({r.usage.input_tokens} tokens)"
    except Exception as e:
        msg = str(e)
        baixo = msg.lower()
        # Chave e saldo tem consertos DIFERENTES, e a mensagem crua nao ajuda
        # quem esta com pressa. Distinguir aqui custa tres linhas.
        if "authentication_error" in baixo or "invalid_api_key" in baixo:
            return False, ("a CHAVE foi rejeitada (invalida ou revogada) -- "
                           "gere outra e troque em hack2l/.env")
        if "credit balance" in baixo or "insufficient" in baixo:
            return False, "SALDO esgotado na conta -- a chave esta ok"
        if "rate_limit" in baixo:
            return False, "limite de taxa: nao e' chave nem saldo, tente daqui a pouco"
        return False, f"{type(e).__name__}: {msg[:200]}"


def contexto_dos_arquivos(diff: str) -> str:
    """Os arquivos tocados pelo diff, para entrar no bloco CACHEADO.

    Montado UMA vez por rodada e reusado nas N acusacoes -- e' o que faz o
    cache ler. Recalcular por acusacao daria o mesmo texto (a lista e' ordenada
    e o conteudo vem do disco), mas gastaria N leituras para nada.

    O conteudo e' exatamente o que `read_file` devolveria, `_corta` incluso.
    Isso e' de proposito: assim "nao peca estes arquivos" e' literalmente
    verdade, e o advogado nao perde nada por nao chamar a ferramenta.
    """
    if not cfg.CONTEXTO_ARQUIVOS:
        return ""
    # ORDENADO: a ordem de um set varia entre processos, e prefixo que varia e'
    # prefixo que nao cacheia -- cache_read viria zero e ninguem perceberia.
    caminhos = sorted(fontes.arquivos_do_diff(diff))
    if not caminhos:
        return ""

    # UMA resolucao de worktree para todos os arquivos: _worktree_de dispara
    # git a cada chamada, e aqui sao dezenas de arquivos do mesmo lado.
    try:
        raiz = ferramentas._worktree_de("head")
    except Exception:
        return ""   # sem worktree nao ha bloco; o advogado le por ferramenta

    partes, total, fora = [], 0, []
    for c in caminhos:
        ferramentas._abre_chamada()
        texto = ferramentas._read_file(c, raiz=raiz)
        if ferramentas.falhou_a_chamada():
            fora.append(f"{c} (nao abriu)")
            continue
        if total + len(texto) > cfg.CONTEXTO_MAX_CHARS:
            fora.append(f"{c} (fora do teto)")
            continue
        partes.append(f"### {c}\n{texto}")
        total += len(texto)
    ferramentas._abre_chamada()   # nao deixa marca pendurada para a 1a tool
    if not partes:
        return ""

    cabeca = (
        "# Os arquivos que o PR toca, na integra\n\n"
        "Ja estao aqui, exatamente como `read_file` os devolveria. NAO chame "
        "`read_file` para nenhum deles -- voce nao receberia nada novo, e "
        "gastaria uma volta do laco.\n\n"
    )
    rodape = ""
    if fora:
        # Dizer o que ficou de fora e' obrigatorio: sem isso o advogado assume
        # que o que nao esta aqui nao existe, e deixa de ler o que precisava.
        rodape = ("\n### Fora deste bloco, use `read_file`\n"
                  + "\n".join(f"- {x}" for x in fora) + "\n")
    return cabeca + "\n\n".join(partes) + "\n" + rodape


def _conta_blocos(resposta_tool) -> int:
    """Quantos resultados de ferramenta voltaram nesta volta. Nunca levanta.

    Isto NAO decide sucesso ou fracasso -- quem decide e' a propria ferramenta,
    em `ferramentas.desfecho_da_acusacao`, porque ela e' quem sabe se falhou.
    Ate' 13/08 quem decidia aqui era `texto.startswith("ERRO")`, e uma
    ferramenta que falhasse sem o prefixo passava batida bem debaixo da R3b.

    O que este contador existe para pegar e' o VAO do registro: chamada que a
    API rejeitou antes de chegar ao nosso codigo (input invalido, tool
    inexistente) devolve bloco e nao gera registro. Bloco a mais que registro =
    chamada que nao observou nada, e isso conta como erro.
    """
    conteudo = resposta_tool.get("content") if isinstance(resposta_tool, dict) else None
    if not isinstance(conteudo, list):
        return 0
    return sum(1 for b in conteudo
               if isinstance(b, dict) and b.get("type") == "tool_result")


# Blocos que a API DEVOLVE mas NAO ACEITA de volta. O `fallback` chega quando o
# beta de fallback do servidor entra em acao -- ver o CLAUDE.md, "o fallback do
# Opus".
#
# 🚨 Medido em 15/08: o fechamento forcado remontava o historico com ele dentro e
# a API respondia 400 ("Input tag 'fallback' ... does not match any of the
# expected tags"). O fechamento e' justamente a rede que impede o teto de voltas
# de custar a pericia inteira -- ela caiu no caso em que mais importava, e a
# acusacao virou INCONCLUSIVO com um erro de SDK no lugar do parecer.
#
# ⚠️ Lista de PERMISSAO, e nao de bloqueio: bloquear exige conhecer todo tipo
# novo que a API venha a inventar, e um tipo desconhecido derrubaria o
# fechamento de novo. O que nao se sabe replicar, nao se replica.
_REPLICAVEIS = {"text", "tool_use", "thinking", "redacted_thinking"}


def _replicavel(conteudo):
    """Só os blocos que a API aceita receber de volta numa nova chamada."""
    if not isinstance(conteudo, list):
        return conteudo
    fora = [b for b in conteudo
            if getattr(b, "type", None) in _REPLICAVEIS
            or (isinstance(b, dict) and b.get("type") in _REPLICAVEIS)]
    # Conteudo vazio e' rejeitado pela API. Melhor um marcador de texto do que
    # uma mensagem que nao pode ser enviada.
    return fora or [{"type": "text", "text": "(volta sem conteudo replicavel)"}]


def _consolida_ferramentas(v: dict, id_acusacao: str, blocos: int) -> None:
    """Fecha a contagem que a R3b le, juntando as duas visoes.

    IDEMPOTENTE de proposito -- ATRIBUI, nunca acumula. E' chamada dentro do
    laco, entao sair por recusa, timeout ou teto de voltas deixa a contagem
    correta em qualquer ponto de saida, sem precisar repetir a consolidacao em
    cada `break`. Guarda que depende de alguem lembrar de chama-la no caminho
    de erro e' guarda que fica muda no caminho de erro.
    """
    ok, erro = ferramentas.desfecho_da_acusacao(id_acusacao)
    # Bloco devolvido sem registro correspondente = chamada que nao chegou a
    # executar. Nao observou nada, entao e' erro -- nunca sucesso. O default
    # tem que cair para o lado de INCONCLUSIVO, que e' o estado honesto.
    nao_executadas = max(0, blocos - (ok + erro))
    v["ferramentas_ok"] = ok
    v["ferramentas_erro"] = erro + nao_executadas


def _prompt_da_acusacao(a: dict) -> str:
    return (
        "# A acusacao que voce vai julgar\n\n"
        f"- categoria: {a.get('categoria', '?')}\n"
        f"- local: {a.get('local', '?')}\n"
        f"- hipotese: {a.get('hipotese', '?')}\n"
        # "nenhum citado" nao e' o mesmo que "nao ha regra violada", e o
        # advogado precisa saber a diferenca: sem arbitro a prova tem que ficar
        # de pe sozinha, e e' ela que vai sustentar a severidade (regra R1).
        f"- arbitro: {arbitro.formata(a.get('arbitro'))}\n"
        f"- provado_se: {a.get('provado_se', '?')}\n\n"
        "Prove ou refute. Termine com o JSON."
    )

