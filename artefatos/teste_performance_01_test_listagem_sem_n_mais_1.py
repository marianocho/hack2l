"""Invariante: o custo em SQL de uma rota de listagem nao cresce com o numero
de linhas listadas. Vale para toda rota GET sem parametro de caminho.
"""
import pytest
from sqlalchemy import event, select

from app.db import engine, SessionLocal
from app.main import app
from app.models import Document, User

try:
    from app.models import Share
except ImportError:  # pragma: no cover - base commit has no sharing
    Share = None


def _list_routes():
    paths = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if "GET" not in methods or "{" in path:
            continue
        if path in ("/health", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
            continue
        paths.append(path)
    return paths


def _seed(email, n):
    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == email))
    for i in range(n):
        doc = Document(owner_id=user.id, title=f"doc {i}", content=f"body {i}")
        db.add(doc)
        db.flush()
        if Share is not None:
            db.add(Share(document_id=doc.id, shared_with_user_id=user.id))
    db.commit()
    db.close()


def _count_queries(client, path, headers):
    stmts = []

    def hook(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    event.listen(engine, "before_cursor_execute", hook)
    try:
        resp = client.get(path, headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", hook)
    return resp, len(stmts)


@pytest.mark.parametrize("path", _list_routes())
def test_listagem_nao_faz_n_mais_1(client, auth_header, path):
    _seed("alice@test.dev", 1)
    resp_small, small = _count_queries(client, path, auth_header)
    if resp_small.status_code != 200:
        pytest.skip(f"{path} nao listavel: {resp_small.status_code}")

    _seed("alice@test.dev", 6)
    resp_big, big = _count_queries(client, path, auth_header)
    assert resp_big.status_code == 200

    assert big <= small + 1, (
        f"{path}: {small} queries com 1 linha, {big} queries com 7 linhas -> N+1"
    )
