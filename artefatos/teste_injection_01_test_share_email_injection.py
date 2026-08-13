"""Invariante: nenhum endpoint aceita um email de destinatario inexistente
contendo SQL e o trata como um usuario valido / falha de servidor.

No base o endpoint nao existe (404) -> invariante vale.
No head o SQL cru interpolado faz a injecao ser executada.
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _mk_user():
    email = f"u{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "pw12345678"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/auth/login", json={"email": email, "password": "pw12345678"})
    if r.status_code != 200:
        r = client.post(
            "/auth/login",
            data={"username": email, "password": "pw12345678"},
        )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_injected_email_is_never_resolved_to_a_user():
    token = _mk_user()
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/documents", json={"title": "t", "content": "hello world"}, headers=h)
    assert r.status_code in (200, 201), r.text
    doc_id = r.json()["id"]

    payload = "' UNION SELECT 999999 -- "
    r = client.post(f"/documents/{doc_id}/share", params={"email": payload}, headers=h)

    # A rota pode nao existir (base): 404 e' aceitavel.
    # O que NAO pode acontecer: erro 5xx nem sucesso ao "encontrar" esse email.
    assert r.status_code < 500, f"SQL injetado foi executado: {r.status_code} {r.text}"
    assert r.status_code not in (200, 201), f"email injetado virou destinatario: {r.text}"
