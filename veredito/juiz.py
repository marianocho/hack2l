"""hack2l / Veredito -- o juiz, na parte que nao pode ser opiniao.

As regras deste modulo sao deterministicas de proposito. Regra escrita em prosa
nao acontece as 14h30 com 12 achados e video para gravar: vira codigo ou nao
existe. E' isto que impede o alarme critico errado mecanicamente, em vez de por
disciplina humana sob pressao.

A sintese em linguagem natural -- deduplicar, ordenar, redigir o conserto
sugerido -- e' uma chamada de modelo e mora fora daqui. O que esta aqui roda em
milissegundos, sem rede, e tem teste.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config as cfg

# CRITICA > ALTA > MEDIA > BAIXA > SUSPEITA
ORDEM = {"CRITICA": 4, "ALTA": 3, "MEDIA": 2, "BAIXA": 1, "SUSPEITA": 0}
SEVERIDADES = list(ORDEM)


def _min_severidade(a: str, b: str) -> str:
    return a if ORDEM.get(a, 0) <= ORDEM.get(b, 0) else b


def aplica_regras(
    veredicto: dict,
    acusacao: dict,
    artefato: dict | None,
    avisos: list[str] | tuple[str, ...] = (),
) -> dict:
    """As regras determinísticas, em ordem. Devolve um veredicto novo.

    Cada rebaixamento fica registrado em `regras_aplicadas`, porque um parecer
    que rebaixa sem dizer por que e' tao opaco quanto um que nao rebaixa.
    """
    v = dict(veredicto)
    v.setdefault("severidade", "BAIXA")
    aplicadas: list[str] = []

    # REGRA 0 -- o artefato manda. Nao esta no documento original, mas a
    # arquitetura inteira depende disto: se o advogado afirma PROVADO e o exit
    # code diz que nao, quem ganha e' o exit code. Sem esta regra, "o LLM nao
    # pode sobrescrever o veredito" e' so uma intencao.
    if artefato is not None:
        if v.get("veredito") == "PROVADO" and artefato.get("estado") != "PROVADO":
            v["veredito"] = artefato.get("estado", "INCONCLUSIVO")
            v["motivo"] = artefato.get("motivo") or v.get("motivo")
            aplicadas.append(
                f"R0: o advogado disse PROVADO, o artefato disse {artefato.get('estado')}. "
                "Vale o artefato."
            )
        # prova ponta a ponta nao e' o advogado quem declara: e' fato do artefato
        v["prova_ponta_a_ponta"] = bool(veredicto.get("prova_ponta_a_ponta")) and (
            artefato.get("estado") == "PROVADO"
        )

    # REGRA 3b -- absolvicao falsa por app alvo sem modelo.
    #
    # O advogado recebe um aviso em texto quando isso acontece, mas aviso em
    # texto e' conselho: o modelo pode ignorar e concluir "resistiu ao ataque".
    # Aqui e' mecanico. Sem OPENAI_API_KEY o app devolve a mesma string para
    # qualquer pergunta, entao "o modelo nao obedeceu" nao e' observacao, e'
    # ausencia de observacao -- e ausencia de observacao nao refuta nada.
    if cfg.AVISO_SEM_MODELO in avisos and v.get("veredito") == "REFUTADO":
        v["veredito"] = "INCONCLUSIVO"
        v["severidade"] = "SUSPEITA"
        v["motivo"] = (
            "o app alvo estava sem OPENAI_API_KEY: a resposta e' enlatada e identica "
            "para qualquer pergunta, entao nao da para provar NEM refutar obediencia "
            "a injection. Nao e' refutacao, e' ausencia de observacao."
        )
        aplicadas.append("R3b: app alvo sem modelo -> REFUTADO vira INCONCLUSIVO")
        v["regras_aplicadas"] = aplicadas
        return v

    # REGRA 3 (antes das de severidade: execucao falha encerra o assunto)
    if v.get("veredito") == "INCONCLUSIVO" or (artefato or {}).get("erro"):
        v["veredito"] = "INCONCLUSIVO"
        v["severidade"] = "SUSPEITA"
        if not v.get("motivo"):
            v["motivo"] = (artefato or {}).get("erro") or "execucao falhou sem causa registrada"
        aplicadas.append("R3: execucao falhou -> INCONCLUSIVO, nunca absolvido")
        v["regras_aplicadas"] = aplicadas
        return v

    # REGRA 1 -- critica sem arbitro citado e' opiniao com teste em anexo
    if v["severidade"] == "CRITICA" and not acusacao.get("arbitro"):
        v["severidade"] = "SUSPEITA"
        aplicadas.append("R1: CRITICA sem arbitro citado -> SUSPEITA")

    # REGRA 2 -- so prova ponta a ponta sustenta severidade alta
    if not v.get("prova_ponta_a_ponta"):
        antes = v["severidade"]
        v["severidade"] = _min_severidade(antes, "MEDIA")
        if v["severidade"] != antes:
            aplicadas.append(f"R2: prova nao e' ponta a ponta -> {antes} rebaixada para MEDIA")

    v["regras_aplicadas"] = aplicadas
    return v


def organiza(
    veredictos: list[dict], acusacoes: dict, artefatos: dict, avisos: dict | None = None
) -> dict:
    """Separa nas tres listas do parecer. Nada e' descartado em silencio."""
    avisos = avisos or {}
    condenados, descartados, inconclusivos = [], [], []
    for v in veredictos:
        id_ = v.get("id", "sem_id")
        final = aplica_regras(
            v, acusacoes.get(id_, {}), artefatos.get(id_), avisos.get(id_, ())
        )
        final["id"] = id_
        destino = {
            "PROVADO": condenados,
            "SUSPEITA": condenados,  # suspeita fundamentada entra rotulada
            "REFUTADO": descartados,
        }.get(final.get("veredito"), inconclusivos)
        destino.append(final)

    condenados.sort(key=lambda x: -ORDEM.get(x.get("severidade", "BAIXA"), 0))
    return {
        "condenados": condenados,
        "descartados": descartados,
        "inconclusivos": inconclusivos,
    }


# ------------------------------------------------------------------- o parecer

def _bloco(v: dict, acusacao: dict, artefato: dict | None) -> str:
    linhas = [
        f"[{v.get('severidade','?')}] [{acusacao.get('confianca','?')}] "
        f"{acusacao.get('categoria','?')} - {acusacao.get('local','?')}",
        f"O QUE: {acusacao.get('hipotese','-')}",
        f"ARBITRO: {acusacao.get('arbitro') or 'nenhum citado'}",
    ]
    if artefato and artefato.get("estado") == "PROVADO":
        linhas.append(
            f"EVIDENCIA: {artefato['arquivo_do_teste']} passa em {artefato['commit_base']} "
            f"e falha em {artefato['commit_head']} (exit {artefato['exit_base']} -> "
            f"{artefato['exit_head']}). Artefato: artefatos/prova_{artefato['id']}.json"
        )
    else:
        linhas.append(f"EVIDENCIA: nao fechou. {v.get('motivo') or 'sem motivo registrado'}")
    if v.get("conserto"):
        linhas.append(f"CONSERTO SUGERIDO: {v['conserto']}")
    if v.get("regras_aplicadas"):
        linhas.append("REGRAS: " + " | ".join(v["regras_aplicadas"]))
    return "\n".join(linhas)


def formata_parecer(organizado: dict, acusacoes: dict, artefatos: dict) -> str:
    """As duas ultimas listas sao a peca que nenhum outro time vai ter.

    Elas precisam ser enquadradas em voz alta no pitch, senao soam como
    confissao de erro em vez de interpretabilidade.
    """
    p: list[str] = ["# PARECER", ""]
    c, d, i = organizado["condenados"], organizado["descartados"], organizado["inconclusivos"]

    p += [
        f"{len(c)} com parecer, {len(d)} descartados com motivo, {len(i)} inconclusivos com causa.",
        "",
        "## CONDENADOS", "",
    ]
    if not c:
        p.append("_nenhum achado sobreviveu a pericia._")
    for v in c:
        p += [_bloco(v, acusacoes.get(v["id"], {}), artefatos.get(v["id"])), ""]

    p += ["## DESCARTADOS, COM MOTIVO", ""]
    if not d:
        p.append("_nenhum._")
    for v in d:
        a = acusacoes.get(v["id"], {})
        p.append(f"- {a.get('categoria','?')} em {a.get('local','?')}: {v.get('motivo','-')}")

    p += ["", "## INCONCLUSIVOS, COM CAUSA", ""]
    if not i:
        p.append("_nenhum._")
    for v in i:
        a = acusacoes.get(v["id"], {})
        p.append(f"- {a.get('categoria','?')} em {a.get('local','?')}: {v.get('motivo','-')}")

    return "\n".join(p) + "\n"


# ------------------------------------------------------------------- carga

def _carrega_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return padrao


def carrega_do_disco() -> tuple[list[dict], dict, dict, dict]:
    """Le o que as outras etapas gravaram.

    Ajustar o juiz pela trigesima vez nao pode re-executar o advogado -- meia
    hora de disciplina que se paga dez vezes.
    """
    veredictos = _carrega_json(cfg.SAIDAS / "veredictos.json", [])
    acusacoes = {a["id"]: a for a in _carrega_json(cfg.SAIDAS / "acusacoes.json", []) if "id" in a}
    artefatos = {}
    if cfg.ARTEFATOS.is_dir():
        for f in cfg.ARTEFATOS.glob("prova_*.json"):
            art = _carrega_json(f, None)
            if art and "id" in art:
                artefatos[art["id"]] = art
    avisos = _carrega_json(cfg.ARTEFATOS / "avisos.json", {})
    return veredictos, acusacoes, artefatos, avisos


def sentencia() -> str:
    veredictos, acusacoes, artefatos, avisos = carrega_do_disco()
    organizado = organiza(veredictos, acusacoes, artefatos, avisos)
    texto = formata_parecer(organizado, acusacoes, artefatos)
    cfg.prepara_pastas()
    (cfg.SAIDAS / "parecer.md").write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    print(sentencia())
