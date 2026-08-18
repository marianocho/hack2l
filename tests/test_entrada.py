"""A porta "revise este PR": endereco -> (repo local, base, head).

Nao bate na rede. O que se trava aqui e' o que a rede NAO conserta:

  - o base tem que ser o MERGE-BASE, nao o topo do ramo alvo. Se a `main` andou
    depois de o PR abrir, o topo carrega mudanca que nao e' do PR, e a prova
    diferencial passaria a medir o PR somado a outra coisa -- falso positivo
    com cara de prova.
  - os DOIS commits tem que ser buscados. O `controle_negativo.py` buscava so'
    o head e apontava o base para o mesmo sha; sem base nao ha prova
    diferencial, que e' a unica via que assina PROVADO junto com o arbitro.
  - fetch que sai 0 sem trazer o commit tem que LEVANTAR. Servidor com
    `allowReachableSHA1InWant` desligado recusa busca por sha solto, e o
    worktree seguinte montaria o commit errado -- falso negativo mudo, a mesma
    familia do `_garante_worktree`.
"""
import subprocess

import pytest

from veredito import entrada


# ------------------------------------------------------------- o endereco

@pytest.mark.parametrize("url,esperado", [
    ("https://github.com/psf/requests/pull/7576", ("psf", "requests", 7576)),
    ("http://github.com/dono/repo/pull/1", ("dono", "repo", 1)),
    ("github.com/a/b/pull/42", ("a", "b", 42)),
    ("  https://github.com/a/b/pull/42#discussion_r1  ", ("a", "b", 42)),
    ("https://github.com/a/b.git/pull/9", ("a", "b", 9)),
])
def test_reconhece_o_endereco(url, esperado):
    assert entrada.partes(url) == esperado


@pytest.mark.parametrize("ruim", [
    "https://github.com/dono/repo",              # repo, nao PR
    "https://github.com/dono/repo/issues/12",    # issue
    "https://gitlab.com/dono/repo/pull/12",      # outro host
    "pull/12",
    "",
])
def test_endereco_invalido_levanta_com_o_formato_certo(ruim):
    with pytest.raises(entrada.EntradaFalhou) as e:
        entrada.partes(ruim)
    assert "pull" in str(e.value), "a mensagem nao mostra o formato esperado"


# ------------------------------------------------- o base e' o merge-base

def _resposta(dados):
    class _R:
        status_code = 200
        text = ""
        def json(self):  # noqa: E301
            return dados
        def raise_for_status(self):  # noqa: E301
            return None
    return _R()


def test_o_base_e_o_MERGE_BASE_quando_o_ramo_alvo_andou(monkeypatch):
    """O caso que faz a prova diferencial mentir.

    `pulls/{n}` diz que o base e' `bbbb` (topo da main AGORA). O PR saiu de
    `mmmm`. Usar `bbbb` mediria o PR + o que entrou na main no meio.
    """
    def falso_get(url, **kw):
        if "/pulls/" in url:
            return _resposta({"head": {"sha": "hhhh"}, "base": {"sha": "bbbb"},
                              "title": "t", "html_url": "u"})
        return _resposta({"merge_base_commit": {"sha": "mmmm"}})

    monkeypatch.setattr(entrada.requests, "get", falso_get)
    base, head, info = entrada.commits_do_pr("d", "r", 1)
    assert base == "mmmm", "usou o topo do ramo alvo em vez do merge-base"
    assert head == "hhhh"
    assert info["base_deslocou"] is True, (
        "o deslocamento tem que ficar registrado: quem auditar precisa saber "
        "contra que commit a prova rodou")


def test_sem_deslocamento_o_merge_base_e_o_proprio_topo(monkeypatch):
    """O controle. Sem ele, `base_deslocou` poderia ser True sempre."""
    def falso_get(url, **kw):
        if "/pulls/" in url:
            return _resposta({"head": {"sha": "hhhh"}, "base": {"sha": "bbbb"},
                              "title": "t", "html_url": "u"})
        return _resposta({"merge_base_commit": {"sha": "bbbb"}})

    monkeypatch.setattr(entrada.requests, "get", falso_get)
    base, _, info = entrada.commits_do_pr("d", "r", 1)
    assert base == "bbbb" and info["base_deslocou"] is False


# --------------------------------------------------- os DOIS, e conferidos

def test_busca_os_dois_commits_e_nao_so_o_head(monkeypatch, tmp_path):
    """Sem o base nao ha prova diferencial. Era o buraco do controle_negativo."""
    buscados = []

    def falso(clone, *args, timeout=120):
        if args and args[0] == "fetch":
            buscados.append(args[-1])
        class _R:
            returncode, stdout, stderr = 0, "", ""
        return _R()

    monkeypatch.setattr(entrada, "_git", falso)
    entrada.busca_os_dois(tmp_path, "base_sha", "head_sha")
    assert buscados == ["base_sha", "head_sha"], buscados


def test_fetch_que_sai_zero_sem_trazer_o_commit_LEVANTA(monkeypatch, tmp_path):
    """A guarda vista falhando.

    Servidor com `uploadpack.allowReachableSHA1InWant` desligado recusa sha
    solto e ainda assim o fetch pode sair 0. Sem esta conferencia o worktree
    seguinte montaria outra coisa, e o artefato registraria o commit PEDIDO --
    exatamente o falso negativo mudo que o `_garante_worktree` existe para
    impedir do outro lado.
    """
    def falso(clone, *args, timeout=120):
        class _R:
            returncode = 0 if args[0] == "fetch" else 1
            stdout = stderr = ""
        return _R()

    monkeypatch.setattr(entrada, "_git", falso)
    with pytest.raises(entrada.EntradaFalhou) as e:
        entrada.busca_os_dois(tmp_path, "aaaa", "bbbb")
    assert "nao esta no clone" in str(e.value)


def test_fetch_que_falha_levanta_dizendo_qual_lado(monkeypatch, tmp_path):
    def falso(clone, *args, timeout=120):
        class _R:
            returncode = 1
            stdout = ""
            stderr = "fatal: nope"
        return _R()

    monkeypatch.setattr(entrada, "_git", falso)
    with pytest.raises(entrada.EntradaFalhou) as e:
        entrada.busca_os_dois(tmp_path, "aaaa", "bbbb")
    assert "base" in str(e.value), "nao diz qual dos dois commits falhou"


# ------------------------------------------------------------- o ambiente

def test_o_ambiente_leva_os_quatro_que_o_config_le_na_importacao(tmp_path):
    """Faltar um deixaria metade da configuracao no projeto anterior -- o item
    4 dos cinco chumbados de 15/08, em que o pre-voo passou VERDE enquanto a
    rodada revisava um repo e conversava com o app de outro."""
    info = {"repo_local": tmp_path / "clone", "worktrees": tmp_path / "wt",
            "head": "hhhh", "merge_base": "mmmm"}
    env = entrada.ambiente(info)
    assert env["CHALLENGE_REPO"] == str(tmp_path / "clone")
    assert env["PR_BRANCH"] == "hhhh"
    assert env["BASE_BRANCH"] == "mmmm", "o base tem que ser o merge-base"
    assert env["WORKTREES_DIR"] == str(tmp_path / "wt"), (
        "sem worktree proprio, `git worktree add` colide com o do desafio")


def test_o_token_nunca_vai_para_o_remote(monkeypatch, tmp_path):
    """`git remote -v` e o .git/config guardariam a credencial em texto."""
    monkeypatch.setenv("GH_TOKEN", "segredo_do_luis")
    chamadas = []

    def falso(clone, *args, timeout=120):
        chamadas.append(args)
        class _R:
            returncode, stdout, stderr = 0, "", ""
        return _R()

    monkeypatch.setattr(entrada, "_git", falso)
    monkeypatch.setattr(entrada, "RAIZ", tmp_path)
    entrada._garante_clone("d", "r")
    remotes = [a for a in chamadas if a[:2] == ("remote", "add")]
    assert remotes, "nao configurou o remoto"
    assert not any("segredo_do_luis" in str(a) for a in remotes), (
        f"o token vazou para o remote: {remotes}")


def test_404_explica_a_ambiguidade_de_repo_privado(monkeypatch):
    """404 do GitHub e' o mesmo para inexistente e para privado sem acesso.
    A mensagem crua manda procurar no lugar errado -- foi o que aconteceu com a
    bancada em 16/08."""
    class _R:
        status_code = 404
        text = "Not Found"
    monkeypatch.setattr(entrada.requests, "get", lambda *a, **k: _R())
    with pytest.raises(entrada.EntradaFalhou) as e:
        entrada._pega("https://api.github.com/x")
    msg = str(e.value).lower()
    assert "privado" in msg and "gh_token" in msg


# ------------------------------------------- 🚨 o cabecalho de autenticacao

def test_o_git_recebe_BASIC_e_nunca_BEARER(tmp_path, monkeypatch):
    """🚨 Medido em 18/08, no primeiro repositorio PRIVADO que passou por aqui.

    O primeiro run da Action contra a bancada morreu em 30 segundos com

        fatal: could not read Username for 'https://github.com'

    e a mensagem enganava: le como "faltou configurar credencial", quando o que
    houve foi o cabecalho ser RECUSADO e o git cair de volta para pedir senha.

        Bearer -> remote: invalid credentials
        Basic  -> fetch exit 0, commit no clone

    `Bearer` vale na `api.github.com` e NAO no transporte git sobre HTTPS, que
    quer `x-access-token:<token>` em base64 -- e' o que o `actions/checkout`
    monta. E o ramo nunca tinha rodado: os alvos ate' aqui (pallets/flask,
    psf/requests) sao PUBLICOS e nem chegam a usar token.
    """
    import base64

    chamadas = []
    monkeypatch.setattr(entrada, "RAIZ", tmp_path)
    monkeypatch.setenv("GH_TOKEN", "t0ken-de-teste")
    monkeypatch.setattr(entrada, "_git",
                        lambda clone, *a, **k: chamadas.append(a) or _ok())

    entrada._garante_clone("dono", "repo")

    cfgs = [a for a in chamadas if a and a[0] == "config"]
    assert cfgs, "nenhum cabecalho de autenticacao foi configurado"
    valor = cfgs[0][2]
    assert valor.startswith("Authorization: Basic "), (
        f"o git nao aceita este esquema para HTTPS: {valor.split()[1]}")
    esperado = base64.b64encode(b"x-access-token:t0ken-de-teste").decode()
    assert valor.endswith(esperado), "o par usuario:token nao e' o do GitHub"


def test_sem_token_nao_configura_cabecalho_nenhum(tmp_path, monkeypatch):
    """Repo publico nao precisa, e configurar a toa poe credencial vazia no
    `.git/config` -- que e' pior que nao ter."""
    chamadas = []
    monkeypatch.setattr(entrada, "RAIZ", tmp_path)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(entrada, "_git",
                        lambda clone, *a, **k: chamadas.append(a) or _ok())

    entrada._garante_clone("dono", "repo")
    assert not [a for a in chamadas if a and a[0] == "config"]


def test_o_token_nunca_vai_para_o_remote(tmp_path, monkeypatch):
    """`git remote -v` imprime a URL inteira, e ela vaza em qualquer log."""
    chamadas = []
    monkeypatch.setattr(entrada, "RAIZ", tmp_path)
    monkeypatch.setenv("GH_TOKEN", "t0ken-de-teste")
    monkeypatch.setattr(entrada, "_git",
                        lambda clone, *a, **k: chamadas.append(a) or _ok())

    entrada._garante_clone("dono", "repo")
    remotes = [a for a in chamadas if a and a[0] == "remote"]
    assert remotes and "t0ken-de-teste" not in " ".join(remotes[0])


def _ok():
    import subprocess
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
