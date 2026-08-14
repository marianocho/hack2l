"""hack2l / Veredito -- configuracao.

Nada de porta, URL ou caminho chumbado no resto do codigo. Duas maquinas com
portas diferentes constroem isto e a apresentacao roda na outra; tudo o que
muda entre elas passa por aqui.

Espelha a convencao no 1 do repo alvo: configuracao le-se de um lugar so.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")


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
COMPOSE = DESAFIO / "docker-compose.yml"
BRANCH_PR = _s("PR_BRANCH", "pr/document-sharing")
BRANCH_BASE = _s("BASE_BRANCH", "main")

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
BANCO_DESCARTAVEL = _s("BANCO_DESCARTAVEL", "kb_veredito")


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
REDE_ISOLADA = _s("REDE_ISOLADA", "veredito_isolada")

# A escotilha. Efeito irreversivel se pergunta ANTES, nao se descobre depois --
# e quem tem contexto para decidir e' o dono do repositorio, nao o agente.
PERMITIR_REDE_NO_BASE = _b("PERMITIR_REDE_NO_BASE", False)


def url_do_banco_descartavel() -> str:
    """A URL que o agente IMPOE ao rodar teste do repositorio sob revisao.

    `db` e `kb:kb` vem do docker-compose do desafio; num cliente isto viria do
    `veredito.yml`, e a Action rodando na CI dele ja tem banco descartavel como
    o normal.
    """
    return f"postgresql+psycopg://kb:kb@db:5432/{BANCO_DESCARTAVEL}"


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
CONTEXTO = Path(_s("CONTEXTO_REPO", str(RAIZ / "contexto" / "hack2l.md")))


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
APP_API_URL = _s("APP_API_URL", "http://127.0.0.1:8000").rstrip("/")
APP_WEB_URL = _s("APP_WEB_URL", "http://127.0.0.1:3000").rstrip("/")

# Os quatro usuarios do seed. carol nao possui nada -- e' o controle negativo.
USUARIOS = {
    "demo": ("demo@hack2l.dev", "demo-password"),
    "alice": ("alice@hack2l.dev", "alice-password"),
    "bob": ("bob@hack2l.dev", "bob-password"),
    "carol": ("carol@hack2l.dev", "carol-password"),
}

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
BANCO_APP = _s("BANCO_APP", "kb_veredito_app")
BANCO_APP_ORIGEM = _s("BANCO_APP_ORIGEM", "kb")


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

MAX_VOLTAS_LOOP = _i("MAX_VOLTAS_LOOP", 10)
TIMEOUT_ACUSACAO_S = _i("TIMEOUT_ACUSACAO_S", 180)

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
