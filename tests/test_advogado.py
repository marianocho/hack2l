"""Testes do parse do veredicto.

Nenhum chama a API. O que se testa aqui e' a fronteira entre o texto do modelo e
o dado que o juiz le -- e' o ponto onde uma acusacao provada pode sumir do
parecer sem ninguem perceber, porque some parecendo rigor.
"""

from types import SimpleNamespace

import pytest

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


# ------------------------------------------------- a causa de uma recusa cyber
# 2 das 10 acusacoes da rodada das 12h15 morreram em recusa do classificador --
# a categoria carro-chefe entre elas. "recusa do classificador" e' verdade e nao
# diz o que fazer; estes testes travam a distincao que diz.

def _msg(categoria=None, recomendado=None, fallback_rodou=False, sinal="usage",
         modelo=None):
    """`sinal` escolhe POR ONDE o fallback se anuncia. Sao tres vias, e o nosso
    caminho e' streaming, onde a canonica (usage.iterations) nao aparece."""
    det = SimpleNamespace(category=categoria, recommended_model=recomendado)
    iteracoes = [SimpleNamespace(type="message")]
    conteudo = [SimpleNamespace(type="text")]
    modelo = modelo or "claude-opus-5"
    if fallback_rodou:
        if sinal == "usage":
            iteracoes.append(SimpleNamespace(type="fallback_message"))
        elif sinal == "bloco":
            conteudo.append(SimpleNamespace(type="fallback"))
        elif sinal == "modelo":
            modelo = "claude-opus-4-8"
    return SimpleNamespace(
        stop_reason="refusal", stop_details=det, model=modelo, content=conteudo,
        usage=SimpleNamespace(iterations=iteracoes),
    )


def test_recusa_sem_fallback_tentado_aponta_o_modelo_sugerido():
    """`recommended_model` preenchido = o fallback nem rodou (rate limit ou
    sobrecarga). E' o caso acionavel: da' pra tentar de novo direto nele."""
    causa = adv._diagnostico_da_recusa(_msg("cyber", recomendado="claude-opus-4-8"))
    assert "cyber" in causa
    assert "NAO foi tentado" in causa and "claude-opus-4-8" in causa


@pytest.mark.parametrize("sinal", ["usage", "bloco", "modelo"])
def test_recusa_com_fallback_rodado_diz_que_a_cadeia_toda_negou(sinal):
    """As tres vias contam. Medido em 08/08 13h25: pelo tool_runner com
    stream=True a recusa NAO trouxe usage.iterations, entao depender so' da via
    canonica fazia todo fallback parecer "nao aconteceu"."""
    causa = adv._diagnostico_da_recusa(_msg("cyber", fallback_rodou=True, sinal=sinal))
    assert "cadeia inteira negou" in causa
    assert "NAO foi tentado" not in causa


def test_recusa_sem_sinal_nenhum_admite_que_nao_sabe():
    """Nao inventar causa. Inconclusivo sobre o proprio inconclusivo e' honesto;
    chutar 'a cadeia recusou' seria afirmar o que nao foi observado."""
    causa = adv._diagnostico_da_recusa(_msg("bio"))
    assert "nenhum dos tres sinais" in causa
    assert "nao da' para afirmar" in causa


def test_recusa_sem_stop_details_nao_levanta():
    msg = SimpleNamespace(stop_reason="refusal", stop_details=None, usage=None)
    assert adv._diagnostico_da_recusa(msg).startswith("recusa do classificador")


# ------------------- desfecho das ferramentas (13/08: era prefixo de string)
#
# Ate' 13/08 quem decidia se uma ferramenta falhou era `startswith("ERRO")` na
# saida. Quem depende disso e' a R3b, e o docstring da funcao ja admitia:
# "uma ferramenta que falhe sem esse prefixo passa batida". Agora quem sabe que
# falhou e' quem falhou -- a ferramenta registra, e o texto e' so' o que o
# modelo le.

from veredito import ferramentas as f
from veredito.advogado import _conta_blocos, _consolida_ferramentas


def _res(*textos, is_error=None):
    return {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": f"t{i}", "content": t,
         **({"is_error": is_error} if is_error is not None else {})}
        for i, t in enumerate(textos)
    ]}


@pytest.fixture(autouse=True)
def _artefatos_isolados(tmp_path, monkeypatch):
    """O registro grava em disco a CADA chamada -- e' o que faz rodada morta no
    meio nao perder a contagem. Sem isolar, estes testes escreveriam
    `chamadas.json` no artefatos/ do repo, e teste que suja a arvore acaba em
    commit acidental."""
    monkeypatch.setattr(f.cfg, "ARTEFATOS", tmp_path)


def _registra(id_acusacao, *desfechos):
    """Roda o caminho REAL de registro: marca falha e fecha a chamada."""
    f.define_acusacao(id_acusacao)
    for ok in desfechos:
        f._abre_chamada()
        if not ok:
            f._marca_falha("qualquer texto")
        f._fecha_chamada("read_file", "saida")


# ------------------------------------------------------------- a regressao

def test_falha_sem_o_prefixo_erro_ainda_conta_como_falha():
    """🚨 O caso que era INVISIVEL, e o motivo deste conserto existir.

    Ferramenta que falha devolvendo texto sem `ERRO` era contada como SUCESSO.
    Com isso a R3b -- PROVADO/REFUTADO com zero ferramenta boa -> INCONCLUSIVO
    -- ficava muda exatamente onde precisava falar, e o resultado e' absolvicao
    ou condenacao sem observacao nenhuma por tras.
    """
    f.define_acusacao("a_sem_prefixo")
    f._abre_chamada()
    f._marca_falha("worktree sumiu no meio da leitura")   # sem 'ERRO'
    f._fecha_chamada("read_file", "conteudo qualquer, tambem sem ERRO")

    v = {}
    _consolida_ferramentas(v, "a_sem_prefixo", blocos=1)
    assert (v["ferramentas_ok"], v["ferramentas_erro"]) == (0, 1)


def test_o_caso_real_todas_falhando():
    """A rodada de 10/08: worktree corrompida, 5 chamadas, 5 RuntimeError.

    O advogado devolveu PROVADO com todas falhando. E' a rodada que comprou a
    R3b, e continua tendo que dar (0, 5).
    """
    _registra("a_10ago", False, False, False, False, False)
    v = {}
    _consolida_ferramentas(v, "a_10ago", blocos=5)
    assert (v["ferramentas_ok"], v["ferramentas_erro"]) == (0, 5)


def test_sucesso_e_falha_misturados():
    _registra("a_mistura", True, False, True)
    v = {}
    _consolida_ferramentas(v, "a_mistura", blocos=3)
    assert (v["ferramentas_ok"], v["ferramentas_erro"]) == (2, 1)


# --------------------------------------------- o vao entre bloco e registro

def test_bloco_sem_registro_conta_como_erro():
    """Chamada que a API rejeitou antes de chegar ao nosso codigo.

    Ela devolve resultado ao modelo e NAO gera registro -- nosso codigo nunca
    rodou. Contar como sucesso seria inventar observacao que nao houve; o
    default tem que cair para o lado do INCONCLUSIVO.
    """
    _registra("a_vao", True)
    v = {}
    _consolida_ferramentas(v, "a_vao", blocos=3)   # 1 registrada, 3 devolvidas
    assert (v["ferramentas_ok"], v["ferramentas_erro"]) == (1, 2)


def test_registro_a_mais_que_bloco_nao_vira_erro_negativo():
    _registra("a_negativo", True, True)
    v = {}
    _consolida_ferramentas(v, "a_negativo", blocos=0)
    assert (v["ferramentas_ok"], v["ferramentas_erro"]) == (2, 0)


def test_consolida_e_idempotente():
    """Ela roda DENTRO do laco: sair por recusa, timeout ou teto nao pode
    multiplicar a contagem. Atribui, nunca acumula."""
    _registra("a_idem", True, False)
    v = {}
    for _ in range(4):
        _consolida_ferramentas(v, "a_idem", blocos=2)
    assert (v["ferramentas_ok"], v["ferramentas_erro"]) == (1, 1)


def test_julgar_a_mesma_acusacao_de_novo_nao_soma_a_tentativa_anterior():
    _registra("a_repetida", True, True, True)
    _registra("a_repetida", False)      # define_acusacao zera o registro
    v = {}
    _consolida_ferramentas(v, "a_repetida", blocos=1)
    assert (v["ferramentas_ok"], v["ferramentas_erro"]) == (0, 1)


# ------------------------------------------------------------ contagem crua

# ------------------------------------------- pre-voo da API (14/08)

def _erro_api(mensagem):
    def _explode(*a, **k):
        raise RuntimeError(mensagem)
    return _explode


def test_sonda_distingue_chave_de_saldo(monkeypatch):
    """Consertos DIFERENTES: chave rejeitada se resolve gerando outra; saldo
    esgotado, nao. A mensagem crua da API nao ajuda quem esta com pressa."""
    monkeypatch.setattr(adv, "_cliente", _erro_api(
        "Error code: 401 - {'type': 'authentication_error'}"))
    ok, detalhe = adv.sonda_api()
    assert ok is False and "CHAVE" in detalhe

    monkeypatch.setattr(adv, "_cliente", _erro_api(
        "Error code: 400 - your credit balance is too low"))
    ok, detalhe = adv.sonda_api()
    assert ok is False and "SALDO" in detalhe


def test_sonda_nao_levanta_em_erro_desconhecido(monkeypatch):
    """Quem decide abortar e' o orquestrador. A sonda so' informa."""
    monkeypatch.setattr(adv, "_cliente", _erro_api("coisa que nunca vimos"))
    ok, detalhe = adv.sonda_api()
    assert ok is False and detalhe


def test_sonda_sem_chave_nem_tenta_a_rede(monkeypatch):
    monkeypatch.setattr(adv.cfg, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(adv, "_cliente", _erro_api("nao devia ter sido chamado"))
    ok, detalhe = adv.sonda_api()
    assert ok is False and "ausente" in detalhe


def test_sonda_gasta_um_token_so(monkeypatch):
    """Ela roda em TODA rodada. Se custasse, seria imposto sobre o pre-voo --
    que existe justamente para nao gastar."""
    pedidos = {}

    class _Fake:
        class messages:
            @staticmethod
            def create(**kw):
                pedidos.update(kw)
                return SimpleNamespace(usage=SimpleNamespace(input_tokens=9))

    monkeypatch.setattr(adv, "_cliente", lambda: _Fake())
    ok, _ = adv.sonda_api()
    assert ok is True
    assert pedidos["max_tokens"] == 1
    assert pedidos["model"] == adv.cfg.MODEL_PROMOTOR, "use o modelo barato"


def test_conta_blocos_so_conta_tool_result():
    assert _conta_blocos(_res("a", "b", "c")) == 3
    assert _conta_blocos({"role": "user", "content": [
        {"type": "text", "text": "nao e' resultado de ferramenta"}]}) == 0


def test_resposta_sem_ferramenta_nao_conta_nada():
    assert _conta_blocos(None) == 0
    assert _conta_blocos({"role": "user", "content": "texto"}) == 0
