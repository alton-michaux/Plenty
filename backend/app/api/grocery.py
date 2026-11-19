"""The week's grocery list, built from the plan, and the pantry staples that stay off it."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.api.auth import current_user
from app.api.plan import require_household, resolve_week
from app.db import get_db
from app.services import ingredients as ing_svc
from meal.merge import Need, merge, scale

router = APIRouter(tags=["list"])


class ItemOut(BaseModel):
    id: int
    name: str
    aisle: str
    amount: str
    used_in: list[str]
    manual: bool
    in_pantry: bool
    checked: bool
    ingredient_id: int | None


class ListOut(BaseModel):
    week_start: date
    week_end: date
    built_at: datetime
    stale: bool  # the plan changed since the list was built
    meals: int  # planned recipe meals the list covers
    items: list[ItemOut]


class ItemPatch(BaseModel):
    checked: bool | None = None
    in_pantry: bool | None = None


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _item_out(i: models.GroceryListItem) -> ItemOut:
    return ItemOut(
        id=i.id,
        name=i.name,
        aisle=i.aisle,
        amount=i.amount,
        used_in=i.used_in or [],
        manual=i.manual,
        in_pantry=i.in_pantry,
        checked=i.checked,
        ingredient_id=i.ingredient_id,
    )


def _planned(db: Session, user_id: int, start: date) -> list[models.PlanEntry]:
    return list(
        db.scalars(
            select(models.PlanEntry).where(
                models.PlanEntry.user_id == user_id,
                models.PlanEntry.kind == "recipe",
                models.PlanEntry.day.between(start, start + timedelta(days=6)),
            )
        )
    )


def _build(db: Session, user: models.User, gl: models.GroceryList) -> None:
    """(Re)build from the plan. Keeps hand-added items, and keeps checked / in-pantry marks on
    items that are still needed."""
    previous = {(i.ingredient_id or i.name.lower()): i for i in gl.items}
    manual = [i for i in gl.items if i.manual]
    staples = set(
        db.scalars(
            select(models.PantryItem.ingredient_id).where(
                models.PantryItem.user_id == user.id, models.PantryItem.staple.is_(True)
            )
        )
    )

    needs: list[Need] = []
    ingredients: dict[str, models.Ingredient] = {}
    for e in _planned(db, user.id, gl.week_start):
        r = e.recipe
        for line in r.ingredients:
            ing = line.ingredient
            ingredients[str(ing.id)] = ing
            needs.append(
                Need(
                    key=str(ing.id),
                    name=ing.name,
                    aisle=ing.aisle,
                    quantity=scale(line.quantity, r.servings, e.servings),
                    unit=line.unit,
                    source=r.title,
                )
            )

    gl.items.clear()
    db.flush()
    pos = 0
    for m in merge(needs):
        ing = ingredients[m.key]
        old = previous.get(ing.id)
        gl.items.append(
            models.GroceryListItem(
                position=pos,
                ingredient_id=ing.id,
                name=m.name,
                aisle=m.aisle,
                amount=m.display[:80],
                used_in=m.sources,
                in_pantry=old.in_pantry if old else ing.id in staples,
                checked=old.checked if old else False,
            )
        )
        pos += 1
    for i in manual:
        gl.items.append(
            models.GroceryListItem(
                position=pos,
                ingredient_id=i.ingredient_id,
                name=i.name,
                aisle=i.aisle,
                amount=i.amount,
                used_in=[],
                manual=True,
                in_pantry=i.in_pantry,
                checked=i.checked,
            )
        )
        pos += 1
    gl.built_at = datetime.now()
    gl.plan_changed_at = None


def _out(db: Session, gl: models.GroceryList) -> ListOut:
    return ListOut(
        week_start=gl.week_start,
        week_end=gl.week_start + timedelta(days=6),
        built_at=gl.built_at,
        stale=gl.plan_changed_at is not None,
        meals=len(_planned(db, gl.user_id, gl.week_start)),
        items=[_item_out(i) for i in gl.items],
    )


def _get_list(db: Session, user: models.User, start: date | None) -> models.GroceryList:
    h = require_household(db, user)
    ws = resolve_week(h, start)
    gl = db.scalar(
        select(models.GroceryList).where(
            models.GroceryList.user_id == user.id, models.GroceryList.week_start == ws
        )
    )
    if gl is None:
        gl = models.GroceryList(user_id=user.id, week_start=ws)
        db.add(gl)
        db.flush()
        _build(db, user, gl)
        db.commit()
    return gl


@router.get("/list", response_model=ListOut)
def get_list(
    start: date | None = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    return _out(db, _get_list(db, user, start))


@router.post("/list/rebuild", response_model=ListOut)
def rebuild_list(
    start: date | None = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    gl = _get_list(db, user, start)
    _build(db, user, gl)
    db.commit()
    return _out(db, gl)


def _owned_item(db: Session, user: models.User, item_id: int) -> models.GroceryListItem:
    item = db.get(models.GroceryListItem, item_id)
    if item is None or item.list.user_id != user.id:
        raise HTTPException(404, "Item not found")
    return item


@router.patch("/list/items/{item_id}", response_model=ItemOut)
def patch_item(
    item_id: int,
    body: ItemPatch,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    item = _owned_item(db, user, item_id)
    if body.checked is not None:
        item.checked = body.checked
    if body.in_pantry is not None:
        item.in_pantry = body.in_pantry
    db.commit()
    return _item_out(item)


@router.post("/list/items", response_model=ItemOut, status_code=201)
def add_item(
    body: ItemIn,
    start: date | None = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    gl = _get_list(db, user, start)
    ing = ing_svc.get_or_create(db, user.id, body.name, None)
    item = models.GroceryListItem(
        position=len(gl.items),
        ingredient_id=ing.id,
        name=ing.name,
        aisle=ing.aisle,
        amount="",
        used_in=[],
        manual=True,
    )
    gl.items.append(item)
    db.commit()
    return _item_out(item)


@router.delete("/list/items/{item_id}", status_code=204)
def delete_item(
    item_id: int, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    db.delete(_owned_item(db, user, item_id))
    db.commit()


# --- Pantry staples -------------------------------------------------------------------------


class Staples(BaseModel):
    names: list[str] = Field(max_length=100)


@router.get("/pantry/staples", response_model=list[str])
def get_staples(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    rows = db.scalars(
        select(models.PantryItem).where(
            models.PantryItem.user_id == user.id, models.PantryItem.staple.is_(True)
        )
    )
    return sorted(p.ingredient.name for p in rows)


@router.put("/pantry/staples", response_model=list[str])
def put_staples(
    body: Staples, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    """Replace the staples: things always on hand that start the week marked 'in pantry'."""
    wanted = {}
    for name in body.names:
        if name.strip():
            ing = ing_svc.get_or_create(db, user.id, name.strip(), None)
            wanted[ing.id] = ing
    existing = {
        p.ingredient_id: p
        for p in db.scalars(select(models.PantryItem).where(models.PantryItem.user_id == user.id))
    }
    for ing_id, p in existing.items():
        if ing_id not in wanted:
            db.delete(p)
    for ing_id in wanted:
        if ing_id not in existing:
            db.add(models.PantryItem(user_id=user.id, ingredient_id=ing_id, staple=True))
        else:
            existing[ing_id].staple = True
    db.commit()
    return sorted(i.name for i in wanted.values())
