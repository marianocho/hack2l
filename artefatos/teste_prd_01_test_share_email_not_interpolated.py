"""Invariant: no user-supplied string is ever interpolated into raw SQL.

A quote character in an email must never reach the database as SQL syntax.
On any route, sending email="'" must produce a normal HTTP response
(4xx), never a 500 caused by a broken SQL statement.
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _token() -> str:
    email = f"probe-{uuid.uuid4().hex[:8]}@hack2l.dev"
    password = "probe-password-123"
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code < 500, r.text
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if isinstance(body, dict) and body.get("access_token"):
        return body["access_token"]
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code < 400, r.text
    return r.json()["access_token"]


def test_quote_in_email_never_breaks_sql():
    headers = {"Authorization": f"Bearer {_token()}"}

    r = client.post("/documents", json={"title": "probe doc", "content": "body"}, headers=headers)
    assert r.status_code < 400, r.text
    doc_id = r.json()["id"]

    r = client.post(f"/documents/{doc_id}/share", params={"email": "'"}, headers=headers)
    assert r.status_code != 500, (
        "quote in email produced a 500: the value is interpolated into raw SQL "
        f"instead of being bound as a parameter (body: {r.text[:200]})"
    )
