"""
run_baseline.py — runs the ORIGINAL, unmodified baseline.idf (fixed
schedule, no AI involvement) and logs its results to a separate table
so you can compare fairly against your AI-controlled run.

Run this BEFORE you let single_agent_loop.py or graph.py overwrite
baseline.idf's schedules — or better, keep a pristine copy:
    cp energyplus/baseline.idf energyplus/baseline_pristine.idf
and point this script at the pristine copy.
"""

import sys
import os
import sqlite3
import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_runner.eplus_interface import run_simulation, get_building_state, PROJECT_ROOT

PRISTINE_IDF = os.path.join(PROJECT_ROOT, "energyplus", "baseline_pristine.idf")
BASELINE_RUN_DIR = os.path.join(PROJECT_ROOT, "energyplus", "baseline_run")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "results.db")


def run_and_log():
    idf_to_use = PRISTINE_IDF if os.path.exists(PRISTINE_IDF) else os.path.join(
        PROJECT_ROOT, "energyplus", "baseline.idf"
    )
    run_simulation(idf_path=idf_to_use, run_dir=BASELINE_RUN_DIR)
    state = get_building_state(run_dir=BASELINE_RUN_DIR)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS baseline_results (
            timestamp TEXT, energy_kw REAL, raw_state TEXT
        )
    """)
    conn.execute(
        "INSERT INTO baseline_results VALUES (?, ?, ?)",
        (datetime.datetime.now().isoformat(), state.get("energy_kw"), str(state))
    )
    conn.commit()
    conn.close()

    print("Baseline run complete. State:", state)
    return state


if __name__ == "__main__":
    run_and_log()
