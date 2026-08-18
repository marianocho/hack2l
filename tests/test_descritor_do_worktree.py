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

def _atribuicoes_do_config() -> dict:
    import ast
    import inspect

    from veredito import config as cfg
    fonte = inspect.getsource(cfg)
    return {t.id: ast.unparse(n.value) for n in ast.walk(ast.parse(fonte))
            if isinstance(n, ast.Assign)
            for t in n.targets if isinstance(t, ast.Name)}


def test_sao_DUAS_raizes_descritor_no_base_e_app_no_head():
    """🚨 A separacao, e ela e' o conserto do abort no pre-voo.

    A primeira versao usava UMA raiz para as duas coisas, e a rodada morria com
    "o app no ar NAO serve o head": `subir: true` construia o container da
    arvore do BASE, e a sonda `app_serve_o_head` -- ESSENCIAL quando ha app --
    comparava o diff do PR contra um container do codigo de antes dele.

    A sonda estava certa (custou tres rodadas pagas em 15/08). Quem estava
    errado era a raiz unica. A linha e' entre CONFIGURACAO e CODIGO SOB
    REVISAO.
    """
    a = _atribuicoes_do_config()
    assert "_wt_base" in a["RAIZ_DO_DESCRITOR"], (
        f"o descritor deixou de sair do base: {a['RAIZ_DO_DESCRITOR']}")
    assert a["_wt_base"] == "WORKTREES / 'base'", (
        f"o lado do descritor e' a trava de seguranca: {a['_wt_base']}")
    assert "_wt_head" in a["RAIZ_DO_APP"], (
        f"o app deixou de sair do head: {a['RAIZ_DO_APP']}")
    assert a["_wt_head"] == "WORKTREES / 'head'"
    assert a["RAIZ_DO_DESCRITOR"] != a["RAIZ_DO_APP"], (
        "as duas raizes colapsaram numa so' -- e' exatamente o estado que "
        "abortava a rodada no pre-voo")


def test_o_compose_e_o_descritor_vem_de_lados_DIFERENTES():
    """O NOME vem do descritor (base); o ARQUIVO vem do app (head).

    Nao sao a mesma informacao em dois lugares -- sao um ponteiro e um alvo. O
    descritor diz "o compose se chama X"; o conteudo de X em cada commit e'
    codigo sob revisao, e e' o do head que tem que subir.
    """
    a = _atribuicoes_do_config()
    assert a["COMPOSE"].startswith("RAIZ_DO_APP"), (
        f"o compose do HEAD nao e' o que sobe: {a['COMPOSE']}")
    assert "_app.get('compose')" in a["COMPOSE"], (
        "o nome do arquivo deixou de vir do descritor")
    assert "no_worktree=RAIZ_DO_DESCRITOR" in a["PROJETO_YML"]


def test_os_worktrees_so_valem_quando_o_clone_nao_tem_arvore():
    """⚠️ Sem esta pergunta o modo local quebra de um jeito traicoeiro.

    `--project-directory` batiza o PROJETO do compose. Apontado para o worktree
    num ambiente onde o operador subiu o app a partir do checkout, `docker
    compose exec db` passaria a procurar containers de um projeto chamado
    `head` -- e o erro sairia "no such service", longe da causa.
    """
    from veredito import config as cfg

    a = _atribuicoes_do_config()
    for nome in ("RAIZ_DO_DESCRITOR", "RAIZ_DO_APP"):
        assert "_tem_arvore(DESAFIO)" in a[nome], (
            f"{nome} nao pergunta se o clone tem arvore: {a[nome]}")

    # E a pergunta responde do disco, nao de bandeira declarada.
    assert cfg._tem_arvore(cfg.RAIZ) is True
    import tempfile
    vazio = pathlib.Path(tempfile.mkdtemp())
    (vazio / ".git").mkdir()
    assert cfg._tem_arvore(vazio) is False, (
        "um clone com so' `.git` foi tratado como checkout")


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


def test_o_compose_roda_na_raiz_do_APP_e_nao_no_clone():
    """`--project-directory` resolve `build: .` e volume relativo do compose.

    Apontado para o clone -- que nao tem working tree -- nao ha contexto de
    build nem caminho relativo para resolver. E apontado para o BASE, constroi
    o app do commit errado, que e' o abort do pre-voo.

    Sao oito chamadas em tres modulos, e uma sobrando ja quebraria a rodada num
    alvo montado por `revisa_pr.py` -- "sete de oito" nao e' um estado que
    alguem perceba lendo.
    """
    import re

    raiz = pathlib.Path(__file__).resolve().parents[1] / "veredito"
    sobraram = []
    for arq in ("contencao_app.py", "ferramentas.py", "subida.py"):
        fonte = (raiz / arq).read_text(encoding="utf-8")
        for m in re.finditer(r'"--project-directory",\s*str\(cfg\.(\w+)\)', fonte):
            if m.group(1) != "RAIZ_DO_APP":
                sobraram.append(f"{arq}: cfg.{m.group(1)}")
    assert not sobraram, (
        "compose apontado para uma raiz que nao e' a do app sob revisao: "
        + ", ".join(sobraram))


# ------------------------------------------- 🚨 e os worktrees existem A TEMPO

def test_monta_os_dois_monta_OS_DOIS():
    """Um lado so' nao serve: o descritor sai do base, o app sai do head."""
    from veredito import ferramentas as f

    pedidos = []
    original = f._garante_worktree
    try:
        f._garante_worktree = lambda commit, nome: pedidos.append((commit, nome))
        f.monta_os_dois("shabase", "shahead")
    finally:
        f._garante_worktree = original
    assert pedidos == [("shabase", "base"), ("shahead", "head")], (
        f"nem os dois lados foram montados: {pedidos}")


def test_revisa_pr_monta_os_worktrees_ANTES_de_subir_o_orquestrador(monkeypatch):
    """🚨 A trava do bug que custou o primeiro run da Action, 18/08.

    Os worktrees nasciam sob demanda, ja dentro do laco do advogado. Mas o
    `veredito.yml` e' lido do worktree do BASE e o `config` resolve isso NA
    IMPORTACAO -- entao o subprocesso importava o config antes de qualquer
    worktree existir, e a bancada foi revisada como se nao se descrevesse:

        projeto: (sem veredito.yml -- usando os padroes)

    Sem app, sem prova diferencial, sem contas. O defeito plantado escapou por
    falta de ferramenta num repositorio que declara todas.

    ⚠️ A asserção e' sobre a ORDEM, e nao sobre "monta_os_dois foi chamado":
    chamar depois de subir o orquestrador nao consertaria nada, e um teste que
    so' confere a chamada passaria igual.
    """
    import subprocess
    import sys as _sys

    _sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import revisa_pr
    from veredito import entrada
    from veredito import ferramentas as f

    ordem = []
    monkeypatch.setattr(_sys, "argv", ["revisa_pr.py", "https://github.com/d/r/pull/1"])
    monkeypatch.setattr(entrada, "resolve", lambda url: {
        "repo": "d/r", "numero": 1, "titulo": "t", "adicoes": 1, "remocoes": 0,
        "arquivos": 1, "merge_base": "b" * 40, "head": "h" * 40,
        "base_do_ramo": "b" * 40, "base_deslocou": False,
        "repo_local": pathlib.Path("."), "worktrees": pathlib.Path("."),
    })
    monkeypatch.setattr(entrada, "ambiente", lambda info: {})
    monkeypatch.setattr(f, "monta_os_dois",
                        lambda base, head: ordem.append("worktrees"))
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: ordem.append("orquestrador") or
        subprocess.CompletedProcess(args=[], returncode=0))

    revisa_pr.main()
    assert ordem == ["worktrees", "orquestrador"], (
        f"o orquestrador subiu antes de os worktrees existirem: {ordem}")
