# Eco-Loop Building Agents — Complete Beginner Build Guide

This is your literal, step-by-step path from "nothing installed" to "submitted." Follow it top to bottom. Every phase ends with a **checkpoint** — do not move to the next phase until the checkpoint works. If you get stuck on a phase past its time budget, skip to the "if stuck" note and keep moving. A finished simple system beats a broken complex one.

Time budget assumes ~26 hours. Adjust proportionally.

---

## PHASE 0 — Environment Setup (Target: 45–60 min)

### 0.1 Install Python
You need Python 3.10 or 3.11 (EnergyPlus's Python API works best with these; 3.12+ can have compatibility issues).

- **Windows**: download from python.org, check "Add Python to PATH" during install.
- **Mac**: `brew install python@3.11`
- **Linux**: `sudo apt install python3.11 python3.11-venv`

Verify: open a terminal and run:
```bash
python3 --version
```
You should see `Python 3.11.x` (or 3.10.x).

### 0.2 Install EnergyPlus
Go to https://energyplus.net/downloads and download **version 9.6 or later** for your OS. Run the installer, accept defaults.

After install, find your install folder — this matters a lot, you'll reference it constantly:
- Windows: `C:\EnergyPlusV9-6-0\`
- Mac: `/Applications/EnergyPlus-9-6-0/`
- Linux: `/usr/local/EnergyPlus-9-6-0/`

Verify it works — open a terminal, `cd` into that folder, and run:
```bash
./energyplus --version
```
(Windows: just `energyplus --version` in Command Prompt from that folder)

### 0.3 Get a baseline building model (don't build one from scratch)
Inside your EnergyPlus install folder there's an `ExampleFiles` directory with hundreds of `.idf` files. You want a **medium office** model — look for something like:
```
RefBldgMediumOfficeNew2004_Chicago.idf
```
If it's not there, search EnergyPlus's example files list online for "Medium Office" — DOE prototype building models are the standard hackathon shortcut.

Copy this file, and its matching weather file (`.epw`, usually in a `WeatherData` folder in the same install), into:
```
eco-loop-building-agents/energyplus/baseline.idf
eco-loop-building-agents/energyplus/weather/weather.epw
```

**Test it runs**, from inside the `energyplus` folder:
```bash
/path/to/energyplus --weather weather/weather.epw --output-directory ./test_run baseline.idf
```
This should take 10–60 seconds and produce output files (including `eplusout.csv`) in `test_run/`. If this works, EnergyPlus itself is fine and any future bugs are in your Python code, not the simulation engine — good to know.

### 0.4 Set up Python environment and install packages
```bash
cd eco-loop-building-agents
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install eppy langgraph langchain-ollama mcp streamlit plotly pandas
```

Also install the EnergyPlus Python bindings — these ship *inside* your EnergyPlus install folder, not via pip. You'll add that folder to your Python path in code later (shown in Phase 1).

### 0.5 Install Ollama and pull a model
Download Ollama from https://ollama.com. Then:
```bash
ollama pull qwen2.5:7b
```
Test it works:
```bash
ollama run qwen2.5:7b "Say hello in one sentence."
```

**Critical de-risking step** — test tool-calling now, not later. Run this Python snippet:
```python
from langchain_ollama import ChatOllama
llm = ChatOllama(model="qwen2.5:7b")
print(llm.invoke("What is 2+2? Reply with only the number.").content)
```
If this errors, fix your Ollama/langchain-ollama install before going further. If your model is too slow or flaky at tool-calling once you get to Phase 3, fall back to a smaller model (`qwen2.5:3b`) or simplify to JSON-mode prompting instead of native tool-calling (see Phase 3 notes).

### 0.6 Git + GitHub
```bash
cd eco-loop-building-agents
git init
git add .
git commit -m "Initial project scaffold"
```
Create an empty repo on GitHub, then:
```bash
git remote add origin https://github.com/YOUR_USERNAME/eco-loop-building-agents.git
git branch -M main
git push -u origin main
```
Commit after every phase checkpoint below — small commits, clear messages. Judges may look at history.

**✅ Checkpoint 0**: EnergyPlus runs standalone and produces `eplusout.csv`. Ollama answers a prompt. Repo is on GitHub.

---

## PHASE 1 — EnergyPlus ⇄ Python bridge (Target: 2.5–3 hrs)

This is the most important phase. Everything else depends on it working.

### 1.1 Understand your two options (pick ONE)

**Option A — eppy + short repeated runs (recommended for beginners, do this first):**
You edit the IDF's thermostat setpoint schedule with `eppy`, run a short simulation (e.g. one day), read the results CSV, adjust setpoints, run again. Not "real-time" in the truest sense, but it *is* a genuine closed loop and is far more reliable to build in a hackathon.

**Option B — EnergyPlus EMS callbacks (more impressive, riskier):**
One persistent EnergyPlus process, Python hooks into it via callbacks each timestep. True real-time closed loop. Only attempt this if Option A works with time to spare (Phase 1 done in under 2 hours).

Start with Option A. The rest of this guide assumes Option A; I'll flag where Option B would slot in.

### 1.2 Read the current state from a completed run

Create `sim_runner/eplus_interface.py`:

This file is already written for you at `sim_runner/eplus_interface.py` in this project — open it now and read through the comments. Run the test at the bottom:
```bash
cd eco-loop-building-agents
python sim_runner/eplus_interface.py
```
It should print a dictionary of current building state (temp, humidity, energy) read from your test run in 0.3.

### 1.3 Modify setpoints and re-run

Also in `eplus_interface.py`, the `apply_setpoints()` function edits the schedule object in the IDF. Test it:
```bash
python -c "from sim_runner.eplus_interface import apply_setpoints, get_building_state; apply_setpoints(zone='Core_mid', new_temp=22.0); print(get_building_state())"
```
You should see the setpoint reflected in the next run's output.

**If stuck**: the most common failure is EnergyPlus object naming — IDFs use specific object types (`ThermostatSetpoint:DualSetpoint`, `Schedule:Compact`, etc.) and your zone/schedule names must match exactly what's in your IDF. Open the IDF in a text editor and search for `Thermostat` to find the real object and field names for your specific file — every building model names things slightly differently. Adjust the constants at the top of `eplus_interface.py` to match.

**✅ Checkpoint 1**: You can call `get_building_state()` and get real numbers. You can call `apply_setpoints()`, re-run, and see the numbers respond. **Commit and push.**

---

## PHASE 2 — MCP Server (Target: 1–1.5 hrs)

The MCP server is already scaffolded at `mcp_server/server.py` and `mcp_server/tools.py`. It wraps the functions from Phase 1 as MCP tools.

### 2.1 Run it standalone
```bash
python mcp_server/server.py
```

### 2.2 Test with a raw client call
Use the test script `mcp_server/test_client.py` (included) to call each tool directly and confirm it returns real data, before any LLM is involved. Isolate bugs here — it's much easier to debug a tool call directly than through an LLM's tool-calling layer.

**✅ Checkpoint 2**: All MCP tools return correct data when called directly. **Commit and push.**

---

## PHASE 3 — Single Agent Loop First (Target: 2–3 hrs)

Don't jump to 4 agents. Get ONE agent looping first.

### 3.1 Run the single-agent version
```bash
python agents/single_agent_loop.py
```
This should: read state → ask the LLM for a setpoint decision → apply it → log it to `data/results.db` → repeat for N cycles.

Watch the terminal output. If the LLM's tool-calling is unreliable (doesn't return valid JSON/tool calls), switch to the JSON-mode fallback noted in the comments at the top of that file — it's more robust with smaller local models than native tool-calling.

**✅ Checkpoint 3a**: The loop runs 5+ cycles without crashing, with real decisions logged to SQLite.

### 3.2 Expand to 4 agents + supervisor
Now open `agents/graph.py` — this has the full LangGraph wiring for Comfort/Energy/Occupancy/Carbon agents plus a Supervisor node. It reuses the same MCP tools and LLM, just with different system prompts per node (see `agents/prompts.py`).

Run:
```bash
python agents/graph.py
```

**✅ Checkpoint 3b**: The multi-agent loop runs reliably over a longer horizon (aim for a simulated week of sim-time if runtime allows — reduce if EnergyPlus runs are too slow). **Commit and push.**

---

## PHASE 4 — Baseline Comparison (Target: 30–45 min)

### 4.1 Run the unmodified baseline
```bash
python sim_runner/run_baseline.py
```
This runs your original `baseline.idf` with its fixed schedule, unmodified, over the same period, and logs results to a separate table in `data/results.db`.

### 4.2 Compute the comparison
```bash
python sim_runner/compute_savings.py
```
This writes `data/results_summary.json` with: % energy reduction, comfort-violation minutes, peak demand delta. **These are your real numbers for the dashboard, doc, and presentation — don't estimate, don't fabricate, use what this script outputs.**

**✅ Checkpoint 4**: `results_summary.json` has real, non-zero, sensible numbers. **Commit and push.**

---

## PHASE 5 — Dashboard (Target: 2 hrs)

```bash
streamlit run dashboard/app.py
```
This is pre-built to read from `data/results.db` and `data/results_summary.json` and show:
- AI vs baseline energy line chart
- Comfort band chart (PMV/temp with acceptable range shaded)
- Agent decision feed with rationale
- Summary cards (kWh saved, % reduction, comfort violations)

If your data schema differs from what the dashboard expects (likely, since your IDF's zone/variable names are specific to your building), adjust the SQL queries near the top of `dashboard/app.py` — they're commented.

**✅ Checkpoint 5**: Dashboard opens in browser, shows your real data, no errors. **Commit and push.**

---

## PHASE 6 — Documentation, Presentation, Video (Target: 3–4 hrs)

Do this LAST, once the system is stable, so your claims match reality.

### 6.1 Architecture document
Fill in `docs/ARCHITECTURE.md` (template included) — system diagram, tool-calling design, prompt strategy, how you handled long simulation logs, and an honest note on eppy vs. EMS and why you chose it.

### 6.2 Presentation
Use the required HirePro template. Suggested flow:
1. Problem (30s): traditional BMS is rigid, buildings are 40% of global energy
2. Architecture (60s): the diagram — EnergyPlus → MCP tools → 4 agents → supervisor → back to EnergyPlus
3. Live demo / results (90s): dashboard, real % savings number
4. Agentic autonomy (30s): show one real agent decision + rationale from your logs
5. Limitations & future work (30s): be honest — this is a judged strength, not a weakness

### 6.3 Demo video (max 3 min)
Script:
- 0:00–0:20 — problem framing, show the architecture diagram
- 0:20–1:50 — live: dashboard updating, terminal/log panel showing an agent decision, then EnergyPlus output changing on the next run
- 1:50–2:20 — results summary (your real numbers)
- 2:20–3:00 — architecture callout, close

Record with OBS Studio (free) or your OS's built-in screen recorder.

**✅ Checkpoint 6**: Doc, slides, and video all reference the SAME real numbers from `results_summary.json`.

---

## PHASE 7 — Submission (Target: 1–2 hrs, mostly buffer)

1. Re-read the deliverables checklist against your repo:
   - [ ] Source code (EnergyPlus wrapper + agent orchestration + MCP)
   - [ ] Building models (baseline `.idf` + modified versions)
   - [ ] Dashboard
   - [ ] Architecture document
   - [ ] Presentation (using required template)
   - [ ] Demo video (≤3 min)
2. Convert everything required to PDF/zip per the submission portal's instructions.
3. Push final commit, tag it `submission`:
```bash
git add .
git commit -m "Final submission"
git tag submission
git push origin main --tags
```
4. Submit the GitHub URL in the portal.
5. **Submit with time to spare** — don't cut it to the wire.

---

## Cutting order if you run out of time
Drop in this order, stopping as soon as you're back on schedule:
1. Carbon Agent (fold its logic into Energy Agent's prompt instead)
2. EMS real-time callbacks (stick with eppy short-run approach)
3. Dashboard polish (keep the core 2 charts, cut the rest)

**Never cut**: the baseline-vs-AI comparison, or closed-loop reliability. These map to 55% of the judging criteria.
