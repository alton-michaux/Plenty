from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db import MEAL_SCHEMA, Base

# --- Auth: same tables and names as Buoy's, in the public schema. On a merge, Buoy's win. ---


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lowercased
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Session(Base):
    """A login. Only a SHA-256 of the cookie token is stored, so a leaked DB can't log anyone in."""

    __tablename__ = "session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


# --- Meal tables: everything below lives in the `meal` schema. ---


def _user_fk(**kw) -> Mapped[int]:
    return mapped_column(ForeignKey("user.id", ondelete="CASCADE"), **kw)


class Household(Base):
    """Who eats when, the food budget and its pay period, and where the shopping happens."""

    __tablename__ = "household"
    __table_args__ = {"schema": MEAL_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = _user_fk(unique=True)
    # All food, groceries and eating out together, per pay period.
    budget_cents: Mapped[int]
    anchor_payday: Mapped[date] = mapped_column(Date)  # any known payday
    period_days: Mapped[int] = mapped_column(default=14)
    stores: Mapped[list[str]] = mapped_column(ARRAY(String(60)))
    # Kids' weekly window, both ends included. Weekdays follow date.weekday() (Mon=0).
    kids: Mapped[int] = mapped_column(default=0)
    kids_from_day: Mapped[int] = mapped_column(default=2)
    kids_from_slot: Mapped[str] = mapped_column(String(10), default="dinner")
    kids_to_day: Mapped[int] = mapped_column(default=5)
    kids_to_slot: Mapped[str] = mapped_column(String(10), default="lunch")
