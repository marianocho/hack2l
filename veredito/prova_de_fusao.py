"""Duas acusacoes sao o mesmo defeito? Pergunta ao exit code, nao ao texto.

`fusao.py` agrupa por ENDERECO e PROCEDENCIA -- inferencia. Funciona, acertou o
PR da bancada, mas e' exatamente o tipo de argumento que este produto recusa de
todo mundo e estava aceitando de si mesmo. Aqui a mesma pergunta vira medicao.

## O teste

Cada acusacao provada deixou um artefato executavel: um teste que passa no base
e falha no head. Entao:

    reverte UM trecho do diff  ->  quais testes param de falhar?

    todos param      -> um trecho explica todos: E' O MESMO DEFEITO
    so' alguns param -> aquele trecho explica so' aqueles: SAO DEFEITOS DIFERENTES
    nenhum trecho    -> nao deu para atribuir: INCONCLUSIVO, e diz por que

O terceiro estado nao e' decoracao: sem ele, "nao consegui medir" viraria "sao o
mesmo", que e' a absolvicao falsa de sempre com roupa nova.

## 🚨 A granularidade e' TRECHO, nunca hunk

Medido a mao em 18/08 e quase implementado errado: o PR da bancada e' UM hunk
com duas mudancas dentro -- uma docstring e a condicao de autorizacao.
Revertendo o hunk inteiro, tudo passa; mas isso e' so' "reverter o PR conserta o
PR", que e' trivialmente verdade e nao diz nada sobre os testes serem o mesmo
defeito.

O que deu sentido ao experimento foi separar as duas: revertendo SO' a docstring
os tres testes continuaram falhando (controle negativo), e revertendo SO' a
condicao os tres passaram.

Por isso a unidade e' o **trecho contiguo de linhas alteradas** -- os opcodes do
`difflib` entre base e head, que separam a docstring da condicao porque ha uma
linha de contexto entre elas.

⚠️ Diff com um unico trecho nao consegue discriminar NADA, e o resultado honesto
ali e' INCONCLUSIVO por trecho unico -- nao "provado". Reverter o trecho unico e'
reverter o PR.

## O que ela pode fazer que a heuristica nao pode

SEPARAR. A heuristica so' junta; se ela juntou errado, nada desfaz. A prova
desfaz: se o trecho que conserta A nao conserta B, A e B voltam a ser dois
achados, com evidencia de que sao dois.

## Onde nao alcanca

Precisa de artefato e de container -- so' onde a `prova_diferencial` funciona.
Em PR de terceiro com `read_file` e `grep` nao ha teste para rodar, e o
agrupamento fica com a heuristica, rotulado como tal. E' a mesma degradacao
honesta do resto do produto: onde nao da' para provar, ele diz que nao provou.
"""

from __future__ import annotations

from difflib import SequenceMatcher

# Teto de execucoes de container por grupo. Cada trecho e' uma rodada de pytest;
# um diff grande com um grupo grande viraria uma tarde. Estourou o teto, o
# desfecho e' INCONCLUSIVO com a causa dita -- nunca um palpite.
MAX_TRECHOS = 12

MESMO = "MESMO_DEFEITO"
DIFERENTES = "DEFEITOS_DIFERENTES"
INCONCLUSIVO = "INCONCLUSIVO"


def trechos(base_texto: str, head_texto: str) -> list[tuple[int, int, int, int]]:
    """Os trechos contiguos de mudanca entre base e head.

    Devolve `(i1, i2, j1, j2)` em indices de LINHA: `base[i1:i2]` virou
    `head[j1:j2]`. Linhas de contexto separam um trecho do seguinte, que e'
    justamente o que separa a docstring da condicao no PR da bancada.
    """
    a = base_texto.splitlines(keepends=True)
    b = head_texto.splitlines(keepends=True)
    return [(i1, i2, j1, j2)
            for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes()
            if tag != "equal"]


def reverte(base_texto: str, head_texto: str,
            trecho: tuple[int, int, int, int]) -> str:
    """O head com UM trecho desfeito, e o resto da mudanca intacto."""
    i1, i2, j1, j2 = trecho
    a = base_texto.splitlines(keepends=True)
    b = head_texto.splitlines(keepends=True)
    return "".join(b[:j1] + a[i1:i2] + b[j2:])


def classifica(passaram_por_trecho: list[set[str]], ids: set[str]) -> tuple[str, dict]:
    """O veredito da fusao, a partir de quem passou em cada reversao.

    `passaram_por_trecho[k]` = ids cujos testes passaram revertendo o trecho k.

    🚨 Exige que o trecho explique o grupo INTEIRO para declarar MESMO. Um
    trecho que conserta 2 de 3 nao e' "quase o mesmo defeito": e' a prova de que
    o terceiro tem outra causa.
    """
    if not passaram_por_trecho:
        return INCONCLUSIVO, {"causa": "nenhum trecho pode ser medido"}
    if len(passaram_por_trecho) == 1:
        # Reverter o unico trecho e' reverter o PR. Nao discrimina nada.
        return INCONCLUSIVO, {"causa": "o diff tem um trecho so': reverte-lo e' "
                                       "reverter o PR, e nao separa causa nenhuma"}
    for k, passaram in enumerate(passaram_por_trecho):
        if passaram >= ids:
            return MESMO, {"trecho": k, "explica": sorted(ids)}
    # Ninguem explica o grupo todo. Se algum trecho explica um pedacao proprio,
    # isso e' evidencia POSITIVA de que sao defeitos distintos.
    for k, passaram in enumerate(passaram_por_trecho):
        parcial = passaram & ids
        if parcial and parcial != ids:
            return DIFERENTES, {"trecho": k, "explica": sorted(parcial),
                                "nao_explica": sorted(ids - parcial)}
    return INCONCLUSIVO, {"causa": "nenhum trecho fez teste algum passar -- a "
                                   "causa pode estar fora do diff"}


def parte(grupo: list[dict], veredito: str, detalhe: dict) -> list[list[dict]]:
    """Aplica o veredito ao grupo: mantem junto, ou separa com a evidencia.

    ⚠️ INCONCLUSIVO mantem o agrupamento da heuristica -- nao desfaz nem
    confirma. Desfazer por nao ter conseguido medir seria tratar ausencia de
    medicao como medicao, que e' a R3 uma camada acima.
    """
    if veredito != DIFERENTES:
        return [grupo]
    explicados = set(detalhe.get("explica") or ())
    dentro = [v for v in grupo if v.get("id") in explicados]
    fora = [v for v in grupo if v.get("id") not in explicados]
    return [g for g in (dentro, fora) if g]


def frase(veredito: str, detalhe: dict, n: int) -> str:
    """A linha que vai ao parecer. Quem le tem que saber se foi PROVA ou palpite."""
    if veredito == MESMO:
        return (f"FUSAO PROVADA: revertendo um unico trecho do diff, os {n} "
                f"testes param de falhar. A causa e' a mesma -- medido por exit "
                f"code, nao inferido por semelhanca.")
    if veredito == DIFERENTES:
        return (f"FUSAO DESFEITA POR PROVA: o trecho que conserta "
                f"{', '.join(detalhe.get('explica') or [])} NAO conserta "
                f"{', '.join(detalhe.get('nao_explica') or [])}. Sao causas "
                f"diferentes, apesar de caírem no mesmo lugar.")
    return (f"AGRUPAMENTO NAO PROVADO ({detalhe.get('causa','sem causa registrada')}). "
            f"Os {n} achados foram agrupados por endereco e procedencia, que e' "
            f"indicio e nao prova.")


# --------------------------------------------------------------- a execucao
#
# Daqui para baixo precisa de container. Tudo acima e' puro e tem teste que roda
# em milissegundos -- a divisao e' de proposito: a logica que decide o veredito
# nao pode depender de Docker para ser conferida.

def _arquivos_do_diff(base: str, head: str) -> list[str]:
    import subprocess
    from . import config as cfg
    r = subprocess.run(["git", "-C", str(cfg.DESAFIO), "diff", "--name-only",
                        base, head], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return [l.strip() for l in (r.stdout or "").splitlines()
            if l.strip().endswith(".py")]


def _conteudo(sha: str, caminho: str) -> str:
    import subprocess
    from . import config as cfg
    r = subprocess.run(["git", "-C", str(cfg.DESAFIO), "show", f"{sha}:{caminho}"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r.stdout or ""



def _resolve(sha: str) -> str:
    """O sha completo. A conferencia do worktree compara a string inteira."""
    import subprocess
    from . import config as cfg
    r = subprocess.run(["git", "-C", str(cfg.DESAFIO), "rev-parse", sha],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip()


def prova_o_grupo(grupo: list[dict], artefatos: dict, base: str, head: str
                  ) -> tuple[str, dict]:
    """Roda a bissecção de trechos contra os testes do grupo.

    Devolve `(veredito, detalhe)` -- os mesmos que `classifica` produz, para
    que o chamador nao precise saber se veio de medicao ou de contagem.

    ⚠️ Qualquer tropeco vira INCONCLUSIVO COM CAUSA, nunca uma suposicao. Um
    grupo que nao pode ser medido continua agrupado pela heuristica e o parecer
    diz que foi a heuristica.
    """
    from pathlib import Path
    from . import config as cfg
    from . import ferramentas as f

    testes = {}
    for v in grupo:
        art = artefatos.get(v.get("id")) or {}
        nome = art.get("arquivo_do_teste")
        if art.get("estado") != "PROVADO" or not nome:
            return INCONCLUSIVO, {"causa": f"{v.get('id')} nao tem artefato de "
                                           "prova diferencial para reexecutar"}
        origem = cfg.ARTEFATOS / f"teste_{v['id']}_{nome}"
        if not origem.exists():
            return INCONCLUSIVO, {"causa": f"o arquivo de teste de {v.get('id')} "
                                           "nao ficou no disco desta rodada"}
        testes[v["id"]] = (origem, nome)

    todos = []
    for caminho in _arquivos_do_diff(base, head):
        b, h = _conteudo(base, caminho), _conteudo(head, caminho)
        if not h:
            continue
        for t in trechos(b, h):
            todos.append((caminho, b, h, t))
    if len(todos) > MAX_TRECHOS:
        return INCONCLUSIVO, {"causa": f"o diff tem {len(todos)} trechos, acima "
                                       f"do teto de {MAX_TRECHOS} desta medicao"}

    # 🚨 Sha COMPLETO. `_garante_worktree` confere a string inteira contra o
    # `rev-parse HEAD`, que sempre volta completo -- passar o curto levanta com
    # uma mensagem que, ate' 18/08, truncava os dois lados e dizia "nao ficou em
    # 61cc0a7 (esta em 61cc0a7)".
    head_cheio = _resolve(head) or head
    try:
        wt = f._garante_worktree(head_cheio, "prova_fusao")
    except Exception as e:  # noqa: BLE001 -- worktree e' infra, nao veredito
        return INCONCLUSIVO, {"causa": f"nao consegui montar o worktree: {e}"}

    destino_testes = Path(wt) / (cfg.CODIGO_TESTES or "tests")
    passaram_por_trecho: list[set[str]] = []
    try:
        for id_, (origem, nome) in testes.items():
            (destino_testes / f"pf_{id_}_{nome}").write_text(
                origem.read_text(encoding="utf-8"), encoding="utf-8")
        for caminho, b, h, t in todos:
            alvo = Path(wt) / caminho
            original = alvo.read_text(encoding="utf-8")
            alvo.write_text(reverte(b, h, t), encoding="utf-8")
            try:
                passaram = set()
                for id_, (_, nome) in testes.items():
                    rel = f"{cfg.CODIGO_TESTES or 'tests'}/pf_{id_}_{nome}"
                    codigo, _saida, _ok = f._roda_pytest(Path(wt), alvo=rel)
                    if codigo == 0:
                        passaram.add(id_)
                passaram_por_trecho.append(passaram)
            finally:
                alvo.write_text(original, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return INCONCLUSIVO, {"causa": f"a reexecucao falhou: {e}"}
    finally:
        for id_, (_, nome) in testes.items():
            (destino_testes / f"pf_{id_}_{nome}").unlink(missing_ok=True)

    return classifica(passaram_por_trecho, set(testes))


# --------------------------------------------------------------- o disco
#
# 🚨 A prova roda no ORQUESTRADOR e grava aqui; o juiz e o comentario apenas
# LEEM. E' a disciplina no 2 do CLAUDE.md ("Juiz le do arquivo"): sem isso,
# reajustar o parecer passaria a subir container, e a propriedade de o juiz
# rodar em milissegundos sem rede -- que e' o que permite ajusta-lo trinta
# vezes -- morreria em troca de nada.

ARQUIVO = "fusao.json"


def grava(resultados: list[dict]) -> None:
    """`[{ids, veredito, detalhe}]` -> `fusao.json` da rodada."""
    import json
    from . import config as cfg
    (cfg.RODADA / ARQUIVO).write_text(
        json.dumps({"grupos": resultados}, indent=2, ensure_ascii=False),
        encoding="utf-8")


def do_disco() -> dict:
    """`{frozenset(ids): (veredito, detalhe)}`. Vazio quando nao houve prova.

    ⚠️ Ausente NAO e' erro: rodada sem Docker, projeto sem `codigo`, ou rodada
    anterior a esta mudanca. O consumidor cai na heuristica e DIZ que caiu.
    """
    import json
    from . import config as cfg
    try:
        d = json.loads((cfg.RODADA / ARQUIVO).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    fora = {}
    for g in d.get("grupos") or []:
        ids = frozenset(g.get("ids") or ())
        if ids:
            fora[ids] = (g.get("veredito") or INCONCLUSIVO, g.get("detalhe") or {})
    return fora


def aplica(grupos: list[list[dict]], resultados: dict
           ) -> list[tuple[list[dict], str, dict]]:
    """Os grupos da heuristica, refinados pela prova. `(grupo, veredito, detalhe)`.

    Grupo sem resultado medido sai como INCONCLUSIVO com a causa "nao medido" --
    e nao como provado. Silencio nunca vira prova.
    """
    fora = []
    for g in grupos:
        chave = frozenset(v.get("id") for v in g)
        veredito, detalhe = resultados.get(
            chave, (INCONCLUSIVO, {"causa": "a fusao nao foi medida nesta rodada"}))
        for pedaco in parte(g, veredito, detalhe):
            fora.append((pedaco, veredito, detalhe))
    return fora
