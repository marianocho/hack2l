"""Invariante: nenhuma rota apresenta ao usuario os DOCUMENTOS DELE MESMO
como "compartilhados com ele". No commit base a rota nao existe (404/405),
e a invariante vale trivialmente."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _token(email: str, password: str = "demo1234") -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_shared_with_me_nunca_lista_documentos_do_proprio_usuario():
    token = _token("alice@hack2l.dev")
    headers = {"Authorization": f"Bearer {token}"}

    mine = client.get("/documents", headers=headers)
    assert mine.status_code == 200, mine.text
    my_ids = {d["id"] for d in mine.json()}

    resp = client.get("/shared-with-me", headers=headers)
    if resp.status_code in (404, 405):
        return  # rota inexistente no base: invariante preservada

    assert resp.status_code == 200, resp.text
    entries = resp.json()
    leaked_own = [e for e in entries if e.get("document_id") in my_ids
                  or e.get("owner_email") == "alice@hack2l.dev"]
    assert leaked_own == [], (
        "/shared-with-me devolveu documentos do proprio usuario: %r" % (entries,)
    )
