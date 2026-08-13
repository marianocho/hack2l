"""Invariant: a user who is neither the owner nor a share recipient must never
be able to read another user's document content, by any route.

Also: a listing of "documents shared with me" must never contain my OWN
documents.

Both invariants hold on the base commit (no sharing routes exist at all, so
there is nothing to leak) and must keep holding after the sharing feature.
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PASSWORD = "s3cret-password"
SECRET = "BLUE-HARBOR-TERM-SHEET-DO-NOT-CIRCULATE"


def _headers(email: str) -> dict:
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    res = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_outsider_cannot_read_and_own_docs_are_not_listed_as_shared():
    tag = uuid.uuid4().hex[:8]
    owner = _headers(f"owner-{tag}@hack2l.dev")
    recipient = _headers(f"recipient-{tag}@hack2l.dev")
    outsider = _headers(f"outsider-{tag}@hack2l.dev")

    created = client.post(
        "/documents",
        json={"title": f"Board pre-read {tag}", "content": SECRET},
        headers=owner,
    )
    assert created.status_code in (200, 201), created.text
    doc_id = created.json()["id"]

    # The owner shares it with the intended recipient (no-op on the base commit,
    # where the route does not exist).
    client.post(
        f"/documents/{doc_id}/share",
        params={"email": f"recipient-{tag}@hack2l.dev"},
        headers=owner,
    )

    # INVARIANT 1: the outsider must not obtain the content, by any route.
    for path in (f"/shared/{doc_id}", f"/documents/{doc_id}"):
        res = client.get(path, headers=outsider)
        assert SECRET not in res.text, (
            f"leak: outsider read owner's content via GET {path} "
            f"(status {res.status_code})"
        )

    # INVARIANT 2: a "shared with me" listing never contains my own documents.
    res = client.get("/shared-with-me", headers=owner)
    if res.status_code == 200:
        titles = [entry.get("document_id") for entry in res.json()]
        assert doc_id not in titles, (
            "wrong listing: /shared-with-me returned the caller's OWN document "
            f"{doc_id}: {res.text}"
        )
