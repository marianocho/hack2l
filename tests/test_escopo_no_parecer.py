"""O parecer confessa o escopo: quantas foram levantadas, quantas foram testadas.

🚨 O defeito que estes testes travam, medido em 15/08 na bancada. O parecer
abria com:

    3 com parecer, 0 descartados com motivo, 0 inconclusivos com causa.

numa rodada que partiu de 24 suspeitas. Nenhum dos tres numeros era falso, e o
conjunto mentia: 21 acusacoes nunca foram examinadas e nao apareciam em lugar
nenhum do arquivo. A regra central do projeto diz que nada e' descartado em
silencio -- e o console, que dizia "8 de 25 vao ao advogado", rola; o parecer
fica.

⚠️ As nao-testadas NAO sao descartes. Um descarte passou pela pericia e voltou
com motivo; estas nunca foram olhadas. Somar as duas listas seria a mesma
absolvicao falsa que somar INCONCLUSIVO com REFUTADO, so' que na entrada do
funil em vez da saida -- e por isso ha' teste para a separacao, nao so' para a
contagem.
"""

import json

import pytest

from veredito import config as cfg
from veredito import juiz, promotores


def acu(id_, cat="correcao", local="app/main.py:10", conf="media"):
    return {"id": id_, "categoria": cat, "local": local, "confianca": conf,
            "arbitro": None, "hipotese": f"hipotese de {id_}"}


@pytest.fixture
def rodada(tmp_path, monkeypatch):
    """Uma pasta de rodada isolada, com os globais restaurados no fim."""
    monkeypatch.setattr(cfg, "SAIDAS", tmp_path / "saidas")
    monkeypatch.setattr(cfg, "RODADA", tmp_path / "saidas")
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "saidas" / "artefatos")
    (tmp_path / "saidas" / "artefatos").mkdir(parents=True)
    return tmp_path / "saidas"


# ------------------------------------------------- a fila, e a conta que fecha

def test_a_conta_fecha_levantadas_igual_fundidas_mais_testadas_mais_fora():
    """Se ela nao fechasse, o bloco seria mais uma metrica medindo outra coisa.

    E' a pergunta nº 2 da lista de busca do CLAUDE.md aplicada ao proprio
    conserto: "isto pode estar medindo outra coisa?"
    """
    brutas = [acu(f"a{i}", local=f"app/f{i}.py:1") for i in range(12)]
    fila = promotores.fila_completa(brutas)
    e = promotores.escopo(brutas, fila, teto=5)
    assert e["levantadas"] == 12
    assert (e["fundidas_por_duplicata"] + e["testadas"] + e["nao_testadas"]
            == e["levantadas"])


def test_seleciona_e_o_prefixo_exato_da_fila_completa():
    """🚨 Guarda contra a divergencia silenciosa entre as duas vias.

    Se o escopo fosse montado por um SEGUNDO caminho de ordenacao, ele poderia
    descrever uma fila que nao e' a que rodou -- e o parecer passaria a falar de
    uma rodada que nao aconteceu. Uma implementacao so'; este teste e' quem
    cobra.
    """
    brutas = [acu(f"a{i}", cat=("prd" if i % 3 else "correcao"),
                  local=f"app/f{i % 4}.py:{i}") for i in range(14)]
    fila = promotores.fila_completa([dict(a) for a in brutas])
    for teto in (1, 3, 8, 14, 40):
        escolhidas = promotores.seleciona([dict(a) for a in brutas], teto)
        assert [a["id"] for a in escolhidas] == [a["id"] for a in fila[:teto]]


def test_quem_fica_de_fora_carrega_o_motivo_e_a_posicao():
    """"Nona numa rodada de oito" e "vigesima quinta" sao conversas diferentes."""
    brutas = [acu(f"a{i}", local=f"app/f{i}.py:1") for i in range(9)]
    e = promotores.escopo(brutas, promotores.fila_completa(brutas), teto=4)
    fora = e["fora_do_orcamento"]
    assert len(fora) == 5
    assert [f["posicao"] for f in fora] == [5, 6, 7, 8, 9]
    assert all(f["motivo"] for f in fora), "motivo vazio nao explica nada"


def test_despriorizada_por_local_diz_que_foi_o_local():
    """O motivo tem que distinguir as tres camadas, senao vira 'ficou de fora'."""
    quentes = [acu(f"q{i}", local="app/main.py:31") for i in range(5)]
    e = promotores.escopo(quentes, promotores.fila_completa(quentes), teto=2)
    motivos = " ".join(f["motivo"] for f in e["fora_do_orcamento"])
    assert "local" in motivos


def test_quem_ganhou_vaga_de_cota_e_caiu_no_teto_nao_diz_que_ganhou_vaga():
    """🚨 O defeito que a primeira execucao sobre dado REAL expos.

    Na rodada 20260815T0239, a nona e a decima da fila tinham ganhado vaga de
    cota e o teto (TOP_N=8) chegou antes. O motivo saia "vaga da cota de
    padroes" -- dentro da lista de NAO TESTADAS. Ler "ganhou vaga" em quem nao
    foi examinado e' o primo do padrao de bug do projeto: o campo descrevia a
    POSICAO na fila e estava sendo lido como a razao da EXCLUSAO.

    Aqui: 4 categorias distintas, uma vaga de cota cada, teto de 2. As duas
    ultimas passaram pela cota e mesmo assim ficaram de fora.
    """
    brutas = [acu("a1", cat="correcao", local="app/a.py:1"),
              acu("a2", cat="prd", local="app/b.py:1"),
              acu("a3", cat="padroes", local="app/c.py:1"),
              acu("a4", cat="performance", local="app/d.py:1")]
    e = promotores.escopo(brutas, promotores.fila_completa(brutas), teto=2)
    fora = e["fora_do_orcamento"]
    assert len(fora) == 2
    for f in fora:
        assert "vaga" not in f["motivo"], f"diz que ganhou vaga: {f['motivo']!r}"
        assert "abaixo do corte" in f["motivo"]


# ------------------------------------------------------------- o cabecalho

def _org(condenados=0, descartados=0, inconclusivos=0):
    return {"condenados": [{"id": f"c{i}"} for i in range(condenados)],
            "descartados": [{"id": f"d{i}"} for i in range(descartados)],
            "inconclusivos": [{"id": f"i{i}"} for i in range(inconclusivos)]}


def test_cabecalho_traz_o_total_levantado_e_o_teto():
    e = {"levantadas": 24, "testadas": 3, "nao_testadas": 21, "teto": 3,
         "fundidas_por_duplicata": 0, "fora_do_orcamento": []}
    texto = juiz.formata_parecer(_org(condenados=3), {}, {}, escopo=e)
    assert "24 suspeitas levantadas" in texto
    assert "3 testadas" in texto
    assert "TOP_N=3" in texto


def test_as_tres_contagens_dizem_que_sao_DAS_EXAMINADAS():
    """🚨 A metade menos obvia do conserto, e a que sobrevive sem escopo.

    "3 com parecer, 0 descartados, 0 inconclusivos" solto implica que 3 era tudo
    que havia. Ancorar as tres em "das examinadas" tira a implicacao de
    completude mesmo quando o total nao pode ser recuperado do disco.
    """
    texto = juiz.formata_parecer(_org(condenados=3), {}, {})
    assert "Das examinadas:" in texto
    assert "3 com parecer" in texto


def test_secao_de_nao_testadas_lista_cada_uma_com_motivo():
    e = {"levantadas": 6, "testadas": 2, "nao_testadas": 2, "teto": 2,
         "fundidas_por_duplicata": 2,
         "fora_do_orcamento": [
             {"id": "a5", "categoria": "correcao", "local": "app/main.py:88",
              "hipotese": "limite de membros nao e' atomico", "posicao": 3,
              "motivo": "despriorizada: o local ja tinha 2 vaga(s)"},
             {"id": "a6", "categoria": "prd", "local": "app/api.py:12",
              "hipotese": "resposta fora do contrato", "posicao": 4,
              "motivo": "abaixo do corte do teto"},
         ]}
    texto = juiz.formata_parecer(_org(condenados=1, descartados=1), {}, {}, escopo=e)
    assert "LEVANTADAS E NAO TESTADAS" in texto
    assert "app/main.py:88" in texto and "app/api.py:12" in texto
    assert "limite de membros nao e' atomico" in texto
    assert "o local ja tinha 2 vaga(s)" in texto
    # As fundidas por duplicata sao um destino diferente de "nao olhada", e o
    # parecer separa os dois -- senao a conta do leitor nao fecha.
    assert "2 eram duplicatas" in texto or "Outras 2" in texto


def test_nao_testada_nunca_e_apresentada_como_descarte():
    """⚠️ A distincao que o produto inteiro defende, na entrada do funil.

    Se a secao nao disser em voz alta que estas nao foram examinadas, ela vira
    uma segunda lista de descartados -- e o parecer passa a alegar pericia que
    nao houve.
    """
    e = {"levantadas": 5, "testadas": 1, "nao_testadas": 4, "teto": 1,
         "fundidas_por_duplicata": 0,
         "fora_do_orcamento": [
             {"id": f"a{i}", "categoria": "correcao", "local": f"app/f{i}.py:1",
              "hipotese": "h", "posicao": i + 1, "motivo": "abaixo do corte"}
             for i in range(1, 5)]}
    texto = juiz.formata_parecer(_org(condenados=1), {}, {}, escopo=e)
    corpo = texto.split("## LEVANTADAS E NAO TESTADAS")[1]
    assert "Não são descartes" in corpo
    assert "nenhuma tem veredito" in corpo
    # E nao contaminou a contagem da pericia: as 4 nao viraram descartados.
    assert "0 descartados com motivo" in texto


def test_sem_nada_fora_do_orcamento_a_secao_nao_aparece():
    """Secao vazia em todo parecer treina o leitor a pular -- e ai ela nao serve
    no dia em que importa. E' a mesma razao do silencio em _secao_efeito_no_banco."""
    e = {"levantadas": 3, "testadas": 3, "nao_testadas": 0, "teto": 8,
         "fundidas_por_duplicata": 0, "fora_do_orcamento": []}
    texto = juiz.formata_parecer(_org(condenados=3), {}, {}, escopo=e)
    assert "LEVANTADAS E NAO TESTADAS" not in texto


# -------------------------------------------- a guarda vista FALHANDO (disco)

def test_escopo_ausente_ainda_conta_pelas_brutas(rodada):
    """🚨 O padrao de bug do projeto, apontado para o proprio conserto.

    `escopo.json` so' passa a existir em 15/08. Se o cabecalho dependesse SO'
    dele, toda rodada anterior -- e qualquer rodada que morresse antes de
    grava-lo -- cairia de volta no cabecalho que implica completude. A guarda
    ficaria muda exatamente onde o artefato falta, que e' o formato de erro que
    este projeto ja cometeu sete vezes.

    Este teste injeta a violacao: pasta SEM escopo.json, com as brutas no lugar.
    """
    (rodada / "acusacoes_brutas.json").write_text(
        json.dumps([acu(f"a{i}") for i in range(25)]), encoding="utf-8")
    (rodada / "veredictos.json").write_text(
        json.dumps([{"id": f"a{i}", "veredito": "REFUTADO"} for i in range(8)]),
        encoding="utf-8")
    assert not (rodada / "escopo.json").exists()

    e = juiz._escopo_do_disco(examinadas=8)
    assert e is not None, "sem escopo.json o parecer voltaria a implicar completude"
    assert e["levantadas"] == 25
    assert e["nao_testadas"] == 17

    texto = juiz.formata_parecer(_org(descartados=8), {}, {}, escopo=e)
    assert "25 suspeitas levantadas" in texto
    # O que NAO se reconstroi tem que ser dito, nao suposto: sem escopo gravado
    # nao da' para separar duplicata fundida de acusacao nao olhada.
    assert "não foi gravado nesta rodada" in texto


def test_escopo_gravado_vence_a_reconstrucao(rodada):
    """Com os dois em disco, vale o que a rodada REGISTROU.

    A reconstrucao e' um teto (conta duplicata fundida como nao-testada); o
    arquivo e' o fato. Preferir a reconstrucao seria trocar medida por estimativa
    tendo a medida em maos.
    """
    (rodada / "acusacoes_brutas.json").write_text(
        json.dumps([acu(f"a{i}") for i in range(25)]), encoding="utf-8")
    (rodada / "escopo.json").write_text(json.dumps(
        {"levantadas": 25, "fundidas_por_duplicata": 3, "testadas": 8,
         "nao_testadas": 14, "teto": 8, "fora_do_orcamento": []}), encoding="utf-8")
    e = juiz._escopo_do_disco(examinadas=8)
    assert e["nao_testadas"] == 14, "ignorou o escopo gravado e reconstruiu 17"
    assert e["fundidas_por_duplicata"] == 3


def test_rodada_sem_brutas_e_sem_escopo_nao_inventa_numero(rodada):
    """Nada em disco = nada a afirmar. Inventar total seria o primo do bug:
    metrica que mede outra coisa, aqui com o valor saindo do nada."""
    assert juiz._escopo_do_disco(examinadas=0) is None
