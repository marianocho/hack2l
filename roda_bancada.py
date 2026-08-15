"""Roda o Veredito contra os quatro PRs da bancada e confronta com o gabarito.

    py -3.12 roda_bancada.py            # os quatro
    py -3.12 roda_bancada.py --top-n 3  # mais barato

⚠️ CUSTA DINHEIRO: ~US$0,30-0,50 por PR. Quatro PRs, ~US$2.

🚨 O `.env` do Veredito precisa NAO ter APP_API_URL nem os bancos, senao ele
sobrepoe o `veredito.yml` da bancada e a rodada revisa o codigo de um projeto
conversando com o app de outro. O orquestrador aborta se isso acontecer, mas
este script ja limpa as chaves do ambiente antes de importar o config.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BANCADA = RAIZ.parent / "bancada"

# Limpo ANTES de importar o config: ele resolve tudo na importacao.
for k in ("APP_API_URL", "APP_WEB_URL", "APP_SAUDE", "BANCO_APP_ORIGEM",
          "BANCO_DESCARTAVEL", "BANCO_APP", "CONTEXTO_REPO"):
    os.environ.pop(k, None)
os.environ["CHALLENGE_REPO"] = str(BANCADA)
# Worktree separado: `git worktree add` dentro de pasta que ja e' worktree de
# OUTRO repo falha.
os.environ["WORKTREES_DIR"] = str(RAIZ.parent / ".worktrees-bancada")
os.environ["BASE_BRANCH"] = "main"

import yaml  # noqa: E402


def gabarito() -> list[dict]:
    d = yaml.safe_load((RAIZ / "bancada_gabarito.yml").read_text(encoding="utf-8"))
    return d["prs"]


def roda(ramo: str, top_n: int) -> dict:
    """Sobe uma rodada NUM PROCESSO SEPARADO.

    O config resolve o projeto na importacao, entao trocar de ramo dentro do
    mesmo processo deixaria metade da configuracao do ramo anterior.
    """
    env = dict(os.environ, PR_BRANCH=ramo)
    r = subprocess.run(
        [sys.executable, "-m", "veredito.orquestrador", "--top-n", str(top_n)],
        cwd=RAIZ, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=2400,
    )
    print(r.stdout[-3000:] if r.returncode else r.stdout[-1500:])
    if r.returncode:
        print(f"  [!] rodada falhou ({r.returncode}): {r.stderr[-500:]}")
        return {}

    # O ponteiro ULTIMA aponta para a pasta que acabou de ser escrita.
    ponteiro = RAIZ / "saidas" / "rodadas" / "ULTIMA"
    pasta = RAIZ / "saidas" / "rodadas" / ponteiro.read_text(encoding="utf-8").strip()
    return {
        "pasta": pasta,
        "veredictos": json.loads((pasta / "veredictos.json").read_text(encoding="utf-8")),
        "brutas": json.loads((pasta / "acusacoes_brutas.json").read_text(encoding="utf-8")),
        "custo": json.loads((pasta / "custo.json").read_text(encoding="utf-8")),
    }


def confronta(pr: dict, saida: dict) -> dict:
    """O que o Veredito disse contra o que o gabarito diz."""
    vs = saida.get("veredictos") or []
    contagem = {}
    for v in vs:
        contagem[v["veredito"]] = contagem.get(v["veredito"], 0) + 1

    esperado = pr["esperado"]
    # PROVADO num PR com defeito: basta UM achado provado no lugar certo.
    # REFUTADO no PR limpo: nenhum condenado.
    if esperado == "REFUTADO":
        bateu = contagem.get("PROVADO", 0) == 0
    else:
        bateu = contagem.get(esperado, 0) > 0

    return {"ramo": pr["ramo"], "esperado": esperado, "contagem": contagem,
            "bateu": bateu, "acusacoes_brutas": len(saida.get("brutas") or []),
            "custo": saida.get("custo", {})}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--top-n", type=int, default=4)
    p.add_argument("--so", default="", help="roda so' este ramo")
    args = p.parse_args()

    prs = [x for x in gabarito() if not args.so or x["ramo"] == args.so]
    linhas = []
    for pr in prs:
        print(f"\n{'=' * 70}\n{pr['ramo']}  (espera {pr['esperado']})\n{'=' * 70}")
        linhas.append(confronta(pr, roda(pr["ramo"], args.top_n)))

    print(f"\n{'=' * 70}\nCONFRONTO COM O GABARITO\n{'=' * 70}")
    print(f"{'ramo':28} {'esperado':14} {'veio':34} {'?'}")
    for l in linhas:
        veio = ", ".join(f"{k}:{v}" for k, v in sorted(l["contagem"].items())) or "(nada)"
        print(f"{l['ramo']:28} {l['esperado']:14} {veio:34} "
              f"{'ok' if l['bateu'] else 'NAO'}")

    entrada = sum(l["custo"].get("tokens_entrada", 0) for l in linhas)
    saida_t = sum(l["custo"].get("tokens_saida", 0) for l in linhas)
    print(f"\ntokens: {entrada} entrada / {saida_t} saida")

    acertos = sum(1 for l in linhas if l["bateu"])
    print(f"\n{acertos} de {len(linhas)} bateram com o gabarito")
    print("\n[!] Isto mede se o INSTRUMENTO funciona, nao se o produto acha "
          "defeito. Com n=4 o segundo nao se conclui.")
    return 0 if acertos == len(linhas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
