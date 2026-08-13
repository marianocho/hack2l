"""Testa a INVARIANTE alegada pela acusacao, sem abrir nenhuma conexao com o banco
da aplicacao: (a) o redirecionamento de DATABASE_URL acontece ANTES de o app
construir o engine, e (b) o engine efetivamente em uso nunca aponta para o banco
da aplicacao.

Nada e' escrito, e nenhuma URL do banco da aplicacao e' usada para conectar: a
string e' apenas montada em memoria e passada para a funcao pura de reescrita.
"""
import importlib.util
import inspect
import os
import sys

import pytest

from app.db import engine

CONFTEST_PATH = os.path.join(os.path.dirname(__file__), "conftest.py")


def _conftest_module():
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if f and os.path.abspath(f) == os.path.abspath(CONFTEST_PATH):
            return mod
    spec = importlib.util.spec_from_file_location("cft_probe", CONFTEST_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_engine_em_uso_nao_e_o_banco_da_aplicacao():
    assert engine.url.database != "kb", f"suite rodando contra o banco do app: {engine.url}"


def test_redirect_reescreve_url_do_app_para_kb_test(monkeypatch):
    mod = _conftest_module()
    fn = getattr(mod, "_redirect_to_test_database", None)
    if fn is None:
        pytest.skip("commit sem _redirect_to_test_database (base)")

    # URL de app montada em memoria a partir da URL de teste: nunca conectamos com ela.
    app_url = engine.url.set(database="kb").render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", app_url)

    fn()

    depois = os.environ["DATABASE_URL"]
    assert depois.rsplit("/", 1)[-1] == "kb_test", f"nao redirecionou: {depois}"


def test_redirect_roda_antes_do_import_que_cria_o_engine():
    """Ordem no arquivo: a chamada do redirect precede `from app.db import ...`,
    que e' onde create_engine le a env var. Se a ordem fosse inversa, o engine
    nasceria apontando para o banco da aplicacao."""
    mod = _conftest_module()
    if getattr(mod, "_redirect_to_test_database", None) is None:
        pytest.skip("commit sem _redirect_to_test_database (base)")

    src = inspect.getsource(mod).splitlines()
    chamada = next(i for i, l in enumerate(src) if l.strip() == "_redirect_to_test_database()")
    import_db = next(i for i, l in enumerate(src) if l.strip().startswith("from app.db import"))
    assert chamada < import_db, "o redirect roda depois do import que cria o engine"
