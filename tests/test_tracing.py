"""Tracing nunca pode derrubar a rodada.

Metade destes testes verifica que o modulo SOBREVIVE ao Langfuse quebrado --
essa e' a propriedade que importa as 14h15, nao a boniteza do trace.
"""
import pytest

from veredito import tracing


@pytest.fixture(autouse=True)
def _limpa():
    tracing._cliente_cache = None
    tracing._tentou = False
    yield
    tracing._cliente_cache = None
    tracing._tentou = False


# ------------------------------------------------- sobrevivencia (o que importa)

def test_rodada_funciona_sem_langfuse(monkeypatch):
    monkeypatch.setattr(tracing, "_cliente", lambda: None)
    with tracing.rodada("teste") as r:
        with r.etapa("promotores") as e:
            e.geracao("prd", "modelo", "entrada", object())
            e.ferramenta("run_tests", "arg", "saida")
            e.evento("qualquer", chave="valor")
        assert r.url is None


def test_cliente_que_explode_na_criacao_nao_derruba(monkeypatch):
    class Explode:
        def trace(self, **kw):
            raise RuntimeError("langfuse fora")

        def flush(self):
            raise RuntimeError("flush fora")

    monkeypatch.setattr(tracing, "_cliente", lambda: Explode())
    with tracing.rodada("teste") as r:
        with r.etapa("etapa") as e:
            e.geracao("g", "m", "i", object())
    # chegou aqui = nao derrubou


def test_span_que_explode_no_end_nao_derruba(monkeypatch):
    class SpanRuim:
        def generation(self, **kw):
            raise RuntimeError("nao")

        def span(self, **kw):
            raise RuntimeError("nao")

        def event(self, **kw):
            raise RuntimeError("nao")

        def end(self, **kw):
            raise RuntimeError("nao")

    class TraceRuim:
        def span(self, **kw):
            return SpanRuim()

        def get_trace_url(self):
            raise RuntimeError("nao")

    monkeypatch.setattr(tracing, "_cliente", lambda: type("C", (), {
        "trace": lambda self, **kw: TraceRuim(), "flush": lambda self: None})())
    with tracing.rodada("teste") as r:
        with r.etapa("etapa") as e:
            e.geracao("g", "m", "i", object())
            e.ferramenta("t", "i", "o")
            e.evento("ev")


def test_excecao_da_rodada_propaga(monkeypatch):
    """Erro real do orquestrador nao pode ser engolido pelo tracing."""
    monkeypatch.setattr(tracing, "_cliente", lambda: None)
    with pytest.raises(ValueError, match="erro de verdade"):
        with tracing.rodada("teste") as r:
            with r.etapa("etapa"):
                raise ValueError("erro de verdade")


# ------------------------------------------------------------------- extracao

class _RespComCache:
    class usage:
        input_tokens, output_tokens = 100, 20
        cache_read_input_tokens, cache_creation_input_tokens = 900, 50


def test_usage_so_tem_as_chaves_que_o_langfuse_aceita():
    """v2 descarta chave extra EM SILENCIO -- cache aqui dentro sumiria."""
    assert tracing._usage(_RespComCache()) == {"input": 100, "output": 20, "total": 120}


def test_cache_sai_separado_para_metadata():
    assert tracing._cache(_RespComCache()) == {"cache_read": 900, "cache_creation": 50}


def test_usage_sem_cache_nao_inventa_campo():
    class U:
        input_tokens, output_tokens = 5, 5

    class R:
        usage = U()

    assert tracing._usage(R())["total"] == 10
    assert tracing._cache(R()) == {}


def test_cache_de_objeto_sem_usage_e_vazio():
    assert tracing._cache(object()) == {}


def test_usage_de_objeto_sem_usage_vira_none():
    assert tracing._usage(object()) is None


def test_texto_de_recusa_nao_estoura():
    """stop_reason=refusal vem com content vazio -- IndexError classico."""
    class R:
        stop_reason = "refusal"
        content = []

    assert "refusal" in tracing._texto(R())


def test_texto_normal():
    class B:
        type, text = "text", "oi"

    class R:
        stop_reason = "end_turn"
        content = [B()]

    assert tracing._texto(R()) == "oi"


def test_texto_so_com_tool_use_nao_estoura():
    class B:
        type = "tool_use"

    class R:
        stop_reason = "tool_use"
        content = [B()]

    assert "sem texto" in tracing._texto(R())


# --------------------------------------------------------- integracao de verdade

def test_langfuse_real_se_estiver_no_ar():
    """Nao falha se o Langfuse estiver fora -- so pula."""
    if not tracing.disponivel():
        pytest.skip("Langfuse fora do ar")
    with tracing.rodada("teste_de_fumaca", origem="pytest") as r:
        assert r.url and r.url.startswith("http"), f"url invalida: {r.url}"
        with r.etapa("etapa_de_teste") as e:
            e.evento("ping")
        print(f"\n  trace: {r.url}")
