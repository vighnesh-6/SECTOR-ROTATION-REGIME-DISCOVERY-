"""Explicit IST clock, independent of host timezone and tzdata installation."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def now_ist():
    return datetime.now(IST)
