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
    from datetime import datetime
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)
    (tmp_path / "ambiente.json").write_text(
        json.dumps({"llm_alvo": "duble", "detalhe": "gravado antes",
                    "medido_em": datetime.now().isoformat()}), encoding="utf-8")
    est, det = llm_alvo.estado_registrado()
    assert est == llm_alvo.DUBLE and det == "gravado antes"


def test_registro_sem_timestamp_nao_e_confiado(tmp_path, monkeypatch):
    """Sem medido_em nao da' para saber a idade -- sonda em vez de confiar."""
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)
    (tmp_path / "ambiente.json").write_text(
        json.dumps({"llm_alvo": "duble", "detalhe": "sem data"}), encoding="utf-8")
    monkeypatch.setattr(llm_alvo, "estado", lambda forcar=True: (llm_alvo.VIVO, "sondado"))
    est, det = llm_alvo.estado_registrado()
    assert est == llm_alvo.VIVO and det == "sondado"


def test_ambiente_json_ilegivel_cai_na_sonda(tmp_path, monkeypatch):
    """Arquivo lixo nao vira INDETERMINADO: sondar e' melhor que desistir."""
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)
    (tmp_path / "ambiente.json").write_text("{lixo", encoding="utf-8")
    monkeypatch.setattr(llm_alvo, "estado", lambda forcar=True: (llm_alvo.DUBLE, "sondado"))
    est, _ = llm_alvo.estado_registrado()
    assert est == llm_alvo.DUBLE


def test_sonda_quebrada_vira_indeterminado(tmp_path, monkeypatch):
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)

    def explode(forcar=True):
        raise RuntimeError("app fora do ar")

    monkeypatch.setattr(llm_alvo, "estado", explode)
    est, det = llm_alvo.estado_registrado()
    assert est == llm_alvo.INDETERMINADO and "app fora do ar" in det


def test_registro_velho_e_ignorado(tmp_path, monkeypatch):
    """Registro de outra rodada -- ou de outra maquina -- nao vale.

    Em 08/08 a maquina do Mariano gravou "duble" e commitou; a do palco, com
    o modelo VIVO, teria lido o duble alheio e disparado R4 em tudo.
    """
    from datetime import datetime, timedelta
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)
    velho = (datetime.now() - timedelta(seconds=llm_alvo.TTL_REGISTRO_S + 60)).isoformat()
    (tmp_path / "ambiente.json").write_text(
        json.dumps({"llm_alvo": "duble", "detalhe": "de outra maquina",
                    "medido_em": velho}), encoding="utf-8")
    monkeypatch.setattr(llm_alvo, "estado", lambda forcar=True: (llm_alvo.VIVO, "sondado agora"))
    est, det = llm_alvo.estado_registrado()
    assert est == llm_alvo.VIVO, "confiou num registro vencido"
    assert det == "sondado agora"


def test_registro_recente_e_usado(tmp_path, monkeypatch):
    from datetime import datetime
    from veredito import config as cfg
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)
    (tmp_path / "ambiente.json").write_text(
        json.dumps({"llm_alvo": "duble", "detalhe": "desta rodada",
                    "medido_em": datetime.now().isoformat()}), encoding="utf-8")
    est, det = llm_alvo.estado_registrado()
    assert est == llm_alvo.DUBLE and det == "desta rodada"
