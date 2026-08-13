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

from . import arbitro
from . import config as cfg
from . import llm_alvo

# CRITICA > ALTA > MEDIA > BAIXA > SUSPEITA
ORDEM = {"CRITICA": 4, "ALTA": 3, "MEDIA": 2, "BAIXA": 1, "SUSPEITA": 0}
SEVERIDADES = list(ORDEM)

# Categorias cuja REFUTACAO depende de o LLM do app alvo ter realmente rodado.
#
# So injection. Vazamento de contexto fica de fora de proposito: prova-se por
# quais documentos foram CITADOS, e citacao nao depende do modelo responder --
# entao um REFUTADO ali continua legitimo com o modelo duble. Incluir vazamento
# aqui incharia a lista de inconclusivos com descartes validos, e uma lista de
# inconclusivos inflada enfraquece o parecer tanto quanto uma vazia.
_DEPENDEM_DO_LLM = {"injection"}


def _min_severidade(a: str, b: str) -> str:
    return a if ORDEM.get(a, 0) <= ORDEM.get(b, 0) else b


def aplica_regras(
    veredicto: dict,
    acusacao: dict,
    artefato: dict | None,
    avisos: list[str] | tuple[str, ...] = (),
    artefato_http: dict | None = None,
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
    # REGRA 0b -- prova ponta a ponta e' FATO DO ARTEFATO, sempre.
    #
    # 🚨 Isto morava DENTRO do `if artefato is not None` acima, e era o furo mais
    # caro do juiz. Prova por `http_request` nao gera artefato de teste
    # diferencial, entao numa acusacao provada pela API o bloco inteiro era
    # pulado e a auto-declaracao do advogado passava sem conferencia -- justo na
    # unica via que, pelo CONTRATO, sustenta severidade alta. Ou seja: a regra
    # que existe para o LLM nao sobrescrever o exit code so' rodava quando havia
    # exit code, e ficava muda exatamente onde nao havia.
    #
    # Morde neste PR em especial: ele adiciona tres endpoints NOVOS, onde prova
    # diferencial nao fecha (404 no base e' o inverso do padrao), entao os
    # achados especificos do PR chegam aqui so' com prova por API.
    #
    # AND deliberado: o modelo alega, o artefato corrobora. Sem artefato http com
    # chamada completada, e' falso -- independente do que ele declarou.
    v["prova_ponta_a_ponta"] = bool(veredicto.get("prova_ponta_a_ponta")) and bool(
        (artefato_http or {}).get("alcancou_a_api")
    )

    # REGRA 4 -- absolvicao falsa por LLM alvo duble.
    #
    # R3 nao pega este caso: nada falhou. Os exit codes estao limpos, `erro` e'
    # None. O que aconteceu e' que o app alvo respondeu a string enlatada (sem
    # OPENAI_API_KEY, ou rate limit), entao o payload de injection nao tinha
    # como surtir efeito -- e "nao surtiu efeito" foi lido como "o app resistiu".
    # Sem esta regra a decisao depende do advogado ter obedecido um aviso em
    # texto, ou seja, PASSA PELO MODELO. Aqui ela e' mecanica.
    #
    # DOIS SINAIS, porque cada um sozinho tem um buraco:
    #
    #   por acusacao  -- a ferramenta gravou que ESTA acusacao viu resposta
    #                    duble. Pega qualquer categoria que tenha sondado o
    #                    chat, nao so as rotuladas 'injection'.
    #   por rodada    -- o llm_alvo mediu a rodada inteira como DUBLE. Pega o
    #                    caso de o advogado ter concluido sem deixar rastro na
    #                    ferramenta.
    #
    # Disparar a mais custa um INCONCLUSIVO onde caberia REFUTADO, e o desafio
    # e' explicito: deixar passar defeito real e' pior que falso alarme.
    #
    # Escopo mantido estreito no resto: so quando REFUTADO. Um PROVADO com LLM
    # duble veio de outra via -- teste diferencial, isolamento -- e e' legitimo.
    if v.get("veredito") == "REFUTADO" and acusacao.get("categoria") in _DEPENDEM_DO_LLM:
        est, detalhe = llm_alvo.estado_registrado()
        por_acusacao = cfg.AVISO_SEM_MODELO in avisos
        por_rodada = est == llm_alvo.DUBLE
        if por_acusacao or por_rodada:
            origem = "observado nesta acusacao" if por_acusacao else "medido na rodada"
            v["veredito"] = "INCONCLUSIVO"
            v["severidade"] = "SUSPEITA"
            v["motivo"] = (
                f"LLM do app alvo esta duble ({origem}): responde o mesmo para "
                f"qualquer pergunta. {detalhe}. Nao e' possivel provar nem refutar "
                "obediencia a injection por esta via -- nao e' refutacao, e' "
                "ausencia de observacao."
            )
            aplicadas.append(
                "R4: REFUTADO com LLM alvo duble -> INCONCLUSIVO, nunca absolvido"
            )
            v["regras_aplicadas"] = aplicadas
            return v

    # REGRA 3b -- veredito com ZERO observacao nao e' veredito.
    #
    # 🚨 O caso real de 10/08: com a worktree corrompida, o advogado chamou
    # read_file/grep, TODA chamada voltou RuntimeError, e ele devolveu PROVADO
    # -- duas vezes -- escrevendo no proprio motivo que as ferramentas tinham
    # falhado. Ele sabia, e concluiu assim mesmo.
    #
    # A R3 nao pegava porque ela olha `artefato.erro`, e verificacao so estatica
    # nao gera artefato. Mesmo formato de furo da R0b, que morava dentro de
    # `if artefato is not None` e ficava muda justo onde nao havia artefato.
    #
    # Isto nao e' restricao nova, e' a regra central aplicada: "nao argumenta,
    # TESTA". Veredito sem nenhuma observacao e' opiniao de modelo -- o que o
    # produto existe para barrar. Vale nos dois sentidos: falsa condenacao
    # (PROVADO) e falsa absolvicao (REFUTADO) tem a mesma causa.
    #
    # ⚠️ AUSENTE nao e' ZERO. Rodada gravada antes de 11/08 nao tem o campo;
    # tratar ausencia como zero viraria todo reprocessamento em inconclusivo,
    # inventando um problema que nao houve.
    ok = v.get("ferramentas_ok")
    if ok == 0 and v.get("veredito") in ("PROVADO", "REFUTADO"):
        erros = v.get("ferramentas_erro") or 0
        antes = v["veredito"]
        v["veredito"] = "INCONCLUSIVO"
        v["severidade"] = "SUSPEITA"
        v["motivo"] = (
            f"nenhuma ferramenta funcionou ({erros} chamada(s) com erro), entao "
            f"nao houve observacao que sustentasse {antes}. "
            + (v.get("motivo") or "")
        ).strip()
        aplicadas.append(
            f"R3b: {antes} com zero ferramenta bem-sucedida -> INCONCLUSIVO"
        )
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

    # REGRA 1 -- CRITICA exige uma autoridade que NAO seja o modelo.
    #
    # Duas vias, e qualquer uma basta:
    #
    #   arbitro com procedencia  uma regra escrita NESTE repositorio foi
    #                            violada, e um humano pode ir conferir onde.
    #   prova ponta a ponta      a coisa ruim aconteceu de fora, contra o app
    #                            rodando, com artefato -- ja aterrado na R0b,
    #                            entao aqui e' fato do artefato, nao alegacao.
    #
    # A segunda via entrou em 10/08, junto com o desacoplamento do arbitro, e
    # nao e' afrouxamento: e' o conserto de um furo que a rodada premiada
    # exibiu em cima do palco. No parecer final do Hack2L, o MESMO SQL injection
    # apareceu duas vezes --
    #
    #   padroes_01   arbitro "C2"   -> CRITICA
    #   correcao_01  arbitro null   -> SUSPEITA
    #
    # -- e o correcao_01 tinha prova diferencial (passa no base, falha no head)
    # E artefato http. A severidade nao seguiu a forca da prova, seguiu o acaso
    # de uma lente ter recitado um rotulo chumbado que a outra nao recitou.
    # Depois de 09/08 sabemos que aquele rotulo nem existia no repositorio do
    # desafio: nos o inventamos. Sem a segunda via, o conserto do arbitro
    # tornaria SUSPEITA todo achado provado em todo repositorio que nao
    # documenta os proprios criterios -- ou seja, quase todos.
    #
    # O que continua barrado: opiniao de modelo sem nenhuma das duas. Que e' o
    # que a R1 sempre quis dizer.
    if v["severidade"] == "CRITICA":
        tem_regra = arbitro.tem_procedencia(acusacao.get("arbitro"))
        tem_prova = bool(v.get("prova_ponta_a_ponta"))
        if not tem_regra and not tem_prova:
            v["severidade"] = "SUSPEITA"
            motivo_r1 = (
                "sem arbitro com procedencia"
                if arbitro.citado(acusacao.get("arbitro"))
                else "sem arbitro citado"
            )
            aplicadas.append(
                f"R1: CRITICA {motivo_r1} e sem prova ponta a ponta -> SUSPEITA"
            )

    # REGRA 2 -- so prova ponta a ponta sustenta severidade alta
    if not v.get("prova_ponta_a_ponta"):
        antes = v["severidade"]
        v["severidade"] = _min_severidade(antes, "MEDIA")
        if v["severidade"] != antes:
            aplicadas.append(f"R2: prova nao e' ponta a ponta -> {antes} rebaixada para MEDIA")

    v["regras_aplicadas"] = aplicadas
    return v


def organiza(
    veredictos: list[dict], acusacoes: dict, artefatos: dict, avisos: dict | None = None,
    http: dict | None = None,
) -> dict:
    """Separa nas tres listas do parecer. Nada e' descartado em silencio."""
    avisos = avisos or {}
    http = http or {}
    condenados, descartados, inconclusivos = [], [], []
    for v in veredictos:
        id_ = v.get("id", "sem_id")
        final = aplica_regras(
            v, acusacoes.get(id_, {}), artefatos.get(id_), avisos.get(id_, ()),
            http.get(id_),
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

def _local(acusacao: dict) -> str:
    """O caminho como ele sai no parecer, com a raiz corrigida quando da.

    Import tardio de proposito: o juiz continua rodando sem git e sem o resto do
    pacote, que e' a propriedade que permite reajustar o parecer trinta vezes
    lendo so o disco.
    """
    bruto = acusacao.get("local") or "?"
    try:
        from .ferramentas import normaliza_local
    except ImportError:
        return bruto
    return normaliza_local(bruto)


def _evidencia_http(art: dict | None) -> str | None:
    """A linha de evidencia de uma prova contra o app rodando.

    O `REVIEW_TASK.md` aceita TRES vias -- teste que falha, **reproducao contra o
    app rodando**, e trace/log/estado do banco. So' a primeira virava linha de
    evidencia aqui; a segunda existia como ferramenta e sumia do parecer.

    Lista as chamadas que completaram, em ordem, nao so' a ultima.

    🚨 Medido na validacao das 13h30: com "cita a ultima" o parecer imprimia o
    404 do email de CONTROLE, enquanto a prova era o 201 do payload de injecao
    duas chamadas antes. O contraste E' a prova -- "com o payload deu 201, sem o
    payload deu 404" e' o que um humano precisa ver, e uma linha so' escolhia
    justamente a metade sem graca.

    Teto de 4 para o bloco nao virar dump; o artefato em disco tem tudo.
    """
    if not (art or {}).get("alcancou_a_api"):
        return None
    completas = [c for c in art["chamadas"] if c["status"] is not None and not c["erro"]]
    mostradas = completas[-4:]
    linhas = [
        f"  {c['metodo']} {c['caminho']} como {c['como']} -> HTTP {c['status']}"
        for c in mostradas
    ]
    omitidas = len(completas) - len(mostradas)
    if omitidas:
        linhas.insert(0, f"  (+{omitidas} chamada(s) antes, no artefato)")
    return (
        "EVIDENCIA: contra o app rodando --\n"
        + "\n".join(linhas)
        + f"\n  Artefato: artefatos/http_{art['id']}.json"
    )


# O desafio nomeia cinco categorias; nos usamos seis, mais granulares. Traduzir
# na saida mantem a granularidade interna e entrega ao jurado o rotulo dele --
# ler um nome que nao e' o seu e' atrito de graca no minuto do parecer.
_CATEGORIA_DO_DESAFIO = {
    "injection": "security",
    "vazamento_de_contexto": "security",
    "correcao": "correctness",
    "performance": "performance",
    "padroes": "convention or pattern",
    "prd": "PRD divergence",
}


def _bloco(v: dict, acusacao: dict, artefato: dict | None, http: dict | None = None) -> str:
    interna = acusacao.get("categoria", "?")
    rotulo = _CATEGORIA_DO_DESAFIO.get(interna, interna)
    linhas = [
        f"[{v.get('severidade','?')}] [{acusacao.get('confianca','?')}] "
        f"{rotulo} - {_local(acusacao)}",
        f"O QUE: {acusacao.get('hipotese','-')}",
        # Com procedencia a linha vira "a regra (arquivo:linha)", e o leitor do
        # parecer pode ir conferir. Era isso que "ARBITRO: AC2" nunca permitiu.
        f"ARBITRO: {arbitro.formata(acusacao.get('arbitro'))}",
    ]
    # Ferramenta deterministica e INDEPENDENTE apontou o mesmo lugar. E' sinal
    # de forca diferente de "duas lentes concordaram" -- as duas lentes sao o
    # mesmo modelo. Sem imprimir, o sinal morre em disco.
    #
    # ⚠️ Cita a ferramenta VERBATIM em vez de resumir. "Corroborado por bandit"
    # deixa o leitor supor que a ferramenta confirmou ESTE achado; o scanner
    # afirmou uma coisa especifica sobre aquela linha, e quem le tem que poder
    # julgar se aquilo sustenta este achado ou so' cai perto.
    for s in acusacao.get("_scanner", [])[:2]:
        linhas.append(
            f"CORROBORADO POR: {s.get('ferramenta', '?')} em {s.get('local', '?')} "
            f'-- "{str(s.get("texto") or "")[:110]}"'
        )
    linha_http = _evidencia_http(http)
    if artefato and artefato.get("estado") == "PROVADO":
        linhas.append(
            f"EVIDENCIA: {artefato['arquivo_do_teste']} passa em {artefato['commit_base']} "
            f"e falha em {artefato['commit_head']} (exit {artefato['exit_base']} -> "
            f"{artefato['exit_head']}). Artefato: artefatos/prova_{artefato['id']}.json"
        )
        # Causalidade e alcance sao provas diferentes, e as duas juntas valem
        # mais: o teste diz que foi esta mudanca, o HTTP diz que da' para fazer
        # agora, de fora.
        if linha_http:
            linhas.append(linha_http.replace("EVIDENCIA:", "E TAMBEM:", 1))
    elif linha_http:
        linhas.append(linha_http)
    else:
        linhas.append(f"EVIDENCIA: nao fechou. {v.get('motivo') or 'sem motivo registrado'}")
    if v.get("conserto"):
        linhas.append(f"CONSERTO SUGERIDO: {v['conserto']}")
    if v.get("regras_aplicadas"):
        linhas.append("REGRAS: " + " | ".join(v["regras_aplicadas"]))
    return "\n".join(linhas)


def formata_parecer(organizado: dict, acusacoes: dict, artefatos: dict,
                    http: dict | None = None) -> str:
    """As duas ultimas listas sao a peca que nenhum outro time vai ter.

    Elas precisam ser enquadradas em voz alta no pitch, senao soam como
    confissao de erro em vez de interpretabilidade.
    """
    http = http or {}
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
        p += [_bloco(v, acusacoes.get(v["id"], {}), artefatos.get(v["id"]),
                     http.get(v["id"])), ""]

    p += ["## DESCARTADOS, COM MOTIVO", ""]
    if not d:
        p.append("_nenhum._")
    for v in d:
        a = acusacoes.get(v["id"], {})
        rotulo = _CATEGORIA_DO_DESAFIO.get(a.get("categoria"), a.get("categoria", "?"))
        p.append(f"- {rotulo} em {_local(a)}: {v.get('motivo','-')}")

    p += ["", "## INCONCLUSIVOS, COM CAUSA", ""]
    if not i:
        p.append("_nenhum._")
    for v in i:
        a = acusacoes.get(v["id"], {})
        rotulo = _CATEGORIA_DO_DESAFIO.get(a.get("categoria"), a.get("categoria", "?"))
        p.append(f"- {rotulo} em {_local(a)}: {v.get('motivo','-')}")

    return "\n".join(p) + "\n"


# ------------------------------------------------------------------- carga

def _carrega_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return padrao


def _por_id(padrao: str) -> dict:
    artefatos = {}
    if cfg.ARTEFATOS.is_dir():
        for f in cfg.ARTEFATOS.glob(padrao):
            art = _carrega_json(f, None)
            if art and "id" in art:
                artefatos[art["id"]] = art
    return artefatos


def carrega_do_disco() -> tuple[list[dict], dict, dict, dict, dict]:
    """Le o que as outras etapas gravaram.

    Ajustar o juiz pela trigesima vez nao pode re-executar o advogado -- meia
    hora de disciplina que se paga dez vezes.
    """
    veredictos = _carrega_json(cfg.RODADA / "veredictos.json", [])
    acusacoes = {a["id"]: a for a in _carrega_json(cfg.RODADA / "acusacoes.json", []) if "id" in a}
    avisos = _carrega_json(cfg.ARTEFATOS / "avisos.json", {})
    # prova_* = teste diferencial (causalidade). http_* = app rodando (alcance).
    return veredictos, acusacoes, _por_id("prova_*.json"), avisos, _por_id("http_*.json")


def sentencia() -> str:
    veredictos, acusacoes, artefatos, avisos, http = carrega_do_disco()
    organizado = organiza(veredictos, acusacoes, artefatos, avisos, http)
    texto = formata_parecer(organizado, acusacoes, artefatos, http)
    cfg.prepara_pastas()
    (cfg.RODADA / "parecer.md").write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    print(sentencia())
