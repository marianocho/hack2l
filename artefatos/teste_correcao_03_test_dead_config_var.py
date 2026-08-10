"""Invariante: nenhum router le uma configuracao (os.getenv) para uma variavel
local e depois nunca a usa. Uma config lida e ignorada e' um limite que nao e'
aplicado -- codigo morto que aparenta enforcement.

Passa no base (nenhum router faz isso) e falha no head (shares.py le
MAX_SHARES_PER_DOC em `max_shares` e nunca usa a variavel).
"""
import ast
import pathlib


ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
if not ROUTERS.is_dir():
    ROUTERS = pathlib.Path("/app/app/routers")
if not ROUTERS.is_dir():
    candidates = list(pathlib.Path("/").glob("**/app/routers"))
    assert candidates, "nao achei app/routers"
    ROUTERS = candidates[0]


def _getenv_assignments(tree):
    """[(nome_da_variavel, linha)] para `x = os.getenv(...)` / `int(os.getenv(...))`."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        src = ast.dump(node.value)
        if "getenv" not in src and "environ" not in src:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out.append((target.id, node.lineno))
    return out


def test_no_router_reads_config_into_an_unused_variable():
    offenders = []
    for path in sorted(ROUTERS.glob("*.py")):
        tree = ast.parse(path.read_text())
        assigned = _getenv_assignments(tree)
        if not assigned:
            continue
        loads = [
            n.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        ]
        for name, lineno in assigned:
            if loads.count(name) == 0:
                offenders.append(f"{path.name}:{lineno}: {name} lido de env e nunca usado")

    assert not offenders, "config lida e ignorada (limite nao aplicado): " + "; ".join(offenders)
