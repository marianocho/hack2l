"""INV-ISOLAMENTO: um usuario sem nenhum documento e sem nenhum share
nao pode alcancar o conteudo do documento de outro usuario por endpoint nenhum.
"""
from tests.conftest import register_and_login

SECRET = "SECRET-DIAMOND-42-carol-nao-pode-ver-isto"


def test_terceiro_nao_alcanca_documento_alheio(client):
    alice = register_and_login(client, "alice@test.dev")
    alice_h = {"Authorization": f"Bearer {alice}"}
    bob = register_and_login(client, "bob@test.dev")
    bob_h = {"Authorization": f"Bearer {bob}"}
    carol = register_and_login(client, "carol@test.dev")
    carol_h = {"Authorization": f"Bearer {carol}"}

    created = client.post(
        "/documents",
        json={"title": "Private", "content": SECRET},
        headers=alice_h,
    )
    assert created.status_code == 201
    doc_id = created.json()["id"]

    # Alice compartilha o documento com Bob (e so com Bob).
    # No commit base esse endpoint nao existe: a chamada e' inofensiva.
    client.post(f"/documents/{doc_id}/share", params={"email": "bob@test.dev"}, headers=alice_h)

    # Bob nao e' o alvo do teste; Carol e'. Carol nao possui nada e nada
    # foi compartilhado com ela.
    assert client.get(f"/documents/{doc_id}", headers=carol_h).status_code == 404
    assert client.get("/documents", headers=carol_h).json() == []

    resp = client.get(f"/shared/{doc_id}", headers=carol_h)
    assert SECRET not in resp.text, (
        f"vazamento: carol leu o conteudo do documento de alice "
        f"(status {resp.status_code}, body {resp.text!r})"
    )
    assert resp.status_code != 200, (
        f"vazamento: carol recebeu 200 em /shared/{doc_id}: {resp.text!r}"
    )
    # sanidade: bob continua existindo e nada acima dependeu do head
    assert client.get("/documents", headers=bob_h).status_code == 200
