"""Confere que esta maquina consegue rodar o Veredito. Le tudo do .env."""
import os, sys, subprocess, pathlib
from dotenv import load_dotenv

RAIZ = pathlib.Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

ok, falhou = [], []


def checa(nome, fn):
    try:
        det = fn()
        ok.append((nome, det))
    except Exception as e:
        falhou.append((nome, f"{type(e).__name__}: {e}"))


def api():
    import requests
    u = os.environ["APP_API_URL"]
    r = requests.get(f"{u}/health", timeout=10)
    assert r.json().get("status") == "ok", r.text
    return u


def rotas():
    import requests
    r = requests.get(f"{os.environ['APP_API_URL']}/openapi.json", timeout=10)
    return f"{len(r.json()['paths'])} rotas"


def web():
    import requests
    u = os.environ["APP_WEB_URL"]
    assert requests.get(u, timeout=15).status_code == 200
    return u


def banco():
    import psycopg2
    c = psycopg2.connect(os.environ["APP_DB_URL"], connect_timeout=10)
    cur = c.cursor()
    cur.execute("select count(*) from users")
    n = cur.fetchone()[0]
    cur.execute("select count(*) from documents")
    d = cur.fetchone()[0]
    c.close()
    return f"{n} usuarios, {d} documentos"


def repo():
    p = (RAIZ / os.environ["CHALLENGE_REPO"]).resolve()
    assert p.is_dir(), f"nao existe: {p}"
    b = subprocess.run(["git", "-C", str(p), "rev-parse", "--abbrev-ref", "HEAD"],
                       capture_output=True, text=True).stdout.strip()
    return f"{p.name} @ {b}"


def langfuse():
    import requests
    u = os.environ["LANGFUSE_HOST"]
    assert requests.get(f"{u}/api/public/health", timeout=15).status_code == 200
    return u


def chave():
    import anthropic
    cli = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    r = cli.messages.create(model=os.environ["MODEL_PROMOTOR"], max_tokens=16,
                            messages=[{"role": "user", "content": "responda so: ok"}])
    return f"{os.environ['MODEL_PROMOTOR']} -> {r.content[0].text.strip()[:20]}"


for nome, fn in [("API", api), ("rotas", rotas), ("Web", web), ("Postgres", banco),
                 ("repo do desafio", repo), ("Langfuse", langfuse), ("chave Anthropic", chave)]:
    checa(nome, fn)

for n, d in ok:
    print(f"  OK    {n:18} {d}")
for n, d in falhou:
    print(f"  FALHA {n:18} {d}")
print(f"\n{len(ok)}/{len(ok) + len(falhou)}")
sys.exit(1 if falhou else 0)
