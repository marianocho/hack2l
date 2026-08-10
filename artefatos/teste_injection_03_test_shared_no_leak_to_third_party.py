"""Invariant: a user who is neither the owner nor a share recipient must never
receive another user's document content, by any route."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SECRET = "BLUE-HARBOR-" + uuid.uuid4().hex


def _register(email, password="pw-Str0ng-123"):
    for path in ("/auth/register", "/auth/signup", "/auth/users"):
        r = client.post(path, json={"email": email, "password": password})
        if r.status_code < 300:
            break
    else:
        pytest.skip("could not register user")
    return _login(email, password)


def _login(email, password="pw-Str0ng-123"):
    for path, kw in (
        ("/auth/login", {"json": {"email": email, "password": password}}),
        ("/auth/login", {"data": {"username": email, "password": password}}),
        ("/auth/token", {"data": {"username": email, "password": password}}),
    ):
        r = client.post(path, **kw)
        if r.status_code < 300 and "access_token" in r.text:
            return r.json()["access_token"]
    pytest.skip("could not log in")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_third_party_never_reads_someone_elses_document():
    tag = uuid.uuid4().hex[:8]
    alice = _register(f"a-{tag}@example.com")
    bob_email = f"b-{tag}@example.com"
    _register(bob_email)
    carol = _register(f"c-{tag}@example.com")

    body = {"title": f"secret-{tag}", "content": SECRET}
    r = client.post("/documents", json=body, headers=_h(alice))
    if r.status_code >= 300:
        r = client.post("/documents", json={"title": body["title"], "text": SECRET},
                        headers=_h(alice))
    assert r.status_code < 300, f"could not create document: {r.status_code} {r.text}"
    doc_id = r.json()["id"]

    # Alice shares the document with Bob only (route may not exist yet: fine).
    client.post(f"/documents/{doc_id}/share?email={bob_email}", headers=_h(alice))

    # Carol is neither owner nor recipient. No route may hand her the content.
    for path in (f"/shared/{doc_id}", f"/documents/{doc_id}"):
        resp = client.get(path, headers=_h(carol))
        assert SECRET not in resp.text, (
            f"leak: {path} returned Alice's content to Carol "
            f"(status {resp.status_code})"
        )

    listed = client.get("/shared-with-me", headers=_h(carol))
    assert SECRET not in listed.text
