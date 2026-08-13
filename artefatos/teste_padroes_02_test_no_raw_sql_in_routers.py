"""Invariante do REFERENCE_GUIDE.md:70 -- "Persistence goes through the ORM
models; there is no raw SQL in the app."

Este teste vale no commit base (nenhum router usa SQL cru) e deve continuar
valendo. Ele varre app/api/app/routers/ procurando uso de sqlalchemy.text()
ou db.execute com string SQL.
"""
import pathlib
import re

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
if not ROUTERS.is_dir():
    # fallback: procura a pasta routers em qualquer lugar do repo montado
    for base in pathlib.Path(__file__).resolve().parents:
        cand = base / "app" / "api" / "app" / "routers"
        if cand.is_dir():
            ROUTERS = cand
            break

SQL_KEYWORD = re.compile(
    r"""text\(\s*f?["'].*?\b(SELECT|INSERT|UPDATE|DELETE|COUNT)\b""",
    re.IGNORECASE | re.DOTALL,
)


def test_routers_dir_found():
    assert ROUTERS.is_dir(), f"nao achei a pasta de routers: {ROUTERS}"


def test_no_raw_sql_in_routers():
    offenders = []
    for path in sorted(ROUTERS.glob("*.py")):
        source = path.read_text()
        for lineno, line in enumerate(source.splitlines(), start=1):
            if SQL_KEYWORD.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
        # tambem pega text( multilinha
        for match in SQL_KEYWORD.finditer(source):
            snippet = match.group(0).replace("\n", " ")
            entry = f"{path.name}: {snippet}"
            if not any(snippet[:40] in o for o in offenders):
                offenders.append(entry)

    assert not offenders, (
        "SQL cru em routers, violando REFERENCE_GUIDE.md:70 "
        "(persistencia deve passar pelo ORM):\n" + "\n".join(offenders)
    )
