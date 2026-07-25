# Eco-Loop Building Agents — Architecture Document

## 1. Problem
Traditional Building Management Systems use fixed schedules (e.g. "AC on at 9am") that cannot
adapt to real-time conditions. This project builds an autonomous, closed-loop AI system that
continuously monitors a building simulation and adjusts HVAC setpoints to reduce energy while
maintaining occupant comfort.

## 2. System Architecture

```
EnergyPlus Simulation
        │
Building Telemetry (temp, humidity, energy)
        │
   MCP Tool Server
        │
 ┌──────┴──────┬───────────┬────────────┐
 Comfort Agent  Energy Agent  Occupancy Agent  Carbon Agent
 └──────┬──────┴───────────┴────────────┘
        │
  Supervisor Agent
        │
  New HVAC Setpoints
        │
EnergyPlus Simulation (next cycle)
```

[Fill in: paste your final diagram here — you can regenerate this as an image for the slides.]

## 3. Components

### 3.1 Simulation Layer
- EnergyPlus [version], building model: [name your baseline IDF / building type]
- Interface method: [eppy short-run replanning / EMS callbacks — state which you used and why]

### 3.2 Tool Layer (MCP)
- MCP server exposes: `get_building_state`, `set_hvac_setpoint`, `run_simulation`,
  `get_energy_baseline`, `log_decision`
- [Note any tools you added/removed]

### 3.3 Agent Layer
- Framework: LangGraph
- Model: [Qwen2.5-7B / Llama 3 / etc.] via Ollama, run locally
- 4 specialist agents (Comfort, Energy, Occupancy, Carbon) + 1 Supervisor, implemented as
  distinct LangGraph nodes sharing one underlying LLM with role-specific system prompts
- [Explain why: cost/latency tradeoff of one model with role prompts vs. 4 separate models]

### 3.4 Prompt Engineering Strategy
- All agents forced into JSON-mode output for reliability with a small local model
- [Describe any prompt iteration you did, what failed, what worked]

### 3.5 Handling Long Simulation Logs
- [Describe how you kept EnergyPlus output CSVs from overwhelming the LLM context —
  e.g. summarizing to a small state dict rather than passing raw CSV rows]

## 4. Closed-Loop Execution
1. Read current building state via MCP
2. Each specialist agent independently recommends a setpoint
3. Supervisor merges recommendations into one final decision, respecting comfort bounds
4. Decision applied to the EnergyPlus model
5. Simulation re-run, new state produced
6. Repeat

## 5. Results
- Baseline avg energy demand: [X] kW
- AI-controlled avg energy demand: [Y] kW
- % Energy reduction: [Z]%
- Comfort violations: [N] cycles outside 21–24°C band
- (Pull these numbers directly from `data/results_summary.json` — do not estimate)

## 6. Limitations & Future Work
- [Be honest: e.g. short-run replanning instead of true real-time EMS callbacks,
  single-zone control instead of full multi-zone, no live grid carbon intensity feed]
- Future: [EMS callbacks for true real-time control, multi-zone scaling, live carbon API]

## 7. Tech Stack
Python, EnergyPlus, eppy, LangGraph, Ollama (Qwen2.5), MCP, Streamlit, Plotly, SQLite
