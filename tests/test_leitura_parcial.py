"""Escala: a leitura degrada ROTULADA, em vez de morrer no relogio (20/08).

Item 5 da T3 / item E da fila. Medido no `next.js`: ~220s por acusacao contra
~30s nos outros, 6 de 8 inconclusivos. *"Quando a fatia nao cabe, ele nao
degrada para 'nao sei' com elegancia -- gasta 220s e ai diz nao sei."*

🚨 O QUARTO SINAL, e o que estas travas existem para prender:

`parcial` e' ORTOGONAL a `erro` e a `indisponivel`. A chamada deu certo e a
ferramenta existe -- ela so' olhou um pedaco. Marcar isso como falha faria a R3
converter em INCONCLUSIVO toda refutacao obtida em repositorio grande, que e' o
erro de 17/08 (`indisponivel` contado como erro no `pallets/flask`) entrando de
novo, agora pela porta do TAMANHO do repo. `test_parcial_NUNCA_vira_erro` e' a
trava dessa ponta, e e' a mais importante do arquivo.

🚨 E a segunda mais importante: `test_desistir_de_procurar_NAO_e_dizer_que_nao_existe`.
Antes disto, varredura que estourava o teto devolvia a MESMA frase de "o arquivo
nao existe". O advogado le "nao existe" e refuta a acusacao em cima disso --
absolvicao falsa fabricada pelo nosso proprio limite de tempo.
"""
import pathlib

import pytest

from veredito import config as cfg
from veredito import ferramentas as f


@pytest.fixture(autouse=True)
def _acusacao_limpa(monkeypatch, tmp_path):
    # `_fecha_chamada` grava `chamadas.json` a cada chamada, de proposito
    # (rodada que morre no meio nao pode levar junto a prova de que as
    # ferramentas funcionavam). Sem redirecionar, a suite suja o `artefatos/`
    # do repo -- e o `_ACUSACAO_ATUAL` e' global, entao o lixo sai com o NOME
    # de uma acusacao deste arquivo mesmo tendo vindo de outro teste.
    monkeypatch.setattr(cfg, "ARTEFATOS", tmp_path / "artefatos")
    # ⚠️ `_ACUSACAO_ATUAL` e' global e `define_acusacao` nao tem volta. Deixar
    # "escala_01" pendurado faz um teste de OUTRO arquivo, que faca chamada
    # http, gravar `artefatos/http_escala_01.json` no repo -- lixo com o nome
    # de uma acusacao daqui, vindo de codigo que nao e' daqui. Restaurar e' o
    # mesmo cuidado que o `_fecha_chamada` toma nas duas pontas.
    anterior = f._ACUSACAO_ATUAL
    f._CHAMADAS.clear()
    f.define_acusacao("escala_01")
    yield
    f._CHAMADAS.clear()
    f.define_acusacao(anterior)


@pytest.fixture
def repo(monkeypatch, tmp_path):
    """Uma arvore pequena, com um `node_modules` gordo dentro."""
    raiz = tmp_path / "head"
    (raiz / "app" / "routers").mkdir(parents=True)
    (raiz / "app" / "routers" / "shares.py").write_text(
        "def lista():\n    return 1\n", encoding="utf-8")
    # o peso que derrubava a leitura: muitos arquivos numa pasta que o `_grep`
    # sempre ignorou e que o resgate por sufixo varria assim mesmo.
    fundo = raiz / "node_modules" / "pacote" / "dist" / "routers"
    fundo.mkdir(parents=True)
    for i in range(60):
        (fundo / f"m{i}.js").write_text("// ruido\n", encoding="utf-8")
    # 🚨 O homonimo casa o MESMO SUFIXO (`routers/shares.py`) de proposito. Um
    # homonimo que nao casa nao prova nada: com ou sem poda o resgate acha um
    # candidato so' e devolve o certo, e a trava ficaria verde com a poda
    # arrancada. Casando, sem poda ha DOIS candidatos, o resgate fica ambiguo e
    # devolve None -- ou seja, sem a poda um arquivo que existe passa a "nao
    # existir" porque alguem vendorizou uma copia.
    (fundo / "shares.py").write_text("# copia vendorizada, mesmo sufixo\n",
                                     encoding="utf-8")
    # ⚠️ Ruido VARRIVEL, fora do `node_modules`: o `_grep` sempre honrou o
    # `_IGNORA`, entao o ruido de cima e' invisivel para ele de proposito, e um
    # teste de teto de grep apontado para la' mediria a poda, nao o teto.
    varrivel = raiz / "app" / "web"
    varrivel.mkdir(parents=True)
    for i in range(60):
        (varrivel / f"v{i}.js").write_text("// ruido\n", encoding="utf-8")
    monkeypatch.setattr(f, "_worktree_de", lambda lado: raiz)
    return raiz


def _chamada(nome, funcao):
    """Roda como a tool roda: abre, executa, fecha.

    Sem o par abre/fecha nada e' registrado em `_CHAMADAS` -- e e' o registro,
    nao a string, que o parecer le. Ver o conserto do `ERRO` como convencao de
    string, 13/08.
    """
    f._abre_chamada()
    return f._fecha_chamada(nome, funcao())


# ------------------------------------------- 1. a varredura de resgate, podada

def test_o_resgate_nao_desce_no_node_modules(repo):
    """A copia vendorizada nao pode entrar na disputa -- nem ser visitada.

    E' de onde vinha o tempo: `rglob` anda a arvore inteira por dentro, mesmo
    com quase nenhum nome casando. O `_grep` sempre honrou `_IGNORA`; este
    caminho nao, e a assimetria nao tinha motivo.

    E o custo nao era so' tempo: com os dois candidatos casando o mesmo sufixo,
    `len(casam) != 1` e o resgate devolve None -- ou seja, um arquivo que EXISTE
    passa a "nao existir" porque alguem vendorizou uma copia.
    """
    alvo, parcial = f._resolve_caminho(repo, "routers/shares.py")
    assert parcial is None
    assert alvo is not None, "sem a poda, os dois candidatos empatam e some tudo"
    assert "node_modules" not in alvo.as_posix()


def test_caminho_EXATO_dentro_de_pasta_ignorada_continua_abrindo(repo):
    """A poda vale so' para o resgate por sufixo, nunca para o caminho certo."""
    alvo, parcial = f._resolve_caminho(
        repo, "node_modules/pacote/dist/routers/shares.py")
    assert parcial is None
    assert alvo is not None and "node_modules" in alvo.as_posix()


def test_varredura_para_no_teto_e_DIZ_que_parou(repo, monkeypatch):
    monkeypatch.setenv("VEREDITO_TETO_VARREDURA", "1")
    alvo, parcial = f._resolve_caminho(repo, "nao/existe/lugar_nenhum.py")
    assert parcial, "parar sem dizer que parou e' o modo de falha que isto fecha"
    assert "teto" in parcial and "NAO conclua" in parcial


def test_procurou_TUDO_e_nao_achou_nao_e_parcial(repo):
    """A guarda consegue ficar quieta: repo pequeno, busca completa."""
    alvo, parcial = f._resolve_caminho(repo, "isto/nao/existe.py")
    assert alvo is None
    assert parcial is None, "sem teto batido nao ha nada a rotular"


# --------------------------- 2. "desisti" nao pode se passar por "nao existe"

def test_desistir_de_procurar_NAO_e_dizer_que_nao_existe(repo, monkeypatch):
    """🚨 A trava do risco real: absolvicao falsa fabricada pelo nosso teto.

    Sem ela, `read_file` num repo grande responde "nao existe em head" para um
    arquivo que esta la'. O advogado refuta a acusacao com base nisso.
    """
    monkeypatch.setenv("VEREDITO_TETO_VARREDURA", "1")
    saida = _chamada("read_file", lambda: f._read_file("nao/existe/lugar_nenhum.py"))

    # ⚠️ Asserção ESTRUTURAL, e nao por substring: o proprio rotulo contem a
    # frase "o arquivo nao existe" dentro do aviso "NAO conclua que o arquivo
    # nao existe". Um `"nao existe" not in saida` reprova o texto CERTO -- e' a
    # armadilha de substring que ja custou duas travas erradas em 13/08.
    assert saida.startswith("ERRO: nao foi possivel LOCALIZAR")
    assert "nao/existe/lugar_nenhum.py nao existe em head" not in saida, (
        "a frase que AFIRMA ausencia autoriza uma refutacao que nao se sustenta")
    assert "NAO conclua" in saida
    assert f.leitura_parcial_da_acusacao("escala_01"), "o parecer precisa saber"


def test_arquivo_que_realmente_nao_existe_continua_dizendo_que_nao_existe(repo):
    """O contraste. Sem ele a trava acima passaria com a mensagem trocada."""
    saida = _chamada("read_file", lambda: f._read_file("isto/nao/existe.py"))
    assert "isto/nao/existe.py nao existe em head" in saida
    assert not f.leitura_parcial_da_acusacao("escala_01")


# --------------------------------------------- 3. o corte do arquivo, rotulado

def test_arquivo_cortado_avisa_que_o_modelo_esta_vendo_o_FIM(repo, monkeypatch):
    """`_corta` fica com o rabo do arquivo, e a acusacao aponta para o comeco."""
    monkeypatch.setattr(cfg, "CORTE_SAIDA", 300)
    gordo = repo / "app" / "routers" / "gordo.py"
    gordo.write_text("".join(f"linha_{i} = {i}\n" for i in range(400)),
                     encoding="utf-8")

    saida = _chamada("read_file", lambda: f._read_file("app/routers/gordo.py"))
    assert saida.startswith("[LEITURA PARCIAL]")
    assert "400 linhas" in saida
    assert "FIM do arquivo" in saida
    assert f.leitura_parcial_da_acusacao("escala_01")


def test_arquivo_que_cabe_nao_diz_nada(repo, monkeypatch):
    """Pergunta 0: alarme que dispara sempre ensina a pular a linha."""
    monkeypatch.setattr(cfg, "CORTE_SAIDA", 100000)
    saida = _chamada("read_file", lambda: f._read_file("app/routers/shares.py"))
    assert "LEITURA PARCIAL" not in saida
    assert not f.leitura_parcial_da_acusacao("escala_01")


# ------------------------------------------------ 4. o teto do grep, rotulado

def test_grep_no_teto_avisa_que_ha_mais(repo):
    saida = _chamada("grep", lambda: f._grep("ruido", glob="*.js", teto=2))
    assert "cortado no teto" in saida
    parcial = f.leitura_parcial_da_acusacao("escala_01")
    assert parcial and "mais ocorrencias" in parcial[0]


def test_grep_que_varreu_tudo_nao_diz_nada(repo):
    _chamada("grep", lambda: f._grep("def lista", glob="*.py"))
    assert not f.leitura_parcial_da_acusacao("escala_01")


# ------------------------------------ 5. 🚨 parcial NAO contamina o veredito

def test_parcial_NUNCA_vira_erro(repo, monkeypatch):
    """A trava mais importante: a R3 nao pode converter por causa de tamanho.

    Uma leitura cortada DEU CERTO. Se ela entrar como `erro`, a R3 transforma em
    INCONCLUSIVO toda refutacao obtida em repositorio grande -- o erro de 17/08
    (`indisponivel` contado como erro) reentrando pela porta da escala.
    """
    monkeypatch.setattr(cfg, "CORTE_SAIDA", 300)
    gordo = repo / "app" / "routers" / "gordo.py"
    gordo.write_text("".join(f"linha_{i} = {i}\n" for i in range(400)),
                     encoding="utf-8")

    _chamada("read_file", lambda: f._read_file("app/routers/gordo.py"))

    chamada = f.chamadas_da_acusacao("escala_01")[-1]
    assert chamada["parcial"], "a fatia nao vista tem que estar registrada"
    assert chamada["desfecho"] == "ok", "leitura cortada nao e' falha"
    assert chamada["ok"] is True

    ok, erros, indisp = f.desfecho_da_acusacao("escala_01")
    assert (ok, erros, indisp) == (1, 0, 0), (ok, erros, indisp)


def test_parcial_de_uma_chamada_nao_vaza_para_a_seguinte(repo, monkeypatch):
    """Estado global que nao se limpa nas duas pontas ja custou caro aqui."""
    monkeypatch.setattr(cfg, "CORTE_SAIDA", 300)
    gordo = repo / "app" / "routers" / "gordo.py"
    gordo.write_text("".join(f"linha_{i} = {i}\n" for i in range(400)),
                     encoding="utf-8")

    _chamada("read_file", lambda: f._read_file("app/routers/gordo.py"))
    _chamada("read_file", lambda: f._read_file("app/routers/shares.py"))

    chamadas = f.chamadas_da_acusacao("escala_01")
    assert chamadas[0]["parcial"], "a primeira cortou"
    assert not chamadas[1]["parcial"], "a segunda coube inteira"


def test_leitura_parcial_nomeia_a_ferramenta(repo):
    _chamada("grep", lambda: f._grep("ruido", glob="*.js", teto=2))
    parcial = f.leitura_parcial_da_acusacao("escala_01")
    assert parcial and parcial[0].startswith("grep: ")
