"""Invariante: nenhuma requisicao de compartilhamento com um e-mail que nao
identifica um usuario real pode resultar em um compartilhamento criado.

Um payload de SQL injection no campo `email` nao corresponde ao e-mail de
nenhum usuario cadastrado, portanto a API nunca pode responder 201 nem
devolver um `shared_with_user_id`.

No commit base a rota nao existe (404) e a invariante vale trivialmente.
"""
from tests.conftest import register_and_login


def _create_doc(client, token, title, content):
    resp = client.post(
        "/documents",
        json={"title": title, "content": content},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def test_injection_email_never_resolves_to_a_user(client):
    # Varios usuarios existem no banco, para que um "OR '1'='1" tenha alvo.
    alice = register_and_login(client, "alice-inj@example.com")
    register_and_login(client, "bob-inj@example.com")
    register_and_login(client, "carol-inj@example.com")

    doc_id = _create_doc(client, alice, "Alice secret", "top secret content")

    payload = "' OR '1'='1"
    resp = client.post(
        f"/documents/{doc_id}/share",
        params={"email": payload},
        headers={"Authorization": f"Bearer {alice}"},
    )

    assert resp.status_code != 500, f"erro interno: {resp.text}"
    assert resp.status_code != 201, (
        "compartilhamento criado com e-mail inexistente (SQL injection): "
        f"{resp.status_code} {resp.text}"
    )

    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    assert "shared_with_user_id" not in body, (
        "a API resolveu um destinatario a partir de um payload de injecao: " + resp.text
    )
