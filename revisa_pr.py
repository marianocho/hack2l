"""Revise este PR.

    py -3.12 revisa_pr.py https://github.com/dono/repo/pull/123
    py -3.12 revisa_pr.py <url> --top-n 5

Clona o PR, monta base e head, e sobe o orquestrador apontado para eles. E' a
peca que faltava entre "temos um revisor" e "aponte ele para um PR" -- e e' o
que a Action vai chamar.

🚨 POR QUE EM PROCESSO SEPARADO

O `config` resolve o projeto inteiro NA IMPORTACAO: `PROJETO`, as contas, a rota
de login, o banco, o layout dos testes -- tudo sai de `CHALLENGE_REPO` no
momento em que o modulo carrega. Trocar `cfg.DESAFIO` depois deixaria metade da
configuracao apontando para o projeto anterior, e o sintoma apareceria longe da
causa: uma rodada revisando um repositorio e conversando com o app de outro.

Isso nao e' hipotetico -- e' o item 4 dos cinco chumbados de 15/08, e naquele
dia o pre-voo passou VERDE enquanto acontecia. Entao: ambiente primeiro,
importacao depois. Mesmo desenho do `roda_bancada.py`.

## O que esperar de um PR de terceiro

Sem `veredito.yml` na raiz do repo revisado, o advogado tem `read_file` e `grep`.
Sem app no ar nao ha `http_request`; sem compose declarado nao ha
`prova_diferencial`. O parecer sai com refutacao fundamentada e severidade no
maximo MEDIA -- a R2 rebaixa o que nao e' ponta a ponta.

Com um `veredito.yml` na raiz, o produto ganha as ferramentas todas e a
possibilidade de CRITICA. O arquivo e' do cliente e mora no repositorio dele,
como um Dockerfile; `projeto.caminho()` procura la' antes de qualquer coisa.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from veredito import entrada  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Revisa um PR do GitHub.")
    p.add_argument("url", help="https://github.com/<dono>/<repo>/pull/<numero>")
    p.add_argument("--top-n", type=int, default=None,
                   help="quantas acusacoes vao ao advogado (o caro)")
    p.add_argument("--so-preparar", action="store_true",
                   help="resolve e monta, mas NAO roda -- nao gasta API")
    args = p.parse_args()

    try:
        info = entrada.resolve(args.url)
    except entrada.EntradaFalhou as e:
        print(f"[!] {e}", file=sys.stderr)
        return 2

    print(f"\n{info['repo']}#{info['numero']} — {info['titulo']}")
    print(f"  +{info['adicoes']}/-{info['remocoes']} em {info['arquivos']} arquivo(s)")
    print(f"  base {info['merge_base'][:8]}  ->  head {info['head'][:8]}")
    if info["base_deslocou"]:
        # Ver o cabecalho de entrada.py: o topo do ramo alvo nao serve como base.
        print(f"  [i] o ramo alvo andou desde a abertura do PR; usando o "
              f"merge-base ({info['merge_base'][:8]}), nao o topo "
              f"({info['base_do_ramo'][:8]})")
    print(f"  clone: {info['repo_local']}")

    # 🚨 AMBIENTE PRIMEIRO, IMPORTACAO DEPOIS -- e "ambiente" inclui os
    # WORKTREES, o que este arquivo nao fazia.
    #
    # Ate' 18/08 eles nasciam sob demanda, na primeira ferramenta que
    # precisasse -- ja dentro do laco do advogado. Mas o `veredito.yml` do
    # projeto e' lido do worktree do BASE, e o `config` resolve isso NA
    # IMPORTACAO. No primeiro run da Action contra a bancada, o subprocesso
    # importou o config antes de qualquer worktree existir e imprimiu
    # "projeto: (sem veredito.yml -- usando os padroes)" num repositorio que
    # declara tudo. A rodada revisou a bancada como se fosse muda, e o defeito
    # plantado escapou por falta de ferramenta.
    #
    # ⚠️ O `os.environ` e' atualizado ANTES do import de `ferramentas`, que
    # arrasta o `config`: e' a mesma razao pela qual o orquestrador roda em
    # subprocesso, aplicada aqui dentro.
    os.environ.update(entrada.ambiente(info))
    from veredito import ferramentas  # noqa: E402  (depois do ambiente, sempre)
    try:
        ferramentas.monta_os_dois(info["merge_base"], info["head"])
    except Exception as e:
        print(f"[!] nao consegui montar os worktrees: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 2

    # 🚫 No WORKTREE DO BASE, nunca no clone. O clone e' `git init` + `fetch`:
    # ele nao tem working tree, entao `<clone>/veredito.yml` e' uma condicao que
    # NAO PODE ser verdadeira -- em repositorio nenhum do mundo. Esta linha
    # imprimia "sem veredito.yml" para todo PR, inclusive para projeto que se
    # descreve inteiro, e a mensagem parecia certa porque o primeiro alvo real
    # (pallets/flask) de fato nao tem um.
    #
    # 🚫 Do BASE e nao do head: `preparar` e' lista de argumentos que NOS
    # executamos. Ver o comentario em `config.RAIZ_DO_DESCRITOR`.
    tem_yml = (info["worktrees"] / "base" / "veredito.yml").is_file()
    if tem_yml:
        print("  [i] o projeto tem veredito.yml: ferramentas completas")
    else:
        # Dito ANTES de gastar, nao descoberto no parecer todo em MEDIA.
        print("  [i] sem veredito.yml no repositorio: a rodada vai ter apenas "
              "read_file e grep.\n      Sem prova ponta a ponta, a R2 limita a "
              "severidade a MEDIA.")

    if args.so_preparar:
        print("\n--so-preparar: montado e nao rodado.")
        return 0

    # O ambiente ja foi aplicado acima, antes dos worktrees. O subprocesso o
    # herda inteiro -- e agora importa o config com os worktrees JA EM DISCO,
    # que e' a diferenca entre achar o `veredito.yml` do projeto e nao achar.
    cmd = [sys.executable, "-m", "veredito.orquestrador"]
    if args.top_n is not None:
        cmd += ["--top-n", str(args.top_n)]
    print()
    return subprocess.run(cmd, cwd=RAIZ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
