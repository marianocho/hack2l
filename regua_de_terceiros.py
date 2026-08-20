"""A regua contra o mundo real: PRs de terceiros, gabarito escrito por terceiros.

O que o produto tem hoje e' medicao em codigo NOSSO (a bancada, 4 de 4 com o
gabarito) e uma revisao avulsa de PR de terceiro. Falta o numero que um
comprador pede primeiro: **como ele se comporta em codigo que nao e' nosso.**

    py -3.12 regua_de_terceiros.py --conferir    # de graca, reconsulta o GitHub
    py -3.12 regua_de_terceiros.py --rodar       # 🚨 GASTA API (~US$13)
    py -3.12 regua_de_terceiros.py --pontuar     # de graca, le o disco

🚨 PONTUA PELO PARECER, NUNCA POR `veredictos.json`.

Em 18/08 os vereditos do advogado batiam com o gabarito e o PARECER dava o
defeito por inexistente -- a R0 derrubava os tres. Quem pontuasse por
`veredictos.json` teria lido "1 de 1, acertou" com o instrumento quebrado.
Por isso `--pontuar` chama `juiz.organiza`, que e' o que APLICA as regras R0-R4;
e' o mesmo caminho do `parecer.md` e do comentario do PR.

🚨 E SEPARA COBERTURA DE RANKING DE VEREDITO.

"Nao achou" tem tres causas com consertos diferentes, e somar as tres num numero
so' esconde qual delas e'. Ver "SE OS PROMOTORES DEIXAREM PASSAR" no CLAUDE.md:

    nenhuma lente acusou naquele arquivo   -> COBERTURA (prompt/contexto)
    acusou e nao chegou ao advogado        -> RANKING   (cota, orcamento, TOP_N)
    chegou e o parecer decidiu             -> VEREDITO  (regras do juiz)

⚠️ O que este arnes NAO pode dizer esta' no cabecalho de `regua/gabarito.yml`:
sem `veredito.yml` nesses repos nao ha prova diferencial nem app de pe, entao
PROVADO por artefato e' inalcancavel e a R2 limita tudo a MEDIA.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

GABARITO = RAIZ / "regua" / "gabarito.yml"
REGISTRO = RAIZ / "regua" / "rodadas.json"     # pr -> carimbo da rodada


def _yaml():
    try:
        import yaml
    except ImportError:
        raise SystemExit("[!] falta pyyaml: py -3.12 -m pip install pyyaml")
    return yaml


def carrega() -> dict:
    return _yaml().safe_load(GABARITO.read_text(encoding="utf-8"))


def _partes(url: str) -> tuple[str, str]:
    """('aio-libs/aiohttp', '12130') a partir da URL do PR."""
    m = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
    if not m:
        raise SystemExit(f"[!] URL de PR que eu nao sei ler: {url}")
    return m.group(1), m.group(2)


def _gh(*args: str) -> tuple[int, str]:
    r = subprocess.run(["gh", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout.strip()


def _referenciam(repo: str, num: str) -> list[str]:
    """Numeros das issues/PRs que referenciaram este PR depois dele.

    Pela TIMELINE, nao por busca textual: `cross-referenced` e' um evento que o
    GitHub registra, entao e' fato. Busca por "#NNNN" nao funciona -- o
    tokenizador descarta o `#` e a consulta casa qualquer coisa.
    """
    rc, saida = _gh("api", f"repos/{repo}/issues/{num}/timeline", "--paginate",
                    "--jq", '.[]|select(.event=="cross-referenced")'
                            '|(.source.issue.number|tostring)')
    if rc != 0:
        return []
    # `dict.fromkeys` em vez de set: a ordem cronologica ajuda quem for olhar.
    return list(dict.fromkeys(v for v in saida.splitlines() if v.strip()))


# --------------------------------------------------------------- CONFERIR

def confere(g: dict, preparar: bool) -> int:
    """Reconsulta o GitHub e (opcional) prova que cada PR resolve. Zero API.

    🚨 O gabarito e' uma alegacao sobre o estado do GitHub em 20/08. Estado de
    terceiro muda: PR revertido, conserto revertido, defeito NOVO descoberto num
    PR do grupo B. Gabarito que envelhece em silencio faz a medicao seguinte
    parecer boa -- e' o `fontes/` do vault com outro nome.
    """
    problemas = 0

    print("=== grupo A: o conserto ainda confirma o defeito? ===")
    for e in g["grupo_a"]:
        repo, num = _partes(e["pr"])
        c_repo, c_num = _partes(e["procedencia"]["conserto"])
        rc, saida = _gh("pr", "view", c_num, "--repo", c_repo,
                        "--json", "state,mergedAt", "--jq", ".state")
        ok = rc == 0 and saida == "MERGED"
        print(f"  {'[ok]' if ok else '[!] '} {repo}#{num}"
              f"  <- conserto {c_repo}#{c_num} {saida or 'SEM RESPOSTA'}")
        if not ok:
            problemas += 1
            print("       o conserto nao esta' mais MERGED: a procedencia caiu.")

    # 🚨 CONTROLE POSITIVO DA PROPRIA CONFERENCIA, antes de usa-la.
    #
    # A conferencia do grupo B abaixo conclui do SILENCIO ("ninguem referenciou
    # este PR"). Silencio de uma consulta quebrada e' identico a silencio de
    # verdade -- e a primeira versao disto usava busca textual por "#NNNN", que
    # o tokenizador do GitHub ignora: ela devolvia 27 mencoes para TODO PR do
    # celery. Guarda que alarma sempre morre igual a guarda que nunca alarma.
    #
    # Entao: a mesma consulta e' rodada nos PRs do grupo A, onde a resposta
    # certa e' CONHECIDA -- o conserto tem que aparecer. Se nao aparecer, o
    # silencio do grupo B nao vale nada e a conferencia se recusa a concluir.
    print("\n=== a conferencia consegue ENXERGAR? (controle positivo) ===")
    # 🚨 E O CONTROLE PRECISA SABER O QUE ELE NAO ALCANCA, senao ele proprio
    # vira a guarda que alarma sempre. Medido em 20/08: dois dos quatro PRs do
    # grupo A nao tem evento `cross-referenced`, por DUAS causas diferentes --
    # e trata-las igual seria a R3 de 17/08 outra vez.
    #
    #   scrapy#6540   o conserto culpa o COMMIT, nunca o PR -> nao ha o que achar
    #   poetry#9304   o PR esta' LOCKED; a citacao existe no corpo do conserto,
    #                 o evento nao -> a consulta E' cega aqui
    #
    # So' as entradas marcadas `referencia_visivel: true` servem de controle. As
    # outras sao listadas com a causa, para nao virarem alarme recorrente.
    esperados = [e for e in g["grupo_a"]
                 if e["procedencia"].get("referencia_visivel")]
    cega = False
    for e in esperados:
        repo, num = _partes(e["pr"])
        _, c_num = _partes(e["procedencia"]["conserto"])
        vistos = _referenciam(repo, num)
        achou = c_num in vistos
        print(f"  {'[ok]' if achou else '[!] '} {repo}#{num}: o conserto "
              f"#{c_num} {'aparece' if achou else 'NAO APARECE'} nas "
              f"referencias ({len(vistos)} no total)")
        if not achou:
            cega = True
    for e in g["grupo_a"]:
        if not e["procedencia"].get("referencia_visivel"):
            repo, num = _partes(e["pr"])
            print(f"  [i]  {repo}#{num}: fora do controle -- "
                  f"{e['procedencia'].get('porque_invisivel', 'motivo nao registrado')}")
    if not esperados:
        problemas += 1
        print("  [!] nenhuma entrada serve de controle positivo: a conferencia")
        print("      do grupo B passaria a concluir de silencio nao medido.")
    elif cega:
        problemas += 1
        print("  [!] a consulta nao acha nem o que sabemos estar la'. O silencio")
        print("      no grupo B abaixo NAO e' evidencia de nada.")

    print("\n=== grupo B: apareceu referencia NOVA a estes PRs? ===")
    for e in g["grupo_b"]:
        repo, num = _partes(e["pr"])
        # ⚠️ NOVA, nao "alguma". Referencia ja explicada -- tipicamente a issue
        # que o PR conserta -- fica no gabarito com o motivo. Sem isso a linha
        # alarmaria em toda execucao, e o leitor aprenderia a pular exatamente
        # a linha que existe para a referencia que ele PRECISA ver.
        conhecidas = {str(x) for x in e.get("referencias_conhecidas", [])}
        novas = [v for v in _referenciam(repo, num) if v not in conhecidas]
        marca = "[ok]" if not novas else "[?] "
        lista = ", ".join("#" + v for v in novas) if novas else "nenhuma"
        nota = f"   (ja explicada: {e['porque_conhecidas']})" if conhecidas else ""
        print(f"  {marca} {repo}#{num}  referencias novas: {lista}{nota}")
        if novas:
            print("       olhe cada uma antes de contar este como controle "
                  "negativo -- referencia nao e' regressao, mas e' onde ela "
                  "apareceria.")

    if not preparar:
        print("\n(--preparar para provar que cada PR resolve e monta; "
              "continua sem gastar API)")
        return 1 if problemas else 0

    print("\n=== cada PR resolve, clona e monta? (sem gastar API) ===")
    for e in g["grupo_a"] + g["grupo_b"]:
        r = subprocess.run([sys.executable, "revisa_pr.py", e["pr"], "--so-preparar"],
                           cwd=RAIZ, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        if not ok:
            problemas += 1
        print(f"  {'[ok]' if ok else '[!] '} {e['pr']}")
        if not ok:
            for l in (r.stderr or r.stdout).strip().splitlines()[-3:]:
                print(f"       {l}")
    return 1 if problemas else 0


# ------------------------------------------------------------------ RODAR

def roda(g: dict, so: str | None) -> int:
    """🚨 GASTA API. Uma rodada por PR, e o carimbo de cada uma fica gravado."""
    registro = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.is_file() else {}
    alvos = [e for e in g["grupo_a"] + g["grupo_b"] if not so or so in e["pr"]]
    print(f"{len(alvos)} PR(s). Cada um custa da ordem de US$1,40.\n")

    for e in alvos:
        print(f"--- {e['pr']}")
        r = subprocess.run([sys.executable, "revisa_pr.py", e["pr"]], cwd=RAIZ)
        ponteiro = RAIZ / "saidas" / "rodadas" / "ULTIMA"
        carimbo = ponteiro.read_text(encoding="utf-8").strip() if ponteiro.is_file() else ""
        # ⚠️ Gravado mesmo com exit != 0: rodada que morreu no meio e' dado --
        # e' dela que sai a causa do inconclusivo. Perder o carimbo do fracasso
        # e' guardar so' as rodadas que deram certo, que e' viés de sobrevivencia.
        registro[e["pr"]] = {"carimbo": carimbo, "exit": r.returncode}
        REGISTRO.write_text(json.dumps(registro, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"    rodada: {carimbo or '(nenhuma gravada)'}  exit={r.returncode}\n")
    return 0


# ---------------------------------------------------------------- PONTUAR

def _le_rodada(carimbo: str):
    """Aponta o config para UMA rodada e devolve o parecer organizado.

    🚨 `organiza` e' quem aplica R0-R4. E' o mesmo caminho do `parecer.md` e do
    comentario do PR -- e e' por isso que a pontuacao sai daqui, e nao de
    `veredictos.json`, que e' a autodeclaracao do advogado antes das regras.
    """
    from veredito import config as cfg, juiz
    destino = cfg.RODADAS / carimbo
    if not destino.is_dir():
        return None
    # Rebind explicito: e' o que `nova_rodada`/`usa_ultima_rodada` fazem, e todo
    # consumidor le `cfg.RODADA` no momento da chamada.
    cfg.RODADA, cfg.ARTEFATOS = destino, destino / "artefatos"
    veredictos, acusacoes, artefatos, avisos, http, escopo = juiz.carrega_do_disco()
    return juiz.organiza(veredictos, acusacoes, artefatos, avisos, http), acusacoes, escopo


def _arquivo(local: str) -> str:
    return (local or "").split(":", 1)[0].replace("\\", "/").strip()


def _acusou_no_lugar(acusacoes: dict, onde: str) -> bool:
    alvo = onde.replace("\\", "/")
    return any(_arquivo(a.get("local", "")).endswith(alvo.split("/")[-1])
               for a in acusacoes.values())


def pontua(g: dict) -> int:
    if not REGISTRO.is_file():
        raise SystemExit("[!] nenhuma rodada registrada -- rode --rodar antes.")
    registro = json.loads(REGISTRO.read_text(encoding="utf-8"))

    print("=== GRUPO A -- PRs que introduziram defeito confirmado por terceiro ===")
    print("cobertura = alguma lente acusou NO ARQUIVO do defeito")
    print("(o veredito nunca pode ser PROVADO aqui: sem veredito.yml nao ha prova"
          " diferencial)\n")
    for e in g["grupo_a"]:
        _linha_a(e, registro)

    print("\n=== GRUPO B -- rotina, nenhum defeito conhecido ===")
    print("o numero que importa e' a coluna 'condenados': ela deveria ser 0\n")
    adjudicar = []
    for e in g["grupo_b"]:
        adjudicar += _linha_b(e, registro)

    if adjudicar:
        print("\n[!] ADJUDICAR A MAO -- condenacao em PR de rotina.")
        print("Nao conte como falso positivo antes de olhar: pode ser achado de")
        print("verdade em codigo de terceiro, que e' o melhor resultado possivel.")
        print("30 segundos por item, olhando o artefato.\n")
        for pr, local, motivo in adjudicar:
            print(f"  - {pr}\n    {local}: {motivo[:150]}")
    return 0


def _gasto(carimbo: str) -> str:
    """O que a rodada REALMENTE gravou: acusacoes, tempo e tokens.

    🚫 Nao converte para dolar. O `custo.json` guarda tokens, nao preco -- a
    primeira versao disto procurava chaves como `usd`/`total_usd`, que nao
    existem em arquivo nenhum, e devolvia "?" para sempre. Inventar o dolar a
    partir de uma tabela de precos aqui seria numero sem procedencia, e tabela
    de preco envelhece dentro do codigo. Quem quiser o dolar multiplica os
    tokens pelo preco do dia, de fora.
    """
    from veredito import config as cfg
    p = cfg.RODADAS / carimbo / "custo.json"
    if not p.is_file():
        return "sem custo.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return f"custo.json ilegivel ({type(e).__name__})"
    return (f"{d.get('acusacoes', '?')} acus., {d.get('segundos', '?')}s, "
            f"{d.get('tokens_entrada', 0) // 1000}k ent / "
            f"{d.get('tokens_saida', 0) // 1000}k sai, "
            f"cache {d.get('cache_read', 0) // 1000}k")


def _linha_a(e: dict, registro: dict) -> None:
    reg = registro.get(e["pr"])
    if not reg or not reg["carimbo"]:
        print(f"  [!] {e['pr']}  -- sem rodada registrada")
        return
    lido = _le_rodada(reg["carimbo"])
    if lido is None:
        print(f"  [!] {e['pr']}  -- rodada {reg['carimbo']} sumiu do disco")
        return
    org, acusacoes, _ = lido
    cob = _acusou_no_lugar(acusacoes, e["onde"])
    no_lugar = [v for v in org["condenados"]
                if _arquivo(acusacoes.get(v["id"], {}).get("local", ""))
                .endswith(e["onde"].split("/")[-1])]
    print(f"  {e['pr']}")
    print(f"    onde o defeito mora: {e['onde']}"
          f"{'  (conserto pre-corte: SONDA DE CONTAMINACAO)' if not e['procedencia']['pos_corte'] else ''}")
    print(f"    cobertura no arquivo certo: {'SIM' if cob else 'NAO'}"
          f"   |  condenados ali: {len(no_lugar)}")
    print(f"    parecer: {len(org['condenados'])} condenado(s), "
          f"{len(org['descartados'])} descartado(s), "
          f"{len(org['inconclusivos'])} inconclusivo(s)   {_gasto(reg['carimbo'])}")
    if not cob:
        print("    -> falha de COBERTURA: nenhuma lente olhou o arquivo. "
              "Conserto e' contexto/prompt, nao ranking.")
    elif cob and not no_lugar:
        print("    -> acusou no lugar e o parecer nao condenou. Ranking ou "
              "regra do juiz -- olhe qual das duas antes de mexer em prompt.")


def _linha_b(e: dict, registro: dict) -> list[tuple[str, str, str]]:
    reg = registro.get(e["pr"])
    if not reg or not reg["carimbo"]:
        print(f"  [!] {e['pr']}  -- sem rodada registrada")
        return []
    lido = _le_rodada(reg["carimbo"])
    if lido is None:
        print(f"  [!] {e['pr']}  -- rodada {reg['carimbo']} sumiu do disco")
        return []
    org, acusacoes, _ = lido
    n = len(org["condenados"])
    print(f"  {'[ok]' if n == 0 else '[?] '} {e['pr']}")
    print(f"    {n} condenado(s), {len(org['descartados'])} descartado(s), "
          f"{len(org['inconclusivos'])} inconclusivo(s)   {_gasto(reg['carimbo'])}")
    return [(e["pr"], acusacoes.get(v["id"], {}).get("local", "?"),
             v.get("motivo", "-")) for v in org["condenados"]]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--conferir", action="store_true",
                   help="reconsulta o GitHub e valida o gabarito. Zero API")
    p.add_argument("--preparar", action="store_true",
                   help="com --conferir: prova que cada PR clona e monta")
    p.add_argument("--rodar", action="store_true",
                   help="GASTA API (~US$13): uma rodada por PR")
    p.add_argument("--so", help="com --rodar: so' os PRs cuja URL contenha isto")
    p.add_argument("--pontuar", action="store_true",
                   help="le as rodadas do disco e pontua PELO PARECER. Zero API")
    args = p.parse_args()

    g = carrega()
    if args.conferir:
        return confere(g, args.preparar)
    if args.rodar:
        return roda(g, args.so)
    if args.pontuar:
        return pontua(g)
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
