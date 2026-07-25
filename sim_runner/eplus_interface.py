"""
eplus_interface.py

The bridge between EnergyPlus and everything else. Two jobs:
  1. get_building_state()  -> read the latest simulation output as a dict
  2. apply_setpoints()     -> edit the IDF's thermostat schedule, ready for next run

IMPORTANT: The object/field names below (ThermostatSetpoint:DualSetpoint,
Schedule:Compact, zone name strings, output variable names) are TYPICAL for
DOE prototype building models but WILL need adjusting to match YOUR specific
.idf file. Open baseline.idf in a text editor, search for "Thermostat" and
"Zone," and update the constants below to match what you actually find.
"""

import os
import subprocess
import pandas as pd
from eppy.modeleditor import IDF

# ---------------------------------------------------------------------------
# CONFIG — adjust these paths and names to match your setup
# ---------------------------------------------------------------------------

# Path to the EnergyPlus install folder (contains Energy+.idd)
EPLUS_INSTALL_DIR = r"C:\EnergyPlusV26-1-0" # <-- CHANGE THIS
IDD_PATH = os.path.join(EPLUS_INSTALL_DIR, "Energy+.idd")
EPLUS_EXE = os.path.join(EPLUS_INSTALL_DIR, "energyplus.exe")

# Project paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDF_PATH = os.path.join(PROJECT_ROOT, "energyplus", "baseline.idf")
WEATHER_PATH = os.path.join(PROJECT_ROOT, "energyplus", "weather", "weather.epw")
RUN_DIR = os.path.join(PROJECT_ROOT, "energyplus", "current_run")

# Zone / schedule names — CHANGE to match your IDF
# Search your IDF for "ThermostatSetpoint:DualSetpoint" to find real zone names
# and for "Schedule:Compact" to find the matching heating/cooling schedule names.
ZONE_SCHEDULE_MAP = {
    # "zone_name_in_idf": "cooling_setpoint_schedule_name_in_idf"
    "Core_mid": "Clg-SetP-Sch",
}

IDF.setiddname(IDD_PATH)


# ---------------------------------------------------------------------------
# READ STATE
# ---------------------------------------------------------------------------

def get_building_state(run_dir: str = RUN_DIR) -> dict:
    """
    Reads the most recent EnergyPlus output CSV (eplusout.csv) and returns
    a summary dict of the current building state. Assumes the IDF has
    Output:Variable requests for Zone Mean Air Temperature, Zone Air
    Relative Humidity, and Facility Total Electricity Demand (add these to
    your IDF if they're missing — see note below).
    """
    csv_path = os.path.join(run_dir, "eplusout.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"No output found at {csv_path}. Run a simulation first with run_simulation()."
        )

    df = pd.read_csv(csv_path)
    last_row = df.iloc[-1]

    state = {}
    for col in df.columns:
        col_lower = col.lower()
        if "zone mean air temperature" in col_lower:
            state.setdefault("zone_temps", {})[col] = last_row[col]
        elif "zone air relative humidity" in col_lower:
            state.setdefault("zone_humidity", {})[col] = last_row[col]
        elif "electricity demand" in col_lower or "facility total electricity" in col_lower:
            state["energy_kw"] = last_row[col]

    # Fallback so downstream code never crashes on missing keys
    state.setdefault("zone_temps", {})
    state.setdefault("zone_humidity", {})
    state.setdefault("energy_kw", None)
    return state


# ---------------------------------------------------------------------------
# WRITE SETPOINTS
# ---------------------------------------------------------------------------

def apply_setpoints(zone: str, new_temp: float, idf_path: str = IDF_PATH):
    """
    Edits the cooling setpoint schedule for `zone` to a constant `new_temp`
    (Celsius) for the next simulation run. Uses a simple Schedule:Compact
    override — good enough for a hackathon closed loop.
    """
    if zone not in ZONE_SCHEDULE_MAP:
        raise ValueError(f"Unknown zone '{zone}'. Add it to ZONE_SCHEDULE_MAP.")

    schedule_name = ZONE_SCHEDULE_MAP[zone]
    idf = IDF(idf_path)

    schedules = idf.idfobjects["SCHEDULE:COMPACT"]
    target = next((s for s in schedules if s.Name == schedule_name), None)
    if target is None:
        raise ValueError(f"Schedule '{schedule_name}' not found in IDF.")

    # Overwrite with a simple "all day, every day, constant value" schedule.
    # Schedule:Compact fields are Field_1, Field_2, ... after Name/Type Limits.
    target.Field_1 = "Through: 12/31"
    target.Field_2 = "For: AllDays"
    target.Field_3 = "Until: 24:00"
    target.Field_4 = str(new_temp)

    idf.save(idf_path)
    return True


# ---------------------------------------------------------------------------
# RUN SIMULATION
# ---------------------------------------------------------------------------

def run_simulation(idf_path: str = IDF_PATH, weather_path: str = WEATHER_PATH,
                    run_dir: str = RUN_DIR):
    """
    Runs EnergyPlus once via command line and writes output into run_dir.
    Keep RunPeriod short in the IDF (e.g. a few days) so each loop cycle
    is fast — edit the RunPeriod object in the IDF directly, or automate
    that with eppy too if you want variable-length runs.
    """
    os.makedirs(run_dir, exist_ok=True)
    result = subprocess.run(
        [EPLUS_EXE, "--weather", weather_path, "--output-directory", run_dir,
         "-r", idf_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"EnergyPlus run failed:\n{result.stderr[-2000:]}")
    return run_dir


if __name__ == "__main__":
    # Quick manual test. Run this file directly after Phase 0.3.
    print("Running simulation...")
    run_simulation()
    print("Reading state...")
    state = get_building_state()
    print(state)
