"""O canario, segunda pergunta: a montagem e' a RAIZ DE IMPORT?

🚨 O VAO QUE ISTO FECHA, e ele estava DECLARADO no docstring do canario desde
19/08 -- escrito como limite conhecido, justamente para nao ser lido como mais
do que era:

    "Ele prova que o `-v` pousa em `/srv/app`; se o codigo da imagem for
     importado de `/code/app`, a montagem esta viva, o canario fica verde, e o
     pytest continua lendo a imagem."

E' o caso (b). A conferencia de ARQUIVO passa: o `-v` pousou, o nonce esta la'.
E mesmo assim o pytest importa `app` de outro lugar, os dois lados voltam
iguais, `_classifica` le "nao falhou no head" e a prova diferencial ABSOLVE.

Mesmo desfecho do caso (a) -- absolvicao falsa e muda -- por um caminho que a
guarda anterior nao alcancava. Guarda que confere o vizinho do que importa.

⚠️ E a assimetria e' de proposito: so' `outra` (importa, mas de fora da
montagem) reprova. `nao_importavel` NAO reprova, porque diretorio de teste, de
dados ou de template nao e' pacote -- cobrar import deles faria a guarda
disparar em projeto correto. Licao 0: guarda que nao consegue ficar quieta
morre de excesso, que da' no mesmo que morrer de falta. O
`test_nao_importavel_NAO_reprova` prende exatamente isso.
"""
import pathlib
import subprocess

import pytest

from veredito import config as cfg
from veredito import ferramentas as f


def _dublê(onde_importa=None):
    """Container que honra os `-v` E resolve imports segundo `onde_importa`.

    `onde_importa` e' `{pacote: caminho}` -- de onde o python DAQUELE container
    importaria cada pacote. `None` no valor significa ImportError.
    """
    mapa_import = onde_importa or {}

    def _roda(cmd, **kw):
        montagens: dict[str, pathlib.Path] = {}
        i = 0
        while i < len(cmd):
            if cmd[i] == "-v" and i + 1 < len(cmd):
                origem, destino = cmd[i + 1].rsplit(":", 1)
                montagens[destino.rstrip("/")] = pathlib.Path(origem)
                i += 2
            else:
                i += 1

        linhas = []
        for a in cmd[cmd.index("-c") + 2:]:
            if a.startswith("P:"):
                pac = a[2:]
                linhas.append(f"IMPORT {pac} {mapa_import.get(pac) or '-'}")
                continue
            achou = "AUSENTE"
            for destino, origem in montagens.items():
                if a == destino or a.startswith(destino + "/"):
                    real = origem / a[len(destino):].lstrip("/")
                    if real.is_file():
                        achou = real.read_text(encoding="utf-8").strip()
                    break
            linhas.append(f"{a} {achou}")
        return subprocess.CompletedProcess(cmd, 0, "\n".join(linhas) + "\n", "")
    return _roda


@pytest.fixture(autouse=True)
def _sem_memo():
    f._canario_memo.clear()
    yield
    f._canario_memo.clear()


@pytest.fixture
def projeto(monkeypatch, tmp_path):
    wt = tmp_path / "head"
    (wt / "app" / "codigo").mkdir(parents=True)
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", True)
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS", [["app/codigo", "/srv/app"]])
    monkeypatch.setattr(cfg, "CODIGO_TRABALHO", "/srv")
    monkeypatch.setattr(cfg, "COMPOSE", tmp_path / "docker-compose.yml")
    monkeypatch.setattr(cfg, "RAIZ_DO_APP", tmp_path)
    monkeypatch.setattr(f, "_worktree_de", lambda lado: wt)
    return wt


# ------------------------------------------------------ derivar o pacote

@pytest.mark.parametrize("trabalho,destino,esperado", [
    ("/code", "/code/app", "app"),            # desafio
    ("/code", "/code/tests", "tests"),        # desafio, o outro
    ("/srv", "/srv/app", "app"),              # bancada
    ("/code", "/code/app/api", "app.api"),    # aninhado
    ("/code", "/code/app/", "app"),           # barra sobrando
])
def test_pacote_derivado_do_trabalho(monkeypatch, trabalho, destino, esperado):
    monkeypatch.setattr(cfg, "CODIGO_TRABALHO", trabalho)
    assert f._pacote_de(destino) == esperado


@pytest.mark.parametrize("trabalho,destino", [
    ("/code", "/outro/lugar"),      # fora do trabalho
    ("", "/code/app"),              # sem trabalho declarado
    ("/code", "/code/my-lib"),      # nao e' identificador Python
    ("/code", "/code/2fa"),         # comeca com digito
    ("/code", "/code"),             # o proprio trabalho, sem sufixo
])
def test_pacote_nao_derivavel_devolve_None(monkeypatch, trabalho, destino):
    """Derivar errado e' pior que nao derivar: acusaria sombra onde nao ha."""
    monkeypatch.setattr(cfg, "CODIGO_TRABALHO", trabalho)
    assert f._pacote_de(destino) is None


def test_onde_importou_le_a_linha_do_container():
    saida = "x AUSENTE\nIMPORT app /code/app/__init__.py\nIMPORT tests -\n"
    assert f._onde_importou(saida, "app") == "/code/app/__init__.py"
    assert f._onde_importou(saida, "tests") is None
    assert f._onde_importou(saida, "nao_citado") is None


# --------------------------------------- 🚨 o caso (b), VISTO REPROVANDO

def test_montagem_VIVA_mas_SOMBRADA_pela_imagem_reprova(projeto, monkeypatch):
    """🚨 A violacao injetada, e ela e' invisivel para a conferencia de arquivo.

    O `-v` pousa em `/srv/app` (o nonce chega la'), mas o python importa `app`
    de `/code/app`, assado na imagem. Antes de 19/08 isto saia VERDE.
    """
    monkeypatch.setattr(subprocess, "run",
                        _dublê({"app": "/code/app/__init__.py"}))
    r = f._canario_das_montagens("head")

    assert r["conferidas"] == 1, "o arquivo POUSOU -- e' esse o ponto"
    assert r["mortas"] == [], "nao e' montagem morta; e' montagem sombreada"
    assert r["ok"] is False
    assert r["sombreadas"], r
    assert "/code/app/__init__.py" in r["sombreadas"][0]
    assert "SOMBRADA" in r["detalhe"]


def test_import_de_dentro_da_montagem_passa(projeto, monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        _dublê({"app": "/srv/app/__init__.py"}))
    r = f._canario_das_montagens("head")
    assert r["ok"] is True, r["detalhe"]
    assert r["sombreadas"] == []
    assert "raiz de import" in r["detalhe"]


def test_import_do_proprio_diretorio_montado_passa(projeto, monkeypatch):
    """Pacote-namespace: `__path__` e' o diretorio, sem `__init__.py`."""
    monkeypatch.setattr(subprocess, "run", _dublê({"app": "/srv/app"}))
    assert f._canario_das_montagens("head")["ok"] is True


# ------------------------------------------ a guarda consegue ficar QUIETA

def test_nao_importavel_NAO_reprova(projeto, monkeypatch):
    """🚨 Licao 0. Diretorio de teste/dados nao e' pacote, e cobrar import dele
    faria a guarda disparar em projeto correto."""
    monkeypatch.setattr(subprocess, "run", _dublê({"app": None}))
    r = f._canario_das_montagens("head")
    assert r["ok"] is True, r["detalhe"]
    assert r["sombreadas"] == []


def test_sem_pacote_derivavel_confere_so_o_arquivo(projeto, monkeypatch):
    """Destino fora do `trabalho`: nao da' para perguntar sobre import, entao
    nao se pergunta -- e nao se reprova por isso."""
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS", [["app/codigo", "/fora/daqui"]])
    monkeypatch.setattr(subprocess, "run", _dublê({}))
    r = f._canario_das_montagens("head")
    assert r["ok"] is True
    assert r["conferidas"] == 1


def test_dublê_antigo_sem_linha_IMPORT_nao_reprova(projeto, monkeypatch):
    """Compatibilidade do protocolo: container que so' emite linhas de arquivo
    continua valendo. Se isto quebrar, as 15 travas do arquivo irmao quebram
    junto -- e por motivo que nao e' o defeito que elas alegam pegar."""
    def _so_arquivo(cmd, **kw):
        saida = "\n".join(f"{a} nonce-errado" for a in cmd[cmd.index("-c") + 2:]
                          if not a.startswith("P:"))
        return subprocess.CompletedProcess(cmd, 0, saida, "")
    monkeypatch.setattr(subprocess, "run", _so_arquivo)
    r = f._canario_das_montagens("head")
    # o nonce nao bate -> montagem morta; o que importa e' que a AUSENCIA de
    # linha IMPORT nao adiciona uma segunda acusacao por cima.
    assert r["sombreadas"] == []


# ------------------------------------------------------------- integracao

def test_montagem_sombrada_faz_a_prova_diferencial_recusar(projeto, monkeypatch, tmp_path):
    """A ponta que importa: sombra NAO pode virar REFUTADO."""
    (projeto / "app" / "tests").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "art")
    monkeypatch.setattr(cfg, "CODIGO_TESTES", "tests")
    monkeypatch.setattr(cfg, "CODIGO_TESTES_NO_REPO", "app/tests")
    monkeypatch.setattr(f, "commit_base", lambda: "a" * 40)
    monkeypatch.setattr(f, "commit_head", lambda: "b" * 40)
    monkeypatch.setattr(f, "_garante_worktree", lambda commit, nome: projeto)
    monkeypatch.setattr(subprocess, "run",
                        _dublê({"app": "/code/app/__init__.py"}))

    rodou = []
    monkeypatch.setattr(f, "_roda_pytest",
                        lambda *a, **k: (rodou.append(1), (0, "1 passed", True))[1])

    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")
    assert rodou == [], "nao pode gastar container com montagem sombreada"
    assert art["erro"], art
    assert "SOMBRADA" in art["erro"]
    assert art["estado"] == "INCONCLUSIVO"
    assert art["estado"] != "REFUTADO"


def test_docker_caido_NAO_faz_a_prova_recusar_por_montagem(projeto, monkeypatch,
                                                           tmp_path):
    """🚨 A trava que FALTAVA, e a falta dela deixou passar um bug meu.

    Ligar a recusa como `aplica and not ok` -- sem excluir `erro` -- fazia toda
    prova diferencial, com o docker parado, voltar dizendo *"montagem declarada
    que NAO pousa: confira `codigo.montagens` no veredito.yml"*. Ou seja,
    CULPANDO A CONFIG DO CLIENTE por uma queda de infraestrutura nossa.

    Pegou em 19/08 por tres testes `@lento` vermelhos, e nao pela trava --
    porque a trava irma so' exercita o caso em que o canario MEDIU e achou
    montagem morta. "Quebrou" != "nao pousou" e' a distincao que a R3 comprou
    em 17/08; o canario a calcula por dentro, e cada ponto que o consome tem
    que honra-la de novo.

    O desfecho certo com docker fora do ar: a prova SEGUE, o `_roda_pytest`
    falha alto, e a R3 devolve INCONCLUSIVO com a causa verdadeira.
    """
    (projeto / "app" / "tests").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "art")
    monkeypatch.setattr(cfg, "CODIGO_TESTES", "tests")
    monkeypatch.setattr(cfg, "CODIGO_TESTES_NO_REPO", "app/tests")
    monkeypatch.setattr(f, "commit_base", lambda: "a" * 40)
    monkeypatch.setattr(f, "commit_head", lambda: "b" * 40)
    monkeypatch.setattr(f, "_garante_worktree", lambda commit, nome: projeto)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw:
                        subprocess.CompletedProcess(cmd, 1, "", "Cannot connect "
                                                   "to the Docker daemon"))
    rodou = []
    monkeypatch.setattr(f, "_roda_pytest",
                        lambda *a, **k: (rodou.append(1), (0, "1 passed", True))[1])

    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")

    assert rodou, "com o canario sem medir, a prova tem que SEGUIR"
    assert not art.get("canario_das_montagens"), \
        "docker caido nao pode ser registrado como montagem morta"
    assert "montagens" not in (art.get("erro") or ""), art.get("erro")


def test_memo_nao_herda_veredito_de_outra_configuracao(projeto, monkeypatch):
    """🚨 O memo indexado so' por `lado` fazia UMA configuracao contaminar outra.

    Sintoma real, 19/08: tres testes `@lento` vermelhos na suite e VERDES
    isolados -- a assinatura de estado compartilhado. Um teste com montagens
    dubladas gravava "montagem morta" em `head`, e a medicao seguinte, com
    outro layout, lia aquele resultado como se fosse dela.

    ⚠️ E as travas do canario nao viam: a fixture `autouse` limpa o memo entre
    testes, ou seja, higienizava exatamente o estado que estava quebrado.

    A chave passou a ser feita do que o resultado DEPENDE -- as montagens e o
    `trabalho` -- e nao de um proxy delas.
    """
    monkeypatch.setattr(subprocess, "run",
                        _dublê({"app": "/code/app/__init__.py"}))
    ruim = f._canario_das_montagens("head")
    assert ruim["ok"] is False, "preparo: esta configuracao tem que reprovar"

    # mesma `lado`, configuracao DIFERENTE -- nao pode herdar o reprovado acima
    (projeto / "outro").mkdir()
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS", [["outro", "/srv/outro"]])
    monkeypatch.setattr(subprocess, "run", _dublê({}))
    bom = f._canario_das_montagens("head")
    assert bom["ok"] is True, f"herdou o veredito da outra config: {bom}"
