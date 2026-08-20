"""A superficie do comentario de PR -- os defeitos medidos no `bancada#1`.

Todos os casos aqui saem do comentario que ESTAVA NO AR em 18/08, e nao de
hipotese sobre o que ficaria bonito. O corpo publicado esta reproduzivel a
partir do disco (`saidas/rodadas/20260818T1928-61cc0a7`), e cada teste abaixo
nomeia o pedaco dele que doia.

🚫 Nenhum destes testes olha o texto do MODELO. O que estava errado era o NOSSO
texto -- o unico que nos escrevemos, e o unico que tinha como estar errado.

⚠️ Nada aqui muda o que o pipeline DECIDE. Acento, plural e link sao texto: a
severidade, o veredito e a lista de descartados saem exatamente iguais. Item que
exigisse mexer em regra do juiz virou PEDIDO para a T3.
"""
import pytest

from veredito import comentario
from veredito import config as cfg
from veredito import juiz
from veredito import superficie


@pytest.fixture(autouse=True)
def sem_secao_de_banco(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "RODADA", tmp_path)


META = {"repo": "luisfelp07/bancada", "head": "61cc0a7", "execucao": "17654321"}


def _a(id_, local="app/main.py:103-106", categoria="correcao", confianca="alta"):
    return {"id": id_, "local": local, "local_normalizado": local,
            "categoria": categoria, "confianca": confianca,
            "hipotese": "remoção da checagem de projeto"}


def _v(id_, sev="ALTA"):
    return {"id": id_, "veredito": "PROVADO", "severidade": sev,
            "motivo": "vaza", "conserto": "restaurar a checagem"}


def _org(condenados=(), descartados=(), inconclusivos=()):
    return {"condenados": list(condenados), "descartados": list(descartados),
            "inconclusivos": list(inconclusivos)}


def _comentario(meta=META, **kw):
    ac = {"c1": _a("c1")}
    return comentario.monta(_org([_v("c1")]), ac, {}, meta=meta, **kw)


# ------------------------------------------------------ o plural, como unidade

def test_plural_concorda_com_o_numero():
    assert superficie.conta(1, "achado") == "1 achado"
    assert superficie.conta(0, "achado") == "0 achados"
    assert superficie.conta(3, "achado") == "3 achados"
    # o que nao faz +s precisa ser dito
    assert superficie.conta(2, "acusação", "acusações") == "2 acusações"
    assert superficie.plural(1, "acusação", "acusações") == "acusação"


# ------------------------------- 🚨 defeito 3: `[ALTA] [alta]`, duas etiquetas
#
# Severidade e confianca sao coisas DIFERENTES, e saiam desenhadas iguais. Le
# como bug -- e esconde a regra central do produto, que e' a severidade
# acompanhar a forca da PROVA enquanto a confianca e' o que a lente achava
# ANTES de existir prova.

def test_severidade_e_confianca_nao_saem_como_duas_etiquetas_iguais():
    corpo = _comentario()
    assert "[ALTA] [alta]" not in corpo, "as duas etiquetas do terminal vazaram"
    assert "severidade" in corpo and "confiança" in corpo, (
        "as duas palavras precisam APARECER: separa-las sem nomea-las deixa o "
        "leitor adivinhando qual e' qual")


# ------------------------ 🚨 defeito 4: caixa alta de terminal dentro de markdown

# 🚨 LITERAL, e nao `superficie.TERMINAL.rotulo(...)`.
#
# A primeira versao destes dois testes perguntava ao estilo qual e' o rotulo
# dele -- o que e' certo para ORDEM ("convergencia vem antes do conserto") e
# errado aqui. A afirmacao destes dois e' sobre a TIPOGRAFIA em si, e os dois
# lados da comparacao saiam da mesma funcao: mutar `Estilo.rotulo` para
# `**{rotulo}.**` mudava o bloco E a referencia junto, e o teste do terminal
# passava VERDE com o defeito presente.
#
# E' o padrao de bug da casa dentro de uma trava escrita nesta trilha: a guarda
# condicionada ao mesmo sinal que ela deveria vigiar. So' apareceu rodando
# `scripts/mutacao_parecer.py`.
_CAIXA_ALTA = ["O QUE:", "ARBITRO:", "EVIDENCIA:", "CONSERTO SUGERIDO:"]


def test_o_bloco_nao_sai_com_rotulo_de_terminal():
    corpo = _comentario()
    for cru in _CAIXA_ALTA:
        assert cru not in corpo, f"`{cru}` e' tipografia de console"
    for rotulo in (juiz.O_QUE, juiz.ARBITRO, juiz.EVIDENCIA, juiz.CONSERTO):
        assert superficie.Markdown().rotulo(rotulo) in corpo


def test_o_terminal_continua_em_caixa_alta():
    """A T1 mexe na superficie do PR. O parecer de terminal nao regride junto."""
    bloco = juiz._bloco(_v("c1"), _a("c1"), None)
    assert bloco.startswith("[ALTA] [alta] correctness - app/main.py:103-106")
    assert "O QUE:" in bloco


# --------------------------------- 🚨 defeito 5: `app/main.py:103-106` sem link

def test_o_local_vira_permalink_ancorado_no_COMMIT():
    corpo = _comentario()
    esperado = ("https://github.com/luisfelp07/bancada/blob/61cc0a7/"
                "app/main.py#L103-L106")
    assert esperado in corpo, "o autor tem a linha exata e teve que procurar"


def test_linha_unica_vira_ancora_de_uma_linha_so():
    lig = superficie.Ligacao(repo="d/r", head="abc1234")
    assert lig.arquivo("app/main.py:103").endswith("/app/main.py#L103")
    assert lig.arquivo("app/main.py:103-106").endswith("#L103-L106")


# 🚨 A metade que importa mais: sem procedencia, NENHUM link.
#
# Um permalink com commit errado manda o autor a um 404, e 404 se le como "o
# Veredito apontou um arquivo que nao existe" -- o mesmo defeito do caminho
# morto, com roupa melhor. Ausente nao e' vazio; sem os dois fatos, texto puro.

def test_sem_repo_ou_commit_o_parecer_NAO_inventa_endereco():
    for meta in ({}, {"repo": "d/r"}, {"head": "abc1234"},
                 {"repo": "sem-barra", "head": "abc1234"}):
        assert superficie.Ligacao.de(meta) is None, meta
    corpo = _comentario(meta={"rodada": "20260818T1928-61cc0a7"})
    assert "http" not in corpo.split("<sub>")[0], "link chutado no cabecalho"
    assert "`app/main.py:103-106`" in corpo, "o endereco sumiu junto com o link"


def test_o_commit_sai_do_carimbo_da_rodada_e_o_casamento_e_ESTRITO():
    assert superficie.head_do_carimbo("20260818T1928-61cc0a7") == "61cc0a7"
    # 🚨 `_carimbo_da_rodada` DEIXA CAIR o sufixo quando o git nao responde.
    # Casamento frouxo transformaria o horario num "commit" e produziria
    # permalink para um sha que nao existe.
    assert superficie.head_do_carimbo("20260818T1928") is None
    assert superficie.head_do_carimbo("") is None
    assert superficie.head_do_carimbo("20260818T1928-zzzzzzz") is None


# ------------------- 🚨 defeito 6: `artefatos/prova_correcao_01.json`, caminho morto
#
# O autor do PR nao tem esse arquivo. E o workflow JA sobe `saidas/rodadas/`
# com `upload-artifact`: a URL existe e nao estava sendo usada.

def test_o_artefato_aponta_para_o_rastro_da_execucao():
    corpo = comentario.monta(
        _org([_v("c1")]), {"c1": _a("c1")},
        {"c1": {"id": "c1", "estado": "PROVADO", "arquivo_do_teste": "t.py",
                "commit_base": "f3bdd65", "commit_head": "61cc0a7",
                "exit_base": 0, "exit_head": 1}},
        meta=META)
    assert "https://github.com/luisfelp07/bancada/actions/runs/17654321" in corpo
    assert "artefatos/prova_c1.json" in corpo, (
        "o nome do arquivo tem que continuar dito: o link e' da execucao "
        "inteira, e o zip tem varios")


def test_sem_execucao_o_caminho_continua_cru_em_vez_de_virar_link_quebrado():
    """Quem rodou na propria maquina TEM o arquivo. Apagar a informacao seria
    pior que deixa-la sem link."""
    est = superficie.Markdown(superficie.Ligacao(repo="d/r", head="abc1234"))
    saida = est.artefato("artefatos/prova_c1.json")
    assert "artefatos/prova_c1.json" in saida
    assert "http" not in saida


# ------------- 🚨 defeito 7: oito suspeitas nao testadas, todas nas mesmas linhas
#
# O cabecalho diz "1 achado" e logo abaixo o autor le oito marcadores sobre o
# mesmo trecho. E' a inflacao de acusacao que a fusao existe para matar,
# sobrevivendo do outro lado da mesma tela.

def _escopo_de_oito():
    return {
        "levantadas": 12, "nao_testadas": 8, "teto": 3,
        "fora_do_orcamento": [
            {"id": f"f{n}", "categoria": "performance",
             "local": f"app/main.py:{linha}", "hipotese": f"h{n}",
             "posicao": 4 + n, "motivo": "abaixo do corte do teto"}
            for n, linha in enumerate(["103", "101-105", "97-108", "89-101",
                                       "103", "95-106", "104", "104"])
        ],
    }


def test_a_fila_toda_no_mesmo_trecho_sai_como_UM_agrupamento():
    corpo = _comentario(escopo=_escopo_de_oito())
    assert "Todas as 8 apontam o mesmo trecho" in corpo
    assert "app/main.py:89-108" in corpo, "a extensao real do trecho"


def test_o_agrupamento_por_endereco_DIZ_que_e_por_endereco():
    """🚫 A fila nao tem artefato: nenhuma daquelas suspeitas foi examinada.
    Chamar de "o mesmo defeito" o que ninguem testou seria a fusao inferindo em
    vez de provar -- o unico lugar do pipeline que a tese do produto proibe."""
    corpo = _comentario(escopo=_escopo_de_oito())
    assert "não** é dizer que são o mesmo defeito" in corpo
    assert "nenhuma delas foi examinada" in corpo


def test_suspeitas_em_trechos_DIFERENTES_nao_sao_juntadas():
    """Guarda do excesso: se agrupasse tudo, o agrupamento nao diria nada."""
    escopo = {
        "levantadas": 5, "nao_testadas": 2, "teto": 3,
        "fora_do_orcamento": [
            {"id": "f1", "categoria": "performance", "local": "app/main.py:10",
             "hipotese": "h1", "posicao": 4, "motivo": "corte"},
            {"id": "f2", "categoria": "prd", "local": "app/outro.py:900",
             "hipotese": "h2", "posicao": 5, "motivo": "corte"},
        ],
    }
    corpo = _comentario(escopo=escopo)
    assert "apontam o mesmo trecho" not in corpo
