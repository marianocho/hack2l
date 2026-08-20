"""Cria a worktree de uma trilha -- COM o `.env`, que e' a parte que morde.

🚨 O CASO, medido em 20/08 na propria worktree da T5.

`TRILHAS_ATE_01SET.md` manda cada trilha trabalhar na worktree dela. Rodei a
suite na minha e vieram **6 vermelhos** que nao existiam em `hack2l/`, com
mensagens que apontavam para o produto:

    RuntimeError: ref nao encontrada no repo do desafio: main

Nao era o produto. Sao DUAS coisas somadas, e nenhuma aparece lendo o codigo:

1. **`.env` esta no `.gitignore`**, entao `git worktree add` nao o leva. A
   worktree nasce sem `ANTHROPIC_API_KEY`, sem `CHALLENGE_REPO`, sem nada -- e o
   `config` cai nos padroes, que apontam para `../hack2l-challenge`, um
   diretorio que nao existe nesta maquina.

2. **`CHALLENGE_REPO=../desafio` e' RELATIVO**, e a worktree mora um nivel mais
   fundo (`Hack2L/.worktrees-trilhas/<trilha>/`). Copiar o `.env` sem tocar nele
   troca um erro por outro: passa a procurar `Hack2L/.worktrees-trilhas/desafio`.

Com o `.env` copiado e o caminho absoluto: **782 verdes, 0 vermelho.**

⚠️ E o modo de falha e' o pior tipo: os 6 vermelhos NAO se anunciam como
"faltou configuracao". Eles se anunciam como defeito do produto, num ramo de
trilha, para quem acabou de comecar naquela area. E' inconclusivo por causa
NOSSA disfarcado de limite do codigo -- a mesma familia do `isolamento_bloqueou`.

🚫 Nao resolvido tirando o `.env` do `.gitignore`: ele tem a chave da API, e
este repositorio e' publico.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

def _raiz_principal() -> Path:
    """A arvore PRINCIPAL do repo, mesmo rodando de dentro de uma worktree.

    🚨 `Path(__file__).parent.parent` da' a worktree em que o script esta, nao o
    repositorio principal -- e foi exatamente assim que a primeira versao disto
    tentou criar `.worktrees-trilhas/.worktrees-trilhas/`. Derivar o fato do git
    em vez de supor o layout: `--git-common-dir` aponta para o `.git`
    COMPARTILHADO, e o pai dele e' a arvore principal.
    """
    aqui = Path(__file__).resolve().parent.parent
    r = subprocess.run(["git", "-C", str(aqui), "rev-parse",
                        "--path-format=absolute", "--git-common-dir"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip()).parent
    return aqui


RAIZ = _raiz_principal()
# Fora dos dois repositorios, de proposito -- mesma razao do `.worktrees` do
# desafio, que o CLAUDE.md de maquina explica.
POUSO = RAIZ.parent / ".worktrees-trilhas"


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd or RAIZ), *args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def env_ajustado(origem: Path) -> str:
    """O `.env` do repo principal, com todo caminho relativo virado absoluto.

    ⚠️ So' mexe em chave que E' caminho. Reescrever o arquivo inteiro por
    heuristica de "parece caminho" acertaria hoje e erraria na primeira chave
    nova -- e o erro seria silencioso.
    """
    de_caminho = ("CHALLENGE_REPO", "WORKTREES_DIR", "CONTEXTO_REPO", "VEREDITO_YML")
    fora = []
    for linha in origem.read_text(encoding="utf-8").splitlines():
        crua = linha.strip()
        if crua and not crua.startswith("#") and "=" in crua:
            chave, _, valor = crua.partition("=")
            chave, valor = chave.strip(), valor.strip()
            if chave in de_caminho and valor and not Path(valor).is_absolute():
                # Resolvido contra o repo PRINCIPAL, que e' onde o valor
                # relativo fazia sentido quando foi escrito.
                linha = f"{chave}={(origem.parent / valor).resolve()}"
        fora.append(linha)
    return "\n".join(fora) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("trilha", help="t1-parecer, t2-aws, t3-bugs, t4-narrativa, t5-vitrine")
    p.add_argument("--de", default="origin/main", help="ponto de partida do ramo")
    args = p.parse_args()

    destino = POUSO / args.trilha
    origem_env = RAIZ / ".env"

    if not origem_env.is_file():
        print(f"[!] {origem_env} nao existe -- e' dele que a worktree herda a "
              "chave da API e o caminho do desafio.", file=sys.stderr)
        return 2

    if destino.exists():
        print(f"[i] {destino} ja existe; so' vou conferir o .env.")
    else:
        existe = git("rev-parse", "--verify", "--quiet", f"refs/heads/{args.trilha}")
        criar = [] if existe.returncode == 0 else ["-b", args.trilha]
        r = git("worktree", "add", str(destino), *criar,
                *( [args.trilha] if criar == [] else [args.de] ))
        if r.returncode:
            print(f"[!] git worktree add falhou:\n{r.stderr}", file=sys.stderr)
            return 2
        print(r.stdout.strip() or f"worktree em {destino}")

    (destino / ".env").write_text(env_ajustado(origem_env), encoding="utf-8")
    print(f"[ok] .env escrito em {destino / '.env'} (caminhos absolutos)")
    print("     Confira antes de gastar tempo:")
    print(f'     py -3.12 -c "from veredito import config as c; '
          f'print(c.DESAFIO.is_dir())"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
