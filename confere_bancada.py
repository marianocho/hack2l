"""Cada defeito plantado e' REALMENTE explorável? E o PR limpo e' limpo mesmo?

Sem isto a bancada nao vale nada: um "defeito" que nao se manifesta faria o
Veredito parecer cego quando ele esta certo, e um PR "limpo" com defeito
acidental faria ele parecer alucinado quando ele esta certo.

Sobe cada ramo, exercita, e volta.
"""
import subprocess
import sys
import time

import requests

REPO = r"C:\hack_agents\Hack2L\bancada"
API = "http://127.0.0.1:8100"


def sh(*args, **kw):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, **kw)


def sobe(ramo: str) -> None:
    sh("git", "checkout", "-q", ramo)
    # ⚠️ `build` de TODOS os servicos, nao so' da api. `api` e `seed` sao imagens
    # separadas construidas do mesmo ./app: rebuildar so' a api deixa o seed com
    # o models.py do ramo anterior, e o SCHEMA do banco fica do ramo errado.
    # Foi assim que o race do PR 3 pareceu nao existir -- a restricao de
    # unicidade do `main` continuava na tabela.
    sh("docker", "compose", "build", timeout=900)
    sh("docker", "compose", "up", "-d", "api", timeout=600)
    sh("docker", "compose", "run", "--rm", "seed", timeout=300)
    for _ in range(40):
        try:
            if requests.get(f"{API}/health", timeout=3).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise SystemExit(f"a api nao subiu no ramo {ramo}")


def tok(nome):
    r = requests.post(f"{API}/login",
                      json={"email": f"{nome}@bancada.dev", "senha": f"{nome}-senha"},
                      timeout=10)
    return {"Authorization": f"Bearer {r.json()['token']}"}


falhas = []


def espera(rotulo, condicao, detalhe=""):
    print(f"  {'ok  ' if condicao else 'FALHA'} {rotulo}" + (f"  [{detalhe}]" if detalhe else ""))
    if not condicao:
        falhas.append(rotulo)


# ---------------------------------------------------------------- PR 1
print("\n[PR 1] filtro de projetos -- injecao de SQL (CWE-89)")
sobe("pr/filtro-de-projetos")
r = requests.get(f"{API}/projects", params={"nome": "migracao"}, headers=tok("ana"), timeout=10)
espera("o filtro funciona para o caso legitimo", r.status_code == 200 and len(r.json()) == 1,
       f"{r.status_code} / {len(r.json()) if r.ok else '-'}")

# ⚠️ davi NAO alcança: `lista_projetos` retorna cedo quando nao ha projeto
# visivel, entao a consulta injetada nem roda para ele. O defeito exige um
# usuario com ao menos um projeto -- e clara e' esse caso: participa de UM e
# passa a ver TRES. Ajustado o teste, nao o fixture.
r = requests.get(f"{API}/projects", params={"nome": "' or '1'='1"}, headers=tok("davi"), timeout=10)
espera("davi segue sem ver nada (o early return o protege por acidente)",
       r.status_code == 200 and r.json() == [], f"{len(r.json()) if r.ok else r.status_code}")

r = requests.get(f"{API}/projects", headers=tok("clara"), timeout=10)
legitimo = len(r.json())
r = requests.get(f"{API}/projects", params={"nome": "' or '1'='1"}, headers=tok("clara"), timeout=10)
espera("EXPLORAVEL: clara vê projeto que nao participa",
       r.status_code == 200 and len(r.json()) > legitimo,
       f"{legitimo} legitimo -> {len(r.json()) if r.ok else '-'} com o payload")

# ---------------------------------------------------------------- PR 2
print("\n[PR 2] tarefa por link -- IDOR (CWE-639)")
sobe("pr/tarefa-por-link")
r = requests.get(f"{API}/tasks/1", headers=tok("davi"), timeout=10)
espera("EXPLORAVEL: davi lê tarefa da ana pelo id", r.status_code == 200,
       f"{r.status_code}")
if r.status_code == 200:
    espera("  e o detalhe sensível vaza", "Acme" in r.json().get("detalhe", ""),
           r.json().get("detalhe", "")[:40])
r = requests.get(f"{API}/projects/1/tasks", headers=tok("davi"), timeout=10)
espera("a rota por projeto CONTINUA protegida (defeito e' so' um)",
       r.status_code == 404, f"{r.status_code}")

# ---------------------------------------------------------------- PR 3
print("\n[PR 3] reconvite -- TOCTOU (CWE-367), FORA do alcance sequencial")
sobe("pr/reconvite-de-membro")
a = requests.post(f"{API}/projects/1/members", params={"email": "davi@bancada.dev"},
                  headers=tok("ana"), timeout=10)
b = requests.post(f"{API}/projects/1/members", params={"email": "davi@bancada.dev"},
                  headers=tok("ana"), timeout=10)
espera("sequencial continua idempotente (por isso e' invisivel)",
       a.status_code == 201 and b.json().get("novo") is False,
       f"{a.json().get('novo')} depois {b.json().get('novo')}")

import concurrent.futures as cf
import threading
h = tok("ana")


def _psql(sql):
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-U", "bancada",
         "-d", "bancada", "-t", "-A", "-c", sql],
        cwd=REPO, capture_output=True, text=True).stdout.strip()


# ⚠️ O race e' PROBABILISTICO -- essa e' a natureza dele, nao fraqueza do teste.
# Uma tentativa nao basta; repetir ate' 6 vezes, limpando entre elas.
n, tentativas = "1", 0
for tentativas in range(1, 7):
    _psql("delete from members where project_id=2 and user_id="
          "(select id from users where email='davi@bancada.dev')")
    barreira = threading.Barrier(24)

    def _dispara(_):
        barreira.wait()      # alinhadas, para cairem na mesma janela
        return requests.post(f"{API}/projects/2/members",
                             params={"email": "davi@bancada.dev"},
                             headers=h, timeout=20).status_code

    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        list(ex.map(_dispara, range(24)))
    n = _psql("select count(*) from members where project_id=2 and user_id="
              "(select id from users where email='davi@bancada.dev')")
    if n.isdigit() and int(n) > 1:
        break

espera("EXPLORAVEL so' com concorrencia: linha duplicada", n.isdigit() and int(n) > 1,
       f"{n} linhas na tentativa {tentativas} de 6 (probabilistico)")

# ---------------------------------------------------------------- PR 4
print("\n[PR 4] contagem de tarefas -- NENHUM defeito (controle negativo)")
sobe("pr/contagem-de-tarefas")
r = requests.get(f"{API}/projects", headers=tok("ana"), timeout=10)
espera("a contagem esta certa", r.status_code == 200 and
       sorted(p["tarefas"] for p in r.json()) == [1, 2], str(r.json() if r.ok else r.status_code)[:60])
espera("davi continua sem ver nada",
       requests.get(f"{API}/projects", headers=tok("davi"), timeout=10).json() == [])
espera("davi continua sem ler tarefa alheia",
       requests.get(f"{API}/tasks/1", headers=tok("davi"), timeout=10).status_code == 404)
espera("clara continua sem ler tarefa da ana",
       requests.get(f"{API}/tasks/1", headers=tok("clara"), timeout=10).status_code == 404)
espera("clara nao adiciona membro no projeto do bruno",
       requests.post(f"{API}/projects/3/members", params={"email": "davi@bancada.dev"},
                     headers=tok("clara"), timeout=10).status_code == 404)

sh("git", "checkout", "-q", "main")
print(f"\n{'TODOS OS QUATRO SE COMPORTAM' if not falhas else 'PROBLEMA: ' + str(falhas)}")
sys.exit(1 if falhas else 0)
