""""Mesmo defeito" decidido por exit code, e o que impede isso de virar carimbo.

A parte que decide o veredito e' pura e roda em milissegundos -- de proposito.
A logica que separa PROVADO de PALPITE nao pode depender de Docker para ser
conferida, senao ela so' e' testada na maquina que tem Docker, que e' o item 5
do "Como procurar" do CLAUDE.md.

O caso real: `luisfelp07/bancada#1`, um hunk com duas mudancas dentro (docstring
e a condicao de autorizacao) e tres acusacoes com tres testes diferentes.
"""
import pytest

from veredito import prova_de_fusao as pf

BASE = """def le_tarefa(task_id, db, user):
    t = db.scalar(select(Task).where(Task.id == task_id))
    if t is None or t.project_id not in _projetos_visiveis(db, user):
        raise HTTPException(status_code=404)
    return TarefaOut(id=t.id)
"""

HEAD = '''def le_tarefa(task_id, db, user):
    """Abre uma tarefa pelo link.

    Agora quem esta autenticado e tem o link abre a tarefa.
    """
    t = db.scalar(select(Task).where(Task.id == task_id))
    if t is None:
        raise HTTPException(status_code=404)
    return TarefaOut(id=t.id)
'''


# ------------------------------------------- os trechos

def test_um_hunk_com_duas_mudancas_vira_DOIS_trechos():
    """🚨 O ponto do modulo inteiro. Bissecar por HUNK aqui daria UM, e reverter
    o hunk unico e' reverter o PR -- trivialmente verdade, nao prova nada."""
    assert len(pf.trechos(BASE, HEAD)) == 2


def test_reverter_um_trecho_desfaz_SO_ele():
    ts = pf.trechos(BASE, HEAD)
    sem_doc = pf.reverte(BASE, HEAD, ts[0])
    sem_bug = pf.reverte(BASE, HEAD, ts[1])

    assert "Abre uma tarefa" not in sem_doc
    assert "if t is None:" in sem_doc, "revertendo a docstring mexeu na condicao"

    assert "Abre uma tarefa" in sem_bug, "revertendo a condicao mexeu na docstring"
    assert "_projetos_visiveis(db, user)" in sem_bug


def test_arquivo_sem_mudanca_nao_tem_trecho():
    assert pf.trechos(BASE, BASE) == []


# ------------------------------------------- o veredito

IDS = {"correcao_01", "padroes_01", "performance_01"}


def test_um_trecho_que_explica_TODOS_prova_o_mesmo_defeito():
    """O caso medido: trecho 0 (docstring) nao conserta ninguem, trecho 1
    (a condicao) conserta os tres."""
    ver, det = pf.classifica([set(), IDS], IDS)
    assert ver == pf.MESMO
    assert det["trecho"] == 1


def test_trecho_que_explica_SO_UM_PEDACO_prova_defeitos_DIFERENTES():
    """A direcao que a heuristica nao consegue: DESFAZER um agrupamento.

    Se o trecho que conserta A e B nao conserta C, isso nao e' "quase o mesmo
    defeito" -- e' evidencia de que C tem outra causa.
    """
    ver, det = pf.classifica([set(), {"correcao_01", "padroes_01"}], IDS)
    assert ver == pf.DIFERENTES
    assert det["explica"] == ["correcao_01", "padroes_01"]
    assert det["nao_explica"] == ["performance_01"]


def test_diff_de_UM_TRECHO_e_INCONCLUSIVO_e_nao_provado():
    """🚨 A armadilha que quase virou codigo. Com um trecho so', reverte-lo e'
    reverter o PR: TODO teste passa, e isso nao diz nada sobre causa comum.

    Declarar MESMO aqui seria carimbar de "provado" o caso em que a medicao
    nao mede nada -- guarda que dispara sempre, que e' a variacao do padrao de
    bug registrada em 17/08.
    """
    ver, det = pf.classifica([IDS], IDS)
    assert ver == pf.INCONCLUSIVO
    assert "um trecho so'" in det["causa"]


def test_nenhum_trecho_conserta_nada_e_INCONCLUSIVO():
    ver, det = pf.classifica([set(), set()], IDS)
    assert ver == pf.INCONCLUSIVO
    assert "fora do diff" in det["causa"]


def test_sem_medicao_nenhuma_e_INCONCLUSIVO():
    ver, _ = pf.classifica([], IDS)
    assert ver == pf.INCONCLUSIVO


# ------------------------------------------- o que se faz com o veredito

def _g(*ids):
    return [{"id": i} for i in ids]


def test_DIFERENTES_separa_o_grupo_em_dois():
    grupos = pf.parte(_g("a", "b", "c"), pf.DIFERENTES,
                      {"explica": ["a", "b"], "nao_explica": ["c"]})
    assert [[v["id"] for v in g] for g in grupos] == [["a", "b"], ["c"]]


def test_INCONCLUSIVO_MANTEM_o_agrupamento_da_heuristica():
    """⚠️ Nao desfaz nem confirma. Desfazer por nao ter conseguido medir seria
    tratar ausencia de medicao como medicao -- a R3 uma camada acima."""
    grupos = pf.parte(_g("a", "b"), pf.INCONCLUSIVO, {"causa": "sem Docker"})
    assert len(grupos) == 1 and len(grupos[0]) == 2


def test_MESMO_mantem_junto():
    grupos = pf.parte(_g("a", "b"), pf.MESMO, {"trecho": 1})
    assert len(grupos) == 1


# ------------------------------------------- o que o leitor ve

def test_so_diz_PROVADA_quando_provou():
    """A palavra "provado" e' o produto inteiro. Ela nao pode aparecer num
    agrupamento que foi palpite."""
    assert "PROVADA" in pf.frase(pf.MESMO, {"trecho": 1}, 3)
    for ver in (pf.INCONCLUSIVO, pf.DIFERENTES):
        assert "FUSAO PROVADA" not in pf.frase(ver, {"causa": "x", "explica": [],
                                                     "nao_explica": []}, 3)


def test_inconclusivo_diz_a_CAUSA_e_se_assume_indicio():
    f = pf.frase(pf.INCONCLUSIVO, {"causa": "o projeto nao declara codigo"}, 2)
    assert "o projeto nao declara codigo" in f
    assert "indicio e nao prova" in f
