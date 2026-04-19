"""NYSE market hours check (including holidays)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import pandas_market_calendars as mcal
import pytz

logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")
_CAL = mcal.get_calendar("NYSE")


def is_us_market_open_window(as_of: datetime | None = None, post_close_hours: int = 1) -> bool:
    """Is `as_of` within market open → close + post_close_hours?

    Handles holidays (Thanksgiving, Christmas, July 4, etc.) via NYSE calendar.
    """
    now_et = (as_of or datetime.now(pytz.UTC)).astimezone(ET)

    schedule = _CAL.schedule(start_date=now_et.date(), end_date=now_et.date())
    if schedule.empty:
        return False

    market_open = schedule.iloc[0]["market_open"].tz_convert(ET)
    market_close = schedule.iloc[0]["market_close"].tz_convert(ET)
    window_end = market_close + pd.Timedelta(hours=post_close_hours)

    return market_open <= now_et <= window_end


def is_post_close_final_run(as_of: datetime | None = None) -> bool:
    """True if we're in the last hour of the post-close window (~17:00 ET).

    Used to decide whether to run `daily_final` mode with full scoring.
    """
    now_et = (as_of or datetime.now(pytz.UTC)).astimezone(ET)
    schedule = _CAL.schedule(start_date=now_et.date(), end_date=now_et.date())
    if schedule.empty:
        return False

    market_close = schedule.iloc[0]["market_close"].tz_convert(ET)
    # "Final" run = between close+30min and close+90min
    return (market_close + timedelta(minutes=30)) <= now_et <= (market_close + timedelta(minutes=90))


def current_trading_date_et(as_of: datetime | None = None):
    """ET date used for cross-day cooldown comparison."""
    now_et = (as_of or datetime.now(pytz.UTC)).astimezone(ET)
    return now_et.date()
