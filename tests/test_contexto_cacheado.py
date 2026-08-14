"""O bloco dos arquivos do PR, que entra no prefixo cacheado.

Ele existe por uma medicao de 14/08: memoizar `read_file` economiza 0,15s de
disco e ZERO dolar, porque o conteudo entra no contexto do mesmo jeito. Cada
acusacao e' uma conversa separada, entao nada e' reaproveitado entre elas -- a
unica coisa que atravessa e' o prefixo cacheado.

🚨 O que se trava aqui e' sobretudo o DETERMINISMO. Prefixo que varia um byte
nao cacheia, todas as N acusacoes pagam preco cheio, e nada falha: o parecer sai
igual, so' que caro. Falha silenciosa que so' aparece na fatura.
"""

from pathlib import Path

import pytest

from veredito import advogado as adv
from veredito import config as cfg
from veredito import ferramentas as f

DIFF = """\
diff --git a/app/b.py b/app/b.py
index 111..222 100644
--- a/app/b.py
+++ b/app/b.py
@@ -1 +1 @@
-x
+y
diff --git a/app/a.py b/app/a.py
index 333..444 100644
--- a/app/a.py
+++ b/app/a.py
@@ -1 +1 @@
-w
+z
"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Worktree head de mentira: contexto_dos_arquivos so' le disco."""
    raiz = tmp_path / "head"
    (raiz / "app").mkdir(parents=True)
    (raiz / "app" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (raiz / "app" / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    # `_worktree_de` nao e' so' um caminho: ela roda `commit_head()` e
    # `git worktree add`, e apagaria estes arquivos. Trocada pela raiz de
    # mentira -- o que se testa aqui e' a montagem do bloco, nao o git.
    monkeypatch.setattr(f, "_worktree_de", lambda lado: raiz)
    monkeypatch.setattr(cfg, "CONTEXTO_ARQUIVOS", True)
    monkeypatch.setattr(cfg, "CONTEXTO_MAX_CHARS", 40000)
    return raiz


# ------------------------------------------------------------- determinismo

def test_o_bloco_e_identico_a_cada_montagem(repo):
    """A disciplina no 4 do CLAUDE.md: cache_read zero na 1a acusacao e' sinal
    de algo variando no prefixo. Aqui isso e' travado antes de custar rodada."""
    assert adv.contexto_dos_arquivos(DIFF) == adv.contexto_dos_arquivos(DIFF)


def test_a_ordem_dos_arquivos_nao_segue_a_ordem_do_diff(repo):
    """`arquivos_do_diff` devolve um SET, e ordem de set varia entre processos.

    Sem o `sorted`, duas rodadas montariam o mesmo conteudo em ordem diferente
    -- prefixo diferente, cache frio, e ninguem perceberia porque o texto
    "parece" igual ao ler.
    """
    bloco = adv.contexto_dos_arquivos(DIFF)
    # o diff cita b.py primeiro; o bloco tem que trazer a.py antes
    assert bloco.index("### app/a.py") < bloco.index("### app/b.py")


# ------------------------------------------------- conteudo e a promessa dele

def test_traz_o_mesmo_que_read_file_devolveria(repo):
    """O cabecalho manda o advogado NAO chamar read_file para estes arquivos.

    Isso so' pode ser dito se o bloco entrega a mesma coisa -- senao a economia
    de uma volta custaria uma observacao, que e' um pessimo negocio neste
    produto.
    """
    f._abre_chamada()
    esperado = f._read_file("app/a.py", raiz=repo)
    assert esperado in adv.contexto_dos_arquivos(DIFF)


def test_avisa_para_nao_reler(repo):
    assert "NAO chame `read_file`" in adv.contexto_dos_arquivos(DIFF)


def test_arquivo_que_nao_abre_vai_para_a_lista_de_fora(repo):
    """Arquivo do diff que sumiu do head (apagado pelo PR, por exemplo).

    Nao pode derrubar a montagem, e NAO pode sumir calado: se o advogado nao
    souber que ele existe, deixa de investigar.
    """
    diff = DIFF + (
        "diff --git a/app/sumiu.py b/app/sumiu.py\n"
        "--- a/app/sumiu.py\n+++ b/app/sumiu.py\n@@ -1 +1 @@\n-a\n+b\n")
    bloco = adv.contexto_dos_arquivos(diff)
    assert "sumiu.py" in bloco and "Fora deste bloco" in bloco
    assert "### app/a.py" in bloco, "um arquivo ilegivel nao pode levar os outros"


def test_o_teto_corta_e_diz_o_que_ficou_de_fora(repo, monkeypatch):
    """O bloco e' lido por TODAS as acusacoes: arquivo que ninguem ia abrir
    custa 10% a toa. O teto existe, e o que sobra tem que ser anunciado."""
    monkeypatch.setattr(cfg, "CONTEXTO_MAX_CHARS", 40)
    bloco = adv.contexto_dos_arquivos(DIFF)
    assert "Fora deste bloco" in bloco
    assert "fora do teto" in bloco


def test_desligado_devolve_vazio(repo, monkeypatch):
    """A escotilha. Vazio faz `julga` voltar ao comportamento anterior, com o
    advogado lendo por ferramenta -- entao desligar nunca quebra a rodada."""
    monkeypatch.setattr(cfg, "CONTEXTO_ARQUIVOS", False)
    assert adv.contexto_dos_arquivos(DIFF) == ""


def test_diff_sem_arquivo_nao_inventa_bloco(repo):
    assert adv.contexto_dos_arquivos("diff vazio, sem cabecalho git") == ""


# ------------------------------------------------ nao suja o estado das tools

def test_montar_o_bloco_nao_deixa_marca_de_falha_pendurada(repo):
    """🚨 `contexto_dos_arquivos` chama `_read_file` FORA de uma ferramenta.

    Se um arquivo do diff nao abrir, `_marca_falha` fica setado. A primeira
    ferramenta de verdade da rodada chamaria `_fecha_chamada` e herdaria essa
    marca -- uma leitura boa contada como falha, alimentando a R3b com erro que
    nao houve. Inconclusivo inflado por contabilidade, nao por observacao.
    """
    diff = DIFF + (
        "diff --git a/app/sumiu.py b/app/sumiu.py\n"
        "--- a/app/sumiu.py\n+++ b/app/sumiu.py\n@@ -1 +1 @@\n-a\n+b\n")
    adv.contexto_dos_arquivos(diff)
    assert not f.falhou_a_chamada(), "marca de falha vazou para a proxima chamada"
