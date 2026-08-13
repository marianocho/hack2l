"""Invariante: nunca pode existir mais de um share para o mesmo (documento, destinatario)."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Document, User


def test_duplicate_share_is_impossible():
    try:
        from app.models import Share
    except ImportError:
        pytest.skip("sem modelo Share neste commit: invariante vale trivialmente")
        return

    with SessionLocal() as setup:
        owner = User(email="race-owner@x.dev", hashed_password="x")
        recip = User(email="race-recip@x.dev", hashed_password="x")
        setup.add_all([owner, recip])
        setup.commit()
        doc = Document(owner_id=owner.id, title="race doc", content="secret")
        setup.add(doc)
        setup.commit()
        doc_id, recip_id = doc.id, recip.id

    q = "SELECT COUNT(*) FROM shares WHERE document_id=:d AND shared_with_user_id=:u"
    p = {"d": doc_id, "u": recip_id}
    s1, s2 = SessionLocal(), SessionLocal()
    try:
        # duas "requisicoes" concorrentes: ambas checam antes de qualquer insert
        assert s1.execute(text(q), p).scalar() == 0
        assert s2.execute(text(q), p).scalar() == 0
        try:
            s1.add(Share(document_id=doc_id, shared_with_user_id=recip_id))
            s1.commit()
            s2.add(Share(document_id=doc_id, shared_with_user_id=recip_id))
            s2.commit()
        except IntegrityError:
            s2.rollback()  # banco recusou o duplicado: invariante preservada
        else:
            with SessionLocal() as check:
                total = check.execute(text(q), p).scalar()
            assert total <= 1, (
                f"{total} shares para o mesmo (documento, destinatario): "
                "check-then-insert nao e' atomico e nao existe constraint unica"
            )
    finally:
        for s in (s1, s2):
            s.rollback()
            s.close()
        with SessionLocal() as cleanup:
            cleanup.execute(text("DELETE FROM shares WHERE document_id=:d"), {"d": doc_id})
            cleanup.execute(text("DELETE FROM documents WHERE id=:d"), {"d": doc_id})
            cleanup.execute(
                text("DELETE FROM users WHERE email IN ('race-owner@x.dev','race-recip@x.dev')")
            )
            cleanup.commit()
