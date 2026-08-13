"""Invariante de convencao: persistencia passa pelo ORM; nao existe SQL cru
interpolado com f-string em nenhum router da API (docs/REFERENCE_GUIDE.md:70).

Passa no base (nenhum router usa text(f"...")) e falha no head (shares.py:31).
"""
import pathlib
import re

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"

# text(f"...  ou  execute(f"...  -> SQL montado por interpolacao de string
INTERPOLATED_SQL = re.compile(r"(text|execute)\s*\(\s*f[\"']", re.IGNORECASE)


def _router_files():
    base = ROUTERS if ROUTERS.is_dir() else pathlib.Path("app/api/app/routers")
    assert base.is_dir(), f"nao encontrei os routers em {base}"
    return sorted(base.glob("*.py"))


def test_routers_do_not_build_sql_by_string_interpolation():
    offenders = []
    for path in _router_files():
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if INTERPOLATED_SQL.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "SQL cru interpolado em routers:\n" + "\n".join(offenders)
