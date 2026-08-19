"""Projeto que nao declara app NAO TEM app -- nunca o do vizinho.

🚨 O caso real, 17/08, na primeira revisao de um PR de terceiro pela porta da
frente. Revisando `pallets/flask`, sem `veredito.yml`, o pre-voo imprimiu:

    ok  http_request  GET /health -> 200
    ok  login         /auth/login como demo: token de 119 chars

VERDE. Ele tinha feito login no app do DESAFIO -- que estava no ar naquela
porta -- com a conta `demo` do desafio, enquanto revisava o Flask.

A causa nao era o `.env` (esse ja tem guarda desde 15/08). Era o PADRAO DO
CODIGO: `APP_API_URL` caia em `127.0.0.1:8000` e `USUARIOS` caia nas quatro
contas do desafio quando o projeto nao declarava nada. O conserto de 14/08
tirou esses valores de serem a UNICA fonte e os deixou como fallback -- e
fallback que aponta para outro projeto e' pior que fallback nenhum, porque as
sondas ficam verdes e a rodada segue.

⚠️ A rodada so' nao chegou ao advogado por SORTE: `app_serve_o_head` falhou por
outro motivo (merge-base em clone raso) e abortou tudo. Sem esse acidente, o
advogado teria rodado com `http_request` apontado para o app do desafio,
podendo criar linha la' e "provar" coisas sobre o app errado.

Contencao, nao predicao: nao adivinhar onde o app esta.
"""
import pytest

from veredito import config as cfg
from veredito import ferramentas as f


@pytest.fixture
def sem_app(monkeypatch):
    """O estado de um PR de terceiro: nada declarado.

    🚨 O `codigo` entrou em 19/08, com o canario das montagens. O fixture dizia
    "nada declarado" e deixava o LAYOUT DO DESAFIO em pe -- entao o "PR de
    terceiro" que ele modelava tinha `codigo.montagens` apontando para
    `app/api/app`, arvore que so' existe no desafio. Ninguem tinha notado porque
    nenhuma sonda do pre-voo dependia disso ate' agora.

    E' o mesmo vao que o `test_projeto_nu` existe para fechar: no estado nu TODO
    valor de projeto tem que estar vazio, e meio-nu produz um cenario que nao e'
    nem o desafio nem um terceiro.
    """
    monkeypatch.setattr(cfg, "TEM_APP", False)
    monkeypatch.setattr(cfg, "APP_API_URL", "")
    monkeypatch.setattr(cfg, "USUARIOS", {})
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", False)
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS", [])


@pytest.fixture
def com_app(monkeypatch):
    monkeypatch.setattr(cfg, "TEM_APP", True)
    monkeypatch.setattr(cfg, "APP_API_URL", "http://127.0.0.1:8000")


# ------------------------------------------- a guarda, vista falhando

def test_http_request_sem_app_NAO_TOCA_A_REDE(sem_app, monkeypatch):
    """A trava central. Nao basta falhar -- nao pode nem tentar.

    Se ele tentasse e errasse, um app de outro projeto no endereco padrao
    responderia, que e' exatamente o que aconteceu em 17/08.
    """
    def nao_pode(*a, **k):
        raise AssertionError("http_request tocou a rede sem app declarado")

    monkeypatch.setattr(f.requests, "request", nao_pode)
    saida = f._http_request("GET", "/health")
    assert saida["status"] is None
    assert "nao declara" in saida["erro"]
    assert "veredito.yml" in saida["erro"], "nao diz ao operador como consertar"


def test_com_app_declarado_ele_chama_normalmente(com_app, monkeypatch):
    """O controle. Sem ele a trava acima passaria com o http_request quebrado."""
    chamou = {}

    class _R:
        status_code = 200
        text = "{}"
        def json(self):  # noqa: E301
            return {}

    def falso(metodo, url, **k):
        chamou["url"] = url
        return _R()

    monkeypatch.setattr(f.requests, "request", falso)
    saida = f._http_request("GET", "/health")
    assert saida["erro"] is None and saida["status"] == 200
    assert chamou["url"].startswith("http://127.0.0.1:8000")


# ------------------------------------------- o pre-voo segue, e DIZ

def test_pre_voo_sem_app_NAO_exige_app_serve_o_head(sem_app, monkeypatch):
    """Sem isto a rodada aborta e o `revisa_pr.py` fica inutil.

    `app_serve_o_head` roda `git merge-base`, que nao existe em clone raso --
    e PR de terceiro nunca vai ter app declarado. Exigi-la ali bloqueava o caso
    de uso inteiro.
    """
    monkeypatch.setattr(f, "_read_file", lambda c: "1 | conteudo do arquivo")
    monkeypatch.setattr(f, "_grep", lambda *a, **k: "arquivo.py:1: casou")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: _fake_raiz())
    r = f.autoteste(sondar_app=True)
    assert "app_serve_o_head" not in r["ferramentas"], (
        "sondou o app de alguem sem o projeto ter declarado app")
    assert r["ok"] is True, "abortou a rodada de um PR que so' precisa de leitura"


def test_pre_voo_sem_app_DIZ_que_nao_ha_app(sem_app, monkeypatch):
    """Sonda que some sem explicacao le como 'nao se aplica'.

    Aqui ela some porque o projeto nao se descreveu, e isso muda o que a rodada
    consegue provar -- entao tem que estar escrito. Mesma doutrina do terceiro
    estado: ausencia de observacao e' dita, nunca omitida.
    """
    monkeypatch.setattr(f, "_read_file", lambda c: "1 | conteudo do arquivo")
    monkeypatch.setattr(f, "_grep", lambda *a, **k: "arquivo.py:1: casou")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: _fake_raiz())
    r = f.autoteste(sondar_app=True)
    assert "app" in r["ferramentas"], "a ausencia do app nao aparece no pre-voo"
    d = r["ferramentas"]["app"]["detalhe"]
    assert "veredito.yml" in d and "MEDIA" in d, (
        "o pre-voo nao diz o que a rodada perde nem como consertar")


# ------------------------------------------- sem fallback de contas

def test_usuarios_nao_tem_fallback_para_as_contas_do_desafio():
    """As quatro contas do desafio eram o padrao quando o projeto nao declarava.

    Revisando o Flask, o produto tentou -- e conseguiu -- logar como
    `demo@hack2l.dev` no app do desafio. O comentario no config ja dizia que
    vazio e' legitimo; o `or {...}` garantia que nunca ficasse vazio.
    """
    import inspect
    fonte = inspect.getsource(cfg)
    i = fonte.index("USUARIOS =")
    trecho = fonte[i:i + 400]
    assert "hack2l.dev" not in trecho, (
        "as contas do desafio voltaram como fallback de USUARIOS")


def _fake_raiz():
    """Uma raiz com um .py de tamanho suficiente para a sonda de leitura."""
    import pathlib
    import tempfile
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "modulo.py").write_text("x = 1\n" * 40, encoding="utf-8")
    return d
