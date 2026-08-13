"""Invariante: entrada de usuario (email) e' tratada como DADO, nunca como SQL.

Nenhuma rota do app pode responder 500 porque o email do destinatario contem
um apostrofo. No commit base a rota de share nem existe (404), o que satisfaz
a invariante. Com SQL interpolado por f-string, o apostrofo quebra a query.
"""


def test_recipient_email_with_apostrophe_never_breaks_sql(client, auth_header):
    created = client.post(
        "/documents",
        json={"title": "share invariant", "content": "corpo do documento"},
        headers=auth_header,
    )
    assert created.status_code in (200, 201), created.text
    doc_id = created.json()["id"]

    response = client.post(
        f"/documents/{doc_id}/share",
        params={"email": "o'brien@hack2l.dev"},
        headers=auth_header,
    )

    # 404 (rota inexistente ou destinatario inexistente), 400 ou 422 sao aceitaveis.
    # 500 significa que o texto do usuario virou SQL.
    assert response.status_code != 500, (
        "email com apostrofo causou erro interno: entrada do usuario esta sendo "
        f"interpolada em SQL cru (status={response.status_code})"
    )


def test_recipient_lookup_does_not_match_arbitrary_users(client, auth_header):
    created = client.post(
        "/documents",
        json={"title": "share invariant 2", "content": "corpo"},
        headers=auth_header,
    )
    assert created.status_code in (200, 201), created.text
    doc_id = created.json()["id"]

    response = client.post(
        f"/documents/{doc_id}/share",
        params={"email": "' OR '1'='1"},
        headers=auth_header,
    )

    # Nao existe usuario com esse email literal: a resposta jamais pode ser
    # um share criado com sucesso.
    assert response.status_code not in (200, 201), (
        "tautologia SQL no campo email produziu um share valido: "
        f"{response.status_code} {response.text}"
    )
