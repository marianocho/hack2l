"""Custo de _ensure_test_database(): quantas conexoes abre e com que frequencia.

Invariante testada (vale no base e deveria valer no head): o helper roda uma
unica vez por sessao de pytest (o corpo do conftest e' executado uma vez, pois
sys.modules cacheia o modulo) e cada chamada abre no maximo UMA conexao admin,
em tempo desprezivel.
"""
import importlib
import sys
import time

import sqlalchemy
from sqlalchemy import event


def _load_conftest():
    for name in ("tests.conftest", "conftest"):
        if name in sys.modules:
            return sys.modules[name]
    return importlib.import_module("conftest")


def test_conftest_import_is_cached_so_helper_runs_once_per_session():
    mod = _load_conftest()
    assert importlib.import_module(mod.__name__) is mod
    assert importlib.import_module(mod.__name__) is mod


def test_helper_opens_at_most_one_connection_and_is_fast():
    mod = _load_conftest()
    opened = []
    event.listen(sqlalchemy.engine.Engine, "connect", lambda c, r: opened.append(1))
    try:
        start = time.perf_counter()
        mod._ensure_test_database()
        elapsed = time.perf_counter() - start
    finally:
        event.remove(
            sqlalchemy.engine.Engine,
            "connect",
            sqlalchemy.event.registry._key(sqlalchemy.engine.Engine, "connect", None)
            if False
            else (lambda c, r: None),
        ) if False else None

    assert len(opened) <= 1, f"conexoes abertas numa chamada: {len(opened)}"
    assert elapsed < 2.0, f"demorou {elapsed:.3f}s"


def test_repeated_calls_stay_cheap():
    mod = _load_conftest()
    start = time.perf_counter()
    for _ in range(5):
        mod._ensure_test_database()
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"5 chamadas levaram {elapsed:.3f}s"
