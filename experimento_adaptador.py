"""Achado de OUTRA ferramenta vira alegação testável? (metade B)

A metade A pergunta se o verificador funciona em repositório que não
preparamos. Esta pergunta é outra, e é a que decide o reposicionamento:

  as acusações dos NOSSOS promotores trazem um campo `provado_se` -- "o
  experimento observável que prova isto". Achado de terceiro não tem esse
  campo. Vem como prosa: "Use of assert detected", "possible hardcoded
  password". Alguém tem que transformar prosa em experimento.

**Se achado externo for vago demais para virar teste, o verificador trava em
INCONCLUSIVO** -- e uma pilha de inconclusivos é tão inútil quanto uma pilha de
falsos positivos. É o risco técnico mais afiado da tese de "camada de
verificação", e custa ~US$3 para descobrir.

## A fonte

`bandit` num clone do `psf/requests`: 708 achados numa biblioteca madura e
auditada, em 5 classes. É a fila de triagem real que um time herda ao ligar um
scanner -- a maioria verdadeira-e-irrelevante, algumas assustadoras e falsas.

Não é "outro produto de IA", e a diferença importa: bandit é determinístico e
seus achados são mais bem formatados que prosa de LLM. **Então este experimento
é o caso FÁCIL.** Se a conversão falhar aqui, falha com folga no caso real.

## A medição

O número que importa é o PRIMEIRO passo, não o veredito:

    de N achados externos, quantos viram alegação com experimento observável?

Por isso o adaptador pode responder NAO_TESTAVEL, e isso é resultado, não erro.
Um adaptador que sempre devolve um `provado_se` estaria inventando, e a
medição perderia o sentido -- é a mesma doença do árbitro chumbado, num lugar
novo.

## Uso

    py -3.12 experimento_adaptador.py             # amostra e roda
    py -3.12 experimento_adaptador.py --so-adapta # só a conversão (~US$0,02)
    py -3.12 experimento_adaptador.py --resumo
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import anthropic
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")
sys.path.insert(0, str(RAIZ))

from veredito import advogado, config as cfg, ferramentas   # noqa: E402
from generaliza import baixa_diff                           # noqa: E402
from controle_negativo import aponta_config_para            # noqa: E402

PR_FONTE = "https://github.com/psf/requests/pull/7576"
PR_IA = "https://github.com/pallets/flask/pull/6095"
ALVO = RAIZ / ".repos" / "wt_psf_requests" / "head"
SAIDA = cfg.SAIDAS / "experimento_adaptador"

# 🚨 A primeira rodada mediu a fonte ERRADA, e o numero (10% de conversao)
# quase virou conclusao sobre o produto. Vale registrar o erro:
#
#   bandit reporta PADRAO ("existe um assert aqui", "falta timeout= nesta
#   chamada"). O adaptador exige COMPORTAMENTO observavel. Sao categorias
#   diferentes de alegacao, entao a conversao baixa era consequencia da
#   definicao, nao descoberta -- e 9 dos 10 achados ainda por cima cairam em
#   tests/, onde defeito de producao nao mora.
#
# O que a tese de "camada de verificacao" alega e' sobre alegacao de
# COMPORTAMENTO: revisor de IA, relatorio de bug bounty, achado de scanner
# dinamico. Por isso a fonte virou parametro, e a de IA existe: e' o unico
# stand-in fiel do Greptile/CodeRabbit que da' para rodar aqui.
FONTES = ("bandit", "ia", "desafio", "bandit-desafio", "semgrep", "promotores")

# O app do desafio, para as fontes que rodam scanner nele.
APP_DESAFIO = cfg.DESAFIO / "app" / "api" / "app"
REGRAS_TAINT = RAIZ / "regras_semgrep" / "taint.yml"

SISTEMA_REVISOR_IA = (
    "You are an expert code reviewer. Review the pull request and list the "
    "problems you find. For each problem give the file and line, and explain "
    "what is wrong and why it matters."
)

# Deliberadamente SEM a estrutura do Veredito: sem `provado_se`, sem arbitro,
# sem esquema. Prosa numerada, que e' o que revisor comercial devolve. Se eu
# pedisse o nosso esquema aqui, o experimento se auto-aprovaria.
PROMPT_REVISOR_IA = """\
Review this pull request and list the problems you find.

Number each problem. For each one, give `file:line` and a short paragraph
explaining what is wrong and why it matters. Do not use any other structure.

# The pull request

{diff}
"""

# Quantos de cada classe do bandit. Deliberadamente NAO proporcional: 579 dos
# 708 sao `assert_used`, e amostrar proporcionalmente mediria a conversao de um
# achado so. A fila que um humano triaria de verdade tem variedade.
COTA = {"B105": 1, "B403": 1, "B301": 3, "B113": 3, "B101": 2}

SISTEMA_ADAPTADOR = (
    "Voce converte achados de ferramentas de analise estatica em alegacoes "
    "VERIFICAVEIS. Responda SEMPRE com um unico objeto JSON e nada mais."
)

PROMPT_ADAPTADOR = """\
# O achado, no formato da ferramenta de origem

ferramenta: {ferramenta}
regra: {regra}
severidade: {severidade} | confianca da ferramenta: {confianca_ferramenta}
local: {arquivo}:{linha}
texto: {texto}

trecho de codigo:
```
{codigo}
```

# Seu trabalho

Transformar isto numa alegacao que um VERIFICADOR possa provar ou refutar
executando alguma coisa -- ou dizer que nao da.

O campo que decide e o `provado_se`: um experimento **concreto e observavel**,
que alguem roda e olha o resultado. Nao e' uma reformulacao do achado, nao e'
"revisar o codigo", nao e' "confirmar que o padrao existe".

🚫 O teste mais importante e' este: se o seu `provado_se` so' consegue
confirmar que o TRECHO DE CODIGO e' o que ele e' -- que existe um `assert`,
que falta um `timeout=` -- entao ele nao verifica nada. A ferramenta ja
afirmou isso, e reconfirma-lo por leitura nao adiciona informacao. Nesse caso
responda NAO_TESTAVEL.

Uma alegacao e' testavel quando existe um comportamento OBSERVAVEL que
distingue "o defeito e' real e alcancavel" de "o padrao esta la mas nao tem
consequencia". Ex.: uma entrada que faz o programa pendurar; uma chamada que
retorna dado que nao deveria; um estado que fica corrompido.

Se voce nao consegue formular isso, responda:

  {{"testavel": false, "motivo": "<uma linha: por que nao da para observar>"}}

**Responder NAO_TESTAVEL e' uma resposta legitima e frequentemente a correta.**
Inventar um experimento que nao prova nada e' o unico erro grave aqui.

Se conseguir:

  {{"testavel": true,
    "categoria": "<correcao|injection|vazamento_de_contexto|padroes|performance|prd>",
    "local": "{arquivo}:{linha}",
    "hipotese": "<uma linha: o defeito afirmado, nao a regra da ferramenta>",
    "arbitro": null,
    "provado_se": "<uma linha: o experimento observavel>",
    "confianca": "<alta|media|baixa>"}}

`arbitro` e' null a menos que voce consiga citar uma regra escrita NESTE
repositorio, com arquivo e linha. A regra do bandit NAO conta: ela e' da
ferramenta, nao do repositorio.
"""


def _rel(caminho: str) -> str:
    """Caminho relativo a raiz do repo -- e' o que o advogado sabe resolver."""
    p = Path(caminho).as_posix()
    marca = ALVO.as_posix()
    return p[len(marca):].lstrip("/") if p.startswith(marca) else p


def fonte_bandit(raiz: Path | None = None) -> list[dict]:
    """Scanner estatico: alegacao de PADRAO. O controle do experimento."""
    raiz = raiz or ALVO
    if not raiz.is_dir():
        raise SystemExit(f"caminho ausente: {raiz}")
    r = subprocess.run(
        ["py", "-3.12", "-m", "bandit", "-r", str(raiz), "-f", "json", "-q"],
        capture_output=True, text=True, timeout=600,
    )
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    if not m:
        raise SystemExit(f"bandit nao devolveu JSON: {r.stderr[:300]}")
    todos = json.loads(m.group(0))["results"]
    print(f"  {len(todos)} achados, {dict(Counter(a['test_id'] for a in todos))}")
    por_regra: dict[str, list[dict]] = defaultdict(list)
    for a in todos:
        por_regra[a["test_id"]].append(a)
    fora = []
    for regra, lista in por_regra.items():
        for a in lista[:COTA.get(regra, 3)]:
            fora.append({
                "ferramenta": "bandit (analise estatica de seguranca, Python)",
                "regra": f"{a['test_id']} ({a['test_name']})",
                "texto": a["issue_text"],
                "arquivo": _rel(a["filename"]), "linha": a["line_number"],
                "codigo": (a.get("code") or "")[:600],
                "severidade": a["issue_severity"],
                "confianca_ferramenta": a["issue_confidence"],
            })
    return fora


# Revisor comercial nao promete formato. Aceita "1.", "1)", "## 1.", "**1.**",
# "### Problem 1" -- e se nada casar, o chamador reclama em vez de devolver [].
def fonte_promotores() -> list[dict]:
    """As acusacoes dos NOSSOS promotores no PR do desafio.

    E' a terceira celula da comparacao. Elas ja estao no esquema (tem
    `provado_se` por construcao), entao nao passam pelo adaptador -- a etapa de
    conversao e' no-op e marcada como tal, senao o numero de conversao mentiria
    a favor da casa.

    Amostra estratificada por categoria: as 45 vem agrupadas por promotor, e um
    corte simples mediria uma lente so.
    """
    from experimento_verificador import amostra as _amostra
    # cfg.RODADA = a ultima rodada gravada, resolvida na importacao de config.
    bruto = json.loads(
        (cfg.RODADA / "acusacoes_brutas.json").read_text(encoding="utf-8"))
    esc = _amostra([a for a in bruto if isinstance(a, dict)], 10)
    print(f"  {len(bruto)} acusacoes dos promotores, amostra de {len(esc)}")
    fora = []
    for a in esc:
        fora.append({
            "ferramenta": "promotores do Veredito (Haiku, 6 lentes)",
            "regra": a.get("id", "?"),
            "texto": a.get("hipotese", ""),
            "arquivo": str(a.get("local", "?")).split(":")[0],
            "linha": (str(a.get("local", "")).split(":") + ["?"])[1],
            "codigo": "", "severidade": a.get("confianca", "?"),
            "confianca_ferramenta": a.get("confianca", "?"),
            "_ja_no_esquema": a,
        })
    return fora


def fonte_semgrep() -> list[dict]:
    """Taint: alegacao de FLUXO -- "entrada do cliente chega neste sink".

    E' o outro lado do experimento. bandit diz que a forma do codigo e' X;
    semgrep diz que existe um CAMINHO de A ate B. Caminho e' comportamento, e
    comportamento se testa mandando a entrada e vendo se chega.
    """
    if not REGRAS_TAINT.is_file():
        raise SystemExit(f"regras ausentes: {REGRAS_TAINT}")
    r = subprocess.run(
        ["semgrep", "--config", str(REGRAS_TAINT), "--dataflow-traces",
         "--json", "--quiet", str(APP_DESAFIO)],
        capture_output=True, text=True, timeout=900, errors="replace",
    )
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    if not m:
        raise SystemExit(f"semgrep nao devolveu JSON: {r.stderr[:300]}")
    res = json.loads(m.group(0)).get("results", [])
    print(f"  {len(res)} achados de taint")
    fora = []
    for a in res:
        caminho = a["path"].replace("\\\\", "/")
        fora.append({
            "ferramenta": "semgrep (analise de fluxo / taint, regra propria)",
            "regra": a["check_id"].split(".")[-1],
            "texto": " ".join(str(a["extra"].get("message", "")).split()),
            "arquivo": caminho, "linha": a["start"]["line"],
            "codigo": (a["extra"].get("lines") or "")[:600],
            "severidade": a["extra"].get("severity", "?"),
            "confianca_ferramenta": "fluxo rastreado da fonte ao sink",
        })
    return fora


_ITEM = re.compile(r"^[#*\s]*(?:problem[a]?\s*)?(\d+)[.):]\s*\**\s*(.+)", re.M | re.I)


def diff_do_desafio() -> tuple[str, dict]:
    """O diff do PR do desafio, direto do repo local.

    Por que esta fonte existe: os 10 PRs de terceiro foram escolhidos para medir
    se as LENTES disparam, nao por conterem defeito. Sao PRs de manutencao --
    troca de fixture, renomeacao, conserto de link. Um revisor de IA rodando
    neles produz alegacao sobre nomenclatura e clareza, e alegacao sobre clareza
    nao tem comportamento observavel POR DEFINICAO.

    Medir conversao ali confunde "achado externo nao vira teste" com "este PR
    nao tem o que testar". O PR do desafio tem defeito plantado E gabarito
    conhecido, entao separa as duas coisas.
    """
    base, head = "32a5241", "1dd2e5c"
    r = subprocess.run(
        ["git", "-C", str(cfg.DESAFIO), "diff", f"{base}..{head}"],
        capture_output=True, text=True, timeout=120, errors="replace",
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit(f"git diff falhou no repo do desafio: {r.stderr[:200]}")
    return r.stdout, {"repo": "hack2l/desafio", "numero": 0,
                      "titulo": "Add document sharing"}


def fonte_revisor_ia(pr_url: str, desafio: bool = False) -> list[dict]:
    """Revisor de IA generico: alegacao de COMPORTAMENTO, em prosa.

    E' o stand-in fiel do que Greptile/CodeRabbit devolvem, e e' a fonte que a
    tese do reposicionamento realmente alega verificar. Sem esquema nosso: se
    pedissemos `provado_se` aqui, o experimento se auto-aprovaria.
    """
    diff, info = diff_do_desafio() if desafio else baixa_diff(pr_url)
    print(f"  revisor de IA ({cfg.MODEL_JUIZ}) em {info['repo']}#{info['numero']}"
          f" — {(info.get('titulo') or '')[:40]}", flush=True)
    cliente = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    # 🚨 max_tokens limita RACIOCINIO + RESPOSTA somados, e o raciocinio vem
    # ligado por padrao. Com 8000 este prompt voltou `stop_reason=max_tokens`,
    # UM bloco `thinking` e ZERO texto -- num diff de 3313 chars. A armadilha
    # esta escrita no CLAUDE.md e mesmo assim mordeu; folga e' barata.
    r = cliente.messages.create(
        model=cfg.MODEL_JUIZ, max_tokens=16000, system=SISTEMA_REVISOR_IA,
        # Sem isto o raciocinio come o max_tokens inteiro e a resposta sai
        # VAZIA: medido, 16000 tokens de thinking e zero texto num diff de
        # 3313 chars. Com 'medium' foram 947. Revisor comercial tambem nao
        # gastaria raciocinio maximo por PR.
        output_config={"effort": "medium"},
        messages=[{"role": "user",
                   "content": PROMPT_REVISOR_IA.format(diff=diff)}],
    )
    if getattr(r, "stop_reason", None) == "refusal":
        raise SystemExit("o revisor de IA recusou -- sem fonte, sem experimento.")
    texto = "\n".join(b.text for b in r.content
                      if getattr(b, "type", None) == "text")
    if not texto.strip():
        raise SystemExit(
            f"o revisor devolveu texto vazio (stop_reason={r.stop_reason}, "
            f"blocos={[getattr(b,'type',None) for b in r.content]}). "
            "Sem fonte nao ha experimento -- nao invente achado."
        )
    (SAIDA).mkdir(parents=True, exist_ok=True)
    (SAIDA / "revisor_ia_bruto.md").write_text(texto, encoding="utf-8")

    itens = _ITEM.findall(texto)
    print(f"  o revisor devolveu {len(itens)} problemas em prosa")
    fora = []
    for num, primeira in itens:
        # O corpo do item vai ate o proximo numerado. Recorta pelo indice.
        i = texto.index(primeira)
        resto = texto[i:]
        prox = _ITEM.search(resto[len(primeira):])
        corpo = (primeira + resto[len(primeira):][:prox.start()]) if prox else \
            (primeira + resto[len(primeira):])
        m = re.search(r"([\w./\\-]+\.\w+)[:\s]+(?:line\s*)?(\d+)", corpo)
        fora.append({
            "ferramenta": "revisor de codigo por IA (prosa, sem esquema)",
            "regra": f"problema {num}",
            "texto": " ".join(corpo.split())[:900],
            "arquivo": m.group(1) if m else "?",
            "linha": m.group(2) if m else "?",
            "codigo": "", "severidade": "nao informada",
            "confianca_ferramenta": "nao informada",
        })
    return fora


def adapta(cliente, achado: dict) -> dict:
    prompt = PROMPT_ADAPTADOR.format(**achado)
    try:
        r = cliente.messages.create(
            model=cfg.MODEL_PROMOTOR, max_tokens=1200,
            system=SISTEMA_ADAPTADOR,
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(r, "stop_reason", None) == "refusal":
            return {"testavel": False, "motivo": "recusa do classificador"}
        texto = "\n".join(b.text for b in r.content
                          if getattr(b, "type", None) == "text")
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if not m:
            return {"testavel": False, "motivo": "adaptador nao devolveu JSON"}
        return json.loads(m.group(0))
    except Exception as e:
        return {"testavel": False, "motivo": f"{type(e).__name__}: {e}"}


def roda(fonte: str = "ia", so_adapta: bool = False) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    cliente = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    pr = PR_FONTE if fonte == "bandit" else PR_IA

    print(f"fonte: {fonte}", flush=True)
    if fonte == "bandit":
        escolhidos = fonte_bandit()
    elif fonte == "bandit-desafio":
        escolhidos = fonte_bandit(APP_DESAFIO)
    elif fonte == "semgrep":
        escolhidos = fonte_semgrep()
    elif fonte == "promotores":
        escolhidos = fonte_promotores()
    else:
        escolhidos = fonte_revisor_ia(pr, desafio=(fonte == "desafio"))
    if not escolhidos:
        raise SystemExit("a fonte nao devolveu achado nenhum.")
    print(f"  amostra: {len(escolhidos)}\n")

    print("--- conversao: achado externo -> alegacao testavel ---\n")
    convertidos = []
    for i, ach in enumerate(escolhidos, 1):
        # Promotor ja emite no esquema: converter seria pedir ao modelo que
        # reescrevesse o que ele mesmo escreveu, e inflaria a conversao.
        if ach.get("_ja_no_esquema"):
            res = {"testavel": True, "_passthrough": True, **ach["_ja_no_esquema"]}
        else:
            res = adapta(cliente, ach)
        reg = {
            "origem": {k: ach[k] for k in
                       ("ferramenta", "regra", "texto", "severidade",
                        "confianca_ferramenta")},
            "local_origem": f"{ach['arquivo']}:{ach['linha']}",
            "adaptado": res,
        }
        convertidos.append(reg)
        marca = "TESTAVEL " if res.get("testavel") else "nao-testavel"
        print(f"[{i}/{len(escolhidos)}] {ach['regra'][:12]:12} {marca} "
              f"{reg['local_origem']}")
        print(f"        origem: {ach['texto'][:76]}")
        if res.get("testavel"):
            print(f"        prova.: {str(res.get('provado_se'))[:76]}")
        else:
            print(f"        motivo: {str(res.get('motivo'))[:76]}")
        (SAIDA / f"convertidos_{fonte}.json").write_text(
            json.dumps(convertidos, ensure_ascii=False, indent=2), encoding="utf-8")

    testaveis = [c for c in convertidos if c["adaptado"].get("testavel")]
    n = len(convertidos)
    print(f"\n  CONVERSAO: {len(testaveis)}/{n} = {len(testaveis)/n:.0%} "
          f"viraram alegacao com experimento observavel")
    if so_adapta:
        return

    if not testaveis:
        print("\n  Nenhuma testavel -- nao ha o que mandar ao verificador.")
        print(f"  E' um resultado: achado de '{fonte}' nao vira experimento.")
        return

    print(f"\n--- verificacao: as {len(testaveis)} testaveis ao advogado ---\n")
    # No desafio o cfg JA aponta para o repo certo -- redirecionar mandaria o
    # verificador ler o Flask enquanto julga achado do desafio.
    if fonte in ("desafio", "bandit-desafio", "semgrep", "promotores"):
        diff, _ = diff_do_desafio()
    else:
        aponta_config_para(pr)
        diff, _ = baixa_diff(pr)
    completo = ferramentas.TOOLS
    ferramentas.TOOLS = [ferramentas.read_file, ferramentas.grep]
    veredictos = []
    try:
        for i, c in enumerate(testaveis, 1):
            a = {**c["adaptado"], "id": f"externo_{i:02d}"}
            print(f"[{i}/{len(testaveis)}] {a['id']} — {a.get('categoria')}", flush=True)
            try:
                v = advogado.julga(a, diff)
            except Exception as e:
                v = {"veredito": "INCONCLUSIVO", "segundos": 0, "voltas": 0,
                     "motivo": f"o experimento falhou: {type(e).__name__}: {e}"}
            veredictos.append({**v, "id": a["id"], "origem": c["origem"],
                               "hipotese": a.get("hipotese")})
            print(f"    -> {v['veredito']} em {v.get('segundos')}s")
            if v.get("motivo"):
                print(f"       {str(v['motivo'])[:110]}")
            (SAIDA / f"veredictos_{fonte}.json").write_text(
                json.dumps(veredictos, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        ferramentas.TOOLS = completo
    relatorio(convertidos, veredictos, fonte)


def relatorio(convertidos: list[dict], veredictos: list[dict],
              fonte: str = "?") -> None:
    n, t = len(convertidos), len([c for c in convertidos if c["adaptado"].get("testavel")])
    c = Counter(v["veredito"] for v in veredictos)
    print("\n" + "=" * 74)
    print("METADE B — achado de outra ferramenta vira alegacao testavel?\n")
    print(f"  achados externos amostrados   {n}")
    print(f"  viraram alegacao testavel     {t}  ({t/max(n,1):.0%})  <- o numero que decide")
    print(f"  recusados pelo adaptador      {n-t}")
    if veredictos:
        print(f"\n  dos {len(veredictos)} testaveis que foram ao verificador:")
        for k in ("REFUTADO", "INCONCLUSIVO", "SUSPEITA", "PROVADO"):
            if c.get(k):
                print(f"    {k:14} {c[k]:3}  {c[k]/len(veredictos):.0%}")
    print("\n--- leitura ---")
    if t / max(n, 1) < 0.3:
        print("  A maior parte dos achados externos NAO vira experimento. A camada")
        print("  de verificacao nao se sustenta sobre saida de scanner estatico --")
        print("  ela precisa de fonte que ja alegue COMPORTAMENTO, nao padrao.")
    elif c.get("INCONCLUSIVO", 0) > len(veredictos) / 2:
        print("  Converte, mas nao decide: o verificador nao consegue observar o")
        print("  que o adaptador prometeu. E' o pior dos casos -- gasta dinheiro")
        print("  e devolve 'nao sei'.")
    else:
        print("  Achado externo vira alegacao testavel e o verificador decide.")
        print("  E' o sinal que sustenta o reposicionamento.")


def main() -> None:
    args = sys.argv[1:]
    fonte = "ia"
    for f in FONTES:
        if f"--{f}" in args:
            fonte = f
    if "--resumo" in args:
        conv = json.loads((SAIDA / f"convertidos_{fonte}.json").read_text(encoding="utf-8"))
        vp = SAIDA / f"veredictos_{fonte}.json"
        ver = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else []
        relatorio(conv, ver, fonte)
        return
    roda(fonte=fonte, so_adapta="--so-adapta" in args)


if __name__ == "__main__":
    main()
