"""Invariante: nunca podem existir duas linhas de share para o mesmo par
(document_id, shared_with_user_id). No base nao ha shares, vale trivialmente.
"""
from sqlalchemy import inspect, text

from app.db import SessionLocal, engine

COLS = {"document_id", "shared_with_user_id"}


def test_no_duplicate_share_rows_possible():
    insp = inspect(engine)
    if "shares" not in insp.get_table_names():
        return  # base: sem compartilhamento, invariante vale

    protected = any(
        COLS.issubset(set(uc["column_names"])) for uc in insp.get_unique_constraints("shares")
    ) or any(
        ix.get("unique") and COLS.issubset(set(ix["column_names"] or []))
        for ix in insp.get_indexes("shares")
    )

    with SessionLocal() as s:
        s.execute(text("DELETE FROM shares"))
        owner = s.execute(text(
            "INSERT INTO users (email, hashed_password, created_at) "
            "VALUES ('race-owner@x.dev', 'x', now()) RETURNING id")).scalar()
        rcpt = s.execute(text(
            "INSERT INTO users (email, hashed_password, created_at) "
            "VALUES ('race-rcpt@x.dev', 'x', now()) RETURNING id")).scalar()
        doc = s.execute(text(
            "INSERT INTO documents (owner_id, title, content, created_at) "
            "VALUES (:o, 'D', 'c', now()) RETURNING id"), {"o": owner}).scalar()
        s.commit()

    q = text("SELECT COUNT(*) FROM shares WHERE document_id = :d AND shared_with_user_id = :u")
    ins = text("INSERT INTO shares (document_id, shared_with_user_id, created_at) "
               "VALUES (:d, :u, now())")
    p = {"d": doc, "u": rcpt}

    a, b = SessionLocal(), SessionLocal()
    try:
        # duas requisicoes concorrentes: ambas leem o COUNT antes de qualquer commit
        ca = a.execute(q, p).scalar()
        cb = b.execute(q, p).scalar()
        if ca == 0:
            a.execute(ins, p)
            a.commit()
        if cb == 0:
            b.execute(ins, p)
            b.commit()
    finally:
        a.close()
        b.close()

    with SessionLocal() as c:
        total = c.execute(q, p).scalar()

    assert protected or total == 1, (
        f"{total} linhas de share para o mesmo par; nenhuma unique constraint em {sorted(COLS)}"
    )
