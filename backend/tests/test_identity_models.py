from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Membership, Organization, User


def make_session() -> tuple[Session, object]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine), engine


def test_user_can_belong_to_an_organization() -> None:
    session, engine = make_session()
    try:
        user = User(email="owner@example.com", password_hash="test-hash", full_name="Test Owner")
        organization = Organization(name="Example Studio", slug="example-studio")
        membership = Membership(user=user, organization=organization, role="owner")
        session.add(membership)
        session.commit()

        saved_user = session.query(User).filter_by(email="owner@example.com").one()
        assert saved_user.id is not None
        assert saved_user.is_active is True
        assert saved_user.memberships[0].organization.slug == "example-studio"
        assert saved_user.memberships[0].role == "owner"
    finally:
        session.close()
        engine.dispose()


def test_organization_slug_must_be_unique() -> None:
    session, engine = make_session()
    try:
        session.add_all([
            Organization(name="First", slug="same-slug"),
            Organization(name="Second", slug="same-slug"),
        ])
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Duplicate organization slugs should be rejected")
    finally:
        session.close()
        engine.dispose()


def test_user_email_must_be_unique() -> None:
    session, engine = make_session()
    try:
        session.add_all([
            User(email="same@example.com", password_hash="hash-1", full_name="First"),
            User(email="same@example.com", password_hash="hash-2", full_name="Second"),
        ])
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Duplicate user emails should be rejected")
    finally:
        session.close()
        engine.dispose()


def test_user_cannot_have_duplicate_membership_in_same_organization() -> None:
    session, engine = make_session()
    try:
        user = User(email="member@example.com", password_hash="hash", full_name="Member")
        organization = Organization(name="Workspace", slug="workspace")
        session.add_all([user, organization])
        session.flush()
        session.add_all([
            Membership(user_id=user.id, organization_id=organization.id, role="owner"),
            Membership(user_id=user.id, organization_id=organization.id, role="member"),
        ])
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Duplicate user/organization memberships should be rejected")
    finally:
        session.close()
        engine.dispose()
