"""Mesmo repo, mesmas ferramentas, tres fontes: qual rende mais por dolar?

A pergunta que sustenta "o advogado deveria comecar pelos achados do scanner":
achado de scanner realmente rende mais que hipotese de promotor?

[!] Ate aqui a comparacao entre fontes estava CONFUNDIDA -- bandit rodou no
psf/requests (sem defeito) e o revisor de IA no desafio (com defeito), entao o
que parecia diferenca de fonte era diferenca de repositorio. Este script so
compara o que rodou no MESMO repo (o PR do desafio) com as MESMAS duas
ferramentas (read_file, grep).

A metrica e' dolar por veredito DECIDIDO -- provado ou refutado. Inconclusivo e'
gasto sem decisao, e dividir por acusacao esconderia isso.

    py -3.12 comparar_fontes.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from veredito import config as cfg   # noqa: E402

SAIDA = cfg.SAIDAS / "experimento_adaptador"

FONTES = [
    ("promotores",     "veredictos_promotores.json",     "hipotese (Haiku, 6 lentes)"),
    ("revisor de IA",  "veredictos_desafio.json",        "comportamento, em prosa"),
    ("semgrep taint",  "veredictos_semgrep.json",        "fluxo (regra propria)"),
    ("bandit",         "veredictos_bandit-desafio.json", "forma (padrao)"),
]


def _custo(vs: list[dict]) -> float:
    tin = sum(v.get("tokens_entrada", 0) for v in vs)
    tout = sum(v.get("tokens_saida", 0) for v in vs)
    cache = sum(v.get("cache_read", 0) for v in vs)
    return (tin * 5 + tout * 25 + cache * 0.5) / 1_000_000


def main() -> None:
    linhas = []
    for nome, arq, tipo in FONTES:
        p = SAIDA / arq
        if not p.exists():
            print(f"  (ausente: {arq})")
            continue
        v = json.loads(p.read_text(encoding="utf-8"))
        c = Counter(x["veredito"] for x in v)
        decididos = c.get("PROVADO", 0) + c.get("REFUTADO", 0)
        custo = _custo(v)
        seg = sum(x.get("segundos", 0) for x in v)
        linhas.append({
            "nome": nome, "tipo": tipo, "n": len(v),
            "prov": c.get("PROVADO", 0), "ref": c.get("REFUTADO", 0),
            "inc": c.get("INCONCLUSIVO", 0), "dec": decididos,
            "custo": custo, "seg": seg,
            "por_dec": custo / decididos if decididos else None,
            "voltas": sum(x.get("voltas", 0) for x in v) / max(len(v), 1),
        })

    print("\n" + "=" * 84)
    print("MESMO REPO (PR do desafio) · MESMAS FERRAMENTAS (read_file, grep)\n")
    print(f"{'fonte':16}{'tipo de alegacao':28}{'n':>3}{'PROV':>6}{'REF':>5}"
          f"{'INC':>5}{'US$':>7}{'US$/dec':>9}{'voltas':>8}")
    print("-" * 84)
    for l in linhas:
        pd = f"{l['por_dec']:.3f}" if l["por_dec"] is not None else "  --"
        print(f"  {l['nome']:14}{l['tipo']:28}{l['n']:3}{l['prov']:6}{l['ref']:5}"
              f"{l['inc']:5}{l['custo']:7.2f}{pd:>9}{l['voltas']:8.1f}")

    print("\n--- leitura ---")
    scan = [l for l in linhas if l["nome"] in ("semgrep taint", "bandit")]
    prom = [l for l in linhas if l["nome"] == "promotores"]
    if scan and prom:
        cs = sum(l["custo"] for l in scan) / max(sum(l["dec"] for l in scan), 1)
        cp = prom[0]["por_dec"]
        n_scan = sum(l["n"] for l in scan)
        print(f"  scanner:    US$ {cs:.3f} por decidido  (n={n_scan})")
        if cp:
            print(f"  promotores: US$ {cp:.3f} por decidido  (n={prom[0]['n']})")
            print(f"\n  razao: scanner custa {cs/cp:.2f}x o promotor por decisao.")
        print("\n  [!] n do scanner e' minusculo (2-3 achados no app inteiro). Isto")
        print("  e' indicio, nao taxa -- e o TETO do scanner e' o proprio numero:")
        print("  ele nao produz volume suficiente para encher a cota do advogado.")


if __name__ == "__main__":
    main()
