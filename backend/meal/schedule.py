"""Pay periods and who's home for which meal. Pure functions: no web, no database."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Slot = Literal["breakfast", "lunch", "dinner"]
SLOTS: tuple[Slot, ...] = ("breakfast", "lunch", "dinner")


@dataclass(frozen=True)
class PayPeriod:
    start: date  # payday that opened the period
    end: date  # last day of the period (the day before the next payday)

    @property
    def next_payday(self) -> date:
        return self.end + timedelta(days=1)

    @property
    def length(self) -> int:
        return (self.end - self.start).days + 1

    def day_number(self, today: date) -> int:
        """1 on payday, `length` on the last day."""
        return (today - self.start).days + 1


def pay_period(today: date, anchor_payday: date, period_days: int = 14) -> PayPeriod:
    """The pay period containing `today`. `anchor_payday` is any known payday, past or future."""
    if period_days < 1:
        raise ValueError("period_days must be at least 1")
    start = anchor_payday + timedelta(
        days=(today - anchor_payday).days // period_days * period_days
    )
    return PayPeriod(start=start, end=start + timedelta(days=period_days - 1))


@dataclass(frozen=True)
class MealPoint:
    """A meal on a weekday: weekday follows date.weekday() (Mon=0 .. Sun=6)."""

    weekday: int
    slot: Slot

    @property
    def index(self) -> int:
        return self.weekday * len(SLOTS) + SLOTS.index(self.slot)


def in_window(day: date, slot: Slot, start: MealPoint, end: MealPoint) -> bool:
    """Whether a meal falls in a weekly window, both ends included. Windows may wrap past Sunday."""
    i = MealPoint(day.weekday(), slot).index
    a, b = start.index, end.index
    return a <= i <= b if a <= b else i >= a or i <= b
