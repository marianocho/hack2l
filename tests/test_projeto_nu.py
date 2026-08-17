"""O PROJETO NU: o Veredito apontado para um repositorio que nao se descreve.

🚨 A alavanca que a suite nao tinha. Os 506 testes rodam todos contra o desafio,
e ali "leu do veredito.yml" e "caiu no padrao chumbado" produzem o MESMO valor
-- entao a suite e' cega para a classe de bug mais reincidente do projeto. Foi
assim que 14 fallbacks apontando para o desafio atravessaram 506 asseroes.

O `CLAUDE.md` tirava disso a licao "foi preciso apontar para um SEGUNDO projeto"
(a bancada). A versao afiada e' o contrario:

    A bancada acha esses bugs por ser um segundo EXEMPLO.
    Quem acha esta classe e' a AUSENCIA de exemplo -- e ela e' de graca.

A bancada custa ~US$2 por varredura e meio dia para crescer. O projeto nu custa
milissegundos: sem repo, sem container, sem chamada de API. E pega a classe
inteira de forma deterministica, porque no estado nu **todo valor de projeto
tem que estar vazio** -- nao ha valor certo para ele cair.

⚠️ Este arquivo mede o CONTRATO do estado nu, nao o carregamento do config (que
resolve na importacao e nao da' para reimportar sem estragar os outros testes).
Cada bandeira e' recalculada aqui a partir de um yml VAZIO, com a mesma
expressao do config -- e `test_config_sem_desafio` e' quem garante que a
expressao de la' nao mudou de forma por baixo.
"""
import pathlib

import pytest

from veredito import config as cfg
from veredito import contencao_app
from veredito import ferramentas as f
from veredito import projeto

RAIZ = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def nu(monkeypatch, tmp_path):
    """Tudo que o projeto declararia, vazio. O estado de um PR de terceiro."""
    for nome, valor in [
        ("APP_API_URL", ""), ("TEM_APP", False),
        ("AUTH_ROTA", ""), ("AUTH_CAMPO_SENHA", ""), ("AUTH_CAMPO_TOKEN", ""),
        ("TEM_AUTH", False),
        ("CODIGO_MONTAGENS", []), ("CODIGO_TESTES", ""),
        ("CODIGO_TESTES_NO_REPO", ""), ("CODIGO_TRABALHO", ""),
        ("TEM_PROVA_DIFERENCIAL", False),
        ("BANCO_APP_ORIGEM", ""), ("BANCO_USUARIO", ""), ("BANCO_SENHA", ""),
        ("TEM_BANCO", False), ("ALCANCA_BANCO", False),
        ("USUARIOS", {}), ("CONTROLE_NEGATIVO", ""),
        ("ARTEFATOS", tmp_path), ("RODADA", tmp_path),
    ]:
        monkeypatch.setattr(cfg, nome, valor)


# --------------------------------- o yml vazio produz o estado nu

def test_yml_ausente_nao_inventa_nada():
    """Ausente nao e' vazio: e' limite honesto, e nao pode virar valor de outro."""
    assert projeto.carrega(None) == {}
    assert projeto.usuarios({}) == {}
    assert projeto.controle_negativo({}) is None


# Tudo que descreve o PROJETO REVISADO. No estado nu, todos vazios: nao existe
# padrao correto para o projeto de outra pessoa.
#
# ⚠️ `BANCO_DESCARTAVEL`, `BANCO_APP` e `REDE_ISOLADA` NAO entram: sao NOSSOS,
# e o padrao deles e' seguranca (banco descartavel vazio faria a suite do
# cliente rodar no banco real, que e' o incidente de 11/08).
DEVEM_NASCER_VAZIOS = [
    "APP_API_URL", "APP_WEB_URL",
    "AUTH_ROTA", "AUTH_CAMPO_SENHA", "AUTH_CAMPO_TOKEN",
    "CODIGO_MONTAGENS", "CODIGO_TESTES", "CODIGO_TESTES_NO_REPO",
    "CODIGO_TRABALHO",
    "BANCO_APP_ORIGEM", "BANCO_USUARIO", "BANCO_SENHA",
    "USUARIOS", "CONTROLE_NEGATIVO",
]
BANDEIRAS_DESLIGADAS = ["TEM_APP", "TEM_AUTH", "TEM_BANCO",
                        "TEM_PROVA_DIFERENCIAL", "ALCANCA_BANCO"]


@pytest.fixture(scope="module")
def config_nu():
    """O config CARREGADO DE VERDADE, sem veredito.yml nenhum.

    🚨 Em subprocesso porque o config resolve o projeto NA IMPORTACAO -- e' a
    mesma razao pela qual o `revisa_pr.py` sobe o orquestrador em processo
    separado. Reimportar aqui deixaria metade da configuracao apontando para o
    desafio e contaminaria os outros 500 testes.

    E' esta fixture que da' a alavanca: exercita o caminho real do carregamento
    com o yml ausente, em vez de afirmar coisas sobre um dicionario vazio
    montado aqui dentro -- que passaria com todos os chumbados de volta.
    """
    import json
    import os
    import subprocess
    import sys

    nomes = DEVEM_NASCER_VAZIOS + BANDEIRAS_DESLIGADAS
    prog = ("import json;from veredito import config as c;"
            f"print(json.dumps({{n: getattr(c, n) for n in {nomes!r}}}, default=str))")
    r = subprocess.run(
        [sys.executable, "-c", prog], cwd=str(RAIZ), capture_output=True,
        text=True, encoding="utf-8",
        # Aponta para um yml que nao existe: `projeto.caminho` devolve None, e
        # e' exatamente o estado do `revisa_pr.py` num repo de terceiro.
        env=dict(os.environ, VEREDITO_YML=str(RAIZ / "nao" / "existe.yml")),
    )
    assert r.returncode == 0, f"o config nem carrega sem projeto:\n{r.stderr[-2000:]}"
    return json.loads(r.stdout)


@pytest.mark.parametrize("nome", DEVEM_NASCER_VAZIOS)
def test_valor_de_projeto_nasce_VAZIO_sem_yml(config_nu, nome):
    """A pergunta que a suite nunca fazia, e por isso 14 fallbacks sobreviveram.

    Contra o desafio, "leu do yml" e "caiu no padrao" dao o mesmo valor. Aqui
    nao ha yml, entao qualquer coisa preenchida so' pode ter vindo do nosso
    codigo -- e valor do projeto de outra pessoa no nosso codigo e' o chumbado.
    """
    assert not config_nu[nome], (
        f"{nome} nasceu com {config_nu[nome]!r} sem projeto nenhum declarado")


@pytest.mark.parametrize("nome", BANDEIRAS_DESLIGADAS)
def test_bandeira_desligada_sem_yml(config_nu, nome):
    """Sem projeto declarado, nenhuma capacidade dependente dele se diz presente."""
    assert config_nu[nome] is False, f"{nome} se declarou capaz sem projeto"


# --------------------------------- e toda ferramenta dependente RECUSA

def test_http_request_recusa(nu, monkeypatch):
    monkeypatch.setattr(f.requests, "request",
                        lambda *a, **k: pytest.fail("tocou a rede"))
    r = f._http_request("GET", "/health")
    assert r["status"] is None and r["indisponivel"] is True


def test_login_recusa_em_vez_de_postar_credencial_no_escuro(nu, monkeypatch):
    """🚨 A pior das cinco, e a que eu quase deixei passar.

    Sem `auth` declarado, o padrao antigo mandaria email e senha das contas
    para `<api>/auth/login` -- um endereco que ESTE projeto nunca disse ser o de
    login. Nao e' um 404: e' credencial enviada para onde ninguem autorizou.
    """
    monkeypatch.setattr(cfg, "USUARIOS", {"ana": ("ana@x.dev", "s3nha")})
    monkeypatch.setattr(f.requests, "post",
                        lambda *a, **k: pytest.fail("postou credencial sem rota declarada"))
    f._TOKENS.pop("ana", None)
    with pytest.raises(RuntimeError, match="nao declara `auth`"):
        f._token("ana")


def test_prova_diferencial_recusa(nu):
    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")
    assert art["erro"] is None and art["indisponivel"]


def test_run_tests_recusa(nu, monkeypatch):
    monkeypatch.setattr(f.subprocess, "run",
                        lambda *a, **k: pytest.fail("chamou o docker"))
    assert "nao declara" in f.run_tests()


def test_retrato_do_banco_recusa(nu, monkeypatch):
    monkeypatch.setattr(contencao_app, "_compose",
                        lambda *a, **k: pytest.fail("chamou o compose"))
    r = contencao_app._psql("qualquer", "select 1")
    assert r.returncode == 1 and "nao declara" in r.stderr


# --------------------------------- e a rodada ainda ROLA, dizendo o que perdeu

def test_pre_voo_nao_aborta_e_diz_o_que_falta(nu, monkeypatch, tmp_path):
    """Leitura e grep bastam para uma rodada honesta -- 26 das 38 refutacoes de
    10/08 sairam so' com eles. Abortar aqui mataria o caso de uso do
    `revisa_pr.py`, que e' o produto tendo por onde entrar."""
    raiz = tmp_path / "wt"
    raiz.mkdir()
    (raiz / "modulo.py").write_text("x = 1\n" * 40, encoding="utf-8")
    monkeypatch.setattr(f, "_read_file", lambda c: "1 | conteudo")
    monkeypatch.setattr(f, "_grep", lambda *a, **k: "arquivo.py:1: casou")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: raiz)

    r = f.autoteste(sondar_app=True)
    assert r["ok"] is True, "abortou um PR que so' precisa de leitura"
    ditos = " ".join(v["detalhe"] for v in r["ferramentas"].values())
    assert "veredito.yml" in ditos, "perdeu ferramenta e nao disse ao operador"
