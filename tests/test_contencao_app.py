"""A contencao do `http_request`: o app aponta para uma copia descartavel.

Nenhum teste aqui sobe container -- o docker e' trocado por dublê. O que se
trava e' a LOGICA que decide seguir ou abortar, porque e' nela que mora o modo
de falha caro: contencao pedida, nao confirmada, e a rodada correndo assim mesmo
em cima do banco de verdade.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from veredito import config as cfg
from veredito import contencao_app as ca


def _res(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def ligada(monkeypatch):
    monkeypatch.setattr(cfg, "APP_EM_BANCO_DESCARTAVEL", True)
    monkeypatch.setattr(cfg, "BANCO_APP", "kb_veredito_app")
    monkeypatch.setattr(cfg, "BANCO_APP_ORIGEM", "kb")


# ------------------------------------------------ a escotilha, desligada

def test_desligada_por_padrao():
    """Mesmo criterio da PERMITIR_REDE_NO_BASE: efeito no ambiente do usuario
    se pergunta antes. Ela reinicia o container da api."""
    import importlib
    novo = importlib.reload(cfg)
    assert novo.APP_EM_BANCO_DESCARTAVEL is False


def test_desligada_e_no_op(monkeypatch, tmp_path):
    """Nao pode nem tentar falar com docker: rodada de quem nao pediu contencao
    corre exatamente como corria."""
    monkeypatch.setattr(cfg, "APP_EM_BANCO_DESCARTAVEL", False)
    monkeypatch.setattr(ca, "_compose", _proibido)
    with ca.app_em_banco_descartavel(tmp_path) as banco:
        assert banco is None


def _proibido(*a, **k):
    raise AssertionError("a contencao desligada nao pode tocar no docker")


# ------------------------------- 🚨 a copia nao pode ser o proprio alvo

def test_copia_igual_a_origem_e_recusada(ligada, monkeypatch):
    """Uma variavel de ambiente trocada faria a rodada escrever no banco REAL
    achando que esta contida -- pior que nao ter contencao, porque some o unico
    sinal de que ha risco."""
    monkeypatch.setattr(cfg, "BANCO_APP", "kb")
    with pytest.raises(ca.ContencaoFalhou, match="mesmo banco"):
        ca.confere_nomes()


def test_copia_vazia_e_recusada(ligada, monkeypatch):
    monkeypatch.setattr(cfg, "BANCO_APP", "  ")
    with pytest.raises(ca.ContencaoFalhou):
        ca.confere_nomes()


def test_nomes_diferentes_passam(ligada):
    ca.confere_nomes()   # nao levanta


# ---------------------------- 🚨 confirmar, nao supor (licao de 11/08)

def test_api_no_banco_errado_aborta_a_rodada(ligada, monkeypatch, tmp_path):
    """O `docker network connect` de 11/08 subia "com sucesso" e ficava
    quebrado; por isso `_garante_rede_isolada` passou a devolver o resultado da
    CONFERENCIA. Aqui e' igual: se o override nao pegar, a api continua no banco
    real. Seguir nesse estado e' o pior desfecho possivel -- a rodada escreveria
    no banco de verdade com o operador achando que pediu protecao.
    """
    monkeypatch.setattr(ca, "copia_o_banco", lambda destino=None: None)
    monkeypatch.setattr(ca, "aponta_api_para", lambda banco, override: None)
    monkeypatch.setattr(ca, "banco_em_uso_pela_api", lambda: "kb")   # nao pegou
    devolveu = []
    monkeypatch.setattr(ca, "devolve_api_ao_original",
                        lambda: devolveu.append(True) or True)

    with pytest.raises(ca.ContencaoFalhou, match="Rodada abortada"):
        with ca.app_em_banco_descartavel(tmp_path):
            pytest.fail("o corpo nao pode rodar sem contencao confirmada")
    assert devolveu, "abortou sem devolver a api ao banco original"


def test_api_confirmada_deixa_a_rodada_seguir(ligada, monkeypatch, tmp_path):
    monkeypatch.setattr(ca, "copia_o_banco", lambda destino=None: None)
    monkeypatch.setattr(ca, "aponta_api_para", lambda banco, override: None)
    monkeypatch.setattr(ca, "banco_em_uso_pela_api", lambda: "kb_veredito_app")
    monkeypatch.setattr(ca, "devolve_api_ao_original", lambda: True)

    with ca.app_em_banco_descartavel(tmp_path) as banco:
        assert banco == "kb_veredito_app"


# ------------------------------------------- devolver SEMPRE, inclusive no erro

def test_rodada_que_explode_devolve_a_api(ligada, monkeypatch, tmp_path):
    """Deixar o app do usuario apontado para um banco temporario seria um
    estrago NOSSO, e o mais provavel de acontecer: rodada longa, muita chance de
    morrer no meio."""
    monkeypatch.setattr(ca, "copia_o_banco", lambda destino=None: None)
    monkeypatch.setattr(ca, "aponta_api_para", lambda banco, override: None)
    monkeypatch.setattr(ca, "banco_em_uso_pela_api", lambda: "kb_veredito_app")
    devolveu = []
    monkeypatch.setattr(ca, "devolve_api_ao_original",
                        lambda: devolveu.append(True) or True)

    with pytest.raises(ZeroDivisionError):
        with ca.app_em_banco_descartavel(tmp_path):
            1 / 0
    assert devolveu, "a api ficou apontada para o banco temporario"


def test_falha_ao_devolver_avisa_e_nao_levanta(ligada, monkeypatch, tmp_path, capsys):
    """Se nem devolver deu certo, o veredicto da rodada ainda vale -- mas o
    operador precisa ver o comando para consertar a mao."""
    monkeypatch.setattr(ca, "copia_o_banco", lambda destino=None: None)
    monkeypatch.setattr(ca, "aponta_api_para", lambda banco, override: None)
    monkeypatch.setattr(ca, "banco_em_uso_pela_api", lambda: "kb_veredito_app")
    monkeypatch.setattr(ca, "devolve_api_ao_original", lambda: False)

    with ca.app_em_banco_descartavel(tmp_path):
        pass
    assert "force-recreate" in capsys.readouterr().out


# ------------------------------------------ a copia so' LE o banco de origem

def test_a_copia_nunca_escreve_no_banco_de_origem(ligada, monkeypatch, tmp_path):
    """O DROP/CREATE so' pode mirar o descartavel. Este teste le os comandos que
    sairiam para o docker e recusa qualquer escrita no banco do app."""
    comandos = []

    def _compose_dublê(*args, timeout=180):
        comandos.append(args)
        return _res(0, stdout="ok")

    monkeypatch.setattr(ca, "_compose", _compose_dublê)
    ca.copia_o_banco()

    # ⚠️ Comparacao ESTRUTURAL, nao substring: "kb" casa dentro de `-U kb` (o
    # usuario) e dentro de `kb_veredito_app`. A primeira versao deste teste
    # falhou justamente por isso -- e um teste que acusa a coisa errada nao vale
    # mais que um que nao acusa nada.
    def _alvo_do_sql(args):
        """O banco citado no SQL, entre aspas: DROP DATABASE "x"."""
        import re
        for x in args:
            m = re.search(r'(?:DROP|CREATE) DATABASE (?:IF EXISTS )?"([^"]+)"', x)
            if m:
                return m.group(1)
        return None

    def _banco_conectado(args):
        """O argumento de `-d`: a qual banco este comando se conecta."""
        args = list(args)
        return args[args.index("-d") + 1] if "-d" in args else None

    destrutivos = [a for a in comandos if _alvo_do_sql(a)]
    assert destrutivos, "o teste nao encontrou os comandos que deveria vigiar"
    for a in destrutivos:
        assert _alvo_do_sql(a) == cfg.BANCO_APP, (
            f"DROP/CREATE mirando '{_alvo_do_sql(a)}' em vez do descartavel")

    # Conectar NO banco de origem so' e' aceitavel para ler.
    for a in comandos:
        if _banco_conectado(a) == cfg.BANCO_APP_ORIGEM:
            assert "pg_dump" in a, (
                f"conectou no banco do app fora do pg_dump: {' '.join(a)}")


def test_pg_dump_que_falha_aborta(ligada, monkeypatch):
    monkeypatch.setattr(ca, "_compose",
                        lambda *a, timeout=180: _res(1, stderr="sem espaco"))
    with pytest.raises(ca.ContencaoFalhou, match="pg_dump"):
        ca.copia_o_banco()


def test_o_override_troca_so_a_database_url(ligada, tmp_path, monkeypatch):
    """A DATABASE_URL da api e' CHUMBADA no compose do desafio, sem `${...}`, e
    por isso variavel de ambiente nao resolve. O override e' um segundo `-f` --
    e ele nao pode carregar mais nada junto."""
    monkeypatch.setattr(ca, "_compose_com_override",
                        lambda ov, *a, timeout=180: _res(0))
    monkeypatch.setattr(ca, "_api_no_ar", lambda tentativas=30: True)
    ov = tmp_path / "compose.contencao.yml"
    ca.aponta_api_para("kb_veredito_app", ov)

    texto = ov.read_text(encoding="utf-8")
    assert "kb_veredito_app" in texto
    assert "DATABASE_URL" in texto
    for proibido in ("ports", "volumes", "build", "command"):
        assert proibido not in texto, f"o override mexe em '{proibido}' sem precisar"


def test_api_que_nao_responde_aborta(ligada, tmp_path, monkeypatch):
    """Subir o container nao e' estar no ar -- a mesma confusao ja custou um
    `compose up` falhando logo depois de eu reportar sucesso (CLAUDE.md)."""
    monkeypatch.setattr(ca, "_compose_com_override",
                        lambda ov, *a, timeout=180: _res(0))
    monkeypatch.setattr(ca, "_api_no_ar", lambda tentativas=30: False)
    with pytest.raises(ca.ContencaoFalhou, match="health"):
        ca.aponta_api_para("kb_veredito_app", tmp_path / "o.yml")
