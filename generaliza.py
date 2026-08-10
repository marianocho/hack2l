"""Os promotores generalizam, ou foram afinados num PR só?

É a metade barata da régua do projeto -- "troca o PR e o agente continua
funcionando". Roda as 6 lentes contra PRs reais do GitHub e mede a forma da
saída. Não precisa de clone, de docker, nem do app rodando: só do diff.

## Por que só os promotores

O passo 1 do PROXIMOS_PASSOS.md confundia duas perguntas de custo muito
diferente:

  A. os promotores generalizam?   -> só precisa do diff. ~$0,05 e 40s por PR.
  B. o advogado prova?            -> precisa do app do cliente rodando. Caro.

A é porteira de B. Se as seis lentes cospem lixo num diff de Django, nada a
jusante importa -- e isso se descobre por cinquenta centavos em vez de um fim
de semana montando docker para dez repositórios.

## O que olhar na saída

  categoria sempre vazia      -> falta contexto naquela lente
  tudo num arquivo só         -> não leu o diff inteiro (foi o que deu no Hack2L:
                                 46 de 47 acusações em shares.py)
  qualquer acusação contaminada -> o conserto de 09/08 regrediu: a lente voltou
                                 a recitar os critérios do desafio num repo que
                                 não é o desafio

⚠️ A taxa de árbitro CAIR em relação aos 45% de 08/08 é o resultado esperado, e
é o certo. Aquele número media contaminação: 94 acusações com árbitro, 94
citando os critérios de aceite da Vindler. O número que vale agora é "árbitro
COM PROCEDÊNCIA" — regra que o promotor consegue localizar naquele repositório.

## Uso

    py -3.12 generaliza.py https://github.com/dono/repo/pull/123
    py -3.12 generaliza.py --lote prs.txt        # um PR por linha
    py -3.12 generaliza.py --resumo              # relê o que já rodou

Grava um JSON por PR em saidas/generaliza/ -- reprocessar não custa API.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")
sys.path.insert(0, str(RAIZ))

from veredito import arbitro as arb     # noqa: E402
from veredito import config as cfg      # noqa: E402
from veredito import promotores         # noqa: E402

SAIDA = cfg.SAIDAS / "generaliza"
PR_URL = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")

# Teto de diff. Acima disso o custo por PR explode e o Haiku perde o fio --
# e PR gigante nao e' o caso de uso: revisor roda em PR que humano revisa.
MAX_CHARS = 60_000


def baixa_diff(url: str) -> tuple[str, dict]:
    """Diff bruto pela API do GitHub. Repo publico nao precisa de auth."""
    m = PR_URL.search(url)
    if not m:
        raise ValueError(f"nao parece URL de PR do GitHub: {url}")
    dono, repo, num = m.groups()
    base = f"https://api.github.com/repos/{dono}/{repo}/pulls/{num}"

    meta = requests.get(base, timeout=30)
    if meta.status_code == 403 and "rate limit" in meta.text.lower():
        raise RuntimeError("rate limit do GitHub (60/h sem auth). Espere ou use GH_TOKEN.")
    meta.raise_for_status()
    m_json = meta.json()

    d = requests.get(base, headers={"Accept": "application/vnd.github.v3.diff"}, timeout=60)
    d.raise_for_status()
    diff = d.text

    info = {
        "url": url, "repo": f"{dono}/{repo}", "numero": int(num),
        "titulo": m_json.get("title"),
        "descricao": (m_json.get("body") or "").strip(),
        "linguagem": (m_json.get("base") or {}).get("repo", {}).get("language"),
        "arquivos": m_json.get("changed_files"),
        "adicoes": m_json.get("additions"), "remocoes": m_json.get("deletions"),
        "chars_diff": len(diff),
    }
    if len(diff) > MAX_CHARS:
        diff = diff[:MAX_CHARS] + "\n\n[... diff truncado ...]"
        info["truncado"] = True
    return diff, info


# Teto da descricao. PR de projeto grande vem com template gigante de
# checklist; o que interessa e' a intencao declarada, que mora no comeco.
MAX_CHARS_DESCRICAO = 6_000


def contexto_do_pr(info: dict) -> str | None:
    """A intencao declarada DESTE PR -- o unico contexto legitimo aqui.

    O repositorio de terceiro nao nos da PRD nem criterios de aceite, e e'
    exatamente por isso que os prompts chumbavam os do Hack2L: a lente de PRD
    nao tinha o que arbitrar, entao recitava o desafio. Sem nada, ela fica muda
    de novo -- e muda nao e' consertada, e' so silenciosa.

    O que existe num PR do GitHub e' titulo e descricao. Nao e' especificacao
    formal, mas e' intencao declarada com procedencia conferivel: um humano abre
    o PR e le. E' menos do que o Hack2L da', e e' honesto sobre ser menos.
    """
    titulo = (info.get("titulo") or "").strip()
    descricao = (info.get("descricao") or "").strip()
    if not titulo and not descricao:
        return None
    if len(descricao) > MAX_CHARS_DESCRICAO:
        descricao = descricao[:MAX_CHARS_DESCRICAO] + "\n\n[... descricao truncada ...]"
    partes = [
        "Este repositorio nao forneceu PRD, criterios de aceite nem guia de",
        "convencoes. O unico material declarado e' o proprio PR, abaixo.",
        "",
        "Para o campo `arbitro`, isto e' procedencia fraca porem conferivel:",
        '`{"regra": "...", "onde": "descricao do PR"}`. Regra que voce NAO',
        "encontrar aqui nem no codigo em volta -> `arbitro` e' `null`.",
        "",
        f"## Titulo do PR\n\n{titulo or '(sem titulo)'}",
    ]
    if descricao:
        partes.append(f"\n## Descricao do PR\n\n{descricao}")
    return "\n".join(partes)


def _stem(url: str) -> str:
    m = PR_URL.search(url)
    return f"{m.group(1)}_{m.group(2)}_{m.group(3)}".replace(".", "_")


def roda_um(url: str, refazer: bool = False) -> dict | None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"{_stem(url)}.json"
    if destino.exists() and not refazer:
        print(f"  (ja rodado, pulando) {url}")
        return json.loads(destino.read_text(encoding="utf-8"))

    try:
        diff, info = baixa_diff(url)
    except Exception as e:
        print(f"  ERRO baixando {url}: {type(e).__name__}: {e}")
        return None

    print(f"\n{info['repo']}#{info['numero']} — {(info['titulo'] or '')[:58]}")
    print(f"  {info['linguagem'] or '?'} · {info['arquivos']} arquivos · "
          f"+{info['adicoes']}/-{info['remocoes']} · {info['chars_diff']} chars"
          + ("  [TRUNCADO]" if info.get("truncado") else ""))

    t0 = time.time()
    try:
        # A funcao dos promotores nao sabe de onde veio o diff -- e' o mesmo
        # codigo que rodou no Hack2L, sem ramo especial para este script. O que
        # muda e' so o contexto: la, o PRD e as convencoes do desafio; aqui, o
        # que o PR de terceiro declara sobre si mesmo, que e' bem menos.
        brutas = promotores.acusa(diff, contexto_do_pr(info))
    except Exception as e:
        print(f"  ERRO nos promotores: {type(e).__name__}: {e}")
        return None

    reg = {**info, "segundos": round(time.time() - t0, 1), "acusacoes": brutas}
    destino.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    return reg


# ------------------------------------------------------------------- relatorio

CATS = ["injection", "vazamento_de_contexto", "prd", "correcao", "padroes", "performance"]


def _por_cat(acusacoes: list[dict]) -> dict[str, int]:
    d = {c: 0 for c in CATS}
    for a in acusacoes:
        c = a.get("categoria", "?")
        d[c] = d.get(c, 0) + 1
    return d


def _concentracao(acusacoes: list[dict]) -> float:
    """Fracao das acusacoes no arquivo mais citado. 1.0 = tudo num arquivo so."""
    if not acusacoes:
        return 0.0
    cont: dict[str, int] = {}
    for a in acusacoes:
        arq = str(a.get("local") or "?").split(":")[0]
        cont[arq] = cont.get(arq, 0) + 1
    return max(cont.values()) / len(acusacoes)


def _contaminadas(acusacoes: list[dict]) -> list[dict]:
    """Acusacoes que citam o vocabulario chumbado do Hack2L, em QUALQUER campo.

    Nao basta olhar o `arbitro`: a hipotese "nenhum requisito R1-R4 pode ser
    validado por esta mudanca" apareceu no `psf/requests` e o advogado a PROVOU
    -- verdade trivial sobre criterios de outro projeto, na lista de condenados.
    Por isso o detector varre hipotese e provado_se tambem.
    """
    fora = []
    for a in acusacoes:
        texto = " ".join(str(a.get(c) or "") for c in ("hipotese", "provado_se"))
        if arb.cita_vocabulario_chumbado(texto) or arb.parece_chumbado(a.get("arbitro")):
            fora.append(a)
    return fora


def relatorio(regs: list[dict]) -> None:
    if not regs:
        print("nada rodado ainda.")
        return

    print("\n" + "=" * 78)
    print("A REGUA: troca o PR, o agente continua funcionando?\n")
    print(f"{'repo#pr':32} {'ling':6} {'acus':>5} {'conc':>6} {'proc':>7} {'seg':>6}")
    print("-" * 78)

    for r in regs:
        a = r["acusacoes"]
        # `proc`, nao `arb`: arbitro PREENCHIDO foi a metrica que nos enganou em
        # 08/08 -- 94 de 94 preenchidos, 94 de 94 reciclando o desafio. O que
        # conta e' arbitro que diz ONDE a regra esta escrita.
        proc = sum(1 for x in a if arb.tem_procedencia(x.get("arbitro")))
        print(f"  {(r['repo'] + '#' + str(r['numero']))[:30]:30} "
              f"{(r.get('linguagem') or '?')[:6]:6} {len(a):5} "
              f"{_concentracao(a):5.0%} {proc:3}/{len(a):<3} {r['segundos']:6}")

    todas = [x for r in regs for x in r["acusacoes"]]
    print("-" * 78)
    print(f"  {'TOTAL':30} {'':6} {len(todas):5}")

    print("\n--- por categoria, PR a PR (categoria sempre vazia = lente cega) ---")
    print(f"{'':32}" + "".join(f"{c[:9]:>11}" for c in CATS))
    zerados = {c: 0 for c in CATS}
    for r in regs:
        pc = _por_cat(r["acusacoes"])
        for c in CATS:
            if pc[c] == 0:
                zerados[c] += 1
        print(f"  {(r['repo'] + '#' + str(r['numero']))[:30]:30}"
              + "".join(f"{pc[c]:>11}" for c in CATS))
    print(f"  {'PRs em que ficou VAZIA':30}"
          + "".join(f"{zerados[c]:>11}" for c in CATS))

    n = len(regs)
    conc = sum(_concentracao(r["acusacoes"]) for r in regs) / n
    citados = sum(1 for x in todas if arb.citado(x.get("arbitro")))
    com_proc = sum(1 for x in todas if arb.tem_procedencia(x.get("arbitro")))
    print("\n--- veredito da regua ---")
    print(f"  PRs testados             {n}")
    print(f"  acusacoes por PR         {len(todas)/n:.1f} (Hack2L: 55)")
    print(f"  concentracao media       {conc:.0%} no arquivo mais citado (Hack2L: 98%)")
    print(f"  arbitro citado           {citados}/{len(todas)} = "
          f"{citados/max(len(todas),1):.0%}")
    print(f"  arbitro COM PROCEDENCIA  {com_proc}/{len(todas)} = "
          f"{com_proc/max(len(todas),1):.0%}  <- o numero que vale")
    cegas = [c for c in CATS if zerados[c] == n]
    print(f"  lentes cegas em TODOS    {cegas or 'nenhuma'}")

    # ------------------------------------------------ o detector de 09/08
    #
    # A medicao que originou o conserto: 94 de 94 arbitros citavam os criterios
    # do desafio da Vindler, em repositorios que nao tem nada a ver com ele.
    # Aqui isso e' uma assercao, nao leitura de 209 acusacoes na madrugada.
    contaminadas = _contaminadas(todas)
    print("\n--- contaminacao (o achado de 08/08 a noite) ---")
    if not contaminadas:
        print(f"  ZERO de {len(todas)} acusacoes citam o vocabulario chumbado do")
        print("  Hack2L (AC1-AC5, R1-R4, C1-C8, INV-*). Era 93 de 94 nos arbitros.")
    else:
        print(f"  🚨 {len(contaminadas)} de {len(todas)} acusacoes ainda citam")
        print("  vocabulario do Hack2L. Se estes PRs sao de terceiros, o conserto")
        print("  de 09/08 regrediu -- ver ACHADO_ARBITRO_CHUMBADO.md.")
        for a in contaminadas[:8]:
            print(f"    {a.get('id','?'):18} {str(a.get('hipotese',''))[:52]}")

    print("\n  Sinal ruim: alguma categoria vazia em todos os PRs, concentracao")
    print("  acima de ~85% em todos, ou QUALQUER acusacao contaminada em repo")
    print("  de terceiro. A taxa de arbitro CAIR e' esperado e correto: os 45%")
    print("  de 08/08 mediam contaminacao, nao cobertura.")


def main() -> None:
    args = sys.argv[1:]
    refazer = "--refazer" in args
    args = [a for a in args if a != "--refazer"]

    if args and args[0] == "--resumo":
        # `controle_negativo.py` grava *_advogado.json na MESMA pasta, com outro
        # formato (veredictos, nao acusacoes). Sem este filtro o --resumo
        # explode em KeyError -- e --resumo e' justamente o caminho de reler
        # sem gastar API, o que nao pode depender de a pasta estar limpa.
        regs = [
            r for r in (json.loads(p.read_text(encoding="utf-8"))
                        for p in sorted(SAIDA.glob("*.json")))
            if isinstance(r, dict) and "acusacoes" in r
        ]
        relatorio(regs)
        return

    if args and args[0] == "--lote":
        urls = [l.strip() for l in Path(args[1]).read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]
    elif args:
        urls = args
    else:
        print(__doc__)
        return

    regs = []
    for u in urls:
        r = roda_um(u, refazer)
        if r:
            regs.append(r)
    relatorio(regs)
    print(f"\ngravado em {SAIDA}/  — use --resumo para reler sem gastar API")


if __name__ == "__main__":
    main()
