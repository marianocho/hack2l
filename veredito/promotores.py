"""hack2l / Veredito -- os promotores. Acusar e' barato; filtrar e' do advogado.

Seis lentes sobre o mesmo diff, em paralelo, no Haiku. O codigo LE a pasta
`promotores/` -- nao importa nada de la. E' isso que faz a integracao entre as
duas trilhas ser um commit em vez de uma reuniao.

⚠️ O prompt do promotor NAO pede seletividade. "Reporte apenas problemas
relevantes" faz o modelo se autocensurar, e modelo segue filtro de severidade ao
pe da letra. O trabalho dele e' COBERTURA. Quem filtra e' o advogado, que tem
ferramenta -- e essa divisao e' o produto inteiro.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import re
import time
from collections import Counter
from pathlib import Path

import anthropic

from . import config as cfg

SISTEMA = (
    "Voce e' um PROMOTOR do Veredito. Le um pull request sob uma lente especifica "
    "e levanta hipoteses de defeito. Voce NAO julga, NAO filtra e NAO estima "
    "impacto: quem faz isso e' o advogado, que tem ferramenta para testar. Seu "
    "trabalho e' cobertura. Responda SEMPRE com um array JSON e nada mais."
)

# Duas lentes de seguranca de IA caem no mesmo bucket para a cota do juiz --
# e' o degrau 2 da escada de conserto do doc: dividir o promotor em dois.
BUCKET = {
    "injection": "seguranca_ia",
    "vazamento_de_contexto": "seguranca_ia",
}

# Cota da rodada final. Sem ela o TOP_N pega as N primeiras da lista e uma
# categoria barulhenta engole as vagas das outras -- o parecer fica torto sem
# ninguem perceber.
COTAS = {"seguranca_ia": 3, "prd": 2, "correcao": 2, "padroes": 2, "performance": 1}


def _bucket(categoria: str) -> str:
    return BUCKET.get(categoria, categoria)


def lentes() -> list[tuple[str, str]]:
    """(nome, texto) de cada promotor. 00_LEIA-ME e' documentacao, nao lente."""
    pasta = cfg.RAIZ / "promotores"
    return [
        (p.stem, p.read_text(encoding="utf-8"))
        for p in sorted(pasta.glob("*.md"))
        if not p.stem.startswith("00")
    ]


def _parse(texto: str, nome: str) -> tuple[list[dict], str | None]:
    """Devolve (acusacoes, erro). Acusacao nunca morre por erro de formato."""
    m = re.search(r"\[.*\]", texto.strip(), re.DOTALL)
    if not m:
        return [], "nenhum array JSON na saida"
    try:
        dados = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return [], f"JSON invalido: {e}"
    if not isinstance(dados, list):
        return [], "a saida nao e' uma lista"
    out = []
    for i, a in enumerate(dados, 1):
        if not isinstance(a, dict) or not a.get("hipotese"):
            continue
        a.setdefault("categoria", nome)
        a.setdefault("id", f"{nome}_{i:02d}")
        a.setdefault("confianca", "baixa")
        a.setdefault("arbitro", None)
        out.append(a)
    return out, None


def _acusa_um(cliente, nome: str, lente: str, diff: str) -> dict:
    inicio = time.time()
    try:
        r = cliente.messages.create(
            model=cfg.MODEL_PROMOTOR,
            max_tokens=8000,
            system=SISTEMA,
            messages=[{"role": "user", "content": [
                # O diff vem ANTES da lente: prefixo identico nas 6 chamadas, o
                # Haiku cacheia uma vez e as outras cinco leem a ~10%.
                {"type": "text", "text": f"# Diff do PR sob revisao\n\n{diff}",
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": lente},
            ]}],
        )
        # stop_reason antes de content, mesmo no Haiku.
        if getattr(r, "stop_reason", None) == "refusal":
            return {"nome": nome, "acusacoes": [], "erro": "recusa do classificador"}
        texto = "\n".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        acusacoes, erro = _parse(texto, nome)
        return {
            "nome": nome, "acusacoes": acusacoes, "erro": erro,
            "saida_crua": texto if erro else None,
            "tokens_entrada": r.usage.input_tokens,
            "tokens_saida": r.usage.output_tokens,
            "cache_read": getattr(r.usage, "cache_read_input_tokens", 0) or 0,
            "segundos": round(time.time() - inicio, 1),
        }
    except Exception as e:
        return {"nome": nome, "acusacoes": [], "erro": f"{type(e).__name__}: {e}"}


def acusa(diff: str) -> list[dict]:
    """Os 6 promotores em paralelo. Grava a lista BRUTA antes de qualquer corte."""
    cfg.prepara_pastas()
    cliente = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    ls = lentes()
    print(f"{len(ls)} promotores em paralelo, modelo {cfg.MODEL_PROMOTOR}")

    # A primeira SOZINHA, depois as outras cinco. Uma entrada de cache so fica
    # legivel depois que a primeira resposta comeca a chegar: disparando as 6
    # juntas, nenhuma le o que as outras estao escrevendo e todas pagam preco
    # cheio pelo diff. Medido -- 5 das 6 vieram com cache zero.
    resultados = [_acusa_um(cliente, ls[0][0], ls[0][1], diff)]
    if len(ls) > 1:
        with cf.ThreadPoolExecutor(max_workers=len(ls) - 1) as ex:
            resultados += list(ex.map(
                lambda t: _acusa_um(cliente, t[0], t[1], diff), ls[1:]))

    todas: list[dict] = []
    vistos: set[str] = set()
    for r in resultados:
        marca = f"{len(r['acusacoes'])} acusacoes"
        if r.get("erro"):
            marca += f"  ⚠ {r['erro']}"
        print(f"  {r['nome']:24} {marca}  ({r.get('segundos', '?')}s, "
              f"cache {r.get('cache_read', 0)})")
        for a in r["acusacoes"]:
            # ids colidem entre promotores rodando em paralelo; a unica exigencia
            # da fronteira e' que sejam unicos.
            while a["id"] in vistos:
                a["id"] += "b"
            vistos.add(a["id"])
            todas.append(a)

    (cfg.SAIDAS / "acusacoes_brutas.json").write_text(
        json.dumps(todas, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _diagnostico(todas)
    return todas


def _diagnostico(acusacoes: list[dict]) -> None:
    """Os sinais que o doc manda olhar quando os promotores deixam passar.

    Categoria com contagem destoante = falta contexto naquela lente.
    Tudo concentrado em poucos arquivos = nao leu o diff inteiro.
    """
    print(f"\n  {len(acusacoes)} acusacoes brutas -> saidas/acusacoes_brutas.json")
    if not acusacoes:
        return
    por_cat = Counter(a.get("categoria", "?") for a in acusacoes)
    print("  por categoria:", dict(por_cat))
    arquivos = Counter(str(a.get("local", "?")).split(":")[0] for a in acusacoes)
    print(f"  arquivos tocados: {len(arquivos)} | top: {dict(arquivos.most_common(4))}")
    sem_arbitro = sum(1 for a in acusacoes if not a.get("arbitro"))
    print(f"  sem arbitro: {sem_arbitro}/{len(acusacoes)} "
          f"(essas nao sustentam CRITICA -- regra R1 do juiz)")


_PESO = {"alta": 0, "media": 1, "baixa": 2}


def seleciona(acusacoes: list[dict], teto: int, cotas: dict | None = None) -> list[dict]:
    """Escolhe quem vai ao advogado, por COTA de categoria e nao por ordem.

    Sem isto, TOP_N pega as N primeiras e uma categoria barulhenta engole as
    vagas das outras. Dentro de cada bucket, confianca alta primeiro.
    """
    cotas = dict(cotas or COTAS)
    ordenadas = sorted(acusacoes, key=lambda a: _PESO.get(a.get("confianca"), 3))
    escolhidas, sobra = [], []
    for a in ordenadas:
        b = _bucket(a.get("categoria", "?"))
        if cotas.get(b, 0) > 0:
            cotas[b] -= 1
            escolhidas.append(a)
        else:
            sobra.append(a)  # curinga: preenche o que a cota deixou vago
    escolhidas.extend(sobra)
    return escolhidas[:teto]
