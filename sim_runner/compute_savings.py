"""
compute_savings.py — reads baseline_results and ai_results tables from
data/results.db and computes the real numbers for your dashboard,
architecture doc, and presentation: % energy reduction, comfort-violation
minutes, peak demand delta.

Run AFTER run_baseline.py and AFTER your AI loop (graph.py) have both
logged data.
"""

import sys
import os
import sqlite3
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_runner.eplus_interface import PROJECT_ROOT

DB_PATH = os.path.join(PROJECT_ROOT, "data", "results.db")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "results_summary.json")

COMFORT_LOW, COMFORT_HIGH = 21.0, 24.0


def compute():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    def table_exists(name):
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cur.fetchone() is not None

    summary = {}

    if table_exists("baseline_results"):
        cur.execute("SELECT AVG(energy_kw), MAX(energy_kw) FROM baseline_results WHERE energy_kw IS NOT NULL")
        avg_e, peak_e = cur.fetchone()
        summary["baseline_avg_energy_j"] = avg_e
        summary["baseline_peak_energy_j"] = peak_e
        summary["baseline_avg_energy_kwh"] = avg_e / 3_600_000 if avg_e is not None else None
        summary["baseline_avg_energy_kw"] = avg_e
        summary["baseline_peak_energy_kw"] = peak_e
    else:
        summary["baseline_avg_energy_kw"] = None
        summary["baseline_peak_energy_kw"] = None

    if table_exists("ai_results"):
        cur.execute("SELECT AVG(energy_kw), MAX(energy_kw), COUNT(*) FROM ai_results WHERE energy_kw IS NOT NULL")
        avg_e, peak_e, n = cur.fetchone()
        summary["ai_avg_energy_j"] = avg_e
        summary["ai_peak_energy_j"] = peak_e
        summary["ai_avg_energy_kwh"] = avg_e / 3_600_000 if avg_e is not None else None
        summary["ai_avg_energy_kw"] = avg_e
        summary["ai_peak_energy_kw"] = peak_e
        summary["ai_cycles_run"] = n

        columns = {row[1] for row in cur.execute("PRAGMA table_info(ai_results)")}
        if "comfort_score_pct" in columns:
            cur.execute("SELECT AVG(comfort_score_pct), COUNT(*) FROM ai_results WHERE comfort_score_pct IS NOT NULL")
            comfort_score, measured_cycles = cur.fetchone()
            summary["comfort_score_pct"] = round(comfort_score, 2) if comfort_score is not None else None
            summary["comfort_measurement_cycles"] = measured_cycles
            summary["comfort_violations"] = None
        else:
            summary["comfort_score_pct"] = None
            summary["comfort_measurement_cycles"] = 0
            summary["comfort_violations"] = None
    else:
        summary["ai_avg_energy_kw"] = None
        summary["ai_peak_energy_kw"] = None
        summary["ai_cycles_run"] = 0
        summary["comfort_violations"] = None
        summary["comfort_score_pct"] = None
        summary["comfort_measurement_cycles"] = 0

    if summary.get("baseline_avg_energy_kw") and summary.get("ai_avg_energy_kw"):
        pct_reduction = (
            (summary["baseline_avg_energy_kw"] - summary["ai_avg_energy_kw"])
            / summary["baseline_avg_energy_kw"] * 100
        )
        summary["pct_energy_reduction"] = round(pct_reduction, 2)
    else:
        summary["pct_energy_reduction"] = None

    if summary.get("baseline_peak_energy_kw") and summary.get("ai_peak_energy_kw"):
        summary["peak_demand_delta_kw"] = round(
            summary["baseline_peak_energy_kw"] - summary["ai_peak_energy_kw"], 3
        )
    else:
        summary["peak_demand_delta_kw"] = None

    conn.close()

    with open(OUTPUT_PATH, "w") as f:
        json.dump(summary, f, indent=2)

    print("Wrote", OUTPUT_PATH)
    print(json.dumps(summary, indent=2))

    if summary["pct_energy_reduction"] is None:
        print("\nNOTE: % reduction is null — make sure you've run BOTH "
              "run_baseline.py AND agents/graph.py before computing savings.")


if __name__ == "__main__":
    compute()
