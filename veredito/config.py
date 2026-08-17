"""hack2l / Veredito -- configuracao.

Nada de porta, URL ou caminho chumbado no resto do codigo. Duas maquinas com
portas diferentes constroem isto e a apresentacao roda na outra; tudo o que
muda entre elas passa por aqui.

Espelha a convencao no 1 do repo alvo: configuracao le-se de um lugar so.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from . import projeto

RAIZ = Path(__file__).resolve().parents[1]

# ⚠️ SEM override=True, de proposito. O padrao do dotenv e' NAO sobrescrever
# variavel de ambiente que ja existe -- e e' isso que faz `APP_EM_BANCO_
# DESCARTAVEL=1 py -3.12 ...` funcionar na linha de comando. Ligar o override
# mataria essa forma de rodar.
#
# O preco e' que uma variavel do sistema VENCE o .env, em silencio. Quem paga
# esse preco tem que ser avisado: `variaveis_ensombradas` abaixo.
load_dotenv(RAIZ / ".env")


def variaveis_ensombradas() -> list[str]:
    """Nomes cujo valor no .env NAO e' o que esta valendo.

    🚨 Custou quatro tentativas em 14/08. A chave da Anthropic estava na
    variavel de ambiente do Windows (via `setx`) E no .env. A do Windows vencia.
    Trocar o .env nao mudava nada, o erro continuava IDENTICO, e nada apontava
    para a causa -- o unico sinal era um 401 que parecia problema de conta.

    Devolve so' os NOMES. Valor de variavel ensombrada e' quase sempre segredo,
    e imprimir os dois lados para comparar seria vazar a chave no log da rodada.
    """
    try:
        do_arquivo = dotenv_values(RAIZ / ".env") or {}
    except OSError:
        return []
    return sorted(
        nome for nome, valor in do_arquivo.items()
        if valor is not None
        and os.environ.get(nome) is not None
        and os.environ[nome] != valor
    )


def _s(nome: str, padrao: str) -> str:
    return os.getenv(nome) or padrao


def _b(nome: str, padrao: bool) -> bool:
    v = (os.getenv(nome) or "").strip().lower()
    return v in ("1", "true", "sim", "yes") if v else padrao


def _i(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome) or padrao)
    except ValueError:
        return padrao


# --- repo sob revisao -------------------------------------------------------
DESAFIO = (RAIZ / _s("CHALLENGE_REPO", "../hack2l-challenge")).resolve()
BRANCH_PR = _s("PR_BRANCH", "pr/document-sharing")
BRANCH_BASE = _s("BASE_BRANCH", "main")

# --- o projeto sob revisao, descrito por ele mesmo --------------------------
#
# 🚨 Ate' 14/08 as contas de teste estavam CHUMBADAS neste arquivo, e era o que
# fazia metade do produto so' funcionar no desafio: a prova ponta a ponta --
# unica via que sustenta CRITICA junto com o arbitro -- dependia de quatro
# emails escritos no NOSSO codigo.
#
# A divisao: `veredito.yml` descreve o PROJETO (como sobe, como autentica, onde
# e' seguro escrever); o `.env` descreve como NOS operamos (modelo, orcamento,
# TOP_N, timeouts). O primeiro muda a cada cliente, o segundo nao.
#
# Precedencia: variavel de ambiente > veredito.yml > padrao daqui. Assim
# `APP_API_URL=... py -3.12 ...` continua servindo para um teste pontual.
#
# Carregado AQUI, logo depois de DESAFIO, porque quase tudo abaixo consome.
PROJETO_YML = projeto.caminho(DESAFIO, _s("VEREDITO_YML", ""))
PROJETO = projeto.carrega(PROJETO_YML)

_app = PROJETO.get("app") or {}
_banco = PROJETO.get("banco") or {}

COMPOSE = DESAFIO / (_app.get("compose") or "docker-compose.yml")

# Worktrees ficam FORA dos dois repos: dentro do nosso virariam commit, dentro
# do deles sujariam a arvore que o app esta servindo.
WORKTREES = Path(_s("WORKTREES_DIR", str(DESAFIO.parent / ".worktrees"))).resolve()

# --- nossas saidas ----------------------------------------------------------
#
# SAIDAS e' a RAIZ das saidas (rodadas/, final/, e as pastas dos experimentos).
# O que uma rodada produz NAO mora aqui -- mora em RODADA, abaixo.
SAIDAS = RAIZ / "saidas"
RODADAS = SAIDAS / "rodadas"

# O ponteiro para a ultima rodada gravada. Arquivo de texto, e nao symlink, de
# proposito: symlink no Windows exige modo desenvolvedor ou admin, e uma
# ferramenta que so' funciona na maquina de um dos socios nao serve.
PONTEIRO = RODADAS / "ULTIMA"

# 🚨 POR QUE ISTO EXISTE
#
# Ate' 13/08 toda rodada escrevia nos MESMOS caminhos: saidas/veredictos.json e
# artefatos/<tipo>_<id>. Namespace plano, chave que se repete entre rodadas --
# entao cada rodada apagava a anterior. Medido no commit cfeb64b: 11 artefatos
# sobrescritos, e as rodadas de 11/08 16h e 21h so' sobrevivem no que a seguinte
# nao pisou. Dado que ja foi PAGO para produzir (US$~1,30 por rodada) e que nao
# da para recuperar.
#
# ⚠️ E os artefatos entram junto, nao so' as saidas. Sao a EVIDENCIA -- num
# produto cuja regra central e' "sem artefato nao ha prova", perder o artefato e
# guardar o veredito e' guardar exatamente a metade que nao vale nada.
#
# RODADA e ARTEFATOS sao REBINDADOS por nova_rodada()/usa_ultima_rodada(). Todo
# consumidor acessa `cfg.RODADA` no momento da chamada, nunca faz `from .config
# import RODADA` -- e' o mesmo motivo pelo qual os testes ja conseguem trocar
# cfg.ARTEFATOS por tmp_path com monkeypatch.
RODADA = SAIDAS
ARTEFATOS = RAIZ / "artefatos"


def _rodada_do_ponteiro() -> Path | None:
    """A pasta apontada por ULTIMA, ou None se ela nao existe MAIS.

    ⚠️ Conferir o diretorio, e nao so' ler o arquivo, e' o ponto todo: o
    ponteiro e' uma string e a pasta pode ter sido apagada a mao. Ponteiro
    pendurado que passa batido faria o juiz ler uma rodada vazia e imprimir
    "0 com parecer" -- absolvicao limpa por acidente de arquivo, que e'
    precisamente o modo de falha que este produto existe para impedir.
    """
    try:
        nome = PONTEIRO.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not nome or "/" in nome or "\\" in nome:
        return None
    destino = RODADAS / nome
    return destino if destino.is_dir() else None


def nova_rodada(carimbo: str) -> Path:
    """Abre a pasta DESTA rodada e faz ULTIMA apontar para ela.

    Chamada uma vez, no comeco de `orquestrador.roda`, ANTES de qualquer
    escrita -- o pre-voo e o `llm_alvo.registra` ja gravam artefato.
    """
    global RODADA, ARTEFATOS
    destino = RODADAS / carimbo
    (destino / "artefatos").mkdir(parents=True, exist_ok=True)
    RODADA, ARTEFATOS = destino, destino / "artefatos"
    PONTEIRO.write_text(carimbo + "\n", encoding="utf-8")
    return destino


def usa_ultima_rodada() -> Path | None:
    """Aponta este processo para a ultima rodada gravada, SEM criar nada.

    E' o que sustenta a disciplina no 2 do CLAUDE.md: ajustar o juiz pela
    trigesima vez nao pode re-executar o advogado. `python -m veredito.juiz`
    sozinho tem que achar a rodada que o orquestrador acabou de gravar.

    Devolve None quando ainda nao ha rodada nenhuma -- e ai RODADA continua
    valendo saidas/ e ARTEFATOS continua valendo artefatos/, que e' onde estao
    as rodadas gravadas antes desta mudanca. Legado continua legivel.
    """
    global RODADA, ARTEFATOS
    destino = _rodada_do_ponteiro()
    if destino is None:
        return None
    RODADA, ARTEFATOS = destino, destino / "artefatos"
    return destino


# Resolve na importacao: quem so' LE (juiz avulso, script de analise) ja abre
# apontando para a ultima rodada, sem precisar saber que rodadas existem.
usa_ultima_rodada()

# --- banco descartavel do agente --------------------------------------------
#
# 🚨 Em 11/08 o advogado APAGOU o banco da aplicacao: 4 usuarios e 5 documentos.
# Nao foi bug, foi o desenho. A prova diferencial roda a suite do repositorio
# nos DOIS commits, e o commit base era anterior ao conserto do proprio autor
# ("Stop the test suite from wiping the app database"). O `DROP SCHEMA public
# CASCADE` existe IGUAL nos dois lados (conftest.py:49); o que o PR acrescentou
# foi para ONDE ele aponta.
#
# Ou seja: o perigo nao estava na mudanca, estava no codigo que a mudanca NAO
# tocou -- e que so era seguro por causa de uma protecao que ainda nao existia.
# Procurar `DROP` no diff nao pegaria: o diff nao tem nenhum.
#
# A protecao tem que vir de FORA, para nao depender de o repositorio ja ter tido
# a ideia. E' literalmente a mesma solucao que o autor do desafio adotou, so que
# imposta pelo agente e valida em qualquer commit, inclusive nos antigos.
#
# ⚠️ Isto protege o BANCO. Uma suite que dispare email de verdade ou chame API
# de pagamento continua fazendo -- banco e' o caso comum, nao blindagem total.
BANCO_DESCARTAVEL = _s("BANCO_DESCARTAVEL",
                       _banco.get("descartavel_testes") or "kb_veredito")


# --- isolamento de rede no lado BASE ----------------------------------------
#
# 🚨 O risco e' ASSIMETRICO, e essa assimetria e' a chave do desenho:
#
#   suite do HEAD -- a CI do cliente ja roda isso a cada push. Risco marginal
#                    nosso: ZERO. Se aquela suite manda email, ela ja manda.
#   suite do BASE -- ninguem roda mais. A CI dele rodou na epoca, com os
#                    segredos e os dados DAQUELA epoca. Nos rodamos hoje.
#
# Entao a contencao pesada so' vale no base -- e foi exatamente ali que o agente
# apagou o banco em 11/08.
#
# A rede interna (`docker network create --internal`) deixa o banco alcancavel e
# a internet nao: smtplib, API de pagamento e webhook morrem em rota. O que a
# suite legitimamente precisa continua funcionando.
#
# ⚠️ CUSTO REAL, e ele e' aceito conscientemente: repositorio cujo ARNES de teste
# precisa de rede externa perde a prova no base -- vira INCONCLUSIVO. Nao vira
# veredito errado, e o achado perdido e' justamente aquele cuja prova teria
# externalidade (alguem recebeu o email de verdade).
#
# 🚫 E o inconclusivo PRECISA ser rotulado. Inconclusivo em silencio incha a
# lista e faz o parecer parecer fraco por culpa nossa -- "uma lista de
# inconclusivos inflada enfraquece o parecer tanto quanto uma vazia".
REDE_ISOLADA = _s("REDE_ISOLADA", PROJETO.get("rede_isolada") or "veredito_isolada")

# A escotilha. Efeito irreversivel se pergunta ANTES, nao se descobre depois --
# e quem tem contexto para decidir e' o dono do repositorio, nao o agente.
PERMITIR_REDE_NO_BASE = _b("PERMITIR_REDE_NO_BASE", False)


# Credenciais e servico do banco, do veredito.yml.
#
# 🚨 `usuario` e `senha` SEM FALLBACK desde 17/08: `kb`/`kb` sao do desafio, e
# foi esse chumbado que fez o retrato do banco falhar contra a bancada e gravar
# `"limpo": true` em seis rodadas sem ter olhado (16/08). Consertaram o retrato
# e deixaram o padrao -- a mesma meia-correcao do `app/api/tests`.
#
# ⚠️ `servico: db` e a porta 5432 ficam: os dois projetos irmaos declaram igual,
# e sao convencao de compose, nao identidade de projeto.
BANCO_SERVICO = _s("BANCO_SERVICO", _banco.get("servico") or "db")
BANCO_USUARIO = _s("BANCO_USUARIO", _banco.get("usuario") or "")
BANCO_SENHA = _s("BANCO_SENHA", _banco.get("senha") or "")
BANCO_PORTA = _i("BANCO_PORTA", int(_banco.get("porta") or 5432))


def url_do_banco_descartavel() -> str:
    """A URL que o agente IMPOE ao rodar teste do repositorio sob revisao.

    🚨 `kb:kb@db` estava CHUMBADO aqui ate' 15/08, e o proprio comentario que
    ficava nesta linha ja dizia "num cliente isto viria do veredito.yml".
    Enquanto nao veio, a prova diferencial num projeto com outro usuario de
    banco morria com `FATAL: password authentication failed` na suite INTEIRA,
    antes de qualquer query -- e a acusacao virava INCONCLUSIVO por
    infraestrutura, parecendo limite do produto.

    Foi o quinto chumbado achado ao apontar o Veredito para o segundo projeto.
    Os quatro primeiros estao no commit anterior.
    """
    return (f"postgresql+psycopg://{BANCO_USUARIO}:{BANCO_SENHA}"
            f"@{BANCO_SERVICO}:{BANCO_PORTA}/{BANCO_DESCARTAVEL}")


# --- contexto do repositorio sob revisao ------------------------------------
# O que o repositorio documenta sobre si mesmo (PRD, criterios de aceite,
# convencoes), com arquivo e linha de cada regra. Entra no contexto dos
# promotores em tempo de execucao.
#
# 🚨 Ate 09/08 este material estava CHUMBADO dentro dos seis prompts, e por isso
# viajava para dentro de qualquer diff do mundo: 94 de 94 arbitros nos 10 PRs de
# Flask, Django, Gin, Next.js e Requests citavam os criterios de aceite do
# desafio da Vindler. Fora do Hack2L a taxa real de arbitro era ZERO.
#
# Por isso ele e' um ARQUIVO, e por isso pode ser vazio: repositorio que nao
# documenta os proprios criterios roda sem contexto, os promotores acusam do
# mesmo jeito, e o arbitro sai `null` -- que e' a resposta honesta.
# O `contexto:` do veredito.yml e' relativo ao ARQUIVO, nao ao cwd nem a' nossa
# raiz: quem escreve o yml esta pensando na arvore dele, e caminho relativo que
# muda de significado conforme quem chama e' fonte garantida de "sumiu em
# silencio" -- que aqui custaria o arbitro inteiro sair `null`.
_ctx_yml = PROJETO.get("contexto")
_ctx_padrao = (
    (PROJETO_YML.parent / _ctx_yml).resolve() if (_ctx_yml and PROJETO_YML)
    else RAIZ / "contexto" / "hack2l.md"
)
CONTEXTO = Path(_s("CONTEXTO_REPO", str(_ctx_padrao)))


def contexto_do_repo() -> str | None:
    """O bloco de contexto, ou None quando o repo nao documenta nada.

    None e vazio sao a mesma coisa de proposito: um arquivo em branco nao pode
    virar um cabecalho "Contexto do repositorio" seguido de nada, que e' um
    convite para o modelo preencher o silencio.
    """
    try:
        texto = CONTEXTO.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return texto or None

# --- app alvo ---------------------------------------------------------------
# 🚨 127.0.0.1 e' deliberado, NAO troque por localhost.
#
# Medido em 08/08 nesta maquina: 'localhost' resolve ::1 antes de 127.0.0.1, o
# Docker publica nos dois, e o caminho IPv6 aceita a conexao e nunca responde.
# Resultado: 0/8 sucesso em localhost, 8/8 em 127.0.0.1, nas tres portas.
# Isso nao da ConnectionRefused, da ReadTimeout -- entao cada chamada pendura o
# timeout inteiro antes de falhar, e a acusacao vira INCONCLUSIVO por
# infraestrutura. Em massa, a categoria de seguranca esvaziaria parecendo rigor.
#
# 🚨 E SEM `app:` DECLARADO O ENDERECO FICA VAZIO -- nao cai em 127.0.0.1:8000.
#
# Medido em 17/08, na primeira revisao de um PR de terceiro pela porta da
# frente: revisando `pallets/flask`, sem `veredito.yml`, o pre-voo imprimiu
#
#     ok  http_request  GET /health -> 200
#     ok  login         /auth/login como demo: token de 119 chars
#
# VERDE. Ele tinha feito login no app do DESAFIO, que estava no ar naquela
# porta, com a conta `demo` do desafio -- enquanto revisava o Flask.
#
# E' o item 4 dos cinco chumbados de 15/08 outra vez ("revisaria um projeto
# conversando com o app do outro, e o pre-voo diria health -> 200"), so' que a
# causa agora nao e' o `.env`: e' este padrao. O conserto de 14/08 tirou os
# valores de serem a UNICA fonte e os deixou como fallback -- e fallback que
# aponta para outro projeto e' pior que fallback nenhum, porque as sondas ficam
# verdes e a rodada segue.
#
# Contencao, nao predicao: nao adivinhar onde o app esta. Projeto que nao
# declara app NAO TEM app, e quem depende dele diz isso em voz alta.
APP_API_URL = _s("APP_API_URL", _app.get("api") or "").rstrip("/")
APP_WEB_URL = _s("APP_WEB_URL", _app.get("web") or "").rstrip("/")
APP_SAUDE = _s("APP_SAUDE", _app.get("saude") or "/health")

# A pergunta que o pre-voo, o `http_request` e a contencao passam a fazer antes
# de tocar em rede. Derivada, nunca declarada duas vezes.
TEM_APP = bool(APP_API_URL)

# Quem montou o alvo ja sabia o merge-base? O `revisa_pr.py` sabe -- ele o
# recebe do endpoint `compare` do GitHub, que enxerga a historia que o clone
# raso nao baixou. Declarado por quem sabe, nunca deduzido de uma falha:
# `commit_base` explica por que a diferenca importa.
BASE_JA_RESOLVIDO = _b("BASE_JA_RESOLVIDO", False)

# --- levantar o app, quando ele nao esta no ar ------------------------------
#
# Padrao FALSO quando o yml nao diz nada: e' o comportamento de hoje, em que o
# app e' responsabilidade de fora. Projeto que quer o contrario declara.
#
# Ligar e' seguro mesmo com o app ja rodando: `subida.app_no_ar` vira no-op
# completo nesse caso -- nao sobe, nao prepara, nao derruba. Ver as duas regras
# no cabecalho daquele modulo.
APP_SUBIR = _b("APP_SUBIR", bool(_app.get("subir")))

# Segundos de espera pela rota de saude. Container subindo nao e' app no ar, e a
# diferenca no desafio e' o warm-up de ~30s da api.
APP_ESPERA_S = _i("APP_ESPERA_S", int(_app.get("espera_s") or 120))

# Comandos de compose rodados DEPOIS de subir -- seed, migration. Lista de
# listas de argumentos, nunca string com shell: vem de arquivo do projeto
# revisado, e passar por shell seria executar texto de terceiro com as nossas
# permissoes.
#
# 🚨 So' roda se NOS levantamos os containers. Seed costuma RESETAR o banco;
# rodar num app que ja estava servindo apagaria dado que nao e' nosso.
APP_PREPARAR = _app.get("preparar") or []

# --- onde o codigo mora dentro do repositorio -------------------------------
#
# 🚨 Descoberto em 14/08 tentando usar o Veredito num SEGUNDO projeto: o
# `_roda_pytest` chumbava `app/api/app` e `app/api/tests` -- o layout do
# desafio. Ou seja, a PROVA DIFERENCIAL, que produz a evidencia mais forte do
# produto, so' funcionava num repositorio.
#
# E' a mesma classe das contas chumbadas, uma camada abaixo: tirei os usuarios
# do codigo e deixei a arvore de diretorios. So' apareceu porque um projeto
# diferente foi apontado para ele -- que e' exatamente para isso que a bancada
# existe.
#
# `montagens` = [[origem no repo, destino no container], ...]. O bind-mount e'
# obrigatorio e nao rebuild: o Dockerfile faz COPY do codigo, entao sem os -v o
# pytest roda o codigo ASSADO NA IMAGEM e a prova diferencial devolve o mesmo
# resultado nos dois lados -- falso negativo silencioso, provado com canario em
# 08/08.
#
# 🚨 SEM FALLBACK desde 17/08, pelo mesmo motivo das contas e do `app.api`: o
# padrao apontava para a arvore do desafio, e projeto que nao declara layout NAO
# TEM layout -- nunca o do vizinho. Ver `TEM_PROVA_DIFERENCIAL` abaixo.
_codigo = PROJETO.get("codigo") or {}
CODIGO_MONTAGENS = _codigo.get("montagens") or []
# `/code` e' a arvore do desafio; a bancada usa `/srv`. Sem fallback, e entra no
# criterio de `TEM_PROVA_DIFERENCIAL` abaixo: `docker run -w ""` nao roda.
CODIGO_TRABALHO = _s("CODIGO_TRABALHO", _codigo.get("trabalho") or "")

# ⚠️ SAO DOIS CAMINHOS DIFERENTES, e confundi-los custou uma rodada inteira.
#
#   testes         alvo do pytest DENTRO do container (depois das montagens)
#   testes_no_repo onde o arquivo de teste e' ESCRITO, relativo ao worktree
#
# No desafio eles divergem: a montagem manda `app/api/tests` para `/code/tests`,
# entao no disco e' `app/api/tests` e no container e' `tests`. Na bancada a
# montagem e' rasa e os dois sao `app/tests`.
#
# 🚨 Ate' 15/08 o caminho de ESCRITA estava chumbado em `app/api/tests`: a
# `prova_diferencial` gravava fora do worktree da bancada e morria com
# FileNotFoundError, e as quatro acusacoes viraram INCONCLUSIVO. A ferramenta
# que assina PROVADO nao funcionava fora do desafio -- de novo.
#
# 🚨 E em 17/08 ele mordeu de novo, na primeira revisao de um PR de terceiro
# pela porta da frente. O comentario acima ja contava a historia da bancada, e o
# conserto de la' foi trocar o valor -- nao tirar o chumbado. Revisando o
# `pallets/flask`, que nao tem `veredito.yml`, as CINCO provas diferenciais
# morreram com "app/api/tests nao existe em base", e o `erro` no artefato levou
# a R3 a converter em INCONCLUSIVO ate' uma refutacao obtida por leitura.
#
# Valor padrao que aponta para o desafio e' a quinta instancia do mesmo padrao
# (contas, APP_API_URL, -U kb do psql, py -3.12 no fontes.py, e este). A troca
# certa e' sempre a mesma: lista mantida -> criterio derivado.
CODIGO_TESTES = _s("CODIGO_TESTES", _codigo.get("testes") or "")
CODIGO_TESTES_NO_REPO = _s("CODIGO_TESTES_NO_REPO",
                           _codigo.get("testes_no_repo") or "")

# A pergunta que `prova_diferencial` e `run_tests` passam a fazer antes de
# escrever arquivo ou chamar docker. Derivada, nunca declarada duas vezes --
# irma de `TEM_APP`.
#
# Os QUATRO sao necessarios e nenhum se deduz do outro: sem `montagens` o pytest
# roda o codigo ASSADO NA IMAGEM (falso negativo silencioso, canario de 08/08);
# sem `testes` nao ha alvo dentro do container; sem `testes_no_repo` nao ha onde
# gravar o arquivo no worktree; sem `trabalho` o `docker run -w ""` nao sobe.
TEM_PROVA_DIFERENCIAL = bool(CODIGO_MONTAGENS and CODIGO_TESTES
                             and CODIGO_TESTES_NO_REPO and CODIGO_TRABALHO)

# O banco de teste do projeto ja vem com dados, ou nasce vazio?
#
# 🚨 Medido em 15/08: na bancada ele nasce VAZIO (a suite dela semeia por
# fixture). O advogado escreveu a invariante certa, o teste rodou, e falhou
# IGUAL nos dois lados por falta de dados -- inconclusivo que parece limite do
# produto e e' caracteristica do projeto.
#
# Ele nao tinha como saber: nada dizia. Agora diz, em execucao, e a instrucao
# entra pelo `veredito.yml` -- nunca chumbada na lente, que foi o erro do
# arbitro.
BANCO_DE_TESTE_SEMEADO = _b("BANCO_DE_TESTE_SEMEADO",
                            bool(_codigo.get("banco_de_teste_semeado", True)))

# --- como o app autentica ---------------------------------------------------
#
# 🚨 Tambem chumbado ate' 15/08: rota `/auth/login`, senha no campo `password`,
# token em `access_token`. Sao tres convencoes do desafio, e nenhum app do mundo
# e' obrigado a compartilhar as tres. Na bancada e' `/login`, `senha` e `token`
# -- o login falhava com 404 e toda prova ponta a ponta morria antes de comecar.
#
# 🚨 SEM FALLBACK desde 17/08. `/auth/login`, `password` e `access_token` sao as
# convencoes DO DESAFIO -- a bancada usa `/login`, `senha` e `token`, e nenhum
# app do mundo e' obrigado a compartilhar as tres. Padrao que aponta para um
# projeto especifico e' pior que padrao nenhum: as sondas ficam verdes e a
# rodada segue contra o alvo errado.
#
# ⚠️ `campo_usuario` mantem `email` de proposito: os dois projetos irmaos
# declaram igual, entao e' convencao e nao contaminacao. A diferenca e' o
# criterio da trava em `tests/test_config_sem_desafio.py`.
_auth = PROJETO.get("auth") or {}
AUTH_ROTA = _s("AUTH_ROTA", _auth.get("rota") or "")
AUTH_CAMPO_USUARIO = _s("AUTH_CAMPO_USUARIO", _auth.get("campo_usuario") or "email")
AUTH_CAMPO_SENHA = _s("AUTH_CAMPO_SENHA", _auth.get("campo_senha") or "")
AUTH_CAMPO_TOKEN = _s("AUTH_CAMPO_TOKEN", _auth.get("campo_token") or "")

# Da' para autenticar neste projeto? Derivada -- o login precisa dos tres, e
# adivinhar qualquer um deles e' postar credencial num endereco que nao e' o de
# login. Ver `ferramentas._token`, que recusa.
TEM_AUTH = bool(AUTH_ROTA and AUTH_CAMPO_SENHA and AUTH_CAMPO_TOKEN)

# {nome: (email, senha)}. Vazio e' legitimo: o projeto perde prova ponta a ponta
# e o pre-voo diz isso em voz alta, em vez de a rodada sair toda em MEDIA e
# parecer que o produto nao funciona.
#
# 🚨 SEM FALLBACK, e a ausencia dele e' o conserto de 17/08. Estas quatro contas
# eram o padrao quando o projeto nao declarava nenhuma -- entao revisando o
# `pallets/flask` o produto tentou (e conseguiu) logar como `demo@hack2l.dev` no
# app do desafio, que estava no ar. O comentario abaixo ja dizia que vazio e'
# legitimo; o `or {...}` garantia que nunca ficasse vazio.
USUARIOS = projeto.usuarios(PROJETO)

# A conta que nao possui nada. Deduzida de `possui: 0` no yml -- declarar duas
# vezes e' convidar as duas a divergirem.
CONTROLE_NEGATIVO = _s("CONTROLE_NEGATIVO", projeto.controle_negativo(PROJETO) or "")

# --- o nosso modelo ---------------------------------------------------------
ANTHROPIC_API_KEY = _s("ANTHROPIC_API_KEY", "")

# Haiku para gerar hipoteses, Opus para verificar, Sonnet para sintetizar:
# modelo caro so onde a decisao acontece.
MODEL_PROMOTOR = _s("MODEL_PROMOTOR", "claude-haiku-4-5-20251001")
MODEL_ADVOGADO = _s("MODEL_ADVOGADO", "claude-opus-5")
MODEL_JUIZ = _s("MODEL_JUIZ", "claude-sonnet-5")

# --- contencao do http_request ----------------------------------------------
#
# 🚨 MEDIDO EM 14/08, numa rodada real: o banco saiu de shares=0 para shares=3.
# Provar a injection na rota de compartilhamento exige chamar POST
# /documents/N/share, que cria linha. Nada foi destruido, mas o advogado
# ALTEROU estado do app real -- e a linha de base documentada desloca a cada
# rodada, sujando comparacao entre rodadas sem ninguem perceber.
#
# A contencao que ja funcionava (banco descartavel, rede sem saida) cobria o
# caminho da `prova_diferencial`. O `http_request` fala com o app DE VERDADE, no
# banco `kb` de verdade, e ficou de fora: a guarda existia e estava muda
# exatamente no caminho que toca dado vivo.
#
# Aqui o app inteiro passa a apontar para uma COPIA descartavel durante a
# rodada. O banco original e' apenas LIDO (`pg_dump`), nunca escrito.
#
# ⚠️ DESLIGADA POR PADRAO, mesmo criterio da PERMITIR_REDE_NO_BASE: ela
# reinicia o container da api, e quem conhece o ambiente decide.
#
# 🚫 O caminho `CREATE DATABASE ... TEMPLATE kb` foi TESTADO e esta proibido:
# com o app conectado ele DERRUBOU o servidor Postgres ("another server process
# exited abnormally", banco em modo de recuperacao). pg_dump com o app rodando
# e' seguro -- 0,6s para 171KB -- e e' o caminho usado aqui.
APP_EM_BANCO_DESCARTAVEL = _b("APP_EM_BANCO_DESCARTAVEL", False)

# A copia. Nunca pode ser igual a BANCO_APP_ORIGEM -- ha teste para isso, porque
# uma variavel de ambiente trocada faria a rodada rodar em cima do banco real
# achando que esta contida, que e' pior do que nao ter contencao nenhuma.
BANCO_APP = _s("BANCO_APP", _banco.get("descartavel_app") or "kb_veredito_app")
# 🚨 Sem fallback: `kb` e' o banco do desafio. Este e' o nome que o retrato LE
# para responder "a rodada mexeu no dado do cliente?" -- apontado para o banco
# errado, ele responde sobre o projeto errado.
BANCO_APP_ORIGEM = _s("BANCO_APP_ORIGEM", _banco.get("nome") or "")

# Da' para tirar retrato do banco deste projeto? Pelo mesmo motivo do
# `TEM_AUTH`: `psql -U "" -d ""` nao e' uma pergunta, e' um erro com cara de
# resposta.
#
# ⚠️ `BANCO_SERVICO` de fora, de proposito, e foi a propria trava do
# `test_banco_nao_se_aplica` que apontou: ele cai em `db`, e um criterio que se
# apoia num valor adivinhado herda o palpite. Alem disso o nome do SERVICO nao
# e' o que torna um banco declarado -- nome e usuario sao. Servico errado faz o
# retrato falhar alto (NAO MEDIDO com causa), que e' o desfecho honesto; nome ou
# usuario vazios fariam o psql responder lixo com cara de resposta.
TEM_BANCO = bool(BANCO_APP_ORIGEM and BANCO_USUARIO)

# 🚨 EXISTE ALGUMA VIA, NESTA RODADA, QUE CHEGUE A UM BANCO?
#
# Sem esta pergunta o parecer de todo PR de terceiro abria com **NAO MEDIDO: a
# rodada pode ter criado ou removido linhas**. Nao podia: sem app declarado o
# `http_request` recusa, sem o bloco `codigo` a suite nao roda, e o retrato
# falhava so' porque procurava um `docker-compose.yml` que aquele repositorio
# nao tem.
#
# ⚠️ E o alarme errado custa MAIS caro que o alarme ausente aqui. Esta e' a
# linha que avisa que o agente mexeu em dado vivo -- o incidente de 14/08
# (`shares` 0 -> 3) so' apareceu porque um humano desconfiou. Disparar em toda
# rodada de terceiro ensina o leitor a pular exatamente ela, e ai a guarda
# morre de excesso em vez de morrer de falta.
#
# 🚫 Conservador de proposito: QUALQUER uma das tres vias liga a medicao de
# volta. So' e' "nao se aplica" quando nao existe caminho nenhum ate' um banco.
#
# ⚠️ `_banco.get("nome")` cru, e nao `BANCO_APP_ORIGEM`: aquele cai em `kb`, o
# banco do desafio, quando o projeto nao declara -- perguntar a ele seria
# perguntar ao proprio chumbado que este criterio existe para nao repetir.
ALCANCA_BANCO = bool(TEM_APP or TEM_PROVA_DIFERENCIAL or TEM_BANCO)


# --- contexto compartilhado no bloco cacheado -------------------------------
#
# Os arquivos que o diff toca, inteiros, DENTRO do bloco que ja leva
# `cache_control` junto com o diff. Duas economias, e a segunda e' a grande:
#
#   1. o arquivo passa a custar ~10% (leitura de cache) em cada acusacao, em vez
#      de 100% em cada uma. Cada acusacao e' uma CONVERSA SEPARADA -- de
#      proposito, para uma nao contaminar a outra -- entao hoje nada e'
#      reaproveitado entre elas.
#   2. o advogado nao gasta uma VOLTA DO LACO pedindo para ler, e volta do laco
#      no modelo caro e' onde o custo mora de verdade.
#
# ⚠️ Medido em 14/08, e foi o que derrubou o desenho anterior: memoizar
# `read_file` em memoria economiza 0,15s de disco e ZERO dolar, porque o
# conteudo entra no contexto do mesmo jeito. O gargalo nunca foi o disco.
#
# 🚨 O prefixo tem que ser BYTE A BYTE IDENTICO nas N acusacoes, senao o cache
# nao le e todas pagam preco cheio -- ver a disciplina no 4 do CLAUDE.md. Por
# isso a lista de arquivos e' ORDENADA e o bloco e' montado UMA vez por rodada.
CONTEXTO_ARQUIVOS = _b("CONTEXTO_ARQUIVOS", True)

# Teto total do bloco. Ele e' lido por TODAS as acusacoes, entao arquivo que
# ninguem ia abrir custa 10% a toa. Melhor apertado: o que ficar de fora
# continua alcancavel por `read_file`, e o bloco diz quais ficaram.
CONTEXTO_MAX_CHARS = _i("CONTEXTO_MAX_CHARS", 40000)


# --- parametros do advogado -------------------------------------------------
TOP_N = _i("TOP_N", 2)
EFFORT = _s("EFFORT", "high")

# No Opus 5 max_tokens limita RACIOCINIO + RESPOSTA somados, e o raciocinio vem
# ligado por padrao -- omitir `thinking` nao desliga. Apertar isto trunca o
# veredito no meio.
MAX_TOKENS_ADVOGADO = _i("MAX_TOKENS_ADVOGADO", 64000)

# O modelo SABE que tem este orcamento e fecha o parecer em vez de ser cortado.
# Minimo da API: 20.000.
TASK_BUDGET_TOKENS = _i("TASK_BUDGET_TOKENS", 30000)

_VOLTAS_BASE = _i("MAX_VOLTAS_LOOP", 10)

# ⚠️ Banco de teste vazio custa VOLTAS: o advogado precisa criar usuario,
# projeto e recurso antes de exercitar a invariante. Em 15/08 ele gastou o teto
# nisso, chutou o nome de um campo do modelo, errou, e nao sobrou volta para ler
# `models.py` e corrigir -- disse isso no proprio motivo: "faltaram voltas...
# com o nome correto do campo o mesmo teste deve fechar".
#
# O acrescimo e' amarrado ao MOTIVO, e nao um numero solto que alguem sobe
# quando incomoda: so' vale onde o projeto declara que o banco nasce vazio.
VOLTAS_EXTRAS_SEM_SEED = _i("VOLTAS_EXTRAS_SEM_SEED", 5)
MAX_VOLTAS_LOOP = _VOLTAS_BASE + (0 if BANCO_DE_TESTE_SEMEADO
                                  else VOLTAS_EXTRAS_SEM_SEED)

TIMEOUT_ACUSACAO_S = _i("TIMEOUT_ACUSACAO_S", 180)

# --- expansao guiada por area cega ------------------------------------------
#
# Quantas acusacoes EXTRAS a rodada pode gastar num ponto que varias lentes
# apontaram e que ninguem julgou. Zero desliga.
#
# 🚨 O gatilho e' AUSENCIA DE EXAME, nunca taxa de acerto. Medido em 15/08: no
# PR do race, OITO acusacoes eram o MESMO defeito visto por cinco lentes.
# Expandir porque "muitas provaram" gastaria reprovando o que ja se sabe.
#
# ⚠️ Teto DURO e uma passada so'. Sem isso o mecanismo que decide gastar e' o
# mesmo que gasta, e uma lente barulhenta faria a rodada crescer sozinha -- o
# projeto ja topou com isso e foi por isso que nasceu o orcamento por lente.
EXPANSAO_MAX = _i("EXPANSAO_MAX", 3)
EXPANSAO_MIN_LENTES = _i("EXPANSAO_MIN_LENTES", 3)

# --- limites ----------------------------------------------------------------
TIMEOUT_PYTEST_S = _i("TIMEOUT_PYTEST_S", 180)
TIMEOUT_GIT_S = _i("TIMEOUT_GIT_S", 60)
TIMEOUT_HTTP_S = _i("TIMEOUT_HTTP_S", 30)

# A api leva ~30s para aceitar conexao depois de um `compose up`. Sem isto, a
# primeira acusacao da rodada vira INCONCLUSIVO por warm-up, e o terceiro
# estado nao se recupera sozinho.
TENTATIVAS_HTTP = _i("TENTATIVAS_HTTP", 3)

# 🚨 O app alvo sem OPENAI_API_KEY devolve a MESMA resposta para qualquer
# pergunta, inclusive um payload de injection. Sem guard, "o modelo nao
# obedeceu" vira REFUTADO -- absolvicao falsa, pior que falso alarme, porque
# engorda a lista de descartados e PARECE rigor.
#
# A deteccao NAO compara com a string enlatada: isso quebraria se o texto
# mudasse. Ver llm_alvo.py -- duas sondas sem nada em comum, respostas iguais
# provam que o modelo nao leu nenhuma das duas. Pega chave ausente, rate limit
# que cai no fallback e stub trocado, sem precisar saber qual foi.
AVISO_SEM_MODELO = "app_sem_modelo"


def app_tem_modelo() -> bool:
    """Le a OPENAI_API_KEY do .env do DESAFIO -- nao a nossa.

    Deteccao na subida, complementar a comparacao de resposta: pega o caso de a
    chave existir mas estar invalida so quando a resposta chega.
    """
    env = DESAFIO / ".env"
    if not env.is_file():
        return False
    for linha in env.read_text(encoding="utf-8", errors="replace").splitlines():
        if linha.strip().startswith("OPENAI_API_KEY="):
            return bool(linha.split("=", 1)[1].strip())
    return False

# Quanto de saida crua volta para o modelo. O artefato em disco guarda tudo;
# isto aqui e' so o que cabe no contexto sem afogar o raciocinio.
CORTE_SAIDA = _i("CORTE_SAIDA", 4000)


def prepara_pastas() -> None:
    # RODADA e ARTEFATOS sao lidos do modulo a cada chamada, e nao capturados no
    # topo, porque nova_rodada() os rebinda -- capturar aqui criaria a pasta da
    # rodada ANTERIOR e deixaria a atual sem existir.
    for p in (SAIDAS, RODADAS, RODADA, ARTEFATOS, WORKTREES):
        p.mkdir(parents=True, exist_ok=True)
