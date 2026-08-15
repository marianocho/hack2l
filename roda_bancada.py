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


def _compose(*args: str, timeout: int = 1200) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(BANCADA / "docker-compose.yml"),
         "--project-directory", str(BANCADA), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )


def prepara_o_app(ramo: str) -> None:
    """Poe o app no ar servindo o codigo DESTE ramo.

    🚨 Sem isto o runner reproduz o falso negativo mais caro do produto. O
    Dockerfile faz COPY do codigo, entao trocar de ramo sem rebuild deixa o
    container servindo o ramo ANTERIOR -- o defeito do PR nao existe de fora, e
    o sintoma parece o produto nao achar nada. Custou uma rodada paga em 15/08,
    e o pre-voo agora aborta por isso (`app_serve_o_head`).

    ⚠️ `build` de TODOS os servicos, nao so' da api: `api` e `seed` sao imagens
    separadas do mesmo ./app, e o schema do banco sai do models.py que o SEED
    tiver. Rebuildar so' a api deixa a tabela com o schema do ramo anterior.
    """
    r = subprocess.run(["git", "checkout", "-q", ramo], cwd=BANCADA,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"nao consegui trocar para {ramo}: {r.stderr.strip()}")

    print(f"  preparando o app em {ramo} (build + up + seed)...", flush=True)
    for passo, args in (("build", ("build",)),
                        ("up", ("up", "-d", "--force-recreate", "api")),
                        ("seed", ("run", "--rm", "seed"))):
        r = _compose(*args)
        if r.returncode != 0:
            raise SystemExit(f"`compose {passo}` falhou em {ramo}: "
                             f"{r.stderr.strip()[:300]}")

    # "container subiu" nao e' "app no ar" -- a confusao ja custou um compose up
    # falhando logo depois de eu reportar sucesso.
    import time
    import urllib.request
    for _ in range(45):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8100/health", timeout=3) as u:
                if u.status == 200:
                    return
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit(f"o app nao respondeu /health depois de subir em {ramo}")


def roda(ramo: str, top_n: int) -> dict:
    """Sobe uma rodada NUM PROCESSO SEPARADO.

    O config resolve o projeto na importacao, entao trocar de ramo dentro do
    mesmo processo deixaria metade da configuracao do ramo anterior.
    """
    prepara_o_app(ramo)
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
    def _le(nome, padrao):
        try:
            return json.loads((pasta / nome).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return padrao

    return {
        "pasta": pasta,
        "veredictos": _le("veredictos.json", []),
        "brutas": _le("acusacoes_brutas.json", []),
        "acusacoes": _le("acusacoes.json", []),
        "custo": _le("custo.json", {}),
    }


def confronta(pr: dict, saida: dict) -> dict:
    """O que o Veredito disse contra o que o gabarito diz.

    🚨 "Nao bateu" tem DUAS causas muito diferentes, e a primeira versao deste
    codigo tratava as duas igual:

      - o defeito foi JULGADO e o veredito divergiu   -> sinal sobre o produto
      - o defeito nem chegou ao advogado              -> falha de SELECAO nossa

    Medido em 15/08 no PR do race: oito acusacoes brutas nomearam o defeito e
    nenhuma entrou no TOP_N=3. Relatar aquilo como "o produto errou" seria
    [[metrica que mede a coisa errada]] -- ele nunca chegou a opinar.
    """
    vs = saida.get("veredictos") or []
    contagem = {}
    for v in vs:
        contagem[v["veredito"]] = contagem.get(v["veredito"], 0) + 1

    esperado = pr["esperado"]
    if esperado == "REFUTADO":
        bateu = contagem.get("PROVADO", 0) == 0
    else:
        bateu = contagem.get(esperado, 0) > 0

    # O defeito plantado chegou a ser acusado? E chegou a ser JULGADO?
    import re
    pistas = pr.get("pistas") or []
    brutas = saida.get("brutas") or []
    escolhidas = {a.get("id") for a in (saida.get("acusacoes") or [])}
    acusaram = [a for a in brutas
                if pistas and re.search("|".join(pistas), str(a), re.I)]
    julgaram = [a for a in acusaram if a.get("id") in escolhidas]

    return {"ramo": pr["ramo"], "esperado": esperado, "contagem": contagem,
            "bateu": bateu, "acusacoes_brutas": len(brutas),
            "acusaram_o_alvo": len(acusaram), "julgaram_o_alvo": len(julgaram),
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
        # A distincao que importa quando NAO bate.
        if not l["bateu"] and l.get("acusaram_o_alvo"):
            if not l.get("julgaram_o_alvo"):
                print(f"{'':28} [!] o defeito foi ACUSADO "
                      f"{l['acusaram_o_alvo']}x e NAO entrou no TOP_N -- falha "
                      f"de RANKING, nao do veredito. Suba --top-n.")
            else:
                print(f"{'':28} [!] o defeito foi julgado e o veredito divergiu "
                      f"-- este e' sinal sobre o produto.")

    entrada = sum(l["custo"].get("tokens_entrada", 0) for l in linhas)
    saida_t = sum(l["custo"].get("tokens_saida", 0) for l in linhas)
    print(f"\ntokens: {entrada} entrada / {saida_t} saida")

    # Devolve a bancada ao `main`: deixar o repositorio de alguem num ramo de PR
    # depois de rodar seria estrago nosso, e a proxima leitura sairia errada.
    subprocess.run(["git", "checkout", "-q", "main"], cwd=BANCADA,
                   capture_output=True, text=True)

    acertos = sum(1 for l in linhas if l["bateu"])
    print(f"\n{acertos} de {len(linhas)} bateram com o gabarito")
    print("\n[!] Isto mede se o INSTRUMENTO funciona, nao se o produto acha "
          "defeito. Com n=4 o segundo nao se conclui.")
    return 0 if acertos == len(linhas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
