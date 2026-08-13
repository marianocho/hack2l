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

from . import arbitro as arb
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


def mede_diff(diff: str) -> tuple[int, int]:
    """(linhas alteradas, arquivos tocados) de um diff unificado."""
    linhas = arquivos = 0
    for l in diff.splitlines():
        if l.startswith("+++") or l.startswith("---"):
            continue
        if l.startswith("diff --git"):
            arquivos += 1
        elif l.startswith("+") or l.startswith("-"):
            linhas += 1
    return linhas, arquivos


# Teto de acusacoes POR LENTE, em funcao do tamanho do diff.
#
# 🚨 Medido em 11/08 nos 10 PRs reais: a contagem de acusacoes e' praticamente
# CONSTANTE (7 a 29) enquanto o diff varia 400x (1 a 389 linhas). A taxa por 10
# linhas vai de 130 (django#21735, UMA linha, 13 acusacoes) a 0,7 (next.js, 389
# linhas, 29 acusacoes) -- 185x de diferenca. Os promotores nao escalam: eles
# produzem "um punhado" e pronto.
#
# A formula e' linear no pe e limitada no teto, de proposito: ela so MORDE nos
# PRs minusculos, que e' onde o comportamento atual e' absurdo. Conferida
# contra os 10:
#
#   1 linha  -> 1/lente (6 no total)   hoje: 13   MORDE
#   2 linhas -> 1/lente                hoje:  8   MORDE
#   13       -> 3/lente (18)           hoje: 15   nao morde
#   51       -> 9/lente (54)           hoje: 20   nao morde
#   389      -> 10/lente (teto)        hoje: 29   nao morde
#
# ⚠️ Isto NAO e' pedir seletividade -- a regra do doc continua valendo, e a
# diferenca importa. "Reporte apenas problemas relevantes" faz o modelo aplicar
# filtro de qualidade e engolir achado real. "Este diff muda 1 linha; emita ate
# 1" e' calibracao de escala, e so aperta onde 13 acusacoes para uma linha ja
# era ruido. Em PR de tamanho normal o teto nem encosta.
TETO_LENTE_MIN = 1
TETO_LENTE_MAX = 10


def orcamento_por_lente(diff: str) -> int:
    linhas, _ = mede_diff(diff)
    bruto = -(-(3 + linhas) // 6)          # ceil((3 + linhas) / 6)
    return max(TETO_LENTE_MIN, min(TETO_LENTE_MAX, bruto))


def _bloco_orcamento(diff: str) -> str:
    linhas, arquivos = mede_diff(diff)
    teto = orcamento_por_lente(diff)
    return (
        "# Tamanho da mudanca sob revisao\n\n"
        f"Este diff altera **{linhas} linha(s)** em **{arquivos} arquivo(s)**.\n\n"
        f"**Emita no maximo {teto} acusacao(oes)** nesta lente.\n\n"
        "Isto e' calibracao de escala, nao filtro de relevancia: uma mudanca "
        "pequena tem menos superficie para esconder defeito, entao levantar "
        "dezenas de hipoteses sobre ela e' ruido que enterra o achado real e "
        "queima o orcamento de quem vai testar. Continue sem filtrar por "
        "gravidade ou por 'quao importante parece' -- so escolha as mais "
        "plausiveis se estourar o teto. Se a mudanca nao tem nada da sua lente, "
        "**devolver um array vazio e' resposta correta.**"
    )


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
        # Normaliza na fronteira, uma vez. O modelo pode devolver o objeto novo,
        # uma sigla solta (habito antigo) ou lixo; a jusante ninguem deveria
        # precisar saber disso.
        a["arbitro"] = arb.normaliza(a.get("arbitro"))
        out.append(a)
    return out, None


def _acusa_um(cliente, nome: str, lente: str, diff: str,
              contexto: str | None = None) -> dict:
    inicio = time.time()
    # Prefixo IDENTICO nas 6 chamadas -- o Haiku cacheia uma vez e as outras
    # cinco leem a ~10%. O contexto do repo entra aqui, junto do diff, e nao
    # dentro da lente: ele e' o mesmo para os seis promotores, entao cacheia
    # igual; chumbado na lente, viajaria para dentro de todo diff do mundo.
    prefixo = [
        {"type": "text", "text": f"# Diff do PR sob revisao\n\n{diff}",
         "cache_control": {"type": "ephemeral"}},
        # Derivado do diff, entao identico nas 6 chamadas -- cacheia junto.
        {"type": "text", "text": _bloco_orcamento(diff)},
    ]
    if contexto:
        prefixo.append({
            "type": "text",
            "text": (
                "# Contexto do repositorio sob revisao\n\n"
                "O que ESTE repositorio documenta sobre si mesmo. E' a unica "
                "fonte legitima para o campo `arbitro`: cite a regra e o "
                "arquivo:linha onde ela esta escrita. Nada aqui vale para outro "
                f"repositorio.\n\n{contexto}"
            ),
            "cache_control": {"type": "ephemeral"},
        })
    try:
        r = cliente.messages.create(
            model=cfg.MODEL_PROMOTOR,
            max_tokens=8000,
            system=SISTEMA,
            messages=[{"role": "user", "content": prefixo + [
                {"type": "text", "text": lente},
            ]}],
        )
        # stop_reason antes de content, mesmo no Haiku.
        if getattr(r, "stop_reason", None) == "refusal":
            return {"nome": nome, "acusacoes": [], "erro": "recusa do classificador"}
        texto = "\n".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        acusacoes, erro = _parse(texto, nome)
        # Anteparo do orcamento. O prompt ja pediu o teto; isto pega o caso de o
        # modelo ignorar. MARCA, nao apaga: a lista bruta continua completa em
        # disco, e quem desprioriza e' `seleciona` -- nada some em silencio.
        teto = orcamento_por_lente(diff)
        if len(acusacoes) > teto:
            acusacoes.sort(key=lambda a: _PESO.get(a.get("confianca"), 3))
            for i, a in enumerate(acusacoes[teto:], 1):
                a["_excedente_orcamento"] = teto + i
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


def acusa(diff: str, contexto: str | None = None) -> list[dict]:
    """Os 6 promotores em paralelo. Grava a lista BRUTA antes de qualquer corte.

    `contexto` e' o que o repositorio sob revisao documenta sobre si mesmo, com
    procedencia. **Ele e' opcional de proposito**: sem ele os promotores acusam
    igual e o `arbitro` sai `null`, que e' a resposta honesta para os
    repositorios que nao documentam os proprios criterios -- ou seja, quase
    todos. Ver `arbitro.py` para o numero que comprou essa decisao.
    """
    cfg.prepara_pastas()
    cliente = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    ls = lentes()
    print(f"{len(ls)} promotores em paralelo, modelo {cfg.MODEL_PROMOTOR}")
    print(f"contexto do repo: "
          f"{f'{len(contexto)} chars' if contexto else 'NENHUM (arbitro sai null)'}")

    # A primeira SOZINHA, depois as outras cinco. Uma entrada de cache so fica
    # legivel depois que a primeira resposta comeca a chegar: disparando as 6
    # juntas, nenhuma le o que as outras estao escrevendo e todas pagam preco
    # cheio pelo diff. Medido -- 5 das 6 vieram com cache zero.
    resultados = [_acusa_um(cliente, ls[0][0], ls[0][1], diff, contexto)]
    if len(ls) > 1:
        with cf.ThreadPoolExecutor(max_workers=len(ls) - 1) as ex:
            resultados += list(ex.map(
                lambda t: _acusa_um(cliente, t[0], t[1], diff, contexto), ls[1:]))

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

    # Quem grava `acusacoes_brutas.json` e' o orquestrador, DEPOIS de juntar
    # todas as fontes. Gravar aqui fazia o arquivo omitir o que nao veio das
    # seis lentes -- e a lista bruta e' justamente o que se olha quando algo
    # passou batido. Os scripts que chamam `acusa` direto (generaliza,
    # experimentos) gravam a propria saida.
    _diagnostico(todas)
    return todas


def _diagnostico(acusacoes: list[dict]) -> None:
    """Os sinais que o doc manda olhar quando os promotores deixam passar.

    Categoria com contagem destoante = falta contexto naquela lente.
    Tudo concentrado em poucos arquivos = nao leu o diff inteiro.
    """
    print(f"\n  {len(acusacoes)} acusacoes brutas -> "
          f"{(cfg.RODADA / 'acusacoes_brutas.json').relative_to(cfg.RAIZ)}")
    if not acusacoes:
        return
    por_cat = Counter(a.get("categoria", "?") for a in acusacoes)
    print("  por categoria:", dict(por_cat))
    arquivos = Counter(str(a.get("local", "?")).split(":")[0] for a in acusacoes)
    print(f"  arquivos tocados: {len(arquivos)} | top: {dict(arquivos.most_common(4))}")

    # Tres numeros, nao um. O antigo "sem arbitro" contava o campo preenchido, e
    # foi exatamente essa metrica que nos enganou: 94 de 94 preenchidos, 94 de 94
    # reciclando os criterios do desafio. Preenchido nao e' o mesmo que valido.
    com_proc = sum(1 for a in acusacoes if arb.tem_procedencia(a.get("arbitro")))
    citado = sum(1 for a in acusacoes if arb.citado(a.get("arbitro")))
    n = len(acusacoes)
    print(f"  arbitro com procedencia: {com_proc}/{n} "
          f"(so estes sustentam CRITICA por regra -- R1 do juiz)")
    if citado > com_proc:
        print(f"  arbitro citado sem dizer onde: {citado - com_proc} "
              f"(nao contam; regra que ninguem localiza e' opiniao)")
    chumbados = [a for a in acusacoes if arb.parece_chumbado(a.get("arbitro"))]
    if chumbados:
        print(f"  [!!] {len(chumbados)} arbitro(s) com vocabulario CHUMBADO "
              f"({', '.join(sorted({str(c['arbitro']['regra'])[:24] for c in chumbados}))})"
              f" -- se este repo nao e' o Hack2L, o conserto de 09/08 regrediu")
    # Sem arbitro nao ha chave de dedup, e sem dedup a duplicata queima vaga de
    # cota. Com `null` honesto virando a maioria, isto deixou de ser detalhe.
    sem_chave = sum(1 for a in acusacoes if _chave_dedup(a) is None)
    if sem_chave:
        print(f"  sem chave de dedup: {sem_chave}/{n} "
              f"(nao deduplicam -- conservador de proposito, ver deduplica())")


_PESO = {"alta": 0, "media": 1, "baixa": 2}


def _chave_dedup(a: dict) -> tuple | None:
    """Duas acusacoes sao a mesma quando apontam o mesmo LOCAL e o mesmo ARBITRO.

    Conservador de proposito: sem arbitro ou sem local, nao deduplica. Fundir
    dois achados distintos e' pior que gastar uma vaga a mais -- o desafio e'
    explicito em que deixar passar defeito real custa mais que falso alarme.

    ⚠️ Efeito colateral do conserto de 09/08, medido e nao consertado aqui: com
    `arbitro` honestamente `null` na maioria dos casos, esta chave devolve None
    quase sempre e o dedup para de acontecer. E' um problema REAL (duplicata
    ocupa vaga de cota), mas e' o buraco 2 do handoff -- "nao existe piso" -- e
    afrouxar a chave para (local, categoria) fundiria achados distintos no mesmo
    arquivo. Fica registrado no diagnostico em vez de ser resolvido as escondidas.
    """
    local = a.get("local")
    chave_arb = arb.chave(a.get("arbitro"))
    if not local or not chave_arb:
        return None
    return (str(local).strip(), chave_arb)


def deduplica(acusacoes: list[dict]) -> list[dict]:
    """Funde acusacoes identicas ANTES do advogado, nao depois.

    Antes importa: cada acusacao custa ~130 s de Opus 5, e numa rodada de 10
    vagas uma duplicata queima uma vaga provando duas vezes a mesma coisa.
    Deduplicar so no parecer limpa o texto com o dinheiro ja gasto.

    Medido em 08/08 nas 47 acusacoes do diff real: 37 caiam em local ja citado
    por outra, e 8 estavam em pares com local E arbitro identicos.

    A sobrevivente e' a de maior confianca. As outras viram `_duplicatas`.

    ⚠️ `_corroborado` distingue os dois casos, e a distincao e' honestidade de
    palco, nao detalhe:

      _corroborado=True   promotores DIFERENTES chegaram ao mesmo ponto. E'
                          sinal: "duas lentes independentes convergiram".
      _corroborado=False  o MESMO promotor repetiu. Nao e' sinal nenhum, e'
                          redundancia interna dele.

    Medido em 08/08 nas 47 acusacoes do diff real: 4 fusoes, e as QUATRO eram
    intra-promotor (correcao+correcao, injection+injection, prd+prd x2). Zero
    corroboracao cruzada. Apresentar aquilo como "N promotores independentes
    apontaram" teria sido falso -- por isso a flag existe antes de alguem
    montar slide em cima do campo.
    """
    por_chave: dict[tuple, dict] = {}
    saida: list[dict] = []
    for a in sorted(acusacoes, key=lambda x: _PESO.get(x.get("confianca"), 3)):
        k = _chave_dedup(a)
        if k is None:
            saida.append(a)
            continue
        primeira = por_chave.get(k)
        if primeira is None:
            por_chave[k] = a
            saida.append(a)
            continue
        primeira.setdefault("_duplicatas", []).append(
            {"id": a.get("id"), "categoria": a.get("categoria"),
             "confianca": a.get("confianca"), "hipotese": a.get("hipotese")}
        )
        fontes = {primeira.get("_promotor") or primeira.get("categoria")} | {
            d.get("categoria") for d in primeira["_duplicatas"]
        }
        primeira["_corroborado"] = len(fontes) > 1
    return saida


# Quantas acusacoes do MESMO arquivo:linha podem ocupar vaga do advogado.
#
# 🚨 Medido em 10/08, no `encode/httpx#3730`: 4 das 6 vagas foram para
# `.github/workflows/test-suite.yml:17`. As outras lentes ficaram sem verificar.
#
# ⚠️ E o diagnostico obvio estava ERRADO. Eu chamei aquilo de "a mesma alegacao
# quatro vezes" e ia fundir por conteudo. Lendo o texto inteiro, sao quatro
# preocupacoes DIFERENTES sobre a mesma mudanca de uma linha: metadados nao
# atualizados, usuario de 3.10 sem aviso, titulo que promete mais que o diff, e
# politica de suporte. Fundir perderia informacao.
#
# A similaridade lexical confirma que nao da para separar automaticamente: os
# pares que "deveriam fundir" deram 0,00-0,13 de Jaccard, indistinguivel dos que
# nao deveriam (0,00-0,06). E dedup por linha exata falharia no caso que mais
# importa -- a injecao de SQL do desafio foi reportada em shares.py:31, :32 e
# :33 por tres lentes, mesma linha nenhuma.
#
# Entao nao se funde nada: limita-se CONCENTRACAO. O dano real nunca foi
# duplicata, foi ponto quente comendo o orcamento.
MAX_POR_LOCAL = 2


def _local_chave(a: dict) -> str | None:
    loc = str(a.get("local") or "").strip()
    return loc.casefold() or None


def seleciona(acusacoes: list[dict], teto: int, cotas: dict | None = None,
              max_por_local: int = MAX_POR_LOCAL) -> list[dict]:
    """Escolhe quem vai ao advogado, por COTA de categoria e nao por ordem.

    Sem isto, TOP_N pega as N primeiras e uma categoria barulhenta engole as
    vagas das outras. Dentro de cada bucket, confianca alta primeiro.

    Deduplica antes de aplicar a cota: uma duplicata que ocupa vaga de cota
    tira a vaga de uma categoria inteira, nao so de outra acusacao.

    E limita quantas do MESMO local ocupam vaga -- ver MAX_POR_LOCAL.

    ⚠️ O limite e' MOLE de proposito: a excedente vai para o FIM da sobra, nao
    para o lixo. Com fila cheia ela nao rouba vaga; com fila curta ela ainda
    entra. "Nada e' descartado em silencio" vale aqui tambem -- um teto duro
    sumiria com acusacao sem ninguem ver.
    """
    cotas = dict(cotas or COTAS)
    antes = len(acusacoes)
    acusacoes = deduplica(acusacoes)
    if len(acusacoes) < antes:
        print(f"  dedup: {antes} -> {len(acusacoes)} "
              f"({antes - len(acusacoes)} fundidas em _duplicatas)")
    ordenadas = sorted(acusacoes, key=lambda a: _PESO.get(a.get("confianca"), 3))
    escolhidas, sobra, excedente = [], [], []
    por_local: Counter = Counter()
    for a in ordenadas:
        # Estourou o orcamento da lente: vai para o fim, junto das de local
        # concentrado. Mesmo tratamento, mesma razao -- despriorizar, nao sumir.
        if a.get("_excedente_orcamento"):
            excedente.append(a)
            continue
        loc = _local_chave(a)
        if loc and por_local[loc] >= max_por_local:
            a["_excedente_no_local"] = por_local[loc] + 1
            excedente.append(a)
            continue
        b = _bucket(a.get("categoria", "?"))
        if cotas.get(b, 0) > 0:
            cotas[b] -= 1
            if loc:
                por_local[loc] += 1
            escolhidas.append(a)
        else:
            sobra.append(a)  # curinga: preenche o que a cota deixou vago
    if excedente:
        quentes = {l: n for l, n in por_local.items() if n >= max_por_local}
        print(f"  concentracao: {len(excedente)} acusacao(oes) despriorizada(s) "
              f"em {len(quentes)} local(is) ja com {max_por_local} vaga(s)")
    escolhidas.extend(sobra)
    escolhidas.extend(excedente)   # por ultimo, mas nunca descartado
    return escolhidas[:teto]
