from datetime import date

import pytest

from meal.schedule import MealPoint, in_window, pay_period

ANCHOR = date(2026, 11, 6)  # a Friday payday


@pytest.mark.parametrize(
    ("today", "start", "end"),
    [
        (date(2026, 11, 6), date(2026, 11, 6), date(2026, 11, 19)),  # payday itself
        (date(2026, 11, 16), date(2026, 11, 6), date(2026, 11, 19)),
        (date(2026, 11, 19), date(2026, 11, 6), date(2026, 11, 19)),  # last day
        (date(2026, 11, 20), date(2026, 11, 20), date(2026, 12, 3)),  # next payday
        (date(2026, 11, 5), date(2026, 10, 23), date(2026, 11, 5)),  # before the anchor
    ],
)
def test_pay_period(today, start, end):
    p = pay_period(today, ANCHOR)
    assert (p.start, p.end) == (start, end)
    assert p.length == 14


def test_pay_period_day_number():
    p = pay_period(date(2026, 11, 16), ANCHOR)
    assert p.day_number(date(2026, 11, 6)) == 1
    assert p.day_number(date(2026, 11, 16)) == 11
    assert p.next_payday == date(2026, 11, 20)


def test_pay_period_rejects_zero_length():
    with pytest.raises(ValueError):
        pay_period(ANCHOR, ANCHOR, 0)


# Kids from Wednesday dinner through Saturday lunch
WED_DINNER, SAT_LUNCH = MealPoint(2, "dinner"), MealPoint(5, "lunch")
WED, THU, SAT, SUN = date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 21), date(2026, 11, 22)


@pytest.mark.parametrize(
    ("day", "slot", "home"),
    [
        (WED, "lunch", False),
        (WED, "dinner", True),
        (THU, "breakfast", True),
        (SAT, "lunch", True),
        (SAT, "dinner", False),
        (SUN, "dinner", False),
    ],
)
def test_kid_window(day, slot, home):
    assert in_window(day, slot, WED_DINNER, SAT_LUNCH) is home


def test_window_wraps_past_sunday():
    fri_dinner, mon_breakfast = MealPoint(4, "dinner"), MealPoint(0, "breakfast")
    assert in_window(SUN, "lunch", fri_dinner, mon_breakfast)
    assert in_window(date(2026, 11, 23), "breakfast", fri_dinner, mon_breakfast)  # Monday
    assert not in_window(date(2026, 11, 23), "lunch", fri_dinner, mon_breakfast)
    assert not in_window(WED, "dinner", fri_dinner, mon_breakfast)
