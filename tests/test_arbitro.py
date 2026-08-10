"""O arbitro desacoplado: citacao com procedencia, ou None honesto.

O que esta sob teste e' a diferenca entre "o campo esta preenchido" e "a regra
existe e da' para conferir onde". Foi confundir as duas que produziu o numero de
08/08: 94 acusacoes com arbitro, 94 citando os criterios de aceite do desafio da
Vindler, em repositorios que nao tem nada a ver com ele.

Nao bate na API.
"""
from veredito import arbitro as arb


# ------------------------------------------------------------------ normaliza

def test_dict_completo_sobrevive_inteiro():
    a = arb.normaliza({"regra": "so o dono compartilha", "onde": "docs/PRD.md:39"})
    assert a == {"regra": "so o dono compartilha", "onde": "docs/PRD.md:39"}


def test_string_velha_vira_regra_sem_procedencia():
    """Rodadas anteriores a 09/08 gravaram "AC2" em disco. O juiz precisa
    conseguir reprocessar aquilo sem explodir -- e sem promover a sigla a
    procedencia que ela nunca teve."""
    assert arb.normaliza("AC2") == {"regra": "AC2", "onde": None}
    assert arb.tem_procedencia("AC2") is False


def test_nada_vira_none():
    for lixo in (None, "", "   ", 42, [], {}, {"onde": "x.py:1"}):
        assert arb.normaliza(lixo) is None


def test_onde_vazio_nao_conta_como_procedencia():
    """O modelo devolvendo a chave com string vazia e' o jeito mais facil de
    fingir procedencia sem dizer nada."""
    a = arb.normaliza({"regra": "alguma regra", "onde": "  "})
    assert a == {"regra": "alguma regra", "onde": None}
    assert arb.tem_procedencia(a) is False


def test_espaco_em_volta_nao_sobrevive():
    a = arb.normaliza({"regra": "  a regra  ", "onde": " docs/X.md:4 "})
    assert a == {"regra": "a regra", "onde": "docs/X.md:4"}


# --------------------------------------------------------------- procedencia

def test_procedencia_exige_os_dois_campos():
    assert arb.tem_procedencia({"regra": "r", "onde": "a.py:1"}) is True
    assert arb.tem_procedencia({"regra": "r", "onde": None}) is False
    assert arb.tem_procedencia({"regra": "", "onde": "a.py:1"}) is False
    assert arb.tem_procedencia(None) is False


def test_citado_e_mais_frouxo_que_procedencia():
    """As duas contagens existem porque a distancia entre elas E' o achado."""
    sem_onde = {"regra": "uma regra", "onde": None}
    assert arb.citado(sem_onde) is True
    assert arb.tem_procedencia(sem_onde) is False


# -------------------------------------------------------------------- formata

def test_formata_com_procedencia_deixa_o_humano_conferir():
    s = arb.formata({"regra": "so o dono compartilha", "onde": "docs/PRD.md:39"})
    assert s == "so o dono compartilha (docs/PRD.md:39)"


def test_formata_diz_quando_falta_procedencia():
    """"ARBITRO: AC2" nunca permitiu ir conferir. O parecer tem que dizer isso
    em vez de imprimir a sigla como se fosse fonte."""
    assert "sem procedencia" in arb.formata({"regra": "AC2", "onde": None})


def test_formata_sem_arbitro_nenhum():
    assert arb.formata(None) == "nenhum citado"


def test_formata_nunca_imprime_dict_cru():
    for entrada in (None, "AC2", {"regra": "r", "onde": "a.py:1"}, {"regra": "r"}):
        assert "{" not in arb.formata(entrada)


# ---------------------------------------------------------------------- chave

def test_chave_ignora_caixa_e_espaco():
    a = {"regra": " So O Dono ", "onde": "docs/PRD.md:39"}
    b = {"regra": "so o dono", "onde": "DOCS/prd.md:39"}
    assert arb.chave(a) == arb.chave(b)


def test_chave_de_string_velha_bate_com_o_dict_equivalente():
    """Dedup nao pode enxergar dois achados so porque um lado veio de uma
    rodada antiga."""
    assert arb.chave("AC2") == arb.chave({"regra": "AC2", "onde": None})


def test_regras_diferentes_nao_colidem():
    a = {"regra": "so o dono compartilha", "onde": "docs/PRD.md:39"}
    b = {"regra": "compartilhar e' idempotente", "onde": "docs/PRD.md:39"}
    assert arb.chave(a) != arb.chave(b)


def test_mesma_regra_com_procedencia_diferente_nao_funde():
    """Duas fontes distintas para a mesma frase sao dois achados: um pode estar
    certo sobre onde a regra mora e o outro nao."""
    a = {"regra": "sem SQL cru", "onde": "docs/GUIA.md:70"}
    b = {"regra": "sem SQL cru", "onde": "CONTRIBUTING.md:12"}
    assert arb.chave(a) != arb.chave(b)


def test_sem_arbitro_nao_ha_chave():
    assert arb.chave(None) is None


# ------------------------------------------------------- detector de regressao

def test_pega_o_vocabulario_que_contaminou_os_10_prs():
    for rotulo in ("AC2", "R1", "C8", "INV-ISOLAMENTO", "INV-INSTRUCAO-NAO-E-DADO"):
        assert arb.parece_chumbado(rotulo), f"{rotulo} passou batido"


def test_pega_a_nonagesima_quarta_a_lista_inteira_colada():
    """A 94a acusacao de 08/08 trazia o vocabulario inteiro do prompt como se
    fosse um arbitro so."""
    assert arb.parece_chumbado("R1 R2 R3 R4 AC1 AC2 AC3 AC4 AC5")


def test_pega_contaminacao_escondida_no_onde():
    assert arb.parece_chumbado({"regra": "a regra", "onde": "AC3"})


def test_nao_acusa_regra_legitima():
    """Detector que grita a toa vira detector que ninguem le."""
    a = {"regra": "quem nao e' dono nem destinatario nao pode ler",
         "onde": "docs/REVIEW_TASK.md:43"}
    assert arb.parece_chumbado(a) is False


def test_nao_casa_no_meio_de_palavra():
    """R1 dentro de VAR1, C1 dentro de C10 -- falso positivo mata a metrica."""
    for inocente in ("VAR1 mudou", "o limite C10 estourou", "MAC2 nao responde",
                     "veja a linha R15"):
        assert not arb.cita_vocabulario_chumbado(inocente), inocente


def test_varre_hipotese_tambem_nao_so_o_arbitro():
    """A acusacao que sobreviveu ao advogado no psf/requests dizia, no campo
    hipotese: "nenhum requisito R1-R4 ou criterio AC1-AC5 pode ser validado por
    esta mudanca". O detector precisa pegar isso, senao mede a metade errada."""
    hip = "nenhum requisito R1-R4 ou criterio AC1-AC5 e' validado por esta mudanca"
    assert set(arb.cita_vocabulario_chumbado(hip)) >= {"R1", "R4", "AC1", "AC5"}


def test_texto_vazio_nao_quebra():
    assert arb.cita_vocabulario_chumbado("") == []
    assert arb.cita_vocabulario_chumbado(None) == []
