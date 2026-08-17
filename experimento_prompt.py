"""A/B de prompt de promotor: a mudanca melhorou, ou a rodada variou?

    # o A/B (custa centavos de Haiku)
    py -3.12 experimento_prompt.py --antes a.md --depois b.md --diff d.txt -n 8

    # so' o desfecho das rodadas ja gravadas (US$0, nao chama API)
    py -3.12 experimento_prompt.py --desfecho padroes

So' os promotores, sem o laco caro do advogado. Mesmo diff, mesmo modelo, N
repeticoes, so' o prompt mudando -- o efeito que sobra e' do prompt.

🚨 POR QUE ELE EXISTE

Em 15/08 mudamos `promotores/padroes.md` e a varredura seguinte da bancada
pareceu confirmar. Nao confirmava: as OUTRAS cinco lentes, que ninguem tocou,
tinham se movido na mesma direcao. Com 2-4 acusacoes por PR, "melhorou" e
"variou" tem exatamente a mesma cara, e a varredura custa ~US$2 para nao
distinguir as duas.

🚨 E POR QUE ELE MOSTRA DESFECHO, E NAO SO' FRASEADO

Em 16/08 eu errei usando este arnes -- ou melhor, usando um numero dele fora de
contexto. Tinha registrado que `performance` emitia 48 de 78 `provado_se` sem
experimento, e parti para consertar. **Li as 46 amostras, e a leitura me deixou
MAIS convencido:** "cresce linear com N" nao diz como conferir, logo parecia
ruim.

O que me corrigiu nao foi ler o texto. Foi cruzar com o DESFECHO:

    padroes / leitura      4 provados em 11  (contra 6 em 6 da execucao)  -> defeito
    performance / descr    5 provados em  7  (0 refutados)                -> nao e'

Ler amostra NAO separa as duas. So' o desfecho separa. Por isso o cruzamento
entra aqui dentro, adjacente ao numero, em vez de morar num script solto que
alguem precisa saber que existe.

⚠️ ELE MEDE FRASEADO. O desfecho vem de rodadas JA gravadas em `saidas/` --
sao fontes diferentes, e o A/B nunca produz veredito, porque veredito exige o
laco caro. Numero melhor aqui e' HIPOTESE de melhora la.

⚠️ E A PORCENTAGEM NAO TEM ALVO EM 100%. Leitura e' a prescricao certa quando a
convencao so' existe no codigo -- camada pulada, nome, import fora de lugar. Em
16/08, das 17 prescricoes de leitura que sobravam, ~12 estavam CERTAS. Empurrar
alem disso e' estragar a lente para melhorar a metrica.

🚫 NAO SERVE PARA CALIBRAR CONTRA O GABARITO. Aqui nao ha gabarito: mede-se o
que a lente emite, contra diffs fixos. A fronteira e' o gabarito nunca entrar.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import glob
import json
import os
import pathlib
import random
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent

# Heuristica de palavra-chave, e ela e' o limite deste instrumento: classifica o
# que o texto PARECE prescrever, nao o que o advogado fara'.
#
# 🚨 E NENHUMA CAIXA E' BOA OU RUIM SOZINHA. Foi o erro de 16/08: `leit` e
# `descr` cairam juntas na minha cabeca como "nao prescreve experimento", e sao
# OPOSTAS no que importa --
#
#   leit   DESVIA para um metodo que absolve falso: o advogado le, nao acha o
#          que violar, e encerra o assunto. Nocivo -- mas so' quando o defeito
#          era observavel de fora. Quando a convencao so' existe no codigo,
#          `leit` e' a prescricao CERTA.
#   descr  deixa o metodo ABERTO, e o advogado escolhe um bom sozinho. O
#          PROVADO do PR limpo em 16/08 veio de uma descricao sem medida
#          nenhuma: ele inventou a carga de 800 linhas e o EXPLAIN.
#
# O que decide e' se a prescricao combina com o defeito, e isso uma regex nao
# sabe. Por isso o desfecho.
EXEC = re.compile(
    r"(?i)\b(chamar|chame|enviar|envie|executa|executar|rodar|rode|requisi|POST|"
    r"GET|PUT|DELETE|curl|teste que|um teste|passa no base|falha no head|inserir|"
    r"criar dois|concorrent|login|autentic)"
)
LEIT = re.compile(
    r"(?i)\b(grep|linha \d|linhas \d|inspecion|ler o|leitura do|o arquivo|no fonte|"
    r"o codigo mostra|o código mostra|busca no c|abrir o)"
)
CAIXAS = ("exec", "leit", "misto", "descr")


def tipo(s: str) -> str:
    e, l = bool(EXEC.search(s)), bool(LEIT.search(s))
    return "exec" if e and not l else "leit" if l and not e else "misto" if e and l else "descr"


# ----------------------------------------------------------------- desfecho

def desfecho_gravado(lente: str | None) -> tuple[dict, int]:
    """Nas rodadas JA gravadas, cada tipo de `provado_se` produziu que veredito?

    Le `saidas/**/acusacoes.json` + `veredictos.json`. Nao chama API, nao custa
    nada, e e' o unico corte que distingue fraseado nocivo de fraseado apenas
    vago -- ver o cabecalho do modulo.
    """
    cruz = collections.defaultdict(collections.Counter)
    pares = 0
    for ac in glob.glob(str(RAIZ / "saidas" / "**" / "acusacoes.json"), recursive=True):
        vd = pathlib.Path(ac).with_name("veredictos.json")
        if not vd.exists():
            continue
        try:
            acs = {a["id"]: a for a in json.loads(pathlib.Path(ac).read_text(encoding="utf-8"))
                   if "id" in a}
            vs = json.loads(vd.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        for v in vs:
            a = acs.get(v.get("id"))
            if not a:
                continue
            if lente and a.get("categoria") != lente:
                continue
            pares += 1
            cruz[tipo(a.get("provado_se") or "")][v.get("veredito", "?")] += 1
    return cruz, pares


def imprime_desfecho(lente: str | None) -> None:
    cruz, pares = desfecho_gravado(lente)
    alvo = f"lente `{lente}`" if lente else "TODAS as lentes"
    print(f"\n=== DESFECHO nas rodadas gravadas -- {alvo} ({pares} acusacoes julgadas) ===")
    if not pares:
        # 🚨 A ausencia tem que ser dita. Sem esta linha, tabela vazia le como
        # "nao houve problema", que e' o mesmo erro do retrato do banco dizendo
        # "limpo" sem ter olhado.
        print("  [!] NENHUMA rodada gravada tem acusacao julgada desta lente.")
        print("      O numero do A/B acima e' sobre FORMA, e nao ha nada aqui")
        print("      que diga o que essa forma causou. Nao decida so' com ele.")
        return
    print(f"  {'tipo':8} {'PROVADO':>8} {'REFUTADO':>9} {'INCONCL':>8} {'n':>5}   {'%provado':>9}")
    for t in CAIXAS:
        c = cruz[t]
        n = sum(c.values())
        if not n:
            continue
        aviso = "   <- n baixo demais para taxa" if n < 10 else ""
        print(f"  {t:8} {c['PROVADO']:8} {c['REFUTADO']:9} {c['INCONCLUSIVO']:8} {n:5}   "
              f"{100*c['PROVADO']/n:8.0f}%{aviso}")
    # [!] e nao emoji: `test_saida_no_console` trava isto, e travou de verdade --
    # `⚠️` em print estoura no console cp1252, que e' o mesmo UnicodeEncodeError
    # que matou o relatorio de uma rodada paga em 15/08.
    print("  [!] `leit` alto NAO e' defeito por si: quando a convencao so' existe no")
    print("      codigo, ler e' a prescricao certa. O sinal e' `leit` com %provado")
    print("      BAIXO ao lado de `exec` com %provado alto -- foi assim no padroes.")


# ----------------------------------------------------------------- amostras

def imprime_amostras(amostra: list[dict], por_caixa: int = 2) -> None:
    """O numero nao viaja sozinho.

    ⚠️ Isto e' a metade FRACA do conserto de 16/08, e esta escrito para nao ser
    confundido com a forte: eu li as 46 amostras de `performance` e a leitura me
    deixou MAIS convencido do erro. Amostra mostra o que a lente escreveu;
    so' o desfecho mostra o que aquilo causou. Leia as duas.
    """
    if not amostra:
        return
    print("\n=== O QUE CADA CAIXA CONTEM (leia antes de confiar na tabela) ===")
    porgrupo = collections.defaultdict(list)
    for x in amostra:
        porgrupo[(x["fase"], x["tipo"])].append(x)
    rnd = random.Random(7)
    for fase in ("ANTES", "DEPOIS"):
        for t in CAIXAS:
            itens = porgrupo.get((fase, t)) or []
            if not itens:
                continue
            for x in rnd.sample(itens, min(por_caixa, len(itens))):
                print(f"  [{fase}/{t}] {(x['provado_se'] or '')[:104]}")
    print("  [!] Se alguma linha de `leit` fala de coisa observavel de FORA (forma")
    print("      de resposta, payload que atravessa), ela esta na caixa errada --")
    print("      e' esse o defeito, nao a porcentagem.")


# ----------------------------------------------------------------- o A/B

def roda_ab(args) -> int:
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        print("ANTHROPIC_API_KEY ausente -- veja o .env", file=sys.stderr)
        return 2
    cli = anthropic.Anthropic(api_key=chave)
    modelo = os.environ.get("MODEL_PROMOTOR", "claude-haiku-4-5-20251001")

    prompts = {"ANTES": args.antes.read_text(encoding="utf-8"),
               "DEPOIS": args.depois.read_text(encoding="utf-8")}
    diffs = {d.stem: d.read_text(encoding="utf-8", errors="replace") for d in args.diff}

    def uma(t):
        fase, nd, i = t
        msg = f"<diff>\n{diffs[nd]}\n</diff>\n\n{prompts[fase]}"
        try:
            r = cli.messages.create(model=modelo, max_tokens=4000,
                                    messages=[{"role": "user", "content": msg}])
            # stop_reason ANTES de content: recusa vem como 200 com content
            # vazio, e `content[0]` viraria IndexError. Ver o CLAUDE.md.
            if r.stop_reason == "refusal" or not r.content:
                return fase, nd, None, r.usage
            txt = r.content[0].text.strip()
            if txt.startswith("```"):
                txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
            return fase, nd, json.loads(txt), r.usage
        except Exception as e:
            print(f"  [!] {fase}/{nd}#{i}: {type(e).__name__}: {e}", flush=True)
            return fase, nd, None, None

    tarefas = [(f, d, i) for f in prompts for d in diffs for i in range(args.n)]
    print(f"{len(tarefas)} chamadas (2 prompts x {len(diffs)} diff(s) x {args.n}), "
          f"modelo {modelo}\n")

    glob_ = collections.defaultdict(collections.Counter)
    por_diff = collections.defaultdict(collections.Counter)
    falhas = collections.Counter()
    lentes = collections.Counter()
    amostra, tin, tout = [], 0, 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for fase, nd, dados, usage in ex.map(uma, tarefas):
            if usage:
                tin += usage.input_tokens
                tout += usage.output_tokens
            if dados is None:
                falhas[fase] += 1
                continue
            for a in dados:
                t = tipo(a.get("provado_se") or "")
                glob_[fase][t] += 1
                por_diff[(fase, nd)][t] += 1
                lentes[a.get("categoria", "?")] += 1
                amostra.append({"fase": fase, "diff": nd, "tipo": t,
                                "hipotese": a.get("hipotese"),
                                "provado_se": a.get("provado_se")})

    def linha(rot, c):
        d = c["exec"] + c["leit"]
        pct = f"{100*c['exec']/d:.0f}%" if d else "-"
        return (f"  {rot:26} {c['exec']:5} {c['leit']:5} {c['misto']:6} "
                f"{c['descr']:6}   {pct:>7}")

    cab = f"  {'':26} {'exec':>5} {'leit':>5} {'misto':>6} {'descr':>6}   {'%exec':>7}"
    print("=== FORMA: o que a lente EMITIU (nao e' desfecho) ===")
    print(cab)
    for fase in ("ANTES", "DEPOIS"):
        print(linha(fase, glob_[fase]))
    print("\n=== POR DIFF (o efeito generaliza, ou vale num caso so'?) ===")
    print(cab)
    for nd in diffs:
        for fase in ("ANTES", "DEPOIS"):
            print(linha(f"{nd[:18]} / {fase}", por_diff[(fase, nd)]))
        print()

    if sum(falhas.values()):
        print(f"falhas: {dict(falhas)}")

    # 🚨 O numero nao sai sozinho. Amostra e desfecho vem juntos, SEMPRE -- nao
    # atras de flag. Em 16/08 o erro foi agir sobre uma contagem que eu mesmo
    # tinha deixado escrita sem contexto, horas antes.
    imprime_amostras(amostra)
    imprime_desfecho(args.lente or (lentes.most_common(1)[0][0] if lentes else None))

    if args.amostra:
        args.amostra.write_text(json.dumps(amostra, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        print(f"\namostra completa: {len(amostra)} acusacoes -> {args.amostra}")
    print(f"tokens: {tin} entrada / {tout} saida")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--desfecho", metavar="LENTE", nargs="?", const="",
                   help="so' o cruzamento das rodadas gravadas; nao chama API. "
                        "Sem valor, cruza todas as lentes.")
    p.add_argument("--antes", type=pathlib.Path)
    p.add_argument("--depois", type=pathlib.Path)
    p.add_argument("--diff", action="append", type=pathlib.Path,
                   help="pode repetir; 2+ diffs mostram se o efeito generaliza")
    p.add_argument("-n", type=int, default=8, help="repeticoes por (prompt, diff)")
    p.add_argument("--lente", help="qual lente cruzar no desfecho (padrao: a mais emitida)")
    p.add_argument("--amostra", type=pathlib.Path, help="grava as acusacoes cruas")
    args = p.parse_args()

    if args.desfecho is not None:
        imprime_desfecho(args.desfecho or None)
        return 0

    if not (args.antes and args.depois and args.diff):
        p.error("o A/B precisa de --antes, --depois e ao menos um --diff "
                "(ou use --desfecho para so' ler o disco)")
    return roda_ab(args)


if __name__ == "__main__":
    raise SystemExit(main())
