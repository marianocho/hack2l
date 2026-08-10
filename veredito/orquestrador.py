"""hack2l / Veredito -- o orquestrador. Promotores -> advogado -> juiz.

Cada etapa grava em disco antes da proxima comecar. Nao e' zelo: ajustar o juiz
pela trigesima vez nao pode re-executar o advogado, e se a rodada morrer no meio
o que ja foi provado continua provado.

    python -m veredito.orquestrador --manual   # uma acusacao escrita a mao
    python -m veredito.orquestrador            # le saidas/acusacoes.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import advogado, config as cfg, juiz, llm_alvo, promotores, tracing

# Acusacao de bancada para o slot 1: exercita o pipeline inteiro sem depender de
# ninguem ter lido o diff. Vem da INVARIANTE do desafio (o seed com carol sem
# nada existe para testar isolamento), nao de um achado -- por isso sobrevive a
# troca de PR, e por isso nao e' resposta chumbada.
ACUSACAO_DE_BANCADA = {
    "id": "bancada_isolamento",
    "categoria": "vazamento_de_contexto",
    "local": "app/api/app/routers/",
    "hipotese": "um usuario consegue alcancar documento que nao e' dele",
    # Arbitro com procedencia, no formato de 10/08: a regra E onde ela esta
    # escrita no repo do desafio. "INV-ISOLAMENTO", que estava aqui antes, era
    # rotulo que nos inventamos -- `grep INV-ISOLAMENTO` no repo deles nao acha
    # nada, e era exatamente esse habito que contaminou os 10 PRs reais.
    "arbitro": {
        "regra": "quem nao e' dono nem destinatario nao pode ler o documento",
        "onde": "docs/REVIEW_TASK.md:43",
    },
    "provado_se": "carol, que nao possui nada, alcanca dado de outro usuario",
    "confianca": "media",
}


def _carrega_acusacoes(manual: bool, reusar: bool, diff: str) -> list[dict]:
    if manual:
        return [ACUSACAO_DE_BANCADA]
    caminho = cfg.SAIDAS / "acusacoes_brutas.json"
    if reusar and caminho.is_file():
        # Afinar o advogado nao pode custar outra rodada de promotores.
        print(f"reusando {caminho.name} (--reusar)")
        try:
            return [a for a in json.loads(caminho.read_text(encoding="utf-8"))
                    if isinstance(a, dict)]
        except (OSError, json.JSONDecodeError) as e:
            print(f"  ilegivel ({e}), rodando os promotores", file=sys.stderr)
    # O contexto do repo entra aqui, em tempo de execucao, e nao chumbado nas
    # lentes. Ausente = os promotores acusam igual e o arbitro sai `null`.
    return promotores.acusa(diff, cfg.contexto_do_repo())


def roda(manual: bool = False, top_n: int | None = None, reusar: bool = False) -> dict:
    cfg.prepara_pastas()
    if not cfg.ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY ausente no .env -- nada roda sem ela.")

    inicio = time.time()

    # Mede o LLM alvo UMA vez e grava. O juiz roda depois, possivelmente em
    # outro processo, e a decisao dele nao pode depender de sondar o app de novo.
    estado, detalhe = llm_alvo.registra()
    print(f"LLM do app alvo: {estado} -- {detalhe[:90]}")

    diff = advogado.diff_do_pr()  # prefixo cacheado; NUNCA imprimir
    print(f"diff do PR carregado: {len(diff)} caracteres (nao exibido de proposito)\n")

    brutas = _carrega_acusacoes(manual, reusar, diff)
    if not brutas:
        return {}
    teto = top_n if top_n is not None else cfg.TOP_N
    # Por COTA de categoria, nao pelas N primeiras -- ver promotores.seleciona.
    acusacoes = brutas if manual else promotores.seleciona(brutas, teto)
    print(f"\n{len(acusacoes)} de {len(brutas)} acusacoes vao ao advogado "
          f"({cfg.MODEL_ADVOGADO})\n")

    # Trace da rodada. Os organizadores dizem, verbatim: "Submitting a trace
    # link is the cleanest way to prove your multi-agent flow actually ran."
    #
    # tracing.rodada NUNCA derruba a rodada -- 4 dos 13 testes do modulo
    # existem so para provar isso (cliente que explode na criacao, span que
    # explode no end). Langfuse fora = no-op silencioso, o parecer sai igual.
    rod_cm = tracing.rodada("veredito", top_n=teto, brutas=len(brutas),
                            ao_advogado=len(acusacoes))
    rod = rod_cm.__enter__()
    if rod.url:
        print(f"trace desta rodada: {rod.url}\n", flush=True)

    veredictos: list[dict] = []
    for i, a in enumerate(acusacoes, 1):
        print(f"[{i}/{len(acusacoes)}] {a.get('id')} -- {a.get('categoria')}", flush=True)
        with rod.etapa(f"advogado/{a.get('id')}",
                       entrada={"categoria": a.get("categoria"),
                                "arbitro": a.get("arbitro"),
                                "local": a.get("local")}) as et:
            v = advogado.julga(a, diff)
            et.evento("veredito", veredito=v.get("veredito"), voltas=v.get("voltas"),
                      severidade=v.get("severidade"), cache_read=v.get("cache_read"))
        veredictos.append(v)

        # Grava a cada acusacao, nao no fim: rodada que morre no meio nao perde
        # o que ja foi provado.
        (cfg.SAIDAS / "veredictos.json").write_text(
            json.dumps(veredictos, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (cfg.SAIDAS / "acusacoes.json").write_text(
            json.dumps(acusacoes, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print(
            f"    -> {v['veredito']} em {v['segundos']}s, {v['voltas']} voltas | "
            f"entrada {v['tokens_entrada']} saida {v['tokens_saida']} "
            f"cache_read {v['cache_read']}"
        )
        if v.get("motivo"):
            print(f"       {v['motivo'][:150]}")
        # Disciplina no 4: conferir o cache na 1a rodada. Zero aqui e' sinal de
        # timestamp, UUID ou ordem de dicionario variando no prefixo.
        if i == 1 and v["cache_read"] == 0:
            print("    ⚠ cache_read zero na 1a acusacao -- algo varia no prefixo",
                  flush=True)

    with rod.etapa("juiz") as et:
        texto = juiz.sentencia()
        et.evento("parecer", caracteres=len(texto))
    rod_cm.__exit__(None, None, None)   # fecha o trace e faz flush
    if rod.url:
        print(f"\ntrace: {rod.url}  (tambem em saidas/trace.txt)")

    total = {
        "acusacoes": len(veredictos),
        "segundos": round(time.time() - inicio, 1),
        "tokens_entrada": sum(v["tokens_entrada"] for v in veredictos),
        "tokens_saida": sum(v["tokens_saida"] for v in veredictos),
        "cache_read": sum(v["cache_read"] for v in veredictos),
    }
    print(f"\n{'=' * 70}\n{texto}\n{'=' * 70}")
    print(
        f"custo da rodada: {total['tokens_entrada']} entrada / "
        f"{total['tokens_saida']} saida / {total['cache_read']} de cache, "
        f"em {total['segundos']}s"
    )
    (cfg.SAIDAS / "custo.json").write_text(
        json.dumps(total, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return total


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manual", action="store_true",
                   help="usa a acusacao de bancada em vez de saidas/acusacoes.json")
    p.add_argument("--top-n", type=int, default=None)
    p.add_argument("--reusar", action="store_true",
                   help="reusa saidas/acusacoes_brutas.json em vez de rodar os promotores")
    args = p.parse_args()
    roda(manual=args.manual, top_n=args.top_n, reusar=args.reusar)
