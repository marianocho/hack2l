"""Acusacao: o engine seria construido ANTES do redirecionamento para kb_test,
ficando com a URL original (banco da aplicacao 'kb').

Invariante testada (vale no base e deve valer no head): o engine que o fixture
clean_db usa para dropar o schema nunca aponta para o banco da aplicacao 'kb',
e o modulo app.db (que constroi o engine no import) so e' importado depois de
qualquer manipulacao de DATABASE_URL feita pelo conftest. Teste read-only.
"""
import inspect
import re

import app.db as appdb
import tests.conftest as conftest


def test_engine_nao_aponta_para_o_banco_da_aplicacao():
    assert appdb.engine.url.database != "kb", (
        f"engine aponta para {appdb.engine.url.database!r}, o banco da aplicacao"
    )


def test_engine_e_construido_no_import_de_app_db():
    src = inspect.getsource(appdb)
    assert re.search(r"^engine\s*=\s*create_engine\(", src, re.M), src


def test_import_de_app_db_vem_depois_de_qualquer_mexida_em_database_url():
    """Ordem estatica no arquivo conftest.py: qualquer escrita em
    os.environ[...DATABASE_URL...] tem de aparecer antes da linha que importa
    app.db (momento em que o engine passa a existir)."""
    src = inspect.getsource(conftest)
    lines = src.splitlines()

    import_line = next(
        (i for i, l in enumerate(lines) if re.match(r"\s*from app\.db import", l)), None
    )
    assert import_line is not None, "conftest nao importa app.db"

    writes = [i for i, l in enumerate(lines) if re.search(r"os\.environ\[[^\]]*DATABASE_URL", l)]
    calls = [
        i
        for i, l in enumerate(lines)
        if re.match(r"\s*_redirect_to_test_database\(\)", l)
    ]

    for i in writes + calls:
        assert i < import_line, (
            f"linha {i + 1} ({lines[i].strip()!r}) mexe em DATABASE_URL depois do "
            f"import de app.db na linha {import_line + 1}: o engine ja teria sido "
            f"criado com a URL antiga"
        )
