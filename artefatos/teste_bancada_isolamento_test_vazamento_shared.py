"""INV-ISOLAMENTO: um usuario que nao e' dono nem destinatario nunca pode ler
o conteudo de um documento alheio, por nenhuma rota da API.

No commit base a rota /shared/{id} nao existe, entao o outsider recebe 404 e a
invariante se mantem. No head, /shared/{id} so verifica se EXISTE algum share
para o documento (nao se ele foi compartilhado com o chamador), entao qualquer
usuario autenticado le o documento.
"""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mk_user() -> str:
    email = f"u{uuid.uuid4().hex[:10]}@hack2l.dev"
    r = client.post("/auth/register", json={"email": email, "password": "senha-123"})
    assert r.status_code in (201, 409), r.text
    r = client.post("/auth/login", json={"email": email, "password": "senha-123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_outsider_nunca_le_documento_alheio():
    owner = _mk_user()
    recipient_email = f"u{uuid.uuid4().hex[:10]}@hack2l.dev"
    r = client.post("/auth/register", json={"email": recipient_email, "password": "senha-123"})
    assert r.status_code == 201, r.text

    outsider = _mk_user()

    secret = "SEGREDO-" + uuid.uuid4().hex
    r = client.post(
        "/documents",
        json={"title": "Documento privado", "content": secret},
        headers=_h(owner),
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]

    # O dono compartilha com o destinatario legitimo (no base a rota nao existe:
    # 404, e a invariante deve continuar valendo mesmo assim).
    client.post(
        f"/documents/{doc_id}/share",
        params={"email": recipient_email},
        headers=_h(owner),
    )

    # O terceiro (nem dono, nem destinatario) tenta ler.
    leaked = client.get(f"/shared/{doc_id}", headers=_h(outsider))
    assert leaked.status_code != 200, (
        f"vazamento: outsider leu documento alheio -> {leaked.text}"
    )
    assert secret not in leaked.text, f"vazamento de conteudo: {leaked.text}"

    # E tambem nao pode le-lo pela rota original de documentos.
    direct = client.get(f"/documents/{doc_id}", headers=_h(outsider))
    assert direct.status_code != 200, f"vazamento em /documents: {direct.text}"
