from datetime import date

from app.api import household
from tests.conftest import PASSWORD, signup

SETUP = {
    "budget_cents": 20_000,
    "anchor_payday": "2026-11-06",
    "stores": ["Food Lion", " Walmart ", ""],
    "kids": 3,
}


def test_health(new_client):
    assert new_client().get("/api/health").json() == {"ok": True}


def test_first_signup_then_closed(new_client):
    first = new_client()
    assert first.get("/api/auth/status").json()["signup_open"] is True
    signup(first)
    assert first.get("/api/auth/status").json()["user"]["email"] == "me@example.com"
    r = new_client().post("/api/auth/signup", json={"email": "x@example.com", "password": PASSWORD})
    assert r.status_code == 403


def test_owner_email_guards_first_signup(new_client, monkeypatch):
    from app.db import config

    monkeypatch.setattr(config, "owner_email", "Owner@Example.com")
    r = new_client().post("/api/auth/signup", json={"email": "x@example.com", "password": PASSWORD})
    assert r.status_code == 403
    signup(new_client(), "owner@example.com")


def test_login_logout(new_client):
    signup(new_client())
    c = new_client()
    assert (
        c.post("/api/auth/login", json={"email": "ME@example.com", "password": "nope"}).status_code
        == 401
    )
    c.post(
        "/api/auth/login", json={"email": "ME@example.com", "password": PASSWORD}
    ).raise_for_status()
    assert c.get("/api/household").status_code == 404  # signed in, not set up yet
    c.post("/api/auth/logout")
    assert c.get("/api/household").status_code == 401


def test_household_needs_auth(new_client):
    assert new_client().get("/api/household").status_code == 401


def test_household_setup_and_period(client, monkeypatch):
    monkeypatch.setattr(household, "_today", lambda: date(2026, 11, 16))
    r = client.put("/api/household", json=SETUP)
    assert r.status_code == 200, r.text
    h = client.get("/api/household").json()
    assert h["stores"] == ["Food Lion", "Walmart"]
    assert (h["kids_from_day"], h["kids_from_slot"]) == (2, "dinner")
    assert h["period"] == {
        "start": "2026-11-06",
        "end": "2026-11-19",
        "next_payday": "2026-11-20",
        "day": 11,
        "length": 14,
    }
    # Updating keeps one row
    client.put("/api/household", json={**SETUP, "budget_cents": 25_000}).raise_for_status()
    assert client.get("/api/household").json()["budget_cents"] == 25_000


def test_household_validates(client):
    assert client.put("/api/household", json={**SETUP, "budget_cents": 0}).status_code == 422
    assert client.put("/api/household", json={**SETUP, "kids_to_slot": "brunch"}).status_code == 422
