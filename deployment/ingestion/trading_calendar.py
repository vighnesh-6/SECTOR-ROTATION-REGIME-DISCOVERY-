"""Reviewed NSE cash-market calendar, independent of frozen research artifacts.

Sources (reviewed 2026-11-09):
https://www.nseindia.com/resources/exchange-communication-holidays?apiversion=v2
https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf

Fail closed outside the reviewed year. This is an operational calendar, not a
change to signals, features, execution rules, or portfolio construction.
"""
from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
COVERED_YEAR = 2026
HOLIDAYS = frozenset(date.fromisoformat(d) for d in (
    "2026-01-15", "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26",
    "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24",
    "2026-12-25",
))
SPECIAL_SESSIONS = frozenset((date(2026, 11, 8),))
# Conservative data-collection eligibility, not an asserted exchange close.
# The existing scheduled runs begin at 19:00 IST.
COLLECTION_CUTOFF = time(18, 30)


class CalendarCoverageError(ValueError):
    pass


class TradingCalendar:
    def is_session(self, day: date) -> bool:
        if day.year != COVERED_YEAR:
            raise CalendarCoverageError("NSE calendar year is not reviewed; collection is blocked")
        return day in SPECIAL_SESSIONS or (day.weekday() < 5 and day not in HOLIDAYS)

    def sessions(self, first: date, last: date):
        result = []
        while first <= last:
            if self.is_session(first):
                result.append(first)
            first += timedelta(days=1)
        return result

    def next_session(self, day: date) -> date:
        day += timedelta(days=1)
        while not self.is_session(day):
            day += timedelta(days=1)
        return day

    def latest_completed_session(self, now: datetime) -> date:
        if now.tzinfo is None:
            raise ValueError("An aware clock is required")
        local = now.astimezone(IST)
        day = local.date()
        if local.time() < COLLECTION_CUTOFF:
            day -= timedelta(days=1)
        while not self.is_session(day):
            day -= timedelta(days=1)
        return day
