"""The week planner: dinners (plus the kids' last lunch) for one Wed-Tue week."""

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import models
from app.api import household as household_api
from app.api.auth import current_user
from app.db import get_db
from meal.schedule import MealPoint, Slot, pay_period, week_slots, week_start

router = APIRouter(prefix="/plan", tags=["plan"])

Kind = Literal["recipe", "out", "leftovers"]


def require_household(db: Session, user: models.User) -> models.Household:
    h = db.scalar(select(models.Household).where(models.Household.user_id == user.id))
    if h is None:
        raise HTTPException(409, "Set up your household first")
    return h


def resolve_week(h: models.Household, start: date | None) -> date:
    """Snap any date to the start of its week (the kids' arrival weekday)."""
    return week_start(start or household_api._today(), h.kids_from_day)


def mark_list_stale(db: Session, user_id: int, day: date, h: models.Household) -> None:
    db.execute(
        update(models.GroceryList)
        .where(
            models.GroceryList.user_id == user_id,
            models.GroceryList.week_start == week_start(day, h.kids_from_day),
        )
        .values(plan_changed_at=datetime.now())
    )


class EntryOut(BaseModel):
    kind: Kind
    recipe_id: int | None
    recipe_title: str | None
    recipe_servings: int | None
    servings: int
    amount_cents: int | None


class SlotOut(BaseModel):
    day: date
    slot: Slot
    kids_home: bool
    default_servings: int
    entry: EntryOut | None


class WeekOut(BaseModel):
    start: date
    end: date
    slots: list[SlotOut]
    # Nights out planned in the pay period containing this week's start, for the budget card
    period_out_cents: int


class EntryIn(BaseModel):
    kind: Kind
    recipe_id: int | None = None
    servings: int | None = Field(None, ge=1, le=50)
    amount_cents: int | None = Field(None, ge=0, le=1_000_00)


def _entry_out(e: models.PlanEntry) -> EntryOut:
    return EntryOut(
        kind=e.kind,  # type: ignore[arg-type]
        recipe_id=e.recipe_id,
        recipe_title=e.recipe.title if e.recipe else None,
        recipe_servings=e.recipe.servings if e.recipe else None,
        servings=e.servings,
        amount_cents=e.amount_cents,
    )


def _slots(h: models.Household, start: date):
    return week_slots(
        start,
        h.kids,
        MealPoint(h.kids_from_day, h.kids_from_slot),  # type: ignore[arg-type]
        MealPoint(h.kids_to_day, h.kids_to_slot),  # type: ignore[arg-type]
    )


@router.get("", response_model=WeekOut)
def get_week(
    start: date | None = Query(None, description="Any day in the week; defaults to today"),
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    h = require_household(db, user)
    ws = resolve_week(h, start)
    end = ws + timedelta(days=6)
    entries = {
        (e.day, e.slot): e
        for e in db.scalars(
            select(models.PlanEntry).where(
                models.PlanEntry.user_id == user.id,
                models.PlanEntry.day.between(ws, end),
            )
        )
    }
    p = pay_period(ws, h.anchor_payday, h.period_days)
    out_cents = db.scalar(
        select(func.coalesce(func.sum(models.PlanEntry.amount_cents), 0)).where(
            models.PlanEntry.user_id == user.id,
            models.PlanEntry.kind == "out",
            models.PlanEntry.day.between(p.start, p.end),
        )
    )
    return WeekOut(
        start=ws,
        end=end,
        slots=[
            SlotOut(
                day=s.day,
                slot=s.slot,
                kids_home=s.kids_home,
                default_servings=s.servings,
                entry=_entry_out(e) if (e := entries.get((s.day, s.slot))) else None,
            )
            for s in _slots(h, ws)
        ],
        period_out_cents=out_cents,
    )


@router.put("/{day}/{slot}", response_model=EntryOut)
def put_entry(
    day: date,
    slot: Slot,
    body: EntryIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    h = require_household(db, user)
    planned = {(s.day, s.slot): s for s in _slots(h, resolve_week(h, day))}
    if (day, slot) not in planned:
        raise HTTPException(422, "That meal isn't part of the plan")
    if body.kind == "recipe":
        r = db.get(models.Recipe, body.recipe_id) if body.recipe_id else None
        if r is None or r.user_id != user.id:
            raise HTTPException(422, "Pick a recipe")
    e = db.scalar(
        select(models.PlanEntry).where(
            models.PlanEntry.user_id == user.id,
            models.PlanEntry.day == day,
            models.PlanEntry.slot == slot,
        )
    )
    if e is None:
        e = models.PlanEntry(user_id=user.id, day=day, slot=slot)
        db.add(e)
    e.kind = body.kind
    e.recipe_id = body.recipe_id if body.kind == "recipe" else None
    e.servings = body.servings or planned[(day, slot)].servings
    e.amount_cents = body.amount_cents if body.kind == "out" else None
    mark_list_stale(db, user.id, day, h)
    db.commit()
    db.refresh(e)
    return _entry_out(e)


@router.delete("/{day}/{slot}", status_code=204)
def delete_entry(
    day: date, slot: Slot, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    h = require_household(db, user)
    e = db.scalar(
        select(models.PlanEntry).where(
            models.PlanEntry.user_id == user.id,
            models.PlanEntry.day == day,
            models.PlanEntry.slot == slot,
        )
    )
    if e:
        db.delete(e)
        mark_list_stale(db, user.id, day, h)
        db.commit()
