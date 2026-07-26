# Eco-Loop Building Agents

An autonomous, multi-agent AI system that closes the loop on building energy management:
EnergyPlus simulation → MCP tools → 4 specialist agents (Comfort, Energy, Occupancy, Carbon) →
Supervisor Agent → new HVAC setpoints → EnergyPlus, continuously.

**Start here: [`00_START_HERE.md`](./00_START_HERE.md)** — a complete, step-by-step build guide
from zero to submission.

## Quick Start
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5:7b

# Phase 1: test the EnergyPlus bridge
python sim_runner/eplus_interface.py

# Phase 2: test MCP tools directly
python mcp_server/test_client.py

# Phase 3: single agent, then multi-agent loop
python agents/single_agent_loop.py
python agents/graph.py

# Phase 4: baseline comparison
python sim_runner/run_baseline.py
python sim_runner/compute_savings.py

# Phase 5: dashboard
streamlit run dashboard/app.py
```

See `docs/ARCHITECTURE.md` for the full system design write-up.
