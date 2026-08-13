"""Invariante: nada devolve ao usuario, como 'compartilhado comigo',
um documento do qual ele mesmo e' o dono.
"""
import uuid


def _login(client, email, password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_shared_with_me_never_lists_my_own_documents(client, clean_db):
    owner_email = f"owner-{uuid.uuid4().hex[:8]}@hack2l.dev"
    friend_email = f"friend-{uuid.uuid4().hex[:8]}@hack2l.dev"

    owner_token = _login(client, owner_email)
    _login(client, friend_email)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    created = client.post(
        "/documents",
        json={"title": "Owner private doc", "content": "top secret content"},
        headers=owner_headers,
    )
    assert created.status_code in (200, 201), created.text
    doc_id = created.json()["id"]

    # Se a rota de share existir (head), compartilha com o amigo.
    client.post(
        f"/documents/{doc_id}/share",
        params={"email": friend_email},
        headers=owner_headers,
    )

    resp = client.get("/shared-with-me", headers=owner_headers)
    if resp.status_code == 404:
        return  # rota inexistente no base: invariante preservada

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert isinstance(payload, list), payload
    leaked = [e for e in payload if e.get("document_id") == doc_id]
    assert leaked == [], (
        "GET /shared-with-me devolveu documento do proprio usuario: %r" % (payload,)
    )
