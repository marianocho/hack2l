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

# --- limites ----------------------------------------------------------------
TIMEOUT_PYTEST_S = _i("TIMEOUT_PYTEST_S", 180)
TIMEOUT_GIT_S = _i("TIMEOUT_GIT_S", 60)
TIMEOUT_HTTP_S = _i("TIMEOUT_HTTP_S", 30)

# A api leva ~30s para aceitar conexao depois de um `compose up`. Sem isto, a
# primeira acusacao da rodada vira INCONCLUSIVO por warm-up, e o terceiro
# estado nao se recupera sozinho.
TENTATIVAS_HTTP = _i("TENTATIVAS_HTTP", 3)

# Quanto de saida crua volta para o modelo. O artefato em disco guarda tudo;
# isto aqui e' so o que cabe no contexto sem afogar o raciocinio.
CORTE_SAIDA = _i("CORTE_SAIDA", 4000)


def prepara_pastas() -> None:
    for p in (SAIDAS, ARTEFATOS, WORKTREES):
        p.mkdir(parents=True, exist_ok=True)
