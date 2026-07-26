"""Deterministic validation and safety interlocks for HVAC recommendations.

This module is intentionally independent of LangChain, LangGraph, and Ollama.
It is the final authority before the HVAC control layer is allowed to update
the EnergyPlus schedule.
"""

from __future__ import annotations

import math
from statistics import mean
from typing import Any


MIN_SETPOINT_C = 21.0
MAX_SETPOINT_C = 24.0
MAX_CHANGE_PER_CYCLE_C = 1.0
DEFAULT_SETPOINT_C = 22.5
MIN_PLAUSIBLE_REQUEST_C = 10.0
MAX_PLAUSIBLE_REQUEST_C = 35.0
MIN_SENSOR_TEMP_C = 5.0
MAX_SENSOR_TEMP_C = 45.0
MAX_ENERGY_SPIKE_RATIO = 2.0


def _number(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def validate_sensor_data(state: dict, historical_energy_j: list[float] | None = None) -> list[dict]:
    """Return every observed data-quality anomaly; never silently repair data."""
    anomalies: list[dict] = []
    temperatures = state.get("zone_temps")
    if not isinstance(temperatures, dict) or not temperatures:
        anomalies.append({"code": "missing_zone_temperature", "message": "No zone temperature telemetry was provided."})
    else:
        for zone, raw in temperatures.items():
            value = _number(raw)
            if value is None:
                anomalies.append({"code": "invalid_temperature", "message": f"{zone}: temperature is not a finite number."})
            elif not MIN_SENSOR_TEMP_C <= value <= MAX_SENSOR_TEMP_C:
                anomalies.append({"code": "impossible_temperature", "message": f"{zone}: {value:.1f} °C is outside the plausible sensor range."})

    humidity = state.get("zone_humidity", {})
    if humidity is None:
        anomalies.append({"code": "invalid_humidity", "message": "Humidity telemetry is invalid."})
    elif isinstance(humidity, dict):
        for zone, raw in humidity.items():
            value = _number(raw)
            if value is None or not 0 <= value <= 100:
                anomalies.append({"code": "impossible_humidity", "message": f"{zone}: relative humidity must be between 0 and 100%."})
    else:
        anomalies.append({"code": "invalid_humidity", "message": "Humidity telemetry must be a zone-to-value mapping."})

    energy_j = _number(state.get("energy_j", state.get("energy_kw")))
    if energy_j is None:
        anomalies.append({"code": "missing_energy", "message": "Facility electricity telemetry is missing or invalid."})
    elif energy_j < 0:
        anomalies.append({"code": "impossible_energy", "message": "Facility electricity cannot be negative."})
    elif historical_energy_j:
        valid_history = [v for v in historical_energy_j if _number(v) is not None and v > 0]
        if valid_history and energy_j > mean(valid_history) * MAX_ENERGY_SPIKE_RATIO:
            anomalies.append({
                "code": "energy_spike",
                "message": f"Facility electricity is {energy_j / mean(valid_history):.1f}× the recent average.",
            })
    return anomalies


def review_setpoint(
    requested_temp: Any,
    state: dict,
    previous_setpoint: Any = DEFAULT_SETPOINT_C,
    historical_energy_j: list[float] | None = None,
    source: str = "coordinator",
) -> dict:
    """Apply deterministic interlocks and return an auditable decision.

    An invalid sensor state blocks control completely.  A valid request is
    clamped to the configured HVAC limits and rate-limited against the last
    applied setpoint.  The caller alone performs the actual HVAC write only
    when ``approved`` is true.
    """
    anomalies = validate_sensor_data(state, historical_energy_j)
    checks = [
        {"name": "Sensor data validation", "passed": not anomalies},
        {"name": f"HVAC bounds ({MIN_SETPOINT_C:.1f}–{MAX_SETPOINT_C:.1f} °C)", "passed": False},
        {"name": f"Maximum change ({MAX_CHANGE_PER_CYCLE_C:.1f} °C/cycle)", "passed": False},
    ]
    if anomalies:
        return {
            "approved": False,
            "source": source,
            "requested_temp": requested_temp,
            "applied_temp": None,
            "overrides": ["Control blocked because sensor data failed validation."],
            "anomalies": anomalies,
            "checks": checks,
        }

    requested = _number(requested_temp)
    if requested is None:
        return {
            "approved": False,
            "source": source,
            "requested_temp": requested_temp,
            "applied_temp": None,
            "overrides": ["Control blocked because the requested setpoint is not a finite number."],
            "anomalies": [{"code": "invalid_setpoint", "message": "Requested setpoint is not a finite number."}],
            "checks": checks,
        }

    if not MIN_PLAUSIBLE_REQUEST_C <= requested <= MAX_PLAUSIBLE_REQUEST_C:
        return {
            "approved": False,
            "source": source,
            "requested_temp": requested,
            "applied_temp": None,
            "overrides": ["Control blocked because the requested setpoint is physically implausible."],
            "anomalies": [{"code": "impossible_setpoint", "message": "Requested setpoint is outside the plausible HVAC range."}],
            "checks": checks,
        }

    previous = _number(previous_setpoint)
    if previous is None:
        previous = DEFAULT_SETPOINT_C
    overrides: list[str] = []
    bounded = min(MAX_SETPOINT_C, max(MIN_SETPOINT_C, requested))
    if bounded != requested:
        overrides.append(f"Setpoint limited to the HVAC operating range: {bounded:.1f} °C.")
    checks[1]["passed"] = True
    lower, upper = previous - MAX_CHANGE_PER_CYCLE_C, previous + MAX_CHANGE_PER_CYCLE_C
    applied = min(upper, max(lower, bounded))
    if applied != bounded:
        overrides.append(f"Setpoint change limited to {MAX_CHANGE_PER_CYCLE_C:.1f} °C from the previous applied value.")
    checks[2]["passed"] = True
    return {
        "approved": True,
        "source": source,
        "requested_temp": round(requested, 2),
        "applied_temp": round(applied, 2),
        "overrides": overrides,
        "anomalies": [],
        "checks": checks,
    }
