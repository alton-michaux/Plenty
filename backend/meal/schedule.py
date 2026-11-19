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


def week_start(today: date, start_weekday: int) -> date:
    """The most recent `start_weekday` on or before today. Plenty's week starts the day the kids
    arrive (Wed by default), so one shopping trip covers one stay plus the solo days after it."""
    return today - timedelta(days=(today.weekday() - start_weekday) % 7)


@dataclass(frozen=True)
class PlannedSlot:
    day: date
    slot: Slot
    kids_home: bool
    servings: int  # default servings: 1 + kids when they're home


def week_slots(
    start: date, kids: int, kids_from: MealPoint, kids_to: MealPoint
) -> list[PlannedSlot]:
    """The meals to plan in a week: every dinner, plus lunch on days the kids are home for lunch
    but gone by dinner (their last day, when lunch is usually leftovers)."""
    out: list[PlannedSlot] = []
    for i in range(7):
        day = start + timedelta(days=i)
        home = {s: kids > 0 and in_window(day, s, kids_from, kids_to) for s in SLOTS}
        if home["lunch"] and not home["dinner"]:
            out.append(PlannedSlot(day, "lunch", True, 1 + kids))
        out.append(PlannedSlot(day, "dinner", home["dinner"], 1 + kids if home["dinner"] else 1))
    return out
