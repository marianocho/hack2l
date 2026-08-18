"""Poe o parecer da ultima rodada como comentario no PR.

    py -3.12 posta_parecer.py https://github.com/dono/repo/pull/123
    py -3.12 posta_parecer.py <url> --postar      # de verdade

🚨 DRY-RUN E' O PADRAO, e nao e' conservadorismo decorativo. Comentar num PR e'
publico e irreversivel na pratica: a notificacao sai para todo mundo que segue
o repositorio no mesmo segundo, e apagar depois nao desfaz o email. Efeito
irreversivel se pergunta ANTES -- e' a mesma regra que deixou
`PERMITIR_REDE_NO_BASE` desligada.

## Atualiza, nunca empilha

O corpo comeca com `<!-- veredito:parecer -->`. Antes de postar, procura um
comentario nosso com essa marca e faz PATCH nele. Sem isso, uma Action que roda
a cada push deixaria doze comentarios num PR de tres dias -- e bot assim e' bot
que o time desliga na primeira semana.

## O token

`GH_TOKEN` ou `GITHUB_TOKEN`, o mesmo caminho do `entrada.py`. Numa Action o
`GITHUB_TOKEN` ja vem no ambiente. Sem token nao da' para comentar em lugar
nenhum, e o erro diz isso em vez de um 404 que se le como "o PR nao existe".
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from veredito import comentario, entrada  # noqa: E402

API = "https://api.github.com"


def _meta_da_rodada() -> dict:
    """O que identifica esta rodada, para o rodape do comentario."""
    import json

    from veredito import config as cfg

    meta = {"rodada": cfg.RODADA.name}
    try:
        custo = json.loads((cfg.RODADA / "custo.json").read_text(encoding="utf-8"))
        meta["segundos"] = custo.get("segundos")
    except (OSError, json.JSONDecodeError):
        pass
    return meta


def acha_o_nosso(dono: str, repo: str, numero: int, cab: dict) -> int | None:
    """O id do comentario que JA e' nosso, ou None.

    Procura pela marca no corpo, e nao pelo autor: numa Action o autor e'
    `github-actions[bot]`, na maquina de alguem e' a conta dessa pessoa, e a
    mesma rodada tem que se reconhecer nos dois casos.
    """
    pagina = 1
    while True:
        r = requests.get(
            f"{API}/repos/{dono}/{repo}/issues/{numero}/comments",
            headers=cab, params={"per_page": 100, "page": pagina}, timeout=30)
        r.raise_for_status()
        lote = r.json()
        for c in lote:
            if comentario.MARCA in (c.get("body") or ""):
                return c["id"]
        if len(lote) < 100:
            return None
        pagina += 1


def posta(url: str, corpo: str, cab: dict) -> str:
    dono, repo, numero = entrada.partes(url)
    existente = acha_o_nosso(dono, repo, numero, cab)
    if existente is not None:
        r = requests.patch(f"{API}/repos/{dono}/{repo}/issues/comments/{existente}",
                           headers=cab, json={"body": corpo}, timeout=30)
        r.raise_for_status()
        return f"atualizado: {r.json()['html_url']}"
    r = requests.post(f"{API}/repos/{dono}/{repo}/issues/{numero}/comments",
                      headers=cab, json={"body": corpo}, timeout=30)
    r.raise_for_status()
    return f"criado: {r.json()['html_url']}"


def main() -> int:
    p = argparse.ArgumentParser(description="Posta o parecer da ultima rodada num PR.")
    p.add_argument("url", help="https://github.com/<dono>/<repo>/pull/<numero>")
    p.add_argument("--postar", action="store_true",
                   help="posta de verdade. Sem isto, so' imprime (padrao)")
    p.add_argument("--saida", default="",
                   help="grava o corpo num arquivo, para conferir antes")
    args = p.parse_args()

    corpo = comentario.do_disco(_meta_da_rodada())

    if args.saida:
        Path(args.saida).write_text(corpo, encoding="utf-8")
        print(f"corpo em {args.saida} ({len(corpo)} caracteres)")

    if not args.postar:
        print(corpo)
        print("\n" + "=" * 70)
        print("DRY-RUN: nada foi postado. Use --postar para comentar de verdade.")
        print(f"{len(corpo)} caracteres (teto do GitHub: {comentario.TETO:,}).")
        return 0

    cab = entrada._cabecalhos()
    if "Authorization" not in cab:
        # Sem isto o GitHub responde 404 para repo publico sem permissao de
        # escrita, e 404 se le como "o PR nao existe" -- manda procurar no lugar
        # errado. E' a mesma mentira do repo privado, documentada no CLAUDE.md.
        print("[!] sem GH_TOKEN/GITHUB_TOKEN no ambiente: nao da' para comentar.",
              file=sys.stderr)
        return 2
    cab = {**cab, "Accept": "application/vnd.github+json"}
    try:
        print(posta(args.url, corpo, cab))
    except requests.HTTPError as e:
        print(f"[!] o GitHub recusou: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
