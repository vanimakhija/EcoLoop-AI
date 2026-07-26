# EcoLoop-AI Architecture

![EcoLoop-AI governed architecture](architecture.png)

## Purpose

EcoLoop-AI demonstrates how multi-agent reasoning can sit inside an accountable building-controls architecture. The AI layer offers explainable recommendations; it is not granted authority to control HVAC directly.

## Runtime sequence

1. **EnergyPlus Digital Twin** produces zone mean-air temperatures, facility electricity, and simulated outdoor conditions.
2. **State Reader** normalises the latest EnergyPlus output. `Electricity:Facility [J]` remains available as joules and is converted to kWh for human-facing calculations.
3. **MCP Server** exposes building-state read, simulation-run, audit, and safety-gated HVAC tools.
4. **Sensor validation** checks required temperature and energy telemetry before any AI call. It detects missing or non-finite data, implausible temperature, humidity outside 0–100%, negative energy, and an energy spike against recent runs.
5. **LangGraph** invokes Comfort, Energy, Weather Forecast, Carbon Impact, and Occupancy agents sequentially. Sequential execution keeps each logged recommendation attributable and avoids concurrent state-write ambiguity.
6. **HVAC Coordinator** selects an advisory setpoint and records its rationale for choosing it relative to the specialist positions.
7. **Safety Supervisor** independently validates the proposal. It is ordinary deterministic Python, not an LLM.
8. **HVAC Control Layer** can update the EnergyPlus cooling schedule only when Safety Supervisor approval is present.
9. **EnergyPlus** runs the next simulation, and runtime evidence is written to SQLite for the dashboard and audit trail.

## Explainability model

`decision_trace` records, for every governed cycle:

- agent identity and input snapshot;
- reasoning text;
- recommendation;
- agreement confidence;
- effect on the coordinator decision; and
- final decision where applicable.

Agreement confidence is calculated from the sample standard deviation of the five specialist recommendations over the 3 °C operating band:

```text
confidence = clamp(100 − standard_deviation(recommendations) / 3 × 100, 0, 100)
```

It measures recommendation convergence, not model correctness.

## Demand response and occupancy prediction

The demonstration tariff is deterministic and displayed in the dashboard:

| Window | Tariff | Energy-agent behaviour |
|---|---:|---|
| Weekday 14:00–20:00 | Peak, $0.25/kWh | Prefer sensible load reduction. |
| 22:00–06:00 | Off-peak, $0.09/kWh | Permit forecast-led pre-conditioning where useful. |
| Remaining hours | Normal, $0.15/kWh | Balance comfort and energy. |

The Occupancy Agent uses a transparent weekday office-hours schedule. It flags a 60-minute pre-conditioning window before an 08:00 start. This is intentionally lightweight and must be replaced by approved site occupancy data in a real deployment.

## Safety Supervisor

The Safety Supervisor is the final decision boundary before HVAC control. Its controls are:

| Rule | Behaviour |
|---|---|
| Required telemetry | Block control if zone-temperature or facility-energy telemetry is missing or invalid. |
| Plausibility checks | Block temperatures outside 5–45 °C, humidity outside 0–100%, negative energy, and energy spikes above 2× recent average. |
| Requested setpoint | Block non-numeric or physically implausible requests outside 10–35 °C. |
| HVAC limits | Constrain valid requests to 21.0–24.0 °C. |
| Rate limit | Limit the movement from the prior applied setpoint to 1.0 °C per cycle. |
| Audit | Log every approval, block, clamp, and facility-manager outcome. |

An MCP transport-level guard applies the same deterministic review to direct tool callers, so an LLM or legacy loop cannot bypass the safety boundary by calling the setpoint tool directly.

## Data and persistence

SQLite holds existing baseline and AI result tables plus these audit tables:

- `decision_trace` — explainability records.
- `safety_events` — Safety Supervisor approvals and blocks.
- `sensor_anomalies` — telemetry quality events.
- `facility_overrides` — facility-manager acceptance or override requests and outcome.

The dashboard is a consumer of this audit data. A manager action queues a request then runs the governed graph; the dashboard never edits the IDF schedule itself.

## Integration boundaries

EnergyPlus is accessed through `sim_runner/eplus_interface.py`; the IDF schedule writer remains the existing focused plain-text schedule update. MCP remains the tool boundary. LangGraph remains the workflow coordinator. The additions are deliberately layered around those working integrations rather than replacing them.

## Limitations

- The model controls one simulated schedule (`Core_mid`) rather than a live multi-zone system.
- Tariff, carbon factor, and occupancy data are demonstration inputs, not live utility or presence feeds.
- The Weather Forecast Agent currently consumes the latest simulated outdoor dry-bulb value; it is not connected to a future-weather forecast feed.
- The thermal comfort score is a temperature-target proxy, not a full PMV/PPD or ASHRAE 55 compliance calculation.
- EnergyPlus results reflect the configured simulation period; savings should not be extrapolated to annual performance without an annual baseline and controlled comparison.
