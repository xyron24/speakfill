"""Pytest setup: isolated speakfill_test database + seeded template + TestClient.

Run inside the api container:  python -m pytest tests/ -q
"""

import os

# Must be set before importing app modules (settings read env at import time).
os.environ["DATABASE_URL"] = "postgresql+psycopg://speakfill:speakfill@db:5432/speakfill_test"
os.environ["LLM_PROVIDER"] = "stub"
os.environ["VOICE_PROVIDER"] = "stub"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

ADMIN_URL = "postgresql+psycopg://speakfill:speakfill@db:5432/postgres"
TEST_URL = os.environ["DATABASE_URL"]


def _ensure_test_db() -> None:
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'speakfill_test'")
        ).first()
        if not exists:
            conn.execute(text("CREATE DATABASE speakfill_test"))


_ensure_test_db()

from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Answer, Base, Feedback, Job, Session, Submission  # noqa: E402

test_engine = create_engine(TEST_URL)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
# Rebuild the test schema every run: create_all alone won't add new columns.
Base.metadata.drop_all(test_engine)
Base.metadata.create_all(test_engine)


def _override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db


@pytest.fixture()
def client():
    # Clean slate per test, then re-seed the template. Bulk deletes execute
    # immediately in loop order (children before parents); ORM-object deletes
    # would flush in table-name order with no relationships to sort by.
    with TestingSession() as db:
        for model in (Answer, Job, Submission, Feedback, Session):
            db.query(model).delete(synchronize_session=False)
        db.commit()
    from app.seed import seed

    seed()
    with TestClient(app) as c:
        yield c
