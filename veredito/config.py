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
SAIDAS = RAIZ / "saidas"
ARTEFATOS = RAIZ / "artefatos"

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
    for p in (SAIDAS, ARTEFATOS, WORKTREES):
        p.mkdir(parents=True, exist_ok=True)
