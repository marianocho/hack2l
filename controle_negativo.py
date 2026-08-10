"""O advogado mata o ruído, ou "prova" o nada?

É a pergunta que o teste de 10 PRs deixou aberta. Os promotores geraram 11
acusações num PR que conserta UM LINK de markdown -- duas delas de injection.
Se o advogado refuta as onze, a divisão de trabalho está certa e o problema é
só custo. Se ele prova alguma, o problema é sério.

## O que este script NÃO consegue testar

Num PR arbitrário do GitHub não existe docker do app nem suíte que rode isolada.
Então o advogado roda com **duas ferramentas em vez de cinco**: `read_file` e
`grep` contra um clone raso do repositório, no commit do PR.

Sem `prova_diferencial` e sem `http_request` não há artefato, então:

  - a Regra 0 do juiz não tem contra o que conferir
  - `prova_ponta_a_ponta` fica falsa e a R2 trava tudo em MÉDIA

Isso é limitação do experimento, não do produto -- e não atrapalha a pergunta.
Para dizer "isto aqui é um link de markdown, não tem caminho de código", ler o
repositório basta. Se ele PROVAR algo mesmo sem conseguir executar nada, é
exatamente o sinal que estamos procurando.

## Uso

    py -3.12 controle_negativo.py https://github.com/psf/requests/pull/7576
    py -3.12 controle_negativo.py <url> --limite 5     # corta o custo

Custo: ~US$ 0,30 por acusação (Opus 5). O PR de markdown tem 11.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")
sys.path.insert(0, str(RAIZ))

from veredito import advogado, config as cfg, ferramentas  # noqa: E402
from generaliza import PR_URL, _stem, baixa_diff           # noqa: E402


def aponta_config_para(url: str) -> str:
    """Clona o repo do PR e REDIRECIONA o config para ele.

    A tentativa ingenua era clonar direto em WORKTREES/head. Nao funciona:
    `_garante_worktree` confere o commit do que achou no disco e, se nao bater,
    apaga e tenta `git worktree add` a partir de cfg.DESAFIO -- que continua
    sendo o repo do desafio, onde o SHA do PR de terceiro nao existe.

    A maquinaria ja faz a coisa certa; ela so precisa apontar para o repo certo.
    Entao: clone raso, cfg.DESAFIO nele, e cfg.BRANCH_PR = o SHA, para que
    commit_head() resolva.
    """
    m = PR_URL.search(url)
    dono, repo, num = m.groups()
    sha = requests.get(
        f"https://api.github.com/repos/{dono}/{repo}/pulls/{num}", timeout=30
    ).json()["head"]["sha"]

    clone = RAIZ / ".repos" / f"{dono}_{repo}"
    if not (clone / ".git").is_dir():
        clone.mkdir(parents=True, exist_ok=True)
        print(f"  clonando {dono}/{repo} ...", flush=True)
        for a in (["init", "-q"],
                  ["remote", "add", "origin", f"https://github.com/{dono}/{repo}.git"]):
            subprocess.run(["git", "-C", str(clone), *a], capture_output=True, timeout=120)

    print(f"  buscando {sha[:8]} ...", flush=True)
    r = subprocess.run(["git", "-C", str(clone), "fetch", "-q", "--depth", "1",
                        "origin", sha], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"fetch falhou: {r.stderr[:200]}")

    cfg.DESAFIO = clone
    cfg.BRANCH_PR = sha
    cfg.BRANCH_BASE = sha          # nao usamos base aqui, mas nao pode apontar para o desafio
    cfg.WORKTREES = RAIZ / ".repos" / f"wt_{dono}_{repo}"
    shutil.rmtree(cfg.WORKTREES, ignore_errors=True)
    return sha


def roda(url: str, limite: int | None = None) -> dict:
    reg_promotores = cfg.SAIDAS / "generaliza" / f"{_stem(url)}.json"
    if not reg_promotores.exists():
        raise SystemExit(f"rode generaliza.py neste PR primeiro: {url}")
    reg = json.loads(reg_promotores.read_text(encoding="utf-8"))
    acusacoes = reg["acusacoes"][:limite] if limite else reg["acusacoes"]

    print(f"\n{reg['repo']}#{reg['numero']} — {reg['titulo']}")
    print(f"  +{reg['adicoes']}/-{reg['remocoes']} em {reg['arquivos']} arquivo(s)")
    print(f"  {len(acusacoes)} acusacoes ao advogado ({cfg.MODEL_ADVOGADO})\n")

    aponta_config_para(url)
    diff, _ = baixa_diff(url)

    # SO leitura. prova_diferencial precisa de docker e http_request do app no
    # ar -- nenhum dos dois existe num PR de terceiro.
    completo = ferramentas.TOOLS
    ferramentas.TOOLS = [ferramentas.read_file, ferramentas.grep]
    try:
        veredictos = []
        t0 = time.time()
        for i, a in enumerate(acusacoes, 1):
            print(f"[{i}/{len(acusacoes)}] {a.get('id')} — {a.get('categoria')} "
                  f"(confianca {a.get('confianca')})", flush=True)
            v = advogado.julga(a, diff)
            veredictos.append({**v, "categoria": a.get("categoria"),
                               "confianca": a.get("confianca"),
                               "hipotese": a.get("hipotese")})
            print(f"    -> {v['veredito']} em {v['segundos']}s, {v['voltas']} voltas")
            if v.get("motivo"):
                print(f"       {v['motivo'][:110]}")
    finally:
        ferramentas.TOOLS = completo

    total = round(time.time() - t0, 1)
    destino = cfg.SAIDAS / "generaliza" / f"{_stem(url)}_advogado.json"
    destino.write_text(json.dumps(
        {"pr": url, "segundos": total, "veredictos": veredictos},
        ensure_ascii=False, indent=2), encoding="utf-8")

    relatorio(reg, veredictos, total)
    return {"veredictos": veredictos}


def relatorio(reg: dict, veredictos: list[dict], segundos: float) -> None:
    from collections import Counter
    c = Counter(v["veredito"] for v in veredictos)
    n = len(veredictos)

    print("\n" + "=" * 74)
    print(f"CONTROLE NEGATIVO — {reg['repo']}#{reg['numero']}")
    print(f"  mudanca real: +{reg['adicoes']}/-{reg['remocoes']} em "
          f"{reg['arquivos']} arquivo(s)\n")

    for k in ("REFUTADO", "INCONCLUSIVO", "SUSPEITA", "PROVADO"):
        if c.get(k):
            print(f"  {k:14} {c[k]:3}   {c[k]/n:.0%}")

    tin = sum(v.get("tokens_entrada", 0) for v in veredictos)
    tout = sum(v.get("tokens_saida", 0) for v in veredictos)
    cache = sum(v.get("cache_read", 0) for v in veredictos)
    custo = (tin * 5 + tout * 25 + cache * 0.5) / 1_000_000
    print(f"\n  {segundos}s · US$ {custo:.2f} · {tin} entrada / {tout} saida / {cache} cache")

    print("\n--- veredito do experimento ---")

    # INCONCLUSIVO NAO E' REFUTADO. Confundir os dois e' exatamente o erro que o
    # produto existe para nao cometer -- a primeira versao deste relatorio somava
    # os dois e dizia "refutou tudo" quando na verdade nenhuma ferramenta tinha
    # funcionado. Absolvicao falsa, no proprio medidor.
    refutados = [v for v in veredictos if v["veredito"] == "REFUTADO"]
    inconclusivos = [v for v in veredictos if v["veredito"] == "INCONCLUSIVO"]
    sobreviveram = [v for v in veredictos if v["veredito"] in ("PROVADO", "SUSPEITA")]

    if sobreviveram:
        print(f"  !! {len(sobreviveram)}/{n} sobreviveram num PR sem defeito:")
        for v in sobreviveram:
            print(f"     [{v['veredito']}] {v['categoria']}: {(v.get('hipotese') or '')[:66]}")
        print("\n  Falso positivo passando pela verificacao. E' o problema serio,")
        print("  nao o de custo.")

    if refutados:
        print(f"\n  {len(refutados)}/{n} REFUTADOS -- o advogado foi olhar e disse que nao.")
        print("  Nessa fracao, a divisao promotor/advogado funciona.")

    if inconclusivos:
        frac = len(inconclusivos) / n
        print(f"\n  {len(inconclusivos)}/{n} INCONCLUSIVOS ({frac:.0%}).")
        if frac > 0.5:
            print("  !! Maioria inconclusiva NAO valida nada. Ou as ferramentas")
            print("  falharam, ou o advogado nao consegue decidir sem executar.")
            print("  Confira os motivos acima antes de tirar qualquer conclusao.")
        else:
            print("  Terceiro estado funcionando: nao conseguiu observar, disse isso.")

    if not sobreviveram and refutados and len(refutados) >= n / 2:
        print(f"\n  RESULTADO: o ruido morre na verificacao. Custa US$ {custo:.2f}")
        print("  para concluir que um PR de documentacao nao tem defeito -- entao")
        print("  o problema que resta e' economico, nao de qualidade.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        raise SystemExit
    lim = None
    if "--limite" in args:
        i = args.index("--limite")
        lim = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    roda(args[0], lim)
