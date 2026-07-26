"""Governed multi-agent HVAC optimisation workflow.
LLM agents explain and recommend.  They never write to HVAC directly: every
request is validated by the deterministic Safety Supervisor before the HVAC
Control Layer can update EnergyPlus.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from statistics import mean, stdev
from typing import Any, Optional, TypedDict


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph

from agents.audit import (
    close_override,
    get_pending_override,
    initialise_audit_tables,
    log_anomalies,
    log_safety_event,
    log_trace,
    recent_energy_j,
)
from agents.operations import get_occupancy_forecast, get_tariff_state
from agents.prompts import (
    CARBON_AGENT_PROMPT,
    COMFORT_AGENT_PROMPT,
    COORDINATOR_PROMPT,
    ENERGY_AGENT_PROMPT,
    OCCUPANCY_AGENT_PROMPT,
    WEATHER_AGENT_PROMPT,
)
from agents.safety_supervisor import DEFAULT_SETPOINT_C, review_setpoint, validate_sensor_data
from mcp_server.tools import (
    tool_get_building_state,
    tool_log_decision,
    tool_run_simulation,
    tool_set_hvac_setpoint,
)
from sim_runner.eplus_interface import get_current_setpoint


MODEL_NAME = "qwen2.5:3b"
N_CYCLES = 1
llm = ChatOllama(model=MODEL_NAME, format="json")

class BuildingState(TypedDict, total=False):
    building_state: dict
    comfort_rec: Optional[dict]
    energy_rec: Optional[dict]
    weather_rec: Optional[dict]
    carbon_rec: Optional[dict]
    occupancy_rec: Optional[dict]
    final_decision: Optional[dict]
    safety_decision: Optional[dict]
    tariff: dict
    occupancy_forecast: dict
    sensor_anomalies: list[dict]
    cycle: int


def _float(value: Any, default: float = DEFAULT_SETPOINT_C) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ask_agent(system_prompt: str, context: dict) -> dict:
    """Get a structured recommendation and retain a safe, explainable fallback."""
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Operational context: {json.dumps(context, default=str)}"},
    ])
    try:
        payload = json.loads(response.content)
        if not isinstance(payload, dict):
            raise ValueError("agent response must be an object")
        return payload
    except (json.JSONDecodeError, ValueError, TypeError):
        return {
            "recommendation": DEFAULT_SETPOINT_C,
            "rationale": "Fallback recommendation: the model response was not valid structured data.",
        }


def _agent_context(state: BuildingState, agent: str) -> dict:
    data = state["building_state"]
    common = {"zone_temps": data.get("zone_temps", {}), "energy_kwh": data.get("energy_kwh")}
    contexts = {
        "comfort_agent": {**common, "zone_humidity": data.get("zone_humidity", {})},
        "energy_agent": {**common, "tariff": state["tariff"], "occupancy_forecast": state["occupancy_forecast"]},
        "weather_agent": {**common, "outdoor_temp_c": data.get("outdoor_temp_c")},
        "carbon_agent": {**common, "carbon_kg_co2": data.get("carbon_kg_co2"), "tariff": state["tariff"]},
        "occupancy_agent": {"occupancy_forecast": state["occupancy_forecast"], "zone_temps": data.get("zone_temps", {})},
    }
    return contexts[agent]


def _record_specialist(state: BuildingState, agent: str, prompt: str) -> BuildingState:
    context = _agent_context(state, agent)
    rec = _ask_agent(prompt, context)
    rec["recommendation"] = _float(rec.get("recommendation"))
    rec["rationale"] = str(rec.get("rationale", "No rationale was supplied."))
    state[agent.replace("_agent", "_rec")] = rec
    return state


def node_fetch_state(state: BuildingState) -> BuildingState:
    
    state["building_state"] = tool_get_building_state()
    

    state["tariff"] = get_tariff_state()
    state["occupancy_forecast"] = get_occupancy_forecast()
    return state


def node_validate_sensors(state: BuildingState) -> BuildingState:
    anomalies = validate_sensor_data(state["building_state"], recent_energy_j())
    state["sensor_anomalies"] = anomalies
    if anomalies:
        log_anomalies(state["cycle"], anomalies, state["building_state"])
        log_safety_event(state["cycle"], "sensor_fault", {
            "source": "Safety Supervisor", "requested_temp": None, "applied_temp": None,
            "approved": False, "anomalies": anomalies,
        })
        tool_log_decision("safety_supervisor", "; ".join(item["message"] for item in anomalies), "control blocked: sensor anomaly")
    return state


def route_after_validation(state: BuildingState) -> str:
    return "blocked" if state.get("sensor_anomalies") else "agents"


def node_comfort_agent(state: BuildingState) -> BuildingState:
   
    return _record_specialist(state, "comfort_agent", COMFORT_AGENT_PROMPT)


def node_energy_agent(state: BuildingState) -> BuildingState:
   
    return _record_specialist(state, "energy_agent", ENERGY_AGENT_PROMPT)


def node_weather_agent(state: BuildingState) -> BuildingState:
  
    return _record_specialist(state, "weather_agent", WEATHER_AGENT_PROMPT)


def node_carbon_agent(state: BuildingState) -> BuildingState:
   
    return _record_specialist(state, "carbon_agent", CARBON_AGENT_PROMPT)


def node_occupancy_agent(state: BuildingState) -> BuildingState:
   
    return _record_specialist(state, "occupancy_agent", OCCUPANCY_AGENT_PROMPT)


def _agreement(recommendations: list[float]) -> float:
    """100% when specialists agree; declines with spread across the 3 °C band."""
    if len(recommendations) < 2:
        return 0.0
    spread = stdev(recommendations)
    return round(max(0.0, min(100.0, 100.0 - spread / 3.0 * 100.0)), 1)


def _coordinator_explanation(recommendations: dict[str, dict], selected: float) -> str:
    values = {name: _float(item.get("recommendation")) for name, item in recommendations.items()}
    closest = min(values, key=lambda name: abs(values[name] - selected))
    disagreements = ", ".join(f"{name.replace('_', ' ')} {value:.1f} °C" for name, value in values.items())
    return (
        f"Selected {selected:.1f} °C because it is closest to the {closest.replace('_', ' ')} "
        f"recommendation while balancing the specialist range ({disagreements})."
    )


def node_coordinator(state: BuildingState) -> BuildingState:
    
    recommendations = {
        "comfort_agent": state["comfort_rec"],
        "energy_agent": state["energy_rec"],
        "weather_agent": state["weather_rec"],
        "carbon_agent": state["carbon_rec"],
        "occupancy_agent": state["occupancy_rec"],
    }
    response = _ask_agent(COORDINATOR_PROMPT, {
        "recommendations": recommendations,
        "tariff": state["tariff"],
        "occupancy_forecast": state["occupancy_forecast"],
    })
    values = [_float(item.get("recommendation")) for item in recommendations.values()]
    final_temp = _float(response.get("final_temp"), mean(values))
    agreement = _agreement(values)
    explanation = str(response.get("selection_reason") or _coordinator_explanation(recommendations, final_temp))
    decision = {
        "final_temp": final_temp,
        "rationale": str(response.get("rationale", "Coordinator balanced specialist recommendations.")),
        "selection_reason": explanation,
        "agreement_confidence": agreement,
    }
    state["final_decision"] = decision

    for name, rec in recommendations.items():
        recommendation = _float(rec.get("recommendation"))
        difference = final_temp - recommendation
        effect = "Selected without adjustment" if abs(difference) < 0.05 else f"Coordinator adjusted by {difference:+.1f} °C"
        log_trace(state["cycle"], name, _agent_context(state, name), rec["rationale"], recommendation,
                  agreement, effect, final_temp)
        tool_log_decision(name, rec["rationale"], f"recommended {recommendation:.1f}")
    log_trace(state["cycle"], "coordinator", {"recommendations": recommendations},
              f"{decision['rationale']} {explanation}", final_temp, agreement,
              "Submitted to Safety Supervisor for deterministic review.", final_temp)
    tool_log_decision("coordinator", f"{decision['rationale']} {explanation}", f"final_temp={final_temp:.1f}")
    return state


def node_safety_supervisor(state: BuildingState) -> BuildingState:
   
    override = get_pending_override()
    requested = state["final_decision"]["final_temp"]
    source = "coordinator"
    if override and override["action"] == "override":
        requested, source = override["requested_temp"], "facility_manager"
    elif override and override["action"] == "accept_ai":
        source = "facility_manager_acceptance"
    decision = review_setpoint(
        requested,
        state["building_state"],
        previous_setpoint=get_current_setpoint() or DEFAULT_SETPOINT_C,
        historical_energy_j=recent_energy_j(),
        source=source,
    )
    if override:
        close_override(override["id"], decision)
        decision["facility_manager_reason"] = override["reason"]
    state["safety_decision"] = decision
    log_safety_event(state["cycle"], "approval" if decision["approved"] else "block", decision)
    rationale = "; ".join(decision["overrides"]) or "All deterministic safety checks passed."
    tool_log_decision("safety_supervisor", rationale, "approved" if decision["approved"] else "blocked")
    log_trace(state["cycle"], "safety_supervisor", {
        "requested_temp": requested,
        "previous_setpoint": get_current_setpoint() or DEFAULT_SETPOINT_C,
        "sensor_anomalies": state.get("sensor_anomalies", []),
    }, rationale, decision.get("applied_temp"), 100.0 if decision["approved"] else 0.0,
              "HVAC Control Layer enabled." if decision["approved"] else "HVAC Control Layer blocked.",
              decision.get("applied_temp"))
    return state


def route_after_safety(state: BuildingState) -> str:
    
    return "apply" if state.get("safety_decision", {}).get("approved") else "blocked"


def node_hvac_control(state: BuildingState) -> BuildingState:
    """The only node permitted to change the EnergyPlus cooling schedule."""
    applied_temp = state["safety_decision"]["applied_temp"]
    tool_set_hvac_setpoint("Core_mid", applied_temp)
    new_state = tool_run_simulation()
    temperatures = [
        float(value) for zone, value in new_state.get("zone_temps", {}).items()
        if "PLENUM" not in str(zone).upper()
    ]
    comfort_score_pct = None
    if temperatures:
        comfort_score_pct = 100.0 * sum(21.0 <= value <= 24.0 for value in temperatures) / len(temperatures)
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "results.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ai_results (
            timestamp TEXT, cycle INTEGER, energy_kw REAL, final_temp REAL, raw_state TEXT
        )""")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_results)")}
        if "comfort_score_pct" not in columns:
            conn.execute("ALTER TABLE ai_results ADD COLUMN comfort_score_pct REAL")
        conn.execute("""INSERT INTO ai_results
            (timestamp, cycle, energy_kw, final_temp, raw_state, comfort_score_pct)
            VALUES (?, ?, ?, ?, ?, ?)""", (
            datetime.now().isoformat(), state["cycle"],
            new_state.get("energy_j", new_state.get("energy_kw")), applied_temp, str(new_state), comfort_score_pct,
        ))
    tool_log_decision("hvac_controller", "Safety-approved setpoint applied to the EnergyPlus control schedule.",
                      f"applied {applied_temp:.1f} °C")
    return state


def build_graph():
    graph = StateGraph(BuildingState)
    graph.add_node("fetch_state", node_fetch_state)
    graph.add_node("validate_sensors", node_validate_sensors)
    graph.add_node("comfort_agent", node_comfort_agent)
    graph.add_node("energy_agent", node_energy_agent)
    graph.add_node("weather_agent", node_weather_agent)
    graph.add_node("carbon_agent", node_carbon_agent)
    graph.add_node("occupancy_agent", node_occupancy_agent)
    graph.add_node("coordinator", node_coordinator)
    graph.add_node("safety_supervisor", node_safety_supervisor)
    graph.add_node("hvac_controller", node_hvac_control)
    graph.set_entry_point("fetch_state")
    graph.add_edge("fetch_state", "validate_sensors")
    graph.add_conditional_edges("validate_sensors", route_after_validation, {"agents": "comfort_agent", "blocked": END})
    graph.add_edge("comfort_agent", "energy_agent")
    graph.add_edge("energy_agent", "weather_agent")
    graph.add_edge("weather_agent", "carbon_agent")
    graph.add_edge("carbon_agent", "occupancy_agent")
    graph.add_edge("occupancy_agent", "coordinator")
    graph.add_edge("coordinator", "safety_supervisor")
    graph.add_conditional_edges("safety_supervisor", route_after_safety, {"apply": "hvac_controller", "blocked": END})
    graph.add_edge("hvac_controller", END)
    return graph.compile()


def run_one_cycle(cycle: int = 0) -> BuildingState:
    """Run one complete governed cycle; used by the CLI and facility-manager UI."""
    initialise_audit_tables()
    app = build_graph()
    return app.invoke({"cycle": cycle, "building_state": {}, "sensor_anomalies": []})


def run_loop():
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"), exist_ok=True)
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "energyplus", "current_run", "eplusout.csv")
    if not os.path.exists(csv_path):
        print("Running bootstrap simulation...")
        tool_run_simulation()
    for cycle in range(N_CYCLES):
        print(f"\n=== Governed cycle {cycle + 1}/{N_CYCLES} ===")
        result = run_one_cycle(cycle)
        print("Safety decision:", result.get("safety_decision", {"status": "blocked before AI"}))
    print("\nMulti-agent loop complete. Review data/results.db and the dashboard audit trail.")


if __name__ == "__main__":
    run_loop()


