"""Invariant: a recipient lookup by email must match ONLY the exact email given.

No user-supplied string may be interpolated into SQL, so an email that is not
registered must never resolve to some other user, and must never grant that
other user access to the document.
"""
from tests.conftest import register_and_login


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def test_bogus_email_with_sql_metacharacters_never_resolves_to_another_user(client):
    victim_token = register_and_login(client, "victim@test.dev")
    bystander_token = register_and_login(client, "bystander@test.dev")

    created = client.post(
        "/documents",
        json={"title": "Private", "content": "secret content here"},
        headers=_hdr(victim_token),
    )
    assert created.status_code == 201
    doc_id = created.json()["id"]

    # This email is not registered. Nothing may be shared with anybody.
    payload = "nobody@test.dev' OR '1'='1"
    resp = client.post(
        f"/documents/{doc_id}/share",
        params={"email": payload},
        headers=_hdr(victim_token),
    )

    assert resp.status_code != 201, (
        "An unregistered email containing SQL metacharacters resolved to a real "
        f"user and created a share: {resp.status_code} {resp.text}"
    )
    body = resp.text
    assert "shared_with_user_id" not in body, f"share created from injected email: {body}"

    # And no third party may read the document by any route.
    for route in (f"/documents/{doc_id}", f"/shared/{doc_id}"):
        got = client.get(route, headers=_hdr(bystander_token))
        assert got.status_code != 200, (
            f"bystander read the victim's document via {route}: {got.text}"
        )
