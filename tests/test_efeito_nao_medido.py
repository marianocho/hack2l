"""Retrato do banco que FALHOU nunca pode ler como "banco limpo".

🚨 O caso real, e ele durou seis rodadas. `_psql` chumbava `-U kb` -- as
credenciais do desafio. Contra a bancada, que usa `bancada`, todo retrato
falhava com `role "kb" does not exist`. O `erro` ficava gravado nos dois
retratos, e `delta_do_banco` lia so' `tabelas`: {} contra {}, nenhuma
diferenca, `limpo: True`.

Seis rodadas afirmaram nao ter tocado no banco do app sem terem conseguido
conectar nele uma vez. E a mensagem impressa era a MESMA do sucesso:
"efeito no banco: NENHUM".

E' o padrao de bug da casa na guarda que existe justamente porque o
`shares 0->3` de 14/08 "so' apareceu porque tiramos retrato a mao" -- e da
forma mais cara possivel, porque falha silenciosa aqui nao parece falha, parece
seguranca.

A doutrina aplicada e' a do terceiro estado: ausencia de observacao nunca e'
absolvicao. `medido: False` e' o INCONCLUSIVO do efeito no banco.
"""

import pytest

from veredito import config as cfg
from veredito import contencao_app as ca


def _ok(**tabelas):
    return {"banco": "app", "tabelas": dict(tabelas)}


def _falhou(msg='role "kb" does not exist'):
    """O formato exato que `retrato_do_banco` devolve quando o psql erra."""
    return {"erro": msg, "tabelas": {}}


# ------------------------------------------------- a guarda, vista falhando

@pytest.mark.parametrize("antes,depois", [
    (_falhou(), _falhou()),                 # o caso real: falhou nos dois lados
    (_falhou(), _ok(users=4)),              # so' o de antes
    (_ok(users=4), _falhou()),              # so' o de depois
])
def test_retrato_que_falhou_nunca_vira_limpo(antes, depois):
    d = ca.delta_do_banco(antes, depois)
    assert d["limpo"] is False, "falha de medicao lida como banco intacto"
    assert d["medido"] is False
    assert d["causa"], "sem a causa, o operador nao sabe o que consertar"


def test_o_caso_exato_das_seis_rodadas():
    """Regressao com o texto real do erro, para o defeito nao voltar disfarcado."""
    erro = ('psql: error: connection to server on socket "/var/run/postgresql/'
            '.s.PGSQL.5432" failed: FATAL:  role "kb" does not exist')
    d = ca.delta_do_banco({"erro": erro, "tabelas": {}}, {"erro": erro, "tabelas": {}})
    assert d["limpo"] is False
    assert "kb" in d["causa"]
    assert "TUDO" in d["nao_detecta"], (
        "o campo que declara o limite tem que dizer que nada foi medido"
    )


def test_medicao_boa_continua_dizendo_limpo():
    """O controle. Sem ele, `limpo: False` sempre passaria os testes acima."""
    d = ca.delta_do_banco(_ok(users=4, docs=5), _ok(users=4, docs=5))
    assert d["limpo"] is True and d["medido"] is True


def test_medicao_boa_ainda_detecta_criacao_e_remocao():
    d = ca.delta_do_banco(_ok(users=4, shares=0), _ok(users=3, shares=3))
    assert d["medido"] is True and d["limpo"] is False
    assert d["criadas"] == {"shares": 3}
    assert d["removidas"] == {"users": 1}
    assert d["houve_remocao"] is True


# ------------------------------------------------- a causa: nada chumbado

def test_psql_usa_as_credenciais_do_projeto_e_nao_as_do_desafio(monkeypatch):
    """Estrutural, pelo ARGV -- nao por substring no fonte.

    ⚠️ Procurar `-U kb` no arquivo casaria com o comentario que explica o
    conserto. Mesmo erro que ja custou tres travas neste projeto (o `kb` dentro
    de `kb_veredito_app`, o `override=True` dentro do comentario, e o
    `py -3.12` dentro da nota do encoding). A pergunta certa e' o que o comando
    EXECUTADO carrega.
    """
    visto = {}
    monkeypatch.setattr(cfg, "BANCO_USUARIO", "bancada")
    monkeypatch.setattr(cfg, "BANCO_SERVICO", "banco_do_cliente")

    class _R:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(ca.subprocess, "run",
                        lambda cmd, **k: (visto.update(cmd=cmd), _R())[1])
    ca._psql("qualquer", "select 1")

    cmd = visto["cmd"]
    assert "bancada" in cmd, f"nao usou BANCO_USUARIO: {cmd}"
    assert "banco_do_cliente" in cmd, f"nao usou BANCO_SERVICO: {cmd}"
    assert "kb" not in cmd, f"credencial do desafio chumbada: {cmd}"
