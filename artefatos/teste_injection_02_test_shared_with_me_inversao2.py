"""Invariante: o que um usuario ve em "compartilhado comigo" sao documentos de
OUTROS compartilhados COM ELE -- nunca os documentos dele mesmo.
No commit base a rota nao existe (404/405) e a invariante vale trivialmente."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mk_user():
    email = f"u{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "senha12345"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/auth/login", json={"email": email, "password": "senha12345"})
    assert r.status_code == 200, r.text
    return email, {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_shared_with_me_nao_lista_documentos_do_proprio_dono():
    a_email, a = _mk_user()
    b_email, b = _mk_user()

    r = client.post("/documents", json={"title": "Doc de A", "content": "segredo de A"}, headers=a)
    assert r.status_code in (200, 201), r.text
    doc_id = r.json()["id"]

    s = client.post(f"/documents/{doc_id}/share", params={"email": b_email}, headers=a)
    if s.status_code in (404, 405):
        return  # feature ausente no base: invariante preservada
    assert s.status_code in (200, 201), s.text

    ra = client.get("/shared-with-me", headers=a)
    if ra.status_code in (404, 405):
        return
    assert ra.status_code == 200, ra.text
    assert [e for e in ra.json() if e.get("document_id") == doc_id] == [], (
        "dono viu o proprio documento em /shared-with-me: %r" % (ra.json(),)
    )

    rb = client.get("/shared-with-me", headers=b)
    assert rb.status_code == 200, rb.text
    assert [e for e in rb.json() if e.get("document_id") == doc_id], (
        "destinatario nao viu o documento compartilhado com ele: %r" % (rb.json(),)
    )
