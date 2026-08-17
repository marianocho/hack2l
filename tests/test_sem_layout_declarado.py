"""Projeto que nao declara layout NAO TEM layout -- nunca a arvore do vizinho.

🚨 O caso real, 17/08, na primeira revisao de um PR de terceiro pela porta da
frente. Revisando `pallets/flask`, sem `veredito.yml`, as CINCO provas
diferenciais da rodada morreram com o mesmo erro:

    app/api/tests nao existe em base. Ajuste `codigo.testes_no_repo`...

`app/api/tests` e' a arvore do desafio, e era o valor PADRAO do codigo. O
advogado escreveu os cinco testes antes de descobrir -- gastou as voltas, e a
ferramenta que assina PROVADO nunca chegou a rodar.

⚠️ E o estrago passou do custo: com `erro` preenchido no artefato, a R3 do juiz
converteu em INCONCLUSIVO ate' o veredicto `padroes_02`, que era REFUTADO
obtido por leitura, com o grep funcionando. O parecer saiu 5 de 5 inconclusivos.

E' a quinta instancia do mesmo padrao -- contas, `APP_API_URL`, `-U kb` do
psql, `py -3.12` no `fontes.py`, e este. A troca certa e' sempre a mesma: valor
padrao mantido a mao -> criterio derivado do que o projeto declarou.

🚫 O que este arquivo NAO faz: mexer na R3. A recusa continua preenchendo
`erro`, entao o veredicto continua sendo convertido exatamente como antes. Se
"ferramenta que o projeto nao declarou" deve ou nao contaminar o veredito e'
decisao separada, e o ultimo teste daqui prende o limite para que ela nao
aconteca por acidente.
"""
import pytest

from veredito import config as cfg
from veredito import ferramentas as f


@pytest.fixture
def sem_layout(monkeypatch, tmp_path):
    """O estado de um PR de terceiro: nada declarado."""
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", False)
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS", [])
    monkeypatch.setattr(cfg, "CODIGO_TESTES", "")
    monkeypatch.setattr(cfg, "CODIGO_TESTES_NO_REPO", "")
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)


@pytest.fixture
def com_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "TEM_PROVA_DIFERENCIAL", True)
    monkeypatch.setattr(cfg, "CODIGO_MONTAGENS", [["app", "/srv/app"]])
    monkeypatch.setattr(cfg, "CODIGO_TESTES", "app/tests")
    monkeypatch.setattr(cfg, "CODIGO_TESTES_NO_REPO", "app/tests")
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path)


def _nao_pode_rodar(*a, **k):
    raise AssertionError("chamou o docker sem o projeto ter declarado layout")


# ------------------------------------------- a guarda, vista falhando

def test_prova_diferencial_sem_layout_NAO_ESCREVE_NEM_RODA(sem_layout, monkeypatch):
    """A trava central. Nao basta devolver erro -- nao pode nem tentar.

    Tentar e' o que aconteceu em 17/08: o advogado pagou por cinco testes
    escritos, e um deles poderia ter sido gravado dentro da arvore de um
    repositorio de terceiro se o caminho por acaso existisse la'.
    """
    def nao_pode_git(*a, **k):
        raise AssertionError("resolveu commit sem o projeto ter declarado layout")

    monkeypatch.setattr(f, "commit_base", nao_pode_git)
    monkeypatch.setattr(f, "commit_head", nao_pode_git)
    monkeypatch.setattr(f.subprocess, "run", _nao_pode_rodar)

    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")
    assert art["estado"] == "INCONCLUSIVO" and art["provado"] is False
    # `indisponivel`, nunca `erro` -- a separacao e' o que impede a R3 de
    # converter uma refutacao por leitura. Ver o teste de mesmo nome mais abaixo.
    assert art["erro"] is None
    assert "nao declara" in art["indisponivel"]
    assert "veredito.yml" in art["indisponivel"], "nao diz ao operador como consertar"
    assert "read_file" in art["indisponivel"], (
        "nao diz ao advogado o que fazer em vez disso")


def test_com_layout_declarado_ela_prossegue(com_layout, monkeypatch):
    """O controle. Sem ele a trava acima passaria com a ferramenta quebrada."""
    monkeypatch.setattr(f, "commit_base", lambda: (_ for _ in ()).throw(
        RuntimeError("cheguei ao git")))

    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")
    assert "cheguei ao git" in art["erro"], (
        "recusou mesmo com o layout declarado -- a guarda pegou o caso errado")


def test_run_tests_sem_layout_NAO_RODA_A_SUITE_DO_DESCONHECIDO(sem_layout, monkeypatch):
    """Com `codigo.testes` vazio o alvo do pytest seria "", que roda TUDO.

    Rodar a suite inteira do repositorio de um desconhecido dentro do nosso
    container e' exatamente o que apagou o banco em 11/08.
    """
    monkeypatch.setattr(f.subprocess, "run", _nao_pode_rodar)
    saida = f.run_tests()
    assert "nao declara" in saida and "veredito.yml" in saida
    assert f.falhou_a_chamada() is False, "a marca ficou pendurada para a proxima"


# ------------------------------------------- o pre-voo segue, e DIZ

def _pre_voo_de_leitura(monkeypatch, tmp_path):
    """Deixa read_file/grep verdes: aqui o que esta sob teste e' o resto."""
    raiz = tmp_path / "wt"
    raiz.mkdir(exist_ok=True)
    (raiz / "modulo.py").write_text("x = 1\n" * 40, encoding="utf-8")
    monkeypatch.setattr(f, "_read_file", lambda c: "1 | conteudo do arquivo")
    monkeypatch.setattr(f, "_grep", lambda *a, **k: "arquivo.py:1: casou")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: raiz)


def test_pre_voo_sem_layout_NAO_FICA_VERDE_por_caminho_vazio(sem_layout, monkeypatch,
                                                             tmp_path):
    """🚨 O padrao de bug, dentro da guarda escrita contra o padrao de bug.

    A sonda `destino_do_teste` confere `WORKTREES/<lado>/CODIGO_TESTES_NO_REPO`.
    Com o caminho vazio isso vira a RAIZ do worktree, que e' sempre um
    diretorio: a sonda sairia `ok: True` -- "o destino existe" -- justo no caso
    em que nao ha destino nenhum. Guarda condicionada ao sinal que ela deveria
    vigiar.
    """
    _pre_voo_de_leitura(monkeypatch, tmp_path)
    monkeypatch.setattr(cfg, "WORKTREES", tmp_path)
    (tmp_path / "base").mkdir(exist_ok=True)
    (tmp_path / "head").mkdir(exist_ok=True)

    r = f.autoteste(sondar_app=False)["ferramentas"]
    assert r.get("destino_do_teste", {}).get("ok") is not True, (
        "o pre-voo disse que o destino do teste existe, e o caminho e' vazio")


def test_pre_voo_sem_layout_DIZ_que_nao_ha_prova_diferencial(sem_layout, monkeypatch,
                                                             tmp_path):
    """Sonda que some sem explicacao le como 'nao se aplica'.

    Aqui ela some porque o projeto nao se descreveu, e isso muda o que a rodada
    consegue provar. Mesma doutrina do terceiro estado: ausencia de observacao
    e' dita, nunca omitida.
    """
    _pre_voo_de_leitura(monkeypatch, tmp_path)
    r = f.autoteste(sondar_app=False)["ferramentas"]
    assert "prova_diferencial" in r, "a ausencia da prova diferencial nao aparece"
    d = r["prova_diferencial"]["detalhe"]
    assert "veredito.yml" in d and "MEDIA" in d, (
        "o pre-voo nao diz o que a rodada perde nem como consertar")


def test_pre_voo_sem_layout_NAO_ABORTA_A_RODADA(sem_layout, monkeypatch, tmp_path):
    """Sem isto o `revisa_pr.py` fica inutil: PR de terceiro nunca declara nada.

    Rodada sem prova diferencial e' DEGRADACAO conhecida -- decide por leitura,
    que foi como 26 das 38 acusacoes de 10/08 foram refutadas.
    """
    _pre_voo_de_leitura(monkeypatch, tmp_path)
    assert f.autoteste(sondar_app=False)["ok"] is True, (
        "abortou a rodada de um PR que so' precisa de leitura")


# ------------------------------------------- sem fallback para a arvore do desafio

def test_config_nao_tem_fallback_para_o_layout_do_desafio():
    """`app/api/tests` era o padrao quando o projeto nao declarava nada.

    O comentario no config ja contava que esse mesmo chumbado tinha custado uma
    rodada em 15/08 -- e o conserto de la' trocou o VALOR em vez de tirar o
    fallback. Ele voltou a morder em 17/08, no Flask.
    """
    import inspect
    fonte = inspect.getsource(cfg)
    i = fonte.index("_codigo = PROJETO.get")
    trecho = fonte[i:fonte.index("BANCO_DE_TESTE_SEMEADO")]
    linhas = [l for l in trecho.splitlines() if not l.lstrip().startswith("#")]
    assert "app/api" not in "\n".join(linhas), (
        "a arvore do desafio voltou como fallback do bloco `codigo`")


def test_tem_prova_diferencial_exige_os_tres(monkeypatch):
    """Nenhum dos tres se deduz dos outros, entao faltar um so' ja basta.

    Sem `montagens` o pytest roda o codigo ASSADO NA IMAGEM e os dois lados dao
    o mesmo resultado -- falso negativo silencioso, provado com canario em
    08/08. Um criterio que aceitasse dois de tres reintroduziria justo esse.
    """
    for faltando in ("montagens", "testes", "testes_no_repo"):
        codigo = {"montagens": [["app", "/srv/app"]], "testes": "app/tests",
                  "testes_no_repo": "app/tests"}
        del codigo[faltando]
        assert not _tem_prova_diferencial_com(codigo), (
            f"sem `{faltando}` ele se declarou capaz de prova diferencial")
    assert _tem_prova_diferencial_com(
        {"montagens": [["app", "/srv/app"]], "testes": "app/tests",
         "testes_no_repo": "app/tests"})


def _tem_prova_diferencial_com(codigo: dict) -> bool:
    """Reproduz o criterio do config a partir de um bloco `codigo` qualquer.

    Recarregar o modulo inteiro exigiria reescrever o yml do projeto em disco; o
    que esta sob teste aqui e' a FORMA do criterio -- que exige os tres.
    """
    return bool((codigo.get("montagens") or []) and (codigo.get("testes") or "")
                and (codigo.get("testes_no_repo") or ""))


# ------------------------------------------- indisponivel NAO e' quebrado

def test_a_recusa_NAO_contamina_o_veredito(sem_layout):
    """A decisao de 17/08, na R3. Medida antes de ser tomada.

    No `pallets/flask#6095`, com `erro` e `indisponivel` no mesmo campo, quatro
    refutacoes obtidas por leitura -- grep funcionando, uma delas apontando a
    assinatura documentada do pytest -- sairam INCONCLUSIVAS. A unica que
    sobreviveu sobreviveu por acaso: naquela o advogado nao chegou a chamar a
    ferramenta que nao existe.
    """
    from veredito import juiz

    art = f._prova_diferencial("def test_x():\n    assert True\n", "test_x.py")
    assert art["erro"] is None, "recusa gravada como falha de execucao"
    assert art["indisponivel"], "a recusa nao ficou registrada em lugar nenhum"

    v = juiz.aplica_regras({"veredito": "REFUTADO", "severidade": "BAIXA",
                            "ferramentas_ok": 2}, {}, art)
    assert v["veredito"] == "REFUTADO", (
        "a R3 converteu uma refutacao por leitura porque a prova diferencial "
        "nao existe neste projeto")


def test_ferramenta_que_QUEBROU_continua_contaminando(sem_layout):
    """🚫 O controle, e a metade que nao pode afrouxar.

    Sem ele, o teste acima passaria com a R3 desligada -- que e' a regra que
    impede absolvicao falsa, e o erro mais caro possivel neste projeto.
    """
    from veredito import juiz

    quebrou = {"estado": "INCONCLUSIVO", "erro": "docker: connection refused",
               "indisponivel": None}
    v = juiz.aplica_regras({"veredito": "REFUTADO", "severidade": "BAIXA",
                            "ferramentas_ok": 2}, {}, quebrou)
    assert v["veredito"] == "INCONCLUSIVO", "a R3 parou de converter falha real"


def test_r3b_continua_disparando_com_zero_observacao(sem_layout):
    """🚫 A outra metade que nao afrouxou, e e' a decisao mais delicada daqui.

    Chamar duas ferramentas que este projeto nao tem, nao ler arquivo nenhum e
    refutar a partir do diff que ja veio no prompt e' ARGUMENTAR -- e o produto
    existe para barrar isso. Indisponivel deixou de contar como erro; nunca
    passou a contar como observacao.

    E' o caso `correcao_05` do Flask, que continua inconclusivo de proposito.
    """
    from veredito import juiz

    v = juiz.aplica_regras(
        {"veredito": "REFUTADO", "severidade": "BAIXA", "ferramentas_ok": 0,
         "ferramentas_erro": 0, "ferramentas_indisponivel": 2}, {}, None)
    assert v["veredito"] == "INCONCLUSIVO"
    assert "nao declara" in v["motivo"], (
        "a R3b disparou sem dizer que a causa foi o projeto nao ter declarado")


def test_recusa_nao_conta_como_erro_na_aritmetica(sem_layout, monkeypatch):
    """🚨 Onde o conserto viraria no-op EM SILENCIO.

    `_consolida_ferramentas` deduz "bloco sem registro" de `blocos - (ok +
    erro)`. Se os indisponiveis nao entrarem na subtracao, cada recusa vira
    bloco nao contabilizado, cai em `nao_executadas` e VOLTA para a conta de
    erro -- de onde tinha acabado de sair. O conserto pareceria feito.
    """
    from veredito import advogado

    f.define_acusacao("a_aritmetica")
    f._CHAMADAS.pop("a_aritmetica", None)
    monkeypatch.setattr(f.subprocess, "run", _nao_pode_rodar)
    f.run_tests()                                    # 1 indisponivel
    f._abre_chamada()
    f._fecha_chamada("grep", "arquivo.py:1: casou")  # 1 ok

    v: dict = {}
    advogado._consolida_ferramentas(v, "a_aritmetica", blocos=2)
    assert (v["ferramentas_ok"], v["ferramentas_erro"],
            v["ferramentas_indisponivel"]) == (1, 0, 1), (
        "a recusa voltou para a conta de erro pela porta dos blocos")
