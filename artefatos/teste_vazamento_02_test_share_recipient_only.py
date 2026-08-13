"""Invariante: um usuario que nao e' dono nem destinatario de um share
nao alcanca o conteudo do documento por NENHUMA rota."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _user(tag):
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    password = "sup3rsecret"
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


def test_outsider_cannot_read_document_shared_with_someone_else():
    _owner_email, owner = _user("owner")
    recipient_email, _recipient = _user("recipient")
    _outsider_email, outsider = _user("outsider")

    secret = "SEKRIT-" + uuid.uuid4().hex
    r = client.post(
        "/documents",
        json={"title": "owner private doc", "content": secret},
        headers=owner,
    )
    assert r.status_code in (200, 201), r.text
    doc_id = r.json()["id"]

    # Owner shares with the recipient (no-op on the base commit, where the
    # endpoint does not exist yet -- that is fine, the invariant still holds).
    client.post(f"/documents/{doc_id}/share?email={recipient_email}", headers=owner)

    # The outsider must not reach the content through any route.
    for path in (f"/shared/{doc_id}", f"/documents/{doc_id}"):
        resp = client.get(path, headers=outsider)
        assert resp.status_code != 200, (
            f"outsider read {path}: {resp.status_code} {resp.text}"
        )
        assert secret not in resp.text, f"content leaked via {path}: {resp.text}"
