"""Invariante: nenhuma entrada de usuario e' interpolada em SQL cru.

A regra vale no codigo base (nao ha SQL cru com dados do usuario) e deve
continuar valendo depois de qualquer feature nova. Um email contendo uma
aspa simples nunca pode virar erro de sintaxe SQL (HTTP 500), nem pode
resolver para um usuario diferente do que foi pedido.
"""
from tests.conftest import register_and_login


def _auth(client, email):
    return {"Authorization": f"Bearer {register_and_login(client, email)}"}


def _make_doc(client, header):
    resp = client.post(
        "/documents",
        json={"title": "Owner doc", "content": "segredo do dono"},
        headers=header,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def test_quote_in_email_never_causes_sql_error(client):
    owner = _auth(client, "owner-inj@test.dev")
    doc_id = _make_doc(client, owner)

    for payload in ["x'", "admin@test.dev' OR '1'='1", "' OR 1=1 --"]:
        resp = client.post(
            f"/documents/{doc_id}/share",
            params={"email": payload},
            headers=owner,
        )
        assert resp.status_code != 500, (
            f"payload {payload!r} produziu erro de servidor: "
            f"{resp.status_code} {resp.text[:200]}"
        )


def test_injection_payload_never_resolves_to_a_real_recipient(client):
    owner = _auth(client, "owner2-inj@test.dev")
    _auth(client, "victim-inj@test.dev")
    doc_id = _make_doc(client, owner)

    resp = client.post(
        f"/documents/{doc_id}/share",
        params={"email": "naoexiste@test.dev' OR '1'='1"},
        headers=owner,
    )
    assert resp.status_code != 500, resp.text
    if resp.status_code in (200, 201):
        body = resp.json()
        assert False, (
            "email inexistente com payload de injecao resolveu para um "
            f"destinatario real: {body}"
        )
