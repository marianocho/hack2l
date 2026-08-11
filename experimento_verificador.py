"""O verificador funciona em repositório que a gente NÃO preparou?

É o risco técnico nº 1 do produto, sob qualquer posicionamento -- bot de PR ou
camada de verificação. E hoje a resposta é desconhecida:

  generaliza.py          rodou só os PROMOTORES (a parte que acusa)
  controle_negativo.py   rodou o advogado em UM PR, de documentação

Este script fecha o buraco usando dado que já está no disco: as 144 acusações
que os promotores produziram em 10 PRs reais e que ninguém nunca verificou.

## Metade A (este arquivo)

Amostra estratificada por (repo, categoria) e manda ao advogado, com as duas
ferramentas que existem num repo de terceiro: `read_file` e `grep`.

⚠️ A estratificação é o ponto. `controle_negativo.py --limite N` pega as N
PRIMEIRAS acusações, e elas vêm ordenadas por promotor -- então um limite de 8
seria 8 acusações de `correcao` e nada mais. A pergunta é sobre o verificador em
geral, não sobre uma lente.

## O que este experimento NÃO mede

Sem docker do app e sem suíte isolada, não há `prova_diferencial` nem
`http_request`. Então:

  - a Regra 0 do juiz não tem artefato contra o que conferir
  - `prova_ponta_a_ponta` fica falsa e a R2 trava tudo em MÉDIA

É limitação do experimento, não do produto. E não atrapalha a pergunta: para
dizer "isto aqui não tem caminho de código", ler o repositório basta. Se ele
PROVAR algo sem conseguir executar nada, é justamente o sinal que procuramos.

🚨 INCONCLUSIVO NÃO É REFUTADO. Somar os dois e comemorar "matou o ruído" é
absolvição falsa -- o erro exato que o produto existe para impedir, cometido no
próprio medidor.

## Uso

    py -3.12 experimento_verificador.py            # a amostra planejada, ~38
    py -3.12 experimento_verificador.py --resumo   # relê o que já rodou
    py -3.12 experimento_verificador.py --plano    # só mostra a amostra e sai

Custo medido: ~US$0,06 por acusação. A amostra inteira custa ~US$2,30.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")
sys.path.insert(0, str(RAIZ))

from veredito import advogado, config as cfg, ferramentas   # noqa: E402
from generaliza import _stem, baixa_diff                    # noqa: E402
from controle_negativo import aponta_config_para            # noqa: E402

SAIDA = cfg.SAIDAS / "experimento_verificador"

# A amostra, escrita aqui para ser reproduzível em vez de improvisada.
#
# Ordem deliberada: repositórios PEQUENOS primeiro, next.js por último. O clone
# raso do next.js é o único que pode demorar ou estourar a rede (a preparação
# do hackathon perdeu conexão 3x), e resultado parcial dos quatro primeiros já
# responde a pergunta. Perder os quatro por causa do quinto seria burrice.
PLANO = [
    ("https://github.com/gin-gonic/gin/pull/4709", 8),        # Go
    ("https://github.com/pallets/flask/pull/6095", 8),        # Python, framework
    ("https://github.com/encode/httpx/pull/3730", 6),         # Python, lib
    ("https://github.com/django/django/pull/21735", 8),       # Python, PR de 1 LINHA
    ("https://github.com/vercel/next.js/pull/96932", 8),      # JavaScript, 13 arquivos
]

_PESO = {"alta": 0, "media": 1, "baixa": 2}


def amostra(acusacoes: list[dict], k: int) -> list[dict]:
    """k acusações girando entre as categorias, maior confiança primeiro.

    Round-robin e não "as k primeiras": a lista vem agrupada por promotor, então
    um corte simples entrega uma lente só e a medição responderia outra pergunta.
    """
    por_cat: dict[str, list[dict]] = defaultdict(list)
    for a in acusacoes:
        por_cat[a.get("categoria", "?")].append(a)
    for cat in por_cat:
        por_cat[cat].sort(key=lambda a: _PESO.get(a.get("confianca"), 3))

    escolhidas: list[dict] = []
    cats = sorted(por_cat, key=lambda c: -len(por_cat[c]))
    while len(escolhidas) < k and any(por_cat.values()):
        for c in cats:
            if por_cat[c] and len(escolhidas) < k:
                escolhidas.append(por_cat[c].pop(0))
    return escolhidas


def _custo(vs: list[dict]) -> float:
    tin = sum(v.get("tokens_entrada", 0) for v in vs)
    tout = sum(v.get("tokens_saida", 0) for v in vs)
    cache = sum(v.get("cache_read", 0) for v in vs)
    return (tin * 5 + tout * 25 + cache * 0.5) / 1_000_000


def roda_um(url: str, k: int) -> dict | None:
    origem = cfg.SAIDAS / "generaliza" / f"{_stem(url)}.json"
    if not origem.exists():
        print(f"  PULANDO {url}: rode generaliza.py nele primeiro")
        return None
    reg = json.loads(origem.read_text(encoding="utf-8"))
    escolhidas = amostra(reg["acusacoes"], k)

    print(f"\n{'='*74}\n{reg['repo']}#{reg['numero']} — {(reg.get('titulo') or '')[:52]}")
    print(f"  {reg.get('linguagem')} · +{reg['adicoes']}/-{reg['remocoes']} em "
          f"{reg['arquivos']} arquivo(s)")
    print(f"  {len(escolhidas)} de {len(reg['acusacoes'])} acusacoes -> advogado "
          f"({dict(Counter(a.get('categoria') for a in escolhidas))})\n", flush=True)

    try:
        aponta_config_para(url)
        diff, _ = baixa_diff(url)
    except Exception as e:
        print(f"  ERRO preparando o repo: {type(e).__name__}: {e}")
        return None

    completo = ferramentas.TOOLS
    ferramentas.TOOLS = [ferramentas.read_file, ferramentas.grep]
    veredictos: list[dict] = []
    t0 = time.time()
    try:
        for i, a in enumerate(escolhidas, 1):
            print(f"[{i}/{len(escolhidas)}] {a.get('id')} — {a.get('categoria')} "
                  f"(conf {a.get('confianca')})", flush=True)
            try:
                v = advogado.julga(a, diff)
            except Exception as e:
                # Nunca derrubar a rodada inteira por uma acusacao. E' o terceiro
                # estado aplicado ao proprio experimento.
                v = {"veredito": "INCONCLUSIVO", "segundos": 0, "voltas": 0,
                     "motivo": f"o experimento falhou: {type(e).__name__}: {e}"}
            veredictos.append({
                **v,
                "id": a.get("id"), "categoria": a.get("categoria"),
                "confianca": a.get("confianca"), "hipotese": a.get("hipotese"),
                "local": a.get("local"), "arbitro": a.get("arbitro"),
            })
            print(f"    -> {v['veredito']} em {v.get('segundos')}s, "
                  f"{v.get('voltas')} voltas", flush=True)
            if v.get("motivo"):
                print(f"       {str(v['motivo'])[:110]}", flush=True)
            # Grava a cada acusacao: rodada que morre no meio nao perde o que ja
            # foi verificado. Disciplina 2 do CLAUDE.md.
            _grava(url, reg, veredictos, time.time() - t0)
    finally:
        ferramentas.TOOLS = completo

    return _grava(url, reg, veredictos, time.time() - t0)


def _grava(url: str, reg: dict, veredictos: list[dict], segundos: float) -> dict:
    SAIDA.mkdir(parents=True, exist_ok=True)
    d = {
        "pr": url, "repo": reg["repo"], "numero": reg["numero"],
        "linguagem": reg.get("linguagem"), "titulo": reg.get("titulo"),
        "arquivos": reg.get("arquivos"), "adicoes": reg.get("adicoes"),
        "remocoes": reg.get("remocoes"), "total_acusacoes": len(reg["acusacoes"]),
        "segundos": round(segundos, 1), "veredictos": veredictos,
    }
    (SAIDA / f"{_stem(url)}.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


# ------------------------------------------------------------------ relatorio

def relatorio(regs: list[dict]) -> None:
    if not regs:
        print("nada rodado ainda.")
        return
    todos = [v for r in regs for v in r["veredictos"]]
    n = len(todos)

    print("\n" + "=" * 78)
    print("METADE A — o verificador em repositorio que nao preparamos\n")
    print(f"{'repo#pr':26} {'ling':11} {'n':>3} {'REFUT':>6} {'INCON':>6} "
          f"{'SOBREV':>7} {'US$':>6}")
    print("-" * 78)
    for r in regs:
        vs = r["veredictos"]
        c = Counter(v["veredito"] for v in vs)
        sobrev = c.get("PROVADO", 0) + c.get("SUSPEITA", 0)
        print(f"  {(r['repo']+'#'+str(r['numero']))[:24]:24} "
              f"{(r.get('linguagem') or '?')[:10]:10} {len(vs):3} "
              f"{c.get('REFUTADO',0):6} {c.get('INCONCLUSIVO',0):6} {sobrev:7} "
              f"{_custo(vs):6.2f}")

    c = Counter(v["veredito"] for v in todos)
    refut, incon = c.get("REFUTADO", 0), c.get("INCONCLUSIVO", 0)
    sobrev = c.get("PROVADO", 0) + c.get("SUSPEITA", 0)
    print("-" * 78)
    print(f"  {'TOTAL':24} {'':10} {n:3} {refut:6} {incon:6} {sobrev:7} "
          f"{_custo(todos):6.2f}")

    print(f"\n  REFUTADO      {refut:3}/{n}  {refut/n:.0%}")
    print(f"  INCONCLUSIVO  {incon:3}/{n}  {incon/n:.0%}")
    print(f"  SOBREVIVERAM  {sobrev:3}/{n}  {sobrev/n:.0%}")

    print("\n--- por categoria (a lente que o verificador nao consegue julgar) ---")
    por_cat: dict[str, Counter] = defaultdict(Counter)
    for v in todos:
        por_cat[v.get("categoria", "?")][v["veredito"]] += 1
    print(f"{'':26}{'REFUT':>8}{'INCON':>8}{'SOBREV':>8}")
    for cat in sorted(por_cat):
        cc = por_cat[cat]
        print(f"  {cat:24}{cc.get('REFUTADO',0):8}{cc.get('INCONCLUSIVO',0):8}"
              f"{cc.get('PROVADO',0)+cc.get('SUSPEITA',0):8}")

    print("\n--- veredito do experimento ---")
    # A leitura honesta, e ela tem TRES saidas possiveis -- nao duas.
    if incon / n > 0.5:
        print(f"  🚨 {incon/n:.0%} INCONCLUSIVO. A maioria nao valida nada: sem")
        print("  executar, o advogado nao consegue decidir em repo de terceiro.")
        print("  Isso NAO e' 'o ruido morreu' -- e' ausencia de observacao, e")
        print("  significa que o produto depende de rodar o app do cliente.")
    elif refut / n >= 0.5:
        print(f"  O verificador decide sem executar: {refut/n:.0%} refutados com")
        print("  motivo, em repositorios que nunca preparamos, com read_file e")
        print("  grep. E' o resultado que sustenta a camada de verificacao.")
    else:
        print(f"  Resultado ambiguo: {refut/n:.0%} refutado, {incon/n:.0%}")
        print("  inconclusivo. Nem confirma nem mata a tese -- olhar os motivos.")

    if sobrev:
        print(f"\n  {sobrev} sobreviveram a verificacao. Cada um e' candidato a")
        print("  falso positivo chegando no humano -- conferir um a um:")
        for v in [v for v in todos if v["veredito"] in ("PROVADO", "SUSPEITA")][:10]:
            print(f"    [{v['veredito']:8}] {v.get('categoria','?'):22} "
                  f"{str(v.get('hipotese') or '')[:44]}")

    print(f"\n  custo total US$ {_custo(todos):.2f} · "
          f"US$ {_custo(todos)/n:.3f} por acusacao verificada")


def _le_tudo() -> list[dict]:
    if not SAIDA.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(SAIDA.glob("*.json"))]


def main() -> None:
    args = sys.argv[1:]
    if "--resumo" in args:
        relatorio(_le_tudo())
        return
    if "--plano" in args:
        for url, k in PLANO:
            origem = cfg.SAIDAS / "generaliza" / f"{_stem(url)}.json"
            reg = json.loads(origem.read_text(encoding="utf-8"))
            esc = amostra(reg["acusacoes"], k)
            print(f"{reg['repo']}#{reg['numero']:6} {len(esc)} de "
                  f"{len(reg['acusacoes'])}: "
                  f"{dict(Counter(a.get('categoria') for a in esc))}")
        return

    if not cfg.ANTHROPIC_API_KEY:
        raise SystemExit("ANTHROPIC_API_KEY ausente no .env")
    regs = []
    for url, k in PLANO:
        r = roda_um(url, k)
        if r:
            regs.append(r)
            relatorio(regs)   # parcial a cada PR: rodada que morre nao perde a leitura
    relatorio(_le_tudo())


if __name__ == "__main__":
    main()
