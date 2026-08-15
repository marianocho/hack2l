"""Os scanners externos somem em silencio? -- travas de 15/08.

🚨 O caso real: maquina nova, `bandit` e `semgrep` instalados via pip, e so' o
bandit rodava. O `Scripts\\` do Python nao estava no PATH, e `fontes.py` chamava
`semgrep` como executavel nu. A rodada teria seguido sem metade da corroboracao
externa -- a UNICA fonte de acusacao que nao e' o mesmo modelo dos promotores.

E o bandit era o pior dos dois. Ausente, o subprocess morria, `stdout` vinha
vazio, a regex nao casava e a funcao devolvia `[]`. O log entao imprimia
"bandit 0 achado(s) nos arquivos do PR" -- que le exatamente igual a "rodou e
nao achou nada". Falha lida como resultado.

Este arquivo existe porque o padrao de bug da casa e' guarda muda, e a resposta
da casa e' ver a guarda FALHANDO. Nenhum teste aqui roda scanner de verdade:
o que se trava e' o comportamento na AUSENCIA deles.
"""

import sys

import pytest

from veredito import ferramentas as f
from veredito import fontes


@pytest.fixture
def sem_bandit(monkeypatch):
    monkeypatch.setattr(fontes, "_argv_bandit", lambda: None)


@pytest.fixture
def sem_semgrep(monkeypatch):
    monkeypatch.setattr(fontes, "_argv_semgrep", lambda: None)


# ------------------------------------------------- a guarda, vista falhando

def test_bandit_ausente_levanta_em_vez_de_devolver_vazio(sem_bandit, tmp_path):
    """O defeito original, exatamente. `[]` aqui vira "0 achado(s)" no log."""
    with pytest.raises(RuntimeError, match="bandit"):
        fontes._bandit(tmp_path, set())


def test_semgrep_ausente_levanta_em_vez_de_devolver_vazio(sem_semgrep, tmp_path):
    with pytest.raises(RuntimeError, match="semgrep"):
        fontes._semgrep(tmp_path, set())


def test_bandit_que_roda_e_nao_devolve_json_tambem_levanta(monkeypatch, tmp_path):
    """Instalado mas quebrado tem que doer igual a ausente.

    Era o segundo jeito de o `[]` mentir: a regex nao casa, ninguem sabe por que,
    e a rodada segue anunciando zero.
    """
    monkeypatch.setattr(fontes, "_argv_bandit", lambda: ["nao-importa"])

    class _R:
        stdout, stderr, returncode = "", "estourou", 2

    monkeypatch.setattr(fontes.subprocess, "run", lambda *a, **k: _R())
    with pytest.raises(RuntimeError, match="nao devolveu JSON"):
        fontes._bandit(tmp_path, set())


def test_regra_semgrep_ausente_devolve_vazio_e_NAO_levanta(monkeypatch, tmp_path):
    """A assimetria e' de proposito, e e' a unica.

    Sem arquivo de regra nao ha o que rodar -- e' escolha de configuracao, nao
    ambiente quebrado. Zero e' a resposta certa, e levantar aqui transformaria
    "este projeto nao usa taint" em falha de infraestrutura.
    """
    monkeypatch.setattr(fontes.cfg, "RAIZ", tmp_path)
    assert fontes._semgrep(tmp_path, set()) == []


# ------------------------------------------------- a rodada nao cai por isso

def test_acusa_segue_sem_scanner_nenhum(sem_bandit, sem_semgrep, capsys, tmp_path):
    """Degradacao, nunca queda: os promotores continuam sendo a fonte principal."""
    assert fontes.acusa("", raiz=tmp_path) == []
    saida = capsys.readouterr().out
    # A CAUSA no log, nao so' o tipo da excecao: falta de binario, de PATH e de
    # regra tem consertos diferentes, e "FALHOU (RuntimeError)" nao distingue.
    assert "NAO RODOU" in saida
    assert "bandit" in saida and "semgrep" in saida


# ------------------------------------------------- visivel no pre-voo

def test_disponiveis_responde_no_formato_do_autoteste():
    d = fontes.disponiveis()
    assert set(d) == {"bandit", "semgrep"}
    for nome, res in d.items():
        assert isinstance(res["ok"], bool), nome
        assert isinstance(res["detalhe"], str) and res["detalhe"], nome


def test_pre_voo_MENCIONA_os_scanners():
    """A trava central deste arquivo.

    Enquanto o pre-voo nao os citava, "sem corroboracao externa" era um estado
    que a rodada inteira podia ter sem ninguem saber.
    """
    r = f.autoteste(sondar_app=False)
    assert {"bandit", "semgrep"} <= set(r["ferramentas"])


def test_scanner_ausente_nao_derruba_o_ok_global(sem_bandit, sem_semgrep):
    """Nao e' essencial -- igual app fora do ar. So' nao pode ser mudo."""
    r = f.autoteste(sondar_app=False)
    assert r["ferramentas"]["bandit"]["ok"] is False
    assert r["ok"] == all(r["ferramentas"][n]["ok"] for n in f.ESSENCIAIS)


# ------------------------------------------------- ambiente fora do produto

def test_bandit_roda_no_MESMO_interpretador_sem_launcher_de_plataforma():
    """`py -3.12` so' existe no Windows com o launcher instalado.

    Chumbado em `_bandit`, ele fazia a corroboracao externa depender da
    plataforma de quem roda -- a mesma classe do layout chumbado em
    `_roda_pytest` que a bancada expos em 14/08.

    ⚠️ A primeira versao desta trava procurava a string `"py"` no FONTE, e
    casou com o comentario que explica o conserto. Mesmo erro por substring que
    ja custou duas travas em 13/08 (`kb` dentro de `kb_veredito_app`,
    `override=True` dentro do comentario que dizia por que esta desligado).
    Aqui a pergunta certa nao e' "o texto aparece?", e' "o comando executado
    depende da plataforma?" -- entao a trava olha o argv, nao o arquivo.
    """
    argv = fontes._argv_bandit()
    assert argv is not None, "bandit ausente: instale para esta trava valer"
    assert argv[0] == sys.executable, argv
