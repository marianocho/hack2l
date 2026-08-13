"""Invariant: a user who is neither the owner nor the share recipient must not
be able to read a document's content by any route.

This holds trivially on the base commit (there is no sharing feature at all) and
must keep holding once sharing exists.
"""
from tests.conftest import register_and_login

SECRET = "codename-blue-harbor-do-not-circulate"


def _doc_id(client, headers):
    resp = client.post(
        "/documents",
        json={"title": "Q3 board pre-read", "content": SECRET},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def test_outsider_cannot_read_document_shared_with_someone_else(client):
    owner = {"Authorization": f"Bearer {register_and_login(client, 'owner@test.dev')}"}
    register_and_login(client, "recipient@test.dev")
    outsider = {
        "Authorization": f"Bearer {register_and_login(client, 'outsider@test.dev')}"
    }

    doc_id = _doc_id(client, owner)

    # Owner shares with the recipient (no-op on the base commit, where the route
    # does not exist yet).
    client.post(f"/documents/{doc_id}/share?email=recipient@test.dev", headers=owner)

    # The outsider must not reach the content through the owned-document route...
    direct = client.get(f"/documents/{doc_id}", headers=outsider)
    assert direct.status_code != 200 or SECRET not in direct.text, (
        f"leak via /documents/{doc_id}: {direct.status_code} {direct.text}"
    )

    # ...nor through any sharing route: the outsider is not the recipient.
    shared = client.get(f"/shared/{doc_id}", headers=outsider)
    assert shared.status_code != 200, (
        f"leak via /shared/{doc_id}: HTTP 200 for a user who is neither owner "
        f"nor recipient -> {shared.text}"
    )
    assert SECRET not in shared.text
