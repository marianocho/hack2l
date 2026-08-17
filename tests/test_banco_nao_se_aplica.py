"""NAO SE APLICA nao e' NAO MEDIDO -- e o alarme falso e' o risco aqui.

🚨 Nas tres rodadas do `pallets/flask#6095`, o parecer fechou assim:

    - **NAO MEDIDO**: o retrato do banco falhou. `open ...\\docker-compose.yml:
      The system cannot find the file specified.`
    - Isto **nao** e' 'nao houve efeito'. A rodada pode ter criado ou removido
      linhas, e este parecer nao sabe.

A ultima frase e' FALSA naquele contexto. Sem `app.api` o `http_request`
recusa; sem o bloco `codigo` a suite nao roda; nao ha banco declarado. Nenhuma
via daquela rodada alcancava um banco, e o retrato falhou so' porque procurava
um compose que o Flask nao tem.

⚠️ Por que isto importa mais do que parece: esta e' a linha que avisa que o
agente mexeu em dado vivo. O deslocamento de 14/08 (`shares` 0 -> 3) so'
apareceu porque um humano desconfiou e anotou o estado a mao. Uma linha de
alarme que dispara em TODA rodada de terceiro ensina o leitor a pular
exatamente ela -- e ai a guarda morre de excesso, que da no mesmo que morrer de
falta.

E' a quarta instancia do padrao "facilidade que assume o layout do desafio",
depois de contas, `APP_API_URL` e `app/api/tests`. Mesmo conserto de sempre:
criterio derivado do que o projeto declarou.
"""
import json

import pytest

from veredito import config as cfg
from veredito import juiz
from veredito import orquestrador


@pytest.fixture
def rodada(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "RODADA", tmp_path)
    return tmp_path


@pytest.fixture
def sem_nada(monkeypatch):
    """Um PR de terceiro: nem app, nem banco, nem suite declarados."""
    monkeypatch.setattr(cfg, "ALCANCA_BANCO", False)
    monkeypatch.setattr(cfg, "APP_EM_BANCO_DESCARTAVEL", False)


# ------------------------------------------- a guarda, vista falhando

def test_sem_via_para_banco_NAO_TIRA_RETRATO(rodada, sem_nada, monkeypatch):
    """Nao basta rotular depois: nao pode nem tentar.

    Dois `docker compose` levam segundos para descobrir que nao ha compose, e o
    resultado deles seria descartado de qualquer jeito.
    """
    def nao_pode(*a, **k):
        raise AssertionError("tirou retrato de um projeto que nao declara banco")

    monkeypatch.setattr(orquestrador.contencao_app, "retrato_do_banco", nao_pode)
    d = orquestrador._registra_efeito_no_banco({})
    assert d["aplicavel"] is False


def test_o_parecer_NAO_DIZ_que_pode_ter_criado_linha(rodada, sem_nada, monkeypatch):
    """A frase do NAO MEDIDO e' falsa aqui, e e' a que treina o leitor a pular."""
    monkeypatch.setattr(orquestrador.contencao_app, "retrato_do_banco", lambda *a, **k: {})
    orquestrador._registra_efeito_no_banco({})

    texto = "\n".join(juiz._secao_efeito_no_banco())
    assert "NAO SE APLICA" in texto
    assert "pode ter criado" not in texto, (
        "o parecer alarma sobre linhas que nenhuma ferramenta desta rodada "
        "poderia ter criado")


def test_nao_se_aplica_APARECE_no_parecer(rodada, sem_nada, monkeypatch):
    """Sumir com a secao faria 'sem secao' significar duas coisas diferentes.

    Foi assim que o `limpo` mudo comecou em 15/08. Ausencia de observacao e'
    dita, nunca omitida -- mesma doutrina do terceiro estado.
    """
    monkeypatch.setattr(orquestrador.contencao_app, "retrato_do_banco", lambda *a, **k: {})
    orquestrador._registra_efeito_no_banco({})
    texto = "\n".join(juiz._secao_efeito_no_banco())
    assert "EFEITO NO BANCO" in texto and "NAO MEDIDO" in texto, (
        "nao diz a diferenca entre 'nao se aplica' e 'nao consegui medir'")


# ------------------------------------------- e a metade que NAO pode afrouxar

def test_com_banco_declarado_o_retrato_que_falha_continua_NAO_MEDIDO(rodada, monkeypatch):
    """🚫 O controle. Sem ele os testes acima passariam com a guarda desligada.

    Projeto QUE TEM banco e cujo retrato falhou continua gritando -- e' o
    conserto de 16/08, e ele custou seis rodadas gravando `limpo: true` sem
    terem olhado.
    """
    monkeypatch.setattr(cfg, "ALCANCA_BANCO", True)
    monkeypatch.setattr(cfg, "APP_EM_BANCO_DESCARTAVEL", False)
    monkeypatch.setattr(orquestrador.contencao_app, "retrato_do_banco",
                        lambda *a, **k: {"banco": "kb", "erro": "psql: recusou"})
    orquestrador._registra_efeito_no_banco({"banco": "kb", "erro": "psql: recusou"})

    texto = "\n".join(juiz._secao_efeito_no_banco())
    assert "NAO MEDIDO" in texto and "pode ter criado" in texto, (
        "retrato que falhou num projeto COM banco parou de alarmar")


def test_contencao_ligada_sem_banco_LEVANTA(rodada, sem_nada, monkeypatch):
    """Pedir contencao de um banco que nao existe e' engano do operador.

    Seguir calado deixaria alguem acreditando que ha uma copia descartavel no
    ar. Mesma leitura do ramo de 16/08 para contencao + retrato falhando.
    """
    monkeypatch.setattr(cfg, "APP_EM_BANCO_DESCARTAVEL", True)
    monkeypatch.setattr(orquestrador.contencao_app, "retrato_do_banco", lambda *a, **k: {})
    with pytest.raises(orquestrador.contencao_app.ContencaoFalhou):
        orquestrador._registra_efeito_no_banco({})


def test_alcanca_banco_liga_com_QUALQUER_uma_das_tres():
    """Conservador de proposito: uma via basta para a medicao voltar.

    Um projeto pode declarar `codigo` e nao declarar `banco` -- e ai a suite
    dele roda contra o banco descartavel, que E' um banco. Exigir as tres
    (um `and`) silenciaria a medicao justo onde ha escrita.

    ⚠️ A asserção e' sobre a EXPRESSAO do config, e nao sobre `or` aplicado a
    literais aqui dentro: isso passaria com o criterio real trocado por `and`,
    e teste que acusa a coisa errada nao vale mais que teste nenhum.
    """
    import ast
    import inspect

    fonte = inspect.getsource(cfg)
    atrib = next(n for n in ast.walk(ast.parse(fonte))
                 if isinstance(n, ast.Assign)
                 and any(getattr(t, "id", "") == "ALCANCA_BANCO" for t in n.targets))
    # bool(<X> or <Y> or <Z>)
    dentro = atrib.value.args[0]
    assert isinstance(dentro, ast.BoolOp) and isinstance(dentro.op, ast.Or), (
        "o criterio deixou de ser 'qualquer uma das vias' -- com `and` ele "
        "silenciaria a medicao em projeto que declara so' o bloco `codigo`")
    termos = {ast.unparse(v) for v in dentro.values}
    assert termos == {"TEM_APP", "TEM_PROVA_DIFERENCIAL", "_banco.get('nome')"}, (
        f"as vias ate' um banco mudaram: {termos}")


def test_criterio_nao_pergunta_ao_proprio_chumbado():
    """`BANCO_APP_ORIGEM` cai em `kb` -- o banco do desafio -- quando o projeto
    nao declara. Derivar o criterio dele seria perguntar ao chumbado que ele
    existe para nao repetir, e `ALCANCA_BANCO` seria SEMPRE verdadeiro.
    """
    import inspect
    fonte = inspect.getsource(cfg)
    i = fonte.index("ALCANCA_BANCO = ")
    linha = fonte[i:fonte.index("\n", i)]
    assert "BANCO_APP_ORIGEM" not in linha, (
        "o criterio pergunta ao valor que tem fallback para o desafio")
    assert '_banco.get("nome")' in linha


def test_json_da_rodada_guarda_a_causa(rodada, sem_nada, monkeypatch):
    """O parecer rola; o arquivo fica. Quem auditar amanha precisa do motivo."""
    monkeypatch.setattr(orquestrador.contencao_app, "retrato_do_banco", lambda *a, **k: {})
    orquestrador._registra_efeito_no_banco({})
    d = json.loads((rodada / "efeito_no_banco.json").read_text(encoding="utf-8"))
    assert d["delta"]["aplicavel"] is False
    assert "veredito.yml" in d["delta"]["causa"]
