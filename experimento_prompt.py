"""A/B de prompt de promotor: a mudanca melhorou, ou a rodada variou?

    py -3.12 experimento_prompt.py --antes a.md --depois b.md \
        --diff d1.txt --diff d2.txt -n 8

So' os promotores (Haiku), sem o laco caro do advogado. Mesmo diff, mesmo
modelo, mesmas condicoes -- a UNICA variavel e' o texto do prompt. Custa
centavos e responde em um minuto.

🚨 POR QUE ELE EXISTE

Em 15/08 mudamos `promotores/padroes.md` e a varredura seguinte da bancada
pareceu confirmar. Nao confirmava: as OUTRAS cinco lentes, que ninguem tocou,
tinham se movido na mesma direcao. Com 2-4 acusacoes por PR, "melhorou" e
"variou" tem exatamente a mesma cara, e a varredura custa ~US$2 para nao
distinguir as duas.

Este arnes distingue. Mesmo diff, N repeticoes, so' o prompt mudando -- e o
efeito que sobra e' do prompt.

⚠️ ELE MEDE FRASEADO, NAO VEREDITO. A ponte entre os dois (que `provado_se` de
leitura produz refutacao onde execucao produz prova) esta em
`ACHADO_PROVADO_SE_DECIDE_O_VEREDITO.md`, e vale n=6 contra n=11. Um numero
melhor aqui e' hipotese de melhora la, nao prova.

🚫 E NAO E' PARA CALIBRAR CONTRA O GABARITO. Aqui nao ha gabarito nem veredito:
mede-se o que a lente emite, contra diffs fixos. Ajustar o prompt ate' a
bancada dar 100% e' decorar a prova; ajustar o fraseado ate' ele bater com a
observabilidade e' outra coisa. A fronteira entre as duas e' o gabarito nunca
entrar aqui.

⚠️ A porcentagem NAO tem alvo em 100%. Leitura e' a prescricao certa quando a
convencao so' existe no codigo -- camada pulada, nome, import fora de lugar.
Empurrar alem disso faz a lente inventar enquadramento executavel para o que
nao e' observavel, que e' estragar a lente para melhorar a metrica. Leia a
`--amostra` antes de comemorar um numero.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import json
import os
import pathlib
import re
import sys

import anthropic
from dotenv import load_dotenv

RAIZ = pathlib.Path(__file__).resolve().parent

# Heuristica de palavra-chave, e ela e' o limite deste instrumento: classifica o
# que o texto PARECE prescrever, nao o que o advogado fara'. Amostrar a saida
# (`--amostra`) continua sendo parte do metodo, nao luxo.
EXEC = re.compile(
    r"(?i)\b(chamar|chame|enviar|envie|executa|executar|rodar|rode|requisi|POST|"
    r"GET|PUT|DELETE|curl|teste que|um teste|passa no base|falha no head|inserir|"
    r"criar dois|concorrent|login|autentic)"
)
LEIT = re.compile(
    r"(?i)\b(grep|linha \d|linhas \d|inspecion|ler o|leitura do|o arquivo|no fonte|"
    r"o codigo mostra|o código mostra|busca no c|abrir o)"
)


def tipo(s: str) -> str:
    e, l = bool(EXEC.search(s)), bool(LEIT.search(s))
    return "exec" if e and not l else "leit" if l and not e else "misto" if e and l else "descr"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--antes", required=True, type=pathlib.Path)
    p.add_argument("--depois", required=True, type=pathlib.Path)
    p.add_argument("--diff", required=True, action="append", type=pathlib.Path,
                   help="pode repetir; 2+ diffs mostram se o efeito generaliza")
    p.add_argument("-n", type=int, default=8, help="repeticoes por (prompt, diff)")
    p.add_argument("--amostra", type=pathlib.Path,
                   help="grava as acusacoes cruas para leitura humana")
    args = p.parse_args()

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
            # stop_reason ANTES de content: recusa vem como 200 com content vazio,
            # e `content[0]` viraria IndexError. Ver o CLAUDE.md.
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
                amostra.append({"fase": fase, "diff": nd, "tipo": t,
                                "hipotese": a.get("hipotese"),
                                "provado_se": a.get("provado_se")})

    def linha(rot, c):
        d = c["exec"] + c["leit"]
        pct = f"{100*c['exec']/d:.0f}%" if d else "-"
        return (f"  {rot:26} {c['exec']:5} {c['leit']:5} {c['misto']:6} "
                f"{c['descr']:6}   {pct:>7}")

    cab = f"  {'':26} {'exec':>5} {'leit':>5} {'misto':>6} {'descr':>6}   {'%exec':>7}"
    print("=== GLOBAL ===");  print(cab)
    for fase in ("ANTES", "DEPOIS"):
        print(linha(fase, glob_[fase]))
    print("\n=== POR DIFF (o efeito generaliza, ou vale num caso so'?) ===");  print(cab)
    for nd in diffs:
        for fase in ("ANTES", "DEPOIS"):
            print(linha(f"{nd[:18]} / {fase}", por_diff[(fase, nd)]))
        print()

    if sum(falhas.values()):
        print(f"falhas: {dict(falhas)}")
    if args.amostra:
        args.amostra.write_text(json.dumps(amostra, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        print(f"amostra: {len(amostra)} acusacoes -> {args.amostra}")
    print(f"tokens: {tin} entrada / {tout} saida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
