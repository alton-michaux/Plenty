import os
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api import auth
from app.db import MEAL_SCHEMA, Base, config, get_db
from app.main import app

PASSWORD = "correct horse battery"
TEST_DB = os.environ.get(
    "PLENTY_TEST_DATABASE_URL", "postgresql+psycopg://plenty:plenty@localhost:5433/plenty_test"
)


@pytest.fixture(scope="session")
def engine():
    """Fresh tables per run. Needs Postgres: `docker compose up -d` from the repo root."""
    eng = create_engine(TEST_DB)
    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {MEAL_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {MEAL_SCHEMA}"))
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """Each test runs in a transaction that's rolled back, so tests can't see each other's rows."""
    with engine.connect() as conn, conn.begin() as tx:
        with Session(bind=conn, join_transaction_mode="create_savepoint") as s:
            yield s
        tx.rollback()


@pytest.fixture
def new_client(db) -> Callable[[], TestClient]:
    """Factory for API clients sharing the test's database. Each has its own cookie jar."""
    app.dependency_overrides[get_db] = lambda: db
    auth._fails.clear()
    yield lambda: TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def open_signup(monkeypatch):
    monkeypatch.setattr(config, "allow_signup", True)


def signup(c: TestClient, email: str = "me@example.com") -> TestClient:
    c.post("/api/auth/signup", json={"email": email, "password": PASSWORD}).raise_for_status()
    return c


@pytest.fixture
def client(new_client) -> TestClient:
    return signup(new_client())
