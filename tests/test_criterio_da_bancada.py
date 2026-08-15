"""O criterio de acerto da bancada: achou O DEFEITO, nao "produziu um PROVADO".

🚨 O defeito que estes testes travam. O criterio era:

    bateu = contagem.get(esperado, 0) > 0

isto e', "existe pelo menos um PROVADO nesta rodada" -- verdade tambem quando o
PROVADO fala de outra coisa. As `pistas`, que sabem apontar o defeito plantado,
existiam e so' eram consultadas no ramo do FRACASSO, para distinguir ranking de
veredito. A guarda existia e ficava muda exatamente no caso perigoso: o falso
ACERTO.

E' o padrao de bug do projeto dentro da regua que deveria medi-lo -- o mesmo
formato do R0b, do R3 e do dedup. Uma bancada que passa pelo motivo errado e'
pior que bancada nenhuma: ela produz um numero para dizer em voz alta.

⚠️ E o PR do race tem DOIS defeitos (o segundo plantado sem querer, achado pelo
proprio Veredito em 15/08). Com "houve algum PROVADO", ele passava tendo achado
metade -- e passaria igual tendo achado a metade errada.
"""

import os

import pytest

# roda_bancada mexe em os.environ na IMPORTACAO (limpa APP_*, aponta
# CHALLENGE_REPO para a bancada). Sem restaurar, todo teste que importar
# veredito.config depois deste veria a configuracao da bancada -- e a suite
# mediria um projeto conversando com o app do outro, que e' o item 4 dos cinco
# chumbados de 15/08.
_ENV = dict(os.environ)
import roda_bancada as rb  # noqa: E402
os.environ.clear()
os.environ.update(_ENV)


def _pr(**kw):
    base = {"ramo": "pr/x", "esperado": "PROVADO", "defeito": "CWE-1",
            "nome": "o defeito plantado", "pistas": ["toctou"]}
    base.update(kw)
    return base


def _saida(brutas, julgadas, veredictos):
    """brutas: [(id, texto)] · julgadas: ids que foram ao advogado."""
    return {
        "brutas": [{"id": i, "categoria": "correcao", "local": "app/main.py:1",
                    "hipotese": t} for i, t in brutas],
        "acusacoes": [{"id": i} for i in julgadas],
        "veredictos": [{"id": i, "veredito": v} for i, v in veredictos],
        "custo": {},
    }


# ------------------------------------------------- o falso acerto, que era mudo

def test_provado_sobre_outra_coisa_nao_conta_como_acerto():
    """🚨 O caso que o criterio antigo dava por certo.

    Uma acusacao sobre paginacao foi julgada e PROVADA; ninguem falou do
    check-then-act plantado. "Existe um PROVADO" dizia ok.
    """
    saida = _saida(brutas=[("a1", "paginacao sem limite na listagem")],
                   julgadas=["a1"], veredictos=[("a1", "PROVADO")])
    r = rb.confronta(_pr(), saida)
    assert r["contagem"] == {"PROVADO": 1}, "houve PROVADO, so' que de outra coisa"
    assert not r["bateu"]
    assert r["achados"][0]["acusaram"] == 0, "cobertura: ninguem nomeou o defeito"


def test_provado_sobre_o_defeito_conta():
    saida = _saida(brutas=[("a1", "check-then-act: TOCTOU entre a checagem e o insert")],
                   julgadas=["a1"], veredictos=[("a1", "PROVADO")])
    assert rb.confronta(_pr(), saida)["bateu"]


def test_acusacao_certa_mas_veredito_divergente_nao_conta():
    """Julgou o defeito e disse REFUTADO. Isso e' sinal sobre o produto, e o
    runner tem que distinguir de "nem chegou ao advogado"."""
    saida = _saida(brutas=[("a1", "TOCTOU na insercao de membro")],
                   julgadas=["a1"], veredictos=[("a1", "REFUTADO")])
    r = rb.confronta(_pr(), saida)
    assert not r["bateu"]
    assert r["achados"][0]["julgaram"] == 1, "foi julgado -- nao e' falha de ranking"


def test_acusado_mas_fora_do_top_n_e_falha_de_ranking():
    """O caso real de 15/08 com --top-n 3: oito nomearam o race, nenhuma entrou."""
    saida = _saida(brutas=[("a1", "TOCTOU entre checagem e insert"),
                           ("a2", "concorrencia permite duplicata")],
                   julgadas=[], veredictos=[])
    r = rb.confronta(_pr(pistas=["toctou", "concorrencia"]), saida)
    assert not r["bateu"]
    a = r["achados"][0]
    assert a["acusaram"] == 2 and a["julgaram"] == 0


# ------------------------------------------------------ os DOIS defeitos do PR 3

DOIS = _pr(
    ramo="pr/reconvite-de-membro", nome="TOCTOU", pistas=["toctou", "duplicat"],
    **{"⚠️_defeito_acidental": {"nome": "campo fora do contrato",
                                "esperado": "PROVADO",
                                "pistas": ["convidado_por"]}})


def test_o_pr_com_dois_defeitos_declara_os_dois():
    alvos = rb.alvos_do(DOIS)
    assert len(alvos) == 2
    assert alvos[1]["nome"] == "campo fora do contrato"


def test_achar_so_um_dos_dois_NAO_e_acerto():
    """🚨 O conserto pedido. Antes: um PROVADO qualquer dava o PR por acertado."""
    saida = _saida(brutas=[("a1", "TOCTOU entre checagem e insert"),
                           ("a2", "convidado_por vaza na resposta")],
                   julgadas=["a1"], veredictos=[("a1", "PROVADO")])
    r = rb.confronta(DOIS, saida)
    assert r["contagem"] == {"PROVADO": 1}
    assert not r["bateu"], "achou o TOCTOU e nao o acidental -- nao e' 'bateu'"
    assert [x["bateu"] for x in r["achados"]] == [True, False]


def test_achar_os_dois_e_acerto():
    saida = _saida(brutas=[("a1", "TOCTOU entre checagem e insert"),
                           ("a2", "convidado_por vaza na resposta")],
                   julgadas=["a1", "a2"],
                   veredictos=[("a1", "PROVADO"), ("a2", "PROVADO")])
    r = rb.confronta(DOIS, saida)
    assert r["bateu"]
    assert all(x["bateu"] for x in r["achados"])


# ------------------------------------------------------ pistas contra o id/categoria

def test_pista_nao_casa_com_a_categoria_nem_com_o_id_da_acusacao():
    """🚨 O criterio antigo casava contra `str(a)`, o dicionario inteiro.

    Ali dentro vao `"id": "injection_01"` e `"categoria": "injection"`. Uma
    pista como "inject" casaria com TODA acusacao da lente de injection, em
    qualquer PR -- medindo de qual promotor a acusacao veio, nao do que ela
    fala. Metrica medindo outra coisa, dentro do instrumento de medicao.
    """
    a = {"id": "injection_01", "categoria": "injection",
         "local": "app/main.py:1", "hipotese": "paginacao sem limite"}
    assert "injection" not in rb._texto(a)
    saida = {"brutas": [a], "acusacoes": [{"id": "injection_01"}],
             "veredictos": [{"id": "injection_01", "veredito": "PROVADO"}]}
    r = rb.confronta(_pr(pistas=["inject"]), saida)
    assert not r["bateu"], "casou com a categoria, nao com o conteudo"


def test_texto_inclui_a_regra_do_arbitro_quando_ha():
    a = {"hipotese": "h", "local": "l", "provado_se": "p",
         "arbitro": {"regra": "adicionar membro e' idempotente", "onde": "d:1"}}
    assert "idempotente" in rb._texto(a)


def test_arbitro_nulo_nao_quebra_o_texto():
    assert rb._texto({"hipotese": "h", "arbitro": None})


# ------------------------------------------------------- defeito sem gabarito

def test_defeito_sem_pistas_levanta_em_vez_de_pontuar_generoso():
    """Ausencia de gabarito e' erro de operador, nao licenca.

    Cair no criterio antigo aqui devolveria o falso acerto pela porta dos
    fundos, e em silencio -- que e' a forma que este bug tem toda vez.
    """
    saida = _saida(brutas=[("a1", "qualquer coisa")], julgadas=["a1"],
                   veredictos=[("a1", "PROVADO")])
    with pytest.raises(SystemExit, match="pistas"):
        rb.confronta(_pr(pistas=[]), saida)


# ------------------------------------------------------- o controle negativo

def test_pr_limpo_com_zero_condenacao_bate():
    limpo = {"ramo": "pr/limpo", "esperado": "REFUTADO", "defeito": None}
    saida = _saida(brutas=[("a1", "x")], julgadas=["a1"],
                   veredictos=[("a1", "REFUTADO"), ("a2", "REFUTADO")])
    r = rb.confronta(limpo, saida)
    assert r["bateu"] and r["achados"] == []


def test_pr_limpo_com_qualquer_condenacao_nao_bate():
    limpo = {"ramo": "pr/limpo", "esperado": "REFUTADO", "defeito": None}
    saida = _saida(brutas=[("a1", "x")], julgadas=["a1"],
                   veredictos=[("a1", "PROVADO")])
    assert not rb.confronta(limpo, saida)["bateu"]


def test_inconclusivo_no_pr_limpo_nao_e_condenacao():
    """INCONCLUSIVO nao e' REFUTADO, mas tambem nao e' condenacao: o criterio do
    controle negativo e' ausencia de PROVADO, e somar os dois inverteria a
    decisao no PR que mede precisao."""
    limpo = {"ramo": "pr/limpo", "esperado": "REFUTADO", "defeito": None}
    saida = _saida(brutas=[("a1", "x")], julgadas=["a1"],
                   veredictos=[("a1", "INCONCLUSIVO")])
    assert rb.confronta(limpo, saida)["bateu"]


# ------------------------------------------------- o gabarito de verdade em disco

def test_todo_defeito_do_gabarito_real_tem_pistas():
    """Trava mecanica: PR novo sem pistas passa a derrubar a suite, em vez de
    virar um acerto generoso na proxima varredura de US$2."""
    for pr in rb.gabarito():
        for alvo in rb.alvos_do(pr):
            assert alvo["pistas"], f"{pr['ramo']}: {alvo['nome']!r} sem pistas"


def test_o_gabarito_real_tem_os_quatro_desfechos_previstos():
    """Se os quatro derem a mesma coisa, o instrumento esta quebrado -- e' o
    criterio de bancada calibrada, e ele mora no arquivo, nao na lembranca."""
    prs = rb.gabarito()
    assert len(prs) == 4
    assert sum(1 for p in prs if not p.get("defeito")) == 1, "um controle negativo"
    assert sum(len(rb.alvos_do(p)) for p in prs) == 4, "3 PRs, 4 defeitos plantados"
