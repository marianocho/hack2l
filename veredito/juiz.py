"""hack2l / Veredito -- o juiz, na parte que nao pode ser opiniao.

As regras deste modulo sao deterministicas de proposito. Regra escrita em prosa
nao acontece as 14h30 com 12 achados e video para gravar: vira codigo ou nao
existe. E' isto que impede o alarme critico errado mecanicamente, em vez de por
disciplina humana sob pressao.

A sintese em linguagem natural -- deduplicar, ordenar, redigir o conserto
sugerido -- e' uma chamada de modelo e mora fora daqui. O que esta aqui roda em
milissegundos, sem rede, e tem teste.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import arbitro
from . import fontes
from . import fusao
from . import prova_de_fusao as pfus
from . import superficie
from . import config as cfg
from . import llm_alvo

# CRITICA > ALTA > MEDIA > BAIXA > SUSPEITA
ORDEM = {"CRITICA": 4, "ALTA": 3, "MEDIA": 2, "BAIXA": 1, "SUSPEITA": 0}
SEVERIDADES = list(ORDEM)

# Categorias cuja REFUTACAO depende de o LLM do app alvo ter realmente rodado.
#
# So injection. Vazamento de contexto fica de fora de proposito: prova-se por
# quais documentos foram CITADOS, e citacao nao depende do modelo responder --
# entao um REFUTADO ali continua legitimo com o modelo duble. Incluir vazamento
# aqui incharia a lista de inconclusivos com descartes validos, e uma lista de
# inconclusivos inflada enfraquece o parecer tanto quanto uma vazia.
_DEPENDEM_DO_LLM = {"injection"}


def _min_severidade(a: str, b: str) -> str:
    return a if ORDEM.get(a, 0) <= ORDEM.get(b, 0) else b


def aplica_regras(
    veredicto: dict,
    acusacao: dict,
    artefato: dict | None,
    avisos: list[str] | tuple[str, ...] = (),
    artefato_http: dict | None = None,
) -> dict:
    """As regras determinísticas, em ordem. Devolve um veredicto novo.

    Cada rebaixamento fica registrado em `regras_aplicadas`, porque um parecer
    que rebaixa sem dizer por que e' tao opaco quanto um que nao rebaixa.
    """
    v = dict(veredicto)
    v.setdefault("severidade", "BAIXA")
    aplicadas: list[str] = []

    # REGRA 0 -- o artefato manda. Nao esta no documento original, mas a
    # arquitetura inteira depende disto: se o advogado afirma PROVADO e o exit
    # code diz que nao, quem ganha e' o exit code. Sem esta regra, "o LLM nao
    # pode sobrescrever o veredito" e' so uma intencao.
    #
    # 🚨 MAS ARTEFATO DE RECUSA NAO E' ARTEFATO -- 18/08, e e' a mesma distincao
    # que a R3 aprendeu na vespera, uma regra acima.
    #
    # Quando `prova_diferencial` recusa por o projeto nao declarar o bloco
    # `codigo`, ela grava um artefato com `estado: INCONCLUSIVO`. Isso nao e' um
    # exit code discordando: e' a ausencia de qualquer medicao. A R0 lia so'
    # `estado` e derrubava por igual.
    #
    # Medido no primeiro run da Action contra a bancada: o advogado achou o IDOR
    # plantado, disse PROVADO nas TRES acusacoes, e o parecer saiu "Nenhum
    # achado sustentado por evidencia -- 3 inconclusivas". Atestado de limpeza
    # para uma vulnerabilidade real e explorada, que e' o pior desfecho que este
    # produto pode produzir.
    #
    # E a incoerencia fechava o circulo: o texto da recusa diz "Prove por
    # leitura (read_file/grep)". O advogado obedeceu, provou por leitura, e o
    # juiz o derrubou POR TER OBEDECIDO.
    #
    # 🚫 O que NAO afrouxou: artefato que RODOU e discordou continua mandando --
    # e' a regra inteira, e ela e' o que impede o LLM de sobrescrever o exit
    # code. So' deixou de valer para o artefato que nunca chegou a existir.
    if artefato is not None and not artefato.get("indisponivel"):
        if v.get("veredito") == "PROVADO" and artefato.get("estado") != "PROVADO":
            v["veredito"] = artefato.get("estado", "INCONCLUSIVO")
            v["motivo"] = artefato.get("motivo") or v.get("motivo")
            aplicadas.append(
                f"R0: o advogado disse PROVADO, o artefato disse {artefato.get('estado')}. "
                "Vale o artefato."
            )
    # REGRA 0b -- prova ponta a ponta e' FATO DO ARTEFATO, sempre.
    #
    # 🚨 Isto morava DENTRO do `if artefato is not None` acima, e era o furo mais
    # caro do juiz. Prova por `http_request` nao gera artefato de teste
    # diferencial, entao numa acusacao provada pela API o bloco inteiro era
    # pulado e a auto-declaracao do advogado passava sem conferencia -- justo na
    # unica via que, pelo CONTRATO, sustenta severidade alta. Ou seja: a regra
    # que existe para o LLM nao sobrescrever o exit code so' rodava quando havia
    # exit code, e ficava muda exatamente onde nao havia.
    #
    # Morde neste PR em especial: ele adiciona tres endpoints NOVOS, onde prova
    # diferencial nao fecha (404 no base e' o inverso do padrao), entao os
    # achados especificos do PR chegam aqui so' com prova por API.
    #
    # AND deliberado: o modelo alega, o artefato corrobora. Sem artefato http com
    # chamada completada, e' falso -- independente do que ele declarou.
    v["prova_ponta_a_ponta"] = bool(veredicto.get("prova_ponta_a_ponta")) and bool(
        (artefato_http or {}).get("alcancou_a_api")
    )

    # REGRA 4 -- absolvicao falsa por LLM alvo duble.
    #
    # R3 nao pega este caso: nada falhou. Os exit codes estao limpos, `erro` e'
    # None. O que aconteceu e' que o app alvo respondeu a string enlatada (sem
    # OPENAI_API_KEY, ou rate limit), entao o payload de injection nao tinha
    # como surtir efeito -- e "nao surtiu efeito" foi lido como "o app resistiu".
    # Sem esta regra a decisao depende do advogado ter obedecido um aviso em
    # texto, ou seja, PASSA PELO MODELO. Aqui ela e' mecanica.
    #
    # DOIS SINAIS, porque cada um sozinho tem um buraco:
    #
    #   por acusacao  -- a ferramenta gravou que ESTA acusacao viu resposta
    #                    duble. Pega qualquer categoria que tenha sondado o
    #                    chat, nao so as rotuladas 'injection'.
    #   por rodada    -- o llm_alvo mediu a rodada inteira como DUBLE. Pega o
    #                    caso de o advogado ter concluido sem deixar rastro na
    #                    ferramenta.
    #
    # Disparar a mais custa um INCONCLUSIVO onde caberia REFUTADO, e o desafio
    # e' explicito: deixar passar defeito real e' pior que falso alarme.
    #
    # Escopo mantido estreito no resto: so quando REFUTADO. Um PROVADO com LLM
    # duble veio de outra via -- teste diferencial, isolamento -- e e' legitimo.
    if v.get("veredito") == "REFUTADO" and acusacao.get("categoria") in _DEPENDEM_DO_LLM:
        est, detalhe = llm_alvo.estado_registrado()
        por_acusacao = cfg.AVISO_SEM_MODELO in avisos
        por_rodada = est == llm_alvo.DUBLE
        if por_acusacao or por_rodada:
            origem = "observado nesta acusacao" if por_acusacao else "medido na rodada"
            v["veredito"] = "INCONCLUSIVO"
            v["severidade"] = "SUSPEITA"
            v["motivo"] = (
                f"LLM do app alvo esta duble ({origem}): responde o mesmo para "
                f"qualquer pergunta. {detalhe}. Nao e' possivel provar nem refutar "
                "obediencia a injection por esta via -- nao e' refutacao, e' "
                "ausencia de observacao."
            )
            aplicadas.append(
                "R4: REFUTADO com LLM alvo duble -> INCONCLUSIVO, nunca absolvido"
            )
            v["regras_aplicadas"] = aplicadas
            return v

    # REGRA 3b -- veredito com ZERO observacao nao e' veredito.
    #
    # 🚨 O caso real de 10/08: com a worktree corrompida, o advogado chamou
    # read_file/grep, TODA chamada voltou RuntimeError, e ele devolveu PROVADO
    # -- duas vezes -- escrevendo no proprio motivo que as ferramentas tinham
    # falhado. Ele sabia, e concluiu assim mesmo.
    #
    # A R3 nao pegava porque ela olha `artefato.erro`, e verificacao so estatica
    # nao gera artefato. Mesmo formato de furo da R0b, que morava dentro de
    # `if artefato is not None` e ficava muda justo onde nao havia artefato.
    #
    # Isto nao e' restricao nova, e' a regra central aplicada: "nao argumenta,
    # TESTA". Veredito sem nenhuma observacao e' opiniao de modelo -- o que o
    # produto existe para barrar. Vale nos dois sentidos: falsa condenacao
    # (PROVADO) e falsa absolvicao (REFUTADO) tem a mesma causa.
    #
    # ⚠️ AUSENTE nao e' ZERO. Rodada gravada antes de 11/08 nao tem o campo;
    # tratar ausencia como zero viraria todo reprocessamento em inconclusivo,
    # inventando um problema que nao houve.
    # ⚠️ O GATILHO NAO MUDOU em 17/08, e nao mudar foi a decisao. Ferramenta
    # indisponivel deixou de contar como ERRO (a R3 parou de converter por causa
    # dela), mas nunca contou como SUCESSO -- entao veredito sem nenhuma
    # observacao continua inconclusivo, tenha a ferramenta quebrado ou nunca
    # existido neste projeto. Ler o diff que ja veio no prompt e' argumentar, e
    # o produto existe para barrar isso. O que mudou aqui e' so a CAUSA dita.
    ok = v.get("ferramentas_ok")
    if ok == 0 and v.get("veredito") in ("PROVADO", "REFUTADO"):
        erros = v.get("ferramentas_erro") or 0
        indisp = v.get("ferramentas_indisponivel") or 0
        if indisp and not erros:
            causa = (f"as {indisp} chamada(s) foram a ferramentas que este "
                     "projeto nao declara, e nenhuma leitura do repositorio foi "
                     "feita")
        elif indisp:
            causa = (f"{erros} chamada(s) com erro e {indisp} a ferramenta(s) "
                     "que este projeto nao declara")
        else:
            causa = f"{erros} chamada(s) com erro"
        antes = v["veredito"]
        v["veredito"] = "INCONCLUSIVO"
        v["severidade"] = "SUSPEITA"
        v["motivo"] = (
            f"nenhuma ferramenta funcionou ({causa}), entao "
            f"nao houve observacao que sustentasse {antes}. "
            + (v.get("motivo") or "")
        ).strip()
        aplicadas.append(
            f"R3b: {antes} com zero ferramenta bem-sucedida -> INCONCLUSIVO"
        )
        v["regras_aplicadas"] = aplicadas
        return v

    # REGRA 3 (antes das de severidade: execucao falha encerra o assunto)
    #
    # 🚨 `erro`, e SO `erro` -- a decisao de 17/08. O artefato passou a ter dois
    # campos, `erro` ("existia e quebrou") e `indisponivel` ("este projeto nao
    # tem esta ferramenta"), e esta regra le apenas o primeiro.
    #
    # Medido no `pallets/flask#6095`: com os dois no mesmo campo, QUATRO
    # refutacoes obtidas por leitura -- com o grep funcionando, uma delas
    # apontando a assinatura documentada do pytest -- sairam inconclusivas. E a
    # unica que sobreviveu sobreviveu por acaso: o advogado, naquela, nao chegou
    # a chamar a ferramenta que nao existe. Mesma qualidade de prova, desfecho
    # decidido por qual ferramenta o modelo tentou -- que e' exatamente o que a
    # segunda via da R1 consertou em 10/08, e pelo mesmo argumento.
    #
    # 🚫 O que NAO afrouxou: ferramenta que quebrou continua convertendo, e a
    # R3b continua disparando com zero observacao. Um projeto que nao declara
    # ferramenta nenhuma nao ganha veredito de graca -- ganha o direito de ser
    # julgado pelo que a leitura sustenta, que e' o limite honesto dele.
    if v.get("veredito") == "INCONCLUSIVO" or (artefato or {}).get("erro"):
        v["veredito"] = "INCONCLUSIVO"
        v["severidade"] = "SUSPEITA"
        if not v.get("motivo"):
            v["motivo"] = (artefato or {}).get("erro") or "execucao falhou sem causa registrada"
        aplicadas.append("R3: execucao falhou -> INCONCLUSIVO, nunca absolvido")
        v["regras_aplicadas"] = aplicadas
        return v

    # REGRA 1 -- CRITICA exige uma autoridade que NAO seja o modelo.
    #
    # Duas vias, e qualquer uma basta:
    #
    #   arbitro com procedencia  uma regra escrita NESTE repositorio foi
    #                            violada, e um humano pode ir conferir onde.
    #   prova ponta a ponta      a coisa ruim aconteceu de fora, contra o app
    #                            rodando, com artefato -- ja aterrado na R0b,
    #                            entao aqui e' fato do artefato, nao alegacao.
    #
    # A segunda via entrou em 10/08, junto com o desacoplamento do arbitro, e
    # nao e' afrouxamento: e' o conserto de um furo que a rodada premiada
    # exibiu em cima do palco. No parecer final do Hack2L, o MESMO SQL injection
    # apareceu duas vezes --
    #
    #   padroes_01   arbitro "C2"   -> CRITICA
    #   correcao_01  arbitro null   -> SUSPEITA
    #
    # -- e o correcao_01 tinha prova diferencial (passa no base, falha no head)
    # E artefato http. A severidade nao seguiu a forca da prova, seguiu o acaso
    # de uma lente ter recitado um rotulo chumbado que a outra nao recitou.
    # Depois de 09/08 sabemos que aquele rotulo nem existia no repositorio do
    # desafio: nos o inventamos. Sem a segunda via, o conserto do arbitro
    # tornaria SUSPEITA todo achado provado em todo repositorio que nao
    # documenta os proprios criterios -- ou seja, quase todos.
    #
    # O que continua barrado: opiniao de modelo sem nenhuma das duas. Que e' o
    # que a R1 sempre quis dizer.
    if v["severidade"] == "CRITICA":
        tem_regra = arbitro.tem_procedencia(acusacao.get("arbitro"))
        tem_prova = bool(v.get("prova_ponta_a_ponta"))
        if not tem_regra and not tem_prova:
            v["severidade"] = "SUSPEITA"
            motivo_r1 = (
                "sem arbitro com procedencia"
                if arbitro.citado(acusacao.get("arbitro"))
                else "sem arbitro citado"
            )
            aplicadas.append(
                f"R1: CRITICA {motivo_r1} e sem prova ponta a ponta -> SUSPEITA"
            )

    # REGRA 2 -- so prova ponta a ponta sustenta severidade alta
    if not v.get("prova_ponta_a_ponta"):
        antes = v["severidade"]
        v["severidade"] = _min_severidade(antes, "MEDIA")
        if v["severidade"] != antes:
            aplicadas.append(f"R2: prova nao e' ponta a ponta -> {antes} rebaixada para MEDIA")

    v["regras_aplicadas"] = aplicadas
    return v


def organiza(
    veredictos: list[dict], acusacoes: dict, artefatos: dict, avisos: dict | None = None,
    http: dict | None = None,
) -> dict:
    """Separa nas tres listas do parecer. Nada e' descartado em silencio."""
    avisos = avisos or {}
    http = http or {}
    condenados, descartados, inconclusivos = [], [], []
    for v in veredictos:
        id_ = v.get("id", "sem_id")
        final = aplica_regras(
            v, acusacoes.get(id_, {}), artefatos.get(id_), avisos.get(id_, ()),
            http.get(id_),
        )
        final["id"] = id_
        destino = {
            "PROVADO": condenados,
            "SUSPEITA": condenados,  # suspeita fundamentada entra rotulada
            "REFUTADO": descartados,
        }.get(final.get("veredito"), inconclusivos)
        destino.append(final)

    condenados.sort(key=lambda x: -ORDEM.get(x.get("severidade", "BAIXA"), 0))
    return {
        "condenados": condenados,
        "descartados": descartados,
        "inconclusivos": inconclusivos,
    }


# ------------------------------------------------------------------- o parecer

def _local(acusacao: dict) -> str:
    """O caminho como ele sai no parecer, com a raiz corrigida quando da.

    Import tardio de proposito: o juiz continua rodando sem git e sem o resto do
    pacote, que e' a propriedade que permite reajustar o parecer trinta vezes
    lendo so o disco.
    """
    # 🚨 O carimbo da RODADA ganha, sempre. Normalizar na hora de formatar
    # resolve o caminho contra a worktree que estiver montada AGORA -- e
    # re-renderizar o parecer do `pallets/flask` com o desafio montado
    # transformava `tests/conftest.py:9` em `app/api/tests/conftest.py:9`, um
    # arquivo que nao existe no repo do autor. Em silencio, porque
    # `normaliza_local` acha um sufixo plausivel em qualquer arvore.
    #
    # Passou a doer agora porque a saida virou COMENTARIO DE PR: o parecer e'
    # formatado longe da rodada, e manda uma pessoa de verdade procurar o
    # arquivo. Ver `ferramentas.carimba_local`.
    carimbado = acusacao.get("local_normalizado")
    if carimbado:
        return carimbado
    bruto = acusacao.get("local") or "?"
    # 🚫 Sem carimbo (rodada gravada antes de 17/08) devolve o CRU. Normalizar
    # aqui seria adivinhar contra outra arvore, que e' exatamente o defeito.
    return bruto


def _evidencia_http(art: dict | None, estilo=None) -> list[str] | None:
    """A evidencia de uma prova contra o app rodando: lead + as chamadas.

    O `REVIEW_TASK.md` aceita TRES vias -- teste que falha, **reproducao contra o
    app rodando**, e trace/log/estado do banco. So' a primeira virava linha de
    evidencia aqui; a segunda existia como ferramenta e sumia do parecer.

    Lista as chamadas que completaram, em ordem, nao so' a ultima.

    🚨 Medido na validacao das 13h30: com "cita a ultima" o parecer imprimia o
    404 do email de CONTROLE, enquanto a prova era o 201 do payload de injecao
    duas chamadas antes. O contraste E' a prova -- "com o payload deu 201, sem o
    payload deu 404" e' o que um humano precisa ver, e uma linha so' escolhia
    justamente a metade sem graca.

    Teto de 4 para o bloco nao virar dump; o artefato em disco tem tudo.

    ⚠️ Devolve LISTA, e nao um bloco de texto ja' formatado com `\\n` e recuo de
    dois espacos. O recuo era tipografia de terminal embutida no dado: para
    virar item de lista no comentario do PR, `bloco_agrupado` tinha que
    desmontar a string de volta com `.replace("EVIDENCIA: ", "")`. Quem monta o
    fato entrega o fato; o recuo e' do estilo.
    """
    estilo = estilo or superficie.TERMINAL
    if not (art or {}).get("alcancou_a_api"):
        return None
    completas = [c for c in art["chamadas"] if c["status"] is not None and not c["erro"]]
    mostradas = completas[-4:]
    linhas = [
        estilo.monoespaco(
            f"{c['metodo']} {c['caminho']} como {c['como']} -> HTTP {c['status']}")
        for c in mostradas
    ]
    omitidas = len(completas) - len(mostradas)
    if omitidas:
        linhas.insert(0, f"(+{superficie.conta(omitidas, 'chamada')} antes, no artefato)")
    return ["Contra o app rodando:", *linhas,
            estilo.artefato(f"artefatos/http_{art['id']}.json")]


# O desafio nomeia cinco categorias; nos usamos seis, mais granulares. Traduzir
# na saida mantem a granularidade interna e entrega ao jurado o rotulo dele --
# ler um nome que nao e' o seu e' atrito de graca no minuto do parecer.
_CATEGORIA_DO_DESAFIO = {
    "injection": "security",
    "vazamento_de_contexto": "security",
    "correcao": "correctness",
    "performance": "performance",
    "padroes": "convention or pattern",
    "prd": "PRD divergence",
}


# Os rotulos, num lugar so'. A fusao remonta o bloco por ELES, entao um rotulo
# escrito duas vezes -- aqui e la' -- e' a "chave em dois lugares" do CLAUDE.md
# esperando para divergir na primeira vez que alguem reescrever um texto.
O_QUE = "O que"
ARBITRO = "Árbitro"
CORROBORADO = "Corroborado por"
CONVERGENCIA = "Convergência"
FUSAO = "Fusão"
EVIDENCIA = "Evidência"
E_TAMBEM = "E também"
TAMBEM_PROVADO = "Também provado por"
CONSERTO = "Conserto sugerido"
REGRAS = "Regras"


def _campos(v: dict, acusacao: dict, artefato: dict | None,
            http: dict | None = None, estilo=None) -> tuple[dict, list]:
    """O bloco como FATOS rotulados: a cabeca, e os campos `(rotulo, valor)`.

    🚨 Separado de `_bloco` porque a fusao precisa MEXER na estrutura -- por o
    "Convergência" logo depois do "O que", as outras provas logo antes do
    conserto -- e ate' aqui ela fazia isso procurando `"O QUE:"` dentro do texto
    ja' formatado. Convencao de string carregando estrutura e' o item 4 do "como
    procurar" do CLAUDE.md, e o preco chegou no dia em que a saida ganhou uma
    SEGUNDA superficie: em markdown os rotulos mudam de forma, e todo o
    remonte apagaria em silencio -- o bloco sairia sem convergencia, e um
    defeito voltaria a parecer tres.

    O valor de um campo e' texto, ou uma lista onde o primeiro item e' a frase e
    o resto sao sub-linhas (recuo no terminal, item de lista no markdown).
    """
    estilo = estilo or superficie.TERMINAL
    interna = acusacao.get("categoria", "?")
    cabeca = {
        "severidade": v.get("severidade", "?"),
        "confianca": acusacao.get("confianca", "?"),
        "categoria": _CATEGORIA_DO_DESAFIO.get(interna, interna),
        "local": _local(acusacao),
    }
    campos = [
        (O_QUE, acusacao.get("hipotese", "-")),
        # Com procedencia a linha vira "a regra (arquivo:linha)", e o leitor do
        # parecer pode ir conferir. Era isso que "ARBITRO: AC2" nunca permitiu.
        (ARBITRO, arbitro.formata(acusacao.get("arbitro"))),
    ]
    # Ferramenta deterministica e INDEPENDENTE apontou o mesmo lugar. E' sinal
    # de forca diferente de "duas lentes concordaram" -- as duas lentes sao o
    # mesmo modelo. Sem imprimir, o sinal morre em disco.
    #
    # ⚠️ Cita a ferramenta VERBATIM em vez de resumir. "Corroborado por bandit"
    # deixa o leitor supor que a ferramenta confirmou ESTE achado; o scanner
    # afirmou uma coisa especifica sobre aquela linha, e quem le tem que poder
    # julgar se aquilo sustenta este achado ou so' cai perto.
    for s in acusacao.get("_scanner", [])[:2]:
        campos.append((
            CORROBORADO,
            f"{s.get('ferramenta', '?')} em {s.get('local', '?')} "
            f'-- "{str(s.get("texto") or "")[:110]}"',
        ))
    http_ = _evidencia_http(http, estilo)
    if artefato and artefato.get("estado") == "PROVADO":
        campos.append((EVIDENCIA, [
            f"{estilo.monoespaco(artefato['arquivo_do_teste'])} passa em "
            f"{artefato['commit_base']} e falha em {artefato['commit_head']} "
            f"(exit {artefato['exit_base']} -> {artefato['exit_head']}).",
            estilo.artefato(f"artefatos/prova_{artefato['id']}.json"),
        ]))
        # Causalidade e alcance sao provas diferentes, e as duas juntas valem
        # mais: o teste diz que foi esta mudanca, o HTTP diz que da' para fazer
        # agora, de fora.
        if http_:
            campos.append((E_TAMBEM, http_))
    elif http_:
        campos.append((EVIDENCIA, http_))
    else:
        campos.append((EVIDENCIA,
                       f"Não fechou. {v.get('motivo') or 'sem motivo registrado'}"))
    if v.get("conserto"):
        campos.append((CONSERTO, v["conserto"]))
    if v.get("regras_aplicadas"):
        campos.append((REGRAS, " | ".join(v["regras_aplicadas"])))
    return cabeca, campos


def _bloco(v: dict, acusacao: dict, artefato: dict | None,
           http: dict | None = None, estilo=None) -> str:
    estilo = estilo or superficie.TERMINAL
    return estilo.bloco(*_campos(v, acusacao, artefato, http, estilo))


def _posicao(campos: list, rotulo: str, depois: bool) -> int:
    """O indice onde entra um campo novo, relativo ao `rotulo`.

    Sem ancora, o fim: perder a ordem custa legibilidade, perder o conteudo
    custa o achado. E' a mesma escolha que a versao por string ja fazia.
    """
    for n, (r, _) in enumerate(campos):
        if r == rotulo:
            return n + 1 if depois else n
    return len(campos)


def _principal(grupo: list[dict], artefatos: dict, http: dict) -> dict:
    """Qual membro do grupo o autor le primeiro: o de prova mais forte.

    Prova diferencial ganha de ponta a ponta por HTTP, que ganha de nenhuma --
    e' a mesma ordem que a R1 e a R2 usam para sustentar severidade. Empate
    fica com a ordem que o juiz ja deu (severidade).
    """
    def forca(v):
        art = artefatos.get(v.get("id")) or {}
        return (art.get("estado") == "PROVADO", bool(http.get(v.get("id"))))
    return max(grupo, key=lambda v: (forca(v), -grupo.index(v)))


def bloco_agrupado(grupo: list[dict], acusacoes: dict, artefatos: dict,
                   http: dict | None = None,
                   prova: tuple[str, dict] | None = None,
                   estilo=None) -> str:
    """Um defeito, com toda a prova que as lentes juntaram nele.

    🚨 O grupo NAO descarta os outros membros. Cada um continua com id, arquivo
    de teste e artefato citados -- a fusao junta a APRESENTACAO, nunca apaga
    verificacao. Tres arquivos de teste diferentes provando a mesma invariante
    valem MAIS que um; o que estava errado era contar isso como tres defeitos.

    ⚠️ "lentes", nunca "revisores independentes": sao seis chamadas do mesmo
    modelo. E' a mesma honestidade que `_corroborado` guarda em promotores.py.
    """
    estilo = estilo or superficie.TERMINAL
    http = http or {}
    if len(grupo) == 1:
        v = grupo[0]
        return _bloco(v, acusacoes.get(v["id"], {}), artefatos.get(v["id"]),
                      http.get(v["id"]), estilo)
    # `prova` chega do disco (fusao.json). Sem ela o bloco continua saindo -- so'
    # que dizendo que o agrupamento foi indicio, nunca calando a diferenca.

    chefe = _principal(grupo, artefatos, http)
    cabeca, campos = _campos(chefe, acusacoes.get(chefe["id"], {}),
                             artefatos.get(chefe["id"]), http.get(chefe["id"]), estilo)

    # O cabecalho passa a mostrar a extensao do DEFEITO, e nao a linha do membro
    # que por acaso liderou: o autor recebe um lugar so' para olhar, e ele cobre
    # o que as lentes apontaram.
    cabeca["local"] = fusao.local_do_grupo(grupo, acusacoes)

    nomes = [_CATEGORIA_DO_DESAFIO.get(c, c) for c in fusao.lentes(grupo, acusacoes)]
    # ⚠️ Acusacoes e lentes sao contagens DIFERENTES, e a rodada 2 tinha 3
    # acusacoes de 2 lentes -- uma lente acusou duas vezes. Dizer "2 lentes,
    # nao 3 problemas" na mesma frase faz o leitor procurar o numero que falta.
    convergencia = (
        f"{superficie.conta(len(grupo), 'acusação', 'acusações')} independentes, "
        f"de {superficie.conta(len(nomes), 'lente')} do revisor "
        f"({', '.join(nomes)}), caem neste mesmo defeito, cada uma com prova "
        f"própria. É UM defeito com UM conserto, não "
        f"{len(grupo)} problemas separados."
    )
    extras = []
    for v in grupo:
        if v is chefe:
            continue
        art = artefatos.get(v["id"]) or {}
        # ⚠️ `evidencia`, e nao `prova`: chamar esta local de `prova` sombreava o
        # PARAMETRO `prova` da funcao, e a guarda `if prova is not None` passava
        # a ler a string do ultimo membro do laco. O bloco saia com uma frase de
        # fusao fabricada a partir de caracteres soltos -- e sem os testes de
        # render isso teria ido para o comentario de PR de alguem.
        if art.get("estado") == "PROVADO":
            evidencia = (f"{estilo.monoespaco(str(art.get('arquivo_do_teste')))} passa "
                         f"em {art.get('commit_base')} e falha em {art.get('commit_head')}")
        else:
            achado = _evidencia_http(http.get(v["id"]), estilo)
            evidencia = "; ".join(achado) if achado else (v.get("motivo") or "sem artefato")
            evidencia = str(evidencia).replace("\n", " ")[:160]
        extras.append(f"{v['id']}: {evidencia}")

    # 🚨 A ordem e' do leitor, nao do codigo. A convergencia sobe para logo
    # depois do "O que" -- e' a primeira coisa que muda a leitura de "tres
    # problemas" para "um" -- e o conserto fica sendo o ultimo campo, que e' a
    # acao.
    campos.insert(_posicao(campos, O_QUE, depois=True), (CONVERGENCIA, convergencia))
    if prova is not None:
        campos.insert(_posicao(campos, CONVERGENCIA, depois=True),
                      (FUSAO, pfus.frase(prova[0], prova[1], len(grupo))))
    if extras:
        # Antes do conserto; sem conserto, antes das regras; sem as duas, no fim.
        antes = min(_posicao(campos, CONSERTO, depois=False),
                    _posicao(campos, REGRAS, depois=False))
        campos.insert(antes, (TAMBEM_PROVADO,
                              ["As outras lentes, cada uma com a prova dela:", *extras]))
    return estilo.bloco(cabeca, campos)


def _cabecalho_do_escopo(escopo: dict | None, examinadas: int) -> list[str]:
    """A primeira linha do parecer, e o que ela deixa de implicar.

    🚨 Ate' 15\\08 ela era so' "3 com parecer, 0 descartados, 0 inconclusivos",
    numa rodada que partiu de 24 suspeitas. Nenhum numero ali era falso e o
    conjunto mentia: quem lia via uma rodada completa.

    Duas mudancas, e a segunda importa tanto quanto a primeira:

    1. o total entra, com o teto que o produziu
    2. as tres contagens passam a ser "das N examinadas" -- assim, mesmo sem
       escopo gravado, o cabecalho nao afirma mais que N era tudo que havia
    """
    if not escopo:
        return [f"{examinadas} suspeitas examinadas nesta rodada."]
    levantadas = escopo.get("levantadas", examinadas)
    teto = escopo.get("teto")
    linha = f"{levantadas} suspeitas levantadas, {examinadas} testadas"
    linha += f" dentro do orcamento da rodada (TOP_N={teto})." if teto else "."
    return [linha]


def _secao_nao_testadas(escopo: dict | None, estilo=None) -> list[str]:
    """As levantadas que ficaram fora do orcamento -- com o motivo de cada uma.

    ⚠️ Elas NAO sao descartes, e a secao diz isso na primeira linha. Um descarte
    passou pela pericia e voltou com motivo; estas nunca foram olhadas. Junta-las
    a lista de descartados seria a mesma absolvicao falsa que somar INCONCLUSIVO
    com REFUTADO -- so' que na entrada do funil em vez da saida.
    """
    estilo = estilo or superficie.TERMINAL
    if not escopo or not escopo.get("nao_testadas"):
        return []
    n = escopo["nao_testadas"]
    fora = escopo.get("fora_do_orcamento") or []
    p = ["", "## LEVANTADAS E NAO TESTADAS", ""]
    p.append(
        f"{superficie.conta(n, 'suspeita')} não "
        f"{superficie.plural(n, 'entrou', 'entraram')} no orçamento desta "
        "rodada. Não são descartes: nenhuma foi examinada, nenhuma tem "
        "veredito. Estão na ordem em que a fila as alcançaria com um teto maior."
    )
    fundidas = escopo.get("fundidas_por_duplicata")
    if fundidas:
        p += ["", "(Outra suspeita era duplicata e foi fundida na acusação "
              "equivalente, antes da fila.)" if fundidas == 1 else
              f"(Outras {fundidas} eram duplicatas e foram fundidas na "
              "acusação equivalente, antes da fila.)"]
    # 🚨 Com HIPOTESE, e nao so' a contagem acima. A fundida por engano some da
    # verificacao; se ela sumir tambem do texto, o autor do PR nunca fica
    # sabendo que aquela suspeita existiu. A cortada por orcamento sempre teve
    # esse tratamento -- dar menos a esta invertia a gravidade das duas.
    detalhe_fundidas = escopo.get("fundidas") or []
    if fundidas and not detalhe_fundidas:
        # Rodada anterior a 18/08: o escopo gravou a contagem e nao a lista.
        # Dizer que nao se sabe e' o unico desfecho honesto -- e' o mesmo
        # tratamento que `fora_do_orcamento` ja da' ao caso equivalente.
        p += ["", "_o detalhamento das fundidas não foi gravado nesta rodada._"]
    if detalhe_fundidas:
        p.append("")
        p.append("_Fundidas como duplicata (mesmo local e mesma regra citada). "
                 "Não foram verificadas em separado:_")
        for f in detalhe_fundidas:
            rotulo = _CATEGORIA_DO_DESAFIO.get(f.get("categoria"), f.get("categoria", "?"))
            hip = str(f.get("hipotese") or "-")
            if len(hip) > 140:
                hip = hip[:137] + "..."
            p.append(f"- {rotulo} em {f.get('local', '?')}: {hip} "
                     f"_(fundida em `{f.get('fundida_em')}`)_")
    p.append("")
    if not fora:
        # Rodada anterior ao registro do escopo. A contagem se reconstroi do
        # `acusacoes_brutas.json`; o detalhamento, nao. Dizer que nao se sabe e'
        # o unico desfecho honesto -- calar seria voltar ao bug de origem.
        p += ["", "_o detalhamento não foi gravado nesta rodada; a contagem "
              "vem de `acusacoes_brutas.json`, e pode incluir duplicatas._"]
        return p
    return p + _fila_por_regiao(fora, estilo)


def _fila_por_regiao(fora: list[dict], estilo) -> list[str]:
    """A fila agrupada pelo PEDACO DE ARQUIVO que ela aponta.

    🚨 O defeito que isto conserta esta publicado no `bancada#1`: oito
    marcadores, todos sobre `app/main.py:97-108`, logo abaixo de um cabecalho
    que diz "1 achado com evidencia". O autor le nove problemas. E' a inflacao
    de acusacao que a fusao existe para matar, sobrevivendo do outro lado da
    mesma tela.

    🚫 E o conserto NAO e' aplicar a fusao aqui. Medido em 20/08 sobre a rodada
    que esta no ar: a chave estrita colapsa os oito em SETE -- tres tem
    `arbitro` nulo, tres apontam regiao mais larga que o teto de corroboracao.
    Seria um no-op com cara de conserto, que e' pior que nao mexer.

    O que da' para afirmar sem artefato e' o ENDERECO, e so' ele. Por isso o
    agrupamento e' por endereco e **diz que e'**: estas suspeitas nunca foram
    examinadas, e chamar de "um defeito" o que ninguem testou seria a fusao
    inferindo em vez de provar -- o unico lugar do pipeline que a tese do
    produto proibe.
    """
    grupos = fusao.agrupa_por_endereco(fora)
    varios = [g for g in grupos if len(g) > 1]
    p: list[str] = []
    if varios:
        maior = max(varios, key=len)
        quantas = (f"Todas as {len(maior)}" if len(maior) == len(fora)
                   else f"{len(maior)} destas suspeitas")
        p.append("")
        p.append(
            f"⚠️ **{quantas} apontam o mesmo trecho** "
            f"({estilo.local(fusao.regiao(maior))}). Estão juntas abaixo para "
            "você ler o trecho uma vez &mdash; agrupar por endereço **não** é "
            "dizer que são o mesmo defeito, e nenhuma delas foi examinada."
        )
    for g in grupos:
        p.append("")
        if len(g) > 1:
            p.append(f"**{estilo.local(fusao.regiao(g))}** &mdash; "
                     f"{superficie.conta(len(g), 'suspeita')} sobre este trecho:")
        for f in g:
            rotulo = _CATEGORIA_DO_DESAFIO.get(f.get("categoria"),
                                               f.get("categoria", "?"))
            hip = str(f.get("hipotese") or "-")
            if len(hip) > 140:
                hip = hip[:137] + "..."
            # ⚠️ Dentro de um grupo o caminho sai, mas a LINHA fica. A
            # primeira versao apagava o endereco inteiro do item agrupado e
            # deixava so' o cabecalho da regiao -- o que trocava oito
            # repeticoes de `app/main.py` por perder a linha exata de cada
            # suspeita. O ruido era o caminho repetido, nao a linha.
            faixa = fontes._faixa(_local(f))
            if len(g) > 1 and faixa is not None:
                _, ini, fim = faixa
                onde = f" (linha {ini})" if ini == fim else f" (linhas {ini}-{fim})"
            else:
                onde = f" em {estilo.local(_local(f))}"
            p.append(f"- {f.get('posicao','?')}º na fila | {rotulo}{onde}: "
                     f"{hip} _({f.get('motivo','-')})_")
    return p


def formata_parecer(organizado: dict, acusacoes: dict, artefatos: dict,
                    http: dict | None = None, escopo: dict | None = None) -> str:
    """As duas ultimas listas sao a peca que nenhum outro time vai ter.

    Elas precisam ser enquadradas em voz alta no pitch, senao soam como
    confissao de erro em vez de interpretabilidade.
    """
    http = http or {}
    p: list[str] = ["# PARECER", ""]
    c, d, i = organizado["condenados"], organizado["descartados"], organizado["inconclusivos"]

    # Antes do cabecalho: a contagem "com parecer" e' de DEFEITOS refinados pela
    # prova, e o cabecalho e' impresso primeiro.
    refinados = pfus.aplica(fusao.agrupa(c, acusacoes), pfus.do_disco())
    p += _cabecalho_do_escopo(escopo, len(c) + len(d) + len(i))
    p += [
        f"Das examinadas: {len(refinados)} com parecer, "
        f"{len(d)} descartados com motivo, "
        f"{len(i)} inconclusivos com causa.",
        "",
        "## CONDENADOS", "",
    ]
    if not c:
        p.append("_nenhum achado sobreviveu a pericia._")
    for grupo, ver, det in refinados:
        p += [bloco_agrupado(grupo, acusacoes, artefatos, http, (ver, det)), ""]

    p += ["## DESCARTADOS, COM MOTIVO", ""]
    if not d:
        p.append("_nenhum._")
    for v in d:
        a = acusacoes.get(v["id"], {})
        rotulo = _CATEGORIA_DO_DESAFIO.get(a.get("categoria"), a.get("categoria", "?"))
        p.append(f"- {rotulo} em {_local(a)}: {v.get('motivo','-')}")

    p += ["", "## INCONCLUSIVOS, COM CAUSA", ""]
    if not i:
        p.append("_nenhum._")
    for v in i:
        a = acusacoes.get(v["id"], {})
        rotulo = _CATEGORIA_DO_DESAFIO.get(a.get("categoria"), a.get("categoria", "?"))
        p.append(f"- {rotulo} em {_local(a)}: {v.get('motivo','-')}")

    p += _secao_nao_testadas(escopo)
    p += _secao_efeito_no_banco()
    return "\n".join(p) + "\n"


def _secao_efeito_no_banco() -> list[str]:
    """O que a pericia deixou no banco do app.

    No PARECER, e nao so' no console: o console rola e o arquivo fica. Quem le
    o parecer amanha precisa saber o que aquela rodada mexeu -- e se removeu
    linha, precisa saber sem ter que procurar.

    Silencio quando nao houve efeito e' proposital: linha a mais no parecer sem
    conteudo treina o leitor a pular a secao, e ai ela nao serve quando importa.
    """
    d = _carrega_json(cfg.RODADA / "efeito_no_banco.json", {}).get("delta") or {}
    if not d or (d.get("limpo") and d.get("medido", True)):
        return []
    p = ["", "## EFEITO NO BANCO DO APP", ""]
    # 🚨 Medicao falhada tem que aparecer no PARECER, nao so' no console: o
    # console rola e o arquivo fica. Quem le amanha precisa saber que ninguem
    # olhou -- caso contrario a ausencia da secao passa a significar "limpo",
    # que e' exatamente a leitura errada que custou seis rodadas em 15-16/08.
    # 🚫 NAO SE APLICA vem antes de NAO MEDIDO, e nao pode usar a frase dele.
    # "A rodada pode ter criado ou removido linhas" e' FALSO num projeto onde
    # nenhuma ferramenta alcanca banco -- e alarme falso repetido em todo PR de
    # terceiro treina o leitor a pular a secao. A guarda morreria de excesso.
    #
    # ⚠️ Dito, nunca omitido: sumir com a secao faria "sem secao" significar
    # duas coisas diferentes, que e' como o `limpo` mudo comecou em 15/08.
    if d.get("aplicavel") is False:
        return p + [
            f"- **NAO SE APLICA**: {d.get('causa')}.",
            "- Nenhum banco foi lido, e nenhum podia ter sido tocado. Isto é "
            "diferente de **NAO MEDIDO**, que é quando havia banco e o retrato "
            "falhou.",
        ]
    if not d.get("medido", True):
        return p + [
            f"- **NAO MEDIDO**: o retrato do banco falhou. `{d.get('causa')}`",
            "- Isto **não** é 'não houve efeito'. A rodada pode ter criado ou "
            "removido linhas, e este parecer não sabe.",
        ]
    if d.get("houve_remocao"):
        p.append(f"- **A rodada REMOVEU linhas** de `{d.get('banco')}`: "
                 f"{d['removidas']}. Criar linha para provar defeito em endpoint "
                 f"de escrita e' esperado; remover nunca e'.")
    if d.get("criadas"):
        p.append(f"- criou em `{d.get('banco')}`: {d['criadas']} "
                 f"(prova de defeito em caminho de escrita)")
    p.append(f"- nao detectado por este metodo: {d.get('nao_detecta')}")
    return p


# ------------------------------------------------------------------- carga

def _carrega_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return padrao


def _por_id(padrao: str) -> dict:
    artefatos = {}
    if cfg.ARTEFATOS.is_dir():
        for f in cfg.ARTEFATOS.glob(padrao):
            art = _carrega_json(f, None)
            if art and "id" in art:
                artefatos[art["id"]] = art
    return artefatos


def _escopo_do_disco(examinadas: int) -> dict | None:
    """O escopo da rodada, e o que sobra quando ele nao foi gravado.

    🚨 Padrao de bug do projeto: a guarda que so' funciona quando o artefato
    existe fica muda exatamente onde ele falta. Aqui o artefato e' o
    `escopo.json`, que so' passou a ser gravado em 15\\08 -- entao toda rodada
    anterior cairia no caso mudo e voltaria a imprimir o cabecalho antigo.

    Por isso a contagem tem uma segunda fonte: `acusacoes_brutas.json`, gravado
    desde sempre. O detalhamento nao se reconstroi, e o parecer diz isso; a
    contagem, que e' o que impede o cabecalho de mentir, se reconstroi.
    """
    e = _carrega_json(cfg.RODADA / "escopo.json", None)
    if isinstance(e, dict) and "levantadas" in e:
        return e
    brutas = _carrega_json(cfg.RODADA / "acusacoes_brutas.json", None)
    if not isinstance(brutas, list) or len(brutas) <= examinadas:
        return None
    return {
        "levantadas": len(brutas),
        "testadas": examinadas,
        # Sem o escopo gravado, duplicatas fundidas e nao-testadas caem no mesmo
        # balde. O numero e' um teto do que ficou sem exame, e a secao avisa.
        "nao_testadas": len(brutas) - examinadas,
        "fundidas_por_duplicata": None,
        "teto": None,
        "fora_do_orcamento": [],
    }


def carrega_do_disco() -> tuple[list[dict], dict, dict, dict, dict, dict | None]:
    """Le o que as outras etapas gravaram.

    Ajustar o juiz pela trigesima vez nao pode re-executar o advogado -- meia
    hora de disciplina que se paga dez vezes.
    """
    veredictos = _carrega_json(cfg.RODADA / "veredictos.json", [])
    acusacoes = {a["id"]: a for a in _carrega_json(cfg.RODADA / "acusacoes.json", []) if "id" in a}
    avisos = _carrega_json(cfg.ARTEFATOS / "avisos.json", {})
    # prova_* = teste diferencial (causalidade). http_* = app rodando (alcance).
    return (veredictos, acusacoes, _por_id("prova_*.json"), avisos,
            _por_id("http_*.json"), _escopo_do_disco(len(veredictos)))


def sentencia() -> str:
    veredictos, acusacoes, artefatos, avisos, http, escopo = carrega_do_disco()
    organizado = organiza(veredictos, acusacoes, artefatos, avisos, http)
    texto = formata_parecer(organizado, acusacoes, artefatos, http, escopo)
    cfg.prepara_pastas()
    (cfg.RODADA / "parecer.md").write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    print(sentencia())
