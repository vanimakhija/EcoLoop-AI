"""
test_client.py — sanity-check the tool functions directly, no LLM, no MCP
protocol overhead. Run this BEFORE wiring anything up to an agent, so you
know any later bugs are in the agent layer, not the tools themselves.
"""

from tools import (
    tool_get_building_state,
    tool_set_hvac_setpoint,
    tool_run_simulation,
    tool_log_decision,
)

if __name__ == "__main__":
    print("1. get_building_state():")
    print(tool_get_building_state())

    print("\n2. set_hvac_setpoint('Core_mid', 23.0):")
    print(tool_set_hvac_setpoint("Core_mid", 23.0))

    print("\n3. run_simulation() [this takes a while]:")
    print(tool_run_simulation())

    print("\n4. log_decision(...):")
    print(tool_log_decision("test_agent", "testing the logger", "no-op"))

    print("\nAll tool functions executed without error.")
