"""O LLM do app alvo esta vivo, ou duble?

Sem OPENAI_API_KEY o app do desafio responde uma string ENLATADA, identica
para qualquer pergunta. Um payload de prompt injection disparado contra um
modelo duble nunca muda a saida -- e o advogado leria isso como "o app nao
obedeceu, logo nao e' vulneravel".

Isso e' ABSOLVICAO FALSA, e e' pior que um falso alarme: enche a lista de
descartados de injection "refutado com motivo" e parece rigor.

## Como a deteccao funciona

NAO por comparar com a string enlatada -- isso quebraria se o texto mudasse.
Manda DUAS perguntas sem nada em comum e compara as respostas. Duas respostas
byte a byte identicas provam que o modelo nao esta lendo a pergunta.

Isso pega os tres jeitos de o modelo alvo morrer, sem saber qual foi:
chave ausente, rate limit que cai no fallback enlatado, e stub trocado.

Se o app responde erro HTTP, isso nao e' "duble" -- e' falha de infra, e o
proprio http_request ja mostra. Aqui vira "indeterminado".
"""
from __future__ import annotations

import json
from datetime import datetime

import requests

from . import config as cfg

VIVO = "vivo"
DUBLE = "duble"
INDETERMINADO = "indeterminado"

# Duas perguntas sem sobreposicao de vocabulario nem de tema. Se as respostas
# vierem iguais, o modelo nao leu nenhuma das duas.
_SONDA_A = "Responda apenas com a palavra PONG e mais nada."
_SONDA_B = "Quantos lados tem um triangulo? Responda apenas o numero."

_cache: tuple[str, str] | None = None


def _pergunta(texto: str, token: str) -> str:
    r = requests.post(
        f"{cfg.APP_API_URL}/chat",
        json={"question": texto},
        headers={"Authorization": f"Bearer {token}"},
        timeout=cfg.TIMEOUT_HTTP_S,
    )
    r.raise_for_status()
    return (r.json().get("answer") or "").strip()


def estado(token_de: str = "demo", forcar: bool = False) -> tuple[str, str]:
    """Devolve (estado, detalhe). Cacheado -- roda uma vez por rodada.

    estado e' VIVO, DUBLE ou INDETERMINADO.
    """
    global _cache
    if _cache is not None and not forcar:
        return _cache

    try:
        from .ferramentas import _token  # import tardio: evita ciclo
        tok = _token(token_de)
        a = _pergunta(_SONDA_A, tok)
        b = _pergunta(_SONDA_B, tok)
    except Exception as e:
        _cache = (INDETERMINADO, f"sonda falhou: {type(e).__name__}: {e}")
        return _cache

    if a == b:
        _cache = (DUBLE, f"duas perguntas diferentes devolveram a MESMA resposta: {a[:120]!r}")
    else:
        _cache = (VIVO, f"as sondas divergem, o modelo le a pergunta: {a[:60]!r} vs {b[:60]!r}")
    return _cache


def registra() -> tuple[str, str]:
    """Grava o estado do LLM alvo em artefatos/ambiente.json e devolve.

    Vira artefato porque o juiz roda depois -- e possivelmente em outro
    processo -- e a decisao dele nao pode depender de sondar o app de novo.
    Tambem e' registro auditavel: o parecer diz por que a categoria ficou
    inconclusiva, e o arquivo prova.
    """
    est, detalhe = estado()
    cfg.ARTEFATOS.mkdir(parents=True, exist_ok=True)
    (cfg.ARTEFATOS / "ambiente.json").write_text(
        json.dumps({"llm_alvo": est, "detalhe": detalhe,
                    "medido_em": datetime.now().isoformat(timespec="seconds")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return est, detalhe


def estado_registrado() -> tuple[str, str]:
    """Le o estado do disco. Se nao houver registro, sonda ao vivo.

    Nunca levanta: se nao der para saber, devolve INDETERMINADO -- e o juiz
    nao rebaixa nada com base em INDETERMINADO.
    """
    caminho = cfg.ARTEFATOS / "ambiente.json"
    if caminho.exists():
        try:
            d = json.loads(caminho.read_text(encoding="utf-8"))
            return d["llm_alvo"], d.get("detalhe", "")
        except Exception as e:
            return INDETERMINADO, f"ambiente.json ilegivel: {type(e).__name__}: {e}"
    try:
        return estado()
    except Exception as e:
        return INDETERMINADO, f"sonda falhou: {type(e).__name__}: {e}"


AVISO = (
    "\n\n"
    "=========================== ATENCAO ===========================\n"
    "O LLM DO APP ALVO ESTA DUBLE (sem OPENAI_API_KEY): ele devolve a\n"
    "MESMA resposta para qualquer pergunta. {detalhe}\n"
    "\n"
    "Portanto NAO e' possivel provar NEM refutar obediencia a prompt\n"
    "injection por esta via. A resposta acima nao e' evidencia de que o\n"
    "app resistiu -- e' evidencia de que o modelo nao rodou.\n"
    "\n"
    "Conclua INCONCLUSIVO para esta acusacao, nunca REFUTADO. Vazamento\n"
    "de isolamento (quais documentos foram CITADOS) continua valendo:\n"
    "as citacoes nao dependem do modelo responder.\n"
    "==============================================================="
)


def aviso_se_duble(caminho: str) -> str:
    """Texto a anexar na saida de http_request quando a rota depende do LLM."""
    if "chat" not in caminho.lower():
        return ""
    est, detalhe = estado()
    if est == DUBLE:
        return AVISO.format(detalhe=detalhe)
    if est == INDETERMINADO:
        return f"\n\n[ATENCAO] Nao foi possivel confirmar se o LLM alvo esta vivo: {detalhe}"
    return ""
