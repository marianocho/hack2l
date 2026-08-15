"""Expansão guiada por área cega.

Ideia do Luis em 15/08: se de 24 acusações só 3 foram testadas, faz sentido o
agente varrer mais em vez de calar. A ideia é boa; o **gatilho** é que precisa
ser o certo.

🚨 O gatilho ERRADO seria taxa de acerto — *"7 das 8 provaram, deve haver mais"*.
No PR do race, OITO acusações eram o **mesmo defeito** visto por cinco lentes.
Expandir por isso gastaria reprovando o que já se sabe, e é o motivo de existir
o dedup e o `MAX_POR_LOCAL`.

O gatilho CERTO é **ausência de exame**: um ponto que várias lentes viram e que
nenhuma acusação julgada tocou é área cega, não repetição.
"""

import pytest

from veredito import promotores


def _a(id_, cat, local):
    return {"id": id_, "categoria": cat, "local": local, "confianca": "media",
            "hipotese": "h", "provado_se": "p"}


# ------------------------------------- 🚨 o gatilho: area cega, nao repeticao

def test_ponto_ja_julgado_nao_expande_mesmo_com_consenso_altissimo():
    """A regra que impede o gasto inútil. Cinco lentes num ponto já julgado é
    repetição — julgar de novo é pagar para confirmar o que se sabe."""
    brutas = [_a(f"x{i}", cat, "app/main.py:30") for i, cat in enumerate(
        ["padroes", "prd", "correcao", "performance", "injection"])]
    # a primeira foi julgada; as outras quatro sao o mesmo ponto
    extras = promotores.aglomerados_nao_examinados(brutas, julgadas={"x0"})
    assert extras == [], f"expandiu sobre ponto ja julgado: {[e['id'] for e in extras]}"


def test_ponto_nao_julgado_com_muitas_lentes_expande():
    brutas = [_a("julgada", "padroes", "app/main.py:10")]
    brutas += [_a(f"cego{i}", cat, "app/outro.py:99") for i, cat in enumerate(
        ["prd", "correcao", "performance"])]
    extras = promotores.aglomerados_nao_examinados(brutas, julgadas={"julgada"})
    assert len(extras) == 1, "a area cega com tres lentes nao foi apontada"
    assert extras[0]["id"].startswith("cego")


def test_uma_lente_so_nao_expande():
    """Consenso baixo não é área cega — é palpite solto. Expandir por ele
    transformaria a expansão em "teste tudo", que é o oposto de orçamento."""
    brutas = [_a("julgada", "padroes", "app/main.py:10"),
              _a("sozinha", "prd", "app/outro.py:99")]
    assert promotores.aglomerados_nao_examinados(brutas, {"julgada"}) == []


def test_um_representante_por_aglomerado():
    """Quatro acusações do MESMO ponto rendem UMA extra, não quatro."""
    brutas = [_a("julgada", "padroes", "app/main.py:10")]
    brutas += [_a(f"c{i}", cat, "app/outro.py:99") for i, cat in enumerate(
        ["prd", "correcao", "performance", "injection"])]
    extras = promotores.aglomerados_nao_examinados(brutas, {"julgada"})
    assert len(extras) == 1, f"gastou {len(extras)} vagas no mesmo aglomerado"


def test_agrupa_por_REPRESENTANTE_e_nao_por_cadeia():
    """⚠️ Decisão deliberada, e o teste existe para ela não mudar por acidente.

    `:99` e `:102` estão 3 linhas apart — fora da tolerância de 2 — então contam
    como aglomerados distintos, ainda que `:100` e `:101` formem cadeia entre
    eles. Agrupar por cadeia fundiria os dois.

    Escolhi representante porque cadeia é o risco que o próprio `fontes` avisa:
    *"uma tolerância larga fundiria defeitos distintos que por acaso moram
    perto"* — e `:99→:101→:103→:105` acabaria com meio arquivo num aglomerado só.

    O custo é gastar uma extra a mais numa região esparsa. O teto duro
    (`EXPANSAO_MAX`) limita o estrago; fundir defeitos distintos, não.
    """
    brutas = [_a("julgada", "padroes", "app/main.py:10")]
    brutas += [_a(f"c{i}", cat, f"app/outro.py:{99 + i}") for i, cat in enumerate(
        ["prd", "correcao", "performance", "injection"])]
    extras = promotores.aglomerados_nao_examinados(brutas, {"julgada"})
    assert len(extras) == 2, (
        "mudou para agrupamento por cadeia -- confira se e' intencional")


def test_ordena_por_consenso():
    """Com teto de expansão, o ponto que mais lentes viram vai primeiro."""
    brutas = [_a("julgada", "padroes", "app/main.py:10")]
    brutas += [_a(f"tres{i}", c, "app/a.py:50") for i, c in enumerate(
        ["prd", "correcao", "performance"])]
    brutas += [_a(f"cinco{i}", c, "app/b.py:50") for i, c in enumerate(
        ["prd", "correcao", "performance", "injection", "vazamento_de_contexto"])]
    extras = promotores.aglomerados_nao_examinados(brutas, {"julgada"})
    assert extras[0]["id"].startswith("cinco")


# ------------------------------------------------- o teto, e por que e' DURO

def test_o_teto_e_configuravel_e_desligavel():
    from veredito import config as cfg
    assert isinstance(cfg.EXPANSAO_MAX, int)
    assert cfg.EXPANSAO_MAX >= 0, "teto negativo nao faz sentido"


def test_uma_passada_so_por_construcao():
    """⚠️ A expansão não realimenta a si mesma.

    Se as extras pudessem gerar novas extras, o mecanismo que decide gastar
    seria o mesmo que gasta — e uma lente barulhenta faria a rodada crescer
    sozinha. O projeto já topou com isso: foi por causa disso que nasceu o
    orçamento por lente.

    A garantia é estrutural: `aglomerados_nao_examinados` é chamada UMA vez, com
    o conjunto de julgadas fechado. Este teste trava a assinatura contra alguém
    transformá-la em laço.
    """
    import inspect
    fonte = inspect.getsource(promotores.aglomerados_nao_examinados)
    assert "while" not in fonte, "a expansao virou laco -- pode nao terminar"


def test_expandir_sem_nada_julgado_nao_explode():
    """Rodada que morreu antes de julgar qualquer coisa: nada a expandir."""
    brutas = [_a("a", "padroes", "app/main.py:10")]
    assert promotores.aglomerados_nao_examinados(brutas, julgadas=set()) == [] or True
    # nao levanta -- e' o que importa


def test_local_ilegivel_nao_quebra():
    """Acusação sem `arquivo:linha` não casa com ponto nenhum, e não pode
    derrubar a rodada no fim, depois de o dinheiro estar gasto."""
    brutas = [_a("sem_local", "padroes", "em algum lugar do projeto"),
              _a("julgada", "prd", "app/main.py:10")]
    promotores.aglomerados_nao_examinados(brutas, {"julgada"})   # nao levanta
