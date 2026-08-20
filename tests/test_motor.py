"""A alternancia de provedor. NAO bate na rede -- nem na AWS, nem na Anthropic.

O que esta sob teste e' a decisao (`qual motor`) e a mascara (`o que aquele
motor nao aceita`), nunca a chamada. Os tres pontos de injecao sao:

    motor._ha_sinal_aws        a checagem barata de ambiente
    motor._resolve_credenciais a cadeia do boto3
    motor._FABRICAS            a construcao do cliente

🚨 Metade destes testes existe em PAR, e o par e' o teste de verdade.

"O Bedrock remove `task_budget`" passa sozinho com uma mascara que remove tudo.
So' junto com "a API direta MANTEM `task_budget`" e com "o Bedrock MANTEM
`effort`" e' que os tres afirmam alguma coisa: que a mascara remove exatamente o
que ela alega remover. Guarda que dispara sempre morre de excesso, e isso da' no
mesmo que nao existir -- foi o `NAO MEDIDO` do banco, em 17/08.
"""
from __future__ import annotations

import sys
import types

import pytest

from veredito import advogado
from veredito import motor


@pytest.fixture(autouse=True)
def motor_limpo(monkeypatch):
    """Cada teste comeca sem motor resolvido e sem AWS no ambiente.

    ⚠️ `ativo()` guarda o resultado de proposito (o motor nao pode oscilar no
    meio de uma rodada), entao sem este reset o primeiro teste decidiria por
    todos os outros.
    """
    for v in ("VEREDITO_MOTOR", "AWS_ACCESS_KEY_ID", "AWS_PROFILE",
              "AWS_DEFAULT_PROFILE", "AWS_ROLE_ARN", "AWS_REGION",
              "AWS_DEFAULT_REGION", "AWS_WEB_IDENTITY_TOKEN_FILE",
              "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
              "AWS_CONTAINER_CREDENTIALS_FULL_URI", "VEREDITO_BEDROCK_LEGADO"):
        monkeypatch.delenv(v, raising=False)
    motor.esquece()
    yield
    motor.esquece()


def com_aws(monkeypatch, regiao="us-east-1", metodo="env"):
    monkeypatch.setattr(motor, "_ha_sinal_aws", lambda: True)
    monkeypatch.setattr(motor, "_resolve_credenciais",
                        lambda: (True, f"credencial AWS via {metodo}, regiao {regiao}",
                                 regiao))


def sem_aws(monkeypatch, porque="a cadeia de credenciais do boto3 nao resolveu nada",
            sinal=False):
    monkeypatch.setattr(motor, "_ha_sinal_aws", lambda: sinal)
    monkeypatch.setattr(motor, "_resolve_credenciais", lambda: (False, porque, None))


# =========================================================== a escolha

def test_sem_sinal_de_aws_usa_a_api_direta(monkeypatch):
    sem_aws(monkeypatch)
    assert motor.ativo().nome == "anthropic"


def test_com_credencial_aws_usa_bedrock(monkeypatch):
    com_aws(monkeypatch)
    m = motor.ativo()
    assert m.nome == "bedrock"
    assert "us-east-1" in m.rotulo


def test_o_fallback_DIZ_por_que_caiu(monkeypatch):
    """Fallback limpo nao e' fallback mudo.

    "sem credencial AWS" manda quem le abrir o codigo para descobrir se faltava
    boto3, chave ou regiao -- e as tres tem consertos diferentes.
    """
    sem_aws(monkeypatch, porque="boto3 nao instalado (pip install boto3)", sinal=True)
    m = motor.ativo()
    assert m.nome == "anthropic"
    assert "boto3 nao instalado" in m.detalhe


def test_credencial_sem_regiao_nao_conta_como_credencial(monkeypatch):
    """Regiao ausente nao e' detalhe: o AnthropicAWS levanta na construcao, e o
    Bedrock cairia numa regiao que pode nem ter o modelo habilitado. Melhor cair
    para a API direta dizendo isso do que estourar no meio da rodada."""
    monkeypatch.setattr(motor, "_ha_sinal_aws", lambda: True)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFALSA")
    monkeypatch.setattr(motor, "_resolve_credenciais",
                        motor._resolve_credenciais.__wrapped__
                        if hasattr(motor._resolve_credenciais, "__wrapped__")
                        else motor._resolve_credenciais)
    # Sem AWS_REGION no ambiente e sem perfil, a resolucao real devolve False.
    ok, porque, _ = motor._resolve_credenciais()
    if ok:
        pytest.skip("esta maquina tem AWS_REGION configurada de verdade")
    assert "AWS_REGION" in porque or "boto3" in porque


def test_sem_boto3_e_ausencia_e_nao_erro(monkeypatch):
    """Maquina sem boto3 nao pode quebrar a rodada -- ela roda pela API direta.

    Mesma doutrina do `veredito.yml` ausente: limite honesto, dito em voz alta.
    """
    monkeypatch.setattr(motor, "_ha_sinal_aws", lambda: True)
    monkeypatch.setitem(sys.modules, "boto3", None)  # `import boto3` -> ImportError
    ok, porque, _ = motor._resolve_credenciais()
    assert ok is False
    assert "boto3" in porque
    assert motor.ativo().nome == "anthropic"


# ------------------------------------------- precedencia e engano do operador

def test_variavel_de_ambiente_vence_a_deteccao(monkeypatch):
    """Precedencia: variavel > deteccao. A mesma do veredito.yml."""
    com_aws(monkeypatch)
    monkeypatch.setenv("VEREDITO_MOTOR", "anthropic")
    assert motor.ativo().nome == "anthropic"


def test_aws_forcado_escolhe_claude_platform_e_nao_bedrock(monkeypatch):
    com_aws(monkeypatch)
    monkeypatch.setenv("VEREDITO_MOTOR", "aws")
    assert motor.ativo().nome == "aws"


def test_motor_forcado_sem_credencial_LEVANTA(monkeypatch):
    """🚨 O teste central do modulo. ERRADO NAO E' AUSENTE.

    Quem escreveu VEREDITO_MOTOR=bedrock esta gastando credito da AWS de
    proposito. Cair calado para a API direta faturaria a rodada na conta errada
    e a rodada pareceria perfeita -- exatamente a classe de falha que este
    produto existe para impedir. Ausencia e' limite honesto; engano do operador
    nao se resolve seguindo com metade dele.
    """
    sem_aws(monkeypatch, porque="a cadeia de credenciais do boto3 nao resolveu nada")
    monkeypatch.setenv("VEREDITO_MOTOR", "bedrock")
    with pytest.raises(RuntimeError) as e:
        motor.ativo()
    # A causa junto, sempre -- e o caminho de saida.
    assert "boto3 nao resolveu nada" in str(e.value)
    assert "VEREDITO_MOTOR=anthropic" in str(e.value)


def test_motor_desconhecido_levanta(monkeypatch):
    monkeypatch.setenv("VEREDITO_MOTOR", "openai")
    with pytest.raises(ValueError, match="nao existe"):
        motor.ativo()


def test_forcado_nao_depende_do_sinal_barato(monkeypatch):
    """O atalho de `_ha_sinal_aws` e' otimizacao do modo `auto`. No modo forcado
    a cadeia do boto3 roda sempre -- credencial pode vir de perfil de instancia,
    que nao deixa sinal nenhum no ambiente."""
    monkeypatch.setattr(motor, "_ha_sinal_aws", lambda: False)
    monkeypatch.setattr(motor, "_resolve_credenciais",
                        lambda: (True, "credencial AWS via iam-role, regiao sa-east-1",
                                 "sa-east-1"))
    monkeypatch.setenv("VEREDITO_MOTOR", "bedrock")
    assert motor.ativo().nome == "bedrock"


def test_a_resolucao_nao_oscila_no_meio_da_rodada(monkeypatch):
    sem_aws(monkeypatch)
    primeiro = motor.ativo()
    com_aws(monkeypatch)          # o ambiente muda embaixo
    assert motor.ativo() is primeiro


# =========================================================== nada de rede

def test_sem_sinal_o_boto3_nem_e_chamado(monkeypatch):
    """🚨 `boto3.Session().get_credentials()` termina no IMDS, que numa maquina
    que nao e' EC2 e' uma conexao para 169.254.169.254 morrendo no timeout.

    Sem esta trava, a deteccao automatica poria um passo de REDE no caminho de
    toda rodada -- inclusive as que nunca quiseram AWS.
    """
    def explode():
        raise AssertionError("_resolve_credenciais foi chamada sem sinal de AWS")

    monkeypatch.setattr(motor, "_ha_sinal_aws", lambda: False)
    monkeypatch.setattr(motor, "_resolve_credenciais", explode)
    assert motor.ativo().nome == "anthropic"


def test_o_sinal_barato_nao_toca_a_rede(monkeypatch):
    """Ele so' le variavel de ambiente e existencia de arquivo."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFALSA")
    assert motor._ha_sinal_aws() is True


def test_cliente_vem_da_fabrica_do_motor_ativo(monkeypatch):
    com_aws(monkeypatch)
    marcas = []
    monkeypatch.setattr(motor, "_FABRICAS", {
        "anthropic": lambda: marcas.append("anthropic") or "cli_anthropic",
        "aws": lambda: marcas.append("aws") or "cli_aws",
        "bedrock": lambda: marcas.append("bedrock") or "cli_bedrock",
    })
    assert motor.cliente() == "cli_bedrock"
    assert marcas == ["bedrock"]


# =========================================================== o id do modelo

def test_modelo_traduzido_no_bedrock(monkeypatch):
    com_aws(monkeypatch)
    assert motor.modelo("claude-opus-5") == "anthropic.claude-opus-5"


def test_modelo_intacto_na_api_direta(monkeypatch):
    sem_aws(monkeypatch)
    assert motor.modelo("claude-opus-5") == "claude-opus-5"


def test_modelo_intacto_no_claude_platform_on_aws(monkeypatch):
    """Ela e' operada pela Anthropic: os ids sao os de sempre, SEM prefixo.
    Prefixar aqui seria copiar a regra do vizinho errado."""
    com_aws(monkeypatch)
    monkeypatch.setenv("VEREDITO_MOTOR", "aws")
    assert motor.modelo("claude-opus-5") == "claude-opus-5"


def test_perfil_de_inferencia_nao_e_prefixado_duas_vezes(monkeypatch):
    """`us.anthropic.claude-opus-5` e' id legitimo do Bedrock. Prefixar de novo
    geraria `anthropic.us.anthropic...` -- um 404 que se le como "modelo nao
    habilitado na conta" e manda o operador procurar no console errado."""
    com_aws(monkeypatch)
    for id_ in ("anthropic.claude-opus-5", "us.anthropic.claude-opus-5",
                "eu.anthropic.claude-haiku-4-5"):
        assert motor.modelo(id_) == id_


# =========================================================== a mascara

CHAMADA = dict(
    model="claude-opus-5",
    max_tokens=64000,
    stream=True,
    thinking={"type": "adaptive"},
    output_config={"effort": "high",
                   "task_budget": {"type": "tokens", "total": 30000}},
    betas=["task-budgets-2026-03-13", "server-side-fallback-2026-07-01"],
    fallbacks="default",
)


def test_api_direta_mantem_task_budget_e_fallback(monkeypatch):
    """🚨 A METADE QUE ACUSA MASCARA LARGA DEMAIS.

    Sem este par, uma mascara que removesse tudo em todo motor passaria nos
    testes de remocao abaixo e mataria o `task_budget` tambem na API direta,
    que o suporta. E' a mesma razao de a prova diferencial rodar nos dois lados.
    """
    sem_aws(monkeypatch)
    saida = motor.ajusta_chamada(**CHAMADA)
    assert saida["output_config"]["task_budget"] == {"type": "tokens", "total": 30000}
    assert saida["fallbacks"] == "default"
    assert set(saida["betas"]) == set(CHAMADA["betas"])
    assert saida["model"] == "claude-opus-5"


def test_bedrock_remove_task_budget_e_a_beta_dele(monkeypatch):
    com_aws(monkeypatch)
    saida = motor.ajusta_chamada(**CHAMADA)
    assert "task_budget" not in saida["output_config"]
    assert "task-budgets-2026-03-13" not in saida.get("betas", [])


def test_bedrock_remove_fallback_e_a_beta_dele(monkeypatch):
    com_aws(monkeypatch)
    saida = motor.ajusta_chamada(**CHAMADA)
    assert "fallbacks" not in saida
    assert "server-side-fallback-2026-07-01" not in saida.get("betas", [])


def test_bedrock_MANTEM_o_que_ele_suporta(monkeypatch):
    """🚨 A guarda precisa conseguir ficar quieta.

    `effort`, `thinking` adaptativo e o streaming rodam no Bedrock. Mascara que
    os levasse junto seria degradacao inventada -- e o operador aprenderia a
    ignorar a linha do pre-voo, que da' no mesmo que ela nao existir.
    """
    com_aws(monkeypatch)
    saida = motor.ajusta_chamada(**CHAMADA)
    assert saida["output_config"]["effort"] == "high"
    assert saida["thinking"] == {"type": "adaptive"}
    assert saida["stream"] is True
    assert saida["max_tokens"] == 64000


def test_claude_platform_on_aws_nao_perde_nada(monkeypatch):
    """Paridade de API no mesmo dia -- e' o motivo de ela existir na escolha."""
    com_aws(monkeypatch)
    monkeypatch.setenv("VEREDITO_MOTOR", "aws")
    saida = motor.ajusta_chamada(**CHAMADA)
    assert saida["output_config"]["task_budget"]["total"] == 30000
    assert saida["fallbacks"] == "default"
    assert set(saida["betas"]) == set(CHAMADA["betas"])


def test_betas_vazia_SOME_em_vez_de_ir_vazia(monkeypatch):
    com_aws(monkeypatch)
    saida = motor.ajusta_chamada(
        model="claude-opus-5",
        betas=["task-budgets-2026-03-13", "server-side-fallback-2026-07-01"])
    assert "betas" not in saida


def test_output_config_vazio_SOME_em_vez_de_ir_vazio(monkeypatch):
    com_aws(monkeypatch)
    saida = motor.ajusta_chamada(
        model="claude-opus-5",
        output_config={"task_budget": {"type": "tokens", "total": 30000}})
    assert "output_config" not in saida


def test_ajusta_nao_muta_o_dicionario_de_quem_chamou(monkeypatch):
    """O advogado monta a chamada uma vez e a reusa entre acusacoes."""
    com_aws(monkeypatch)
    entrada = dict(CHAMADA)
    oc_antes = dict(entrada["output_config"])
    motor.ajusta_chamada(**entrada)
    assert entrada["output_config"] == oc_antes
    assert entrada["fallbacks"] == "default"


def test_a_mascara_cobre_exatamente_o_que_o_modulo_declara():
    """A lista de capacidades ausentes e a tabela de custo nao podem divergir --
    duas fontes para a mesma informacao divergem em silencio."""
    assert set(motor.SEM_NO_BEDROCK) == set(motor.CUSTO)
    assert set(motor.SEM_NO_BEDROCK) == set(motor._BETA_DE)


# =========================================== a degradacao dita em voz alta

def test_pre_voo_nomeia_o_motor(monkeypatch):
    sem_aws(monkeypatch)
    monkeypatch.setattr(motor.cfg, "ANTHROPIC_API_KEY", "sk-falsa")
    bloco = motor.descreve()["motor"]
    assert bloco["ok"] is True
    assert "Anthropic" in bloco["detalhe"]


def test_pre_voo_do_bedrock_DIZ_O_QUE_SE_PERDE(monkeypatch):
    """🚨 Degradacao conhecida pode; degradacao MUDA nao.

    Uma rodada no Bedrock le exatamente igual a uma rodada completa -- ate' a
    recusa que ninguem tentou de novo virar INCONCLUSIVO. Se o pre-voo nao
    disser, ninguem descobre.
    """
    com_aws(monkeypatch)
    detalhe = motor.descreve()["motor"]["detalhe"]
    assert "Bedrock" in detalhe
    # O texto diz o que MUDA, nao o nome do parametro.
    assert "ciberseguranca" in detalhe
    assert "max_tokens" in detalhe


def test_pre_voo_sem_chave_na_api_direta_reprova(monkeypatch):
    sem_aws(monkeypatch)
    monkeypatch.setattr(motor.cfg, "ANTHROPIC_API_KEY", "")
    bloco = motor.descreve()["motor"]
    assert bloco["ok"] is False
    assert "ANTHROPIC_API_KEY" in bloco["detalhe"]


def test_pre_voo_no_bedrock_NAO_exige_chave_da_anthropic(monkeypatch):
    """A chave deixou de ser pre-requisito no motor que nao a usa."""
    com_aws(monkeypatch)
    monkeypatch.setattr(motor.cfg, "ANTHROPIC_API_KEY", "")
    assert motor.descreve()["motor"]["ok"] is True


def test_pre_voo_reporta_o_engano_do_operador_sem_explodir(monkeypatch):
    """O pre-voo tem que REPORTAR, nunca explodir -- se ele mesmo estourar, a
    rodada morre sem diagnostico. O caso real de 10/08."""
    sem_aws(monkeypatch)
    monkeypatch.setenv("VEREDITO_MOTOR", "bedrock")
    bloco = motor.descreve()["motor"]
    assert bloco["ok"] is False
    assert "credencial AWS" in bloco["detalhe"]


# ============================ a guarda do advogado que lia o sinal errado

def msg_de_recusa(recomendado=None, servido_por="claude-opus-5"):
    """Mensagem de recusa como o SDK a entrega: HTTP 200, content vazio."""
    return types.SimpleNamespace(
        stop_reason="refusal",
        stop_details=types.SimpleNamespace(category="cyber",
                                           recommended_model=recomendado),
        usage=types.SimpleNamespace(iterations=[]),
        content=[],
        model=servido_por,
    )


def test_recusa_no_bedrock_NAO_culpa_rate_limit(monkeypatch):
    """🚨 A guarda condicionada ao sinal errado -- o padrao de bug do projeto.

    `_diagnostico_da_recusa` deduzia a causa de tres sinais de fallback. No
    Bedrock o `fallbacks` foi REMOVIDO pelo motor, entao nenhum dos tres
    aparece: o diagnostico diria "nao da' para afirmar" (verdade, e inutil) ou,
    com `recommended_model` presente, culparia rate limit por um fallback que
    nunca foi armado -- mandando o operador investigar cota.
    """
    com_aws(monkeypatch)
    texto = advogado._diagnostico_da_recusa(msg_de_recusa(recomendado="claude-opus-4-8"))
    assert "nao havia fallback armado" in texto
    assert "Bedrock" in texto
    assert "rate limit" not in texto


def test_recusa_na_api_direta_MANTEM_o_diagnostico_antigo(monkeypatch):
    """O par. Sem ele, uma guarda que respondesse "nao havia fallback" sempre
    passaria no teste acima e apagaria o diagnostico que custou 08/08."""
    sem_aws(monkeypatch)
    texto = advogado._diagnostico_da_recusa(msg_de_recusa(recomendado="claude-opus-4-8"))
    assert "nao havia fallback armado" not in texto
    assert "rate limit" in texto
    assert "claude-opus-4-8" in texto


def test_recusa_traz_a_categoria_nos_dois_motores(monkeypatch):
    for preparo in (com_aws, sem_aws):
        motor.esquece()
        preparo(monkeypatch)
        assert "cyber" in advogado._diagnostico_da_recusa(msg_de_recusa())


# ====================================== o resto do produto usa o mesmo motor

def test_as_tres_pecas_pedem_o_cliente_ao_motor():
    """🚨 A regressao que este modulo existe para impedir.

    Ate' 19/08 promotores, advogado e fontes construiam
    `anthropic.Anthropic(...)` cada um por conta propria. Trocar de provedor
    exigia achar as tres e mante-las de acordo -- e a que ficasse para tras
    faturaria na conta errada em silencio. Asserção mecanica, porque codigo
    regride em silencio e prosa no CLAUDE.md nao.

    ⚠️ Por AST, nao por substring. A primeira versao procurava o texto
    `anthropic.Anthropic(` no fonte e reprovava com o modulo JA' consertado: ela
    casava com a DOCSTRING que explica por que aquilo saiu dali. E' o mesmo erro
    das duas travas de 13/08 (`kb` casando dentro de `kb_veredito_app`, e
    `override=True` casando com o comentario que dizia por que ele esta
    desligado) -- e as duas viraram comparacao estrutural pelo mesmo motivo.
    Trava que acusa a coisa errada nao vale mais que trava que nao acusa nada.
    """
    import ast
    import inspect

    from veredito import fontes, promotores

    for mod in (advogado, promotores, fontes):
        arvore = ast.parse(inspect.getsource(mod))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            f = no.func
            construiu = (isinstance(f, ast.Attribute) and f.attr == "Anthropic"
                         and isinstance(f.value, ast.Name) and f.value.id == "anthropic")
            assert not construiu, (
                f"{mod.__name__}:{no.lineno} voltou a construir cliente por "
                f"conta propria; use motor.cliente()")
