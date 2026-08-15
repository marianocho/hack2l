"""Levantar o app do projeto. Nenhum teste aqui sobe container -- docker e' dublê.

O que se trava são as duas regras, porque as duas protegem o ambiente de quem
está rodando:

  1. não derruba o que não subiu
  2. `preparar` (seed) só roda se nós levantamos os containers

A segunda é a séria: seed costuma RESETAR o banco. Rodá-lo num app que já estava
servindo apagaria dado que não é nosso -- mesma classe do incidente de 11/08, em
que a suíte do commit base apagou 4 usuários e 5 documentos.
"""

from types import SimpleNamespace

import pytest

from veredito import config as cfg
from veredito import subida


def _res(returncode=0, stderr=""):
    return SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)


@pytest.fixture
def docker(monkeypatch):
    """Registra o que teria sido mandado ao docker, sem mandar."""
    chamadas = []
    monkeypatch.setattr(subida, "_compose",
                        lambda *a, timeout=600: chamadas.append(a) or _res())
    return chamadas


@pytest.fixture
def pedido(monkeypatch):
    monkeypatch.setattr(cfg, "APP_SUBIR", True)
    monkeypatch.setattr(cfg, "APP_ESPERA_S", 4)
    monkeypatch.setattr(cfg, "APP_PREPARAR", [["run", "--rm", "seed"]])


# ------------------------------- 🚨 regra 1: nao derruba o que nao subiu

def test_app_ja_no_ar_e_no_op_completo(pedido, docker, monkeypatch):
    """Nem sobe, nem prepara, nem derruba. O app de pé é do operador -- talvez
    com o navegador aberto nele.

    É isso que torna `subir: true` seguro de deixar ligado no projeto: quem roda
    não precisa saber o estado do ambiente antes."""
    monkeypatch.setattr(subida, "no_ar", lambda *a, **k: True)
    with subida.app_no_ar() as estado:
        assert estado["ja_estava"] is True
        assert estado["subimos"] is False
    assert docker == [], f"tocou no docker sem precisar: {docker}"


def test_nao_derruba_no_fim_quando_nao_subiu(pedido, docker, monkeypatch):
    monkeypatch.setattr(subida, "no_ar", lambda *a, **k: True)
    with subida.app_no_ar():
        pass
    assert not any("down" in c for c in docker)


# ---------------------------- 🚨 regra 2: seed so' se NOS levantamos

def test_preparar_nao_roda_em_app_que_ja_estava_de_pe(pedido, docker, monkeypatch):
    """A regra mais séria do módulo. Seed reseta banco; rodá-lo num app que já
    servia apagaria dado de terceiro."""
    monkeypatch.setattr(subida, "no_ar", lambda *a, **k: True)
    with subida.app_no_ar() as estado:
        assert estado["preparacao"] == []
    assert not any("seed" in " ".join(c) for c in docker)


def test_preparar_roda_quando_nos_subimos(pedido, docker, monkeypatch):
    _sobe_com_sucesso(monkeypatch)
    with subida.app_no_ar() as estado:
        assert estado["subimos"] is True
        assert estado["preparacao"] == ["run --rm seed"]
    assert any("seed" in " ".join(c) for c in docker)


def _sobe_com_sucesso(monkeypatch):
    """Primeira sonda diz 'fora', as seguintes dizem 'no ar'."""
    respostas = iter([False] + [True] * 20)
    monkeypatch.setattr(subida, "no_ar",
                        lambda *a, **k: next(respostas, True))


# ------------------------------------------- subir, esperar, e desistir

def test_sobe_e_derruba_no_fim(pedido, docker, monkeypatch):
    _sobe_com_sucesso(monkeypatch)
    with subida.app_no_ar():
        pass
    assert ("up", "-d") in [tuple(c) for c in docker]
    assert ("down",) in [tuple(c) for c in docker]


def test_derruba_mesmo_se_a_rodada_explodir(pedido, docker, monkeypatch):
    """Rodada é longa e morrer no meio é o caso provável. Deixar containers de
    pé atrás de nós seria estrago nosso."""
    _sobe_com_sucesso(monkeypatch)
    with pytest.raises(ZeroDivisionError):
        with subida.app_no_ar():
            1 / 0
    assert ("down",) in [tuple(c) for c in docker]


def test_app_que_nao_responde_derruba_e_levanta(pedido, docker, monkeypatch):
    """Não vale deixar meio ambiente de pé. E levanta em vez de seguir: rodada
    sem app sai toda em MÉDIA e parece o produto não funcionando."""
    monkeypatch.setattr(subida, "no_ar", lambda *a, **k: False)
    with pytest.raises(subida.SubidaFalhou, match="nao respondeu"):
        with subida.app_no_ar():
            pytest.fail("o corpo nao pode rodar sem app")
    assert ("down",) in [tuple(c) for c in docker]


def test_compose_up_que_falha_levanta(pedido, monkeypatch):
    monkeypatch.setattr(subida, "no_ar", lambda *a, **k: False)
    monkeypatch.setattr(subida, "_compose",
                        lambda *a, timeout=600: _res(1, "sem imagem"))
    with pytest.raises(subida.SubidaFalhou, match="compose up"):
        with subida.app_no_ar():
            pass


def test_preparacao_que_falha_derruba_e_levanta(pedido, monkeypatch):
    """App de pé com seed pela metade é pior que app fora: os dados estão num
    estado que ninguém previu, e a rodada mediria isso."""
    _sobe_com_sucesso(monkeypatch)
    chamadas = []

    def _falha_no_seed(*a, timeout=600):
        chamadas.append(a)
        return _res(1, "seed explodiu") if "seed" in a else _res()

    monkeypatch.setattr(subida, "_compose", _falha_no_seed)
    with pytest.raises(subida.SubidaFalhou, match="preparacao"):
        with subida.app_no_ar():
            pass
    assert ("down",) in [tuple(c) for c in chamadas]


# --------------------------------------------------- a escotilha desligada

def test_desligado_nao_toca_no_docker(docker, monkeypatch):
    """Padrão quando o yml não diz nada: o app é responsabilidade de fora, como
    sempre foi."""
    monkeypatch.setattr(cfg, "APP_SUBIR", False)
    monkeypatch.setattr(subida, "no_ar", lambda *a, **k: False)
    with subida.app_no_ar() as estado:
        assert estado["pedido"] is False
    assert docker == []


# ------------------------------------- 🚨 `preparar` nunca passa por shell

def test_preparar_e_lista_de_argumentos_nunca_string(pedido, docker, monkeypatch):
    """`preparar` vem de arquivo do projeto REVISADO. Passar isso por shell
    seria executar texto de terceiro com as nossas permissões."""
    _sobe_com_sucesso(monkeypatch)
    monkeypatch.setattr(cfg, "APP_PREPARAR", ["rm -rf / # string, nao lista"])
    with subida.app_no_ar() as estado:
        assert estado["preparacao"] == [], "string foi aceita como comando"
    assert not any("rm" in " ".join(c) for c in docker)


def test_argumentos_do_preparar_viram_texto(pedido, docker, monkeypatch):
    """YAML devolve int para `- 5`. Passar int ao subprocess levanta TypeError
    no meio da rodada, longe da causa."""
    _sobe_com_sucesso(monkeypatch)
    monkeypatch.setattr(cfg, "APP_PREPARAR", [["run", "--rm", "seed", 5]])
    with subida.app_no_ar():
        pass
    assert any("5" in " ".join(c) for c in docker)
