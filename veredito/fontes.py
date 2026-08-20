"""hack2l / Veredito -- fontes de acusacao que NAO sao os nossos promotores.

Scanner estatico gratis (bandit, semgrep) rodando em PARALELO com as seis
lentes, e nao em serie. A distincao importa e foi medida em 11/08:

  ❌ EM SERIE -- scanner primeiro, promotores atacando so o ponto cego dele.
     Ancora o modelo. No app do desafio a injecao de SQL esta em shares.py:31 e
     a quebra de isolamento em :92, tres funcoes abaixo: dizer ao promotor que
     ":31 ja esta coberto" convida a ler "shares.py ja esta coberto", e perde-se
     o achado mais valioso do PR para economizar centavos. E destroi o sinal de
     `_corroborado`, que so vale entre fontes INDEPENDENTES.

  ✅ EM PARALELO -- as duas listas se encontram no dedup, que e' codigo.

E nao e' por custo: medido, o scanner custa US$0,062 por veredito decidido
contra US$0,057 dos promotores. Nao rende mais. O que ele traz e' uma fonte
determinística, gratis, e independente -- a primeira vez que `_corroborado`
significa "duas fontes que nao sao o mesmo modelo".

⚠️ O TETO E' BAIXO. bandit no app do desafio: 2 achados, contra 45 dos
promotores. Ele nao viu a quebra de isolamento, nem a config morta, nem o
/shared-with-me errado. Scanner e' precisao SEM cobertura -- entra como
corroboracao, nunca como motor.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import config as cfg
from . import motor

# Achado de scanner que cai FORA dos arquivos do PR e' ruido de revisao: ele
# fala de codigo que ninguem tocou. Medido: bandit no psf/requests devolve 708
# achados no repo inteiro, quase todos `assert` em teste. Filtrando pelo diff,
# o scanner passa a responder a pergunta certa -- "o que ESTA MUDANCA trouxe".
_ARQUIVO_DO_DIFF = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.M)


def arquivos_do_diff(diff: str) -> set[str]:
    return {b for _, b in _ARQUIVO_DO_DIFF.findall(diff)}


def _dentro_do_diff(caminho: str, alvos: set[str]) -> bool:
    if not alvos:
        return True
    c = Path(caminho).as_posix()
    return any(c.endswith(a) or a.endswith(c) for a in alvos)


def _relativo(caminho: str, raiz: Path) -> str:
    """Caminho como os promotores o escrevem: relativo a raiz do repo.

    🚨 Sem isto a integracao inteira nao serve para nada. O scanner devolve
    caminho ABSOLUTO (`C:/.../desafio/app/api/app/routers/shares.py`) e o
    promotor devolve relativo (`app/api/app/routers/shares.py`). Locais que nao
    batem = dedup nao funde, cap de concentracao nao agrupa, e `_corroborado`
    nunca fica True -- ou seja, o unico motivo de ter posto o scanner em
    paralelo evapora. E o parecer ainda imprimiria o caminho da maquina de quem
    rodou.
    """
    try:
        return Path(caminho).resolve().relative_to(raiz.resolve()).as_posix()
    except (ValueError, OSError):
        return Path(caminho).as_posix()


# ------------------------------------------------- onde os scanners MORAM
#
# 🚨 Ate' 15/08 isto era `["py", "-3.12", "-m", "bandit", ...]` e `["semgrep",
# ...]`. Os dois chumbavam ambiente dentro do produto, cada um do seu jeito, e
# os dois falhavam CALADOS -- em formatos diferentes, o que atrasou o
# diagnostico:
#
#   bandit    `py -3.12` so' existe no Windows com o launcher. Onde nao existe,
#             o subprocess morre, `stdout` vem vazio, a regex nao casa e a
#             funcao devolvia `[]`. O `acusa` entao imprimia
#             "bandit 0 achado(s)" -- IDENTICO a "rodou e nao achou nada".
#   semgrep   executavel nu depende do PATH. Numa maquina onde o `Scripts\` do
#             Python nao esta no PATH, levanta FileNotFoundError. Barulhento por
#             acidente, nao por desenho.
#
# Medido nesta maquina em 15/08: bandit instalado e semgrep instalado, mas so'
# o bandit rodava. A rodada teria seguido sem metade da corroboracao externa,
# anunciando zero achados como se fosse resultado.
#
# E' o padrao de bug da casa: a guarda existe, mas fica muda exatamente onde
# precisa falar. Aqui a resolucao e' explicita e a ausencia LEVANTA.
_SEM_BANDIT = "bandit nao esta instalado neste interpretador"
_SEM_SEMGREP = "semgrep nao esta no PATH"


def _argv_bandit() -> list[str] | None:
    """`sys.executable`, nunca `py -3.12`: o scanner roda no MESMO interpretador
    que nos, entao `pip install bandit` no ambiente certo basta -- e nao ha
    launcher de plataforma nenhum no caminho."""
    if importlib.util.find_spec("bandit") is None:
        return None
    return [sys.executable, "-m", "bandit"]


def _argv_semgrep() -> list[str] | None:
    """`-m semgrep` esta DEPRECADO desde a 1.38 (avisa e nao roda), entao aqui
    nao ha simetria possivel com o bandit: e' o executavel ou nada. `which`
    resolve o caminho completo e tira o PATH da equacao na hora da chamada."""
    caminho = shutil.which("semgrep")
    return [caminho] if caminho else None


def disponiveis() -> dict[str, dict]:
    """Quais scanners rodariam AGORA -- no formato do `autoteste`.

    Existe para o pre-voo poder dizer em voz alta que a corroboracao externa
    nao vai acontecer, ANTES de a rodada gastar. Nao e' essencial: rodada sem
    scanner e' degradacao conhecida, igual app fora do ar.
    """
    fora = {}
    for nome, resolve, falta in (
        ("bandit", _argv_bandit, _SEM_BANDIT),
        ("semgrep", _argv_semgrep, _SEM_SEMGREP),
    ):
        argv = resolve()
        fora[nome] = {
            "ok": argv is not None,
            "detalhe": " ".join(argv) if argv else falta,
        }
    return fora


def _bandit(raiz: Path, alvos: set[str]) -> list[dict]:
    argv = _argv_bandit()
    if argv is None:
        raise RuntimeError(_SEM_BANDIT)
    r = subprocess.run(
        [*argv, "-r", str(raiz), "-f", "json", "-q"],
        capture_output=True, text=True, timeout=600, errors="replace",
    )
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    if not m:
        # Chegou aqui com o bandit instalado = ele rodou e nao produziu JSON.
        # Isso e' falha de execucao, nao ausencia de achado, e some se virar [].
        raise RuntimeError(
            f"bandit nao devolveu JSON (exit {r.returncode}): "
            f"{(r.stderr or r.stdout or '').strip()[:200]}"
        )
    fora = []
    for a in json.loads(m.group(0)).get("results", []):
        if not _dentro_do_diff(a["filename"], alvos):
            continue
        fora.append({
            "ferramenta": "bandit (analise estatica de seguranca)",
            "regra": f"{a['test_id']} ({a['test_name']})",
            "texto": a["issue_text"],
            "arquivo": _relativo(a["filename"], raiz), "linha": a["line_number"],
            "codigo": (a.get("code") or "")[:600],
            "severidade": a["issue_severity"],
        })
    return fora


def _semgrep(raiz: Path, alvos: set[str]) -> list[dict]:
    regras = cfg.RAIZ / "regras_semgrep" / "taint.yml"
    if not regras.is_file():
        # Regra ausente e' escolha de configuracao, nao defeito de ambiente:
        # sem arquivo de regra nao ha o que rodar, e zero e' a resposta certa.
        return []
    argv = _argv_semgrep()
    if argv is None:
        raise RuntimeError(_SEM_SEMGREP)
    r = subprocess.run(
        [*argv, "--config", str(regras), "--dataflow-traces", "--json",
         "--quiet", str(raiz)],
        capture_output=True, text=True, timeout=900, errors="replace",
    )
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    if not m:
        raise RuntimeError(
            f"semgrep nao devolveu JSON (exit {r.returncode}): "
            f"{(r.stderr or r.stdout or '').strip()[:200]}"
        )
    fora = []
    for a in json.loads(m.group(0)).get("results", []):
        if not _dentro_do_diff(a["path"], alvos):
            continue
        fora.append({
            "ferramenta": "semgrep (analise de fluxo / taint)",
            "regra": a["check_id"].split(".")[-1],
            "texto": " ".join(str(a["extra"].get("message", "")).split()),
            "arquivo": _relativo(a["path"], raiz), "linha": a["start"]["line"],
            "codigo": (a["extra"].get("lines") or "")[:600],
            "severidade": a["extra"].get("severity", "?"),
        })
    return fora


SISTEMA_ADAPTADOR = (
    "Voce converte achados de ferramentas de analise estatica em alegacoes "
    "VERIFICAVEIS. Responda SEMPRE com um unico objeto JSON e nada mais."
)

PROMPT_ADAPTADOR = """\
# O achado, no formato da ferramenta de origem

ferramenta: {ferramenta}
regra: {regra}
severidade: {severidade}
local: {arquivo}:{linha}
texto: {texto}

trecho de codigo:
```
{codigo}
```

# Seu trabalho

Transformar isto numa alegacao que um VERIFICADOR possa provar ou refutar
executando alguma coisa -- ou dizer que nao da.

O campo que decide e' o `provado_se`: um experimento **concreto e observavel**,
que alguem roda e olha o resultado.

🚫 Se o seu `provado_se` so' consegue confirmar que o TRECHO DE CODIGO e' o que
ele e' -- que existe um `assert`, que falta um `timeout=` -- ele nao verifica
nada. A ferramenta ja afirmou isso. Responda NAO_TESTAVEL.

⚠️ Prova de injecao e' sempre READ-ONLY: `' OR '1'='1` fazendo a query devolver
linhas demais, **nunca** DROP/DELETE. O verificador roda isto contra o app real.

Se nao consegue formular:

  {{"testavel": false, "motivo": "<uma linha>"}}

Se consegue:

  {{"testavel": true,
    "categoria": "<correcao|injection|vazamento_de_contexto|padroes|performance|prd>",
    "local": "{arquivo}:{linha}",
    "hipotese": "<uma linha: o defeito afirmado, nao a regra da ferramenta>",
    "arbitro": null,
    "provado_se": "<uma linha: o experimento observavel>",
    "confianca": "<alta|media|baixa>"}}

`arbitro` e' SEMPRE null aqui: a regra do scanner e' da ferramenta, nao do
repositorio sob revisao.
"""


def _adapta(cliente, achado: dict) -> dict | None:
    try:
        r = cliente.messages.create(
            model=motor.modelo(cfg.MODEL_PROMOTOR), max_tokens=1200,
            system=SISTEMA_ADAPTADOR,
            messages=[{"role": "user",
                       "content": PROMPT_ADAPTADOR.format(**achado)}],
        )
        if getattr(r, "stop_reason", None) == "refusal":
            return None
        texto = "\n".join(b.text for b in r.content
                          if getattr(b, "type", None) == "text")
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if not m:
            return None
        res = json.loads(m.group(0))
        return res if res.get("testavel") else None
    except Exception:
        return None


# Tolerancia, em linhas, para considerar que duas fontes falam do mesmo ponto.
#
# 🚨 Casamento exato de string NAO funciona, e a medicao de 11/08 mostra por
# que: os promotores emitem FAIXAS e a linha oscila. Para o mesmo defeito de SQL
# eles escreveram `shares.py:30`, `:31`, `:32`, `:30-34`, `:32-35` e `:23-35`,
# enquanto o scanner -- que le a AST -- emite `:31` seco. Sem faixa, zero
# corroboracao, que foi exatamente o que aconteceu na primeira rodada integrada.
#
# 2 e nao 5: em shares.py a injecao esta na :31 e a config morta na :36. Uma
# tolerancia larga fundiria defeitos distintos que por acaso moram perto.
TOLERANCIA_LINHAS = 2

# Acima disto, a acusacao aponta uma REGIAO, nao um ponto -- e regiao nao pode
# ser corroborada por um achado de uma linha.
#
# 🚨 Medido: com o scanner apontando so shares.py:31, o cruzamento sem este
# limite marcou ONZE acusacoes como corroboradas, incluindo uma em `:15-96` (82
# linhas, o arquivo inteiro) que falava de schema Pydantic. Inflar o sinal e' o
# erro de sempre deste projeto -- "arbitro preenchido" contava 94 de 94.
LARGURA_MAX_PARA_CORROBORAR = 10


def _faixa(local) -> tuple[str, int, int] | None:
    """(arquivo, primeira, ultima) de `arquivo:12` ou `arquivo:12-20`."""
    m = re.match(r"^\s*(.+?):(\d+)(?:\s*-\s*(\d+))?", str(local or ""))
    if not m:
        return None
    ini = int(m.group(2))
    fim = int(m.group(3)) if m.group(3) else ini
    return Path(m.group(1).strip()).as_posix(), min(ini, fim), max(ini, fim)


def _mesmo_ponto(a, b) -> bool:
    """Mesmo arquivo e faixas que se tocam, com folga de TOLERANCIA_LINHAS."""
    fa, fb = _faixa(a), _faixa(b)
    if not fa or not fb:
        return False
    arq_a, ia, ta = fa
    arq_b, ib, tb = fb
    if not (arq_a.endswith(arq_b) or arq_b.endswith(arq_a)):
        return False
    if (ta - ia + 1) > LARGURA_MAX_PARA_CORROBORAR:
        return False          # o primeiro aponta uma regiao, nao um ponto
    return ia - TOLERANCIA_LINHAS <= tb and ib - TOLERANCIA_LINHAS <= ta


def cruza(dos_promotores: list[dict], do_scanner: list[dict]) -> list[dict]:
    """Cruza as duas fontes por LOCAL. Anota o que coincide, devolve o que e' novo.

    🚨 Este desenho substitui o primeiro, que nao funcionava -- e a medicao de
    11/08 e' que mostrou:

      1. `arbitro` do scanner e' SEMPRE null (a regra e' da ferramenta, nao do
         repo sob revisao). Correto, e mantido.
      2. `_chave_dedup` chaveia em (local, arbitro), entao arbitro null devolve
         None.
      3. Logo o achado de scanner NUNCA funde e `_corroborado` NUNCA fica True.

    As duas regras que eu escrevi se contradiziam: o mecanismo existia e a
    precondicao dele nunca valia. Padrao de bug deste projeto, num lugar novo.

    O conserto nao e' afrouxar o dedup -- e' notar que o scanner **nao devia
    disputar vaga**. Medido: os 3 achados dele cairam todos em shares.py:31,
    onde um promotor ja acusava. Gastar 1 das 10 vagas do advogado para
    reverificar a mesma linha nao compra nada; dizer que uma ferramenta
    DETERMINISTICA e INDEPENDENTE apontou o mesmo lugar compra bastante -- e' a
    evidencia de que o promotor nao alucinou.

    Entao: corrobora o que coincide, acusa o que ninguem viu.
    """
    novas = []
    for s in do_scanner:
        alvos = [a for a in dos_promotores if _mesmo_ponto(a.get("local"), s.get("local"))]
        if not alvos:
            novas.append(s)          # ninguem viu: entra como acusacao
            continue
        for a in alvos:              # coincidiu: vira corroboracao
            a.setdefault("_scanner", []).append({
                "ferramenta": s.get("_fonte"),
                "texto": s.get("_texto_original") or s.get("hipotese"),
                "local": s.get("local"),
            })
            a["_corroborado_externo"] = True
    return novas


def acusa(diff: str, raiz: Path | None = None) -> list[dict]:
    """Achados de scanner, ja no esquema de acusacao. Nunca derruba a rodada.

    Falha de scanner e' degradacao, nao erro: os promotores continuam sendo a
    fonte principal, e uma lista vazia aqui so' significa uma rodada sem
    corroboracao externa.
    """
    raiz = raiz or cfg.DESAFIO
    alvos = arquivos_do_diff(diff)
    brutos: list[dict] = []
    for nome, fn in (("bandit", _bandit), ("semgrep", _semgrep)):
        try:
            achados = fn(raiz, alvos)
            print(f"  {nome:10} {len(achados)} achado(s) nos arquivos do PR")
            brutos += achados
        except Exception as e:
            # A CAUSA, nao so' o tipo. "FALHOU (RuntimeError)" mandava quem le
            # o log abrir o codigo para descobrir se faltava binario, PATH ou
            # regra -- e as tres tem consertos diferentes.
            print(f"  {nome:10} NAO RODOU -- {e} (seguindo sem ele)")
    if not brutos:
        return []

    cliente = motor.cliente()
    fora = []
    for i, a in enumerate(brutos, 1):
        conv = _adapta(cliente, a)
        if conv is None:
            continue
        conv["id"] = f"scanner_{i:02d}"
        conv["_fonte"] = a["ferramenta"]
        conv["_texto_original"] = a["texto"]
        conv["arbitro"] = None
        fora.append(conv)
    print(f"  {len(fora)}/{len(brutos)} viraram alegacao testavel")
    return fora
