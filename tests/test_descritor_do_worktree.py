"""De onde o projeto revisado se descreve -- e por que e' do BASE.

🚨 O ACHADO, 18/08, tentando montar a demo da Action contra a bancada.

`revisa_pr.py` monta o alvo com `git init` + `fetch` dos dois commits. O clone
NUNCA tem working tree -- so' os worktrees `base/` e `head/` tem arquivos.
Conferido: `.repos/pallets_flask/` contem exatamente um item, `.git`.

Entao `<clone>/veredito.yml`, que era onde o `projeto.caminho` procurava, nao
existe em repositorio NENHUM do mundo. Pela porta da frente, todo PR caia no
caminho so'-leitura -- inclusive um projeto que se descreve por inteiro, como a
bancada. Metade do produto (a prova ponta a ponta, que 14-15/08 construiram
tirando cinco chumbados do codigo) ficava desligada, em silencio.

⚠️ E a guarda que deveria avisar era

    tem_yml = (info["repo_local"] / "veredito.yml").is_file()

no proprio `revisa_pr.py`: uma condicao que NAO PODE ser verdadeira. Ela
imprimia "sem veredito.yml no repositorio" em toda rodada, e ninguem estranhou
porque o primeiro alvo real -- `pallets/flask` -- de fato nao tem um. Mais uma
guarda condicionada ao sinal que ela deveria vigiar.

🚫 E O LADO IMPORTA. O descritor e' configuracao EXECUTAVEL: `preparar` e' lista
de argumentos que NOS rodamos (`subida.py`), e `app.api` diz para onde mandamos
chamada autenticada. Lido do HEAD, qualquer pessoa que abre um PR escolhe o que
a nossa CI executa e para onde vao as credenciais das contas de teste. O base e'
o codigo ja revisado e mesclado.
"""
import pathlib

import pytest

from veredito import projeto


@pytest.fixture
def alvo(tmp_path):
    """Um clone sem working tree e os dois worktrees, como o revisa_pr monta."""
    clone = tmp_path / ".repos" / "dono_repo"
    (clone / ".git").mkdir(parents=True)
    wt = tmp_path / ".repos" / "wt_dono_repo"
    for lado in ("base", "head"):
        (wt / lado).mkdir(parents=True)
    return clone, wt


def _descreve(raiz: pathlib.Path, api: str) -> None:
    (raiz / "veredito.yml").write_text(
        f"versao: 1\napp:\n  api: {api}\n", encoding="utf-8")


# ------------------------------------------- a guarda, vista falhando

def test_acha_o_descritor_no_worktree_do_base(alvo):
    """O clone nao tem arquivo nenhum: se procurar so' nele, nunca acha."""
    clone, wt = alvo
    _descreve(wt / "base", "http://127.0.0.1:8100")

    achado = projeto.caminho(clone, no_worktree=wt / "base")
    assert achado is not None, (
        "o projeto se descreve e o descritor nao foi encontrado -- a rodada "
        "cairia no caminho so'-leitura com as ferramentas todas disponiveis")
    assert projeto.carrega(achado)["app"]["api"] == "http://127.0.0.1:8100"


def test_sem_o_worktree_nao_acha_NADA_no_clone(alvo):
    """O controle: e' isto que acontecia antes, e explica o sintoma."""
    clone, wt = alvo
    _descreve(wt / "base", "http://127.0.0.1:8100")
    assert projeto.caminho(clone) is None, (
        "o clone tem working tree? entao a premissa do conserto mudou")


# ------------------------------------------- 🚫 e o head NAO manda

def test_o_head_NAO_pode_descrever_o_projeto(alvo):
    """🚨 A trava de seguranca, e e' a razao de o lado ser escolhido e nao obvio.

    `preparar` e' lista de argumentos que NOS executamos, e `app.api` diz para
    onde mandamos chamada autenticada com as contas do seed. Se o descritor
    viesse do head, quem abre um PR escolhe o que a nossa CI roda.
    """
    clone, wt = alvo
    _descreve(wt / "head", "http://servidor-do-atacante:9999")

    achado = projeto.caminho(clone, no_worktree=wt / "base")
    assert achado is None, (
        "o descritor do HEAD foi aceito -- um PR de terceiro passa a escolher "
        "o que a nossa CI executa e para onde vao as credenciais")


def test_o_base_ganha_quando_os_dois_existem(alvo):
    """PR que MODIFICA o veredito.yml nao muda como ele proprio e' revisado."""
    clone, wt = alvo
    _descreve(wt / "base", "http://127.0.0.1:8100")
    _descreve(wt / "head", "http://servidor-do-atacante:9999")

    achado = projeto.caminho(clone, no_worktree=wt / "base")
    assert projeto.carrega(achado)["app"]["api"] == "http://127.0.0.1:8100"


# ------------------------------------------- e o config amarra os dois

def test_config_resolve_descritor_e_compose_na_MESMA_raiz():
    """Um aponta para o outro: `app.compose` e' relativo a raiz do descritor.

    Resolver os dois em lugares diferentes e' a mesma classe da chave da API em
    dois lugares -- divergem em silencio, e o sintoma aparece longe da causa.
    """
    import ast
    import inspect

    from veredito import config as cfg
    fonte = inspect.getsource(cfg)
    atribs = {t.id: ast.unparse(n.value) for n in ast.walk(ast.parse(fonte))
              if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name)}
    assert atribs["COMPOSE"].startswith("RAIZ_DO_PROJETO"), (
        f"COMPOSE saiu da raiz do descritor: {atribs['COMPOSE']}")
    assert "PROJETO_YML" in atribs and "no_worktree=RAIZ_DO_PROJETO" in atribs["PROJETO_YML"]
    # A raiz sai do worktree do BASE -- segue a cadeia em vez de procurar a
    # palavra na linha errada, que foi o primeiro erro deste teste.
    assert "_wt_base" in atribs["RAIZ_DO_PROJETO"], (
        f"a raiz do projeto nao sai do worktree: {atribs['RAIZ_DO_PROJETO']}")
    assert atribs["_wt_base"] == "WORKTREES / 'base'", (
        f"o lado mudou, e o lado e' a trava de seguranca: {atribs['_wt_base']}")


def test_revisa_pr_confere_o_worktree_e_nao_o_clone():
    """A guarda que nao podia ser verdadeira, agora podendo."""
    import inspect
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import revisa_pr

    fonte = inspect.getsource(revisa_pr)
    assert 'info["repo_local"] / "veredito.yml"' not in fonte, (
        "voltou a conferir o descritor no clone, que nunca tem working tree")
    assert 'info["worktrees"] / "base" / "veredito.yml"' in fonte


def test_o_compose_roda_na_raiz_do_descritor_e_nao_no_clone():
    """`--project-directory` resolve `build: .` e volume relativo do compose.

    Apontado para o clone -- que nao tem working tree -- nao ha contexto de
    build nem caminho relativo para resolver. Sao oito chamadas em tres modulos,
    e uma sobrando ja quebraria a rodada num alvo montado por `revisa_pr.py`.
    """
    import re

    raiz = pathlib.Path(__file__).resolve().parents[1] / "veredito"
    sobraram = []
    for arq in ("contencao_app.py", "ferramentas.py", "subida.py"):
        fonte = (raiz / arq).read_text(encoding="utf-8")
        for m in re.finditer(r'"--project-directory",\s*str\(cfg\.(\w+)\)', fonte):
            if m.group(1) != "RAIZ_DO_PROJETO":
                sobraram.append(f"{arq}: cfg.{m.group(1)}")
    assert not sobraram, (
        "compose apontado para uma raiz que pode nao ter arquivos: "
        + ", ".join(sobraram))
