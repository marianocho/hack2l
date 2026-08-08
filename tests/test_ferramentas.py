"""Testes da pericia.

Nenhum depende do conteudo do PR: exercitam os tres estados com testes
sinteticos. Isso e' de proposito -- a regua do desafio e' que trocar o PR nao
pode quebrar o agente, e uma suite que so passa neste PR falharia a regua.

    pytest tests -q            # tudo
    pytest tests -q -m "not lento"   # so as unitarias, milissegundos
"""

import subprocess

import requests

import pytest

from veredito import ferramentas as f

lento = pytest.mark.lento


# ------------------------------------------------- a regra central, unitaria
# Estes sao os testes mais importantes do repo: e' aqui que mora a decisao que
# o LLM nao pode tomar.

def test_provado_exige_passar_no_base_e_falhar_no_head():
    estado, provado, motivo = f._classifica(0, 1)
    assert (estado, provado) == ("PROVADO", True)
    assert motivo


def test_passar_nos_dois_lados_e_refutacao_nao_prova():
    estado, provado, _ = f._classifica(0, 0)
    assert estado == "REFUTADO"
    assert provado is False


@pytest.mark.parametrize("exit_head", [2, 3, 4, 5])
def test_erro_de_execucao_no_head_nunca_vira_prova(exit_head):
    """exit_head != 0 seria a leitura ingenua e transformaria docker fora do ar
    em condenacao critica. So o exit 1 -- teste falhou de verdade -- e' prova.
    """
    estado, provado, motivo = f._classifica(0, exit_head)
    assert estado == "INCONCLUSIVO"
    assert provado is False
    assert motivo


# ---------------------------------------------- docker devolve 1, igual a falha
# Achado da auditoria adversarial de 08/08. Esta parametrizacao ia so ate 5 e
# por isso carimbava falsa seguranca justamente no ponto mais afiado do modulo.

def test_docker_caindo_no_head_nao_vira_prova_mesmo_com_exit_1():
    """`docker compose` devolve 1 quando o daemon falha -- o MESMO codigo que o
    pytest usa para 'teste falhou'. `docker run` puro usa 125; o compose nao.

    Sem a guarda de 'o pytest chegou a rodar', um flap do healthcheck do db
    entre as duas execucoes virava acusacao CRITICA falsa, e o exit code
    medido -- a unica salvaguarda deterministica do produto -- era derrotado
    pelo caso que ela dizia proteger.
    """
    estado, provado, motivo = f._classifica(0, 1, rodou_base=True, rodou_head=False)
    assert estado == "INCONCLUSIVO"
    assert provado is False
    assert "nao chegou a rodar" in motivo


def test_docker_caindo_no_base_nao_manda_enfraquecer_o_teste():
    """A direcao inversa, que e' a mais provavel: docker ruim no inicio da
    rodada da exit_base=1 em TODAS as acusacoes. O motivo antigo dizia
    'reescreva o teste para passar no codigo de hoje' -- instrucao para o
    advogado ENFRAQUECER um teste correto ate ele passar. Loop de auto-sabotagem
    com o parecer esvaziando e parecendo rigor.
    """
    _, _, motivo = f._classifica(1, 1, rodou_base=False, rodou_head=False)
    assert "reescreva" not in motivo.lower()
    assert "nao chegou a rodar" in motivo


# -------------------------------- o codigo do teste vem do modelo, e ele erra

def test_recusa_teste_que_fala_com_o_app_no_ar():
    """O servico 'api' no ar serve o codigo ASSADO NA IMAGEM, identico nos dois
    lados. Um teste que bate nele mede estado acumulado, nao a mudanca do PR --
    e como o head sempre roda depois, a diferenca aparece e vira PROVADO falso.
    """
    for url in ("http://api:8000/documents", "http://localhost:8000/chat",
                "http://127.0.0.1:8000/documents"):
        motivo = f._valida_codigo_do_teste(f"import requests\nr = requests.get('{url}')\n")
        assert motivo and "NO AR" in motivo


def test_recusa_teste_que_escreve_no_banco_da_aplicacao():
    """O pior estrago possivel: apagar demo/alice/bob/carol no meio da rodada.

    O conftest deles redireciona DATABASE_URL para kb_test, mas so quando a URL
    termina em /kb -- um teste que monte a propria engine passa por cima.
    """
    codigo = (
        "from sqlalchemy import create_engine\n"
        "e = create_engine('postgresql+psycopg://kb:kb@db:5432/kb')\n"
    )
    motivo = f._valida_codigo_do_teste(codigo)
    assert motivo and "kb_test" in motivo


def test_nao_recusa_teste_legitimo_contra_kb_test():
    """A guarda nao pode bloquear o caminho certo, senao empurra o advogado
    para o errado."""
    codigo = (
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "def test_x():\n"
        "    with TestClient(app) as c:\n"
        "        assert c.get('/health').status_code == 200\n"
    )
    assert f._valida_codigo_do_teste(codigo) is None
    assert f._valida_codigo_do_teste(
        "e = create_engine('postgresql+psycopg://kb:kb@db:5432/kb_test')\n"
    ) is None


def test_resumo_do_pytest_e_o_que_distingue_teste_de_infra():
    """A deteccao nao pergunta ao exit code, pergunta ao pytest."""
    assert f._RESUMO_PYTEST.search("5 passed in 2.43s")
    assert f._RESUMO_PYTEST.search("1 failed, 4 passed in 70.90s")
    assert f._RESUMO_PYTEST.search("no tests ran in 0.01s")
    # saidas tipicas de docker quebrado: nenhuma tem linha de resumo
    assert not f._RESUMO_PYTEST.search(
        "failed to connect to the docker API, check if the daemon is running"
    )
    assert not f._RESUMO_PYTEST.search("no such service: api")
    assert not f._RESUMO_PYTEST.search("Error response from daemon: no space left on device")
    assert not f._RESUMO_PYTEST.search("invalid spec: :/code/app: empty section between colons")


def test_teste_que_ja_falha_no_base_nao_isola_a_mudanca():
    estado, provado, motivo = f._classifica(1, 1)
    assert estado == "INCONCLUSIVO"
    assert provado is False
    assert "base" in motivo


def test_todo_estado_tem_motivo_e_nada_e_absolvido_em_silencio():
    """Nenhum par de exit codes sai daqui sem explicacao legivel."""
    for base in range(0, 6):
        for head in range(0, 6):
            estado, provado, motivo = f._classifica(base, head)
            assert estado in {"PROVADO", "REFUTADO", "INCONCLUSIVO"}
            assert motivo, f"estado sem motivo em base={base} head={head}"
            assert provado is (estado == "PROVADO")


# ------------------------------------------------------ nome vindo do modelo

@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("test_vazamento.py", "test_vazamento.py"),
        ("vazamento", "test_vazamento.py"),
        ("vazamento.py", "test_vazamento.py"),
        ("../../etc/passwd", "test_passwd.py"),
        ("a/b/c/test_x.py", "test_x.py"),
        ("", "test_acusacao.py"),
    ],
)
def test_sanitiza_nome_do_arquivo(entrada, esperado):
    """Nome fora do padrao faz o pytest coletar zero e a prova morre parecendo
    refutacao. Travessia de caminho tambem sai aqui."""
    assert f._sanitiza_nome(entrada) == esperado


# --------------------------------------------------------- retry de rede, unit

def test_retry_repete_falha_de_conexao():
    """Conexao que nunca subiu nao aplicou nada: repetir e' seguro e necessario,
    porque a api leva ~30s para aceitar conexao depois de um compose up."""
    tentativas = []

    def instavel():
        tentativas.append(1)
        if len(tentativas) < 3:
            raise requests.exceptions.ConnectionError("recusou")
        return "ok"

    assert f._com_retry("POST", instavel) == "ok"
    assert len(tentativas) == 3


def test_retry_nao_repete_post_que_deu_timeout():
    """Num ReadTimeout o pedido pode ter sido aplicado. Repetir um POST criaria
    o recurso duas vezes e sujaria o raciocinio do advogado."""
    tentativas = []

    def pendura():
        tentativas.append(1)
        raise requests.exceptions.ReadTimeout("pendurou")

    with pytest.raises(requests.exceptions.ReadTimeout):
        f._com_retry("POST", pendura)
    assert len(tentativas) == 1, "POST com timeout nao pode ser repetido"


def test_retry_repete_get_que_deu_timeout():
    tentativas = []

    def pendura():
        tentativas.append(1)
        raise requests.exceptions.ReadTimeout("pendurou")

    with pytest.raises(requests.exceptions.ReadTimeout):
        f._com_retry("GET", pendura)
    assert len(tentativas) == f.cfg.TENTATIVAS_HTTP


def test_url_do_app_nao_usa_localhost():
    """08/08: localhost resolve ::1 primeiro e o caminho IPv6 do Docker pendura.
    0/8 em localhost, 8/8 em 127.0.0.1, nas tres portas. E' ReadTimeout, entao
    cada chamada gasta o timeout inteiro antes de virar INCONCLUSIVO.

    Se na outra maquina localhost funcionar, 127.0.0.1 funciona tambem -- entao
    a escolha estrita nao custa nada la e salva a demo aqui.
    """
    assert "localhost" not in f.cfg.APP_API_URL, "use 127.0.0.1 -- ver comentario em config.py"


# ------------------------------------------- o caminho que vai parar no slide

def _raiz_falsa(tmp_path, monkeypatch, *arquivos):
    """Worktree de mentira: normaliza_local so le disco, entao nao precisa git."""
    raiz = tmp_path / "head"
    for a in arquivos:
        alvo = raiz / a
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text("x", encoding="utf-8")
    raiz.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(f.cfg, "WORKTREES", tmp_path)
    f._CACHE_LOCAL.clear()
    return raiz


def test_normaliza_local_corrige_a_raiz_que_o_promotor_inventou(tmp_path, monkeypatch):
    """24, 20 e 7 acusacoes da mesma rodada citaram este arquivo com tres raizes
    diferentes. Sem isto o parecer exibe um caminho que nao abre no repo."""
    _raiz_falsa(tmp_path, monkeypatch, "app/api/app/routers/shares.py")
    assert f.normaliza_local("app/routers/shares.py:31") == "app/api/app/routers/shares.py:31"
    assert f.normaliza_local("routers/shares.py") == "app/api/app/routers/shares.py"


def test_normaliza_local_devolve_o_que_recebeu_quando_nao_da(tmp_path, monkeypatch):
    """Cosmetica nao pode inventar caminho. Ambiguo, inexistente ou diretorio
    saem intactos -- caminho errado no parecer e' pior que caminho feio."""
    _raiz_falsa(tmp_path, monkeypatch,
                "app/api/app/routers/shares.py", "app/web/app/routers/shares.py")
    assert f.normaliza_local("routers/shares.py:9") == "routers/shares.py:9"   # ambiguo
    assert f.normaliza_local("nao_existe_xyz.py:1") == "nao_existe_xyz.py:1"
    assert f.normaliza_local("app/api/app/routers/") == "app/api/app/routers/"  # diretorio
    assert f.normaliza_local("") == ""


def test_normaliza_local_nao_cria_worktree(tmp_path, monkeypatch):
    """Chamada pelo juiz, que roda em milissegundos e sem git de proposito."""
    monkeypatch.setattr(f.cfg, "WORKTREES", tmp_path / "vazio")
    f._CACHE_LOCAL.clear()
    assert f.normaliza_local("app/routers/shares.py:31") == "app/routers/shares.py:31"
    assert not (tmp_path / "vazio").exists(), "normaliza_local montou worktree"


# ------------------------------------------------------------- git, sem docker

def test_base_e_o_pai_do_pr_nao_a_ponta_da_main():
    """A correcao de 08/08: f491ae1 e' irmao do PR, nao ancestral."""
    base, head = f.commit_base(), f.commit_head()
    assert base != head
    r = subprocess.run(
        ["git", "-C", str(f.cfg.DESAFIO), "merge-base", "--is-ancestor", base, head],
        capture_output=True,
    )
    assert r.returncode == 0, "o base calculado nao e' ancestral do head"


# --------------------------------------------------------- ponta a ponta, lento

@lento
def test_teste_que_passa_dos_dois_lados_e_refutado():
    f.define_acusacao("selftest_refutado")
    art = f._prova_diferencial("def test_ok():\n    assert True\n", "test_selftest_ok.py")
    assert art["exit_base"] == 0
    assert art["estado"] == "REFUTADO"
    assert art["provado"] is False

    # O defeito de 08/08: o motivo da refutacao estava indo no campo `erro`, e o
    # juiz trata erro != None como INCONCLUSIVO. Toda refutacao viraria
    # inconclusivo e a lista de descartados -- que e' peca de demo -- esvaziaria
    # sozinha. `erro` e' SO falha de infraestrutura.
    assert art["erro"] is None, "refutacao nao e' erro de execucao"
    assert art["motivo"], "descartado sem motivo nao entra no parecer"


@lento
def test_teste_que_ja_falha_no_base_e_inconclusivo():
    f.define_acusacao("selftest_falha_no_base")
    art = f._prova_diferencial("def test_nao():\n    assert False\n", "test_selftest_nao.py")
    assert art["exit_base"] == 1
    assert art["estado"] == "INCONCLUSIVO"
    assert "base" in art["motivo"]
    assert art["erro"] is None, "exit code ruim nao e' falha de infraestrutura"


@lento
def test_arquivo_sem_funcao_test_nao_coleta_e_e_inconclusivo():
    """Exit 5. Sem este ramo, 'nao coletou' viraria absolvicao limpa."""
    f.define_acusacao("selftest_nao_coleta")
    art = f._prova_diferencial("def verifica():\n    assert True\n", "test_selftest_vazio.py")
    assert art["exit_base"] == 5
    assert art["estado"] == "INCONCLUSIVO"


@lento
def test_artefato_registra_os_commits_reais_e_fica_em_disco():
    """O artefato e' o que o juiz le e o que vai pro slide."""
    f.define_acusacao("selftest_artefato")
    art = f._prova_diferencial("def test_ok():\n    assert True\n", "test_selftest_art.py")
    caminho = f.cfg.ARTEFATOS / "prova_selftest_artefato.json"
    assert caminho.is_file()
    assert art["commit_base"] == f.commit_base()[:7]
    assert art["commit_head"] == f.commit_head()[:7]


@lento
def test_worktree_do_teste_fica_limpo_depois():
    """Se o arquivo sobrar, a proxima acusacao roda com lixo da anterior."""
    f.define_acusacao("selftest_limpeza")
    f._prova_diferencial("def test_ok():\n    assert True\n", "test_selftest_limpa.py")
    for lado in ("base", "head"):
        sujeira = f.cfg.WORKTREES / lado / "app" / "api" / "tests" / "test_selftest_limpa.py"
        assert not sujeira.exists(), f"sobrou {sujeira}"

