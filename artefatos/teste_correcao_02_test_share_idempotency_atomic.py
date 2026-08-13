"""Invariante: nao pode existir mais de um share para o mesmo (documento, destinatario).

A idempotencia prometida pelo PRD ("compartilhar D com B duas vezes deixa
exatamente um share") so e' garantida se o banco recusar o par duplicado.
Se a garantia e' apenas um SELECT COUNT(*) seguido de INSERT em Python, duas
sessoes concorrentes inserem duas linhas.

Este teste vale nos dois lados: se o modelo Share nao existe (commit base),
a invariante vale trivialmente.
"""
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
        u_owner = User(email="race-owner@x.dev", password_hash="x")
        u_recip = User(email="race-recip@x.dev", password_hash="x")
        setup.add_all([u_owner, u_recip])
        setup.commit()
        doc = Document(owner_id=u_owner.id, title="race doc", content="secret")
        setup.add(doc)
        setup.commit()
        doc_id, recip_id = doc.id, u_recip.id

    # Duas sessoes simulam duas requisicoes concorrentes: ambas fazem a
    # verificacao de existencia ANTES de qualquer INSERT (exatamente a janela
    # do check-then-insert), e depois ambas inserem.
    s1, s2 = SessionLocal(), SessionLocal()
    try:
        c1 = s1.execute(
            text("SELECT COUNT(*) FROM shares WHERE document_id=:d AND shared_with_user_id=:u"),
            {"d": doc_id, "u": recip_id},
        ).scalar()
        c2 = s2.execute(
            text("SELECT COUNT(*) FROM shares WHERE document_id=:d AND shared_with_user_id=:u"),
            {"d": doc_id, "u": recip_id},
        ).scalar()
        assert c1 == 0 and c2 == 0

        duplicated = False
        try:
            s1.add(Share(document_id=doc_id, shared_with_user_id=recip_id))
            s1.commit()
            s2.add(Share(document_id=doc_id, shared_with_user_id=recip_id))
            s2.commit()
        except IntegrityError:
            # banco recusou o duplicado: invariante preservada
            s2.rollback()
        else:
            with SessionLocal() as check:
                total = check.execute(
                    text(
                        "SELECT COUNT(*) FROM shares "
                        "WHERE document_id=:d AND shared_with_user_id=:u"
                    ),
                    {"d": doc_id, "u": recip_id},
                ).scalar()
            duplicated = total > 1
            assert not duplicated, (
                f"{total} shares para o mesmo (documento, destinatario): "
                "check-then-insert nao e' atomico e nao ha constraint unica"
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
