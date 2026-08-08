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
    """O ponto mais afiado do modulo.

    exit_head != 0 seria a leitura ingenua e transformaria docker fora do ar em
    condenacao critica. So o exit 1 -- teste falhou de verdade -- e' prova.
    """
    estado, provado, motivo = f._classifica(0, exit_head)
    assert estado == "INCONCLUSIVO"
    assert provado is False
    assert motivo


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

