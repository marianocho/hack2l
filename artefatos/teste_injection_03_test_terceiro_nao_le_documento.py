"""Invariante: um usuario que nao e' dono nem destinatario de um share
NAO pode alcancar o conteudo do documento de outra pessoa por nenhuma rota.
"""
from tests.conftest import register_and_login


def test_terceiro_nao_alcanca_documento_de_outro(client):
    owner_token = register_and_login(client, "owner-inv@test.dev")
    owner_header = {"Authorization": f"Bearer {owner_token}"}

    secret = "codename blue harbor term sheet unsigned"
    created = client.post(
        "/documents",
        json={"title": "Board pre-read", "content": secret},
        headers=owner_header,
    )
    assert created.status_code == 201
    doc_id = created.json()["id"]

    # destinatario legitimo
    register_and_login(client, "recipient-inv@test.dev")

    # o dono compartilha com o destinatario legitimo (se a feature existir)
    client.post(
        f"/documents/{doc_id}/share?email=recipient-inv@test.dev",
        headers=owner_header,
    )

    # terceiro: nem dono, nem destinatario
    third_token = register_and_login(client, "third-inv@test.dev")
    third_header = {"Authorization": f"Bearer {third_token}"}

    for path in (f"/documents/{doc_id}", f"/shared/{doc_id}"):
        resp = client.get(path, headers=third_header)
        assert resp.status_code != 200, (
            f"{path} devolveu 200 para um terceiro: {resp.text}"
        )
        assert secret not in resp.text, f"{path} vazou o conteudo: {resp.text}"
