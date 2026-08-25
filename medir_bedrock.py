"""Mede o que `motor.SEM_NO_BEDROCK` afirma. Nao le a matriz -- manda e olha.

O comentario que declara a constante diz, com todas as letras, "conferido contra
a matriz de disponibilidade por plataforma, nao de memoria". Ler doc melhor e'
melhor que lembrar, e continua sendo LEITURA. Este projeto inteiro e' sobre a
diferenca, e a constante decide o que sai da chamada do advogado: se ela estiver
errada para mais, o produto joga fora `fallbacks` -- a guarda que impede a
categoria carro-chefe de se esvaziar -- de graca, e ninguem descobre, porque a
remocao E' o comportamento esperado. Guarda que some sem avisar, de novo.

O DESENHO: cinco celulas, nao uma chamada
------------------------------------------
Mandar os dois parametros juntos e ver um 400 nao mede NADA sobre qual dos dois
o Bedrock recusa -- e nao adianta mais que a matriz que ja' foi lida. A prova
diferencial do proprio produto e' o molde: sem o lado de controle, a falha nao
tem a quem ser atribuida.

    controle     nenhum dos dois          a chamada minima passa neste motor?
    task_budget  so' ele + a beta dele    isola `task_budget`
    fallback     so' ele + a beta dele    isola `fallbacks`
    ambos        os dois                  o que o advogado mandaria SEM mascara
    mascarado    ambos -> ajusta_chamada  o que o advogado manda HOJE

⚠️ So' os parametros variam entre as celulas. O `model` ja' vai traduzido pelo
motor em TODAS elas, inclusive nas cruas: se o controle fosse com o id sem
prefixo e o `mascarado` com o prefixado, a diferenca medida seria a do prefixo,
nao a do parametro -- e o 404 resultante se leria como recusa.

🚨 `controle` e' a base do diferencial, e a regra que ele compra e' dura: se ele
nao voltar 200, TODA celula vira INCONCLUSIVO, inclusive as que voltaram 400.
Modelo nao habilitado, regiao errada ou credencial sem permissao produzem erro
nas cinco, e ler isso como "o parametro foi recusado" seria fabricar uma medicao
a partir de uma falha de infraestrutura.

🚨 `mascarado` e' o par de `ambos`, e juntos respondem a pergunta que importa --
nao "existe 400?", mas "a mascara e' carga ou peso morto?":

    ambos RECUSADO + mascarado ACEITO   -> SEM_NO_BEDROCK certa, mascara e' carga
    ambos ACEITO   + mascarado ACEITO   -> a constante esta ERRADA PARA MAIS.
                                           O produto perde `fallbacks` a toa.
    ambos RECUSADO + mascarado RECUSADO -> a mascara nao cobre o que devia:
                                           sobrou parametro recusado na chamada

⚠️ 403/404/429 NAO sao veredito sobre parametro. Habilitacao de modelo no
Bedrock e' por conta e por regiao, e o erro e' um 404 que se le como "o modelo
nao existe" -- mesma classe de mentira do 404 do repositorio privado. Isso e'
INCONCLUSIVO nomeando a causa, nunca RECUSADO.

MODO OFFLINE -- e por que ele nao e' consolo
---------------------------------------------
Sem credencial nenhuma, `--offline` roda de graca e em milissegundos, e mede
duas coisas que nao dependem da AWS:

 1. o corpo JSON exato que cada celula poria no fio, capturado no transporte;
 2. que as celulas sao de fato DIFERENTES entre si.

O (2) e' a licao de 19/08 e nao e' formalidade: naquele dia uma mutacao virou
no-op por um literal errado, a suite passou inteira, e aquilo se leu como "a
trava e' fraca". **Sonda que nao manda o parametro e' indistinguivel de
parametro aceito.** Rodar online sem conferir o corpo produziria cinco `ACEITO`
e a conclusao invertida -- e a conclusao invertida aqui e' a que diz "pode rodar
o produto inteiro no credito da AWS".

    py -3.12 medir_bedrock.py --offline      sem credencial, sem rede, sem custo
    py -3.12 medir_bedrock.py --motor bedrock          ~US$0,01, cinco chamadas
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from veredito import config as cfg
from veredito import motor

SAIDA = pathlib.Path(__file__).resolve().parent / "saidas" / "bedrock"

BETA_TASK_BUDGET = "task-budgets-2026-03-13"
BETA_FALLBACK = "server-side-fallback-2026-07-01"


# --- as celulas -------------------------------------------------------------

def _base() -> dict:
    """A chamada minima. Barata de proposito e sem NADA que possa causar 400 por
    conta propria: uma mensagem de uma palavra, teto de token baixo, zero
    ferramenta, zero `thinking`. O erro que sobrar e' sobre o parametro."""
    return {
        "model": motor.modelo(cfg.MODEL_ADVOGADO),
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "oi"}],
    }


def celulas() -> list[tuple[str, dict, str]]:
    """(nome, kwargs CRUS, o que a celula isola).

    🚫 Cruas de proposito: `ajusta_chamada` e' o OBJETO da medicao em `ambos`, e
    passar por ela aqui removeria justo o parametro que queremos ver recusado.
    So' a celula `mascarado` a atravessa, e ela existe para ser o par de `ambos`.
    """
    tb = _base()
    tb["output_config"] = {"task_budget": {"type": "tokens", "total": 20000}}
    tb["betas"] = [BETA_TASK_BUDGET]

    fb = _base()
    fb["fallbacks"] = "default"
    fb["betas"] = [BETA_FALLBACK]

    ambos = _base()
    ambos["output_config"] = {"task_budget": {"type": "tokens", "total": 20000}}
    ambos["fallbacks"] = "default"
    ambos["betas"] = [BETA_TASK_BUDGET, BETA_FALLBACK]

    return [
        ("controle", _base(), "a chamada minima passa neste motor"),
        ("task_budget", tb, "task_budget sozinho, com a beta dele"),
        ("fallback", fb, "fallbacks sozinho, com a beta dele"),
        ("ambos", ambos, "os dois -- o que o advogado mandaria sem mascara"),
        ("mascarado", motor.ajusta_chamada(**ambos),
         "o que ajusta_chamada deixa passar -- a chamada de hoje"),
    ]


# --- classificacao ----------------------------------------------------------
#
# Tres estados, e o terceiro e' obrigatorio. Um 400 e' medicao; um 404 e'
# ausencia de medicao com cara de medicao.

def _classifica(exc: BaseException | None, resposta) -> tuple[str, str]:
    if exc is None:
        return "ACEITO", f"HTTP 200, stop_reason={getattr(resposta, 'stop_reason', '?')}"

    status = getattr(exc, "status_code", None)
    corpo = str(getattr(exc, "message", "") or exc)[:400]

    if status == 400:
        return "RECUSADO", f"HTTP 400 -- {corpo}"
    if status in (401, 403):
        return "INCONCLUSIVO", (
            f"HTTP {status}: a credencial nao tem permissao para este modelo ou "
            f"regiao. Nao e' veredito sobre o parametro -- {corpo}")
    if status == 404:
        return "INCONCLUSIVO", (
            f"HTTP 404: quase sempre MODELO NAO HABILITADO nesta conta e regiao, "
            f"nao modelo inexistente. Habilite em Bedrock > Model access, na "
            f"regiao de AWS_REGION -- {corpo}")
    if status == 429:
        return "INCONCLUSIVO", f"HTTP 429: throttle, nao recusa. Repita -- {corpo}"
    if status is not None:
        return "INCONCLUSIVO", f"HTTP {status} inesperado -- {corpo}"
    return "INCONCLUSIVO", f"{type(exc).__name__}: {corpo}"


def _sela_pelo_controle(linhas: list[dict]) -> list[dict]:
    """🚨 Sem controle verde, nada foi medido -- nem o que voltou 400.

    E' a guarda que a prova diferencial compra, e ela precisa conseguir ficar
    QUIETA: com o controle passando, nao mexe em linha nenhuma. Guarda que
    reescreve sempre ensina a ignorar o campo que ela escreve.
    """
    ctrl = next((l for l in linhas if l["celula"] == "controle"), None)
    if ctrl is not None and ctrl["veredito"] == "ACEITO":
        return linhas
    causa = ctrl["detalhe"] if ctrl else "a celula de controle nao rodou"
    for l in linhas:
        if l["celula"] == "controle":
            continue
        l["veredito_bruto"] = l["veredito"]
        l["veredito"] = "INCONCLUSIVO"
        l["detalhe"] = (f"o controle nao passou, entao esta celula nao mede "
                        f"parametro nenhum. Controle: {causa}")
    return linhas


# --- modo offline: o corpo que iria no fio ----------------------------------

def _cliente_de_captura(caixa: list):
    """Cliente Bedrock de verdade, com o transporte trocado. O caminho de
    serializacao e' o mesmo da rodada real -- e' ele que estamos medindo.

    ⚠️ O transporte devolve 200 em vez de levantar uma sentinela. Levantar do
    dentro do transporte faz o SDK embrulhar tudo em `APIConnectionError` e
    RETENTAR: as celulas viravam cinco erros de conexao identicos, sem corpo
    nenhum -- exatamente o desfecho que a sonda existe para nao produzir.
    """
    def _handler(request: httpx.Request) -> httpx.Response:
        caixa.append({
            "url": str(request.url),
            "header_beta": request.headers.get("anthropic-beta"),
            "corpo": json.loads(request.content or b"{}"),
        })
        return httpx.Response(200, json={
            "id": "msg_offline", "type": "message", "role": "assistant",
            "model": "offline", "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    import anthropic
    return anthropic.AnthropicBedrockMantle(
        aws_region=os.getenv("AWS_REGION") or "us-east-1",
        skip_auth=True,
        http_client=httpx.Client(transport=httpx.MockTransport(_handler)))


def offline() -> dict:
    """O que cada celula poria no fio, sem mandar nada. De graca."""
    # `_escolhe()` no modo forcado exige credencial de proposito (o "forcado
    # levanta"). Aqui nao queremos credencial nenhuma, so' a mascara -- entao o
    # motor bedrock e' injetado direto, e e' o MESMO objeto que `_bedrock()`
    # constroi na rodada real, com a mesma `sem` e o mesmo prefixo.
    motor.esquece()
    motor._ATIVO = motor._bedrock("offline: sem credencial, so' o corpo", "us-east-1")

    linhas = []
    for nome, kw, isola in celulas():
        caixa: list = []
        cli = _cliente_de_captura(caixa)
        try:
            cli.beta.messages.create(**kw)
        except Exception as e:
            linhas.append({"celula": nome, "isola": isola,
                           "erro_local": f"{type(e).__name__}: {e}", "corpo": None})
            continue
        visto = caixa[0] if caixa else {}
        corpo = visto.get("corpo", {})
        linhas.append({
            "celula": nome,
            "isola": isola,
            "url": visto.get("url"),
            "header_beta": visto.get("header_beta"),
            "modelo_no_fio": corpo.get("model") or visto.get("url", "").split("/model/")[-1],
            "tem_task_budget": "task_budget" in (corpo.get("output_config") or {}),
            "tem_fallbacks": "fallbacks" in corpo,
            "betas_no_corpo": corpo.get("anthropic_beta"),
            "betas_no_fio": sorted(_betas_no_fio(visto)),
            "corpo": corpo,
        })
    return {"modo": "offline", "celulas": linhas}


def _betas_no_fio(visto: dict) -> set[str]:
    """As betas que SAEM, olhando os dois lugares onde elas podem sair.

    🚨 Medido, e a primeira versao desta sonda errou exatamente aqui: no Mantle
    a beta viaja SO' no cabecalho `anthropic-beta` e nunca aparece no corpo,
    entao conferir `corpo["anthropic_beta"]` dava lista vazia nas cinco celulas
    e a exigencia passava por vacuidade -- verde, muda, e do lado errado. No
    Bedrock legado e' o contrario: `_prepare_options` copia o cabecalho para
    `anthropic_beta` no corpo. Uniao dos dois, porque a resposta certa depende
    de qual cliente foi construido, e a sonda nao pode depender disso.
    """
    do_corpo = (visto.get("corpo") or {}).get("anthropic_beta") or []
    cabecalho = visto.get("header_beta") or ""
    do_cabecalho = [b.strip() for b in cabecalho.split(",") if b.strip()]
    return set(do_corpo) | set(do_cabecalho)


def confere_offline(res: dict) -> list[str]:
    """A sonda manda mesmo o que diz que manda?

    ⚠️ E' a parte que impede a medicao de mentir a nosso favor. Cada exigencia
    aqui existe porque a violacao dela produziria `ACEITO` em tudo e a conclusao
    invertida.
    """
    por = {l["celula"]: l for l in res["celulas"]}
    falhas: list[str] = []

    def exige(cond, msg):
        if not cond:
            falhas.append(msg)

    faltando = [n for n in ("controle", "task_budget", "fallback", "ambos",
                            "mascarado") if n not in por]
    if faltando:
        return [f"celula(s) que nem chegaram a serializar: {faltando}"]

    # 🚨 Celula que morreu ANTES do fio nao tem corpo para conferir, e as
    # exigencias abaixo levantariam KeyError -- que se le como sonda quebrada em
    # vez de sonda que nao mediu. Nomeia a causa e para aqui.
    quebradas = [(n, l["erro_local"]) for n, l in por.items() if l.get("erro_local")]
    if quebradas:
        return [f"celula '{n}' nao chegou a serializar: {e}" for n, e in quebradas]

    exige(not por["controle"]["tem_task_budget"] and not por["controle"]["tem_fallbacks"],
          "o controle NAO esta limpo -- carrega parametro e deixa de ser base")
    exige(por["task_budget"]["tem_task_budget"],
          "a celula task_budget nao poe task_budget no corpo: sonda no-op")
    exige(not por["task_budget"]["tem_fallbacks"],
          "a celula task_budget carrega fallbacks junto: nao isola nada")
    exige(por["fallback"]["tem_fallbacks"],
          "a celula fallback nao poe fallbacks no corpo: sonda no-op")
    exige(not por["fallback"]["tem_task_budget"],
          "a celula fallback carrega task_budget junto: nao isola nada")
    exige(por["ambos"]["tem_task_budget"] and por["ambos"]["tem_fallbacks"],
          "a celula ambos nao leva os dois: e' ela que mede a mascara")
    exige(not por["mascarado"]["tem_task_budget"] and not por["mascarado"]["tem_fallbacks"],
          "ajusta_chamada NAO removeu os dois do CORPO -- a mascara vaza no fio")

    # As betas, nos dois lugares por onde elas saem -- ver `_betas_no_fio`.
    # Exigir que ELAS APARECAM nas celulas que as mandam e' o que impede a
    # exigencia de baixo de passar por vacuidade: sem isto, uma sonda que
    # deixasse de mandar beta nenhuma daria "mascara perfeita" nas cinco.
    exige(BETA_TASK_BUDGET in por["task_budget"]["betas_no_fio"],
          "a celula task_budget nao poe a beta dela no fio: sonda no-op")
    exige(BETA_FALLBACK in por["fallback"]["betas_no_fio"],
          "a celula fallback nao poe a beta dela no fio: sonda no-op")
    exige({BETA_TASK_BUDGET, BETA_FALLBACK} <= set(por["ambos"]["betas_no_fio"]),
          "a celula ambos nao leva as duas betas no fio")
    exige(not por["mascarado"]["betas_no_fio"],
          f"beta de primeira parte sobreviveu a mascara: "
          f"{por['mascarado']['betas_no_fio']}")

    # Um so' modelo entre as celulas: senao a diferenca medida e' a do prefixo.
    modelos = {l["modelo_no_fio"] for l in res["celulas"]}
    exige(len(modelos) == 1,
          f"as celulas nao usam o mesmo modelo: {modelos}. O diferencial mede o "
          f"prefixo, nao o parametro")
    return falhas


# --- modo online: manda de verdade ------------------------------------------

def online(motor_pedido: str) -> dict:
    os.environ["VEREDITO_MOTOR"] = motor_pedido
    motor.esquece()
    m = motor.ativo()          # forcado: levanta aqui se nao ha' credencial
    cli = motor.cliente()

    linhas = []
    for nome, kw, isola in celulas():
        exc = resp = None
        try:
            resp = cli.beta.messages.create(**kw)
        except BaseException as e:      # noqa: BLE001 -- a excecao E' o dado
            exc = e
        v, detalhe = _classifica(exc, resp)
        uso = getattr(resp, "usage", None)
        linhas.append({
            "celula": nome, "isola": isola, "veredito": v, "detalhe": detalhe,
            "entrada": getattr(uso, "input_tokens", None),
            "saida": getattr(uso, "output_tokens", None),
        })
        print(f"  {nome:<12} {v:<13} {detalhe[:110]}")

    return {"modo": "online", "motor": m.nome, "rotulo": m.rotulo,
            "modelo": motor.modelo(cfg.MODEL_ADVOGADO),
            "celulas": _sela_pelo_controle(linhas)}


def conclui(res: dict) -> list[str]:
    """A leitura do par ambos/mascarado. Sem inventar o que nao foi medido."""
    por = {l["celula"]: l for l in res["celulas"]}
    a, msk = por["ambos"]["veredito"], por["mascarado"]["veredito"]
    tb, fb = por["task_budget"]["veredito"], por["fallback"]["veredito"]

    if "INCONCLUSIVO" in (a, msk):
        return ["INCONCLUSIVO: o par ambos/mascarado nao fechou "
                f"(ambos={a}, mascarado={msk}). SEM_NO_BEDROCK segue NAO MEDIDA."]
    if a == "RECUSADO" and msk == "ACEITO":
        out = ["SEM_NO_BEDROCK CONFIRMADA, e a mascara e' CARGA: sem ela a "
               "chamada do advogado e' recusada; com ela, passa.",
               f"  task_budget sozinho: {tb} | fallbacks sozinho: {fb}"]
        if tb == "ACEITO" or fb == "ACEITO":
            out.append("  !! e a constante esta LARGA DEMAIS: um dos dois passa "
                       "sozinho e esta sendo removido a toa -- ver as celulas.")
        return out
    if a == "ACEITO":
        return ["!! SEM_NO_BEDROCK ERRADA PARA MAIS: os dois passaram juntos. O "
                "produto esta jogando fora `fallbacks` -- a guarda da categoria "
                "carro-chefe -- sem que o Bedrock peca."]
    return [f"!! a mascara NAO cobre o que devia (ambos={a}, mascarado={msk}). "
            "Sobrou parametro recusado na chamada que o advogado manda hoje."]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--offline", action="store_true",
                   help="so' o corpo que iria no fio. Sem rede, sem credencial, sem custo.")
    p.add_argument("--motor", default="bedrock", choices=("bedrock", "aws", "anthropic"))
    a = p.parse_args()

    SAIDA.mkdir(parents=True, exist_ok=True)
    carimbo = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    if a.offline:
        res = offline()
        falhas = confere_offline(res)
        res["sonda_confiavel"] = not falhas
        res["falhas_da_sonda"] = falhas
        for l in res["celulas"]:
            print(f"  {l['celula']:<12} task_budget={str(l.get('tem_task_budget')):<5} "
                  f"fallbacks={str(l.get('tem_fallbacks')):<5} "
                  f"betas={l.get('betas_no_fio')}")
        print()
        if falhas:
            print("SONDA NAO CONFIAVEL -- nao rode online antes de consertar:")
            for f in falhas:
                print(f"  [x] {f}")
        else:
            print("sonda confiavel: as cinco celulas poem no fio o que dizem por.")
    else:
        print(f"medindo SEM_NO_BEDROCK contra o motor {a.motor}\n")
        res = online(a.motor)
        print()
        for linha in conclui(res):
            print(linha)

    destino = SAIDA / f"{carimbo}-{'offline' if a.offline else a.motor}.json"
    destino.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\ngravado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
