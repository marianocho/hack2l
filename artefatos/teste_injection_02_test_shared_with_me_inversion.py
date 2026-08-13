"""Invariante: /shared-with-me nunca pode devolver documentos do PROPRIO usuario.

No commit base a rota nao existe (404) e a invariante vale trivialmente.
No head a rota existe e devolve exatamente os documentos do proprio dono,
invertendo a direcao do compartilhamento (PRD, docs/REVIEW_TASK.md:43,45).
"""
import uuid


def _register_and_login(client, email, password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_shared_with_me_never_lists_my_own_documents(client):
    suffix = uuid.uuid4().hex[:8]
    owner_email = f"owner-{suffix}@hack2l.dev"
    other_email = f"other-{suffix}@hack2l.dev"

    owner = _register_and_login(client, owner_email)
    _register_and_login(client, other_email)

    created = client.post(
        "/documents",
        json={"title": f"Owner secret {suffix}", "content": "top secret body"},
        headers=owner,
    )
    assert created.status_code in (200, 201), created.text
    doc_id = created.json()["id"]

    # Compartilha com o outro usuario (rota inexistente no base -> 404/405).
    client.post(f"/documents/{doc_id}/share?email={other_email}", headers=owner)

    listed = client.get("/shared-with-me", headers=owner)
    if listed.status_code in (404, 405):
        # base: nao ha rota, nada pode ser devolvido errado.
        return

    assert listed.status_code == 200, listed.text
    own_ids = [entry.get("document_id") for entry in listed.json()]
    assert doc_id not in own_ids, (
        "/shared-with-me devolveu um documento do PROPRIO usuario: "
        f"{listed.json()}"
    )
