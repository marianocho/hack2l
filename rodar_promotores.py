"""Roda os 6 promotores contra o diff real e grava saidas/acusacoes.json.

Pluga no orquestrador: a saida e' exatamente o esquema do CONTRATO, e a
funcao roda_promotores() pode ser importada em vez de chamada pela CLI.

## O prefixo e' o diff, e vem PRIMEIRO

As 6 chamadas compartilham o mesmo prefixo (o diff) com cache_control; a
lente de cada promotor vem depois. Assim o diff e' pago uma vez e relido a
~10% nas outras cinco. Se cache_read vier zero na saida, tem algo variando
no prefixo -- ou o diff e' menor que o minimo cacheavel do modelo.

## Nada morre por erro de formato

try/except no parse. Se o modelo devolver prosa, a acusacao entra mesmo
assim com _bruto preenchido, para o juiz saber que existiu.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")
sys.path.insert(0, str(RAIZ))

from veredito import config as cfg          # noqa: E402
from veredito import tracing                # noqa: E402
from veredito.ferramentas import _git, commit_base, commit_head  # noqa: E402

CHAVES = {"id", "categoria", "local", "hipotese", "arbitro", "provado_se", "confianca"}


def pega_diff() -> tuple[str, str, str]:
    """O diff do PR: base calculada em runtime, nunca chumbada."""
    base, head = commit_base(), commit_head()
    r = _git("diff", f"{base}..{head}", cwd=cfg.DESAFIO)
    if r.returncode != 0:
        raise RuntimeError(f"git diff falhou: {r.stderr[:300]}")
    return r.stdout, base, head


def arquivos_do_diff(diff: str) -> list[str]:
    """Caminhos canonicos, lidos dos cabecalhos +++ b/ do proprio diff."""
    return sorted({m.group(1) for m in re.finditer(r"^\+\+\+ b/(.+)$", diff, re.M)})


def normaliza_local(local, canonicos: list[str]) -> str | None:
    """Reescreve `local` para o caminho canonico do diff. Deterministico.

    Medido em 08/08: o mesmo arquivo saiu como 'routers/shares.py' (25x) e
    'app/api/app/routers/shares.py' (23x), e um `local` veio como prosa. O
    read_file do advogado recebe caminho relativo a raiz do repo, entao
    metade das acusacoes daria arquivo-nao-encontrado -- e o juiz nao
    deduplicaria as duas grafias do mesmo lugar.

    Nao inventa caminho: o que nao casar com nenhum arquivo do diff volta
    como veio, para nao mascarar um achado em codigo em volta.
    """
    if not isinstance(local, str) or not local.strip():
        return None
    # separa o caminho da prosa que as vezes vem junto, e da :linha
    m = re.search(r"[\w./\\-]+\.\w+", local)
    if not m:
        return local.strip()
    caminho = m.group(0).replace("\\", "/")
    linha = re.search(rf"{re.escape(caminho)}:(\d+)", local)
    sufixo = f":{linha.group(1)}" if linha else ""

    exatos = [c for c in canonicos if c == caminho]
    if exatos:
        return exatos[0] + sufixo
    # sufixo de caminho: 'routers/shares.py' -> 'app/api/app/routers/shares.py'
    parciais = [c for c in canonicos if c.endswith("/" + caminho)]
    if len(parciais) == 1:
        return parciais[0] + sufixo
    # ultimo recurso: casar so pelo nome do arquivo, se for unico no diff
    nome = caminho.rsplit("/", 1)[-1]
    por_nome = [c for c in canonicos if c.rsplit("/", 1)[-1] == nome]
    if len(por_nome) == 1:
        return por_nome[0] + sufixo
    # Fora do diff: e' codigo em volta, que os promotores tambem leem. Devolve
    # o caminho limpo em vez da prosa -- o read_file consegue tentar um
    # caminho, nao consegue tentar uma frase.
    return caminho + sufixo


def _parse(texto: str) -> tuple[list[dict], str | None]:
    """Devolve (acusacoes, erro). Nunca levanta."""
    t = texto.strip()
    if t.startswith("```"):                       # cerca markdown
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        dados = json.loads(t)
    except Exception:
        m = re.search(r"\[.*\]", t, re.S)          # array embutido em prosa
        if not m:
            return [], "nao achei array JSON na saida"
        try:
            dados = json.loads(m.group(0))
        except Exception as e:
            return [], f"{type(e).__name__}: {e}"
    if not isinstance(dados, list):
        return [], "a saida nao e' um array"
    return [a for a in dados if isinstance(a, dict)], None


def um_promotor(caminho: Path, diff: str, etapa) -> dict:
    cli = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    lente = caminho.read_text(encoding="utf-8")
    t0 = time.time()
    try:
        r = cli.messages.create(
            model=cfg.MODEL_PROMOTOR,
            max_tokens=8000,
            messages=[{"role": "user", "content": [
                # PREFIXO ESTAVEL, identico nas 6 chamadas -> cacheia aqui
                {"type": "text", "text": f"<diff_do_pr>\n{diff}\n</diff_do_pr>",
                 "cache_control": {"type": "ephemeral"}},
                # a lente, especifica de cada promotor, fica FORA do bloco
                {"type": "text", "text": lente},
            ]}],
        )
    except Exception as e:
        return {"promotor": caminho.stem, "acusacoes": [], "erro": f"{type(e).__name__}: {e}",
                "segundos": round(time.time() - t0, 1), "usage": None}

    if r.stop_reason == "refusal" or not r.content:
        return {"promotor": caminho.stem, "acusacoes": [],
                "erro": f"stop_reason={r.stop_reason}",
                "segundos": round(time.time() - t0, 1), "usage": None}

    etapa.geracao(caminho.stem, cfg.MODEL_PROMOTOR, f"<lente {caminho.name}>", r)
    acusacoes, erro = _parse(r.content[0].text)
    if erro:  # fallback: a acusacao nao morre por formato
        acusacoes = [{"id": f"{caminho.stem}_bruto", "categoria": caminho.stem,
                      "local": None, "hipotese": "saida nao parseavel -- ver _bruto",
                      "arbitro": None, "provado_se": None, "confianca": "baixa",
                      "_bruto": r.content[0].text[:4000]}]
    u = r.usage
    return {
        "promotor": caminho.stem, "acusacoes": acusacoes, "erro": erro,
        "segundos": round(time.time() - t0, 1),
        "usage": {"input": u.input_tokens, "output": u.output_tokens,
                  "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
                  "cache_creation": getattr(u, "cache_creation_input_tokens", 0) or 0},
    }


def roda_promotores() -> dict:
    diff, base, head = pega_diff()
    arquivos = sorted(p for p in (RAIZ / "promotores").glob("*.md")
                      if not p.name.startswith("00_"))
    if not arquivos:
        raise RuntimeError("nenhum promotor em promotores/")

    print(f"diff {base[:7]}..{head[:7]}  |  {len(diff)} chars  |  "
          f"{len(arquivos)} promotores em {cfg.MODEL_PROMOTOR}\n")

    with tracing.rodada("promotores", base=base, head=head, n=len(arquivos)) as rod:
        if rod.url:
            print(f"trace: {rod.url}\n")
        with rod.etapa("promotores", entrada=f"diff {base[:7]}..{head[:7]}") as etapa:
            # ⚠️ O PRIMEIRO SOZINHO, o resto em paralelo.
            #
            # Uma entrada de cache so fica legivel depois que a primeira
            # resposta comeca a streamar. Disparando os 6 juntos, nenhum
            # consegue ler o que os outros ainda estao escrevendo: medido em
            # 08/08, 5 escreveram 31.785 tokens a 1,25x e so 1 leu. Pagar a
            # escrita uma vez e deixar os outros lerem a 0,1x e' ~12x mais
            # barato no prefixo -- e o advogado, que rele o diff por acusacao
            # no Opus 5, sente isso multiplicado.
            resultados = [um_promotor(arquivos[0], diff, etapa)]
            if len(arquivos) > 1:
                with cf.ThreadPoolExecutor(max_workers=len(arquivos) - 1) as ex:
                    resultados += list(ex.map(
                        lambda p: um_promotor(p, diff, etapa), arquivos[1:]))

    canonicos = arquivos_do_diff(diff)
    todas, vistos = [], set()
    for res in resultados:
        for a in res["acusacoes"]:
            a.setdefault("categoria", res["promotor"])
            id_ = a.get("id") or f"{res['promotor']}_{len(todas)+1:02d}"
            while id_ in vistos:                    # ids unicos entre promotores
                id_ += "_b"
            a["id"], a["_promotor"] = id_, res["promotor"]
            bruto = a.get("local")
            a["local"] = normaliza_local(bruto, canonicos)
            if bruto and a["local"] != bruto:
                a["_local_bruto"] = bruto           # rastro: o juiz ve o que mudou
            vistos.add(id_)
            todas.append(a)

    cfg.SAIDAS.mkdir(parents=True, exist_ok=True)
    saida = {"commit_base": base, "commit_head": head,
             "modelo": cfg.MODEL_PROMOTOR, "total": len(todas),
             "por_promotor": [{k: v for k, v in r.items() if k != "acusacoes"}
                              for r in resultados],
             "acusacoes": todas}
    (cfg.SAIDAS / "acusacoes.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    return saida


def relatorio(saida: dict) -> None:
    """SO estatistica agregada -- nao imprime hipotese.

    E' o diagnostico que o doc pede em SE OS PROMOTORES DEIXAREM PASSAR:
    contagem por categoria e distribuicao por arquivo. Quem le a hipotese
    e' o advogado.
    """
    print(f"{'promotor':24} {'acus':>5} {'seg':>6} {'in':>7} {'out':>7} {'cache_r':>8}  erro")
    tin = tout = tcr = tcw = 0
    for r in saida["por_promotor"]:
        u = r["usage"] or {}
        tin += u.get("input", 0); tout += u.get("output", 0)
        tcr += u.get("cache_read", 0); tcw += u.get("cache_creation", 0)
        n = sum(1 for a in saida["acusacoes"] if a["_promotor"] == r["promotor"])
        print(f"  {r['promotor']:22} {n:5} {r['segundos']:6} {u.get('input',0):7} "
              f"{u.get('output',0):7} {u.get('cache_read',0):8}  {r['erro'] or ''}")

    print(f"\ntotal: {saida['total']} acusacoes")
    print("\npor categoria:")
    cats: dict[str, int] = {}
    for a in saida["acusacoes"]:
        cats[a.get("categoria", "?")] = cats.get(a.get("categoria", "?"), 0) + 1
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c:26} {n}")

    print("\npor arquivo citado (distribuicao = leu o diff inteiro?):")
    arqs: dict[str, int] = {}
    for a in saida["acusacoes"]:
        arq = (a.get("local") or "sem_local").split(":")[0]
        arqs[arq] = arqs.get(arq, 0) + 1
    for f, n in sorted(arqs.items(), key=lambda x: -x[1]):
        print(f"  {f:46} {n}")

    conf: dict[str, int] = {}
    arb = 0
    for a in saida["acusacoes"]:
        conf[a.get("confianca", "?")] = conf.get(a.get("confianca", "?"), 0) + 1
        if a.get("arbitro"):
            arb += 1
    print(f"\nconfianca: {conf}")
    print(f"com arbitro citado: {arb}/{saida['total']}")

    custo = (tin * 1.00 + tout * 5.00 + tcw * 1.25 + tcr * 0.10) / 1_000_000
    print(f"\ntokens: {tin} in, {tout} out, {tcw} cache_w, {tcr} cache_r")
    print(f"custo desta etapa: ${custo:.4f}")
    if tcr == 0:
        print("\n⚠️  cache_read=0 -- o diff nao cacheou. Ou e' menor que o minimo do")
        print("    modelo (Haiku 4.5: 4096 tokens), ou tem algo variando no prefixo.")


if __name__ == "__main__":
    s = roda_promotores()
    relatorio(s)
    print(f"\ngravado: saidas/acusacoes.json")
