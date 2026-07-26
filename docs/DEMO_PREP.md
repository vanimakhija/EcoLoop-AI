# EcoLoop-AI Demo Package

## Three-minute judge demo

### 0:00–0:25 — The problem and position

> “Commercial HVAC is a high-value optimisation problem, but production systems cannot let an AI model directly control equipment. EcoLoop-AI is a governed smart-building platform: it combines an EnergyPlus digital twin with explainable AI and deterministic safety controls.”

Open the dashboard and point to the executive metrics and system-monitoring panel.

### 0:25–1:15 — Explainable decisioning

> “Every cycle starts with validated EnergyPlus telemetry. Comfort, Energy, Weather Forecast, Carbon Impact, and Occupancy agents review the same operating context from distinct perspectives. The Energy Agent sees the current demand-response tariff; the Occupancy Agent forecasts whether pre-conditioning is warranted.”

Open **Explainable AI decision cycle**. Expand the specialist cards.

> “This is not a black box. Each card shows the precise input received, its reasoning, recommendation, agreement confidence, and the way the coordinator used it. The coordinator explains why it selected one setpoint instead of the alternatives.”

### 1:15–2:10 — Safety and human accountability

> “The coordinator only proposes a setpoint. It cannot write to HVAC. The deterministic Safety Supervisor is the authority between AI and the HVAC Control Layer. It checks sensor validity, humidity range, energy spikes, setpoint plausibility, HVAC bounds, and the maximum permitted change per cycle.”

Point to **Safety and system monitoring** and then **Facility Manager override**.

> “A facility manager can accept the recommendation or submit a documented override. That request returns through the same Safety Supervisor. The override is auditable, and it never bypasses the control boundary.”

### 2:10–3:00 — Evidence and production path

> “The energy, comfort, carbon, runtime, and safety figures are derived from EnergyPlus output and audit data—not display-only placeholders. EnergyPlus emits facility electricity in joules; we convert it to kWh before calculating energy and carbon impact. Comfort is calculated from actual reported zone temperatures against the stated demonstration target.”

Show the architecture tab.

> “For production, the digital twin and controls workflow map to a secure BACnet or Modbus gateway with site-specific engineering, BMS interlocks, authenticated identities, and append-only audit logging. AI improves the decision process; the building automation system keeps operational authority.”

## Five-minute technical walkthrough

### Minute 1 — Data and engineering units

- EnergyPlus produces zone mean-air temperature, outdoor dry-bulb, and `Electricity:Facility [J]`.
- The state reader retains joules and calculates kWh using `J / 3,600,000`.
- The dashboard labels all energy and carbon values with their engineering basis.
- The thermal-comfort score is the proportion of available zone temperatures in the 21.0–24.0 °C demonstration target; it is not a full ASHRAE 55 compliance claim.

### Minute 2 — Multi-agent workflow

- LangGraph runs Comfort, Energy, Weather Forecast, Carbon Impact, and Occupancy agents.
- The Energy Agent receives the deterministic peak, normal, or off-peak tariff.
- The Occupancy Agent receives a transparent weekday schedule forecast and a 60-minute pre-conditioning signal.
- The Coordinator receives the recommendations and writes a human-readable selection reason.
- Agreement confidence is calculated from recommendation spread, not invented by the model.

### Minute 3 — Fault detection and safety

- Validation occurs before AI execution.
- Missing or non-finite required telemetry blocks the cycle.
- Temperature plausibility, humidity range, negative energy, and energy spikes are explicit fault checks.
- Safety Supervisor logic is deterministic Python, isolated from the LLM runtime.
- It blocks physically implausible requests, constrains HVAC limits, and rate-limits setpoint movement.

### Minute 4 — Human override and auditability

- The dashboard queues an acceptance or manual override request with a reason.
- The graph reads that request only after the coordinator recommendation is available.
- The Safety Supervisor evaluates it with the same rules as AI-originated requests.
- `decision_trace`, `safety_events`, `sensor_anomalies`, and `facility_overrides` provide an evidence trail.

### Minute 5 — Production architecture

- Keep AI, safety, and protocol integration as separate services.
- Use a BACnet or Modbus gateway with a point allowlist, write/read-back, command expiry, and local BMS priority/interlocks.
- Require SSO, role-based authorisation, traceable controls changes, network segmentation, and a commissioning environment.
- Validate policies in the EnergyPlus digital twin before any staged on-site rollout.

## Likely judge questions and strong answers

### Is the AI actually in control?

The AI is intentionally not the control authority. It provides specialised, explainable recommendations. The deterministic Safety Supervisor authorises or blocks a value, and the HVAC Control Layer executes only an approved value. This is closer to an industrial control pattern than direct model-to-equipment automation.

### Why use multiple agents rather than one prompt?

The specialist roles make competing objectives explicit: comfort, cost, weather, carbon, and occupancy. The dashboard exposes the input, reasoning, recommendation, agreement, and final impact of each role, so a manager can audit the trade-off rather than accepting one opaque answer.

### Are the savings real?

The calculation uses the configured EnergyPlus baseline and AI-controlled runs, converting source joules to kWh before comparison. It is real for the simulated run period. We do not present it as an annual or site-specific savings guarantee without an annual calibrated baseline.

### How do you prevent a bad model answer from changing HVAC?

Bad model output still has to pass deterministic telemetry validation, plausibility checks, operating bounds, and maximum-change limits. Invalid telemetry blocks control before agents run. The MCP setpoint transport also has a safety guard so direct tool callers cannot bypass the boundary.

### How would this connect to Honeywell or an existing BMS?

The application would use an authenticated, site-approved BACnet or Modbus gateway. The gateway exposes a point allowlist and owns protocol details, while Safety Supervisor policies and BMS priority/interlocks remain outside the model. The project documents the mapping but does not claim to implement it.

### Why is occupancy prediction simple?

It is deliberately transparent for the demo: a schedule creates a pre-conditioning signal. The interface and agent role are already separated, so it can be replaced with approved calendar, badge, reservation, or privacy-preserving sensor feeds without changing the safety architecture.

### What is the future roadmap?

1. Calibrate the EnergyPlus model to site telemetry and run annual baseline comparisons.
2. Replace demonstration tariff, carbon, and occupancy inputs with approved production feeds.
3. Add a secure BACnet/Modbus gateway, BMS read-back, and point ownership policy.
4. Externalise Safety Supervisor configuration with controls-engineering approval and test coverage.
5. Introduce SSO, tamper-evident audit retention, observability, and staged rollout across zones and buildings.

## Presenter checklist

- Run baseline and governed simulation cycles before presenting.
- Open `streamlit run dashboard/app.py` and verify system-monitoring status.
- Confirm the latest decision trace and safety event are visible.
- Have `docs/architecture.png` open in the dashboard Architecture tab.
- Avoid stating annual savings, standards compliance, or live BACnet/Modbus integration unless those are actually implemented.
