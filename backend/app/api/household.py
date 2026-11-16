"""The household's setup, plus the pay period it's in today."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.api.auth import current_user
from app.db import get_db
from meal.schedule import Slot, pay_period

router = APIRouter(prefix="/household", tags=["household"])


def _today() -> date:
    return date.today()


class HouseholdIn(BaseModel):
    budget_cents: int = Field(gt=0, le=10_000_00)
    anchor_payday: date
    period_days: int = Field(14, ge=7, le=31)
    stores: list[str] = Field(default_factory=list, max_length=10)
    kids: int = Field(0, ge=0, le=12)
    kids_from_day: int = Field(2, ge=0, le=6)
    kids_from_slot: Slot = "dinner"
    kids_to_day: int = Field(5, ge=0, le=6)
    kids_to_slot: Slot = "lunch"


class PeriodOut(BaseModel):
    start: date
    end: date
    next_payday: date
    day: int
    length: int


class HouseholdOut(HouseholdIn):
    period: PeriodOut


def _out(h: models.Household) -> HouseholdOut:
    today = _today()
    p = pay_period(today, h.anchor_payday, h.period_days)
    return HouseholdOut(
        **HouseholdIn.model_validate(h, from_attributes=True).model_dump(),
        period=PeriodOut(
            start=p.start,
            end=p.end,
            next_payday=p.next_payday,
            day=p.day_number(today),
            length=p.length,
        ),
    )


def _get(db: Session, user: models.User) -> models.Household | None:
    return db.scalar(select(models.Household).where(models.Household.user_id == user.id))


@router.get("", response_model=HouseholdOut)
def get_household(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    h = _get(db, user)
    if h is None:
        raise HTTPException(404, "Set up your household first (PUT /household)")
    return _out(h)


@router.put("", response_model=HouseholdOut)
def put_household(
    body: HouseholdIn, db: Session = Depends(get_db), user: models.User = Depends(current_user)
):
    h = _get(db, user)
    if h is None:
        h = models.Household(user_id=user.id)
        db.add(h)
    data = body.model_dump()
    data["stores"] = [s.strip() for s in body.stores if s.strip()]
    for k, v in data.items():
        setattr(h, k, v)
    db.commit()
    return _out(h)
