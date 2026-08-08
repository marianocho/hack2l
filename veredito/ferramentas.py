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
    """Worktree idempotente. O advogado chama isto em loop; recriar toda vez
    seria minutos jogados fora ao longo da rodada."""
    destino = cfg.WORKTREES / nome
    if destino.exists():
        atual = _git("rev-parse", "HEAD", cwd=destino)
        if atual.returncode == 0 and atual.stdout.strip() == commit:
            return destino
        _git("worktree", "remove", "--force", str(destino))
    cfg.WORKTREES.mkdir(parents=True, exist_ok=True)
    r = _git("worktree", "add", "--detach", str(destino), commit)
    if r.returncode != 0 and not destino.exists():
        raise RuntimeError(f"git worktree add falhou: {r.stderr.strip()}")
    return destino


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

def _roda_pytest(worktree: Path, alvo: str = "tests") -> tuple[int, str]:
    """Roda a suite dentro do container, com o codigo do worktree por cima.

    Bind-mount e nao rebuild: o Dockerfile faz COPY do codigo e o compose nao
    monta volume nenhum no servico api, entao sem estes -v o pytest roda o
    codigo assado na imagem e a prova diferencial da o MESMO resultado nos dois
    lados -- falso negativo silencioso. Provado com canario em 08/08.
    """
    cmd = [
        "docker", "compose", "-f", str(cfg.COMPOSE),
        "--project-directory", str(cfg.DESAFIO),
        "run", "--rm",
        "-v", f"{worktree / 'app' / 'api' / 'app'}:/code/app",
        "-v", f"{worktree / 'app' / 'api' / 'tests'}:/code/tests",
        "api", "python", "-m", "pytest", alvo, "-q",
    ]
    r = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=cfg.TIMEOUT_PYTEST_S,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# Codigos do pytest: 0 passou | 1 falhou | 2 interrompido | 3 erro interno
#                    4 erro de uso | 5 nenhum teste coletado
_CAUSA = {
    2: "execucao interrompida",
    3: "erro interno do pytest",
    4: "erro de uso do pytest",
    5: "nenhum teste foi coletado -- o arquivo nao casa com o padrao ou nao compila",
}


def _classifica(exit_base: int, exit_head: int) -> tuple[str, bool, str]:
    """A regra central, em codigo. O LLM nao participa desta decisao.

    Devolve (estado, provado, motivo). `motivo` explica todo estado que nao e'
    PROVADO -- e' o texto que vira a lista de descartados e a de inconclusivos
    no parecer. NAO confundir com `erro`, que e' so falha de infraestrutura:
    refutacao com motivo e' um resultado valido, nao um erro.

    Exigir exit_head == 1 (e nao != 0) e' deliberado: tratar erro de execucao
    como prova transformaria docker fora do ar em condenacao critica.
    """
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
        art["exit_base"], art["stdout_base"] = _roda_pytest(wt_base, alvo)
        art["exit_head"], art["stdout_head"] = _roda_pytest(wt_head, alvo)
        art["estado"], art["provado"], art["motivo"] = _classifica(
            art["exit_base"], art["exit_head"]
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


def _read_file(caminho: str, lado: str = "head") -> str:
    raiz = _worktree_de(lado)
    alvo = (raiz / caminho.strip().lstrip("/\\")).resolve()
    if raiz.resolve() not in alvo.parents and alvo != raiz.resolve():
        return f"ERRO: {caminho} sai da raiz do repo."
    if not alvo.is_file():
        return f"ERRO: {caminho} nao existe em {lado}."
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
        return f"ERRO: regex invalida: {e}"
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


def _http_request(metodo: str, caminho: str, corpo: str = "", como_usuario: str = "") -> dict:
    saida = {"status": None, "corpo": "", "erro": None, "como": como_usuario or "anonimo"}
    metodo = metodo.upper().strip() or "GET"
    try:
        cabecalhos = {}
        if como_usuario:
            cabecalhos["Authorization"] = f"Bearer {_token(como_usuario)}"
        payload = json.loads(corpo) if corpo.strip() else None
        r = _com_retry(metodo, lambda: requests.request(
            metodo,
            f"{cfg.APP_API_URL}/{caminho.strip().lstrip('/')}",
            json=payload, headers=cabecalhos, timeout=cfg.TIMEOUT_HTTP_S,
        ))
        saida["status"] = r.status_code
        saida["corpo"] = r.text
    except Exception as e:
        saida["erro"] = f"{type(e).__name__}: {e}"
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
    return _formata_prova(_prova_diferencial(codigo_do_teste, nome_do_arquivo))


@beta_tool
def run_tests(expressao: str = "") -> str:
    """Roda a suite de testes ja existente contra o codigo do PR.

    Serve para ver se a mudanca quebrou algo que ja era testado. Para provar
    uma acusacao nova, use prova_diferencial.

    Args:
        expressao: nome de arquivo dentro de tests/, ex. test_documents.py.
            Vazio roda a suite inteira.
    """
    try:
        wt = _worktree_de("head")
        alvo = f"tests/{Path(expressao).name}" if expressao.strip() else "tests"
        codigo, saida = _roda_pytest(wt, alvo)
        return f"exit {codigo}\n{_corta(saida)}"
    except Exception as e:
        return f"ERRO ao rodar os testes: {type(e).__name__}: {e}"


@beta_tool
def read_file(caminho: str) -> str:
    """Le um arquivo do codigo sob revisao (o head do PR), com numero de linha.

    Args:
        caminho: caminho relativo a raiz do repo, ex. app/api/app/rag.py
    """
    try:
        return _read_file(caminho)
    except Exception as e:
        return f"ERRO ao ler {caminho}: {type(e).__name__}: {e}"


@beta_tool
def grep(padrao: str, glob: str = "") -> str:
    """Procura uma regex no codigo sob revisao. Devolve arquivo:linha: conteudo.

    Args:
        padrao: expressao regular.
        glob: filtro de arquivo, ex. **/*.py. Vazio busca em tudo.
    """
    try:
        return _grep(padrao, glob)
    except Exception as e:
        return f"ERRO no grep: {type(e).__name__}: {e}"


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
    r = _http_request(metodo, caminho, corpo, como_usuario)
    if r["erro"]:
        return f"ERRO ({r['como']}): {r['erro']}"
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
    return saida + aviso


TOOLS = [prova_diferencial, run_tests, read_file, grep, http_request]
