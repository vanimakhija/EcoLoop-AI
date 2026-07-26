"""
dashboard/app.py — run with: streamlit run dashboard/app.py

Reads data/results.db and data/results_summary.json (produced by
sim_runner/run_baseline.py, agents/graph.py, and sim_runner/compute_savings.py)
and displays:
  - summary cards (kWh saved, % reduction, comfort violations)
  - AI vs baseline energy chart
  - comfort band chart
  - agent decision feed with rationale
"""

import os
import json
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "results.db")
SUMMARY_PATH = os.path.join(PROJECT_ROOT, "data", "results_summary.json")

st.set_page_config(page_title="Eco-Loop Building Agents", layout="wide")
st.title("Eco-Loop Building Agents — Live Dashboard")

# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------
if os.path.exists(SUMMARY_PATH):
    with open(SUMMARY_PATH) as f:
        summary = json.load(f)

    col1, col2, col3, col4 = st.columns(4)
    pct = summary.get("pct_energy_reduction")
    col1.metric("Energy Reduction", f"{pct:.1f}%" if pct is not None else "—")
    col2.metric("AI Avg Demand (kW)",
                f"{summary.get('ai_avg_energy_kw'):.2f}" if summary.get("ai_avg_energy_kw") else "—")
    col3.metric("Baseline Avg Demand (kW)",
                f"{summary.get('baseline_avg_energy_kw'):.2f}" if summary.get("baseline_avg_energy_kw") else "—")
    col4.metric("Comfort Violations", summary.get("comfort_violations", "—"))
else:
    st.warning("No results_summary.json found yet. Run sim_runner/compute_savings.py first.")

st.divider()

# ---------------------------------------------------------------------------
# AI vs baseline energy chart
# ---------------------------------------------------------------------------
st.subheader("AI vs Baseline Energy Demand")

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)

    try:
        ai_df = pd.read_sql("SELECT cycle, energy_kw, final_temp FROM ai_results ORDER BY cycle", conn)
    except Exception:
        ai_df = pd.DataFrame()

    try:
        baseline_df = pd.read_sql("SELECT rowid AS cycle, energy_kw FROM baseline_results ORDER BY rowid", conn)
    except Exception:
        baseline_df = pd.DataFrame()

    fig = go.Figure()
    if not ai_df.empty:
        fig.add_trace(go.Scatter(x=ai_df["cycle"], y=ai_df["energy_kw"], name="AI-controlled", mode="lines+markers"))
    if not baseline_df.empty:
        # Baseline is usually a single run — draw as a flat reference line at its average
        avg_baseline = baseline_df["energy_kw"].mean()
        fig.add_hline(y=avg_baseline, line_dash="dash", annotation_text="Baseline avg", line_color="gray")
    fig.update_layout(xaxis_title="Cycle", yaxis_title="Energy Demand (kW)", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Comfort band chart
    # -----------------------------------------------------------------------
    st.subheader("Setpoint vs Comfort Band")
    if not ai_df.empty:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=ai_df["cycle"], y=ai_df["final_temp"], name="Setpoint (°C)", mode="lines+markers"))
        fig2.add_hrect(y0=21.0, y1=24.0, fillcolor="green", opacity=0.1, annotation_text="Comfort band")
        fig2.update_layout(xaxis_title="Cycle", yaxis_title="Temperature (°C)", height=350)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No AI cycle data yet — run agents/graph.py first.")

    # -----------------------------------------------------------------------
    # Agent decision feed
    # -----------------------------------------------------------------------
    st.subheader("Agent Decision Log")
    try:
        decisions_df = pd.read_sql(
            "SELECT timestamp, agent, rationale, action FROM agent_decisions ORDER BY timestamp DESC LIMIT 50",
            conn
        )
        st.dataframe(decisions_df, use_container_width=True)
    except Exception:
        st.info("No agent decisions logged yet.")

    conn.close()
else:
    st.warning(f"No database found at {DB_PATH}. Run the agent loop and baseline first.")
