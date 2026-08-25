"""A escotilha do Bedrock legado, e por que ela nao e' equivalente ao Mantle.

MEDIDO em 20/08, construindo os dois clientes de verdade (sem rede, sem
credencial): `anthropic.AnthropicBedrock` -- o legado, por InvokeModel -- NAO
expoe `beta.messages.tool_runner`. O `lib/bedrock/_beta_messages.Messages`
define `create` e mais nada. O Mantle expoe, porque o `MantleBeta.messages`
devolve a classe de primeira parte.

Isso importa mais do que parece. O `tool_runner` E' o advogado: sem ele o loop
pensa -> ferramenta -> resultado -> decide nao existe. Com a escotilha ligada, a
chamada morreria com `AttributeError` dentro do `try` de `julga`, que converte
qualquer excecao em INCONCLUSIVO -- em TODA acusacao. A rodada terminaria com a
categoria carro-chefe vazia e o parecer parecendo rigoroso. E' o desfecho exato
que o terceiro estado existe para impedir, chegando pela porta da infraestrutura.

⚠️ O arquivo separado nao e' capricho: `tests/test_motor.py` veio da sessao de
19/08 e o protocolo das trilhas manda cada um criar o seu.
"""
from __future__ import annotations

import anthropic
import pytest

from veredito import motor


@pytest.fixture(autouse=True)
def motor_limpo(monkeypatch):
    monkeypatch.delenv("VEREDITO_BEDROCK_LEGADO", raising=False)
    monkeypatch.delenv("VEREDITO_MOTOR", raising=False)
    motor.esquece()
    yield
    motor.esquece()


# ------------------------------------------------ o fato medido, sem dublê
#
# Estes dois nao usam monkeypatch nenhum: constroem o cliente do SDK instalado e
# perguntam. Se o SDK mudar e o legado passar a ter `tool_runner`, o segundo cai
# -- e cair e' o comportamento certo, porque a guarda em `motor` deixaria de ter
# motivo. Trava que sobrevive ao fim do problema vira folclore.

def test_o_cliente_mantle_expoe_tool_runner():
    cli = anthropic.AnthropicBedrockMantle(aws_region="us-east-1", skip_auth=True)
    assert hasattr(cli.beta.messages, "tool_runner")


def test_o_cliente_legado_NAO_expoe_tool_runner():
    cli = anthropic.AnthropicBedrock(
        aws_access_key="x", aws_secret_key="y", aws_region="us-east-1")
    assert hasattr(cli.beta.messages, "create")
    assert not hasattr(cli.beta.messages, "tool_runner"), (
        "o SDK passou a expor tool_runner no cliente legado do Bedrock -- "
        "a perda declarada em motor._bedrock deixou de existir, remova-a")


# ------------------------------------------------------ o motor declara a perda

def _bedrock(monkeypatch, legado: bool):
    if legado:
        monkeypatch.setenv("VEREDITO_BEDROCK_LEGADO", "1")
    monkeypatch.setattr(motor, "_resolve_credenciais",
                        lambda: (True, "dublê", "us-east-1"))
    monkeypatch.setenv("VEREDITO_MOTOR", "bedrock")
    motor.esquece()
    return motor.ativo()


def test_bedrock_no_mantle_NAO_perde_tool_runner(monkeypatch):
    m = _bedrock(monkeypatch, legado=False)
    assert m.tem("tool_runner")
    # E a guarda consegue ficar QUIETA: no caminho normal ela nao diz nada.
    assert "tool_runner" not in " ".join(m.perdas())


def test_bedrock_legado_declara_a_perda_do_tool_runner(monkeypatch):
    m = _bedrock(monkeypatch, legado=True)
    assert not m.tem("tool_runner")
    assert "advogado" in " ".join(m.perdas()).lower()


def test_a_perda_do_legado_NAO_come_o_resto_da_mascara(monkeypatch):
    """A mascara nova nao pode alargar a antiga -- guarda que come demais e'
    tao ruim quanto guarda muda, e foi o `NAO MEDIDO` do banco."""
    m = _bedrock(monkeypatch, legado=True)
    assert not m.tem("task_budget") and not m.tem("fallback_de_recusa")
    kw = motor.ajusta_chamada(model="claude-opus-5", max_tokens=8,
                              output_config={"effort": "high"})
    assert kw["output_config"] == {"effort": "high"}, (
        "`effort` e' suportado no Bedrock e nao pode sair junto")


# --------------------------------------------------------- o pre-voo reprova

def test_pre_voo_REPROVA_no_legado_e_diz_como_sair(monkeypatch):
    _bedrock(monkeypatch, legado=True)
    bloco = motor.descreve()["motor"]
    assert bloco["ok"] is False, (
        "sem tool_runner nao ha' advogado: o pre-voo tem que barrar ANTES de a "
        "rodada gastar, nao virar mais uma linha de aviso")
    assert "VEREDITO_BEDROCK_LEGADO" in bloco["detalhe"]


def test_pre_voo_APROVA_no_mantle(monkeypatch):
    """O par da trava acima. Sem ele, `ok = False` fixo passaria as duas."""
    _bedrock(monkeypatch, legado=False)
    bloco = motor.descreve()["motor"]
    assert bloco["ok"] is True
    # A degradacao que NAO cancela continua sendo dita, e continua sendo ok.
    assert "task_budget" in bloco["detalhe"]


def test_a_escotilha_e_lida_num_lugar_so(monkeypatch):
    """O cliente construido e a perda declarada saem da MESMA leitura.

    A "chave em dois lugares" ja' custou quatro tentativas neste projeto: uma
    variavel lida em dois pontos diverge em silencio, e aqui a divergencia seria
    um motor que promete tool_runner e constroi o cliente que nao tem.
    """
    construidos = []
    monkeypatch.setattr(anthropic, "AnthropicBedrock",
                        lambda *a, **k: construidos.append("legado"))
    monkeypatch.setattr(anthropic, "AnthropicBedrockMantle",
                        lambda *a, **k: construidos.append("mantle"))

    for legado, esperado in ((True, "legado"), (False, "mantle")):
        construidos.clear()
        monkeypatch.delenv("VEREDITO_BEDROCK_LEGADO", raising=False)
        m = _bedrock(monkeypatch, legado=legado)
        motor.cliente()
        assert construidos == [esperado]
        # o cliente construido e a promessa do motor concordam
        assert m.tem("tool_runner") is (esperado == "mantle")
