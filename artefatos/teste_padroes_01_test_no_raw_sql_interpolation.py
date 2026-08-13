"""Invariante do projeto (docs/REFERENCE_GUIDE.md): persistencia passa pelo ORM;
nao ha SQL cru interpolado com valores de request nos routers.

Passa no base (todos os routers usam select()/db.get()) e deve continuar passando.
"""
import pathlib
import re

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"

# text("...") ou text(f"...") contendo SELECT/INSERT/UPDATE/DELETE com f-string
FSTRING_SQL = re.compile(r"text\(\s*f[\"']", re.IGNORECASE)


def _router_files():
    files = sorted(ROUTERS.glob("*.py"))
    assert files, f"nao achei routers em {ROUTERS}"
    return files


def test_no_fstring_sql_in_routers():
    offenders = []
    for path in _router_files():
        source = path.read_text()
        for lineno, line in enumerate(source.splitlines(), start=1):
            if FSTRING_SQL.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "SQL cru interpolado (f-string) em routers:\n" + "\n".join(offenders)


def test_user_lookup_by_email_uses_orm():
    """Busca de usuario por email deve usar o ORM, nao SELECT em string."""
    offenders = []
    for path in _router_files():
        source = path.read_text()
        for lineno, line in enumerate(source.splitlines(), start=1):
            if re.search(r"SELECT\s+.*\s+FROM\s+users", line, re.IGNORECASE):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "SELECT cru na tabela users:\n" + "\n".join(offenders)
