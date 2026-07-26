"""Deterministic operational context used by the LangGraph workflow.

These helpers deliberately do not call an LLM.  They make the tariff and
occupancy assumptions visible, testable, and easy to replace with production
feeds later.
"""

from __future__ import annotations

from datetime import datetime, timedelta


TARIFFS = {
    "off_peak": {"label": "Off-peak", "rate_usd_per_kwh": 0.09},
    "normal": {"label": "Normal", "rate_usd_per_kwh": 0.15},
    "peak": {"label": "Peak", "rate_usd_per_kwh": 0.25},
}


def get_tariff_state(when: datetime | None = None) -> dict:
    """Return the active demonstration tariff using an explicit local schedule.

    Weekdays 14:00–20:00 are peak, 22:00–06:00 are off-peak, and the
    remaining hours are normal.  The value is an operational simulation input,
    not a claim about a specific utility tariff.
    """
    now = when or datetime.now()
    if now.weekday() < 5 and 14 <= now.hour < 20:
        key = "peak"
    elif now.hour >= 22 or now.hour < 6:
        key = "off_peak"
    else:
        key = "normal"
    return {"key": key, "timestamp": now.isoformat(), **TARIFFS[key]}


def get_occupancy_forecast(when: datetime | None = None) -> dict:
    """Return a lightweight, transparent office-hours occupancy forecast.

    The forecast enables pre-conditioning for a weekday 08:00 start.  It is a
    schedule-based model only; it must be replaced by approved occupancy data
    before operational deployment.
    """
    now = when or datetime.now()
    is_weekday = now.weekday() < 5
    occupied = is_weekday and 8 <= now.hour < 18
    next_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if not is_weekday or now >= next_start:
        days_ahead = 1
        next_start += timedelta(days=days_ahead)
        while next_start.weekday() >= 5:
            next_start += timedelta(days=1)
    minutes_to_start = int((next_start - now).total_seconds() // 60)
    precondition = is_weekday and 0 < minutes_to_start <= 60
    if occupied:
        expected = 100
        strategy = "Maintain the thermal comfort target for occupied operation."
    elif precondition:
        expected = 70
        strategy = "Pre-condition ahead of the scheduled occupancy start."
    else:
        expected = 5
        strategy = "Use an energy-conserving unoccupied strategy."
    return {
        "model": "weekday office-hours schedule",
        "occupied_now": occupied,
        "expected_occupancy_pct": expected,
        "next_occupied_start": next_start.isoformat(),
        "minutes_to_next_start": max(0, minutes_to_start),
        "preconditioning_recommended": precondition,
        "strategy": strategy,
    }
