"""Customer-independent date helpers for the tools."""

from datetime import date, timedelta

SPENDING_PERIODS = (
    "today", "yesterday", "this_week", "last_week", "this_month", "last_month",
    "last_7_days", "last_30_days", "this_year", "all",
)


def resolve_period(period: str, today: date | None = None) -> tuple[date | None, date | None]:
    """Map a named period to inclusive (since, until) dates; weeks start Monday."""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    return {
        "today": (today, today),
        "yesterday": (today - timedelta(days=1),) * 2,
        "this_week": (week_start, today),
        "last_week": (week_start - timedelta(days=7), week_start - timedelta(days=1)),
        "this_month": (month_start, today),
        "last_month": (last_month_end.replace(day=1), last_month_end),
        "last_7_days": (today - timedelta(days=6), today),
        "last_30_days": (today - timedelta(days=29), today),
        "this_year": (today.replace(month=1, day=1), today),
        "all": (None, None),
    }[period]


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def resolve_date(when: str, today: date | None = None) -> date | None:
    """Resolve an ISO date, 'today', 'tomorrow', 'this_<weekday>' or
    'next_<weekday>' (weekday in the current / next calendar week, weeks
    starting Monday) to a date; None if it cannot be parsed."""
    today = today or date.today()
    key = when.strip().lower().replace(" ", "_")
    if key == "today":
        return today
    if key == "tomorrow":
        return today + timedelta(days=1)
    for prefix, offset in (("this_", 0), ("next_", 7)):
        if key.startswith(prefix) and key[len(prefix):] in _WEEKDAYS:
            monday = today - timedelta(days=today.weekday())
            return monday + timedelta(days=offset + _WEEKDAYS.index(key[len(prefix):]))
    try:
        return date.fromisoformat(key)
    except ValueError:
        return None
