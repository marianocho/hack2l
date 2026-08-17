"""hack2l / Veredito -- "revise este PR", traduzido para o que a maquina consome.

A maquinaria toda ja sabe trabalhar com (repositorio local, commit base, commit
head). O que faltava era a porta: dado um endereco de PR, produzir esses tres.

    resolve("https://github.com/dono/repo/pull/123")
      -> {"repo": Path(".repos/dono_repo"), "base": "<sha>", "head": "<sha>", ...}

Nao decide nada sobre a rodada, nao chama modelo, nao sobe app. So' localiza.

🚨 O BASE E' O MERGE-BASE, NAO O TOPO DO RAMO ALVO

`pulls/{n}` devolve `base.sha` = o topo do ramo de destino AGORA. Se a `main`
andou depois que o PR foi aberto, esse commit carrega mudancas que nao sao do
PR -- e a prova diferencial ("passa no base, falha no head") passaria a medir o
PR *mais* o que entrou na main no meio. Falso positivo com cara de prova.

O commit certo e' de onde o PR realmente saiu, e quem sabe dele e' o endpoint
`compare`, no campo `merge_base_commit`. Custa uma chamada a mais e e' a
diferenca entre provar o PR e provar o PR somado a outra coisa.

⚠️ E NAO DA' PARA CALCULAR LOCALMENTE: `git merge-base` precisa da historia dos
dois lados, e aqui o clone e' raso de proposito (dois commits, nao o repo
inteiro). Perguntar ao GitHub e' o caminho barato e correto.

## O que este PR vai render, e e' bom saber antes de gastar

Num repositorio de terceiro sem `veredito.yml`, o advogado tem `read_file` e
`grep` -- e mais nada. Sem app no ar nao ha `http_request`; sem compose
declarado nao ha `prova_diferencial`. O parecer sai com refutacao fundamentada
(68% medido em 10 PRs reais) e severidade no maximo MEDIA, porque a R2 rebaixa
o que nao e' ponta a ponta.

Isso nao e' defeito da entrada. E' o que muda quando o projeto se descreve: o
`veredito.yml` na raiz do repo revisado devolve as ferramentas todas, e com
elas a possibilidade de CRITICA. `projeto.caminho()` ja procura la' primeiro.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]

# A mesma regex vivia copiada em `generaliza.py` e `controle_negativo.py`. Duas
# fontes para a mesma informacao divergem em silencio -- a licao que a chave da
# API custou em 14/08. Esta e' a de casa.
PR_URL = re.compile(r"github\.com/([^/]+?)/([^/]+?)/pull/(\d+)")

TIMEOUT_API = 30
TIMEOUT_FETCH = 600


class EntradaFalhou(RuntimeError):
    """Nao consegui transformar o endereco em (repo, base, head)."""


def _cabecalhos() -> dict:
    """`GH_TOKEN` quando existir: repo privado e o limite de 60/h sem auth."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def partes(url: str) -> tuple[str, str, int]:
    m = PR_URL.search(url.strip())
    if not m:
        raise EntradaFalhou(
            f"nao parece endereco de PR do GitHub: {url!r}. "
            "Formato: https://github.com/<dono>/<repo>/pull/<numero>")
    dono, repo, num = m.groups()
    return dono, repo.removesuffix(".git"), int(num)


def _pega(url: str, cabecalhos: dict | None = None) -> dict:
    r = requests.get(url, timeout=TIMEOUT_API,
                     headers={**_cabecalhos(), **(cabecalhos or {})})
    if r.status_code == 404:
        # 🚨 404 do GitHub e' ambiguo: repositorio privado SEM acesso responde
        # 404, nao 403. A mensagem diz "not found" e manda procurar no lugar
        # errado -- exatamente o que aconteceu com a bancada em 16/08.
        raise EntradaFalhou(
            f"404 em {url} -- pode nao existir, ou pode ser privado e o token "
            "nao ter acesso. O GitHub responde igual nos dois casos. "
            "Confira o endereco e, se for privado, exporte GH_TOKEN.")
    if r.status_code == 403 and "rate limit" in r.text.lower():
        raise EntradaFalhou(
            "limite de chamadas do GitHub (60/h sem autenticacao). "
            "Exporte GH_TOKEN para subir para 5000/h.")
    r.raise_for_status()
    return r.json()


def commits_do_pr(dono: str, repo: str, num: int) -> tuple[str, str, dict]:
    """(merge_base, head, metadados). Ver o cabecalho sobre o merge-base."""
    api = f"https://api.github.com/repos/{dono}/{repo}"
    pr = _pega(f"{api}/pulls/{num}")
    head = (pr.get("head") or {}).get("sha")
    base_ramo = (pr.get("base") or {}).get("sha")
    if not head or not base_ramo:
        raise EntradaFalhou(f"PR sem head/base no retorno da API: {dono}/{repo}#{num}")

    comp = _pega(f"{api}/compare/{base_ramo}...{head}")
    base = ((comp.get("merge_base_commit") or {}).get("sha")) or base_ramo

    info = {
        "url": pr.get("html_url"), "repo": f"{dono}/{repo}", "numero": num,
        "titulo": pr.get("title"),
        "descricao": (pr.get("body") or "").strip(),
        "arquivos": pr.get("changed_files"),
        "adicoes": pr.get("additions"), "remocoes": pr.get("deletions"),
        "base_do_ramo": base_ramo, "merge_base": base, "head": head,
        # Quando os dois diferem, a `main` andou depois de o PR abrir. Fica
        # registrado no artefato: quem auditar amanha precisa saber contra o
        # que a prova diferencial rodou.
        "base_deslocou": base != base_ramo,
    }
    return base, head, info


def _git(clone: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(clone), *args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _garante_clone(dono: str, repo: str) -> Path:
    """Repo vazio com o remoto configurado. Idempotente."""
    clone = RAIZ / ".repos" / f"{dono}_{repo}"
    if (clone / ".git").is_dir():
        return clone
    clone.mkdir(parents=True, exist_ok=True)
    r = _git(clone, "init", "-q")
    if r.returncode != 0:
        raise EntradaFalhou(f"git init falhou em {clone}: {r.stderr.strip()[:200]}")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    # 🚫 O token vai na chamada, NUNCA no remote: `git remote -v` e o
    # `.git/config` guardariam a credencial em texto no disco.
    _git(clone, "remote", "add", "origin",
         f"https://github.com/{dono}/{repo}.git")
    if token:
        _git(clone, "config", "http.extraheader", f"Authorization: Bearer {token}")
    return clone


def busca_os_dois(clone: Path, base: str, head: str) -> None:
    """Traz base E head. Raso: sao dois commits, nao o repositorio inteiro.

    🚨 O `controle_negativo.py` buscava so' o head e apontava o base para o
    MESMO sha, com o comentario "nao usamos base aqui". Para revisar de verdade
    os dois sao obrigatorios -- sem o base nao existe prova diferencial, que e'
    a unica via que assina PROVADO junto com o arbitro.
    """
    for sha, papel in ((base, "base"), (head, "head")):
        r = _git(clone, "fetch", "-q", "--depth", "1", "origin", sha,
                 timeout=TIMEOUT_FETCH)
        if r.returncode != 0:
            raise EntradaFalhou(
                f"nao consegui buscar o commit {papel} ({sha[:8]}): "
                f"{r.stderr.strip()[:200]}")
        # Conferir que o objeto chegou -- fetch pode sair 0 sem trazer o que se
        # pediu quando o servidor recusa busca por sha solto.
        c = _git(clone, "cat-file", "-e", f"{sha}^{{commit}}")
        if c.returncode != 0:
            raise EntradaFalhou(
                f"o fetch do {papel} saiu 0 mas o commit {sha[:8]} nao esta no "
                "clone. O servidor pode nao permitir busca por sha solto "
                "(uploadpack.allowReachableSHA1InWant desligado).")


def resolve(url: str) -> dict:
    """"Revise este PR" -> (repo local, base, head). E' a porta inteira."""
    dono, repo, num = partes(url)
    base, head, info = commits_do_pr(dono, repo, num)
    clone = _garante_clone(dono, repo)
    busca_os_dois(clone, base, head)
    info["repo_local"] = clone
    info["worktrees"] = RAIZ / ".repos" / f"wt_{dono}_{repo}"
    return info


def ambiente(info: dict) -> dict:
    """As variaveis que o orquestrador le NA IMPORTACAO.

    Devolve em vez de aplicar: o config resolve `PROJETO` a partir de
    `CHALLENGE_REPO` no momento do import, entao trocar depois deixaria metade
    da configuracao apontando para o projeto anterior. Quem chama poe isto no
    ambiente ANTES de subir o orquestrador -- mesmo desenho do roda_bancada.
    """
    return {
        "CHALLENGE_REPO": str(info["repo_local"]),
        "PR_BRANCH": info["head"],
        "BASE_BRANCH": info["merge_base"],
        "WORKTREES_DIR": str(info["worktrees"]),
        # O merge-base veio do `compare` do GitHub. Sem isto, `commit_base`
        # tentaria recalcular com `git merge-base` -- que nao funciona em clone
        # raso, e matava a rodada DEPOIS de o pre-voo passar.
        "BASE_JA_RESOLVIDO": "1",
    }
