import json

import pytest

from app import models
from app.services import extract, fetch
from app.services.recipe_page import parse_page

LINE = extract.ExtractedLine


def recipe(**kw) -> extract.ExtractedRecipe:
    base = dict(
        is_recipe=True,
        title="Chicken & rice skillet",
        servings=4,
        minutes=35,
        steps=["Brown the chicken.", "Add rice and broth."],
        ingredients=[
            LINE(original="2 lb chicken thighs", quantity=2, unit="lb", item="chicken thigh",
                 note=None, aisle="Meat & seafood", problem=None),
            LINE(original="1 onion, diced", quantity=1, unit=None, item="yellow onion",
                 note="diced", aisle="Produce", problem=None),
            LINE(original="fresh parsley", quantity=None, unit=None, item="parsley",
                 note=None, aisle="Produce", problem="couldn't read the amount"),
        ],
    )  # fmt: skip
    base.update(kw)
    return extract.ExtractedRecipe(**base)


def to_recipe_in(draft: dict, **kw) -> dict:
    return {
        "title": draft["title"],
        "servings": draft["servings"],
        "minutes": draft["minutes"],
        "steps": draft["steps"],
        "source_url": draft["source_url"],
        "source_kind": draft["source_kind"],
        "image_id": draft["image_id"],
        "lines": [
            {k: ln[k] for k in ("original", "quantity", "unit", "name", "aisle", "note",
                                "ingredient_id")}
            for ln in draft["lines"]
        ],
        **kw,
    }  # fmt: skip


def test_text_import_uses_model_and_caches(client, fake_model, db):
    fake_model.reply = recipe()
    r = client.post("/api/import/text", json={"text": "chicken and rice caption..."})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["read_by"] == "model"
    assert [ln["name"] for ln in d["lines"]] == ["chicken thigh", "yellow onion", "parsley"]
    assert d["lines"][2]["problem"] == "couldn't read the amount"

    # Same text again: served from the extraction log, no second model call
    client.post("/api/import/text", json={"text": "chicken and rice caption..."}).raise_for_status()
    assert len(fake_model.calls) == 1
    row = db.query(models.Extraction).one()
    assert (row.input_tokens, row.output_tokens, row.cost_micros) == (1000, 500, 14_000)


def test_text_import_without_model_parses_lines(client):
    r = client.post("/api/import/text", json={"text": "2 lb chicken thighs\n\n1 cup rice"})
    d = r.json()
    assert d["read_by"] == "parser"
    assert [(ln["quantity"], ln["unit"], ln["name"]) for ln in d["lines"]] == [
        (2, "lb", "chicken thighs"),
        (1, "cup", "rice"),
    ]
    assert d["lines"][0]["aisle"] == "Meat & seafood"


def test_not_a_recipe(client, fake_model):
    fake_model.reply = recipe(is_recipe=False, ingredients=[])
    r = client.post("/api/import/text", json={"text": "follow me for more"})
    assert r.status_code == 422


def test_refusal_is_reported_and_logged(client, fake_model, db):
    fake_model.reply = None
    r = client.post("/api/import/text", json={"text": "something"})
    assert r.status_code == 422
    assert db.query(models.Extraction).one().error == "refused"


def test_save_then_reimport_matches_saved_ingredients(client, fake_model):
    fake_model.reply = recipe()
    draft = client.post("/api/import/text", json={"text": "a"}).json()
    # On the confirm screen: rename the onion to plain "onion" and give parsley an amount
    body = to_recipe_in(draft)
    body["lines"][1]["name"] = "onion"
    body["lines"][2]["quantity"] = 0.25
    body["lines"][2]["unit"] = "cup"
    saved = client.post("/api/recipes", json=body)
    assert saved.status_code == 201, saved.text
    out = saved.json()
    assert [ln["name"] for ln in out["lines"]] == ["chicken thigh", "onion", "parsley"]

    # A different recipe whose model reading says "yellow onion" again lands on "onion",
    # because the confirmed wording ("onion" from "1 onion, diced") is remembered
    fake_model.reply = recipe(title="Other")
    d2 = client.post("/api/import/text", json={"text": "b"}).json()
    onion = d2["lines"][1]
    assert (onion["name"], onion["matched"]) == ("onion", True)
    assert onion["ingredient_id"] == out["lines"][1]["ingredient_id"]


def test_aisle_correction_sticks(client):
    body = {
        "title": "Tacos",
        "lines": [{"original": "1 lb ground beef", "quantity": 1, "unit": "lb",
                   "name": "ground beef", "aisle": "Other"}],
    }  # fmt: skip
    first = client.post("/api/recipes", json=body).json()
    body["lines"][0]["aisle"] = "Meat & seafood"
    body["lines"][0]["ingredient_id"] = first["lines"][0]["ingredient_id"]
    client.put(f"/api/recipes/{first['id']}", json=body).raise_for_status()
    ings = client.get("/api/ingredients").json()
    assert ings == [{"id": ings[0]["id"], "name": "ground beef", "aisle": "Meat & seafood"}]


def test_recipe_crud_and_ownership(client, new_client, open_signup):
    from tests.conftest import signup

    body = {"title": "Eggs & toast", "servings": 1, "tags": ["Solo"],
            "lines": [{"original": "2 eggs", "quantity": 2, "name": "egg"}]}  # fmt: skip
    rid = client.post("/api/recipes", json=body).json()["id"]
    lst = client.get("/api/recipes").json()
    assert lst[0]["tags"] == ["solo"] and lst[0]["ingredient_count"] == 1

    other = signup(new_client(), "other@example.com")
    assert other.get(f"/api/recipes/{rid}").status_code == 404
    assert other.delete(f"/api/recipes/{rid}").status_code == 404

    assert client.delete(f"/api/recipes/{rid}").status_code == 204
    assert client.get("/api/recipes").json() == []


LD_PAGE = """<html><head><title>Best Chili | Site</title>
<meta property="og:description" content="Our chili.">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"WebPage","name":"x"},
 {"@type":["Recipe"],"name":"Best Chili","recipeYield":["6","6 bowls"],"totalTime":"PT1H15M",
  "recipeIngredient":["1 lb ground beef","1 (15 oz) can kidney beans","2 tbsp chili powder"],
  "recipeInstructions":[{"@type":"HowToSection","itemListElement":[
     {"@type":"HowToStep","text":"Brown the beef."},{"@type":"HowToStep","text":"Simmer."}]}]}
]}</script></head><body></body></html>"""


def test_parse_page_reads_schema_org_recipe():
    page = parse_page(LD_PAGE)
    assert page.recipe is not None
    assert page.recipe.title == "Best Chili"
    assert (page.recipe.servings, page.recipe.minutes) == (6, 75)
    assert page.recipe.ingredients[1] == "1 (15 oz) can kidney beans"
    assert page.recipe.steps == ["Brown the beef.", "Simmer."]


def test_parse_page_social_caption():
    html = (
        '<meta property="og:title" content="TikTok · Cook">'
        '<meta property="og:description" content="Easy pasta! 1 lb pasta, 2 cups sauce">'
    )
    page = parse_page(html)
    assert page.recipe is None
    assert page.description.startswith("Easy pasta!")


def test_link_import_page_without_model(client, monkeypatch):
    monkeypatch.setattr(fetch, "fetch_html", lambda url: ("https://ex.com/chili", LD_PAGE))
    d = client.post("/api/import/link", json={"url": "https://ex.com/chili"}).json()
    assert d["read_by"] == "page"
    assert d["servings"] == 6
    assert [ln["unit"] for ln in d["lines"]] == ["lb", "can", "tbsp"]


def test_link_import_page_with_model_keeps_page_numbers(client, monkeypatch, fake_model):
    monkeypatch.setattr(fetch, "fetch_html", lambda url: ("https://ex.com/chili", LD_PAGE))
    fake_model.reply = recipe(title="chili", servings=2, minutes=10)
    d = client.post("/api/import/link", json={"url": "https://ex.com/chili"}).json()
    assert d["read_by"] == "model"
    assert (d["title"], d["servings"], d["minutes"]) == ("Best Chili", 6, 75)
    sent = json.loads(fake_model.calls[0][0]["text"])
    assert sent["ingredients"][0] == "1 lb ground beef"


def test_link_import_fetch_error(client, monkeypatch):
    def boom(url):
        raise fetch.FetchError("Couldn't load that page.")

    monkeypatch.setattr(fetch, "fetch_html", boom)
    r = client.post("/api/import/link", json={"url": "https://ex.com/x"})
    assert r.status_code == 422
    assert "screenshot" in r.json()["detail"]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "ftp://example.com/",
        "https://example.com:8443/",
    ],
)
def test_fetch_refuses_private_and_odd_urls(url):
    with pytest.raises(fetch.FetchError):
        fetch._check_url(url)


def test_image_import(client, fake_model):
    fake_model.reply = recipe()
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = client.post("/api/import/image", files={"file": ("r.png", png, "image/png")})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source_kind"] == "image" and d["image_id"]
    assert fake_model.calls[0][0]["type"] == "image"
    img = client.get(f"/api/uploads/{d['image_id']}")
    assert img.content == png and img.headers["content-type"] == "image/png"


def test_image_import_rejects_non_images(client, fake_model):
    r = client.post("/api/import/image", files={"file": ("r.txt", b"hi", "text/plain")})
    assert r.status_code == 415
