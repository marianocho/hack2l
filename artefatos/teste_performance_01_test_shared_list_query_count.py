"""Invariante: listar documentos compartilhados nao pode disparar uma query
por documento (N+1). A contagem de SQL deve ser O(1) em relacao ao numero de
compartilhamentos, nao O(N).

No commit base nao existe nenhuma rota de listagem de compartilhamento, logo
nao existe N+1 nenhum e a invariante vale trivialmente.
"""
from sqlalchemy import event

from app.db import engine
from tests.conftest import register_and_login


def _count_queries(fn):
    stmts = []

    def before(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", before)
    return result, stmts


def test_shared_with_me_does_not_issue_one_query_per_document(client):
    alice = register_and_login(client, "alice-n1@test.dev")
    bob = register_and_login(client, "bob-n1@test.dev")
    ah = {"Authorization": f"Bearer {alice}"}

    doc_ids = []
    for i in range(10):
        r = client.post(
            "/documents",
            json={"title": f"doc {i}", "content": f"conteudo numero {i}"},
            headers=ah,
        )
        assert r.status_code in (200, 201), r.text
        doc_ids.append(r.json()["id"])

    # Se a rota de listagem nao existe (commit base), a invariante vale.
    probe = client.get("/shared-with-me", headers=ah)
    if probe.status_code == 404:
        return

    for doc_id in doc_ids:
        s = client.post(
            f"/documents/{doc_id}/share",
            params={"email": "bob-n1@test.dev"},
            headers=ah,
        )
        assert s.status_code in (200, 201), s.text

    resp, stmts = _count_queries(lambda: client.get("/shared-with-me", headers=ah))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 10, body

    selects = [s for s in stmts if s.strip().upper().startswith("SELECT")]
    doc_selects = [s for s in selects if " FROM documents" in s]
    user_selects = [s for s in selects if " FROM users" in s]

    assert len(doc_selects) <= 2, (
        f"N+1: {len(doc_selects)} SELECTs em documents para 10 shares; "
        f"total de SELECTs={len(selects)}, users={len(user_selects)}"
    )
    assert len(selects) <= 4, (
        f"N+1: {len(selects)} SELECTs para listar 10 shares: {selects}"
    )
