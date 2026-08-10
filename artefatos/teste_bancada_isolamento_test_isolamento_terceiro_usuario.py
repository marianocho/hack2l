"""INV-ISOLAMENTO: um usuario que nao e' dono nem destinatario nunca alcanca
o conteudo de um documento alheio, por nenhuma rota.

Cenario: alice cria o documento D e o compartilha com bob. carol nao possui
nada e nao e' destinataria de nada. carol nao pode ver o conteudo de D.
"""
from tests.conftest import register_and_login

SECRET = "BLUE-HARBOR-TERM-SHEET-NAO-CIRCULAR"


def test_terceiro_usuario_nao_alcanca_documento_alheio(client):
    alice = register_and_login(client, "alice-inv@test.dev")
    bob = register_and_login(client, "bob-inv@test.dev")
    carol = register_and_login(client, "carol-inv@test.dev")

    h_alice = {"Authorization": f"Bearer {alice}"}
    h_bob = {"Authorization": f"Bearer {bob}"}
    h_carol = {"Authorization": f"Bearer {carol}"}

    created = client.post(
        "/documents",
        headers=h_alice,
        json={"title": "Q3 board pre-read", "content": SECRET},
    )
    assert created.status_code in (200, 201), created.text
    doc_id = created.json()["id"]

    # Alice compartilha com bob. No commit base a rota pode nao existir (404);
    # isso nao importa para a invariante, so' prepara o cenario.
    client.post(f"/documents/{doc_id}/share", headers=h_alice, params={"email": "bob-inv@test.dev"})

    # bob e' destinatario legitimo; carol nao e' nada.
    assert client.get("/documents", headers=h_carol).json() == []

    for rota in (f"/shared/{doc_id}", f"/documents/{doc_id}", "/shared-with-me"):
        resp = client.get(rota, headers=h_carol)
        assert SECRET not in resp.text, (
            f"vazamento: carol alcancou o conteudo de alice via {rota} "
            f"(HTTP {resp.status_code}): {resp.text[:300]}"
        )
        assert resp.status_code != 200 or rota == "/shared-with-me" or "title" not in resp.json(), (
            f"vazamento: carol recebeu metadados do documento de alice via {rota}: {resp.text[:300]}"
        )

    # controle: quem tinha direito continua tendo (nao exigido no base).
    _ = client.get(f"/shared/{doc_id}", headers=h_bob)
