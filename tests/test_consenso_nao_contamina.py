"""O consenso entre lentes ORDENA. Nunca julga.

🚨 A pergunta que motivou estes testes, feita em 15/08: *"não acha que ele
contaminaria a conclusão? Só porque tem mais, ele validaria como certa."*

A preocupação está certa e tem três formas. Duas são impedidas pelo desenho e
travadas aqui; a terceira é mitigada pela cota:

  1. o advogado VER o consenso        -> viraria pressão para confirmar
  2. o consenso mexer na SEVERIDADE   -> opinião virando força de prova
  3. o consenso matar o achado sutil  -> o que só uma lente viu nunca entraria

A 3 é a mais séria e a menos óbvia: um ranking puro por consenso premiaria
sempre o defeito evidente e mataria o que uma única lente afiada viu. Por isso o
consenso ordena DENTRO da cota, e a cota garante vaga por categoria.
"""

import json
from pathlib import Path

from veredito import promotores


def _a(id_, cat, local, conf="media"):
    return {"id": id_, "categoria": cat, "local": local, "confianca": conf,
            "hipotese": "h", "provado_se": "p"}


# ------------------------------------------------- o que o consenso conta

def test_conta_lentes_e_nao_acusacoes():
    """⚠️ Cinco acusações da MESMA lente são uma opinião repetida, não cinco.

    Contar acusações premiaria a lente barulhenta — que é exatamente o que as
    cotas existem para impedir."""
    mesma_lente = [_a(f"x{i}", "padroes", "app/main.py:30") for i in range(5)]
    c = promotores.consenso(mesma_lente)
    assert all(v == 1 for v in c.values()), f"contou acusacoes, nao lentes: {c}"

    cinco_lentes = [_a(f"y{i}", cat, "app/main.py:30") for i, cat in enumerate(
        ["padroes", "prd", "correcao", "performance", "injection"])]
    assert all(v == 5 for v in promotores.consenso(cinco_lentes).values())


def test_lugares_diferentes_nao_somam():
    acus = [_a("a", "padroes", "app/main.py:30"),
            _a("b", "prd", "app/outro.py:30"),
            _a("c", "correcao", "app/main.py:900")]
    assert promotores.consenso(acus) == {"a": 1, "b": 1, "c": 1}


def test_faixa_proxima_conta_como_mesmo_ponto():
    """As lentes escrevem `:30`, `:31`, `:32` para o mesmo defeito — medido em
    11/08. Casamento exato daria zero consenso justamente onde há mais."""
    acus = [_a("a", "padroes", "app/main.py:30"),
            _a("b", "prd", "app/main.py:31"),
            _a("c", "correcao", "app/main.py:32")]
    assert promotores.consenso(acus) == {"a": 3, "b": 3, "c": 3}


def test_regiao_larga_nao_corrobora():
    """Acusação que aponta 80 linhas não é o mesmo ponto de nada — é o erro dos
    94 árbitros, inflar sinal."""
    acus = [_a("largo", "padroes", "app/main.py:10-95"),
            _a("ponto", "prd", "app/main.py:30")]
    assert promotores.consenso(acus)["largo"] == 1


# ----------------------------------- 🚨 1: o advogado NUNCA vê o consenso

def test_o_prompt_da_acusacao_nao_menciona_consenso():
    """Se o advogado soubesse que cinco lentes concordam, isso viraria pressão
    para confirmar — e o produto mediria opinião de modelo em vez de exit code.

    É o mesmo motivo pelo qual o scanner roda EM PARALELO: mostrar o achado dele
    ao promotor ancora a lente e destrói o sinal de corroboração."""
    from veredito.advogado import _prompt_da_acusacao
    a = _a("x", "padroes", "app/main.py:30")
    a["_lentes_concordam"] = 5
    prompt = _prompt_da_acusacao(a)
    assert "5" not in prompt or "lentes" not in prompt.lower()
    assert "concordam" not in prompt.lower()
    assert "consenso" not in prompt.lower()


def test_o_sistema_nao_fala_de_consenso():
    from veredito.advogado import SISTEMA
    baixo = SISTEMA.lower()
    for proibido in ("consenso", "lentes concordam", "quantas lentes"):
        assert proibido not in baixo, f"o SISTEMA menciona '{proibido}'"


# ------------------------------- 🚨 2: a severidade segue a PROVA, não o voto

def test_consenso_nao_entra_nas_regras_do_juiz():
    """A regra central: a severidade acompanha a FORÇA DA PROVA, não a
    gravidade teórica — e muito menos quantas lentes acharam."""
    fonte = Path(__import__("veredito.juiz", fromlist=["x"]).__file__)
    texto = fonte.read_text(encoding="utf-8-sig")
    for proibido in ("_lentes_concordam", "consenso"):
        assert proibido not in texto, (
            f"juiz.py menciona '{proibido}': voto de lente nao pode virar "
            "severidade")


# ------------------------- 🚨 3: o achado que só UMA lente viu não morre

def test_consenso_ordena_dentro_da_cota_e_nao_por_cima():
    """A forma mais séria da contaminação, e a menos óbvia.

    Ranking puro por consenso premiaria sempre o defeito evidente e mataria o
    que uma única lente afiada viu. A cota garante vaga por categoria, e o
    consenso só reordena dentro dela.
    """
    # 4 acusações de padrões no mesmo ponto (consenso alto entre si é 1 -- mesma
    # lente), e UMA de performance sozinha noutro lugar.
    acus = [_a(f"p{i}", "padroes", "app/main.py:30") for i in range(4)]
    acus += [_a("solitaria", "performance", "app/outro.py:99")]
    escolhidas = promotores.seleciona(acus, teto=3)
    ids = [a["id"] for a in escolhidas]
    assert "solitaria" in ids, (
        "o achado de lente unica perdeu a vaga da propria categoria")


def test_ponto_com_mais_lentes_sobe_dentro_da_categoria():
    """O ganho que o consenso compra, medido em 15/08: no PR do race, o
    aglomerado de concorrência tinha 5 lentes e levou 1 vaga de 3."""
    # duas de `correcao`: uma isolada, outra num ponto que 3 lentes apontam.
    acus = [
        _a("isolada", "correcao", "app/main.py:10"),
        _a("consensual", "correcao", "app/main.py:50"),
        _a("eco1", "prd", "app/main.py:50"),
        _a("eco2", "performance", "app/main.py:51"),
    ]
    escolhidas = promotores.seleciona(acus, teto=1, cotas={"correcao": 1})
    assert escolhidas[0]["id"] == "consensual", (
        "a acusacao que tres lentes viram nao subiu dentro da categoria")


# --------------------------------------------- o registro fica no artefato

def test_o_numero_fica_gravado_para_auditoria():
    """Ordenar sem deixar rastro seria uma decisão invisível. O número entra na
    acusação e viaja para `acusacoes.json`."""
    acus = [_a("a", "padroes", "app/main.py:30"), _a("b", "prd", "app/main.py:30")]
    escolhidas = promotores.seleciona(acus, teto=2)
    assert all("_lentes_concordam" in a for a in escolhidas)
    assert json.dumps(escolhidas)  # serializavel: o artefato precisa gravar
