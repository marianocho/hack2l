"""Invariante de convencao (docs/REFERENCE_GUIDE.md):

Configuracao se le SO por app.config.settings. Nenhum modulo de aplicacao
(app/api/app/**.py) pode chamar os.getenv / os.environ diretamente.

Passa no base (nenhum modulo viola). Deve falhar no head se shares.py
introduzir os.getenv solto.
"""
import pathlib
import re

APP_DIR = pathlib.Path(__file__).resolve().parents[1] / "app"

PATTERN = re.compile(r"os\s*\.\s*(getenv|environ)")


def test_nenhum_modulo_de_app_le_env_direto():
    assert APP_DIR.is_dir(), f"diretorio de app nao encontrado: {APP_DIR}"

    violacoes = []
    for path in sorted(APP_DIR.rglob("*.py")):
        # config.py e o unico lugar autorizado a ler o ambiente.
        if path.name == "config.py":
            continue
        texto = path.read_text(encoding="utf-8")
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if PATTERN.search(linha):
                violacoes.append(f"{path.relative_to(APP_DIR.parent)}:{numero}: {linha.strip()}")

    assert not violacoes, (
        "configuracao deve vir de app.config.settings, nunca de os.getenv/os.environ "
        "solto em modulos de aplicacao:\n" + "\n".join(violacoes)
    )


def test_max_shares_por_doc_se_lido_vem_de_settings():
    """Se o limite de shares existe, ele tem que estar em Settings."""
    shares = APP_DIR / "routers" / "shares.py"
    if not shares.exists():
        return  # no base o arquivo nao existe; invariante vacuamente satisfeita
    texto = shares.read_text(encoding="utf-8")
    if "MAX_SHARES_PER_DOC" in texto:
        config = (APP_DIR / "config.py").read_text(encoding="utf-8")
        assert "max_shares_per_doc" in config.lower(), (
            "MAX_SHARES_PER_DOC usado em routers/shares.py mas nao declarado em app/config.py"
        )
