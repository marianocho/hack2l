"""A prova sai do disco e chega ao parecer -- ou nao chega, e ele diz isso.

A prova roda no orquestrador e grava `fusao.json`; o juiz e o comentario apenas
LEEM. Estes testes cobrem a junta entre os dois, que e' onde este produto
historicamente mente em silencio: um arquivo ausente que vira "provado", uma
contagem que nao reflete o que a prova decidiu.

🚨 O teste que mais importa e' `test_ausencia_de_prova_NAO_vira_provado`. Sem
ele, uma rodada sem Docker publicaria "FUSAO PROVADA" sem nada ter rodado -- a
absolvicao falsa de sempre, do outro lado do funil.
"""
import json

import pytest

from veredito import comentario, fusao, juiz
from veredito import config as cfg
from veredito import prova_de_fusao as pf

REGRAS = "docs/REGRAS.md:Acesso e isolamento"


@pytest.fixture(autouse=True)
def rodada(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "RODADA", tmp_path)
    return tmp_path


def _a(id_, local, categoria="correcao"):
    return {"id": id_, "local": local, "local_normalizado": local,
            "categoria": categoria,
            "arbitro": {"regra": "a regra", "onde": REGRAS}}


def _v(id_, sev="ALTA"):
    return {"id": id_, "veredito": "PROVADO", "severidade": sev,
            "conserto": "restaurar a checagem"}


def _cena():
    ac = {a["id"]: a for a in (_a("c1", "app/main.py:103"),
                               _a("p1", "app/main.py:104", "padroes"),
                               _a("f1", "app/main.py:103", "performance"))}
    return [_v("c1"), _v("p1"), _v("f1")], ac


def _org(cond):
    return {"condenados": cond, "descartados": [], "inconclusivos": []}


# ------------------------------------------- o contrato de disco

def test_grava_e_le_de_volta(rodada):
    pf.grava([{"ids": ["c1", "p1"], "veredito": pf.MESMO, "detalhe": {"trecho": 1}}])
    lido = pf.do_disco()
    assert lido[frozenset({"c1", "p1"})] == (pf.MESMO, {"trecho": 1})


def test_arquivo_ausente_e_dicionario_vazio(rodada):
    assert pf.do_disco() == {}


def test_arquivo_corrompido_nao_derruba(rodada):
    (rodada / pf.ARQUIVO).write_text("{ isto nao e json", encoding="utf-8")
    assert pf.do_disco() == {}


# ------------------------------------------- 🚨 ausencia nunca vira prova

def test_ausencia_de_prova_NAO_vira_provado(rodada):
    """Sem `fusao.json`, o agrupamento continua saindo -- rotulado como indicio.

    Se isto quebrar, uma rodada sem Docker publica "FUSAO PROVADA" sem nada ter
    rodado. E' a absolvicao falsa de sempre, na outra ponta do funil.
    """
    cond, ac = _cena()
    grupos = pf.aplica(fusao.agrupa(cond, ac), pf.do_disco())
    assert len(grupos) == 1
    _, ver, det = grupos[0]
    assert ver == pf.INCONCLUSIVO
    bloco = juiz.bloco_agrupado(grupos[0][0], ac, {}, {}, (ver, det))
    assert "FUSAO PROVADA" not in bloco
    assert "indicio e nao prova" in bloco


def test_grupo_sem_resultado_no_arquivo_tambem_e_indicio(rodada):
    """O arquivo existe, mas nao cobre ESTE grupo. Silencio nao e' prova."""
    pf.grava([{"ids": ["outro_a", "outro_b"], "veredito": pf.MESMO, "detalhe": {}}])
    cond, ac = _cena()
    _, ver, _ = pf.aplica(fusao.agrupa(cond, ac), pf.do_disco())[0]
    assert ver == pf.INCONCLUSIVO


# ------------------------------------------- provado

def test_MESMO_mantem_junto_e_diz_que_provou(rodada):
    cond, ac = _cena()
    pf.grava([{"ids": ["c1", "p1", "f1"], "veredito": pf.MESMO,
               "detalhe": {"trecho": 1, "explica": ["c1", "p1", "f1"]}}])
    grupos = pf.aplica(fusao.agrupa(cond, ac), pf.do_disco())
    assert len(grupos) == 1 and len(grupos[0][0]) == 3
    bloco = juiz.bloco_agrupado(grupos[0][0], ac, {}, {}, (grupos[0][1], grupos[0][2]))
    assert "FUSAO PROVADA" in bloco


# ------------------------------------------- 🚨 a prova DESFAZ

def test_DIFERENTES_separa_o_grupo_no_parecer(rodada):
    """A direcao que so' a prova consegue: desfazer o que a heuristica juntou.

    A heuristica agrupou os tres pelo endereco; a medicao mostrou que o trecho
    que conserta c1 e p1 NAO conserta f1. O parecer tem que voltar a ter dois
    achados -- senao a prova mediu e o texto ignorou.
    """
    cond, ac = _cena()
    pf.grava([{"ids": ["c1", "p1", "f1"], "veredito": pf.DIFERENTES,
               "detalhe": {"trecho": 1, "explica": ["c1", "p1"],
                           "nao_explica": ["f1"]}}])
    grupos = pf.aplica(fusao.agrupa(cond, ac), pf.do_disco())
    assert len(grupos) == 2, "a prova desfez o agrupamento e o parecer nao viu"
    assert [v["id"] for v in grupos[0][0]] == ["c1", "p1"]
    assert [v["id"] for v in grupos[1][0]] == ["f1"]


def test_a_CONTAGEM_do_comentario_segue_a_prova(rodada):
    """O numero que o autor le e' o que a prova decidiu, nao o da heuristica.

    E' a linha de resumo do comentario de PR -- a unica que muita gente le.
    """
    cond, ac = _cena()
    pf.grava([{"ids": ["c1", "p1", "f1"], "veredito": pf.DIFERENTES,
               "detalhe": {"explica": ["c1", "p1"], "nao_explica": ["f1"]}}])
    corpo = comentario.monta(_org(cond), ac, {})
    assert "**2 achado(s) com evidencia.**" in corpo, (
        "a heuristica dizia 1; a prova disse 2, e o resumo ficou no numero velho")


def test_sem_prova_a_contagem_e_a_da_heuristica(rodada):
    cond, ac = _cena()
    corpo = comentario.monta(_org(cond), ac, {})
    assert "**1 achado(s) com evidencia.**" in corpo


# ------------------------------------------- o texto do desfazer

def test_o_bloco_do_grupo_desfeito_diz_QUEM_nao_e_explicado(rodada):
    cond, ac = _cena()
    det = {"explica": ["c1", "p1"], "nao_explica": ["f1"]}
    bloco = juiz.bloco_agrupado([_v("c1"), _v("p1")], ac, {}, {}, (pf.DIFERENTES, det))
    assert "FUSAO DESFEITA POR PROVA" in bloco
    assert "f1" in bloco


# ------------------------------------------- a guarda do orquestrador

def test_projeto_sem_codigo_nao_TENTA_provar(rodada, monkeypatch, capsys):
    """Sem `codigo` no veredito.yml nao ha teste para reexecutar.

    Tentar levantaria worktree e container para nada, e -- pior -- um tropeco
    ali viraria ruido no console de toda revisao de PR de terceiro, que e'
    exatamente o alarme que dispara sempre de 17/08.
    """
    from veredito import orquestrador
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", False)
    orquestrador._prova_as_fusoes([_v("c1")], {"c1": _a("c1", "app/main.py:10")})
    saida = capsys.readouterr().out
    assert "nao declara `codigo`" in saida
    assert not (rodada / pf.ARQUIVO).exists(), "gravou prova sem ter medido nada"


def test_tropeco_na_medicao_nao_derruba_a_rodada(rodada, monkeypatch, capsys):
    """🚨 A medicao e' um extra. Se ela explodir, a rodada inteira -- que ja
    custou o laco do advogado -- nao pode ir junto."""
    from veredito import orquestrador
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", True)
    monkeypatch.setattr(orquestrador.juiz, "organiza",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    orquestrador._prova_as_fusoes([_v("c1")], {"c1": _a("c1", "app/main.py:10")})
    assert "nao mediu" in capsys.readouterr().out
    assert not (rodada / pf.ARQUIVO).exists()
