"""
server.py — MCP server exposing building control tools.

Run standalone: python mcp_server/server.py
Then test with mcp_server/test_client.py before wiring up any LLM.
"""

from mcp.server.fastmcp import FastMCP
from tools import (
    tool_get_building_state,
    tool_set_hvac_setpoint,
    tool_run_simulation,
    tool_get_energy_baseline,
    tool_log_decision,
)

mcp = FastMCP("eco-loop-building-agents")


@mcp.tool()
def get_building_state() -> dict:
    """Get the current building state: zone temperatures, humidity, and energy demand."""
    return tool_get_building_state()


@mcp.tool()
def set_hvac_setpoint(zone: str, temp: float) -> dict:
    """Set a new HVAC cooling setpoint (in Celsius) for a given zone."""
    return tool_set_hvac_setpoint(zone, temp)


@mcp.tool()
def run_simulation() -> dict:
    """Re-run the EnergyPlus simulation with the current setpoints and return the new state."""
    return tool_run_simulation()


@mcp.tool()
def get_energy_baseline() -> dict:
    """Get the stored baseline (fixed-schedule) energy consumption for comparison."""
    return tool_get_energy_baseline()


@mcp.tool()
def log_decision(agent: str, rationale: str, action: str) -> dict:
    """Log an agent's decision and rationale for dashboard display."""
    return tool_log_decision(agent, rationale, action)


if __name__ == "__main__":
    mcp.run()
