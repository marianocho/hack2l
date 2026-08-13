"""Invariante: listar documentos compartilhados nao pode custar um numero de
queries proporcional ao numero de compartilhamentos (N+1).

No commit base a rota nao existe (404) e a invariante vale trivialmente.
"""
from sqlalchemy import event

from app.db import engine
from tests.conftest import register_and_login


def _make_docs_and_shares(client, header, other_email, n):
    for i in range(n):
        r = client.post("/documents", json={"title": f"doc {i}", "content": "x" * 30},
                        headers=header)
        assert r.status_code in (200, 201), r.text
        doc_id = r.json()["id"]
        client.post(f"/documents/{doc_id}/share?email={other_email}", headers=header)


def _count_queries(client, header):
    counter = {"n": 0}

    def before(conn, cursor, statement, params, context, executemany):
        counter["n"] += 1

    event.listen(engine, "before_cursor_execute", before)
    try:
        resp = client.get("/shared-with-me", headers=header)
    finally:
        event.remove(engine, "before_cursor_execute", before)
    return resp, counter["n"]


def test_shared_with_me_query_count_is_not_linear(client):
    owner = register_and_login(client, "owner@test.dev")
    header = {"Authorization": f"Bearer {owner}"}
    register_and_login(client, "recipient@test.dev")

    _make_docs_and_shares(client, header, "recipient@test.dev", 2)
    resp_small, q_small = _count_queries(client, header)
    if resp_small.status_code == 404:
        # rota inexistente: nada para listar, nada para amplificar
        return
    assert resp_small.status_code == 200, resp_small.text
    n_small = len(resp_small.json())

    _make_docs_and_shares(client, header, "recipient@test.dev", 8)
    resp_big, q_big = _count_queries(client, header)
    assert resp_big.status_code == 200, resp_big.text
    n_big = len(resp_big.json())

    assert n_big > n_small, "precisa de mais linhas para medir crescimento"
    growth = q_big - q_small
    assert growth <= 2, (
        f"N+1: {n_small} linhas custaram {q_small} queries, {n_big} linhas "
        f"custaram {q_big} queries (crescimento {growth} para "
        f"{n_big - n_small} linhas a mais)"
    )
