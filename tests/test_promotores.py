"""Deduplicacao antes do advogado. Nao bate na API.

O que esta sob teste e' a regra de fusao, nao a chamada de modelo.

⚠️ Desde 10/08 o `arbitro` e' um objeto com procedencia, nao uma sigla. Os
literais aqui usam o formato novo de proposito: teste que so exercita o formato
velho passa a medir uma coisa que o sistema nao produz mais.
"""
from veredito.promotores import COTAS, _chave_dedup, deduplica, seleciona

# Dois arbitros distintos, os dois com procedencia. Sao os que aparecem em
# quase todo caso abaixo; o que muda entre os testes e' o local.
DONO = {"regra": "quem nao e' dono nem destinatario nao pode ler",
        "onde": "docs/REVIEW_TASK.md:43"}
IDEMP = {"regra": "compartilhar duas vezes deixa exatamente um share",
         "onde": "docs/REVIEW_TASK.md:55"}


def acu(id_, cat, local, arbitro, conf="media", **extra):
    return {"id": id_, "categoria": cat, "local": local, "arbitro": arbitro,
            "confianca": conf, "hipotese": f"hipotese de {id_}", **extra}


# ------------------------------------------------------------------ a chave

def test_mesmo_local_e_arbitro_e_a_mesma_acusacao():
    a = acu("prd_01", "prd", "shares.py:89", DONO)
    b = acu("correcao_03", "correcao", "shares.py:89", DONO)
    assert _chave_dedup(a) == _chave_dedup(b)


def test_mesmo_local_arbitro_diferente_nao_funde():
    """shares.py:89 apareceu com dois arbitros distintos na rodada real."""
    a = acu("prd_01", "prd", "shares.py:89", DONO)
    b = acu("injection_01", "injection", "shares.py:89", IDEMP)
    assert _chave_dedup(a) != _chave_dedup(b)
    assert len(deduplica([a, b])) == 2


def test_espaco_em_volta_nao_cria_duplicata_falsa():
    a = acu("a", "prd", " shares.py:89 ", DONO)
    b = acu("b", "correcao", "shares.py:89",
            {"regra": f"  {DONO['regra']}  ", "onde": f" {DONO['onde']} "})
    assert len(deduplica([a, b])) == 1


def test_acusacao_de_rodada_antiga_ainda_deduplica():
    """saidas/*.json de antes de 10/08 tem `arbitro` como string. Reprocessar
    aquilo nao pode explodir nem parar de deduplicar."""
    a = acu("a", "prd", "shares.py:89", "AC2")
    b = acu("b", "correcao", "shares.py:89", {"regra": "AC2", "onde": None})
    assert _chave_dedup(a) == _chave_dedup(b)
    assert len(deduplica([a, b])) == 1


def test_sem_arbitro_nunca_deduplica():
    """Conservador: fundir dois achados distintos e' pior que gastar uma vaga."""
    a = acu("a", "correcao", "shares.py:89", None)
    b = acu("b", "performance", "shares.py:89", None)
    assert _chave_dedup(a) is None
    assert len(deduplica([a, b])) == 2


def test_sem_local_nunca_deduplica():
    a = acu("a", "prd", None, DONO)
    b = acu("b", "correcao", None, DONO)
    assert len(deduplica([a, b])) == 2


# ------------------------------------------------------------------ a fusao

def test_sobrevive_a_de_maior_confianca():
    baixa = acu("baixa", "prd", "shares.py:54", DONO, conf="baixa")
    alta = acu("alta", "correcao", "shares.py:54", DONO, conf="alta")
    r = deduplica([baixa, alta])
    assert len(r) == 1 and r[0]["id"] == "alta"


def test_as_fundidas_viram_duplicatas_e_nao_somem():
    """'3 promotores independentes apontaram isto' e' produto, nao limpeza."""
    r = deduplica([
        acu("a", "prd", "shares.py:54", DONO, conf="alta"),
        acu("b", "correcao", "shares.py:54", DONO),
        acu("c", "padroes", "shares.py:54", DONO),
    ])
    assert len(r) == 1
    dups = r[0]["_duplicatas"]
    assert len(dups) == 2
    assert {d["categoria"] for d in dups} == {"correcao", "padroes"}
    assert all(d["hipotese"] for d in dups), "a hipotese fundida tem que sobreviver"


def test_acusacao_unica_nao_ganha_campo_duplicatas():
    r = deduplica([acu("a", "prd", "shares.py:1", DONO)])
    assert "_duplicatas" not in r[0]


def test_lista_vazia():
    assert deduplica([]) == []


# --------------------------------------------------------------- na selecao

def test_seleciona_deduplica_antes_da_cota():
    """Duplicata que ocupa vaga de cota tira a vaga de uma CATEGORIA inteira."""
    acusacoes = [
        acu(f"inj_{i}", "injection", f"a.py:{i}", IDEMP)
        for i in range(3)
    ] + [
        # tres iguais: sem dedup comeriam vagas que sao de outras categorias
        acu("prd_1", "prd", "b.py:9", DONO, conf="alta"),
        acu("cor_1", "correcao", "b.py:9", DONO),
        acu("pad_1", "padroes", "b.py:9", DONO),
        acu("perf_1", "performance", "c.py:3", None),
    ]
    r = seleciona(acusacoes, teto=10)
    ids = [a["id"] for a in r]
    assert "prd_1" in ids
    assert "cor_1" not in ids and "pad_1" not in ids
    assert "perf_1" in ids, "performance perdeu a vaga para uma duplicata"


def test_seleciona_respeita_o_teto_depois_do_dedup():
    acusacoes = [acu(f"x{i}", "correcao", f"a.py:{i}", IDEMP) for i in range(20)]
    assert len(seleciona(acusacoes, teto=4)) == 4


def test_cotas_continuam_valendo():
    """Regressao: o dedup nao pode ter quebrado a repartição por bucket."""
    acusacoes = [
        acu(f"i{i}", "injection", f"a.py:{i}",
            {"regra": f"regra {i}", "onde": f"docs/X.md:{i}"})
        for i in range(9)
    ]
    r = seleciona(acusacoes, teto=3, cotas=dict(COTAS))
    assert len(r) == 3


# ------------------------------------------- corroboracao cruzada vs interna

def test_promotores_diferentes_marcam_corroborado():
    r = deduplica([
        acu("prd_1", "prd", "a.py:9", DONO, conf="alta"),
        acu("cor_1", "correcao", "a.py:9", DONO),
    ])
    assert r[0]["_corroborado"] is True


def test_mesmo_promotor_repetindo_NAO_e_corroboracao():
    """Medido em 08/08: as 4 fusoes reais eram todas intra-promotor.

    Chamar isso de 'N promotores independentes apontaram' no palco seria
    falso -- a flag existe para impedir esse slide.
    """
    r = deduplica([
        acu("prd_1", "prd", "a.py:9", DONO, conf="alta"),
        acu("prd_2", "prd", "a.py:9", DONO),
    ])
    assert r[0]["_corroborado"] is False


def test_corroborado_ausente_quando_nao_ha_duplicata():
    r = deduplica([acu("a", "prd", "a.py:1", DONO)])
    assert "_corroborado" not in r[0]


# ------------------------------------------- concentracao num local so (10/08)

def test_um_local_nao_come_a_rodada():
    """Medido no encode/httpx#3730: 4 das 6 vagas foram para test-suite.yml:17.

    NAO sao duplicatas -- sao quatro preocupacoes distintas sobre a mesma
    mudanca. Por isso o conserto limita CONCENTRACAO em vez de fundir.
    """
    quentes = [acu(f"q{i}", "padroes", "ci.yml:17", None) for i in range(4)]
    outras = [acu(f"o{i}", "correcao", f"outro{i}.py:{i}", None) for i in range(4)]
    r = seleciona(quentes + outras, teto=6)
    ids = [a["id"] for a in r]
    do_local = [i for i in ids if i.startswith("q")]
    assert len(do_local) <= 2, f"um local levou {len(do_local)} vagas de 6"
    assert sum(1 for i in ids if i.startswith("o")) >= 4


def test_excedente_e_despriorizado_nunca_descartado():
    """Teto MOLE: com fila curta, a excedente ainda entra. Nada some em silencio."""
    quentes = [acu(f"q{i}", "padroes", "ci.yml:17", None) for i in range(4)]
    r = seleciona(quentes, teto=10)
    assert len(r) == 4, "acusacao sumiu por causa do limite de concentracao"
    assert r[-1].get("_excedente_no_local"), "a excedente devia vir marcada e por ultimo"


def test_locais_diferentes_no_mesmo_arquivo_nao_disputam():
    """A injecao de SQL do desafio foi reportada em shares.py:31, :32 e :33.

    Linha diferente = local diferente. Um teto por ARQUIVO mataria achados
    legitimos (shares.py tinha tambem :36 config morta e :39 race condition).
    """
    a = [acu(f"s{i}", "correcao", f"shares.py:{i}", None) for i in (31, 32, 33, 36, 39)]
    r = seleciona(a, teto=10)
    assert len(r) == 5
    assert not any(x.get("_excedente_no_local") for x in r)


def test_limite_de_concentracao_e_ajustavel():
    """Com a fila CHEIA o limite segura. Fila curta e' o caso do teste seguinte."""
    quentes = [acu(f"q{i}", "padroes", "ci.yml:17", None) for i in range(4)]
    outras = [acu(f"o{i}", "correcao", f"a{i}.py:{i}", None) for i in range(6)]
    r = seleciona(quentes + outras, teto=4, max_por_local=1)
    assert sum(1 for a in r if a["id"].startswith("q")) == 1


def test_com_fila_curta_o_limite_cede_em_vez_de_descartar():
    """O contrario do teste acima, e e' de proposito: sem concorrencia por vaga,
    despriorizar viraria descartar -- e nada e' descartado em silencio."""
    quentes = [acu(f"q{i}", "padroes", "ci.yml:17", None) for i in range(4)]
    r = seleciona(quentes, teto=4, max_por_local=1)
    assert len(r) == 4


def test_sem_local_nao_entra_no_limite():
    """Acusacao sem local nao pode ser agrupada com as outras sem local."""
    a = [acu(f"n{i}", "correcao", None, None) for i in range(4)]
    r = seleciona(a, teto=10)
    assert len(r) == 4
    assert not any(x.get("_excedente_no_local") for x in r)


# ------------------------------------------ orcamento por tamanho (11/08)

from veredito.promotores import mede_diff, orcamento_por_lente, _bloco_orcamento


def _diff(n_linhas: int, n_arquivos: int = 1) -> str:
    partes = []
    for f in range(n_arquivos):
        partes += [f"diff --git a/f{f}.py b/f{f}.py", "--- a/f.py", "+++ b/f.py", "@@ -1 +1 @@"]
    partes += ["+linha alterada"] * n_linhas
    return "\n".join(partes)


def test_mede_diff_ignora_cabecalho():
    """+++ e --- sao cabecalho, nao mudanca. Contar errado inflaria o teto."""
    linhas, arquivos = mede_diff(_diff(5, n_arquivos=2))
    assert linhas == 5 and arquivos == 2


def test_pr_de_uma_linha_ganha_o_teto_minimo():
    """django#21735: 1 linha alterada gerou 13 acusacoes. E' o caso que motivou."""
    assert orcamento_por_lente(_diff(1)) == 1


def test_pr_grande_nao_e_estrangulado():
    """next.js#96932: 389 linhas, 29 acusacoes -- o teto nao pode morder ai."""
    assert orcamento_por_lente(_diff(389)) == 10
    assert orcamento_por_lente(_diff(51)) * 6 > 20, "flask#6095 tinha 20; nao pode apertar"


def test_o_teto_cresce_com_o_diff():
    tetos = [orcamento_por_lente(_diff(n)) for n in (1, 13, 51, 200)]
    assert tetos == sorted(tetos) and len(set(tetos)) > 1


def test_o_bloco_diz_o_numero_ao_modelo():
    b = _bloco_orcamento(_diff(1))
    assert "1 linha" in b and "no maximo 1" in b
    assert "array vazio" in b, "silencio precisa ser resposta legitima"


def test_excedente_de_orcamento_e_despriorizado_nao_apagado():
    a = [acu(f"x{i}", "correcao", f"a.py:{i}", None) for i in range(4)]
    for x in a[2:]:
        x["_excedente_orcamento"] = 3
    r = seleciona(a, teto=10)
    assert len(r) == 4, "acusacao sumiu por causa do orcamento"
    assert all(x.get("_excedente_orcamento") for x in r[-2:])
