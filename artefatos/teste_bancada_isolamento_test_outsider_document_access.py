"""Invariant: a user who is neither the owner nor a share recipient must not be
able to read a document's content by any route (docs/REVIEW_TASK.md:43).
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PASSWORD = "pw12345678"


def _user(email: str) -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code >= 400:
        r = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_outsider_cannot_read_someone_elses_document():
    tag = uuid.uuid4().hex[:8]
    owner_email = f"owner-{tag}@hack2l.dev"
    friend_email = f"friend-{tag}@hack2l.dev"
    outsider_email = f"outsider-{tag}@hack2l.dev"

    owner = _user(owner_email)
    _user(friend_email)
    outsider = _user(outsider_email)

    secret = f"SECRET-CONTENT-{tag}"
    r = client.post(
        "/documents", json={"title": f"private-{tag}", "content": secret}, headers=owner
    )
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    doc_id = r.json()["id"]

    # The owner shares with the friend (route may not exist on base; that is fine).
    client.post(
        f"/documents/{doc_id}/share", params={"email": friend_email}, headers=owner
    )

    # The outsider is neither owner nor recipient: no route may hand them the content.
    for path in (f"/documents/{doc_id}", f"/shared/{doc_id}"):
        resp = client.get(path, headers=outsider)
        assert secret not in resp.text, (
            f"{path} leaked the document to a non-owner, non-recipient: "
            f"{resp.status_code} {resp.text}"
        )
