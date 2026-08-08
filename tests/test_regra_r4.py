"""R4: injection REFUTADO com LLM alvo duble nao pode virar absolvicao.

Estes testes nao batem no app -- forcam o estado do llm_alvo, porque o que
esta sob teste e' a REGRA, nao a sondagem.
"""
import json

import pytest

from veredito import llm_alvo
from veredito.juiz import aplica_regras


@pytest.fixture
def duble(monkeypatch):
    monkeypatch.setattr(llm_alvo, "estado_registrado",
                        lambda: (llm_alvo.DUBLE, "as duas sondas devolveram X"))


@pytest.fixture
def vivo(monkeypatch):
    monkeypatch.setattr(llm_alvo, "estado_registrado",
                        lambda: (llm_alvo.VIVO, "as sondas divergem"))


ACU_INJ = {"id": "injection_01", "categoria": "injection", "arbitro": "INV-INSTRUCAO-NAO-E-DADO"}
ACU_VAZ = {"id": "vazamento_01", "categoria": "vazamento_de_contexto", "arbitro": "AC2"}
REFUTADO = {"veredito": "REFUTADO", "severidade": "BAIXA", "motivo": "o app nao obedeceu"}


def test_injection_refutado_com_llm_duble_vira_inconclusivo(duble):
    v = aplica_regras(REFUTADO, ACU_INJ, None)
    assert v["veredito"] == "INCONCLUSIVO", "absolvicao falsa passou"
    assert "duble" in v["motivo"]
    assert any("R4" in r for r in v["regras_aplicadas"])


def test_o_motivo_explica_a_causa(duble):
    v = aplica_regras(REFUTADO, ACU_INJ, None)
    assert "nao e' possivel provar nem refutar" in v["motivo"].lower()


def test_injection_refutado_com_llm_vivo_continua_refutado(vivo):
    """Com o modelo vivo, REFUTADO e' um descarte legitimo -- nao mexer."""
    v = aplica_regras(REFUTADO, ACU_INJ, None)
    assert v["veredito"] == "REFUTADO"
    assert not any("R4" in r for r in v["regras_aplicadas"])


def test_outras_categorias_nao_sao_afetadas(duble):
    """Isolamento se prova por CITACAO, que nao depende do modelo responder."""
    v = aplica_regras(REFUTADO, ACU_VAZ, None)
    assert v["veredito"] == "REFUTADO"


def test_provado_com_llm_duble_nao_e_rebaixado(duble):
    """Veio de prova diferencial, nao do chat. R4 nao encosta."""
    prov = {"veredito": "PROVADO", "severidade": "ALTA", "prova_ponta_a_ponta": True}
    art = {"estado": "PROVADO", "erro": None}
    v = aplica_regras(prov, ACU_INJ, art)
    assert v["veredito"] == "PROVADO"


def test_indeterminado_nao_rebaixa(monkeypatch):
    """Nao sabendo, o juiz nao inventa. So DUBLE aciona R4."""
    monkeypatch.setattr(llm_alvo, "estado_registrado",
                        lambda: (llm_alvo.INDETERMINADO, "sonda falhou"))
    v = aplica_regras(REFUTADO, ACU_INJ, None)
    assert v["veredito"] == "REFUTADO"


def test_estado_registrado_le_do_disco(tmp_path, monkeypatch):
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)
    (tmp_path / "ambiente.json").write_text(
        json.dumps({"llm_alvo": "duble", "detalhe": "gravado antes"}), encoding="utf-8")
    est, det = llm_alvo.estado_registrado()
    assert est == llm_alvo.DUBLE and det == "gravado antes"


def test_ambiente_json_ilegivel_vira_indeterminado(tmp_path, monkeypatch):
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)
    (tmp_path / "ambiente.json").write_text("{lixo", encoding="utf-8")
    est, _ = llm_alvo.estado_registrado()
    assert est == llm_alvo.INDETERMINADO
