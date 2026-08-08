"""Deduplicacao antes do advogado. Nao bate na API.

O que esta sob teste e' a regra de fusao, nao a chamada de modelo.
"""
from veredito.promotores import COTAS, _chave_dedup, deduplica, seleciona


def acu(id_, cat, local, arbitro, conf="media", **extra):
    return {"id": id_, "categoria": cat, "local": local, "arbitro": arbitro,
            "confianca": conf, "hipotese": f"hipotese de {id_}", **extra}


# ------------------------------------------------------------------ a chave

def test_mesmo_local_e_arbitro_e_a_mesma_acusacao():
    a = acu("prd_01", "prd", "shares.py:89", "AC2")
    b = acu("correcao_03", "correcao", "shares.py:89", "AC2")
    assert _chave_dedup(a) == _chave_dedup(b)


def test_mesmo_local_arbitro_diferente_nao_funde():
    """shares.py:89 apareceu com AC2 E com INV-INSTRUCAO na rodada real."""
    a = acu("prd_01", "prd", "shares.py:89", "AC2")
    b = acu("injection_01", "injection", "shares.py:89", "INV-INSTRUCAO-NAO-E-DADO")
    assert _chave_dedup(a) != _chave_dedup(b)
    assert len(deduplica([a, b])) == 2


def test_espaco_em_volta_nao_cria_duplicata_falsa():
    a = acu("a", "prd", " shares.py:89 ", "AC2")
    b = acu("b", "correcao", "shares.py:89", " AC2 ")
    assert len(deduplica([a, b])) == 1


def test_sem_arbitro_nunca_deduplica():
    """Conservador: fundir dois achados distintos e' pior que gastar uma vaga."""
    a = acu("a", "correcao", "shares.py:89", None)
    b = acu("b", "performance", "shares.py:89", None)
    assert _chave_dedup(a) is None
    assert len(deduplica([a, b])) == 2


def test_sem_local_nunca_deduplica():
    a = acu("a", "prd", None, "AC2")
    b = acu("b", "correcao", None, "AC2")
    assert len(deduplica([a, b])) == 2


# ------------------------------------------------------------------ a fusao

def test_sobrevive_a_de_maior_confianca():
    baixa = acu("baixa", "prd", "shares.py:54", "AC4", conf="baixa")
    alta = acu("alta", "correcao", "shares.py:54", "AC4", conf="alta")
    r = deduplica([baixa, alta])
    assert len(r) == 1 and r[0]["id"] == "alta"


def test_as_fundidas_viram_duplicatas_e_nao_somem():
    """'3 promotores independentes apontaram isto' e' produto, nao limpeza."""
    r = deduplica([
        acu("a", "prd", "shares.py:54", "AC4", conf="alta"),
        acu("b", "correcao", "shares.py:54", "AC4"),
        acu("c", "padroes", "shares.py:54", "AC4"),
    ])
    assert len(r) == 1
    dups = r[0]["_duplicatas"]
    assert len(dups) == 2
    assert {d["categoria"] for d in dups} == {"correcao", "padroes"}
    assert all(d["hipotese"] for d in dups), "a hipotese fundida tem que sobreviver"


def test_acusacao_unica_nao_ganha_campo_duplicatas():
    r = deduplica([acu("a", "prd", "shares.py:1", "AC1")])
    assert "_duplicatas" not in r[0]


def test_lista_vazia():
    assert deduplica([]) == []


# --------------------------------------------------------------- na selecao

def test_seleciona_deduplica_antes_da_cota():
    """Duplicata que ocupa vaga de cota tira a vaga de uma CATEGORIA inteira."""
    acusacoes = [
        acu(f"inj_{i}", "injection", f"a.py:{i}", "INV-INSTRUCAO-NAO-E-DADO")
        for i in range(3)
    ] + [
        # tres iguais: sem dedup comeriam vagas que sao de outras categorias
        acu("prd_1", "prd", "b.py:9", "AC2", conf="alta"),
        acu("cor_1", "correcao", "b.py:9", "AC2"),
        acu("pad_1", "padroes", "b.py:9", "AC2"),
        acu("perf_1", "performance", "c.py:3", None),
    ]
    r = seleciona(acusacoes, teto=10)
    ids = [a["id"] for a in r]
    assert "prd_1" in ids
    assert "cor_1" not in ids and "pad_1" not in ids
    assert "perf_1" in ids, "performance perdeu a vaga para uma duplicata"


def test_seleciona_respeita_o_teto_depois_do_dedup():
    acusacoes = [acu(f"x{i}", "correcao", f"a.py:{i}", "AC3") for i in range(20)]
    assert len(seleciona(acusacoes, teto=4)) == 4


def test_cotas_continuam_valendo():
    """Regressao: o dedup nao pode ter quebrado a repartição por bucket."""
    acusacoes = [acu(f"i{i}", "injection", f"a.py:{i}", f"INV-{i}") for i in range(9)]
    r = seleciona(acusacoes, teto=3, cotas=dict(COTAS))
    assert len(r) == 3


# ------------------------------------------- corroboracao cruzada vs interna

def test_promotores_diferentes_marcam_corroborado():
    r = deduplica([
        acu("prd_1", "prd", "a.py:9", "AC2", conf="alta"),
        acu("cor_1", "correcao", "a.py:9", "AC2"),
    ])
    assert r[0]["_corroborado"] is True


def test_mesmo_promotor_repetindo_NAO_e_corroboracao():
    """Medido em 08/08: as 4 fusoes reais eram todas intra-promotor.

    Chamar isso de 'N promotores independentes apontaram' no palco seria
    falso -- a flag existe para impedir esse slide.
    """
    r = deduplica([
        acu("prd_1", "prd", "a.py:9", "AC2", conf="alta"),
        acu("prd_2", "prd", "a.py:9", "AC2"),
    ])
    assert r[0]["_corroborado"] is False


def test_corroborado_ausente_quando_nao_ha_duplicata():
    r = deduplica([acu("a", "prd", "a.py:1", "AC1")])
    assert "_corroborado" not in r[0]


# ----------------------------------------- desempate por arbitro citado

def test_arbitro_desempata_confianca_igual():
    """Medido 13h32: 28 acusacoes tinham alta+arbitro e a selecao pegou None.

    Sem arbitro a R1 rebaixa CRITICA para SUSPEITA, entao mandar acusacao sem
    arbitro trava o teto de severidade em ALTA por construcao.
    """
    acusacoes = [
        acu("sem_1", "correcao", "a.py:1", None, conf="alta"),
        acu("sem_2", "correcao", "a.py:2", None, conf="alta"),
        acu("com_1", "correcao", "a.py:3", "AC1", conf="alta"),
    ]
    r = seleciona(acusacoes, teto=1)
    assert r[0]["id"] == "com_1", "escolheu sem arbitro tendo um com arbitro igual"


def test_confianca_ainda_manda_mais_que_arbitro():
    """Arbitro e' desempate, nao criterio primario."""
    acusacoes = [
        acu("baixa_com", "correcao", "a.py:1", "AC1", conf="baixa"),
        acu("alta_sem", "correcao", "a.py:2", None, conf="alta"),
    ]
    assert seleciona(acusacoes, teto=1)[0]["id"] == "alta_sem"


def test_performance_nao_e_penalizada_pelo_desempate():
    """A cota reserva a vaga; dentro dela ninguem tem arbitro, desempate neutro."""
    acusacoes = [
        acu(f"cor_{i}", "correcao", f"a.py:{i}", f"AC{i}", conf="alta") for i in range(6)
    ] + [acu("perf_1", "performance", "b.py:1", None, conf="alta")]
    ids = [a["id"] for a in seleciona(acusacoes, teto=3, cotas=dict(COTAS))]
    assert "perf_1" in ids
