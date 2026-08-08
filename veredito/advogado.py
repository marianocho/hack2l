"""hack2l / Veredito -- o advogado. A unica peca que e' agente de verdade.

Loop: pensa -> ferramenta -> resultado -> decide. Ele NAO argumenta, TESTA.

Ve UMA acusacao por vez, isolado. Sem historico compartilhado entre acusacoes:
uma acusacao fraca nao contamina a proxima, e o prefixo do diff fica identico em
todas as chamadas, que e' o que faz o cache pagar.
"""

from __future__ import annotations

import json
import re
import time

import anthropic

from . import config as cfg
from . import ferramentas

# O prompt e' produto, nao configuracao. Cada paragrafo aqui existe por um
# motivo que custou caro em outro lugar.
SISTEMA = """Voce e' o ADVOGADO do Veredito, um revisor de codigo autonomo.

Voce recebe UMA acusacao sobre um pull request e tem um trabalho so: descobrir
se ela se sustenta, produzindo um ARTEFATO REPRODUZIVEL. Voce nao argumenta,
nao opina e nao avalia plausibilidade. Voce testa.

## O que conta como prova

Um artefato que outra pessoa possa rodar e ver o mesmo resultado. Nada mais.
Codigo que "parece errado" nao e' prova. Raciocinio convincente nao e' prova.

## Escreva o teste sobre a INVARIANTE, nao sobre o endpoint

`prova_diferencial` so assina PROVADO se o teste passa no base e falha no head.
Isso parece impedir provar defeito em endpoint NOVO -- um teste que chama
/shared/{id} da 404 no base, que e' falha, e o resultado sai inconclusivo.

A saida e' escrever o teste sobre a REGRA que o PR deveria respeitar, nao sobre
o codigo que ele adicionou:

  ruim:  "GET /shared/1 como carol devolve 200"     -> 404 no base, inconclusivo
  bom:   "carol nao alcanca o documento de alice
          por nenhuma rota"                          -> passa no base (nao havia
                                                         como vazar), falha no
                                                         head. PROVADO.

A invariante quase sempre ja vale no commit base -- e' por isso que ela e'
invariante. Formule assim e a prova diferencial serve para os dois casos.

Se ainda assim nao der, `http_request` mostra o comportamento errado
acontecendo de fora, autenticado como usuario do seed.

## Prove das duas formas quando puder

Um teste diferencial prova CAUSALIDADE: foi esta mudanca que quebrou.
Um `http_request` prova ALCANCE: da para fazer isso de fora, agora.

Sao coisas diferentes e a segunda vale mais. Uma acusacao provada so por teste
e' rebaixada a MEDIA automaticamente; so prova ponta a ponta pela API sustenta
severidade alta. Se o app esta no ar e o defeito e' alcancavel, faca as duas --
custa uma volta e muda a severidade.

## A linha de base do isolamento, ja medida

demo tem 3 documentos. alice tem 1. bob tem 1. carol NAO TEM NADA.
carol e' o controle negativo: qualquer dado de outro usuario que apareca para
ela e' vazamento. Uma chamada como carol vale mais que um paragrafo de analise.

## Ausencia de observacao nao e' refutacao

Se o payload nao surtiu efeito porque o modelo do app alvo esta duble, se o
docker caiu, se o teste nao coletou, se deu timeout -- o veredito e'
INCONCLUSIVO, com a causa. Nunca REFUTADO. As ferramentas avisam quando isso
acontece; leia o aviso.

REFUTADO e' um resultado forte e significa uma coisa so: voce testou, o teste
rodou, e a acusacao nao se sustentou.

## Economia do loop

Voce tem NO MAXIMO {teto} voltas de ferramenta. Isso e' pouco, e acabar sem
veredito e' um fracasso -- a acusacao vira inconclusiva e o trabalho se perde.

Orcamento tipico: 1 a 2 voltas para se situar, 1 para montar a prova, 1 para
rodar. Va direto ao ponto de prova. Nao leia arquivo por curiosidade, nao
confirme o que a acusacao ja te disse, nao explore o repo. Se depois de 3
voltas voce ainda nao sabe como provar, decida a estrategia e execute com o que
tem.

## Formato da resposta final

Quando terminar, responda APENAS com um objeto JSON, sem cercas de codigo e sem
texto em volta:

{"veredito": "PROVADO|REFUTADO|INCONCLUSIVO",
 "severidade": "CRITICA|ALTA|MEDIA|BAIXA",
 "prova_ponta_a_ponta": true|false,
 "motivo": "uma frase",
 "conserto": "uma frase, so se PROVADO"}

`prova_ponta_a_ponta` e' true apenas se a falha foi demonstrada pela API
rodando (`http_request`), nao por chamada direta de funcao.
`motivo` explica o que aconteceu: por que provou, por que nao se sustentou, ou
o que foi tentado e por que nao fechou."""


FECHAMENTO = (
    "Voce chegou ao teto de voltas. Nao ha mais ferramenta disponivel.\n\n"
    "Responda AGORA com o JSON do veredito, a partir do que voce ja apurou.\n"
    "Se conseguiu um artefato reproduzivel, o veredito e' PROVADO ou REFUTADO "
    "conforme o resultado. Se nao chegou la, o veredito e' INCONCLUSIVO e o "
    "campo `motivo` precisa dizer O QUE VOCE TENTOU e por que nao fechou -- "
    "esse texto vai para o parecer, entao seja especifico e util."
)


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)


def diff_do_pr() -> str:
    """O diff base..head. Prefixo IDENTICO em toda chamada -- e' o que cacheia.

    Nunca imprimir: o time nao pode ver o diff antes do agente trabalhar.
    """
    base, head = ferramentas.commit_base(), ferramentas.commit_head()
    r = ferramentas._git("diff", f"{base}..{head}")
    if r.returncode != 0:
        raise RuntimeError(f"git diff falhou: {r.stderr.strip()}")
    return r.stdout


def _texto_final(msg) -> str:
    return "\n".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def _parse_veredicto(texto: str) -> dict:
    """try/except com a saida crua no fallback.

    Um veredicto nunca morre por erro de formato: sem isto, uma acusacao provada
    sumiria do parecer porque o modelo pos uma cerca de codigo em volta do JSON.

    🚨 A versao ganancioso (`re.search(r"\\{.*\\}", DOTALL)`) casava do PRIMEIRO
    `{` ate o ULTIMO, e o advogado escreve prosa antes do JSON. Na rodada das
    12h15 a prosa citava `SELECT ... email = '{email}'` e a rota
    `/documents/{id}/share`: o span comecou em `{email}`, o json.loads quebrou, e
    um PROVADO **com artefato no disco** virou INCONCLUSIVO por formatacao. E'
    exatamente a falha que este fallback existia para impedir.

    Entao: `raw_decode` a partir de cada `{`, do fim para o comeco. O ultimo
    objeto valido com `veredito` ganha -- que e' o veredito final, e nao uma
    chave qualquer que apareceu no meio do texto.
    """
    bruto = texto.strip()
    dec = json.JSONDecoder()
    for i in reversed([m.start() for m in re.finditer(r"\{", bruto)]):
        try:
            v, _ = dec.raw_decode(bruto[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(v, dict) and v.get("veredito"):
            return v
    return {
        "veredito": "INCONCLUSIVO",
        "motivo": "o advogado nao devolveu JSON valido; saida crua preservada",
        "saida_crua": bruto[:2000],
    }


def _diagnostico_da_recusa(msg) -> str:
    """A causa da recusa, com o que o SDK sabe e a gente estava descartando.

    Verificado no anthropic 0.120.2 instalado, nao de memoria: `fallbacks` E'
    aceito pelo tool_runner (esta na assinatura em
    resources/beta/messages/messages.py, nas duas sobrecargas), o escalar
    "default" E' valido (BetaFallbacksParam = Union[Iterable[...], "default"])
    e `cyber` E' categoria coberta -- a docstring do proprio SDK diz que
    "benign cybersecurity work can also trigger this category".

    Ou seja: o pareamento esta certo, e uma recusa que chega aqui significa uma
    de DUAS coisas, que pedem acoes diferentes:

      fallback nao rodou  -- rate limit ou sobrecarga no modelo de fallback. O
                             servidor preenche `recommended_model`, e um retry
                             direto nele tem chance de passar.
      cadeia toda recusou -- o fallback rodou e tambem recusou. Sinal: um item
                             `fallback_message` em usage.iterations.

    Sem distinguir, o parecer diz so "recusa do classificador": verdade, e
    inutil. A regra do desafio e' INCONCLUSIVO **com a causa**.
    """
    partes = ["recusa do classificador"]
    det = getattr(msg, "stop_details", None)
    if det is not None and getattr(det, "category", None):
        partes.append(f"categoria {det.category}")

    recomendado = getattr(det, "recommended_model", None) if det is not None else None

    # TRES sinais, porque cada um sozinho tem um buraco -- e o nosso caminho e'
    # streaming, onde o primeiro nao aparece.
    #
    #   usage.iterations  -- o "served-by" canonico. Medido em 08/08 13h25: NAO
    #                        veio na recusa pelo tool_runner com stream=True.
    #   bloco `fallback`  -- em streaming a troca chega como content_block comum,
    #                        marcando o ponto de virada. E' o sinal do stream.
    #   msg.model         -- se quem respondeu nao e' quem pedimos, alguem mais
    #                        rodou. Pega o caso sticky, que nao emite bloco.
    iteracoes = getattr(getattr(msg, "usage", None), "iterations", None) or []
    conteudo = getattr(msg, "content", None) or []
    servido_por = getattr(msg, "model", None)
    rodou = (
        any(getattr(i, "type", None) == "fallback_message" for i in iteracoes)
        or any(getattr(b, "type", None) == "fallback" for b in conteudo)
        or bool(servido_por and servido_por != cfg.MODEL_ADVOGADO)
    )

    if recomendado:
        partes.append(
            f"o fallback NAO foi tentado (rate limit ou sobrecarga); "
            f"o servidor sugere retry direto em {recomendado}"
        )
    elif rodou:
        quem = f" ({servido_por})" if servido_por else ""
        partes.append(f"o fallback rodou{quem} e tambem recusou -- a cadeia inteira negou")
    else:
        # Terceiro estado aplicado ao proprio diagnostico: nao inventar causa.
        partes.append(
            f"nenhum dos tres sinais de fallback apareceu (servido por "
            f"{servido_por or 'modelo nao informado'}) -- nao da' para afirmar se "
            "a cadeia recusou ou se o fallback nao chegou a ser tentado"
        )
    return " | ".join(partes)


def _soma(uso: dict, u) -> None:
    if not u:
        return
    for campo, chave in (
        ("input_tokens", "tokens_entrada"),
        ("output_tokens", "tokens_saida"),
        ("cache_read_input_tokens", "cache_read"),
        ("cache_creation_input_tokens", "cache_write"),
    ):
        uso[chave] += getattr(u, campo, 0) or 0


def julga(acusacao: dict, diff: str) -> dict:
    """Uma acusacao. Devolve o veredicto que o juiz vai ler."""
    id_ = acusacao.get("id", "sem_id")
    ferramentas.define_acusacao(id_)
    inicio = time.time()
    uso = {"tokens_entrada": 0, "tokens_saida": 0, "cache_read": 0, "cache_write": 0}
    v: dict = {
        "id": id_, "veredito": "INCONCLUSIVO", "severidade": "BAIXA",
        "prova_ponta_a_ponta": False, "motivo": "o loop nao chegou a concluir",
        "voltas": 0, "erro": None,
    }

    try:
        runner = _cliente().beta.messages.tool_runner(
            model=cfg.MODEL_ADVOGADO,
            max_tokens=cfg.MAX_TOKENS_ADVOGADO,
            # Teto do SDK. O break do for abaixo e' redundante de proposito:
            # advogado que nunca para de pedir ferramenta e' o jeito mais rapido
            # de perder a tarde, e uma so das duas travas ja falhou em teste.
            max_iterations=cfg.MAX_VOLTAS_LOOP,
            # Obrigatorio, nao preferencia: com max_tokens alto o SDK recusa a
            # chamada nao-streaming ("Streaming is required for operations that
            # may take longer than 10 minutes"). E precisamos do max_tokens alto
            # porque no Opus 5 ele cobre raciocinio + resposta somados.
            stream=True,
            thinking={"type": "adaptive"},
            output_config={
                "effort": cfg.EFFORT,
                # O modelo SABE que tem orcamento e fecha o parecer em vez de
                # ser cortado no meio.
                "task_budget": {"type": "tokens", "total": cfg.TASK_BUDGET_TOKENS},
            },
            betas=["task-budgets-2026-03-13", "server-side-fallback-2026-07-01"],
            # Recusa do classificador de ciberseguranca vai para o Opus 4.8
            # sozinha, em vez de derrubar a categoria carro-chefe ao vivo.
            fallbacks="default",
            system=[{"type": "text", "text": SISTEMA.replace("{teto}", str(cfg.MAX_VOLTAS_LOOP)),
                     "cache_control": {"type": "ephemeral"}}],
            tools=ferramentas.TOOLS,
            messages=[{"role": "user", "content": [
                # O diff vem ANTES da acusacao: prefixo identico nas N chamadas,
                # entao o cache le a ~10% em vez de reprocessar tudo.
                {"type": "text", "text": f"# Diff do PR sob revisao\n\n{diff}",
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": _prompt_da_acusacao(acusacao)},
            ]}],
        )

        ultima = None
        historico: list = []  # espelho da conversa, para o fechamento abaixo
        estourou = False
        for turno in runner:
            # Com stream=True cada iteracao entrega um stream, nao a mensagem:
            # get_final_message() da a mensagem acumulada daquela volta.
            msg = turno.get_final_message() if hasattr(turno, "get_final_message") else turno
            v["voltas"] += 1
            _soma(uso, getattr(msg, "usage", None))
            ultima = msg

            historico.append({"role": "assistant", "content": msg.content})
            resposta_tool = runner.generate_tool_call_response()
            if resposta_tool is not None:
                historico.append(resposta_tool)

            # stop_reason ANTES de content, sempre. Uma recusa vem como HTTP 200
            # com content vazio, e ler content[0] vira IndexError no meio da
            # rodada.
            if getattr(msg, "stop_reason", None) == "refusal":
                v["erro"] = _diagnostico_da_recusa(msg)
                break

            if v["voltas"] >= cfg.MAX_VOLTAS_LOOP:
                estourou = True
                break
            if time.time() - inicio > cfg.TIMEOUT_ACUSACAO_S:
                estourou = True
                v["timeout"] = True
                break

        if estourou:
            # Bater no teto NAO pode custar a peritagem inteira. Uma chamada
            # final SEM ferramentas obriga o veredito a partir do que ele ja
            # descobriu -- e se nao descobriu nada, ele mesmo diz INCONCLUSIVO
            # com o que tentou, que e' o texto que o parecer precisa.
            v["fechamento_forcado"] = True
            try:
                final = _cliente().beta.messages.create(
                    model=cfg.MODEL_ADVOGADO,
                    max_tokens=4000,
                    output_config={"effort": "low"},
                    tool_choice={"type": "none"},
                    # messages.create nao aceita os objetos do @beta_tool, so o
                    # tool_runner aceita. E as definicoes precisam estar aqui de
                    # qualquer forma: o historico contem blocos tool_use, e a
                    # API rejeita historico com tool_use sem as tools declaradas.
                    tools=[t.to_dict() for t in ferramentas.TOOLS],
                    system=SISTEMA.replace("{teto}", str(cfg.MAX_VOLTAS_LOOP)),
                    messages=[*historico, {"role": "user", "content": FECHAMENTO}],
                )
                _soma(uso, getattr(final, "usage", None))
                if getattr(final, "stop_reason", None) == "refusal":
                    v["erro"] = "recusa do classificador no fechamento"
                else:
                    v.update(_parse_veredicto(_texto_final(final)))
                    v["id"] = id_
            except Exception as e:
                v["erro"] = f"fechamento falhou: {type(e).__name__}: {e}"
        elif v["erro"] is None and ultima is not None:
            v.update(_parse_veredicto(_texto_final(ultima)))
            v["id"] = id_

    except Exception as e:
        v["erro"] = f"{type(e).__name__}: {e}"

    if v["erro"]:
        # Falha de execucao nunca e' absolvicao. O juiz aplica a R3 de novo em
        # cima disto -- duas travas, porque esta e' a que mais custa errar.
        v["veredito"] = "INCONCLUSIVO"
        v["motivo"] = v["erro"]

    v.update(uso)
    v["segundos"] = round(time.time() - inicio, 1)
    return v


def _prompt_da_acusacao(a: dict) -> str:
    return (
        "# A acusacao que voce vai julgar\n\n"
        f"- categoria: {a.get('categoria', '?')}\n"
        f"- local: {a.get('local', '?')}\n"
        f"- hipotese: {a.get('hipotese', '?')}\n"
        f"- arbitro: {a.get('arbitro') or 'nenhum citado'}\n"
        f"- provado_se: {a.get('provado_se', '?')}\n\n"
        "Prove ou refute. Termine com o JSON."
    )

