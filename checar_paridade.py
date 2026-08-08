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


def app_serve_o_pr():
    """🚨 O app no ar serve o codigo ASSADO NA IMAGEM, nao o checkout.

    Sem esta checagem, uma maquina com a imagem construida a partir da `main`
    roda o Veredito inteiro sem erro nenhum e devolve TUDO em MEDIA -- porque
    `http_request` nunca alcanca o codigo do PR, `prova_ponta_a_ponta` fica
    falsa e a R2 rebaixa. O sintoma nao parece problema de ambiente: parece o
    produto nao funcionando. Foi assim nesta maquina ate 12h58.

    Compara os routers do worktree do head com os que estao dentro do container.
    Divergencia = imagem velha; rebuild com `up -d --build api web`.
    """
    from veredito import ferramentas as f

    wt = f._garante_worktree(f.commit_head(), "head")
    origem = wt / "app" / "api" / "app" / "routers"
    esperado = {
        p.name: len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        for p in sorted(origem.glob("*.py"))
    }
    assert esperado, f"nenhum router em {origem}"

    r = subprocess.run(
        ["docker", "compose", "-f", str(f.cfg.COMPOSE),
         "--project-directory", str(f.cfg.DESAFIO),
         "exec", "-T", "api", "sh", "-c", "wc -l /code/app/routers/*.py"],
        capture_output=True, text=True, timeout=90,
    )
    assert r.returncode == 0, f"nao consegui ler os routers do container: {r.stderr.strip()[:200]}"

    servido = {}
    for linha in r.stdout.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[0].isdigit() and partes[1].endswith(".py"):
            servido[pathlib.PurePosixPath(partes[1]).name] = int(partes[0])

    return compara_routers(esperado, servido, f.commit_head())


def compara_routers(esperado: dict, servido: dict, commit: str) -> str:
    """Puro, para ter teste. Levanta se o container nao serve o head.

    Assimetrico de proposito: so' cobra o que o head TEM. Router extra no
    container nao e' erro -- pode ser sobra de outro branch, e nao impede a
    prova. O que impede e' faltar arquivo do PR (imagem construida do base) ou
    ele estar com outro tamanho (imagem velha, construida antes do checkout).
    """
    faltando = sorted(set(esperado) - set(servido))
    diferentes = sorted(n for n in set(esperado) & set(servido) if esperado[n] != servido[n])
    if faltando or diferentes:
        raise AssertionError(
            f"a imagem NAO serve o head do PR ({commit[:7]}). "
            f"routers ausentes: {faltando or '-'}; com tamanho diferente: {diferentes or '-'}. "
            "Rode: docker compose ... up -d --build api web"
        )
    return f"{len(esperado)} routers batem com {commit[:7]}"


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


CHECAGENS = [("API", api), ("rotas", rotas), ("Web", web), ("Postgres", banco),
             ("repo do desafio", repo), ("app serve o PR", app_serve_o_pr),
             ("Langfuse", langfuse), ("chave Anthropic", chave)]


def main() -> int:
    for nome, fn in CHECAGENS:
        checa(nome, fn)
    for n, d in ok:
        print(f"  OK    {n:18} {d}")
    for n, d in falhou:
        print(f"  FALHA {n:18} {d}")
    print(f"\n{len(ok)}/{len(ok) + len(falhou)}")
    return 1 if falhou else 0


# Guarda de __main__ para o modulo poder ser importado -- sem ela, `import
# checar_paridade` roda as 8 checagens e chama sys.exit no meio de quem
# importou. E' o que permite testar as proprias checagens.
if __name__ == "__main__":
    sys.exit(main())
