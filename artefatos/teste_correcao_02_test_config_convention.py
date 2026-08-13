"""Invariante: toda configuracao do backend passa por app/config.py (settings).

Nenhum modulo da aplicacao le variavel de ambiente solta com os.getenv, e
nenhum modulo declara um limite configuravel que nunca e' usado (dead config).

Ver docs/REFERENCE_GUIDE.md: "All configuration is read once, here, and
accessed through the `settings` object".
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if not (APP_DIR / "config.py").exists():
    APP_DIR = Path("/app/app")

PY_FILES = [p for p in APP_DIR.rglob("*.py") if p.name != "config.py"]


def test_app_dir_found():
    assert (APP_DIR / "config.py").exists(), f"nao achei app/config.py em {APP_DIR}"
    assert PY_FILES, "nenhum modulo python encontrado"


def test_no_loose_env_reads_outside_config():
    offenders = []
    for path in PY_FILES:
        src = path.read_text()
        for i, line in enumerate(src.splitlines(), start=1):
            if re.search(r"os\.(getenv|environ)", line):
                offenders.append(f"{path}:{i}: {line.strip()}")
    assert not offenders, "config lida fora de app/config.py:\n" + "\n".join(offenders)


def test_no_dead_configuration_variable():
    """Se um modulo cria uma variavel a partir do ambiente, ela tem que ser usada."""
    dead = []
    for path in PY_FILES:
        src = path.read_text()
        for i, line in enumerate(src.splitlines(), start=1):
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.*os\.(getenv|environ)", line)
            if not m:
                continue
            name = m.group(1)
            uses = len(re.findall(rf"\b{re.escape(name)}\b", src))
            if uses <= 1:
                dead.append(f"{path}:{i}: '{name}' atribuido e nunca usado")
    assert not dead, "configuracao morta:\n" + "\n".join(dead)
