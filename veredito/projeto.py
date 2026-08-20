"""hack2l / Veredito -- o projeto sob revisao, descrito em `veredito.yml`.

Ate' 14/08 as quatro contas de teste estavam chumbadas em `config.py`. Isso
fazia a prova ponta a ponta -- a unica via que sustenta CRITICA junto com o
arbitro -- funcionar so' no repositorio do desafio. Este modulo tira isso do
codigo e poe num arquivo do PROJETO.

A divisao que vale:

    veredito.yml  ->  o PROJETO revisado: como sobe, como autentica, onde e'
                      seguro escrever
    .env          ->  como NOS operamos: modelo, orcamento, TOP_N, timeouts

⚠️ AUSENTE NAO E' VAZIO. Sem `veredito.yml` o Veredito continua rodando, com
leitura e grep -- e diz em voz alta o que perdeu. Um projeto que nao descreve
suas contas nao ganha prova ponta a ponta, e isso e' um limite honesto, nao um
erro. Cair calado seria pior: a rodada sairia toda em MEDIA e pareceria o
produto nao funcionando.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


class ProjetoInvalido(ValueError):
    """O arquivo existe mas descreve algo que nao da' para usar.

    Levanta em vez de degradar: arquivo escrito errado e' engano do operador, e
    seguir com metade dele produziria uma rodada que parece boa e nao e'.
    Ausencia total, essa sim, degrada -- ver o docstring do modulo.
    """


def caminho(raiz_do_projeto: Path, explicito: str = "",
            no_worktree: Path | None = None) -> Path | None:
    """Onde esta o `veredito.yml` deste projeto.

    Ordem: o que o operador mandou > o do proprio projeto > o nosso, em
    `projetos/`. A do meio e' a que vale para o produto -- o arquivo mora junto
    do codigo que descreve, e e' assim que a Action vai achar. `projetos/` so'
    existe porque o `desafio` e' de terceiro e nao da' para commitar dentro.

    🚨 `no_worktree` entrou em 18/08 e e' o que faz "o arquivo mora junto do
    codigo" virar verdade pela porta da frente. `revisa_pr.py` monta o alvo com
    `git init` + `fetch`: o clone nao tem working tree, entao procurar em
    `<clone>/veredito.yml` nunca acha nada -- em repositorio nenhum. Quem tem
    os arquivos e' o worktree do BASE.

    ⚠️ O `projetos/<nome>.yml` continua sendo procurado pelo nome do CLONE, e
    nao pelo do worktree: o worktree se chama `base`, e `projetos/base.yml` nao
    quer dizer nada.
    """
    if explicito:
        p = Path(explicito).expanduser()
        return p if p.is_file() else None
    for raiz in (no_worktree, raiz_do_projeto):
        if raiz is not None and (raiz / "veredito.yml").is_file():
            return raiz / "veredito.yml"
    nosso = Path(__file__).resolve().parents[1] / "projetos" / f"{raiz_do_projeto.name}.yml"
    return nosso if nosso.is_file() else None


def carrega(caminho_do_yml: Path | None) -> dict:
    """Le e valida. Devolve {} quando nao ha arquivo -- ausencia e' legitima."""
    if caminho_do_yml is None:
        return {}
    try:
        dado = yaml.safe_load(caminho_do_yml.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as e:
        raise ProjetoInvalido(f"{caminho_do_yml}: nao consegui ler ({e})") from e
    if dado is None:
        return {}
    if not isinstance(dado, dict):
        raise ProjetoInvalido(f"{caminho_do_yml}: a raiz precisa ser um mapa")
    _valida(dado, caminho_do_yml)
    return dado


def _valida(d: dict, onde: Path) -> None:
    contas = d.get("contas")
    if contas is None:
        return          # projeto sem contas: perde prova ponta a ponta, e ok
    if not isinstance(contas, list) or not contas:
        raise ProjetoInvalido(f"{onde}: `contas` precisa ser uma lista nao vazia")

    for c in contas:
        if not isinstance(c, dict):
            raise ProjetoInvalido(f"{onde}: cada conta precisa ser um mapa")
        faltando = [k for k in ("nome", "email") if not c.get(k)]
        if faltando:
            raise ProjetoInvalido(
                f"{onde}: conta {c.get('nome', '?')} sem {', '.join(faltando)}")

        # A senha vem de UMA das duas: literal no arquivo, ou o NOME de uma
        # variavel de ambiente. Ver o docstring de `_senha_de`.
        tem_literal = bool(c.get("senha"))
        tem_variavel = bool(c.get("senha_em"))
        if tem_literal and tem_variavel:
            # Duas fontes para o mesmo valor divergem em silencio -- foi o que
            # a chave da API custou em 14/08, quatro tentativas. Aqui sairia
            # pior: o login usaria uma e o operador leria a outra no arquivo.
            raise ProjetoInvalido(
                f"{onde}: conta {c['nome']} declara `senha` E `senha_em`. "
                "Escolha uma -- duas fontes para o mesmo valor divergem em silencio")
        if not tem_literal and not tem_variavel:
            raise ProjetoInvalido(
                f"{onde}: conta {c['nome']} sem `senha` nem `senha_em`")

    nomes = [c["nome"] for c in contas]
    if len(set(nomes)) != len(nomes):
        raise ProjetoInvalido(f"{onde}: ha contas com o mesmo `nome`")


def _senha_de(conta: dict, ambiente=None) -> str | None:
    """A senha desta conta, ou None se ela nao esta disponivel AGORA.

    🚨 POR QUE `senha_em` EXISTE -- 19/08.

    O `veredito.yml` mora na RAIZ DO PROJETO REVISADO e e' commitado. Senha
    literal ali e' senha em controle de versao, e a objecao nao e' de percepcao:

      - scanner de segredo (GitGuardian, TruffleHog, o do proprio GitHub)
        dispara pela FORMA do valor, entao renomear o campo nao resolve -- e se
        resolvesse seria pior, porque estaria driblando o controle e mantendo a
        pratica;
      - o advogado le o repositorio sob revisao por worktree, `read_file` nao
        bloqueia arquivo nenhum, nao ha redacao em lugar algum do pipeline, e o
        parecer e' POSTADO NO PR. Uma acusacao de "credencial em codigo" -- que
        e' exatamente o que as lentes `padroes` e `vazamento` procuram -- levaria
        o advogado a ler o `veredito.yml` e poder citar a senha num comentario
        publico. O arquivo se chama config e contem a palavra senha varias
        vezes: e' isca para as lentes que nos mesmos rodamos.

    Com `senha_em` o arquivo carrega o NOME da variavel e nunca o valor. Nao
    sobra nada com forma de senha na arvore, e o pedido de onboarding vira
    "adicione tres valores aos secrets da Action" -- que todo time ja faz.

    ⚠️ Devolve None, nunca "". Senha vazia faria o `_token` POSTAR credencial
    vazia no endpoint de login do cliente.
    """
    if conta.get("senha"):
        return str(conta["senha"])
    variavel = conta.get("senha_em")
    if not variavel:
        return None
    amb = os.environ if ambiente is None else ambiente
    valor = amb.get(str(variavel))
    return str(valor) if valor else None


def resolve_contas(d: dict, ambiente=None) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """({nome: (email, senha)}, [o que nao deu para resolver]).

    🚨 A conta que nao resolve NAO ENTRA no dicionario, e a lista do que faltou
    sai junto de proposito -- os dois fatos precisam viajar juntos.

    O buraco que isso fecha: se `usuarios()` simplesmente pulasse a conta sem
    ninguem contar, a rodada sairia com menos contas do que o projeto declarou,
    e as guardas do `avisos()` continuariam passando -- elas contavam a lista
    DECLARADA, nao a resolvida. Tres contas no arquivo, uma variavel esquecida,
    `len(contas) >= 3` verde, e o login falhando la' na frente, longe da causa.
    Guarda condicionada a um sinal que o operador satisfaz sem o fato ser
    verdade: o padrao de bug deste projeto.

    ⚠️ A lista de faltantes nomeia a VARIAVEL, nunca o valor.
    """
    resolvidas: dict[str, tuple[str, str]] = {}
    faltando: list[str] = []
    for c in d.get("contas") or []:
        senha = _senha_de(c, ambiente)
        if senha is None:
            faltando.append(
                f"{c['nome']}: a variavel {c.get('senha_em')!r} nao esta no ambiente")
            continue
        resolvidas[c["nome"]] = (c["email"], senha)
    return resolvidas, faltando


def usuarios(d: dict, ambiente=None) -> dict[str, tuple[str, str]]:
    """{nome: (email, senha)} -- o formato que `ferramentas._token` consome.

    So' as contas que RESOLVERAM. Ver `resolve_contas`.
    """
    return resolve_contas(d, ambiente)[0]


def controle_negativo(d: dict, ambiente=None) -> str | None:
    """A conta que nao possui nada.

    🚨 E' a mais valiosa da lista e a que ninguem lembra de criar. Qualquer dado
    de outro usuario que apareca para ela e' vazamento, sem precisar
    interpretar -- foi ela que provou a CRITICA de 14/08. Deduzida de
    `possui: 0` para o operador nao ter que declarar duas vezes e as duas
    divergirem.

    ⚠️ So' conta se ela RESOLVEU: controle negativo em que nao da' para logar
    nao e' controle negativo, e apontar um sem senha faria a rodada acreditar
    que tem a peca que sustenta a CRITICA de vazamento.
    """
    resolvidas, _ = resolve_contas(d, ambiente)
    for c in d.get("contas") or []:
        if c.get("possui") == 0 and c["nome"] in resolvidas:
            return c["nome"]
    return None


def ensombrado_pelo_env(d: dict, ambiente: dict) -> list[str]:
    """O que o projeto declarou e o nosso `.env` esta sobrepondo.

    🚨 DESCOBERTO EM 15/08, apontando o Veredito para o segundo projeto.

    A precedencia e' `variavel de ambiente > veredito.yml > padrao`, e ela existe
    para permitir um teste pontual. Mas o `.env` do Veredito e' PERSISTENTE: ele
    tinha `APP_API_URL=http://127.0.0.1:8000` do desafio, e a bancada declara
    8100. Resultado: a rodada revisaria o codigo da bancada CONVERSANDO COM O APP
    DO DESAFIO -- e o pre-voo diria `health -> 200`, porque o outro app responde.

    Medicao inteira invalida, sem um unico sinal de erro.

    ⚠️ `variaveis_ensombradas` do config NAO pega este caso: la' a comparacao e'
    entre o `.env` e o ambiente, e aqui os dois concordam. O conflito e' entre o
    `.env` e o ARQUIVO DO PROJETO -- outra fronteira, outra guarda. E' o padrao
    de bug do projeto de novo: a guarda existe e esta muda na fronteira que
    ninguem tinha olhado.
    """
    fora = []
    app = d.get("app") or {}
    banco = d.get("banco") or {}
    pares = [
        ("APP_API_URL", app.get("api")),
        ("APP_WEB_URL", app.get("web")),
        ("APP_SAUDE", app.get("saude")),
        ("BANCO_APP_ORIGEM", banco.get("nome")),
        ("BANCO_DESCARTAVEL", banco.get("descartavel_testes")),
        ("BANCO_APP", banco.get("descartavel_app")),
    ]
    for nome, do_projeto in pares:
        vigente = ambiente.get(nome)
        if do_projeto and vigente and str(vigente).rstrip("/") != str(do_projeto).rstrip("/"):
            fora.append(f"{nome}: o projeto declara {do_projeto!r} e esta valendo "
                        f"{vigente!r}")
    return fora


def avisos(d: dict, contexto_resolvido: Path | None = None,
           ambiente=None) -> list[str]:
    """O que este projeto NAO vai conseguir provar, dito antes de gastar.

    Sai no pre-voo. Descobrir no fim da rodada que faltava conta e' pagar
    US$1,30 para aprender uma coisa que o arquivo ja sabia.

    🚨 CONTA AS RESOLVIDAS, nunca as declaradas -- 19/08, com o `senha_em`. A
    contagem sobre a lista do arquivo e' a mesma classe de erro dos 94 arbitros
    "preenchidos": mede a existencia da linha, nao a existencia do fato.
    """
    fora = []
    # 🚨 "Nao declarei contexto" e "declarei e o caminho esta errado" sao coisas
    # diferentes, e so' a segunda e' bug. Tratar as duas como silencio faz um
    # caminho digitado errado sair como arbitro `null` -- que parece o
    # repositorio nao documentar nada, e nao um erro de uma linha no yml.
    if d.get("contexto") and contexto_resolvido is not None \
            and not contexto_resolvido.is_file():
        fora.append(f"`contexto` aponta para {contexto_resolvido}, que nao existe "
                    "-- o arbitro vai sair `null` por engano, nao por honestidade")
    contas = d.get("contas") or []
    if not contas:
        fora.append("sem `contas`: nao ha prova ponta a ponta, so' leitura e grep "
                    "-- e nada passa de MEDIA pela R2")
        return fora

    resolvidas, faltando = resolve_contas(d, ambiente)
    # Dito ANTES da contagem: a causa explica o numero que vem logo abaixo, e
    # "so' 2 contas" sem a causa manda o operador editar o yml -- que esta
    # certo. O que falta e' a variavel, e o aviso nomeia qual.
    for f in faltando:
        fora.append(f"conta declarada e NAO disponivel -- {f}")

    if len(resolvidas) < 3:
        # A regra do Carlos, 06/08: isolamento precisa de tres contas.
        declaradas = (f" ({len(contas)} declarada(s), {len(faltando)} sem a "
                      "variavel no ambiente)") if faltando else ""
        fora.append(f"so' {len(resolvidas)} conta(s) utilizavel(is){declaradas}: "
                    "provar isolamento entre usuarios pede pelo menos tres")
    if controle_negativo(d, ambiente) is None:
        fora.append("nenhuma conta utilizavel com `possui: 0`: sem controle "
                    "negativo, vazamento vira interpretacao em vez de fato")
    if not d.get("contexto"):
        fora.append("sem `contexto`: o arbitro sai `null` e nada sustenta CRITICA "
                    "por regra (R1)")
    return fora
