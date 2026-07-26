# Production Readiness and Integration Notes

EcoLoop-AI is a simulation demonstrator. This document describes the production mapping required for a building-management-system deployment; it does not implement BACnet, Modbus, cloud hosting, or physical controls.

## BACnet mapping approach

Use a site-approved BACnet integration service between the application and the BMS. Map application concepts to named BACnet objects under explicit ownership and priority rules.

| EcoLoop-AI concept | Typical BACnet object | Direction | Production control |
|---|---|---|---|
| Zone mean air temperature | `AI` / `AV` | Read | Validate engineering units, timestamp, quality, and stale-value timeout. |
| Zone humidity | `AI` / `AV` | Read | Validate 0–100% range and sensor health. |
| Facility electricity | `AI` / `AV` / meter object | Read | Capture interval, unit, and meter-quality metadata. |
| Cooling setpoint command | `AV` / schedule object | Write | Use priority array, command TTL, read-back, and local BMS interlock. |
| Equipment mode / alarm | `BI` / `BV` | Read | Block optimisation during fault, maintenance, or manual mode. |

The application should never write a raw BACnet point by name from an LLM response. A hardened adapter must validate the data contract, enforce a whitelist, perform write/read-back, and release the command at the agreed priority when expired.

## Modbus mapping approach

Where equipment exposes Modbus, use a dedicated gateway that exposes a documented register map to the application service.

| EcoLoop-AI concept | Typical Modbus representation | Required protection |
|---|---|---|
| Temperature and humidity | Input registers with scale factor | Validate signedness, scale, endianness, range, and polling age. |
| Electrical meter values | Input registers, often 32-bit | Validate register order, interval, units, and rollover. |
| Setpoint request | Holding register | Permit writes only through a gateway whitelist, acknowledgement, and rate limiter. |
| Equipment status | Coil / discrete input | Require state confirmation before issuing control. |

Do not expose a Modbus TCP endpoint to a browser or an LLM process. Segment it on the operational-technology network and terminate integration in a controlled gateway.

## Cybersecurity considerations

- Segment IT, application, and OT networks; apply deny-by-default firewall rules.
- Use mutual TLS for service-to-service links and an authenticated gateway for BMS protocols.
- Store secrets in a managed secrets store, not code, prompts, SQLite, or dashboard session state.
- Apply least-privilege service identities with per-building and per-point allowlists.
- Validate all telemetry schemas and reject malformed, stale, replayed, or out-of-range values.
- Maintain vulnerability management, patching, backup, incident-response, and supplier-access procedures.
- Treat prompt injection, tool misuse, model availability, and audit-log tampering as explicit threat scenarios.

## Authentication and authorisation

Production access should use enterprise identity (OIDC or SAML) and role-based authorisation:

| Role | Capability |
|---|---|
| Viewer | View dashboard and read audit history. |
| Facility Manager | Submit an override request with reason; cannot bypass Safety Supervisor. |
| Controls Engineer | Configure approved limits, point mapping, and commissioning mode. |
| Security Administrator | Manage identities, policies, certificates, and audit retention. |

Require step-up authentication for control-related actions, make the building and point scope explicit, and include the authenticated user identity in the audit event.

## Audit logging

The demonstrator logs agent inputs and reasoning, coordinator selection, safety evaluations, sensor anomalies, and manager requests in SQLite. A production implementation should additionally provide:

- append-only or tamper-evident event storage;
- time synchronisation and trace IDs across gateway, workflow, and BMS write/read-back;
- authenticated user identity and approval context;
- configurable retention, export, and incident-review controls; and
- alerting for repeated blocks, abnormal overrides, or missing audit signals.

## Safety Supervisor deployment

The Safety Supervisor should remain deterministic, versioned, independently tested, and separated from the model runtime. Its configuration—limits, allowable rate of change, sensor quality rules, and equipment interlocks—must be approved by controls engineering per site. The BMS must retain its own physical safeties, local mode, and fail-safe sequence; application logic is never a substitute for them.

## Future deployment architecture

```text
Facility Manager → SSO / RBAC → Operations UI → Application API
                                         │
                             Audit service / event store
                                         │
          Forecast + optimisation service → Safety Supervisor service
                                         │
                  BACnet / Modbus gateway with point allowlist
                                         │
                     BMS / PLC / equipment local interlocks
```

Deploy the API and workflow in a managed runtime with health checks, immutable releases, configuration management, telemetry, and a per-site digital-twin validation environment. Promote a policy only after offline simulation, commissioning, and controlled rollout.
