from datetime import date

import pytest

from app.api import household

WED = "2026-11-18"


@pytest.fixture
def home(client, monkeypatch):
    """Household set up, 'today' is Thu Nov 19, and two recipes saved."""
    monkeypatch.setattr(household, "_today", lambda: date(2026, 11, 19))
    client.put(
        "/api/household",
        json={"budget_cents": 20_000, "anchor_payday": "2026-11-06", "kids": 3,
              "stores": ["Food Lion", "Walmart"]},
    ).raise_for_status()  # fmt: skip

    def recipe(title, servings, lines):
        body = {"title": title, "servings": servings, "lines": [
            {"original": o, "quantity": q, "unit": u, "name": n, "aisle": a}
            for o, q, u, n, a in lines]}  # fmt: skip
        r = client.post("/api/recipes", json=body)
        r.raise_for_status()
        return r.json()["id"]

    skillet = recipe("Chicken & rice skillet", 4, [
        ("2 lb chicken thighs", 2, "lb", "chicken thigh", "Meat & seafood"),
        ("1 cup rice", 1, "cup", "white rice", "Pantry"),
        ("3 cloves garlic", 3, "clove", "garlic", "Produce"),
    ])  # fmt: skip
    pasta = recipe("Tuna pasta", 1, [
        ("1/4 lb pasta", 0.25, "lb", "pasta", "Pantry"),
        ("1 can tuna", 1, "can", "canned tuna", "Pantry"),
        ("1 clove garlic", 1, "clove", "garlic", "Produce"),
    ])  # fmt: skip
    return client, skillet, pasta


def test_week_shape(home):
    client, *_ = home
    w = client.get("/api/plan").json()
    assert (w["start"], w["end"]) == (WED, "2026-11-24")
    got = [(s["day"][-2:], s["slot"], s["kids_home"], s["default_servings"]) for s in w["slots"]]
    assert got[:5] == [
        ("18", "dinner", True, 4),
        ("19", "dinner", True, 4),
        ("20", "dinner", True, 4),
        ("21", "lunch", True, 4),
        ("21", "dinner", False, 1),
    ]
    assert w["period_out_cents"] == 0


def test_plan_and_list(home):
    client, skillet, pasta = home
    client.put(f"/api/plan/{WED}/dinner", json={"kind": "recipe", "recipe_id": skillet})
    client.put("/api/plan/2026-11-19/dinner", json={"kind": "out", "amount_cents": 1500})
    # Fri Nov 20 is payday: that night out counts against the next pay period
    client.put("/api/plan/2026-11-20/dinner", json={"kind": "out", "amount_cents": 2500})
    client.put("/api/plan/2026-11-21/lunch", json={"kind": "leftovers"})
    r = client.put("/api/plan/2026-11-22/dinner", json={"kind": "recipe", "recipe_id": pasta})
    assert r.json()["servings"] == 1

    w = client.get("/api/plan?start=2026-11-22").json()  # any day snaps to the week
    assert w["start"] == WED
    assert w["period_out_cents"] == 1500
    by_day = {(s["day"], s["slot"]): s["entry"] for s in w["slots"]}
    assert by_day[(WED, "dinner")]["recipe_title"] == "Chicken & rice skillet"
    assert by_day[("2026-11-20", "dinner")]["kind"] == "out"

    lst = client.get("/api/list").json()
    assert lst["meals"] == 2 and not lst["stale"]
    items = {i["name"]: i for i in lst["items"]}
    assert [i["name"] for i in lst["items"]] == [
        "garlic", "chicken thigh", "canned tuna", "pasta", "white rice"
    ]  # fmt: skip
    assert items["garlic"]["amount"] == "4 cloves"
    assert items["garlic"]["used_in"] == ["Chicken & rice skillet", "Tuna pasta"]
    assert items["chicken thigh"]["amount"] == "2 lb"


def test_servings_scale_the_list(home):
    client, skillet, _ = home
    client.put(
        f"/api/plan/{WED}/dinner", json={"kind": "recipe", "recipe_id": skillet, "servings": 2}
    )
    items = {i["name"]: i["amount"] for i in client.get("/api/list").json()["items"]}
    assert items["chicken thigh"] == "1 lb"
    assert items["white rice"] == "1/2 cup"


def test_rebuild_keeps_checks_and_manual_items(home):
    client, skillet, pasta = home
    client.put(f"/api/plan/{WED}/dinner", json={"kind": "recipe", "recipe_id": skillet})
    lst = client.get("/api/list").json()
    garlic = next(i for i in lst["items"] if i["name"] == "garlic")
    client.patch(f"/api/list/items/{garlic['id']}", json={"checked": True}).raise_for_status()
    client.post("/api/list/items", json={"name": "Bananas"}).raise_for_status()

    client.put("/api/plan/2026-11-23/dinner", json={"kind": "recipe", "recipe_id": pasta})
    assert client.get("/api/list").json()["stale"] is True

    lst = client.post("/api/list/rebuild").json()
    items = {i["name"]: i for i in lst["items"]}
    assert lst["stale"] is False
    assert items["garlic"]["checked"] is True and items["garlic"]["amount"] == "4 cloves"
    assert items["Bananas"]["manual"] is True and items["Bananas"]["aisle"] == "Produce"


def test_staples_start_in_pantry(home):
    client, skillet, _ = home
    assert client.put("/api/pantry/staples", json={"names": ["Garlic", "eggs"]}).json() == [
        "eggs", "garlic"
    ]  # fmt: skip
    client.put(f"/api/plan/{WED}/dinner", json={"kind": "recipe", "recipe_id": skillet})
    items = {i["name"]: i for i in client.get("/api/list").json()["items"]}
    assert items["garlic"]["in_pantry"] is True
    assert items["chicken thigh"]["in_pantry"] is False
    assert client.put("/api/pantry/staples", json={"names": ["eggs"]}).json() == ["eggs"]


def test_plan_validation(home):
    client, skillet, _ = home
    assert client.put("/api/plan/2026-11-19/lunch", json={"kind": "leftovers"}).status_code == 422
    assert client.put(f"/api/plan/{WED}/dinner", json={"kind": "recipe"}).status_code == 422
    client.put(f"/api/plan/{WED}/dinner", json={"kind": "recipe", "recipe_id": skillet})
    assert client.delete(f"/api/plan/{WED}/dinner").status_code == 204
    assert client.get("/api/plan").json()["slots"][0]["entry"] is None


def test_list_needs_owner(home, new_client, open_signup):
    from tests.conftest import signup

    client, *_ = home
    client.post("/api/list/items", json={"name": "milk"})
    item = client.get("/api/list").json()["items"][0]
    other = signup(new_client(), "other@example.com")
    assert other.patch(f"/api/list/items/{item['id']}", json={"checked": True}).status_code == 404
