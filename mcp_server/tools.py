"""
tools.py — the actual logic behind each MCP tool.
Kept separate from server.py so you can unit-test these functions directly
without going through the MCP protocol layer.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_runner.eplus_interface import get_building_state, apply_setpoints, get_current_setpoint, run_simulation
from agents.audit import log_safety_event, recent_energy_j
from agents.safety_supervisor import DEFAULT_SETPOINT_C, review_setpoint

# Store the last known baseline energy value once you've run Phase 4,
# so agents can reference it for context (optional, nice for prompts).
BASELINE_ENERGY_KW = None


def tool_get_building_state() -> dict:
    """Returns current zone temps, humidity, and energy demand."""
    return get_building_state()


def tool_set_hvac_setpoint(zone: str, temp: float) -> dict:
    """Set a cooling setpoint only after deterministic safety review.

    This keeps direct MCP callers and the legacy single-agent test loop behind
    the same interlock as the LangGraph workflow.  The governed workflow logs
    the full audit event before it reaches this transport-level guard.
    """
    decision = review_setpoint(
        temp,
        get_building_state(),
        previous_setpoint=get_current_setpoint(zone=zone) or DEFAULT_SETPOINT_C,
        historical_energy_j=recent_energy_j(),
        source="mcp_hvac_guard",
    )
    log_safety_event(-1, "mcp_guard_approval" if decision["approved"] else "mcp_guard_block", decision)
    if not decision["approved"]:
        raise ValueError("HVAC command blocked by Safety Supervisor: " + "; ".join(decision["overrides"]))
    apply_setpoints(zone=zone, new_temp=decision["applied_temp"])
    return {"status": "ok", "zone": zone, "new_temp": decision["applied_temp"], "safety": decision}


def tool_run_simulation() -> dict:
    """Re-runs the simulation with current setpoints and returns new state."""
    run_simulation()
    return get_building_state()


def tool_get_energy_baseline() -> dict:
    """Returns the stored baseline energy figure for comparison, if set."""
    return {"baseline_energy_kw": BASELINE_ENERGY_KW}


def tool_log_decision(agent: str, rationale: str, action: str) -> dict:
    """Logs an agent's decision to SQLite for the dashboard's reasoning feed."""
    import sqlite3
    import datetime

    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "results.db"
    )
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_decisions (
            timestamp TEXT, agent TEXT, rationale TEXT, action TEXT
        )
    """)
    conn.execute(
        "INSERT INTO agent_decisions VALUES (?, ?, ?, ?)",
        (datetime.datetime.now().isoformat(), agent, rationale, action)
    )
    conn.commit()
    conn.close()
    return {"status": "logged"}
