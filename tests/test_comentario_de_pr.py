"""O parecer como comentario de PR -- a saida, e o leitor que ela tem.

🚨 O leitor aqui NAO e' quem rodou. No terminal, quem le sabe o que as palavras
significam. Num PR, quem le e' o AUTOR, que nunca ouviu falar deste produto.

Medido do jeito mais direto possivel: o dono do projeto, olhando um parecer com
"4 descartados", perguntou se aquilo era boa noticia. Se quem CONSTRUIU o
Veredito precisa perguntar, o autor de um PR de terceiro le "4 descartados"
como "acharam 4 problemas no meu PR" -- e o produto vira acusador de uma coisa
que ele acabou de inocentar.
"""
import json

import pytest

from veredito import comentario
from veredito import config as cfg
from veredito import ferramentas as f
from veredito import juiz


def _org(condenados=(), descartados=(), inconclusivos=()):
    return {"condenados": list(condenados), "descartados": list(descartados),
            "inconclusivos": list(inconclusivos)}


def _v(id_, motivo="porque sim", sev="MEDIA"):
    return {"id": id_, "veredito": "REFUTADO", "severidade": sev, "motivo": motivo}


def _a(id_, local="app/x.py:1", categoria="correcao"):
    return {"id": id_, "local": local, "local_normalizado": local,
            "categoria": categoria}


@pytest.fixture(autouse=True)
def sem_secao_de_banco(monkeypatch, tmp_path):
    """O efeito no banco tem arquivo proprio e testes proprios."""
    monkeypatch.setattr(cfg, "RODADA", tmp_path)


# ------------------------------------------- o enquadramento

def test_descartado_e_explicado_como_NAO_e_problema_do_autor():
    """A frase que impede o comentario de acusar o que ele inocentou."""
    corpo = comentario.monta(_org(descartados=[_v("a1")]), {"a1": _a("a1")}, {})
    assert "não é um problema no seu PR" in corpo, (
        "o autor vai ler 'descartado' como 'achado'")


def test_resumo_sem_condenado_diz_NADA_A_APONTAR():
    """Uma linha, e e' a unica que muita gente le."""
    corpo = comentario.monta(_org(descartados=[_v("a1"), _v("a2")]),
                             {"a1": _a("a1"), "a2": _a("a2")}, {})
    primeira = [l for l in corpo.splitlines() if l.startswith("**")][0]
    assert "Nada a apontar" in primeira


def test_resumo_com_condenado_poe_o_achado_na_frente():
    corpo = comentario.monta(
        _org(condenados=[{"id": "c1", "veredito": "PROVADO", "severidade": "ALTA",
                          "motivo": "vaza", "prova_ponta_a_ponta": True}],
             descartados=[_v("a1")]),
        {"c1": _a("c1"), "a1": _a("a1")}, {})
    primeira = [l for l in corpo.splitlines() if l.startswith("**")][0]
    assert "1 achado com evidência" in primeira


def test_condenado_fica_ABERTO_e_o_resto_colapsado():
    """O autor precisa agir no achado; o resto e' contexto que nao pode competir."""
    corpo = comentario.monta(
        _org(condenados=[{"id": "c1", "veredito": "PROVADO", "severidade": "ALTA",
                          "motivo": "vaza"}],
             descartados=[_v("a1")]),
        {"c1": _a("c1"), "a1": _a("a1")}, {})
    antes = corpo.index("c1") if "c1" in corpo else corpo.index("vaza")
    assert antes < corpo.index("<details>"), "o achado ficou depois do colapsavel"


# ------------------------------------- 🚨 a superficie do CLIENTE, nao a nossa

# As duas travas abaixo guardam os defeitos 1 e 2 da trilha T1, medidos no
# comentario que estava no ar em `bancada#1`. Nenhuma delas olha o texto do
# MODELO -- so' o nosso, que e' o unico que nos escrevemos e o unico que tinha
# como estar errado.

def _corpo_de_exemplo(**contagens):
    """Um comentario com condenado, descartado e inconclusivo, sem tocar em API."""
    c = [{"id": "c1", "veredito": "PROVADO", "severidade": "ALTA",
          "motivo": "vaza", "conserto": "restaurar a checagem"}]
    d = [_v(f"d{i}") for i in range(contagens.get("d", 3))]
    i = [_v(f"i{n}") for n in range(contagens.get("i", 2))]
    ac = {v["id"]: _a(v["id"]) for v in c + d + i}
    # Com escopo: exercita tambem a secao das nao-testadas, que e' onde o
    # defeito 7 mora e onde a palavra "orcamento" aparece.
    escopo = {
        "levantadas": 9, "nao_testadas": 2, "teto": 3,
        "fora_do_orcamento": [
            {"id": "f1", "categoria": "performance", "local": "app/x.py:10",
             "hipotese": "h1", "posicao": 4, "motivo": "abaixo do corte do teto"},
            {"id": "f2", "categoria": "prd", "local": "app/x.py:11",
             "hipotese": "h2", "posicao": 5, "motivo": "abaixo do corte do teto"},
        ],
    }
    return comentario.monta(_org(c, d, i), ac, {}, escopo=escopo)


# Plural de formulario: `1 achado(s)`, `0 suspeita(s)`, `2 lente(s)`. O leitor
# le "o robo nao sabe contar" antes de ler o achado, e le isso na PRIMEIRA linha.
def test_o_plural_nao_e_de_formulario():
    """🚨 Estava no ar: `**1 achado(s) com evidencia.**`, na linha de abertura."""
    for d, i in ((3, 2), (1, 1), (0, 0)):
        corpo = _corpo_de_exemplo(d=d, i=i)
        assert "(s)" not in corpo, (
            f"plural de formulario sobreviveu com d={d}, i={i}: "
            + next(l for l in corpo.splitlines() if "(s)" in l))


# Acento: a restricao do console cp1252 vazou para o navegador, onde ela nunca
# valeu -- e nem no console ela pedia isto, porque acento CABE em cp1252.
_NOSSAS_PALAVRAS = [
    ("evidência", "evidencia"), ("verificação", "verificacao"),
    ("acusação", "acusacao"), ("não", "nao"), ("é", "e'"),
    ("reproduzível", "reproduzivel"), ("orçamento", "orcamento"),
]


def test_o_texto_que_o_autor_le_vem_acentuado():
    """🚨 `1 achado(s) com evidencia` ao lado de `Remoção` do modelo, na mesma
    tela. Restricao de uma superficie aplicada onde ela nao vale."""
    corpo = _corpo_de_exemplo()
    faltando = [certo for certo, _ in _NOSSAS_PALAVRAS if certo not in corpo]
    assert not faltando, f"sumiram do comentario (nosso texto): {faltando}"
    sobrando = [errado for _, errado in _NOSSAS_PALAVRAS if errado in corpo]
    assert not sobrando, f"forma sem acento no texto do cliente: {sobrando}"


# ------------------------------------------- e o bot nao empilha

def test_tem_marca_invisivel_para_atualizar():
    """Bot que deixa doze comentarios num PR e' bot que o time desliga."""
    corpo = comentario.monta(_org(), {}, {})
    assert corpo.startswith(comentario.MARCA)
    assert comentario.MARCA.startswith("<!--"), "a marca apareceria renderizada"


def test_corta_no_teto_do_github_e_DIZ_que_cortou():
    """🚫 Truncar em silencio le como parecer completo -- e a primeira coisa a
    sumir e' a lista de suspeitas NAO TESTADAS, entao o autor concluiria que o
    Veredito examinou tudo."""
    corpo, cortou = comentario.corta("x" * 200, 100)
    assert cortou and len(corpo) <= 100
    assert "truncado" in corpo.lower()


def test_nao_estoura_o_teto_com_o_rodape():
    """O rodape entra DEPOIS do corte: cortar no teto exato estouraria, e o erro
    so' apareceria contra a API, num PR de verdade."""
    muitos = [_v(f"a{i}", motivo="m" * 900) for i in range(200)]
    corpo = comentario.monta(_org(descartados=muitos),
                             {f"a{i}": _a(f"a{i}") for i in range(200)}, {})
    assert len(corpo) <= comentario.TETO


# ------------------------------------------- 🚨 o caminho e' fato da rodada

def test_local_vem_do_CARIMBO_e_nao_da_worktree_de_agora(monkeypatch):
    """🚨 O bug que apareceu montando esta saida, e que so' ela expoe.

    `_local` normalizava o caminho na hora de FORMATAR, contra a worktree que
    estivesse montada. Re-renderizando o parecer do `pallets/flask` com o
    desafio montado, `tests/conftest.py:9` virou `app/api/tests/conftest.py:9`
    -- um arquivo que NAO EXISTE no repo do autor.

    No terminal isso era feio. Num comentario de PR e' mandar uma pessoa de
    verdade procurar arquivo em outro projeto.

    ⚠️ O carimbo aqui e' DIFERENTE do cru de proposito. A primeira versao deste
    teste punha os dois iguais, e com isso ele passava mesmo com o carimbo
    ignorado -- as duas saidas coincidiam e nada distinguia os caminhos. O caso
    real e' justamente o desencontro: `normaliza_local` existe porque o promotor
    escreve a raiz errada, entao o carimbo quase sempre difere do cru.
    """
    def worktree_de_outro_projeto(bruto):
        return "app/api/" + bruto
    monkeypatch.setattr(f, "normaliza_local", worktree_de_outro_projeto)

    a = {"id": "a1",
         "local": "routers/shares.py:31",                       # o que a lente disse
         "local_normalizado": "app/routers/shares.py:31",       # o que a RODADA achou
         "categoria": "correcao"}
    assert juiz._local(a) == "app/routers/shares.py:31", (
        "o caminho nao veio do carimbo da rodada")
    assert "app/api/" not in juiz._local(a), (
        "o caminho foi reescrito contra a arvore de outro projeto")


def test_sem_carimbo_devolve_o_CRU_em_vez_de_adivinhar(monkeypatch):
    """Rodada gravada antes de 17/08 nao tem carimbo. Normalizar ali seria
    adivinhar contra outra arvore, que e' exatamente o defeito."""
    monkeypatch.setattr(f, "normaliza_local", lambda b: "app/api/" + b)
    a = {"id": "a1", "local": "tests/conftest.py:9", "categoria": "correcao"}
    assert juiz._local(a) == "tests/conftest.py:9"


def test_carimba_local_grava_na_acusacao(monkeypatch):
    """O carimbo e' posto no ambiente da rodada, uma vez, por quem observou."""
    monkeypatch.setattr(f, "normaliza_local", lambda b: "app/api/" + b)
    a = f.carimba_local({"id": "a1", "local": "tests/conftest.py:9"})
    assert a["local_normalizado"] == "app/api/tests/conftest.py:9"


def test_o_orquestrador_carimba_antes_de_julgar():
    """A trava mecanica: sem a chamada nos dois lacos, nenhuma acusacao sai
    carimbada e o `_local` cai no cru para sempre -- silenciosamente."""
    import inspect

    from veredito import orquestrador
    fonte = inspect.getsource(orquestrador)
    assert fonte.count("ferramentas.carimba_local(a)") == 2, (
        "os dois lacos que julgam (cota e expansao) precisam carimbar")
    assert fonte.count("advogado.julga(a, diff, contexto_arquivos)") == 2


# ------------------------------------------- e o que a rodada gravou

def test_do_disco_monta_sem_gastar_api(tmp_path, monkeypatch):
    """Mesma disciplina do juiz: ajustar o formato trinta vezes le so' o disco."""
    monkeypatch.setattr(cfg, "RODADA", tmp_path)
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "artefatos")
    (tmp_path / "veredictos.json").write_text(json.dumps(
        [{"id": "a1", "veredito": "REFUTADO", "severidade": "BAIXA",
          "motivo": "nao se sustenta", "ferramentas_ok": 2}]), encoding="utf-8")
    (tmp_path / "acusacoes.json").write_text(json.dumps([_a("a1")]), encoding="utf-8")

    corpo = comentario.do_disco({"head": "abc1234", "rodada": "20260817T1410"})
    assert "nao se sustenta" in corpo
    assert "abc1234" in corpo and "20260817T1410" in corpo
