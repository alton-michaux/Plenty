"""Recipe box: import (link, text, image) into a draft, confirm it, and keep it."""

import hashlib
import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.api.auth import current_user
from app.db import get_db
from app.services import extract, fetch, recipe_page
from app.services import ingredients as ing_svc
from meal.ingredients import AISLES, guess_aisle, parse_line
from meal.units import canonical

log = logging.getLogger(__name__)
router = APIRouter(tags=["recipes"])

MAX_IMAGE_BYTES = 6 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

SourceKind = Literal["link", "text", "image", "manual"]


class LineIn(BaseModel):
    original: str = Field(max_length=300)
    quantity: float | None = Field(None, ge=0, le=100_000)
    unit: str | None = Field(None, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    aisle: str = "Other"
    note: str | None = Field(None, max_length=200)
    ingredient_id: int | None = None


class DraftLine(LineIn):
    problem: str | None = None
    matched: bool = False  # name/aisle came from a saved ingredient


class RecipeDraft(BaseModel):
    title: str
    servings: int | None
    minutes: int | None
    steps: list[str]
    source_url: str | None
    source_kind: SourceKind
    image_id: int | None = None
    lines: list[DraftLine]
    read_by: Literal["model", "page", "parser"]  # who did the reading, for the confirm screen
    warning: str | None = None


class RecipeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    servings: int | None = Field(None, ge=1, le=100)
    minutes: int | None = Field(None, ge=1, le=10_000)
    steps: list[str] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=10)
    source_url: str | None = Field(None, max_length=2000)
    source_kind: SourceKind = "manual"
    image_id: int | None = None
    lines: list[LineIn] = Field(max_length=100)


class RecipeLineOut(BaseModel):
    id: int
    original: str
    quantity: float | None
    unit: str | None
    note: str | None
    ingredient_id: int
    name: str
    aisle: str


class RecipeSummary(BaseModel):
    id: int
    title: str
    servings: int | None
    minutes: int | None
    tags: list[str]
    source_kind: str
    image_id: int | None
    ingredient_count: int


class RecipeOut(RecipeSummary):
    source_url: str | None
    steps: list[str]
    lines: list[RecipeLineOut]


class TextImport(BaseModel):
    text: str = Field(min_length=1, max_length=30_000)
    url: str | None = Field(None, max_length=2000)


class LinkImport(BaseModel):
    url: HttpUrl


# --- Drafts -------------------------------------------------------------------------------


def _match_lines(db: Session, user: models.User, lines: list[DraftLine]) -> list[DraftLine]:
    """Swap in saved ingredients where the recipe's wording (or the suggested item) is known."""
    for line in lines:
        ing = ing_svc.find(db, user.id, parse_line(line.original).name, line.name)
        if ing:
            line.name, line.aisle, line.ingredient_id, line.matched = (
                ing.name,
                ing.aisle,
                ing.id,
                True,
            )
    return lines


def _from_model(r: extract.ExtractedRecipe) -> list[DraftLine]:
    return [
        DraftLine(
            original=x.original[:300],
            quantity=x.quantity,
            unit=x.unit,
            name=x.item[:120] or parse_line(x.original).name[:120] or x.original[:120],
            aisle=x.aisle,
            note=(x.note or None) and x.note[:200],
            problem=x.problem,
        )
        for x in r.ingredients
        if x.original.strip()
    ]


def _from_parser(lines: list[str]) -> list[DraftLine]:
    out = []
    for raw in lines:
        p = parse_line(raw)
        if not p.name:
            continue
        out.append(
            DraftLine(
                original=p.original[:300],
                quantity=p.quantity,
                unit=p.unit,
                name=p.name[:120],
                aisle=guess_aisle(p.name),
                note=p.note and p.note[:200],
            )
        )
    return out


def _model_draft(
    r: extract.ExtractedRecipe, kind: SourceKind, url: str | None, image_id: int | None = None
) -> RecipeDraft:
    if not r.is_recipe or not r.ingredients:
        raise HTTPException(422, "No recipe found there. Try pasting the ingredients.")
    return RecipeDraft(
        title=r.title[:200] or "Untitled recipe",
        servings=r.servings if r.servings and r.servings <= 100 else None,
        minutes=r.minutes if r.minutes and r.minutes <= 10_000 else None,
        steps=r.steps,
        source_url=url,
        source_kind=kind,
        image_id=image_id,
        lines=_from_model(r),
        read_by="model",
    )


def _extraction(fn, *args):
    try:
        return fn(*args)
    except extract.ExtractionError as e:
        raise HTTPException(422, str(e)) from None


@router.post("/import/link", response_model=RecipeDraft)
def import_link(
    body: LinkImport, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    url = str(body.url)
    try:
        final_url, html = fetch.fetch_html(url)
    except fetch.FetchError as e:
        raise HTTPException(
            422, f"{e} Try pasting the caption or sharing a screenshot instead."
        ) from None
    page = recipe_page.parse_page(html)

    if page.recipe:
        pr = page.recipe
        if extract.available():
            text = extract.page_text(pr.title, pr.ingredients, pr.steps)
            r = _extraction(extract.from_text, db, user.id, text)
            draft = _model_draft(r, "link", final_url)
            # The page's own numbers beat the model's reading of them
            draft.title = pr.title[:200] or draft.title
            draft.servings = pr.servings or draft.servings
            draft.minutes = pr.minutes or draft.minutes
            draft.steps = pr.steps or draft.steps
        else:
            draft = RecipeDraft(
                title=pr.title[:200] or "Untitled recipe",
                servings=pr.servings,
                minutes=pr.minutes,
                steps=pr.steps,
                source_url=final_url,
                source_kind="link",
                lines=_from_parser(pr.ingredients),
                read_by="page",
            )
    else:
        # Social posts: the caption is in the page description
        text = "\n".join(t for t in (page.title, page.description) if t).strip()
        if len(text) < 40 or not extract.available():
            raise HTTPException(
                422,
                "Couldn't find a recipe on that page. Paste the caption or share a screenshot.",
            )
        draft = _model_draft(_extraction(extract.from_text, db, user.id, text), "link", final_url)

    draft.lines = _match_lines(db, user, draft.lines)
    return draft


@router.post("/import/text", response_model=RecipeDraft)
def import_text(
    body: TextImport, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    if extract.available():
        r = _extraction(extract.from_text, db, user.id, body.text)
        draft = _model_draft(r, "text", body.url)
    else:
        # No model: treat each non-empty line as an ingredient line
        lines = [ln for ln in body.text.splitlines() if ln.strip()]
        draft = RecipeDraft(
            title="Untitled recipe",
            servings=None,
            minutes=None,
            steps=[],
            source_url=body.url,
            source_kind="text",
            lines=_from_parser(lines),
            read_by="parser",
            warning="Read line by line. Set the title and check each ingredient.",
        )
    draft.lines = _match_lines(db, user, draft.lines)
    return draft


@router.post("/import/image", response_model=RecipeDraft)
def import_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(415, "Send a JPEG, PNG, WebP or GIF image.")
    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "That image is too big (6 MB max).")
    upload = models.Upload(
        user_id=user.id,
        content_type=file.content_type,
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(upload)
    db.commit()
    r = _extraction(extract.from_image, db, user.id, data, file.content_type)
    draft = _model_draft(r, "image", None, upload.id)
    draft.lines = _match_lines(db, user, draft.lines)
    return draft


@router.get("/uploads/{upload_id}", response_class=Response)
def get_upload(
    upload_id: int, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    up = db.get(models.Upload, upload_id)
    if up is None or up.user_id != user.id:
        raise HTTPException(404, "Not found")
    return Response(
        up.data, media_type=up.content_type, headers={"Cache-Control": "private, max-age=86400"}
    )


# --- Recipes ------------------------------------------------------------------------------


def _owned_recipe(db: Session, user: models.User, recipe_id: int) -> models.Recipe:
    r = db.get(models.Recipe, recipe_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "Recipe not found")
    return r


def _summary(r: models.Recipe) -> RecipeSummary:
    return RecipeSummary(
        id=r.id,
        title=r.title,
        servings=r.servings,
        minutes=r.minutes,
        tags=r.tags or [],
        source_kind=r.source_kind,
        image_id=r.image_id,
        ingredient_count=len(r.ingredients),
    )


def _out(r: models.Recipe) -> RecipeOut:
    return RecipeOut(
        **_summary(r).model_dump(),
        source_url=r.source_url,
        steps=r.steps or [],
        lines=[
            RecipeLineOut(
                id=li.id,
                original=li.original,
                quantity=li.quantity,
                unit=li.unit,
                note=li.note,
                ingredient_id=li.ingredient_id,
                name=li.ingredient.name,
                aisle=li.ingredient.aisle,
            )
            for li in r.ingredients
        ],
    )


def _apply(db: Session, user: models.User, r: models.Recipe, body: RecipeIn) -> None:
    if body.image_id is not None:
        up = db.get(models.Upload, body.image_id)
        if up is None or up.user_id != user.id:
            raise HTTPException(422, "Unknown image")
    r.title = body.title.strip()
    r.servings, r.minutes = body.servings, body.minutes
    r.steps = [s.strip()[:2000] for s in body.steps if s.strip()]
    r.tags = list(dict.fromkeys(t.strip().lower()[:40] for t in body.tags if t.strip()))
    r.source_url, r.source_kind, r.image_id = body.source_url, body.source_kind, body.image_id

    r.ingredients.clear()
    db.flush()
    for pos, line in enumerate(body.lines):
        aisle = line.aisle if line.aisle in AISLES else None
        ing = None
        if line.ingredient_id is not None:
            ing = db.get(models.Ingredient, line.ingredient_id)
            if ing is None or ing.user_id != user.id:
                raise HTTPException(422, "Unknown ingredient")
            if ing.name.lower() != line.name.strip().lower():
                ing = None  # renamed on the confirm screen: it's a different item
            elif aisle and aisle != ing.aisle:
                ing.aisle = aisle
        if ing is None:
            ing = ing_svc.get_or_create(db, user.id, line.name, aisle)
        ing_svc.remember(db, user.id, line.original or line.name, ing)
        r.ingredients.append(
            models.RecipeIngredient(
                position=pos,
                ingredient=ing,
                quantity=line.quantity,
                unit=canonical(line.unit) if line.unit else None,
                note=line.note,
                original=(line.original or line.name)[:300],
            )
        )


@router.get("/recipes", response_model=list[RecipeSummary])
def list_recipes(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    rows = db.scalars(
        select(models.Recipe).where(models.Recipe.user_id == user.id).order_by(models.Recipe.title)
    ).unique()
    return [_summary(r) for r in rows]


@router.post("/recipes", response_model=RecipeOut, status_code=201)
def create_recipe(
    body: RecipeIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    r = models.Recipe(user_id=user.id, title=body.title, source_kind=body.source_kind)
    db.add(r)
    _apply(db, user, r, body)
    db.commit()
    return _out(r)


@router.get("/recipes/{recipe_id}", response_model=RecipeOut)
def get_recipe(
    recipe_id: int, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    return _out(_owned_recipe(db, user, recipe_id))


@router.put("/recipes/{recipe_id}", response_model=RecipeOut)
def update_recipe(
    recipe_id: int,
    body: RecipeIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    r = _owned_recipe(db, user, recipe_id)
    _apply(db, user, r, body)
    db.commit()
    return _out(r)


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(
    recipe_id: int, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    db.delete(_owned_recipe(db, user, recipe_id))
    db.commit()


class IngredientOut(BaseModel):
    id: int
    name: str
    aisle: str


@router.get("/ingredients", response_model=list[IngredientOut])
def list_ingredients(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    rows = db.scalars(
        select(models.Ingredient)
        .where(models.Ingredient.user_id == user.id)
        .order_by(models.Ingredient.name)
    )
    return [IngredientOut(id=i.id, name=i.name, aisle=i.aisle) for i in rows]


@router.get("/aisles", response_model=list[str])
def list_aisles():
    return list(AISLES)
