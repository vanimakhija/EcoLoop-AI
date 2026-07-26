"""EcoLoop-AI enterprise operations dashboard.

The dashboard reads auditable runtime data and can submit a facility-manager
decision. It never writes an HVAC setpoint directly; a submitted action runs
through the governed LangGraph workflow and Safety Supervisor.
"""

from __future__ import annotations

import html
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from statistics import stdev
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "results.db")
SUMMARY_PATH = os.path.join(DATA_DIR, "results_summary.json")
CSV_PATH = os.path.join(PROJECT_ROOT, "energyplus", "current_run", "eplusout.csv")
ERR_PATH = os.path.join(PROJECT_ROOT, "energyplus", "current_run", "eplusout.err")
ARCH_PNG = os.path.join(PROJECT_ROOT, "docs", "architecture.png")
EPLUS_EXE = os.path.join(r"C:\EnergyPlusV26-1-0", "energyplus.exe")
COMFORT_LOW_C, COMFORT_HIGH_C = 21.0, 24.0
CARBON_FACTOR_KG_PER_KWH = 0.386
NOT_AVAILABLE = "—"


st.set_page_config(
    page_title="EcoLoop-AI | Building Operations",
    page_icon="E",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --app-bg: #06111f;
        --panel: #0b1d31;
        --panel-strong: #102842;
        --panel-muted: #0b2238;
        --line: #244967;
        --line-bright: #39749c;
        --text: #f4f8fc;
        --text-soft: #c7d6e2;
        --muted: #9bb0c1;
        --cyan: #4cc9f0;
        --green: #48d597;
        --amber: #f9c74f;
        --red: #ff7187;
    }

    .stApp {
        background:
            radial-gradient(circle at 12% -12%, rgba(23, 84, 121, .56), transparent 32rem),
            radial-gradient(circle at 100% 0%, rgba(10, 89, 111, .22), transparent 28rem),
            var(--app-bg);
    }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"] { right: 1rem; }
    .block-container { max-width: 1600px; padding-top: 1.55rem; padding-bottom: 3rem; }

    h1, h2, h3 { color: var(--text) !important; letter-spacing: -.025em; }
    h1 { margin-bottom: .15rem !important; font-size: 2.1rem !important; font-weight: 700 !important; }
    h2 {
        margin-top: 1.75rem !important;
        padding: 0 0 .65rem !important;
        border-bottom: 1px solid var(--line);
        font-size: 1.28rem !important;
        font-weight: 650 !important;
    }
    h3 { font-size: 1rem !important; font-weight: 650 !important; }
    p, li, [data-testid="stCaptionContainer"] { color: var(--text-soft); }

    [data-testid="stMetric"] {
        min-height: 132px;
        padding: 1.05rem 1.1rem;
        background: linear-gradient(140deg, rgba(16, 40, 66, .98), rgba(8, 26, 44, .98));
        border: 1px solid var(--line);
        border-radius: 12px;
        box-shadow: 0 10px 24px rgba(0, 0, 0, .16);
    }
    [data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: .76rem; font-weight: 600; text-transform: uppercase; letter-spacing: .055em; }
    [data-testid="stMetricValue"] { color: var(--text) !important; font-size: 1.78rem; font-weight: 700; }
    [data-testid="stMetricDelta"] { color: var(--text-soft) !important; font-size: .78rem; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        overflow: hidden;
        min-width: 0;
        background: linear-gradient(145deg, rgba(13, 35, 57, .96), rgba(7, 22, 37, .98));
        border: 1px solid var(--line);
        border-radius: 13px;
        box-shadow: 0 12px 28px rgba(0, 0, 0, .18);
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div,
    [data-testid="stVerticalBlock"],
    [data-testid="column"] { min-width: 0; }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: var(--line-bright);
        box-shadow: 0 15px 32px rgba(0, 0, 0, .24);
    }

    [data-testid="stSidebar"] { background: #071526; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: var(--text-soft); }
    [data-testid="stSidebar"] h1 { font-size: 1.45rem !important; }

    .stButton > button, .stFormSubmitButton > button {
        min-height: 2.55rem;
        border: 1px solid #2b9dcc;
        border-radius: 8px;
        background: linear-gradient(135deg, #087db6, #0b6797);
        color: #ffffff;
        font-weight: 650;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover { background: #1299d3; border-color: #69d6f7; }
    .stSelectbox label, .stTextInput label, .stTextArea label, .stRadio label, .stNumberInput label { color: var(--text-soft) !important; }

    [data-testid="stDataFrame"] { overflow: auto !important; border: 1px solid var(--line); border-radius: 8px; }
    [data-testid="stDataFrame"] * { max-width: 100%; }
    [data-testid="stExpander"] {
        overflow: hidden;
        border: 1px solid var(--line) !important;
        border-radius: 8px !important;
        background: rgba(4, 16, 29, .42);
    }
    [data-testid="stExpander"] summary { color: var(--text-soft) !important; font-weight: 600; }
    [data-testid="stCode"], pre, code {
        max-width: 100% !important;
        box-sizing: border-box;
        font-family: 'IBM Plex Mono', monospace !important;
    }
    pre { white-space: pre-wrap !important; overflow-wrap: anywhere !important; word-break: break-word !important; overflow-x: auto !important; }
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] div {
        max-width: 100%; overflow-wrap: anywhere; word-break: break-word;
    }
    .stTabs [data-baseweb="tab-list"] { gap: .45rem; }
    .stTabs [data-baseweb="tab"] { color: var(--muted); border-radius: 7px; font-weight: 600; }
    .stTabs [aria-selected="true"] { color: var(--text) !important; background: rgba(76, 201, 240, .12); }
    .stProgress > div > div > div > div { background-color: var(--cyan); }

    .eyebrow { margin: 0 0 .35rem; color: var(--cyan); font-size: .72rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
    .page-subtitle { margin: 0; color: var(--text-soft); font-size: .98rem; }
    .section-intro { margin: -.1rem 0 .95rem; color: var(--muted); font-size: .9rem; }
    .agent-title { margin: 0; color: var(--text); font-size: 1.08rem; font-weight: 700; }
    .agent-role { margin-top: .2rem; color: var(--muted); font-size: .82rem; }
    .field-label { margin: .55rem 0 .36rem; color: #9fcce0; font-size: .7rem; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; }
    .reasoning-copy, .effect-copy {
        padding: .78rem .88rem;
        border-left: 3px solid var(--cyan);
        border-radius: 0 8px 8px 0;
        background: rgba(10, 36, 58, .74);
        color: var(--text) !important;
        font-size: .91rem;
        line-height: 1.55;
    }
    .effect-copy { border-left-color: var(--green); background: rgba(12, 52, 48, .42); }
    .flow-step {
        min-height: 76px;
        padding: .75rem .8rem;
        border: 1px solid var(--line);
        border-radius: 9px;
        background: rgba(10, 34, 55, .62);
    }
    .flow-step strong { display: block; color: var(--text); font-size: .86rem; }
    .flow-step span { display: block; margin-top: .2rem; color: var(--muted); font-size: .76rem; line-height: 1.3; }
    .status-note { color: var(--text-soft); font-size: .86rem; }
    .architecture-flow { display: flex; flex-direction: column; gap: .25rem; max-width: 940px; margin: .3rem auto 0; }
    .architecture-node {
        display: flex; align-items: center; gap: .75rem; min-height: 38px; padding: .46rem .72rem;
        border: 1px solid var(--line); border-radius: 8px; background: linear-gradient(90deg, rgba(16, 48, 75, .86), rgba(8, 29, 48, .74));
        color: var(--text); font-size: .86rem; font-weight: 650;
    }
    .architecture-icon, .decision-icon { display: inline-flex; align-items: center; justify-content: center; flex: 0 0 25px; color: var(--cyan); font-size: 1rem; }
    .architecture-arrow, .decision-arrow { color: var(--cyan); text-align: center; font-size: 1.05rem; font-weight: 700; line-height: .95; }
    .decision-summary { padding: .15rem 0 .2rem; }
    .decision-signal {
        min-height: 100px; padding: .72rem .55rem; border: 1px solid var(--line); border-radius: 9px;
        background: rgba(9, 33, 54, .7); text-align: center;
    }
    .decision-signal span { display: block; color: var(--text-soft); font-size: .75rem; line-height: 1.25; }
    .decision-signal .decision-icon { margin: 0 auto .3rem; color: var(--cyan); font-size: 1.15rem; }
    .decision-signal strong { display: block; margin-top: .4rem; color: var(--text); font-size: .92rem; }
    .decision-final {
        min-height: 86px; padding: .72rem; border: 1px solid #2c637f; border-radius: 9px;
        background: linear-gradient(145deg, rgba(12, 57, 72, .72), rgba(10, 33, 53, .88)); text-align: center;
    }
    .decision-final span { display: block; color: #aad6e7; font-size: .72rem; font-weight: 700; letter-spacing: .055em; text-transform: uppercase; }
    .decision-final strong { display: block; margin-top: .42rem; color: var(--text); font-size: 1rem; }
    .timeline { display: flex; align-items: stretch; gap: .45rem; }
    .timeline-step { flex: 1; padding: .7rem .55rem; border: 1px solid var(--line); border-radius: 9px; background: rgba(10, 34, 55, .6); text-align: center; }
    .timeline-step b { display: block; color: var(--cyan); font-size: 1.05rem; }
    .timeline-step span { display: block; margin-top: .25rem; color: var(--text-soft); font-size: .76rem; font-weight: 600; line-height: 1.25; }
    .outcome-item { padding: .65rem .75rem; border: 1px solid rgba(72, 213, 151, .45); border-radius: 8px; background: rgba(18, 74, 59, .38); color: #dcf9ea; font-size: .84rem; font-weight: 650; text-align: center; }

    @media (max-width: 760px) {
        .block-container { padding: 1rem .75rem 2rem; }
        h1 { font-size: 1.72rem !important; }
        [data-testid="stMetric"] { min-height: 104px; }
        .timeline { flex-direction: column; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def db_table(table: str, limit: int = 1000) -> pd.DataFrame:
    """Read dashboard data without changing any governed-system state."""
    allowed = {
        "agent_decisions",
        "ai_results",
        "baseline_results",
        "decision_trace",
        "safety_events",
        "sensor_anomalies",
        "facility_overrides",
    }
    if table not in allowed or not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", conn, params=(limit,))
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()


@st.cache_data(ttl=15)
def load_summary() -> dict[str, Any]:
    try:
        with open(SUMMARY_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def friendly_zone_name(value: object) -> str:
    """Convert EnergyPlus zone/sensor identifiers into labels for operators."""
    raw = str(value).split(":", 1)[0].strip().upper()
    direct_names = {
        "CORE_BOTTOM": "Core Bottom",
        "CORE_MID": "Core Mid",
        "CORE_TOP": "Core Top",
        "FIRSTFLOOR_PLENUM": "First Floor Plenum",
        "MIDFLOOR_PLENUM": "Mid Floor Plenum",
        "TOPFLOOR_PLENUM": "Top Floor Plenum",
    }
    if raw in direct_names:
        return direct_names[raw]

    perimeter_match = re.fullmatch(r"PERIMETER_(BOT|MID|TOP)_ZN_(\d+)", raw)
    if perimeter_match:
        level = {"BOT": "Bottom", "MID": "Mid", "TOP": "Top"}[perimeter_match.group(1)]
        return f"Perimeter {level} Zone {perimeter_match.group(2)}"

    token_names = {
        "BOT": "Bottom",
        "MID": "Mid",
        "TOP": "Top",
        "ZN": "Zone",
        "PLENUM": "Plenum",
        "FIRSTFLOOR": "First Floor",
        "MIDFLOOR": "Mid Floor",
        "TOPFLOOR": "Top Floor",
    }
    words = [token_names.get(token, token.title()) for token in raw.replace("-", "_").split("_") if token]
    return " ".join(words) or "Unknown Zone"


def friendly_sensor_name(value: object) -> str:
    """Provide a readable label even when a full EnergyPlus sensor name is supplied."""
    zone = friendly_zone_name(value)
    sensor_text = str(value).split(":", 1)[-1].lower()
    if "temperature" in sensor_text and not zone.lower().endswith("temperature"):
        return f"{zone} Temperature"
    return zone


def friendly_label(value: object) -> str:
    labels = {
        "zone_temps": "Zone temperatures",
        "energy_kwh": "Facility energy",
        "energy_j": "Facility energy",
        "carbon_kg_co2": "Estimated carbon",
        "outdoor_temp_c": "Outdoor dry-bulb",
        "occupancy_forecast": "Occupancy forecast",
        "expected_occupancy_pct": "Expected occupancy",
        "next_occupied_start": "Next scheduled occupancy",
        "preconditioning_recommended": "Pre-conditioning",
        "rate_usd_per_kwh": "Energy rate",
        "requested_temp": "Requested setpoint",
        "previous_setpoint": "Previous setpoint",
        "sensor_anomalies": "Sensor anomalies",
        "recommendations": "Agent recommendations",
    }
    key = str(value)
    return labels.get(key, key.replace("_", " ").strip().title())


@st.cache_data(ttl=15)
def load_sensor_state() -> tuple[dict[str, float], float | None, float | None]:
    if not os.path.exists(CSV_PATH):
        return {}, None, None
    try:
        frame = pd.read_csv(CSV_PATH)
        if frame.empty:
            return {}, None, None
        last = frame.iloc[-1]
        temperatures = {
            friendly_zone_name(col): float(last[col])
            for col in frame.columns
            if "zone mean air temperature" in col.lower() and pd.notna(last[col])
        }
        energy_columns = [
            col for col in frame.columns
            if ("electricity:facility" in col.lower() or "facility total electricity" in col.lower()) and pd.notna(last[col])
        ]
        monthly_energy_column = next((col for col in energy_columns if "monthly" in col.lower()), None)
        selected_energy_column = monthly_energy_column or (energy_columns[0] if energy_columns else None)
        energy_j = float(last[selected_energy_column]) if selected_energy_column else None
        outdoor_c = next(
            (
                float(last[col])
                for col in frame.columns
                if "site outdoor air drybulb temperature" in col.lower() and pd.notna(last[col])
            ),
            None,
        )
        return temperatures, energy_j, outdoor_c
    except (OSError, ValueError, pd.errors.ParserError):
        return {}, None, None


@st.cache_data(ttl=15)
def simulation_status() -> tuple[str, str, float | None]:
    if not os.path.exists(ERR_PATH):
        return "warning", "No completed simulation output", None
    try:
        text = open(ERR_PATH, encoding="utf-8", errors="ignore").read()
    except OSError:
        return "error", "Simulation log cannot be read", None
    seconds = None
    match = re.search(r"Elapsed Time[^\d]*([\d.]+)\s*seconds", text, re.IGNORECASE)
    if match:
        seconds = float(match.group(1))
    if "Completed Successfully" in text:
        return "healthy", "Last simulation completed successfully", seconds
    if "Fatal" in text:
        return "error", "EnergyPlus reported a fatal error", seconds
    return "warning", "Simulation status is incomplete", seconds


def energy_kwh(value_j: float | None) -> float | None:
    return float(value_j) / 3_600_000 if value_j is not None else None


def fmt_energy_kwh(value_kwh: object) -> str:
    try:
        value = float(value_kwh)
    except (TypeError, ValueError):
        return NOT_AVAILABLE
    if pd.isna(value):
        return NOT_AVAILABLE
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.2f} GWh"
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.2f} MWh"
    return f"{value:,.1f} kWh"


def fmt_energy(value_j: float | None) -> str:
    value = energy_kwh(value_j)
    return fmt_energy_kwh(value) if value is not None else NOT_AVAILABLE


def as_float(value: object) -> float | None:
    try:
        parsed = float(value)
        return None if pd.isna(parsed) else parsed
    except (TypeError, ValueError):
        return None


def present_text(value: object, fallback: str = "Not available.") -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text and text.lower() != "nan" else fallback


def parse_trace_input(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        decoded = json.loads(str(value))
        return decoded if isinstance(decoded, dict) else {"value": decoded}
    except (json.JSONDecodeError, TypeError):
        return {"unparsed_input": present_text(value, "")}


def raw_json(value: object) -> str:
    try:
        return json.dumps(value, indent=2, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return present_text(value, "{}")


def zone_temperature_frame(zone_temps: object, *, include_plenums: bool = True) -> pd.DataFrame:
    if not isinstance(zone_temps, dict):
        return pd.DataFrame(columns=["Zone", "Temperature (°C)"])
    rows = []
    for name, temperature in zone_temps.items():
        numeric_temperature = as_float(temperature)
        if numeric_temperature is None:
            continue
        readable_name = friendly_zone_name(name)
        if not include_plenums and "PLENUM" in readable_name.upper():
            continue
        rows.append({"Zone": readable_name, "Temperature (°C)": round(numeric_temperature, 1)})
    if not rows:
        return pd.DataFrame(columns=["Zone", "Temperature (°C)"])
    return pd.DataFrame(rows).sort_values("Temperature (°C)", kind="stable").reset_index(drop=True)


def latest_cycle_trace(trace: pd.DataFrame) -> pd.DataFrame:
    if trace.empty or "agent" not in trace:
        return pd.DataFrame()
    expected = {
        "comfort_agent",
        "energy_agent",
        "weather_agent",
        "carbon_agent",
        "occupancy_agent",
        "coordinator",
        "safety_supervisor",
    }
    recent = trace[trace["agent"].isin(expected)].head(7).copy()
    return recent.sort_values("id") if not recent.empty and "id" in recent else recent.iloc[::-1]


def actual_agreement(trace: pd.DataFrame) -> float | None:
    specialist = trace[trace["agent"].isin(["comfort_agent", "energy_agent", "weather_agent", "carbon_agent", "occupancy_agent"])]
    values = pd.to_numeric(specialist.get("recommendation", pd.Series(dtype=float)), errors="coerce").dropna().tolist()
    if len(values) < 2:
        return None
    return max(0.0, min(100.0, 100.0 - stdev(values) / 3.0 * 100.0))


def active_operational_context() -> tuple[dict[str, Any], dict[str, Any]]:
    from agents.operations import get_occupancy_forecast, get_tariff_state

    return get_tariff_state(), get_occupancy_forecast()


def monitor_rows(sim_state: str, trace: pd.DataFrame, safety: pd.DataFrame) -> pd.DataFrame:
    installed = os.path.exists(EPLUS_EXE)
    mcp_source = os.path.exists(os.path.join(PROJECT_ROOT, "mcp_server", "server.py"))
    graph_source = os.path.exists(os.path.join(PROJECT_ROOT, "agents", "graph.py"))
    ollama_store = os.path.exists(os.path.join(os.path.expanduser("~"), ".ollama", "models"))
    checks = [
        ("EnergyPlus", "Healthy" if installed and sim_state == "healthy" else "Warning", "Installed and latest run verified" if installed else "Executable not found"),
        ("MCP", "Warning" if mcp_source else "Error", "Source present; process health is not probed" if mcp_source else "Server source not found"),
        ("LangGraph", "Warning" if graph_source else "Error", "Source present; workflow execution is not confirmed" if graph_source else "Workflow source not found"),
        ("Ollama", "Warning" if ollama_store else "Error", "Model store detected; runtime and model are not probed" if ollama_store else "Local model store not found"),
        ("Agents", "Healthy" if not trace.empty else "Warning", "Auditable decision trace available" if not trace.empty else "No decisions logged"),
        ("Simulation", "Healthy" if sim_state == "healthy" else sim_state.title(), "EnergyPlus runtime status"),
        ("HVAC Control Layer", "Healthy" if not safety.empty else "Warning", "Safety Supervisor audit available" if not safety.empty else "No safety event logged"),
    ]
    return pd.DataFrame(checks, columns=["Component", "Status", "Evidence"])


def next_cycle_number() -> int:
    results = db_table("ai_results", limit=10000)
    if results.empty or "cycle" not in results:
        return 0
    values = pd.to_numeric(results["cycle"], errors="coerce").dropna()
    return int(values.max() + 1) if not values.empty else 0


def agent_label(agent: str) -> str:
    labels = {
        "comfort_agent": "Comfort Agent",
        "energy_agent": "Energy Agent",
        "weather_agent": "Weather Agent",
        "carbon_agent": "Carbon Agent",
        "occupancy_agent": "Occupancy Agent",
        "coordinator": "Decision Coordinator",
        "safety_supervisor": "Safety Supervisor",
    }
    return labels.get(agent, agent.replace("_", " ").title())


def agent_role(agent: str) -> str:
    roles = {
        "comfort_agent": "Thermal comfort assessment",
        "energy_agent": "Energy and tariff optimisation",
        "weather_agent": "Weather-aware operating context",
        "carbon_agent": "Carbon-impact assessment",
        "occupancy_agent": "Occupancy-led operating strategy",
        "coordinator": "Balances specialist recommendations",
        "safety_supervisor": "Deterministic control validation",
    }
    return roles.get(agent, "Decision support")


def format_temperature(value: object) -> str:
    numeric = as_float(value)
    return f"{numeric:.1f} °C" if numeric is not None else NOT_AVAILABLE


def context_table(rows: list[tuple[str, str]]) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows, columns=["Signal", "Current value"]), use_container_width=True, hide_index=True)


def render_zone_input_summary(zone_temps: object) -> None:
    frame = zone_temperature_frame(zone_temps)
    if frame.empty:
        return
    values = frame["Temperature (°C)"]
    metric_columns = st.columns(3)
    metric_columns[0].metric("Zones", str(len(frame)))
    metric_columns[1].metric("Average", f"{values.mean():.1f} °C")
    metric_columns[2].metric("Range", f"{values.min():.1f}–{values.max():.1f} °C")
    st.markdown("<div class='field-label'>Zone temperatures</div>", unsafe_allow_html=True)
    st.dataframe(frame, use_container_width=True, hide_index=True, height=min(330, 74 + len(frame) * 35))


def render_recommendation_input_summary(recommendations: object) -> None:
    if not isinstance(recommendations, dict) or not recommendations:
        return
    rows: list[dict[str, object]] = []
    proposals: list[float] = []
    for name, detail in recommendations.items():
        recommendation = detail.get("recommendation") if isinstance(detail, dict) else detail
        numeric = as_float(recommendation)
        if numeric is not None:
            proposals.append(numeric)
        rows.append({"Specialist": agent_label(str(name)), "Proposed setpoint (°C)": None if numeric is None else round(numeric, 1)})
    if proposals:
        metric_columns = st.columns(3)
        metric_columns[0].metric("Specialist signals", str(len(proposals)))
        metric_columns[1].metric("Average proposal", f"{sum(proposals) / len(proposals):.1f} °C")
        metric_columns[2].metric("Proposal span", f"{min(proposals):.1f}–{max(proposals):.1f} °C")
    st.markdown("<div class='field-label'>Specialist proposals</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_agent_input_summary(agent: str, input_data: dict[str, Any]) -> None:
    """Render compact, operator-friendly agent inputs; raw payload stays collapsed."""
    if agent == "coordinator":
        render_recommendation_input_summary(input_data.get("recommendations"))
        return

    if "zone_temps" in input_data:
        render_zone_input_summary(input_data.get("zone_temps"))

    if agent == "safety_supervisor":
        anomalies = input_data.get("sensor_anomalies", [])
        anomaly_count = len(anomalies) if isinstance(anomalies, list) else 0
        safety_metrics = st.columns(3)
        safety_metrics[0].metric("Requested setpoint", format_temperature(input_data.get("requested_temp")))
        safety_metrics[1].metric("Previous setpoint", format_temperature(input_data.get("previous_setpoint")))
        safety_metrics[2].metric("Active anomalies", str(anomaly_count))
        return

    rows: list[tuple[str, str]] = []
    energy = input_data.get("energy_kwh")
    if energy is not None:
        rows.append(("Facility energy", fmt_energy_kwh(energy)))
    carbon = as_float(input_data.get("carbon_kg_co2"))
    if carbon is not None:
        rows.append(("Estimated carbon", f"{carbon:,.1f} kg CO₂"))
    outdoor = as_float(input_data.get("outdoor_temp_c"))
    if outdoor is not None:
        rows.append(("Outdoor dry-bulb", f"{outdoor:.1f} °C"))

    tariff = input_data.get("tariff")
    if isinstance(tariff, dict):
        label = present_text(tariff.get("label"), "Normal")
        rate = as_float(tariff.get("rate_usd_per_kwh"))
        rows.append(("Current tariff", label if rate is None else f"{label} (${rate:.2f}/kWh)"))

    occupancy = input_data.get("occupancy_forecast")
    if isinstance(occupancy, dict):
        expected = as_float(occupancy.get("expected_occupancy_pct"))
        if expected is not None:
            rows.append(("Expected occupancy", f"{expected:.0f}%"))
        next_start = present_text(occupancy.get("next_occupied_start"), "")
        if next_start:
            rows.append(("Next scheduled occupancy", next_start[:16].replace("T", " ")))
        strategy = present_text(occupancy.get("strategy"), "")
        if strategy:
            rows.append(("Operating strategy", strategy))

    if rows:
        st.markdown("<div class='field-label'>Operating context</div>", unsafe_allow_html=True)
        context_table(rows)
    elif "zone_temps" not in input_data:
        st.info("No structured input fields were captured for this step.")


def render_text_panel(label: str, value: object, css_class: str) -> None:
    message = html.escape(present_text(value))
    st.markdown(
        f"<div class='field-label'>{html.escape(label)}</div><div class='{css_class}'>{message}</div>",
        unsafe_allow_html=True,
    )


def render_agent_card(agent: str, row: Any, *, show_raw_json: bool = True) -> None:
    input_data = parse_trace_input(getattr(row, "input_json", "{}"))
    recommendation = getattr(row, "recommendation", None)
    confidence = getattr(row, "confidence", None)
    with st.container(border=True):
        title_column, recommendation_column, confidence_column = st.columns([2.25, 1, 1])
        with title_column:
            st.markdown(
                f"<p class='agent-title'>{html.escape(agent_label(agent))}</p>"
                f"<p class='agent-role'>{html.escape(agent_role(agent))}</p>",
                unsafe_allow_html=True,
            )
        recommendation_column.metric("Recommendation", format_temperature(recommendation))
        confidence_value = as_float(confidence)
        confidence_column.metric("Confidence", NOT_AVAILABLE if confidence_value is None else f"{confidence_value:.0f}%")

        st.markdown("<div class='field-label'>Input summary</div>", unsafe_allow_html=True)
        render_agent_input_summary(agent, input_data)

        narrative_column, effect_column = st.columns([1.25, 1])
        with narrative_column:
            render_text_panel("Reasoning", getattr(row, "reasoning", None), "reasoning-copy")
        with effect_column:
            render_text_panel("Effect on decision", getattr(row, "effect_on_final", None), "effect-copy")

        if show_raw_json:
            with st.expander("View Raw JSON", expanded=False):
                st.code(raw_json(input_data), language="json")


def trace_recommendation(trace: pd.DataFrame, agent: str) -> object:
    if trace.empty or "agent" not in trace:
        return None
    rows = trace[trace["agent"] == agent]
    return None if rows.empty else rows.iloc[-1].get("recommendation")


def latest_safety_status(trace: pd.DataFrame) -> str:
    if trace.empty or "agent" not in trace:
        return "Not available"
    rows = trace[trace["agent"] == "safety_supervisor"]
    if rows.empty:
        return "Awaiting review"
    effect = present_text(rows.iloc[-1].get("effect_on_final"), "").lower()
    if any(word in effect for word in ("enabled", "approved", "passed")):
        return "Approved"
    if any(word in effect for word in ("blocked", "rejected", "denied")):
        return "Blocked"
    return "Reviewed"


def render_architecture_flow_card() -> None:
    """Show the governed system path without exposing implementation details."""
    steps = [
        ("&#128246;", "Building Telemetry"),
        ("&#127970;", "EnergyPlus Digital Twin"),
        ("&#8646;", "MCP Server"),
        ("&#129302;", "5 Specialist AI Agents"),
        ("&#129504;", "Coordinator"),
        ("&#128737;", "Safety Supervisor"),
        ("&#9881;", "HVAC Control Layer"),
        ("&#128260;", "Updated EnergyPlus Simulation"),
    ]
    with st.container(border=True):
        st.markdown("<div class='field-label'>Governed architecture</div>", unsafe_allow_html=True)
        st.markdown("<p class='section-intro'>Every operating change follows this reviewed, auditable path.</p>", unsafe_allow_html=True)
        nodes = []
        for index, (icon, label) in enumerate(steps):
            nodes.append(
                f"<div class='architecture-node'><span class='architecture-icon'>{icon}</span>{label}</div>"
            )
            if index < len(steps) - 1:
                nodes.append("<div class='architecture-arrow'>&darr;</div>")
        st.markdown(f"<div class='architecture-flow'>{''.join(nodes)}</div>", unsafe_allow_html=True)


def render_latest_ai_decision_summary(trace: pd.DataFrame, applied_setpoint: object) -> None:
    """Render the current governed recommendation as an executive decision snapshot."""
    specialist_signals = [
        ("&#127777;", "Comfort Agent", "comfort_agent"),
        ("&#9889;", "Energy Agent", "energy_agent"),
        ("&#9729;", "Weather Agent", "weather_agent"),
        ("&#9851;", "Carbon Agent", "carbon_agent"),
        ("&#128101;", "Occupancy Agent", "occupancy_agent"),
    ]
    with st.container(border=True):
        st.markdown("<div class='field-label'>Latest governed cycle</div>", unsafe_allow_html=True)
        st.subheader("Latest AI Decision")
        st.caption("Showing the latest completed governed cycle automatically. No operator input is required for this demo view.")
        specialist_columns = st.columns(5)
        for column, (icon, label, agent) in zip(specialist_columns, specialist_signals):
            with column:
                proposal = trace_recommendation(trace, agent)
                st.markdown(
                    f"<div class='decision-signal'><span class='decision-icon'>{icon}</span>"
                    f"<span>{label}</span><strong>{format_temperature(proposal)}</strong></div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<div class='decision-arrow'>&darr;</div>", unsafe_allow_html=True)
        coordinator_value = trace_recommendation(trace, "coordinator")
        safety_value = trace_recommendation(trace, "safety_supervisor")
        final_columns = st.columns(3)
        final_values = [
            ("&#129504;", "Coordinator Proposal", format_temperature(coordinator_value)),
            ("&#128737;", "Safety Decision", latest_safety_status(trace)),
            ("&#9881;", "Applied Setpoint", format_temperature(applied_setpoint if applied_setpoint is not None else safety_value)),
        ]
        for column, (icon, label, value) in zip(final_columns, final_values):
            with column:
                st.markdown(
                    f"<div class='decision-final'><span>{icon} {label}</span><strong>{value}</strong></div>",
                    unsafe_allow_html=True,
                )


def render_project_workflow() -> None:
    steps = [
        ("&#128246;", "Telemetry"),
        ("&#129302;", "AI Analysis"),
        ("&#129504;", "Decision Coordination"),
        ("&#128737;", "Safety Validation"),
        ("&#128260;", "EnergyPlus Update"),
    ]
    st.markdown("<div class='field-label'>Project workflow</div>", unsafe_allow_html=True)
    content = "".join(f"<div class='timeline-step'><b>{icon}</b><span>{label}</span></div>" for icon, label in steps)
    st.markdown(f"<div class='timeline'>{content}</div>", unsafe_allow_html=True)


def render_demo_final_results(
    trace: pd.DataFrame,
    applied_setpoint: object,
    facility_energy_j: float | None,
    comfort: float | None,
    reduction: float | None,
) -> None:
    st.header("Final Results")
    st.markdown("<p class='section-intro'>The latest cycle outcome, presented for executive review.</p>", unsafe_allow_html=True)
    with st.container(border=True):
        result_columns = st.columns(4)
        result_columns[0].metric("Applied setpoint", format_temperature(applied_setpoint))
        result_columns[1].metric("Facility energy", fmt_energy(facility_energy_j))
        result_columns[2].metric("Comfort maintained", NOT_AVAILABLE if comfort is None else f"{comfort:.0f}%")
        result_columns[3].metric("Safety decision", latest_safety_status(trace), NOT_AVAILABLE if reduction is None else f"Energy change {reduction:+.1f}%")
        st.caption("The displayed setpoint is the latest safety-governed value recorded by the system.")
    render_project_workflow()


def render_demo_conclusion() -> None:
    st.header("Conclusion")
    st.success("EcoLoop-AI turns live building telemetry into a safety-governed HVAC decision that is traceable from simulation to applied setpoint.")
    st.markdown("<div class='field-label'>Key outcomes</div>", unsafe_allow_html=True)
    outcome_columns = st.columns(5)
    outcomes = ["&#10004; Energy Reduced", "&#10004; Comfort Maintained", "&#10004; Carbon Reduced", "&#10004; Safety Validated", "&#10004; Fully Auditable"]
    for column, outcome in zip(outcome_columns, outcomes):
        with column:
            st.markdown(f"<div class='outcome-item'>{outcome}</div>", unsafe_allow_html=True)


# Data snapshot
summary = load_summary()
temperatures, current_energy_j, outdoor_c = load_sensor_state()
conditioned_temperatures = {zone: temperature for zone, temperature in temperatures.items() if "PLENUM" not in zone.upper()}
sim_state, sim_message, runtime_s = simulation_status()
trace = db_table("decision_trace")
safety_events = db_table("safety_events")
anomalies = db_table("sensor_anomalies", limit=50)
overrides = db_table("facility_overrides", limit=50)
ai_results = db_table("ai_results")
latest_trace = latest_cycle_trace(trace)
agreement = actual_agreement(latest_trace)
tariff, occupancy = active_operational_context()

baseline_j = summary.get("baseline_avg_energy_j", summary.get("baseline_avg_energy_kw"))
ai_j = summary.get("ai_avg_energy_j", summary.get("ai_avg_energy_kw"))
if ai_j is None and current_energy_j is not None:
    ai_j = current_energy_j
reduction_pct = None
if baseline_j not in (None, 0) and ai_j is not None:
    reduction_pct = (float(baseline_j) - float(ai_j)) / float(baseline_j) * 100
comfort_score = None
if conditioned_temperatures:
    in_target = sum(COMFORT_LOW_C <= temp <= COMFORT_HIGH_C for temp in conditioned_temperatures.values())
    comfort_score = 100 * in_target / len(conditioned_temperatures)
carbon_delta = None
if baseline_j is not None and ai_j is not None:
    carbon_delta = (energy_kwh(float(baseline_j)) - energy_kwh(float(ai_j))) * CARBON_FACTOR_KG_PER_KWH
approved_safety = int((safety_events.get("event_type", pd.Series(dtype=str)) == "approval").sum())
blocked_safety = int((safety_events.get("event_type", pd.Series(dtype=str)).isin(["block", "sensor_fault"])).sum())
current_setpoint = None
if not ai_results.empty and "final_temp" in ai_results:
    applied_values = pd.to_numeric(ai_results["final_temp"], errors="coerce").dropna()
    current_setpoint = applied_values.iloc[0] if not applied_values.empty else None


with st.sidebar:
    st.title("EcoLoop-AI")
    st.caption("Building Operations Intelligence")
    st.divider()
    demo_mode = st.toggle("Demo mode", value=True, help="Show the concise executive demo flow.")
    st.divider()
    st.caption("CONTROL GOVERNANCE")
    st.write("All actions route through the Safety Supervisor. The dashboard never writes setpoints directly.")
    if st.button("Refresh telemetry", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.caption("ENGINEERING BASIS")
    st.write("EnergyPlus facility electricity is converted to a readable kWh or MWh value for every energy and carbon display.")
    st.caption("Thermal Comfort Target")
    st.write("21.0–24.0 °C demonstration target; not a claim of ASHRAE 55 compliance.")


st.markdown("<p class='eyebrow'>EcoLoop-AI / governed building control</p>", unsafe_allow_html=True)
st.title("Smart Building Operations")
st.markdown(
    "<p class='page-subtitle'>EnergyPlus digital twin &middot; Auditable multi-agent decisioning &middot; Safety-governed HVAC control</p>",
    unsafe_allow_html=True,
)
render_architecture_flow_card()

if not anomalies.empty:
    latest_anomaly = anomalies.iloc[0]
    st.error(
        f"Control protection active: {latest_anomaly.get('message', 'Invalid telemetry detected')}. "
        "HVAC changes are blocked until valid sensor data is available."
    )

overview_columns = st.columns(5)
overview_columns[0].metric("Energy reduction", NOT_AVAILABLE if reduction_pct is None else f"{reduction_pct:+.1f}%", "Baseline vs AI-controlled simulation")
overview_columns[1].metric("Comfort score", NOT_AVAILABLE if comfort_score is None else f"{comfort_score:.0f}%", "Conditioned zones within target")
overview_columns[2].metric("Carbon impact", NOT_AVAILABLE if carbon_delta is None else f"{carbon_delta:+.1f} kg CO₂", "Estimated vs baseline")
overview_columns[3].metric("Safety checks", f"{approved_safety} passed", f"{blocked_safety} blocked")
overview_columns[4].metric("AI decisions", str(len(ai_results)), "Safety-approved cycle records")


st.header("Operational context")
st.markdown("<p class='section-intro'>The current operating signals used to frame the next governed decision.</p>", unsafe_allow_html=True)
context_left, context_mid, context_right = st.columns([1, 1, 1.25])
with context_left:
    with st.container(border=True):
        st.subheader("Demand response")
        st.metric("Current simulated tariff", tariff["label"], f"${tariff['rate_usd_per_kwh']:.2f}/kWh")
        tariff_message = {
            "peak": "Energy Agent prioritises sensible load reduction during the peak window.",
            "normal": "Energy Agent balances comfort and operating cost.",
            "off_peak": "Energy Agent may support forecast-led pre-conditioning.",
        }.get(tariff.get("key"), "Tariff context is available to the Energy Agent.")
        st.caption(tariff_message)
with context_mid:
    with st.container(border=True):
        st.subheader("Occupancy forecast")
        st.metric("Expected occupancy", f"{occupancy['expected_occupancy_pct']}%", occupancy["model"])
        st.write(occupancy["strategy"])
        st.caption(f"Next scheduled occupancy: {occupancy['next_occupied_start'][:16].replace('T', ' ')}")
with context_right:
    with st.container(border=True):
        st.subheader("HVAC operating position")
        setpoint_column, runtime_column = st.columns([1.15, .85])
        setpoint_column.metric("Last applied setpoint", format_temperature(current_setpoint), "Safety-approved HVAC Control Layer")
        runtime_column.metric("Simulation runtime", NOT_AVAILABLE if runtime_s is None else f"{runtime_s:.1f} s", sim_state.title())
        st.caption(f"Outdoor dry-bulb: {format_temperature(outdoor_c)} · Facility energy: {fmt_energy(current_energy_j)}")


render_latest_ai_decision_summary(latest_trace, current_setpoint)


st.header("Explainable AI decision cycle")
st.markdown(
    "<p class='section-intro'>A readable audit of what each specialist received, why it responded, and how its recommendation affected the governed outcome.</p>",
    unsafe_allow_html=True,
)
if latest_trace.empty:
    st.info("No governed decision trace is available yet. Submit a facility-manager decision below or run `python agents/graph.py` to create one.")
else:
    coordinator_rows = latest_trace[latest_trace["agent"] == "coordinator"]
    safety_rows = latest_trace[latest_trace["agent"] == "safety_supervisor"]
    coordinator_value = None if coordinator_rows.empty else coordinator_rows.iloc[-1].get("recommendation")
    safety_value = None if safety_rows.empty else safety_rows.iloc[-1].get("recommendation")

    flow_columns = st.columns(4)
    flow_steps = [
        ("1. Specialist analysis", "Comfort, energy, weather, carbon and occupancy signals"),
        ("2. Coordination", f"Proposed setpoint: {format_temperature(coordinator_value)}"),
        ("3. Safety validation", f"Safety output: {format_temperature(safety_value)}"),
        ("4. HVAC control layer", "Only safety-approved actions are enabled"),
    ]
    for column, (title, detail) in zip(flow_columns, flow_steps):
        with column:
            st.markdown(f"<div class='flow-step'><strong>{title}</strong><span>{detail}</span></div>", unsafe_allow_html=True)

    summary_columns = st.columns([1, 1, 1.4])
    specialist_count = int(latest_trace["agent"].isin(["comfort_agent", "energy_agent", "weather_agent", "carbon_agent", "occupancy_agent"]).sum())
    summary_columns[0].metric("Specialist inputs", str(specialist_count), "Signals evaluated")
    summary_columns[1].metric("Coordinator proposal", format_temperature(coordinator_value), "Submitted for review")
    summary_columns[2].metric("Consensus confidence", NOT_AVAILABLE if agreement is None else f"{agreement:.0f}%", "Based on specialist recommendation spread")
    if agreement is not None:
        st.progress(int(round(agreement)), text=f"Specialist alignment: {agreement:.0f}%")

    display_order = ["comfort_agent", "energy_agent", "weather_agent", "carbon_agent", "occupancy_agent", "coordinator", "safety_supervisor"]
    trace_by_agent = {str(row.agent): row for row in latest_trace.itertuples()}
    for agent in display_order:
        row = trace_by_agent.get(agent)
        if row is not None:
            render_agent_card(agent, row, show_raw_json=not demo_mode)


if demo_mode:
    render_demo_final_results(latest_trace, current_setpoint, current_energy_j, comfort_score, reduction_pct)
    render_demo_conclusion()
    st.caption(f"Live data snapshot: {datetime.now().strftime('%d %b %Y %H:%M:%S')} · Demo view automatically shows the latest governed cycle.")
    st.stop()


st.header("Facility Manager override")
st.markdown("<p class='section-intro'>A manager may accept or propose an action; every request remains subject to deterministic safety validation.</p>", unsafe_allow_html=True)
override_left, override_right = st.columns([1.1, 1])
with override_left:
    with st.container(border=True):
        st.subheader("Approve or propose an override")
        st.caption("An override remains a request. The Safety Supervisor validates it against telemetry, HVAC bounds, and the maximum change per cycle before control is enabled.")
        with st.form("facility_manager_decision", clear_on_submit=True):
            action_label = st.radio("Decision", ["Accept AI recommendation", "Propose manual override"], horizontal=True)
            requested_temp = st.number_input(
                "Requested cooling setpoint (°C)",
                min_value=10.0,
                max_value=35.0,
                value=22.5,
                step=0.1,
                disabled=action_label == "Accept AI recommendation",
            )
            reason = st.text_area("Facility manager reason", placeholder="Document the operating reason for this decision.")
            submitted = st.form_submit_button("Record decision and run governed cycle", use_container_width=True)
        if submitted:
            if not reason.strip():
                st.warning("A facility-manager reason is required for the audit log.")
            else:
                from agents.audit import queue_facility_override

                action = "accept_ai" if action_label == "Accept AI recommendation" else "override"
                queue_facility_override(action, None if action == "accept_ai" else float(requested_temp), reason.strip())
                try:
                    with st.spinner("Running the governed decision cycle through EnergyPlus…"):
                        from agents.graph import run_one_cycle

                        result = run_one_cycle(next_cycle_number())
                    decision = result.get("safety_decision", {})
                    if decision.get("approved"):
                        st.success(f"Safety Supervisor approved {decision.get('applied_temp'):.1f} °C for the HVAC Control Layer.")
                    else:
                        st.error("Safety Supervisor blocked the control action. Review the safety audit below.")
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(f"The governed cycle could not complete: {exc}")
with override_right:
    with st.container(border=True):
        st.subheader("AI recommendation vs human decision")
        coordinator = latest_trace[latest_trace["agent"] == "coordinator"] if not latest_trace.empty else pd.DataFrame()
        ai_value = None if coordinator.empty else coordinator.iloc[-1].get("recommendation")
        manager = overrides.iloc[0] if not overrides.empty else None
        st.metric("AI coordinator proposal", format_temperature(ai_value))
        if manager is None:
            st.metric("Latest manager decision", "No recorded decision")
        else:
            requested = manager.get("requested_temp")
            label = "Accepted AI" if manager.get("action") == "accept_ai" else format_temperature(requested)
            st.metric("Latest manager decision", label, present_text(manager.get("status"), "Pending").title())
            st.caption(f"Reason: {present_text(manager.get('reason'), NOT_AVAILABLE)}")


st.header("Engineering performance")
st.markdown("<p class='section-intro'>Live simulation telemetry and energy comparison, translated into operator-friendly units.</p>", unsafe_allow_html=True)
performance_left, performance_right = st.columns(2)
with performance_left:
    with st.container(border=True):
        st.subheader("Zone thermal conditions")
        if conditioned_temperatures:
            frame = pd.DataFrame(
                {"Zone": list(conditioned_temperatures), "Temperature (°C)": list(conditioned_temperatures.values())}
            ).sort_values("Temperature (°C)")
            frame["Temperature (°C)"] = frame["Temperature (°C)"].round(1)
            st.dataframe(frame, use_container_width=True, hide_index=True, height=min(370, 74 + len(frame) * 35))

            colours = [
                "#ff7187" if value > COMFORT_HIGH_C else "#f9c74f" if value < COMFORT_LOW_C else "#48d597"
                for value in frame["Temperature (°C)"]
            ]
            figure = go.Figure(
                go.Bar(
                    x=frame["Temperature (°C)"],
                    y=frame["Zone"],
                    orientation="h",
                    marker_color=colours,
                    hovertemplate="%{y}<br>%{x:.1f} °C<extra></extra>",
                )
            )
            figure.add_vrect(
                x0=COMFORT_LOW_C,
                x1=COMFORT_HIGH_C,
                fillcolor="rgba(72, 213, 151, .12)",
                line_width=0,
                annotation_text="Comfort target",
                annotation_position="top left",
                annotation_font_color="#c7d6e2",
            )
            figure.update_layout(
                height=max(330, len(frame) * 23),
                margin=dict(l=0, r=10, t=40, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#dce9f2",
                xaxis_title="Temperature (°C)",
                yaxis_title=None,
            )
            figure.update_xaxes(gridcolor="#244967", zeroline=False)
            figure.update_yaxes(gridcolor="rgba(0,0,0,0)", autorange="reversed")
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
            st.caption("Plenum zones are excluded because the thermal-comfort target applies to conditioned occupant zones.")
        else:
            st.info("Zone telemetry will appear after an EnergyPlus simulation produces `eplusout.csv`.")
with performance_right:
    with st.container(border=True):
        st.subheader("Baseline vs AI-controlled energy")
        if baseline_j is not None and ai_j is not None:
            base_kwh, controlled_kwh = energy_kwh(float(baseline_j)), energy_kwh(float(ai_j))
            energy_metrics = st.columns(2)
            energy_metrics[0].metric("Baseline energy", fmt_energy_kwh(base_kwh))
            energy_metrics[1].metric("AI-controlled energy", fmt_energy_kwh(controlled_kwh))
            figure = go.Figure(
                [
                    go.Bar(
                        name="Baseline",
                        x=["Facility electricity"],
                        y=[base_kwh / 1_000],
                        marker_color="#718096",
                        hovertemplate="Baseline: %{y:,.2f} MWh<extra></extra>",
                    ),
                    go.Bar(
                        name="AI-controlled",
                        x=["Facility electricity"],
                        y=[controlled_kwh / 1_000],
                        marker_color="#4cc9f0",
                        hovertemplate="AI-controlled: %{y:,.2f} MWh<extra></extra>",
                    ),
                ]
            )
            figure.update_layout(
                height=320,
                barmode="group",
                margin=dict(l=0, r=0, t=20, b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#dce9f2",
                yaxis_title="Energy (MWh)",
                legend_title=None,
            )
            figure.update_yaxes(gridcolor="#244967", zeroline=False)
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
            st.caption(f"Energy is converted from EnergyPlus facility electricity. Carbon impact uses {CARBON_FACTOR_KG_PER_KWH:.3f} kg CO₂/kWh.")
        else:
            st.info("Run the baseline and at least one governed AI cycle to populate the comparison.")


st.header("Safety and system monitoring")
monitor_tab, safety_tab, architecture_tab = st.tabs(["System monitoring", "Safety audit", "Architecture"])
with monitor_tab:
    st.dataframe(monitor_rows(sim_state, trace, safety_events), use_container_width=True, hide_index=True)
with safety_tab:
    if safety_events.empty:
        st.info("No Safety Supervisor audit events have been logged yet.")
    else:
        audit = safety_events[
            [column for column in ["timestamp", "event_type", "source", "requested_temp", "applied_temp"] if column in safety_events]
        ].copy()
        audit.columns = [friendly_label(column) for column in audit.columns]
        if "Requested Setpoint" in audit:
            audit["Requested Setpoint"] = audit["Requested Setpoint"].map(format_temperature)
        if "Applied Temp" in audit:
            audit = audit.rename(columns={"Applied Temp": "Applied Setpoint"})
            audit["Applied Setpoint"] = audit["Applied Setpoint"].map(format_temperature)
        st.dataframe(audit, use_container_width=True, hide_index=True)
    if not anomalies.empty:
        st.caption("Recent sensor anomalies")
        anomaly_view = anomalies[[column for column in ["timestamp", "code", "message"] if column in anomalies]].copy()
        anomaly_view.columns = [friendly_label(column) for column in anomaly_view.columns]
        st.dataframe(anomaly_view, use_container_width=True, hide_index=True)
with architecture_tab:
    if os.path.exists(ARCH_PNG):
        st.image(ARCH_PNG, caption="EcoLoop-AI governed building-control architecture")
    else:
        st.warning("Architecture image is not available. Run `python generate_arch_diagram.py`.")


st.caption(
    f"Data snapshot: {datetime.now().strftime('%d %b %Y %H:%M:%S')} · "
    "EcoLoop-AI is a simulation demonstrator; production building control requires site-specific engineering approval."
)
