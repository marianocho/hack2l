"""Invariant: a user who is neither the owner nor a share recipient must never
be able to read another user's document content, by any route."""
from tests.conftest import register_and_login

SECRET = "blue harbor term sheet is unsigned"


def test_third_party_cannot_read_document_by_any_route(client, auth_header):
    created = client.post(
        "/documents",
        json={"title": "Board pre-read", "content": SECRET},
        headers=auth_header,
    )
    assert created.status_code == 201
    doc_id = created.json()["id"]

    recipient_email = "recipient@test.dev"
    register_and_login(client, recipient_email)

    # Owner shares with the recipient, if the feature exists at all.
    client.post(f"/documents/{doc_id}/share?email={recipient_email}", headers=auth_header)

    # A third user: neither owner nor recipient.
    third_token = register_and_login(client, "carol-third@test.dev")
    third_header = {"Authorization": f"Bearer {third_token}"}

    for path in (f"/documents/{doc_id}", f"/shared/{doc_id}"):
        resp = client.get(path, headers=third_header)
        assert resp.status_code in (401, 403, 404), (
            f"{path} returned {resp.status_code} to a third party: {resp.text}"
        )
        assert SECRET not in resp.text, f"{path} leaked document content: {resp.text}"
