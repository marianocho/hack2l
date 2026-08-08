"""Langfuse: o trace do nosso agente, que e' material de submissao.

`starter-kit/README.md` dos organizadores, verbatim:

    "Submitting a trace link is the cleanest way to prove your multi-agent
    flow actually ran."

## 🚨 A regra numero um deste modulo

**Instrumentacao NUNCA derruba a rodada.** Toda operacao engole excecao e vira
no-op. Se o Langfuse estiver fora as 14h15, a rodada final continua e o parecer
sai -- so nao ha link. Tracing que quebra a rodada e' pior que tracing nenhum.

Por isso nao ha `raise` em lugar nenhum aqui, e por isso o `auth_check` roda com
timeout curto e uma vez so.

## Uso, do lado do orquestrador (uma linha por etapa)

    from veredito import tracing

    with tracing.rodada("veredito", top_n=10, pr=cfg.PR_BRANCH) as r:

        with r.etapa("promotores") as e:
            for nome, prompt in promotores:
                resp = cliente.messages.create(...)
                e.geracao(nome, cfg.MODEL_PROMOTOR, prompt, resp)

        for acusacao in top_n:
            with r.etapa(f"advogado/{acusacao['id']}", entrada=acusacao) as e:
                for msg in runner:
                    e.geracao("volta", cfg.MODEL_ADVOGADO, None, msg)

        with r.etapa("juiz") as e:
            e.geracao("sintese", cfg.MODEL_JUIZ, entrada, resp)

    print(r.url)   # tambem gravado em saidas/trace.txt

SDK fixado em 2.57.0: o servidor do desafio e' a imagem langfuse/langfuse:2 e a
v4 do SDK nao conversa com ele.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime

from . import config as cfg

_cliente_cache: object | None = None
_tentou = False


def _cliente():
    """Cliente Langfuse, ou None. Tenta uma vez so; nunca levanta."""
    global _cliente_cache, _tentou
    if _tentou:
        return _cliente_cache
    _tentou = True
    try:
        from langfuse import Langfuse

        pk = os.environ.get("LANGFUSE_PUBLIC_KEY")
        sk = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST")
        if not (pk and sk and host):
            return None
        c = Langfuse(public_key=pk, secret_key=sk, host=host, timeout=10)
        if not c.auth_check():
            return None
        _cliente_cache = c
    except Exception:
        _cliente_cache = None
    return _cliente_cache


def disponivel() -> bool:
    return _cliente() is not None


def _usage(resposta) -> dict | None:
    """Usage no formato que o Langfuse v2 ACEITA. Nunca levanta.

    ⚠️ So `input`, `output` e `total` sobrevivem aqui. O schema do v2 descarta
    chave extra EM SILENCIO -- descoberto em 08/08 mandando cache_read por este
    caminho e nao encontrando nada no trace depois. Cache vai por metadata.
    """
    try:
        u = resposta.usage
        entrada = getattr(u, "input_tokens", 0)
        saida = getattr(u, "output_tokens", 0)
        return {"input": entrada, "output": saida, "total": entrada + saida}
    except Exception:
        return None


def _cache(resposta) -> dict:
    """Numeros de cache, para metadata (onde chave arbitraria sobrevive).

    E' o numero da disciplina no 4: os promotores compartilham o diff como
    prefixo, entao `cache_read` alto e' o que mantem o TOP_N alto.
    """
    try:
        u = resposta.usage
        d = {}
        for origem, destino in (("cache_read_input_tokens", "cache_read"),
                                ("cache_creation_input_tokens", "cache_creation")):
            v = getattr(u, origem, None)
            if v is not None:
                d[destino] = v
        return d
    except Exception:
        return {}


def _texto(resposta) -> str:
    """Texto de uma Message, sem estourar em recusa (content vazio)."""
    try:
        if getattr(resposta, "stop_reason", None) == "refusal":
            return "<refusal: content vazio>"
        partes = [b.text for b in resposta.content if getattr(b, "type", None) == "text"]
        return "\n".join(partes) if partes else f"<sem texto: {resposta.content!r}>"
    except Exception:
        return str(resposta)[:2000]


class _Etapa:
    """Um span. Todos os metodos sao no-op silencioso se o span nao existir."""

    def __init__(self, span):
        self._span = span

    def geracao(self, nome: str, modelo: str, entrada, resposta) -> None:
        """Registra uma chamada de modelo, com usage e cache."""
        if self._span is None:
            return
        try:
            g = self._span.generation(
                name=nome, model=modelo, input=entrada,
                usage=_usage(resposta),
                metadata={"stop_reason": getattr(resposta, "stop_reason", None),
                          **_cache(resposta)},
            )
            g.end(output=_texto(resposta))
        except Exception:
            pass

    def ferramenta(self, nome: str, entrada, saida) -> None:
        """Registra uma chamada de ferramenta do advogado."""
        if self._span is None:
            return
        try:
            self._span.span(name=f"tool/{nome}", input=entrada).end(output=saida)
        except Exception:
            pass

    def evento(self, nome: str, **dados) -> None:
        if self._span is None:
            return
        try:
            self._span.event(name=nome, metadata=dados)
        except Exception:
            pass


class _Rodada:
    def __init__(self, trace):
        self._trace = trace
        self.url: str | None = None
        try:
            if trace is not None:
                self.url = trace.get_trace_url()
        except Exception:
            self.url = None

    @contextmanager
    def etapa(self, nome: str, entrada=None):
        span = None
        try:
            if self._trace is not None:
                span = self._trace.span(name=nome, input=entrada)
        except Exception:
            span = None
        e = _Etapa(span)
        try:
            yield e
        except Exception as exc:
            try:
                if span is not None:
                    span.end(output=f"EXCECAO: {type(exc).__name__}: {exc}",
                             level="ERROR", status_message=str(exc))
            except Exception:
                pass
            raise  # a excecao da rodada e' da rodada, nao nossa para engolir
        else:
            try:
                if span is not None:
                    span.end()
            except Exception:
                pass


@contextmanager
def rodada(nome: str = "veredito", **metadata):
    """Abre um trace para a rodada inteira. Sempre entrega um _Rodada usavel.

    Se o Langfuse estiver fora, devolve um _Rodada no-op com url None -- a
    rodada segue normalmente.
    """
    c = _cliente()
    trace = None
    if c is not None:
        try:
            trace = c.trace(
                name=nome,
                metadata={**metadata, "inicio": datetime.now().isoformat(timespec="seconds")},
                tags=["hack2l", "veredito"],
            )
        except Exception:
            trace = None

    r = _Rodada(trace)
    _grava_url(r.url)
    try:
        yield r
    finally:
        # flush e' obrigatorio: o SDK envia em lote e o processo pode morrer
        # logo depois do parecer, levando o trace junto.
        try:
            if c is not None:
                c.flush()
        except Exception:
            pass


def _grava_url(url: str | None) -> None:
    """Guarda o link em disco. O console rola; o arquivo fica."""
    if not url:
        return
    try:
        cfg.SAIDAS.mkdir(parents=True, exist_ok=True)
        (cfg.SAIDAS / "trace.txt").write_text(
            f"{datetime.now().isoformat(timespec='seconds')}  {url}\n",
            encoding="utf-8",
        )
    except Exception:
        pass
