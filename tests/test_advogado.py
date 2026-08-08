"""Testes do parse do veredicto.

Nenhum chama a API. O que se testa aqui e' a fronteira entre o texto do modelo e
o dado que o juiz le -- e' o ponto onde uma acusacao provada pode sumir do
parecer sem ninguem perceber, porque some parecendo rigor.
"""

from veredito import advogado as adv


# ------------------------------------------- a regressao medida em 08/08 12h15

# Saida real do advogado na acusacao correcao_01. A prosa cita `{email}` e a
# rota `/documents/{id}/share` ANTES do JSON. O regex ganancioso casava do
# primeiro `{` ate o ultimo, o json.loads quebrava, e um PROVADO com artefato no
# disco virava INCONCLUSIVO.
_SAIDA_REAL = (
    "PROVADO por teste diferencial: o email e' interpolado com f-string em "
    "`SELECT id FROM users WHERE email = '{email}'`, e o payload "
    "`nobody@test.dev' OR '1'='1` retornou 201. O app em execucao ainda e' o "
    "commit base (a rota `/documents/{id}/share` responde 404 default), entao "
    "nao foi possivel provar ponta a ponta pela API.\n\n"
    '{"veredito": "PROVADO", "severidade": "MEDIA", "prova_ponta_a_ponta": false, '
    '"motivo": "SQL injection no teste diferencial", "conserto": "consulta parametrizada"}'
)


def test_chave_em_prosa_nao_engole_o_veredito():
    v = adv._parse_veredicto(_SAIDA_REAL)
    assert v["veredito"] == "PROVADO", "o parse perdeu um PROVADO por causa de `{email}`"
    assert v["severidade"] == "MEDIA"
    assert v["conserto"]


def test_cerca_de_codigo_em_volta_do_json():
    """O motivo original do fallback existir. Continua valendo."""
    texto = '```json\n{"veredito": "REFUTADO", "motivo": "passa nos dois lados"}\n```'
    assert adv._parse_veredicto(texto)["veredito"] == "REFUTADO"


def test_json_puro_sem_nada_em_volta():
    v = adv._parse_veredicto('{"veredito": "INCONCLUSIVO", "motivo": "docker fora"}')
    assert (v["veredito"], v["motivo"]) == ("INCONCLUSIVO", "docker fora")


def test_o_ultimo_veredito_ganha_do_exemplo_citado_antes():
    """O advogado as vezes reproduz o formato pedido antes de responder. O que
    vale e' o que ele decidiu, nao o exemplo que ele copiou."""
    texto = (
        'O formato pedido era {"veredito": "PROVADO|REFUTADO", "severidade": "..."}.\n'
        'Minha conclusao:\n{"veredito": "REFUTADO", "motivo": "o teste passou nos dois lados"}'
    )
    v = adv._parse_veredicto(texto)
    assert v["veredito"] == "REFUTADO"
    assert v["motivo"] == "o teste passou nos dois lados"


def test_chaves_dentro_das_strings_do_proprio_json():
    texto = (
        '{"veredito": "PROVADO", "motivo": "a rota /documents/{id}/share aceita '
        '{\\"email\\": \\"x\\"} de qualquer um", "severidade": "ALTA"}'
    )
    v = adv._parse_veredicto(texto)
    assert v["veredito"] == "PROVADO"
    assert "{id}" in v["motivo"]


# ------------------------------------------------------------------- fallback

def test_sem_json_nenhum_vira_inconclusivo_com_a_saida_crua():
    """Terceiro estado: sem artefato nao ha prova, e nunca ha absolvicao. A saida
    crua e' o que permite reparsar depois sem re-rodar o advogado (~130s)."""
    v = adv._parse_veredicto("Nao consegui concluir, o docker caiu no meio.")
    assert v["veredito"] == "INCONCLUSIVO"
    assert "docker caiu" in v["saida_crua"]


def test_json_valido_sem_veredito_nao_conta_como_veredicto():
    v = adv._parse_veredicto('Resultado: {"severidade": "CRITICA", "motivo": "x"}')
    assert v["veredito"] == "INCONCLUSIVO"
    assert "saida_crua" in v


def test_json_quebrado_nao_levanta():
    v = adv._parse_veredicto('{"veredito": "PROVADO", "motivo": ')
    assert v["veredito"] == "INCONCLUSIVO"
