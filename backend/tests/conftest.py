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


@pytest.fixture(autouse=True)
def no_model_calls(monkeypatch):
    """Tests never reach the real API, even with a key in backend/.env."""
    from app.services import extract

    def refuse(_content):
        raise AssertionError("Unexpected model call; use the fake_model fixture")

    monkeypatch.setattr(config, "anthropic_api_key", None)
    monkeypatch.setattr(extract, "call_model", refuse)


@pytest.fixture
def fake_model(monkeypatch):
    """Turn the model 'on' and answer every call with whatever the test sets in .reply."""
    from app.services import extract

    class Fake:
        reply: "extract.ExtractedRecipe | None" = None
        calls: list = []

        def __call__(self, content):
            self.calls.append(content)
            meta = {
                "model": "claude-opus-5-5",
                "request_id": "req_test",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cost_micros": 14_000,
            }
            return self.reply, meta

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(config, "anthropic_api_key", "test-key")
    monkeypatch.setattr(extract, "call_model", fake)
    return fake
