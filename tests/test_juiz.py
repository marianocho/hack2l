"""Testes das regras deterministicas do juiz.

Rodam em milissegundos, sem rede e sem docker. Sao a rede de seguranca contra o
erro que mais custa no palco: o alarme critico errado.
"""

from veredito import juiz


def _art(estado="PROVADO", erro=None):
    return {
        "id": "a1", "arquivo_do_teste": "test_x.py",
        "commit_base": "32a5241", "commit_head": "1dd2e5c",
        "exit_base": 0, "exit_head": 1 if estado == "PROVADO" else 0,
        "estado": estado, "provado": estado == "PROVADO",
        "motivo": "motivo qualquer", "erro": erro,
    }


# ------------------------------------------------------------------- regra 0

def test_artefato_ganha_do_advogado_que_afirma_ter_provado():
    """Sem esta regra, 'o LLM nao pode sobrescrever o veredito' e' so intencao."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "criterio 3"},
        _art(estado="REFUTADO"),
    )
    assert v["veredito"] == "REFUTADO"
    assert any("R0" in r for r in v["regras_aplicadas"])


def test_advogado_nao_declara_sozinho_que_a_prova_foi_ponta_a_ponta():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "criterio 3"},
        _art(estado="INCONCLUSIVO"),
    )
    assert v["prova_ponta_a_ponta"] is False


# ------------------------------------------------------------------- regra 1

def test_critica_sem_arbitro_vira_suspeita():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": None},
        _art(),
    )
    assert v["severidade"] == "SUSPEITA"


def test_critica_com_arbitro_sobrevive():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "criterio de aceite no 3"},
        _art(),
    )
    assert v["severidade"] == "CRITICA"


# ------------------------------------------------------------------- regra 2

def test_prova_que_nao_e_ponta_a_ponta_nao_passa_de_media():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "ALTA", "prova_ponta_a_ponta": False},
        {"arbitro": "criterio 3"},
        _art(),
    )
    assert v["severidade"] == "MEDIA"


def test_regra_2_nao_promove_severidade_baixa():
    """min, nao atribuicao: BAIXA nao pode subir para MEDIA."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "BAIXA", "prova_ponta_a_ponta": False},
        {"arbitro": "criterio 3"},
        _art(),
    )
    assert v["severidade"] == "BAIXA"


# ------------------------------------------------------------------- regra 3

def test_erro_de_infra_vira_inconclusivo_com_causa_e_nunca_absolvido():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "criterio 3"},
        _art(estado="INCONCLUSIVO", erro="timeout: passou de 180s"),
    )
    assert v["veredito"] == "INCONCLUSIVO"
    assert v["motivo"]
    assert v["veredito"] != "REFUTADO"


def test_inconclusivo_sempre_carrega_motivo_mesmo_sem_artefato():
    v = juiz.aplica_regras({"id": "a1", "veredito": "INCONCLUSIVO"}, {}, None)
    assert v["motivo"]


# ------------------------------------------------------------------ regra 3b

def test_app_sem_modelo_impede_refutacao_de_injection():
    """Achado do Luis as 10h40: sem OPENAI_API_KEY o app alvo devolve a mesma
    string para qualquer pergunta, inclusive payload de injection.

    'O modelo nao obedeceu' vira REFUTADO -- absolvicao falsa, que e' pior que
    falso alarme porque engorda a lista de descartados e PARECE rigor.
    """
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "REFUTADO", "motivo": "o sentinela nao apareceu"},
        {"categoria": "seguranca_ia"},
        None,
        avisos=[juiz.cfg.AVISO_SEM_MODELO],
    )
    assert v["veredito"] == "INCONCLUSIVO"
    assert "sem OPENAI_API_KEY" in v["motivo"]
    assert any("R3b" in r for r in v["regras_aplicadas"])


def test_app_sem_modelo_nao_mexe_em_quem_foi_provado():
    """O aviso e' por acusacao, nao por rodada: quem provou por outra via -- um
    teste de isolamento, que nao depende de LLM -- continua provado."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "criterio 3"},
        _art(),
        avisos=[juiz.cfg.AVISO_SEM_MODELO],
    )
    assert v["veredito"] == "PROVADO"
    assert v["severidade"] == "CRITICA"


def test_acusacao_sem_aviso_nao_e_afetada():
    v = juiz.aplica_regras(
        {"id": "a2", "veredito": "REFUTADO", "motivo": "passa nos dois lados"},
        {}, None, avisos=[],
    )
    assert v["veredito"] == "REFUTADO"


# -------------------------------------------------------------------- listas

def test_as_tres_listas_e_nada_sumindo_em_silencio():
    veredictos = [
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"id": "a2", "veredito": "REFUTADO", "motivo": "passa nos dois lados"},
        {"id": "a3", "veredito": "INCONCLUSIVO", "motivo": "docker fora"},
    ]
    acusacoes = {
        "a1": {"id": "a1", "categoria": "vazamento", "local": "rag.py:10", "arbitro": "criterio 3"},
        "a2": {"id": "a2", "categoria": "padroes", "local": "x.py:1"},
        "a3": {"id": "a3", "categoria": "prd", "local": "y.py:2"},
    }
    org = juiz.organiza(veredictos, acusacoes, {"a1": _art()})
    assert len(org["condenados"]) == 1
    assert len(org["descartados"]) == 1
    assert len(org["inconclusivos"]) == 1
    total = sum(len(v) for v in org.values())
    assert total == len(veredictos), "acusacao sumiu entre a entrada e o parecer"


def test_condenados_saem_ordenados_por_severidade():
    veredictos = [
        {"id": "b", "veredito": "PROVADO", "severidade": "MEDIA", "prova_ponta_a_ponta": True},
        {"id": "a", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
    ]
    acusacoes = {k: {"id": k, "arbitro": "criterio"} for k in ("a", "b")}
    org = juiz.organiza(veredictos, acusacoes, {"a": _art(), "b": _art()})
    assert [v["id"] for v in org["condenados"]] == ["a", "b"]


def test_parecer_traz_as_duas_listas_mesmo_vazias():
    """Sao a peca que nenhum outro time vai ter. Sumir quando vazias tira do
    palco justamente a evidencia de que a filtragem existe."""
    org = {"condenados": [], "descartados": [], "inconclusivos": []}
    texto = juiz.formata_parecer(org, {}, {})
    assert "DESCARTADOS, COM MOTIVO" in texto
    assert "INCONCLUSIVOS, COM CAUSA" in texto


def test_parecer_de_condenado_cita_os_dois_commits():
    """O que vai pro slide precisa dizer base e head, nao 'o teste falhou'."""
    veredictos = [{"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA",
                   "prova_ponta_a_ponta": True, "conserto": "filtrar por owner_id"}]
    acusacoes = {"a1": {"id": "a1", "categoria": "vazamento", "local": "rag.py:10",
                        "hipotese": "nao filtra por dono", "arbitro": "criterio 3",
                        "confianca": "alta"}}
    artefatos = {"a1": _art()}
    texto = juiz.formata_parecer(juiz.organiza(veredictos, acusacoes, artefatos),
                                 acusacoes, artefatos)
    assert "32a5241" in texto and "1dd2e5c" in texto
    assert "CONSERTO SUGERIDO" in texto
