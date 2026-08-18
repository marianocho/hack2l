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


def _http(alcancou_a_api=True, status=200):
    """Artefato de prova contra o app rodando. Desde 08/08 e' ele, e nao a
    palavra do advogado, que decide se a prova foi ponta a ponta."""
    return {
        "id": "a1", "tipo": "http", "alcancou_a_api": alcancou_a_api,
        "chamadas": [{"metodo": "GET", "caminho": "/shared/2", "como": "carol",
                      "status": status, "erro": None, "corpo": "{...}"}],
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


def test_sem_artefato_nenhum_a_autodeclaracao_nao_sustenta_critica():
    """🚨 O furo corrigido em 08/08, e o mais caro do juiz.

    O aterramento de `prova_ponta_a_ponta` morava DENTRO do `if artefato is not
    None`. Prova por http_request nao gera artefato de teste diferencial, entao
    o bloco inteiro era pulado e a palavra do advogado passava sem conferencia
    -- justo na unica via que, pelo CONTRATO, sustenta severidade alta.
    """
    # Arbitro COM procedencia de proposito: assim a R1 esta fora de questao e o
    # que sobra sob teste e' so o aterramento da R0b + o teto da R2. Com um
    # arbitro fraco o teste passaria por SUSPEITA e nao provaria nada sobre R2.
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": {"regra": "o dono e' checado antes de devolver o recurso",
                     "onde": "docs/REFERENCE_GUIDE.md:72"}},
        None,          # nenhum teste diferencial
        artefato_http=None,   # e nenhuma chamada registrada
    )
    assert v["prova_ponta_a_ponta"] is False
    assert v["severidade"] == "MEDIA", "a palavra do modelo sustentou severidade alta"


def test_prova_so_por_http_sustenta_critica_e_vira_evidencia():
    """O caso que o PR de hoje exige: os 3 endpoints sao NOVOS, entao prova
    diferencial nao fecha neles (404 no base) e o achado chega so' por API."""
    acusacao = {"id": "a1", "categoria": "injection", "arbitro": "INV-ISOLAMENTO",
                "local": "app/api/app/routers/shares.py:82", "hipotese": "carol le doc de alice"}
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        acusacao, None, artefato_http=_http(),
    )
    assert v["prova_ponta_a_ponta"] is True
    assert v["severidade"] == "CRITICA"

    bloco = juiz._bloco(v, acusacao, None, _http())
    assert "nao fechou" not in bloco, "prova por API imprimindo 'nao fechou'"
    assert "GET /shared/2 como carol -> HTTP 200" in bloco
    assert "artefatos/http_a1.json" in bloco


def test_evidencia_http_mostra_o_contraste_nao_so_a_ultima_chamada():
    """🚨 Medido em 13h30: com "cita a ultima" o parecer imprimia o 404 do email
    de CONTROLE enquanto a prova era o 201 do payload, duas chamadas antes. O
    contraste e' a prova; uma linha so' escolhia a metade sem graca."""
    art = {
        "id": "a1", "tipo": "http", "alcancou_a_api": True,
        "chamadas": [
            {"metodo": "POST", "caminho": "/documents/1/share", "como": "alice",
             "status": 201, "erro": None, "corpo": "{}"},
            {"metodo": "POST", "caminho": "/documents/1/share", "como": "alice",
             "status": 404, "erro": None, "corpo": "{}"},
        ],
    }
    linha = juiz._evidencia_http(art)
    assert "HTTP 201" in linha and "HTTP 404" in linha


def test_evidencia_http_nao_vira_dump():
    art = {
        "id": "a1", "tipo": "http", "alcancou_a_api": True,
        "chamadas": [{"metodo": "GET", "caminho": f"/x/{i}", "como": "carol",
                      "status": 200, "erro": None, "corpo": ""} for i in range(9)],
    }
    linha = juiz._evidencia_http(art)
    assert linha.count("HTTP 200") == 4
    assert "+5 chamada(s) antes" in linha


def test_404_conta_como_ter_alcancado_a_api_e_isso_e_deliberado():
    """Medido em 08/08: carol -> GET /shared/2 devolve 404, e o artefato marca
    alcancou_a_api. Nao e' bug -- o campo significa "a chamada completou contra
    o app rodando", nao "o defeito foi alcancado". Quem garante que o defeito
    apareceu e' o AND com a declaracao do advogado mais o corpo no artefato, que
    um humano le. Se alguem apertar isto para exigir 2xx, prova de negacao
    indevida (403/404 onde deveria haver dado) deixa de ser demonstravel.
    """
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "INV-ISOLAMENTO"}, None, artefato_http=_http(status=404),
    )
    assert v["prova_ponta_a_ponta"] is True


def test_chamada_que_nao_completou_nao_e_prova():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "x"}, None, artefato_http=_http(alcancou_a_api=False),
    )
    assert v["prova_ponta_a_ponta"] is False


def test_categoria_sai_no_vocabulario_do_desafio():
    """O desafio nomeia cinco categorias; nos usamos seis, mais granulares.
    Jurado lendo rotulo que nao e' o dele e' atrito de graca."""
    acusacao = {"id": "a1", "categoria": "injection", "arbitro": "x", "local": "a.py:1"}
    bloco = juiz._bloco({"severidade": "MEDIA"}, acusacao, _art())
    assert "security" in bloco and "injection" not in bloco


# ------------------------------------------------------------------- regra 1

ARB_OK = {"regra": "quem nao e' dono nem destinatario nao pode ler",
          "onde": "docs/REVIEW_TASK.md:43"}


def test_critica_sem_arbitro_e_sem_prova_ponta_a_ponta_vira_suspeita():
    """Nenhuma das duas vias: e' opiniao de modelo com teste em anexo."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": None},
        _art(),          # artefato de teste, mas nenhuma chamada http registrada
    )
    assert v["severidade"] == "SUSPEITA"


def test_arbitro_sem_procedencia_nao_sustenta_critica():
    """🚨 O aperto de 10/08. "AC2" nao diz onde a regra esta escrita, e depois
    de 09/08 sabemos que na maioria das vezes ela nao estava escrita em lugar
    nenhum -- eram os criterios do desafio aplicados a repo de terceiro."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": "AC2"},
        _art(),
    )
    assert v["severidade"] == "SUSPEITA"
    assert any("sem arbitro com procedencia" in r for r in v["regras_aplicadas"])


def test_arbitro_com_procedencia_passa_pela_r1():
    """Passar pela R1 nao e' virar CRITICA: a R2 ainda cobra prova ponta a
    ponta. O que se testa aqui e' que a R1 nao rebaixou para SUSPEITA."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": False},
        {"arbitro": ARB_OK},
        _art(),
    )
    assert v["severidade"] == "MEDIA"
    assert not any("R1" in r for r in v["regras_aplicadas"])


def test_critica_com_arbitro_e_prova_sobrevive():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": ARB_OK},
        _art(),
        artefato_http=_http(),
    )
    assert v["severidade"] == "CRITICA"


def test_prova_ponta_a_ponta_e_a_SEGUNDA_via_para_critica():
    """🚨 A regra nova de 10/08, e o furo que ela fecha esta no parecer premiado.

    O MESMO SQL injection saiu duas vezes na rodada final do Hack2L:

        padroes_01   arbitro "C2"   -> CRITICA
        correcao_01  arbitro null   -> SUSPEITA

    O correcao_01 tinha prova diferencial (passa no base, falha no head) E
    artefato http. A severidade nao seguiu a forca da prova, seguiu o acaso de
    uma lente ter recitado um rotulo chumbado que a outra nao recitou -- rotulo
    que, sabemos desde 09/08, nos mesmos inventamos.

    Sem esta via, desacoplar o arbitro tornaria SUSPEITA todo achado provado em
    todo repositorio que nao documenta os proprios criterios. Ou seja: quase
    todos.
    """
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": None},
        _art(),
        artefato_http=_http(),
    )
    assert v["severidade"] == "CRITICA"
    assert not any("R1" in r for r in v["regras_aplicadas"])


def test_a_segunda_via_nao_aceita_a_palavra_do_advogado():
    """A via de prova so vale aterrada no artefato (R0b). Se valesse a
    autodeclaracao, teriamos trocado um rotulo reciclado por um LLM dizendo
    'provei' -- que e' pior, porque parece evidencia."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"arbitro": None},
        _art(),
        artefato_http=_http(alcancou_a_api=False),
    )
    assert v["prova_ponta_a_ponta"] is False
    assert v["severidade"] == "SUSPEITA"


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

def test_aviso_por_acusacao_dispara_a_r4_sem_depender_do_estado_da_rodada():
    """Segundo sinal da R4, complementar ao do llm_alvo: a propria ferramenta
    registrou que ESTA acusacao viu resposta duble.

    Serve para o caso de a sonda da rodada nao ter rodado ou ter dado
    indeterminado -- sem isto, a regra dependeria de um unico detector.
    """
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "REFUTADO", "motivo": "o sentinela nao apareceu"},
        {"categoria": "injection"},
        None,
        avisos=[juiz.cfg.AVISO_SEM_MODELO],
    )
    assert v["veredito"] == "INCONCLUSIVO"
    assert "nao e' possivel provar nem refutar" in v["motivo"].lower()
    assert any("R4" in r for r in v["regras_aplicadas"])


def test_llm_duble_nao_mexe_em_quem_foi_provado():
    """Quem provou por outra via -- teste diferencial, isolamento -- continua
    provado e critico. O modelo duble nao contamina a rodada inteira."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA", "prova_ponta_a_ponta": True},
        {"categoria": "injection", "arbitro": "criterio 3"},
        _art(),
        avisos=[juiz.cfg.AVISO_SEM_MODELO],
        artefato_http=_http(),
    )
    assert v["veredito"] == "PROVADO"
    assert v["severidade"] == "CRITICA"


def test_vazamento_refutado_sobrevive_mesmo_com_aviso():
    """Isolamento se prova por CITACAO, e citacao nao depende do modelo
    responder -- entao REFUTADO ali continua sendo descarte legitimo.

    Ampliar a R4 para esta categoria incharia a lista de inconclusivos com
    descartes validos, e inconclusivo inflado enfraquece o parecer tanto quanto
    inconclusivo vazio.
    """
    v = juiz.aplica_regras(
        {"id": "a2", "veredito": "REFUTADO", "motivo": "carol nao viu nada"},
        {"categoria": "vazamento_de_contexto"},
        None,
        avisos=[juiz.cfg.AVISO_SEM_MODELO],
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
    org = juiz.organiza(veredictos, acusacoes, {"a": _art(), "b": _art()},
                        http={"a": _http(), "b": _http()})
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


# ------------------------------------------------------- regra 3b (11/08)

def test_provado_com_TODAS_as_ferramentas_falhando_e_inconclusivo():
    """🚨 O caso real de 10/08, e o furo que ele expos.

    Numa rodada com a worktree corrompida, o advogado chamou read_file/grep,
    TODA chamada voltou RuntimeError, e ele devolveu PROVADO -- duas vezes --
    escrevendo no proprio motivo que as ferramentas falharam. Ele sabia.

    A R3 nao pegava: ela olha `artefato.erro`, e numa verificacao so estatica
    nao existe artefato. Mesmo formato de furo da R0b, que morava dentro de
    `if artefato is not None` e ficava muda onde nao havia artefato.
    """
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA",
         "prova_ponta_a_ponta": False, "ferramentas_ok": 0, "ferramentas_erro": 7,
         "motivo": "as ferramentas de leitura/grep falharam (worktree corrompida)"},
        {"arbitro": None}, None,
    )
    assert v["veredito"] == "INCONCLUSIVO"
    assert v["severidade"] == "SUSPEITA"
    assert any("R3b" in r for r in v["regras_aplicadas"])


def test_refutado_com_todas_as_ferramentas_falhando_tambem_e_inconclusivo():
    """Falsa condenacao e falsa absolvicao tem a mesma causa: zero observacao."""
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "REFUTADO", "severidade": "BAIXA",
         "ferramentas_ok": 0, "ferramentas_erro": 3, "motivo": "nao se sustenta"},
        {"arbitro": None}, None,
    )
    assert v["veredito"] == "INCONCLUSIVO"


def test_uma_ferramenta_que_funcionou_basta_para_o_veredito_valer():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "REFUTADO", "severidade": "BAIXA",
         "ferramentas_ok": 1, "ferramentas_erro": 4, "motivo": "li o codigo, e falso"},
        {"arbitro": None}, None,
    )
    assert v["veredito"] == "REFUTADO"


def test_veredicto_antigo_sem_o_campo_NAO_vira_inconclusivo():
    """Ausencia do campo nao e' o mesmo que zero.

    saidas/*.json de antes de 11/08 nao tem `ferramentas_ok`. Tratar ausente
    como zero viraria toda rodada antiga em inconclusiva no reprocessamento --
    inventando um problema que nao houve.
    """
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "PROVADO", "severidade": "CRITICA",
         "prova_ponta_a_ponta": True},
        {"arbitro": None}, _art(), artefato_http=_http(),
    )
    assert v["veredito"] == "PROVADO"


def test_inconclusivo_com_zero_ferramentas_continua_inconclusivo_sem_ruido():
    v = juiz.aplica_regras(
        {"id": "a1", "veredito": "INCONCLUSIVO", "ferramentas_ok": 0,
         "motivo": "docker fora"},
        {"arbitro": None}, None,
    )
    assert v["veredito"] == "INCONCLUSIVO"
    assert sum("R3b" in r for r in v["regras_aplicadas"]) <= 1


def test_corroboracao_externa_aparece_no_parecer():
    """Sinal que nao e' impresso morre em disco. E precisa ser distinguivel de
    'duas lentes concordaram' -- as duas lentes sao o mesmo modelo."""
    acusacao = {"id": "a1", "categoria": "injection", "local": "shares.py:31",
                "hipotese": "SQL injection", "arbitro": None, "confianca": "alta",
                "_corroborado_externo": True,
                "_scanner": [
                    {"ferramenta": "bandit", "local": "shares.py:31",
                     "texto": "Possible SQL injection vector"},
                    {"ferramenta": "semgrep", "local": "shares.py:31",
                     "texto": "parametro do cliente alcanca text()"}]}
    bloco = juiz._bloco({"severidade": "MEDIA"}, acusacao, _art())
    assert "CORROBORADO POR" in bloco
    assert "bandit" in bloco and "semgrep" in bloco
    # Verbatim, nao resumido: quem le julga se aquilo sustenta ESTE achado.
    assert "Possible SQL injection vector" in bloco


def test_sem_corroboracao_externa_a_linha_nao_aparece():
    bloco = juiz._bloco({"severidade": "MEDIA"},
                        {"id": "a1", "categoria": "prd", "local": "x.py:1"}, _art())
    assert "CORROBORADO POR" not in bloco


# ------------------------------- o efeito da pericia no banco do app (14/08)

import json                                        # noqa: E402
from veredito import config as cfg                 # noqa: E402


def _grava_delta(tmp_path, monkeypatch, delta):
    monkeypatch.setattr(cfg, "RODADA", tmp_path)
    (tmp_path / "efeito_no_banco.json").write_text(
        json.dumps({"delta": delta}), encoding="utf-8")


def test_rodada_que_removeu_linhas_aparece_no_PARECER(tmp_path, monkeypatch):
    """No arquivo, nao so' no console: o console rola e o arquivo fica.

    Remover linha e' a unica coisa que nunca deveria acontecer. Quem ler o
    parecer amanha precisa ver isso sem ter que ir procurar em outro lugar.
    """
    _grava_delta(tmp_path, monkeypatch, {
        "banco": "kb", "criadas": {}, "removidas": {"documents": 2},
        "limpo": False, "houve_remocao": True, "nao_detecta": "UPDATE no lugar"})
    texto = "\n".join(juiz._secao_efeito_no_banco())
    assert "REMOVEU" in texto and "documents" in texto


def test_linhas_criadas_aparecem_sem_alarme(tmp_path, monkeypatch):
    """Criar para provar defeito em endpoint de escrita e' esperado -- entra
    como registro, nao como alarme. Tratar as duas iguais faria o leitor
    ignorar as duas."""
    _grava_delta(tmp_path, monkeypatch, {
        "banco": "kb", "criadas": {"shares": 3}, "removidas": {},
        "limpo": False, "houve_remocao": False, "nao_detecta": "UPDATE no lugar"})
    texto = "\n".join(juiz._secao_efeito_no_banco())
    assert "shares" in texto and "REMOVEU" not in texto


def test_o_limite_do_metodo_vai_junto(tmp_path, monkeypatch):
    """Metrica que nao declara o que NAO cobre vira cobertura imaginaria -- o
    erro dos 45% de arbitro, que contavam 'preenchido' achando que contavam
    'valido'."""
    _grava_delta(tmp_path, monkeypatch, {
        "banco": "kb", "criadas": {"shares": 1}, "removidas": {},
        "limpo": False, "houve_remocao": False,
        "nao_detecta": "linha modificada no lugar"})
    assert "modificada no lugar" in "\n".join(juiz._secao_efeito_no_banco())


def test_banco_intacto_nao_gera_secao(tmp_path, monkeypatch):
    """Silencio e' proposital: secao sem conteudo em toda rodada treina o leitor
    a pular, e ai ela nao serve quando importa."""
    _grava_delta(tmp_path, monkeypatch, {
        "banco": "kb", "criadas": {}, "removidas": {}, "limpo": True,
        "houve_remocao": False, "nao_detecta": "x"})
    assert juiz._secao_efeito_no_banco() == []


def test_sem_medicao_o_parecer_sai_igual(tmp_path, monkeypatch):
    """Rodada antiga, ou medicao que falhou, nao pode quebrar o parecer."""
    monkeypatch.setattr(cfg, "RODADA", tmp_path)
    assert juiz._secao_efeito_no_banco() == []


# ------------------------------------------- 🚨 R0 e o artefato de RECUSA

def _recusa():
    """O artefato que a `prova_diferencial` grava quando o projeto nao a declara."""
    return {"estado": "INCONCLUSIVO", "provado": False, "erro": None,
            "indisponivel": "o projeto revisado nao declara o bloco `codigo` "
                            "... Prove por leitura (read_file/grep)."}


def test_R0_nao_derruba_PROVADO_com_artefato_de_recusa():
    """🚨 O caso real do primeiro run da Action contra a bancada, 18/08.

    O advogado achou o IDOR plantado, disse PROVADO nas TRES acusacoes, e o
    parecer saiu "Nenhum achado sustentado por evidencia -- 3 inconclusivas".
    Atestado de limpeza para uma vulnerabilidade real: o pior desfecho que este
    produto pode produzir.

    A recusa nao e' um exit code discordando, e' a ausencia de medicao. E o
    texto dela manda provar por leitura -- o advogado obedeceu, e o juiz o
    derrubou por ter obedecido.
    """
    v = juiz.aplica_regras(
        {"veredito": "PROVADO", "severidade": "ALTA", "ferramentas_ok": 3},
        {}, _recusa())
    assert v["veredito"] == "PROVADO", (
        "a R0 derrubou um PROVADO usando um artefato que nunca chegou a rodar")
    # A R2 e' quem cuida da forca: sem prova ponta a ponta, no maximo MEDIA.
    assert v["severidade"] == "MEDIA"


def test_R0_continua_derrubando_quando_o_artefato_RODOU():
    """🚫 O controle, e a metade que nao pode afrouxar.

    Sem ele o teste acima passaria com a R0 desligada -- e a R0 e' o que impede
    o LLM de sobrescrever o exit code, que a arquitetura inteira pressupoe.
    """
    rodou = {"estado": "REFUTADO", "provado": False, "erro": None,
             "indisponivel": None, "motivo": "passou nos dois lados"}
    v = juiz.aplica_regras(
        {"veredito": "PROVADO", "severidade": "ALTA", "ferramentas_ok": 3},
        {}, rodou)
    assert v["veredito"] == "REFUTADO"
    assert any("R0" in r for r in v["regras_aplicadas"])


def test_R3_continua_convertendo_erro_de_verdade_mesmo_com_recusa_no_campo():
    """Os dois campos coexistem: `erro` preenchido manda, venha o que vier."""
    misto = {"estado": "INCONCLUSIVO", "erro": "docker: connection refused",
             "indisponivel": "tambem nao declarado"}
    v = juiz.aplica_regras(
        {"veredito": "REFUTADO", "severidade": "BAIXA", "ferramentas_ok": 2},
        {}, misto)
    assert v["veredito"] == "INCONCLUSIVO"
