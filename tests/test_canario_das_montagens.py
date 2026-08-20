"""O canario do bind-mount: as montagens declaradas POUSAM no container?

🚨 O FURO. `_montagens` produz os `-v` e ninguem conferia que eles pousam. Com
o mapeamento errado o pytest importa o codigo ASSADO NA IMAGEM, os dois lados
dao o mesmo exit code, e `_classifica` le isso como "nao falhou no head" ->
REFUTADO. Absolvicao falsa e MUDA, na unica ferramenta que assina PROVADO.

⚠️ E o arquivo de teste NAO servia de canario -- e' por isso que o furo
sobreviveu a todo o conserto feito em volta dele. Ele e' gravado no worktree e
roda, entao a montagem de TESTES esta viva e `rodou_base`/`rodou_head` ficam
True. A montagem que decide o veredito e' a do CODIGO, e nenhuma sonda a
exercitava. O `test_o_arquivo_de_teste_nao_denuncia_a_montagem_morta` prende
exatamente essa diferenca.

🚨 O dublê do container HONRA os `-v` de verdade -- ele le a montagem do proprio
comando e resolve o destino como o docker resolveria. Nao e' dublê de string:
se fosse, a violacao injetada seria "eu mudei o texto que o dublê devolve", e a
trava mediria a si mesma. Aqui a montagem errada faz o arquivo sumir pelo MESMO
motivo que sumiria no container.
"""
import pathlib
import subprocess

import pytest

from veredito import config as cfg
from veredito import ferramentas as f


# --------------------------------------------------------------- o dublê

def _container_que_honra_os_v(cmd, **kw):
    """Simula `compose run -v origem:destino ... python -c <leitor> alvos...`.

    Le os `-v` do comando, resolve cada alvo pelo mapa, e devolve o conteudo
    real do disco -- exatamente o que o docker faria.
    """
    mapa: dict[str, pathlib.Path] = {}
    i = 0
    while i < len(cmd):
        if cmd[i] == "-v" and i + 1 < len(cmd):
            origem, destino = cmd[i + 1].rsplit(":", 1)
            mapa[destino.rstrip("/")] = pathlib.Path(origem)
            i += 2
        else:
            i += 1

    alvos = cmd[cmd.index("-c") + 2:]
    linhas = []
    for p in alvos:
        achou = "AUSENTE"
        for destino, origem in mapa.items():
            if p == destino or p.startswith(destino + "/"):
                real = origem / p[len(destino):].lstrip("/")
                if real.is_file():
                    achou = real.read_text(encoding="utf-8").strip()
                break
        linhas.append(f"{p} {achou}")
    return subprocess.CompletedProcess(cmd, 0, "\n".join(linhas) + "\n", "")


@pytest.fixture(autouse=True)
def _sem_memo():
    """O memo e' por rodada; entre testes ele mentiria."""
    f._canario_memo.clear()
    yield
    f._canario_memo.clear()


@pytest.fixture
def projeto(monkeypatch, tmp_path):
    """Worktree com codigo e testes, e as montagens declaradas certas."""
    wt = tmp_path / "head"
    (wt / "app" / "codigo").mkdir(parents=True)
    (wt / "app" / "tests").mkdir(parents=True)
    # ⚠️ Arquivo de verdade, e nao so' diretorio: a sonda `read_file` do pre-voo
    # procura um alvo REAL na worktree, e sem ele ela reprova. Com a worktree
    # so' de pastas, `autoteste()["ok"]` saia False por causa do `read_file` --
    # e a trava do canario passava medindo a falha do vizinho.
    # >80 bytes de proposito: a sonda ignora arquivo minusculo (`st_size > 80`).
    (wt / "app" / "codigo" / "modulo.py").write_text(
        "def soma(a, b):\n"
        "    # conteudo suficiente para a sonda de leitura escolher este alvo\n"
        "    return a + b\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", True)
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS",
                        [["app/codigo", "/srv/app"], ["app/tests", "/srv/tests"]])
    monkeypatch.setattr(cfg, "CODIGO_TRABALHO", "/srv")
    monkeypatch.setattr(cfg, "COMPOSE", tmp_path / "docker-compose.yml")
    monkeypatch.setattr(cfg, "RAIZ_DO_APP", tmp_path)
    monkeypatch.setattr(f, "_worktree_de", lambda lado: wt)
    monkeypatch.setattr(subprocess, "run", _container_que_honra_os_v)
    return wt


# ------------------------------------------------- a guarda, VISTA FALHANDO

def test_canario_verde_quando_as_montagens_pousam(projeto):
    r = f._canario_das_montagens("head")
    assert r["aplica"] is True
    assert r["ok"] is True, r["detalhe"]
    assert r["conferidas"] == 2
    assert r["mortas"] == []


def test_montagem_que_nao_pousa_e_PEGA(projeto, monkeypatch):
    """🚨 A violacao injetada: o `-v` vai para outro destino.

    E' o bug historico -- `codigo.montagens` declara um destino e o `-v` real
    aponta para outro lugar. O canario tem que ficar VERMELHO.
    """
    real = f._montagens

    def _montagens_tortas(worktree):
        # troca o destino do codigo, mantendo o dos testes -- que e' exatamente
        # a assimetria perigosa: o teste roda, o codigo vem da imagem.
        fora = real(worktree)
        return [x.replace(":/srv/app", ":/lugar/nenhum") for x in fora]

    monkeypatch.setattr(f, "_montagens", _montagens_tortas)
    r = f._canario_das_montagens("head")
    assert r["ok"] is False
    assert any("app/codigo" in m for m in r["mortas"]), r["mortas"]
    assert "/srv/app" in r["detalhe"] or "app/codigo" in r["detalhe"]


def test_o_arquivo_de_teste_nao_denuncia_a_montagem_morta(projeto, monkeypatch):
    """🚨 A trava que explica por que o furo durou tanto.

    Com a montagem do CODIGO morta e a dos TESTES viva, o pytest roda (o
    arquivo de teste chega la'), `rodou_*` fica True, o `destino_do_teste` do
    pre-voo fica verde -- e nada acusa. So' o canario acusa.
    """
    real = f._montagens
    monkeypatch.setattr(f, "_montagens", lambda wt: [
        x.replace(":/srv/app", ":/lugar/nenhum") for x in real(wt)])

    r = f._canario_das_montagens("head")

    # a montagem de TESTES continua viva -- e' isso que mantinha tudo verde
    assert "app/tests" not in " ".join(r["mortas"])
    # e mesmo assim o canario reprova, por causa da do codigo
    assert r["ok"] is False
    assert r["conferidas"] == 1


def test_origem_que_sumiu_entra_como_morta_e_nao_e_pulada(projeto, monkeypatch):
    """🚨 O furo que estava DENTRO do canario.

    `_montagens` pula origem inexistente de proposito. Se o canario pulasse
    igual, a montagem que nunca chegou a ser montada seria invisivel para a
    guarda que existe para vigia-la -- o padrao de bug dentro da guarda escrita
    contra ele.
    """
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS",
                        [["app/codigo", "/srv/app"],
                         ["app/renomeado", "/srv/outro"]])
    r = f._canario_das_montagens("head")
    assert r["ok"] is False
    assert any("app/renomeado" in m for m in r["mortas"]), r["mortas"]


# ------------------------------------------- a guarda consegue ficar QUIETA

def test_sem_layout_declarado_nao_se_aplica_e_nao_alarma(monkeypatch, tmp_path):
    """NAO SE APLICA nao e' NAO MEDIDO -- a licao do alarme do banco, 17/08.

    PR de terceiro nao declara `codigo`. Alarme que dispara em todos eles
    ensina o leitor a pular justamente esta linha.
    """
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", False)
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS", [])
    r = f._canario_das_montagens("head")
    assert r["aplica"] is False
    assert r["ok"] is True          # nao reprova quem nao tinha o que pousar
    assert r["mortas"] == []


def test_nao_exigido_no_pre_voo_quando_nao_ha_prova_diferencial():
    """A exigencia entra so' com `TEM_PROVA_DIFERENCIAL` -- senao abortaria
    toda revisao de PR de terceiro."""
    assert "montagens_vivas" in f.ESSENCIAIS_COM_PROVA
    assert "montagens_vivas" not in f.ESSENCIAIS


def test_docker_caido_NAO_aborta_a_rodada_mas_e_dito(projeto, monkeypatch):
    """🚨 A conflacao que eu mesmo cometi ao ligar o canario no pre-voo.

    O canario separa "quebrou" de "nao pousou"; a primeira versao do pre-voo
    jogava a distincao fora, e um docker fora do ar abortava ate' a rodada de um
    PR que so' precisa de leitura -- quebrando o
    `test_pre_voo_sem_app_NAO_exige_app_serve_o_head`.

    Docker caido nao e' o caso perigoso: o `_roda_pytest` falha alto e a R3
    devolve INCONCLUSIVO. O perigoso e' docker FUNCIONANDO com montagem morta.

    🚫 E nao pode virar verde MUDO: quem nao conseguiu olhar diz que nao olhou.
    """
    monkeypatch.setattr(f, "_read_file", lambda c: "1 | conteudo")
    monkeypatch.setattr(f, "_grep", lambda *a, **k: "arquivo.py:1: casou")
    monkeypatch.setattr(cfg, "TEM_APP", False)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw:
                        subprocess.CompletedProcess(cmd, 1, "", "Cannot connect to the Docker daemon"))

    r = f.autoteste(sondar_app=True)
    sonda = r["ferramentas"]["montagens_vivas"]
    assert sonda["ok"] is True, "docker caido nao pode abortar rodada de leitura"
    assert "NAO CONFERIDO" in sonda["detalhe"], "degradacao MUDA e' pior que a doenca"


def test_montagem_morta_com_docker_VIVO_aborta_a_rodada(projeto, monkeypatch):
    """O contraste: aqui o docker respondeu e a montagem nao pousou. Fatal.

    E' o unico caso em que o pre-voo deve derrubar a rodada -- o pytest rodaria,
    daria exit igual nos dois lados, e a prova absolveria em silencio.
    """
    monkeypatch.setattr(f, "_read_file", lambda c: "1 | conteudo")
    monkeypatch.setattr(f, "_grep", lambda *a, **k: "arquivo.py:1: casou")
    monkeypatch.setattr(cfg, "TEM_APP", False)
    real = f._montagens
    monkeypatch.setattr(f, "_montagens", lambda wt: [
        x.replace(":/srv/app", ":/lugar/nenhum") for x in real(wt)])

    r = f.autoteste(sondar_app=True)

    # 🚨 Prender a CAUSA, nao so' o desfecho. Sem estas duas linhas o
    # `r["ok"] is False` passava mesmo com o canario fora das exigidas -- quem
    # derrubava era a sonda `read_file` na worktree de mentira. Trava que acusa
    # a coisa errada nao vale mais que trava que nao acusa nada.
    for essencial in f.ESSENCIAIS:
        assert r["ferramentas"][essencial]["ok"], (
            f"{essencial} caiu -- a trava mediria a falha do vizinho")
    assert r["ferramentas"]["montagens_vivas"]["ok"] is False
    assert r["ok"] is False, "montagem morta com docker vivo tem que abortar"


# ------------------------------------------- quebrou != nao pousou (a R3)

def test_docker_fora_do_ar_e_ERRO_e_nao_culpa_o_veredito_yml(projeto, monkeypatch):
    """A distincao que a R3 comprou em 17/08.

    Se o container nem rodou, nao houve medicao -- e' infraestrutura, nao
    montagem morta. Culpar o `codigo.montagens` do cliente por um docker caido
    manda consertar a coisa errada.
    """
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw:
                        subprocess.CompletedProcess(cmd, 1, "", "Cannot connect to the Docker daemon"))
    r = f._canario_das_montagens("head")
    assert r["ok"] is False
    assert r.get("erro"), "falha de infra tem que preencher `erro`"
    assert "infraestrutura" in r["detalhe"]
    assert "montagens" not in r["detalhe"].replace("`codigo.montagens` do projeto", "")


def test_timeout_e_erro_e_nao_montagem_morta(projeto, monkeypatch):
    def _estoura(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)
    monkeypatch.setattr(subprocess, "run", _estoura)
    r = f._canario_das_montagens("head")
    assert r["ok"] is False
    assert "timeout" in r["erro"]
    assert r["mortas"] == []


# --------------------------------------------------- higiene e integracao

def test_o_canario_nao_deixa_lixo_no_worktree(projeto):
    f._canario_das_montagens("head")
    sobrou = list(projeto.rglob(f._NOME_DO_CANARIO))
    assert sobrou == [], f"canario deixou arquivo no worktree: {sobrou}"


def test_o_canario_limpa_mesmo_quando_o_docker_falha(projeto, monkeypatch):
    def _estoura(cmd, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(subprocess, "run", _estoura)
    f._canario_das_montagens("head")
    assert list(projeto.rglob(f._NOME_DO_CANARIO)) == []


def test_memoiza_para_custar_um_container_por_lado(projeto, monkeypatch):
    chamadas = []
    real = _container_que_honra_os_v
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: (chamadas.append(1), real(cmd, **kw))[1])
    for _ in range(5):
        f._canario_das_montagens("head")
    assert len(chamadas) == 1, "o canario tem que ser memoizado por lado"


def test_prova_diferencial_recusa_com_montagem_morta(projeto, monkeypatch, tmp_path):
    """A ponta que importa: montagem morta NAO pode virar REFUTADO.

    `erro` preenchido -> o `finally` poe INCONCLUSIVO, e a R3 do juiz mantem.
    Absolvicao falsa e' o desfecho que o produto existe para impedir.
    """
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "art")
    monkeypatch.setattr(cfg, "CODIGO_TESTES", "tests")
    monkeypatch.setattr(cfg, "CODIGO_TESTES_NO_REPO", "app/tests")
    monkeypatch.setattr(f, "commit_base", lambda: "a" * 40)
    monkeypatch.setattr(f, "commit_head", lambda: "b" * 40)
    monkeypatch.setattr(f, "_garante_worktree", lambda commit, nome: projeto)

    real = f._montagens
    monkeypatch.setattr(f, "_montagens", lambda wt: [
        x.replace(":/srv/app", ":/lugar/nenhum") for x in real(wt)])

    # 🚨 NAO levantar aqui. Levantar faria o `except Exception` do
    # `_prova_diferencial` preencher `erro` e o `finally` poe INCONCLUSIVO --
    # e o teste passaria com o canario ARRANCADO, pelo motivo errado. Foi o que
    # a mutacao 1 mostrou. O desfecho tem que distinguir "recusou pelo canario"
    # de "quebrou por outra coisa qualquer".
    rodou = []
    monkeypatch.setattr(f, "_roda_pytest",
                        lambda *a, **k: (rodou.append(1), (0, "1 passed", True))[1])

    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")

    assert rodou == [], "nao pode gastar container com montagem morta"
    assert art["erro"], "montagem morta tem que preencher `erro`"
    assert "app/codigo" in art["erro"] or "pousa" in art["erro"], art["erro"]
    assert art.get("canario_das_montagens"), "o artefato tem que guardar o canario"
    assert art["estado"] == "INCONCLUSIVO"
    assert art["provado"] is False
    assert art["estado"] != "REFUTADO"


def test_prova_diferencial_segue_normal_com_montagem_viva(projeto, monkeypatch, tmp_path):
    """O contraste que prova que a recusa acima e' do canario e nao do acaso.

    Mesma montagem, agora VIVA: o `_roda_pytest` tem que ser alcancado.
    """
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "art")
    monkeypatch.setattr(cfg, "CODIGO_TESTES", "tests")
    monkeypatch.setattr(cfg, "CODIGO_TESTES_NO_REPO", "app/tests")
    monkeypatch.setattr(f, "commit_base", lambda: "a" * 40)
    monkeypatch.setattr(f, "commit_head", lambda: "b" * 40)
    monkeypatch.setattr(f, "_garante_worktree", lambda commit, nome: projeto)

    rodou = []
    monkeypatch.setattr(f, "_roda_pytest",
                        lambda *a, **k: (rodou.append(1), (0, "1 passed", True))[1])

    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")
    assert rodou, "com montagem viva a prova tem que rodar"
    assert not art.get("canario_das_montagens")
