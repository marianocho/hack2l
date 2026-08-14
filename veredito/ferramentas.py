"""hack2l / Veredito -- a pericia. As ferramentas do advogado.

ZERO chamada de LLM neste modulo. Tudo aqui e' verificavel com pytest, e isso e'
o ponto inteiro: o veredito e' um exit code, e exit code se confere.

A divisao interna importa:

  _funcao_privada(...) -> dict   e' o que o juiz consome. Dado, nao prosa.
  funcao_publica(...)  -> str    e' o que o modelo le. Prosa, nao dado.

O modelo nunca toca no dict. Ele pode descrever a prova errado no texto dele; o
artefato em disco continua dizendo a verdade, porque foi calculado em Python.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests
from anthropic import beta_tool

from . import config as cfg
from . import llm_alvo

# O orquestrador carimba isto antes de soltar o advogado em cada acusacao, para
# que o nome do artefato case com a acusacao sem mudar a assinatura da tool --
# a assinatura e' contrato com a outra trilha.
_ACUSACAO_ATUAL = "sem_id"


def define_acusacao(id_acusacao: str) -> None:
    global _ACUSACAO_ATUAL
    _ACUSACAO_ATUAL = re.sub(r"[^A-Za-z0-9_.-]", "_", id_acusacao) or "sem_id"
    # Zera o registro de chamadas DESTA acusacao. `_AVISOS` e' um set e nao
    # precisa, mas o registro e' lista: sem zerar, julgar a mesma acusacao duas
    # vezes no mesmo processo somaria as chamadas da tentativa anterior e a R3b
    # veria observacao que nao houve nesta.
    _CHAMADAS.pop(_ACUSACAO_ATUAL, None)


# Avisos por acusacao, nao por rodada. Global demais e o juiz nao consegue ligar
# a causa ao veredito certo; por acusacao ele rebaixa exatamente quem foi
# afetado e deixa o resto em paz.
_AVISOS: dict[str, set[str]] = {}


def _avisa(codigo: str) -> None:
    _AVISOS.setdefault(_ACUSACAO_ATUAL, set()).add(codigo)
    # Grava a cada aviso, nao no fim: se a rodada morrer no meio, o juiz ainda
    # sabe o que estava degradado.
    cfg.ARTEFATOS.mkdir(parents=True, exist_ok=True)
    (cfg.ARTEFATOS / "avisos.json").write_text(
        json.dumps({k: sorted(v) for k, v in _AVISOS.items()}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def avisos_da_acusacao(id_acusacao: str) -> list[str]:
    return sorted(_AVISOS.get(id_acusacao, set()))


# --- desfecho estruturado de cada chamada de ferramenta ---------------------
#
# 🚨 O QUE ISTO SUBSTITUI, e por que era o "caso vivo" do padrao de bug
#
# Ate' 13/08 quem decidia se uma ferramenta tinha falhado era
# `advogado._conta_ferramentas`, farejando `texto.startswith("ERRO")` na saida.
# O proprio docstring de la' admitia: "uma ferramenta que falhe sem esse prefixo
# passa batida".
#
# Quem depende disso e' a R3b -- PROVADO/REFUTADO com ZERO ferramenta
# bem-sucedida vira INCONCLUSIVO. Ela existe porque em 10/08 o advogado devolveu
# PROVADO com TODAS as chamadas falhando. Um unico caminho de erro sem o prefixo
# e a R3b fica muda exatamente onde ela e' necessaria, e o resultado e'
# absolvicao (ou condenacao) falsa. E' o padrao do CLAUDE.md ao pe da letra:
# guarda condicionada ao mesmo sinal que ela deveria vigiar.
#
# Agora quem sabe que falhou e' quem falhou. A ferramenta REGISTRA o desfecho; a
# string deixou de ser a fonte da verdade e virou so' o que o modelo le.
#
# ⚠️ A assinatura `-> str` das tools NAO muda -- e' o que o `@beta_tool` expoe ao
# modelo, e e' contrato com a outra trilha. O que mudou e' o lado de dentro.
_CHAMADAS: dict[str, list[dict]] = {}

# Marcado por _marca_falha durante UMA chamada, lido por _fecha_chamada.
_FALHA_DA_CHAMADA: str | None = None


def _marca_falha(texto: str) -> str:
    """Marca que a chamada em curso falhou e devolve o texto INALTERADO.

    Uma chamada so', para que registro e texto nao possam divergir: nao existe
    caminho que escreva o `ERRO` para o modelo sem contar a falha para a R3b.
    """
    global _FALHA_DA_CHAMADA
    _FALHA_DA_CHAMADA = texto[:300]
    return texto


def _abre_chamada() -> None:
    global _FALHA_DA_CHAMADA
    _FALHA_DA_CHAMADA = None


def _fecha_chamada(nome: str, saida: str) -> str:
    """Registra o desfecho e devolve a saida que o modelo le, sem tocar nela."""
    global _FALHA_DA_CHAMADA
    _CHAMADAS.setdefault(_ACUSACAO_ATUAL, []).append({
        "ferramenta": nome,
        "ok": _FALHA_DA_CHAMADA is None,
        "causa": _FALHA_DA_CHAMADA or "",
    })
    # Limpa ao registrar, e nao so' no _abre_chamada. `autoteste` chama
    # `_read_file`/`_grep`/`_http_request` DIRETO, fora de qualquer ferramenta:
    # uma falha de pre-voo deixa a marca pendurada, e sem esta linha ela so'
    # some porque a proxima ferramenta lembrou de abrir. Depender de alguem
    # lembrar e' como o prefixo `ERRO` virou divida -- entao o estado se limpa
    # nas duas pontas.
    _FALHA_DA_CHAMADA = None
    # Grava a cada chamada, nao no fim: rodada que morre no meio nao pode levar
    # junto a prova de que as ferramentas estavam funcionando. Mesmo motivo do
    # _avisa acima.
    try:
        cfg.ARTEFATOS.mkdir(parents=True, exist_ok=True)
        (cfg.ARTEFATOS / "chamadas.json").write_text(
            json.dumps(_CHAMADAS, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        # Disco cheio nao pode derrubar a pericia: o registro em memoria e' que
        # alimenta a R3b nesta rodada, e ele continua de pe.
        pass
    return saida


def chamadas_da_acusacao(id_acusacao: str) -> list[dict]:
    return list(_CHAMADAS.get(id_acusacao, []))


def desfecho_da_acusacao(id_acusacao: str) -> tuple[int, int]:
    """(sucessos, erros) das ferramentas que EXECUTARAM nesta acusacao.

    ⚠️ Nao cobre chamada que nem chegou ao nosso codigo -- input invalido que a
    API rejeita antes de nos chamar nao aparece aqui. Quem fecha esse vao e'
    `advogado._conta_ferramentas`, contando os blocos que voltaram. Somar os
    dois e' de proposito: cada um enxerga o que o outro nao ve.
    """
    chamadas = _CHAMADAS.get(id_acusacao, [])
    ok = sum(1 for c in chamadas if c["ok"])
    return ok, len(chamadas) - ok


# Chamadas HTTP por acusacao. Mesma chaveagem dos avisos, e pelo mesmo motivo:
# o juiz precisa ligar a evidencia ao veredito certo, nao a' rodada.
_HTTP: dict[str, list[dict]] = {}


# ---------------------------------------------------------------- utilitarios

def _corta(texto: str, limite: int = None) -> str:
    """Corta pelo comeco, nao pelo fim: o resumo do pytest fica no rodape."""
    limite = limite or cfg.CORTE_SAIDA
    if len(texto) <= limite:
        return texto
    return f"[... {len(texto) - limite} caracteres cortados ...]\n" + texto[-limite:]


def _git(*args: str, cwd: Path = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd or cfg.DESAFIO), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=cfg.TIMEOUT_GIT_S,
    )


def _resolve_ref(ref: str) -> str:
    """Aceita 'pr/document-sharing' ou 'origin/pr/document-sharing'."""
    for tentativa in (ref, f"origin/{ref}"):
        r = _git("rev-parse", "--verify", "--quiet", f"{tentativa}^{{commit}}")
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    raise RuntimeError(f"ref nao encontrada no repo do desafio: {ref}")


def commit_head() -> str:
    return _resolve_ref(cfg.BRANCH_PR)


def commit_base() -> str:
    """O pai do PR, calculado -- NUNCA chumbado.

    A ponta da main pode ser irmao do PR e nao ancestral (foi o caso aqui:
    f491ae1 so adiciona LICENSE/README, o pai de verdade e' 32a5241). Chumbar o
    hash poe uma mentira no artefato que vai pro slide.
    """
    r = _git("merge-base", _resolve_ref(cfg.BRANCH_BASE), _resolve_ref(cfg.BRANCH_PR))
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"git merge-base falhou: {r.stderr.strip()}")
    return r.stdout.strip()


def _garante_worktree(commit: str, nome: str) -> Path:
    """Worktree idempotente, e CONFERIDO. O advogado chama isto em loop.

    🚨 Nunca confiar no returncode do `worktree add` e seguir em frente. A
    guarda antiga era `if r.returncode != 0 and not destino.exists(): raise` --
    ou seja, se o diretorio existisse mas estivesse obsoleto, o add falhava, a
    guarda passava batido e a prova rodava contra o COMMIT ERRADO, gravando no
    artefato o commit que se pediu e nao o que se montou. Falso negativo mudo.

    Acontece de verdade na outra maquina: os ponteiros de worktree do git sao
    caminhos ABSOLUTOS, chumbados em quem criou. Clonar o repo e rodar la
    encontra `.worktrees/head` apontando para um caminho que nao existe.

    Entao: conferir o que ficou no disco, sempre.
    """
    destino = cfg.WORKTREES / nome
    if destino.exists():
        atual = _git("rev-parse", "HEAD", cwd=destino)
        if atual.returncode == 0 and atual.stdout.strip() == commit:
            return destino
        _git("worktree", "remove", "--force", str(destino))
        if destino.exists():  # ponteiro quebrado: o remove nao da conta
            shutil.rmtree(destino, ignore_errors=True)
    _git("worktree", "prune")  # limpa registro orfao de outra maquina
    cfg.WORKTREES.mkdir(parents=True, exist_ok=True)
    r = _git("worktree", "add", "--detach", str(destino), commit)

    conferido = _git("rev-parse", "HEAD", cwd=destino)
    if conferido.returncode != 0 or conferido.stdout.strip() != commit:
        raise RuntimeError(
            f"worktree '{nome}' nao ficou em {commit[:7]} "
            f"(esta em {conferido.stdout.strip()[:7] or 'nada'}). "
            f"add: {r.stderr.strip()[:200]} | conferencia: {conferido.stderr.strip()[:200]}"
        )
    return destino


# 🚨 O codigo do teste vem do MODELO, e o container da prova esta na rede do
# compose. De la, `api:8000` e `db:5432` resolvem, e as credenciais kb:kb estao
# no docker-compose.yml que o modelo le com read_file. Dois estragos possiveis:
#
#   falar com o app no ar -- ele serve o codigo ASSADO NA IMAGEM, o mesmo nos
#   dois lados. A diferenca entre base e head viria de estado acumulado (e o
#   head sempre roda depois), nao da mudanca do PR. PROVADO falso.
#
#   escrever no banco `kb` -- apaga o seed de demo/alice/bob/carol, que e' o
#   canario de isolamento. O conftest deles redireciona DATABASE_URL para
#   kb_test, mas so quando a URL termina em /kb; um teste que monte a propria
#   engine passa por cima e destroi o ambiente da demo no meio da rodada.
_TESTE_PERIGOSO = [
    (
        re.compile(r"api:8000|localhost:8000|127\.0\.0\.1:8000"),
        "o teste fala com o servico 'api' que esta NO AR. Ele serve o codigo assado na "
        "imagem, identico nos dois lados, entao a diferenca viria de estado acumulado e "
        "nao da mudanca do PR. Use o app em processo: "
        "'from fastapi.testclient import TestClient; from app.main import app'.",
    ),
    (
        # Ancorado no @host:porta antes do nome do banco. Sem o @, o proprio
        # 'postgresql://kb:kb@...' casaria pelo USUARIO kb depois do '//'.
        re.compile(r"postgresql[^\s'\"]*@[^\s'\"/]+/kb(?![_\w])"),
        "o teste conecta no banco da APLICACAO (kb) em vez de kb_test. Isso apagaria o "
        "seed de demo/alice/bob/carol, que e' o canario de isolamento. Use as fixtures do "
        "conftest, que ja apontam para kb_test.",
    ),
]


def _valida_codigo_do_teste(codigo: str) -> str | None:
    """Devolve o motivo da recusa, ou None se o teste pode rodar."""
    for rx, motivo in _TESTE_PERIGOSO:
        if rx.search(codigo):
            return f"prova recusada antes de executar: {motivo}"
    return None


def _sanitiza_nome(nome: str) -> str:
    """O nome vem do modelo. Sem isto, um nome fora do padrao faz o pytest nao
    coletar nada (exit 5) e a prova morre parecendo refutacao."""
    nome = Path(nome.strip().replace("\\", "/")).name or "test_acusacao.py"
    nome = re.sub(r"[^A-Za-z0-9_.-]", "_", nome)
    if not nome.endswith(".py"):
        nome += ".py"
    if not nome.startswith("test_"):
        nome = "test_" + nome
    return nome


# ------------------------------------------------------------------- execucao

# 🚨 O exit code SOZINHO nao distingue "teste falhou" de "docker caiu".
#
# `docker run` puro usa 125 para falha de infraestrutura, mas `docker compose`
# usa 1 -- o mesmo codigo que o pytest usa para "teste falhou". Medido: daemon
# inalcancavel -> 1, servico inexistente -> 1, mount spec invalido -> 1,
# arquivo de compose ausente -> 1.
#
# Ou seja, a guarda `exit_head == 1` protegia contra 2/3/4/5 e deixava passar
# exatamente o caso que ela dizia proteger. Um flap do healthcheck do `db`
# entre as duas execucoes virava acusacao CRITICA falsa; e docker ruim no
# inicio virava INCONCLUSIVO dizendo ao advogado "reescreva o teste para passar
# no codigo de hoje" -- instrucao para ENFRAQUECER um teste correto.
#
# Entao nao se pergunta ao exit code se o pytest rodou. Pergunta-se ao pytest.
_RESUMO_PYTEST = re.compile(
    r"\d+\s+(passed|failed|error|skipped|deselected|xfailed|xpassed)"
    r"|no tests ran"
    r"|={3,}\s*(ERRORS?|FAILURES?)\s*={3,}",
    re.IGNORECASE,
)


def _garante_banco_descartavel() -> None:
    """Cria o banco do agente se ele nao existir. Idempotente, e nunca levanta.

    Falhar aqui nao pode derrubar a rodada: se o banco ja existe (o caso comum)
    o CREATE devolve erro e esta tudo certo. O que importa e' que ele exista
    ANTES de o pytest do repositorio rodar apontado para ele.
    """
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(cfg.COMPOSE),
             "--project-directory", str(cfg.DESAFIO),
             "exec", "-T", "db", "psql", "-U", "kb", "-d", "postgres",
             "-c", f'CREATE DATABASE "{cfg.BANCO_DESCARTAVEL}"'],
            capture_output=True, text=True, timeout=cfg.TIMEOUT_GIT_S,
        )
    except Exception:
        pass


# Sinais de que o teste morreu por FALTA DE REDE, e nao por defeito no codigo.
# Sem distinguir, o isolamento gera inconclusivo mudo e o parecer parece fraco
# por culpa nossa.
_SEM_REDE = re.compile(
    r"name or service not known|temporary failure in name resolution|"
    r"nodename nor servname|network is unreachable|no route to host|"
    r"failed to establish a new connection|max retries exceeded|"
    r"connectionerror|gaierror|getaddrinfo",
    re.I,
)


def falhou_por_isolamento(saida: str) -> bool:
    """A saida do pytest acusa rede indisponivel?

    ⚠️ Nao basta ter o padrao: o banco tambem e' rede, e a suite legitima fala
    com ele. Mas o banco esta DENTRO da rede isolada, entao um erro de resolucao
    aqui e' de host EXTERNO -- que e' exatamente o que a contencao bloqueia.
    """
    return bool(_SEM_REDE.search(saida or ""))


def _tem_alias_db(container: str) -> bool:
    """O banco responde por `db` DENTRO da rede isolada?

    E' a conferencia que faltava: sem ela a contencao sobe achando que esta
    certa e todo teste do base morre sem alcancar o banco.
    """
    try:
        r = subprocess.run(
            ["docker", "inspect", container, "--format",
             "{{json .NetworkSettings.Networks}}"],
            capture_output=True, text=True, timeout=cfg.TIMEOUT_GIT_S,
        )
        redes = json.loads(r.stdout or "{}")
        return "db" in (redes.get(cfg.REDE_ISOLADA, {}).get("Aliases") or [])
    except Exception:
        return False


def _garante_rede_isolada() -> bool:
    """Rede sem saida, com o banco dentro. Idempotente. Nunca levanta.

    `--internal` e' o mecanismo do proprio Docker: "Restrict external access to
    the network". O container fala com o db e nao alcanca a internet.

    Devolve False se nao conseguiu montar -- e aí o chamador NAO roda contido,
    porque rodar sem a contencao achando que esta contido e' pior que nao ter.
    """
    try:
        subprocess.run(["docker", "network", "create", "--internal", cfg.REDE_ISOLADA],
                       capture_output=True, text=True, timeout=cfg.TIMEOUT_GIT_S)
        r = subprocess.run(
            ["docker", "compose", "-f", str(cfg.COMPOSE),
             "--project-directory", str(cfg.DESAFIO), "ps", "-q", "db"],
            capture_output=True, text=True, timeout=cfg.TIMEOUT_GIT_S,
        )
        db = (r.stdout or "").strip().splitlines()
        if not db:
            return False
        # 🚨 `--alias db` NAO e' detalhe. Sem ele o container do banco entra na
        # rede pelo NOME DELE (`desafio-db-1`), e o `db` que o conftest do
        # cliente procura nao resolve. Medido: internet bloqueada (certo) e
        # BANCO INALCANCAVEL (errado) -- todo teste do base viraria inconclusivo
        # e a contencao pareceria um desastre em vez de uma protecao.
        #
        # ⚠️ E `connect` e' no-op quando ja existe conexao, mesmo SEM o alias.
        # Entao nao basta chamar com --alias: se uma execucao anterior conectou
        # sem ele, o alias nunca aparece e a falha e' silenciosa. Confere-se o
        # alias e reconecta se faltar.
        if not _tem_alias_db(db[0]):
            subprocess.run(["docker", "network", "disconnect", cfg.REDE_ISOLADA, db[0]],
                           capture_output=True, text=True, timeout=cfg.TIMEOUT_GIT_S)
            subprocess.run(["docker", "network", "connect", "--alias", "db",
                            cfg.REDE_ISOLADA, db[0]],
                           capture_output=True, text=True, timeout=cfg.TIMEOUT_GIT_S)
        return _tem_alias_db(db[0])
    except Exception:
        return False


def _imagem_da_api() -> str | None:
    """A imagem que o `compose run` usaria. Precisamos dela porque `compose run`
    NAO aceita `--network` -- entao o lado contido vai de `docker run` direto."""
    try:
        r = subprocess.run(
            ["docker", "compose", "-f", str(cfg.COMPOSE),
             "--project-directory", str(cfg.DESAFIO), "images", "-q", "api"],
            capture_output=True, text=True, timeout=cfg.TIMEOUT_GIT_S,
        )
        return (r.stdout or "").strip().splitlines()[0] or None
    except Exception:
        return None


def _roda_pytest(worktree: Path, alvo: str = "tests",
                 contido: bool = False) -> tuple[int, str, bool]:
    """Roda a suite dentro do container, com o codigo do worktree por cima.

    `contido=True` prende o container numa rede SEM SAIDA -- usado no lado
    BASE, onde mora o risco que so' nos criamos (a CI do cliente ja roda o
    head a cada push; o base ninguem roda mais).

    Bind-mount e nao rebuild: o Dockerfile faz COPY do codigo e o compose nao
    monta volume nenhum no servico api, entao sem estes -v o pytest roda o
    codigo assado na imagem e a prova diferencial da o MESMO resultado nos dois
    lados -- falso negativo silencioso. Provado com canario em 08/08.
    """
    _garante_banco_descartavel()
    imagem = _imagem_da_api() if contido else None
    if contido and imagem and _garante_rede_isolada():
        # `docker run` e nao `compose run`: o compose nao aceita --network, e
        # sem a rede isolada a contencao seria so' intencao.
        cmd = [
            "docker", "run", "--rm", "--network", cfg.REDE_ISOLADA,
            "-e", f"DATABASE_URL={cfg.url_do_banco_descartavel()}",
            "-v", f"{worktree / 'app' / 'api' / 'app'}:/code/app",
            "-v", f"{worktree / 'app' / 'api' / 'tests'}:/code/tests",
            "-w", "/code",
            # Teto de recurso: fork bomb e disco cheio nao sao efeito de rede,
            # mas custam o mesmo barato de barrar aqui.
            "--memory", "2g", "--pids-limit", "512",
            imagem, "python", "-m", "pytest", alvo, "-q",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=cfg.TIMEOUT_PYTEST_S)
        saida = (r.stdout or "") + (r.stderr or "")
        return r.returncode, saida, bool(_RESUMO_PYTEST.search(saida))

    cmd = [
        "docker", "compose", "-f", str(cfg.COMPOSE),
        "--project-directory", str(cfg.DESAFIO),
        "run", "--rm",
        # 🚨 O ALVO E' IMPOSTO DE FORA, e e' o conserto do incidente de 11/08.
        #
        # A suite que roda aqui e' do REPOSITORIO sob revisao, em DOIS commits,
        # e nao ha nenhuma garantia de que a versao antiga seja segura -- o
        # commit base do desafio era anterior ao proprio conserto do autor, e
        # apagou o banco da aplicacao (4 usuarios, 5 documentos).
        #
        # Forcando DATABASE_URL aqui, o `DROP SCHEMA` do conftest deles acontece
        # num banco que existe para ser destruido. Nao depende do repositorio
        # ter tido a ideia, e vale em qualquer commit.
        "-e", f"DATABASE_URL={cfg.url_do_banco_descartavel()}",
        "-v", f"{worktree / 'app' / 'api' / 'app'}:/code/app",
        "-v", f"{worktree / 'app' / 'api' / 'tests'}:/code/tests",
        "api", "python", "-m", "pytest", alvo, "-q",
    ]
    r = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=cfg.TIMEOUT_PYTEST_S,
    )
    saida = (r.stdout or "") + (r.stderr or "")
    # O terceiro valor e' a unica prova de que o exit code veio do pytest e nao
    # do docker: sem linha de resumo, nenhum teste foi executado.
    return r.returncode, saida, bool(_RESUMO_PYTEST.search(saida))


# Codigos do pytest: 0 passou | 1 falhou | 2 interrompido | 3 erro interno
#                    4 erro de uso | 5 nenhum teste coletado
_CAUSA = {
    2: "execucao interrompida",
    3: "erro interno do pytest",
    4: "erro de uso do pytest",
    5: "nenhum teste foi coletado -- o arquivo nao casa com o padrao ou nao compila",
}


def _classifica(
    exit_base: int, exit_head: int, rodou_base: bool = True, rodou_head: bool = True
) -> tuple[str, bool, str]:
    """A regra central, em codigo. O LLM nao participa desta decisao.

    Devolve (estado, provado, motivo). `motivo` explica todo estado que nao e'
    PROVADO -- e' o texto que vira a lista de descartados e a de inconclusivos
    no parecer. NAO confundir com `erro`, que e' so falha de infraestrutura:
    refutacao com motivo e' um resultado valido, nao um erro.

    `rodou_*` vem antes de tudo e nao e' redundante com o exit code: o
    `docker compose` devolve 1 quando o daemon falha, que e' o MESMO codigo de
    "teste falhou". Sem esta guarda, um flap do docker entre as duas execucoes
    vira acusacao critica falsa -- ver o comentario em _RESUMO_PYTEST.

    Exigir exit_head == 1 (e nao != 0) continua valendo para os codigos
    proprios do pytest (2/3/4/5).
    """
    if not rodou_base or not rodou_head:
        lado = "base" if not rodou_base else "head"
        return "INCONCLUSIVO", False, (
            f"no {lado}: o pytest nao chegou a rodar -- a saida nao tem linha de "
            "resumo. O exit code veio do docker, nao do teste, e docker compose "
            "usa 1 igual a teste falhando. Nao da para provar nem refutar."
        )
    if exit_base == 0 and exit_head == 1:
        return "PROVADO", True, "passa no commit base e falha no head do PR"
    if exit_base == 0 and exit_head == 0:
        return "REFUTADO", False, "o teste passa nos dois lados: a mudanca do PR nao quebra isto"
    if exit_base == 1:
        return "INCONCLUSIVO", False, (
            "o teste ja falha no commit base, entao nao isola a mudanca do PR -- "
            "reescreva o teste para passar no codigo de hoje"
        )
    if exit_base in _CAUSA:
        return "INCONCLUSIVO", False, f"no base: {_CAUSA[exit_base]} (exit {exit_base})"
    if exit_head in _CAUSA:
        return "INCONCLUSIVO", False, f"no head: {_CAUSA[exit_head]} (exit {exit_head})"
    return "INCONCLUSIVO", False, f"par de exit codes inesperado: base={exit_base} head={exit_head}"


def _prova_diferencial(codigo_do_teste: str, nome_do_arquivo: str) -> dict:
    inicio = time.time()
    cfg.prepara_pastas()
    nome = _sanitiza_nome(nome_do_arquivo)

    art = {
        "id": _ACUSACAO_ATUAL,
        "arquivo_do_teste": nome,
        "commit_base": None, "commit_head": None,
        "exit_base": None, "exit_head": None,
        "stdout_base": "", "stdout_head": "",
        # estado e' o campo autoritativo -- calculado em Python, o LLM nao toca.
        # motivo explica qualquer nao-PROVADO. erro e' SO falha de infra.
        "estado": "INCONCLUSIVO", "provado": False,
        "motivo": "a prova nao chegou a rodar", "erro": None,
        "segundos": 0.0,
    }
    escritos: list[Path] = []

    # Recusa ANTES de executar: um teste que escreve no banco da aplicacao
    # destroi o seed, e nao ha como desfazer depois de rodar.
    recusa = _valida_codigo_do_teste(codigo_do_teste)
    if recusa:
        art["motivo"] = recusa
        cfg.ARTEFATOS.mkdir(parents=True, exist_ok=True)
        (cfg.ARTEFATOS / f"prova_{art['id']}.json").write_text(
            json.dumps(art, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return art

    try:
        base, head = commit_base(), commit_head()
        art["commit_base"], art["commit_head"] = base[:7], head[:7]

        wt_base = _garante_worktree(base, "base")
        wt_head = _garante_worktree(head, "head")

        for wt in (wt_base, wt_head):
            destino = wt / "app" / "api" / "tests" / nome
            destino.write_text(codigo_do_teste, encoding="utf-8")
            escritos.append(destino)

        alvo = f"tests/{nome}"
        # O BASE roda CONTIDO: e' o lado onde mora o risco que so' nos criamos.
        # A CI do cliente roda o head a cada push; o base ninguem roda mais, e
        # foi rodando o base que o agente apagou o banco em 11/08.
        contido = not cfg.PERMITIR_REDE_NO_BASE
        art["base_contido"] = contido
        art["exit_base"], art["stdout_base"], rodou_base = _roda_pytest(
            wt_base, alvo, contido=contido)
        art["exit_head"], art["stdout_head"], rodou_head = _roda_pytest(wt_head, alvo)
        art["rodou_base"], art["rodou_head"] = rodou_base, rodou_head
        art["estado"], art["provado"], art["motivo"] = _classifica(
            art["exit_base"], art["exit_head"], rodou_base, rodou_head
        )

        # 🚫 Inconclusivo MUDO por causa nossa e' pior que a doenca: incha a
        # lista e faz o parecer parecer fraco por culpa da contencao, nao do PR.
        # Se o base morreu por falta de rede, o motivo diz isso E diz a saida.
        if (contido and not art["provado"]
                and falhou_por_isolamento(art.get("stdout_base", ""))):
            art["estado"], art["provado"] = "INCONCLUSIVO", False
            art["isolamento_bloqueou"] = True
            art["motivo"] = (
                "o arnes de teste deste repositorio precisa de REDE EXTERNA, e o "
                "lado base roda contido. Isto NAO e' defeito do PR. Rodar o base "
                "com rede pode disparar efeito irreversivel (email de verdade, "
                "cobranca, webhook), entao a decisao e' de quem conhece a suite: "
                "libere com PERMITIR_REDE_NO_BASE=1 se souber que e' seguro."
            )

        # CONFIRMACAO: so para quem seria PROVADO, roda o base DE NOVO, depois
        # do head. Custa ~7s e so nos candidatos a condenacao.
        #
        # Mata dois falsos positivos de uma vez: teste nao-deterministico, e
        # poluicao de estado -- o banco `kb` da aplicacao nunca e' limpo entre
        # execucoes, e o head sempre roda depois do base, entao "passou antes,
        # falhou depois" pode ser a ordem e nao o codigo. Se o base nao repete
        # o exit 0 depois do head, a diferenca nao era a mudanca do PR.
        if art["estado"] == "PROVADO":
            e2, s2, rodou2 = _roda_pytest(wt_base, alvo)
            art["exit_base_confirmacao"] = e2
            if not rodou2:
                art["estado"], art["provado"] = "INCONCLUSIVO", False
                art["motivo"] = "confirmacao no base nao rodou -- infraestrutura instavel"
                art["erro"] = _corta(s2, 500)
            elif e2 != 0:
                art["estado"], art["provado"] = "INCONCLUSIVO", False
                art["motivo"] = (
                    f"o teste passou no base, falhou no head, mas ao repetir no base "
                    f"deu exit {e2}. Entao ele nao e' deterministico ou depende de "
                    "estado acumulado, e a diferenca nao pode ser atribuida ao PR."
                )

        # O CONTRATO promete `erro` preenchido quando o docker cai. Sem isto so
        # a excecao preenchia, e o docker devolvendo exit 1 nao levanta excecao
        # nenhuma -- a promessa era falsa.
        if not rodou_base or not rodou_head:
            lado = "base" if not rodou_base else "head"
            art["erro"] = (
                f"pytest nao executou no {lado} (exit "
                f"{art['exit_base'] if lado == 'base' else art['exit_head']} veio do docker). "
                + _corta(art[f"stdout_{lado}"], 500)
            )
    except subprocess.TimeoutExpired:
        art["erro"] = f"timeout: passou de {cfg.TIMEOUT_PYTEST_S}s"
    except Exception as e:  # nunca virar absolvicao por silencio
        art["erro"] = f"{type(e).__name__}: {e}"
    finally:
        # Falha de infra nunca e' absolvicao: estado volta a INCONCLUSIVO, e o
        # motivo passa a ser a causa tecnica. Fica no finally de proposito --
        # e' a ultima palavra, aconteca o que acontecer acima.
        if art["erro"]:
            art["estado"], art["provado"] = "INCONCLUSIVO", False
            art["motivo"] = art["erro"]
        for p in escritos:  # worktree limpo para a proxima acusacao
            p.unlink(missing_ok=True)
        art["segundos"] = round(time.time() - inicio, 1)
        cfg.ARTEFATOS.mkdir(parents=True, exist_ok=True)
        (cfg.ARTEFATOS / f"prova_{art['id']}.json").write_text(
            json.dumps(art, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (cfg.ARTEFATOS / f"teste_{art['id']}_{nome}").write_text(
            codigo_do_teste, encoding="utf-8"
        )
    return art


def _formata_prova(art: dict) -> str:
    linhas = [
        f"PROVA DIFERENCIAL -- {art['arquivo_do_teste']}",
        f"  base {art['commit_base']}: exit {art['exit_base']}",
        f"  head {art['commit_head']}: exit {art['exit_head']}",
        f"  => {art['estado']}: {art['motivo']}",
    ]
    if art["erro"]:
        linhas.append(f"  falha de execucao: {art['erro']}")
    if art["estado"] == "PROVADO":
        linhas.append("  Este teste passa no codigo de hoje e quebra com a mudanca do PR.")
    linhas.append(f"  artefato: artefatos/prova_{art['id']}.json ({art['segundos']}s)")
    if art["stdout_head"]:
        linhas += ["--- saida no head ---", _corta(art["stdout_head"], 2000)]
    if art["estado"] != "PROVADO" and art["stdout_base"]:
        linhas += ["--- saida no base ---", _corta(art["stdout_base"], 1500)]
    return "\n".join(linhas)


# ------------------------------------------------------------ leitura do repo

def _worktree_de(lado: str) -> Path:
    commit = commit_head() if lado == "head" else commit_base()
    return _garante_worktree(commit, lado)


def _resolve_caminho(raiz: Path, caminho: str) -> Path | None:
    """Acha o arquivo mesmo quando a raiz do caminho vem errada.

    Os promotores discordam entre si sobre a raiz: 29 acusacoes disseram
    `app/routers/shares.py` e 20 disseram `app/api/app/routers/shares.py` para o
    MESMO arquivo. Sem isto o advogado gasta voltas do loop descobrindo que o
    caminho nao existe -- e volta gasta e' acusacao que morre inconclusiva.
    """
    rel = caminho.strip().lstrip("/\\").replace("\\", "/")
    alvo = (raiz / rel).resolve()
    if alvo.is_file():
        return alvo
    # sufixo: 'app/routers/shares.py' casa com '.../app/api/app/routers/shares.py'
    casam = [p for p in raiz.rglob(Path(rel).name)
             if p.is_file() and p.as_posix().endswith(rel)]
    return casam[0] if len(casam) == 1 else None


_CACHE_LOCAL: dict[str, str] = {}


def normaliza_local(local: str) -> str:
    """Reescreve `app/routers/shares.py:31` no caminho que existe de verdade.

    O `local` vem do promotor e vai CRU para o parecer. Os promotores discordam
    entre si sobre a raiz (ver _resolve_caminho: 24, 20 e 7 acusacoes desta
    rodada citaram o mesmo arquivo com tres grafias), entao o slide pode exibir
    um caminho que ninguem acha no repo -- e caminho que nao abre no palco custa
    mais que estas linhas.

    E' cosmetica, e se comporta como tal: NAO cria worktree e NUNCA levanta. Sem
    worktree no disco, com caminho ambiguo ou com diretorio em vez de arquivo,
    devolve o que recebeu.
    """
    if not local:
        return local
    if local in _CACHE_LOCAL:
        return _CACHE_LOCAL[local]
    resultado = local
    try:
        raiz = cfg.WORKTREES / "head"
        if raiz.is_dir():
            caminho, sep, sufixo = local.strip().partition(":")
            alvo = _resolve_caminho(raiz, caminho)
            if alvo is not None:
                resultado = alvo.relative_to(raiz.resolve()).as_posix() + sep + sufixo
    except (OSError, ValueError):
        resultado = local
    _CACHE_LOCAL[local] = resultado
    return resultado


def _read_file(caminho: str, lado: str = "head") -> str:
    raiz = _worktree_de(lado)
    alvo = _resolve_caminho(raiz, caminho)
    if alvo is None:
        return _marca_falha(
            f"ERRO: {caminho} nao existe em {lado} (nem como sufixo de outro caminho).")
    if raiz.resolve() not in alvo.parents:
        return _marca_falha(f"ERRO: {caminho} sai da raiz do repo.")
    texto = alvo.read_text(encoding="utf-8", errors="replace")
    # numerado, porque a acusacao pede 'arquivo:linha' e chute de linha nao cola
    numerado = "\n".join(f"{i:5d} | {l}" for i, l in enumerate(texto.splitlines(), 1))
    return _corta(numerado)


_IGNORA = {".git", "node_modules", ".next", "__pycache__", ".venv", "dist", "build"}


def _grep(padrao: str, glob: str = "", lado: str = "head", teto: int = 200) -> str:
    raiz = _worktree_de(lado)
    try:
        rx = re.compile(padrao)
    except re.error as e:
        return _marca_falha(f"ERRO: regex invalida: {e}")
    achados: list[str] = []
    for p in raiz.rglob(glob or "*"):
        if not p.is_file() or _IGNORA & set(p.relative_to(raiz).parts):
            continue
        try:
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, linha in enumerate(texto.splitlines(), 1):
            if rx.search(linha):
                achados.append(f"{p.relative_to(raiz).as_posix()}:{i}: {linha.strip()[:200]}")
                if len(achados) >= teto:
                    achados.append(f"[... cortado no teto de {teto} ...]")
                    return "\n".join(achados)
    return "\n".join(achados) if achados else f"nenhum resultado para /{padrao}/ em {lado}."


# ---------------------------------------------------------------------- http

_TOKENS: dict[str, str] = {}

# Metodos seguros de repetir quando a RESPOSTA se perde. Num ReadTimeout o
# pedido pode ter sido aplicado; repetir um POST criaria o recurso duas vezes e
# sujaria o raciocinio do advogado. ConnectionError e' diferente -- a conexao
# nunca subiu, nada foi aplicado -- e por isso se repete para qualquer metodo.
_IDEMPOTENTES = {"GET", "HEAD", "OPTIONS"}


def _com_retry(metodo: str, chamada):
    """Repete falha de conexao. Sem isto, o warm-up de ~30s da api e qualquer
    soluco de rede viram INCONCLUSIVO -- e inconclusivo nao se recupera."""
    ultimo = None
    for tentativa in range(cfg.TENTATIVAS_HTTP):
        try:
            return chamada()
        except requests.exceptions.ConnectionError as e:
            ultimo = e
        except requests.exceptions.Timeout as e:
            ultimo = e
            if metodo.upper() not in _IDEMPOTENTES:
                break  # pode ter sido aplicado; repetir seria pior
        if tentativa < cfg.TENTATIVAS_HTTP - 1:
            time.sleep(2 * (tentativa + 1))
    raise ultimo


def _token(usuario: str) -> str:
    if usuario in _TOKENS:
        return _TOKENS[usuario]
    if usuario not in cfg.USUARIOS:
        raise RuntimeError(f"usuario desconhecido: {usuario}. Use: {', '.join(cfg.USUARIOS)}")
    email, senha = cfg.USUARIOS[usuario]
    # login e' idempotente na pratica: nao cria recurso, so devolve token.
    r = _com_retry("GET", lambda: requests.post(
        f"{cfg.APP_API_URL}/auth/login",
        json={"email": email, "password": senha},
        timeout=cfg.TIMEOUT_HTTP_S,
    ))
    r.raise_for_status()
    tok = r.json()["access_token"]
    _TOKENS[usuario] = tok
    return tok


def _grava_chamada_http(chamada: dict) -> None:
    """Registra a chamada no artefato da acusacao. Grava a CADA chamada.

    🚨 Sem isto, `http_request` era a unica das cinco ferramentas que nao deixava
    rastro -- e o CONTRATO diz que ela e' a unica que sustenta severidade alta. O
    resultado combinado era incoerente nas duas pontas: o parecer imprimia
    "EVIDENCIA: nao fechou" para um defeito que o advogado tinha visto acontecer,
    e a Regra 0 pulava a conferencia inteira (o bloco mora sob
    `if artefato is not None`), deixando a auto-declaracao do modelo valer
    sozinha -- o oposto exato do que a R0 existe para fazer.

    ⚠️ `alcancou_a_api` diz uma coisa so', e o nome e' literal de proposito: esta
    acusacao produziu ao menos uma chamada que COMPLETOU contra o app rodando --
    inclusive um 404. NAO significa "o defeito foi alcancado", e o parecer nao
    pode prometer mais do que da' para apurar mecanicamente aqui.

    Combinado com a declaracao do advogado (AND, no juiz), o que fica garantido
    e': quem alega prova ponta a ponta tocou mesmo a API nesta acusacao. Se o
    modelo mentir sobre o CONTEUDO da resposta isso nao pega -- mas o status e o
    corpo ficam no disco, e quem le e' humano. O buraco que fecha e' o outro, o
    mudo: declarar prova por API sem nunca ter chamado nada.

    O advogado nao escreve este campo e nao pode contradize-lo.
    """
    # Fora de acusacao nao e' evidencia. A sonda do llm_alvo na subida da rodada
    # bate em /chat como demo antes de existir acusacao, e gravava
    # `http_sem_id.json` no meio dos artefatos -- medicao de ambiente parecendo
    # prova, justo no diretorio que o parecer cita como evidencia.
    if _ACUSACAO_ATUAL == "sem_id":
        return

    _HTTP.setdefault(_ACUSACAO_ATUAL, []).append(chamada)
    chamadas = _HTTP[_ACUSACAO_ATUAL]
    art = {
        "id": _ACUSACAO_ATUAL,
        "tipo": "http",
        "chamadas": chamadas,
        "alcancou_a_api": any(c["status"] is not None and not c["erro"] for c in chamadas),
    }
    cfg.ARTEFATOS.mkdir(parents=True, exist_ok=True)
    (cfg.ARTEFATOS / f"http_{_ACUSACAO_ATUAL}.json").write_text(
        json.dumps(art, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _http_request(metodo: str, caminho: str, corpo: str = "", como_usuario: str = "") -> dict:
    saida = {"status": None, "corpo": "", "erro": None, "como": como_usuario or "anonimo"}
    metodo = metodo.upper().strip() or "GET"
    alvo = "/" + caminho.strip().lstrip("/")
    try:
        cabecalhos = {}
        if como_usuario:
            cabecalhos["Authorization"] = f"Bearer {_token(como_usuario)}"
        payload = json.loads(corpo) if corpo.strip() else None
        r = _com_retry(metodo, lambda: requests.request(
            metodo,
            f"{cfg.APP_API_URL}{alvo}",
            json=payload, headers=cabecalhos, timeout=cfg.TIMEOUT_HTTP_S,
        ))
        saida["status"] = r.status_code
        saida["corpo"] = r.text
    except Exception as e:
        saida["erro"] = f"{type(e).__name__}: {e}"

    _grava_chamada_http({
        "metodo": metodo, "caminho": alvo, "como": saida["como"],
        "status": saida["status"], "erro": saida["erro"],
        # truncado: o artefato e' evidencia para humano ler, nao dump de resposta
        "corpo": _corta(saida["corpo"], 1500),
    })
    return saida


# ------------------------------------------------------------- as tools do SDK
# As docstrings abaixo sao o que o modelo le. Sao produto, nao comentario.

@beta_tool
def prova_diferencial(codigo_do_teste: str, nome_do_arquivo: str) -> str:
    """Roda um teste no commit base e no head do PR, e compara os dois lados.

    Esta e' a unica forma de PROVAR uma acusacao. Provado significa: o teste
    passa no codigo de hoje e falha com a mudanca do PR. Qualquer outra
    combinacao nao e' prova.

    Escreva um teste pytest completo e autocontido, no estilo dos que ja
    existem em tests/. Ele roda dentro do container, contra o banco kb_test.

    Args:
        codigo_do_teste: o arquivo de teste inteiro, em python.
        nome_do_arquivo: ex. test_vazamento_tenant.py
    """
    _abre_chamada()
    art = _prova_diferencial(codigo_do_teste, nome_do_arquivo)
    saida = _formata_prova(art)
    # Falha vem do CAMPO do artefato, nao de farejar o texto formatado. O
    # artefato ja sabe se a execucao quebrou -- e' a mesma fonte que a R3 le.
    if art.get("erro"):
        _marca_falha(f"prova_diferencial: {art['erro']}")
    return _fecha_chamada("prova_diferencial", saida)


@beta_tool
def run_tests(expressao: str = "") -> str:
    """Roda a suite de testes ja existente contra o codigo do PR.

    Serve para ver se a mudanca quebrou algo que ja era testado. Para provar
    uma acusacao nova, use prova_diferencial.

    Args:
        expressao: nome de arquivo dentro de tests/, ex. test_documents.py.
            Vazio roda a suite inteira.
    """
    _abre_chamada()
    try:
        wt = _worktree_de("head")
        alvo = f"tests/{Path(expressao).name}" if expressao.strip() else "tests"
        codigo, saida, rodou = _roda_pytest(wt, alvo)
        if not rodou:
            return _fecha_chamada("run_tests", _marca_falha(
                f"ERRO DE INFRAESTRUTURA: o pytest nao chegou a rodar. O exit {codigo} "
                f"veio do docker, nao do teste. Nao conclua nada sobre o codigo.\n{_corta(saida)}"
            ))
        return _fecha_chamada("run_tests", f"exit {codigo}\n{_corta(saida)}")
    except Exception as e:
        return _fecha_chamada("run_tests", _marca_falha(
            f"ERRO ao rodar os testes: {type(e).__name__}: {e}"))


@beta_tool
def read_file(caminho: str) -> str:
    """Le um arquivo do codigo sob revisao (o head do PR), com numero de linha.

    Args:
        caminho: caminho relativo a raiz do repo, ex. app/api/app/rag.py
    """
    _abre_chamada()
    try:
        return _fecha_chamada("read_file", _read_file(caminho))
    except Exception as e:
        return _fecha_chamada("read_file", _marca_falha(
            f"ERRO ao ler {caminho}: {type(e).__name__}: {e}"))


@beta_tool
def grep(padrao: str, glob: str = "") -> str:
    """Procura uma regex no codigo sob revisao. Devolve arquivo:linha: conteudo.

    Args:
        padrao: expressao regular.
        glob: filtro de arquivo, ex. **/*.py. Vazio busca em tudo.
    """
    _abre_chamada()
    try:
        return _fecha_chamada("grep", _grep(padrao, glob))
    except Exception as e:
        return _fecha_chamada("grep", _marca_falha(
            f"ERRO no grep: {type(e).__name__}: {e}"))


@beta_tool
def http_request(metodo: str, caminho: str, corpo: str = "", como_usuario: str = "") -> str:
    """Chama a API do app rodando, autenticado como um dos usuarios do seed.

    Use para provar que uma falha e' alcancavel de fora, e nao so teorica.
    Os usuarios existem para testar isolamento: demo tem 3 documentos, alice e
    bob tem 1 cada, e carol NAO TEM NADA -- carol e' o controle negativo, entao
    qualquer dado de outro usuario que apareca para ela e' vazamento.

    Args:
        metodo: GET, POST, PATCH ou DELETE.
        caminho: ex. /documents/3
        corpo: JSON como string. Vazio para GET.
        como_usuario: demo, alice, bob ou carol. Vazio chama sem autenticacao.
    """
    _abre_chamada()
    r = _http_request(metodo, caminho, corpo, como_usuario)
    if r["erro"]:
        # De novo o CAMPO, e nao o texto: `_http_request` ja devolve o desfecho
        # estruturado, entao nao ha o que adivinhar.
        return _fecha_chamada("http_request", _marca_falha(
            f"ERRO ({r['como']}): {r['erro']}"))
    saida = f"HTTP {r['status']} (como {r['como']})\n{_corta(r['corpo'], 3000)}"

    # Deteccao por SONDA (llm_alvo), nao por comparar com a string enlatada:
    # duas perguntas sem nada em comum devolvendo a mesma resposta provam que o
    # modelo nao leu nenhuma das duas. Isso pega chave ausente, rate limit que
    # cai no fallback e stub trocado, sem precisar saber qual foi -- e sobrevive
    # ao texto enlatado mudar.
    aviso = llm_alvo.aviso_se_duble(caminho)
    if aviso:
        # Aviso em texto e' conselho, e o modelo pode ignorar. Registrar por
        # acusacao e' o que deixa o juiz aplicar a R3b mecanicamente depois.
        _avisa(cfg.AVISO_SEM_MODELO)
    # O app respondeu: a FERRAMENTA funcionou. Que o modelo do alvo seja um
    # duble e' problema da R4, e nao contagem de ferramenta -- misturar os dois
    # faria a R3b disparar por um motivo que nao e' o dela.
    return _fecha_chamada("http_request", saida + aviso)


TOOLS = [prova_diferencial, run_tests, read_file, grep, http_request]


# ----------------------------------------------------------------- pre-voo

# Ferramentas sem as quais a rodada nao produz NADA. `http_request`,
# `run_tests` e `prova_diferencial` ficam de fora de proposito: sem elas a
# rodada degrada (nao ha prova ponta a ponta), mas ainda decide por leitura --
# foi assim que 26 das 38 acusacoes de 10/08 foram refutadas.
ESSENCIAIS = ("read_file", "grep")


def autoteste(sondar_app: bool = True) -> dict:
    """Exercita cada ferramenta uma vez, ANTES da rodada.

    🚨 Por que isto existe: em 10/08 a worktree do desafio estava corrompida
    (um `.git` diretorio vazio deixado por uma criacao parcial). Toda chamada de
    `read_file`/`grep` voltou RuntimeError, e o advogado devolveu PROVADO duas
    vezes -- infraestrutura podre virou veredito positivo, e o modo de falha foi
    "PROVADO", nao "erro". A R3b do juiz pega isso depois; este pre-voo pega
    antes, por segundos em vez de ~US$0,71 de rodada condenada.

    Devolve `{"ok": bool, "ferramentas": {nome: {"ok", "detalhe"}}}`. `ok` e'
    False so quando ESSENCIAL falha -- app fora do ar e' degradacao conhecida,
    nao motivo para nao comecar.
    """
    r: dict[str, dict] = {}

    # A sonda de leitura precisa de um alvo que EXISTA. Achar um arquivo real na
    # worktree e' parte do teste: se nem listar da', o problema e' anterior.
    alvo = None
    try:
        raiz = _worktree_de("head")
        for p in sorted(raiz.rglob("*.py")) + sorted(raiz.rglob("*.ts")):
            # Arquivo VAZIO nao serve de sonda: `__init__.py` le como "" e a
            # leitura bem-sucedida seria indistinguivel da falha.
            if not any(x in p.parts for x in _IGNORA) and p.stat().st_size > 80:
                alvo = p.relative_to(raiz).as_posix()
                break
        if alvo is None:
            r["read_file"] = {"ok": False, "detalhe": f"nenhum arquivo em {raiz}"}
    except Exception as e:
        r["read_file"] = {"ok": False, "detalhe": f"worktree: {type(e).__name__}: {e}"}

    if alvo is not None:
        saida = _read_file(alvo)
        deu = not saida.lstrip().startswith("ERRO") and "|" in saida
        r["read_file"] = {
            "ok": deu,
            "detalhe": f"{alvo}: {len(saida)} chars" if deu else saida[:160],
        }

    # Padrao que casa com qualquer linha nao vazia: o que esta sob teste e' a
    # ferramenta, nao a regex.
    try:
        saida = _grep(r".", glob="**/*.py", teto=3)
        deu = not saida.lstrip().startswith("ERRO") and ":" in saida
        r["grep"] = {"ok": deu, "detalhe": "casou" if deu else saida[:160]}
    except Exception as e:
        r["grep"] = {"ok": False, "detalhe": f"{type(e).__name__}: {e}"}

    if sondar_app:
        try:
            resp = _http_request("GET", "/health")
            deu = bool(resp.get("status"))
            r["http_request"] = {
                "ok": deu,
                "detalhe": f"GET /health -> {resp.get('status')}" if deu
                else str(resp.get("erro"))[:160],
            }
        except Exception as e:
            r["http_request"] = {"ok": False, "detalhe": f"{type(e).__name__}: {e}"}

    return {"ok": all(r.get(n, {}).get("ok") for n in ESSENCIAIS), "ferramentas": r}
