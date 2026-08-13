"""Invariante (docs/REVIEW_TASK.md req. 3): a lista "compartilhados comigo"
nunca pode conter documentos do PROPRIO chamador.

No commit base a rota nao existe (404) e a invariante vale trivialmente.
No head, se a rota existe, ela nao pode devolver documento cujo owner_email
seja o email do proprio chamador.
"""
from tests.conftest import register_and_login


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_shared_with_me_nao_lista_documentos_do_proprio_usuario(client):
    owner_email = "owner@test.dev"
    other_email = "other@test.dev"

    owner = register_and_login(client, owner_email)
    register_and_login(client, other_email)

    doc = client.post(
        "/documents",
        json={"title": "Doc do dono", "content": "conteudo secreto do dono"},
        headers=_h(owner),
    )
    assert doc.status_code in (200, 201), doc.text
    doc_id = doc.json()["id"]

    # Se a feature existir, o dono compartilha o documento com o outro usuario.
    client.post(
        f"/documents/{doc_id}/share",
        params={"email": other_email},
        headers=_h(owner),
    )

    listing = client.get("/shared-with-me", headers=_h(owner))
    if listing.status_code == 404:
        # rota inexistente (base): nada a violar
        return

    assert listing.status_code == 200, listing.text
    entries = listing.json()
    proprios = [e for e in entries if e.get("owner_email") == owner_email]
    assert proprios == [], (
        "/shared-with-me devolveu documentos do proprio usuario: %r" % proprios
    )
