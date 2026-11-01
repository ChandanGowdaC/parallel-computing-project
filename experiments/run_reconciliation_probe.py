#!/usr/bin/env python3
"""
run_reconciliation_probe.py — Step A & B reconciliation and tuning probe runs.
Matrix:
- Map: maps/tiled/kiva_4x2.map (132x92, N=400)
- Tuning seeds: [101, 202, 303]
- T_sim = 250 (50 cycles, h=5, w=10)
- Workloads: uniform and zoned (cross_zone_prob = 0.05)
- V in {1, 2, 3}, p in {1, 4, 8}
"""

import os
import sys
import subprocess
import time
import shutil
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
from scripts.verify_collision_freedom import verify_paths
BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")

TUNING_SEEDS = [101, 202, 303]
AGENTS = 400
MAP_FILE = "maps/tiled/kiva_4x2.map"
SIM_TIMESTEPS = 250
PLANNING_WINDOW = 10
PLANNING_HORIZON = 5


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    items = []
    for s in TUNING_SEEDS:
        for wl in ["uniform", "zoned"]:
            is_zoned = (wl == "zoned")
            for V in [1, 2, 3]:
                for p in [1, 4, 8]:
                    v_type = "V1" if p == 1 else "V2"
                    run_id = f"reconcile_kiva400_{v_type}_V{V}_{wl}_t{p}_s{s}"
                    items.append({
                        "run_id": run_id,
                        "seed": s,
                        "workload": wl,
                        "zoned": is_zoned,
                        "V": V,
                        "threads": p,
                    })

    total = len(items)
    print(f"Starting {total} reconciliation probe runs...")
    t_start = time.time()

    for idx, it in enumerate(items):
        rid = it["run_id"]
        csv_file = os.path.join(RAW_DIR, f"run_{rid}.csv")
        ep_file = os.path.join(RAW_DIR, f"episodes_{rid}.csv")
        out_dir = os.path.join(RAW_DIR, rid)
        paths_file = os.path.join(out_dir, "paths.txt")
        log_file = os.path.join(LOG_DIR, f"{rid}.log")

        cmd = [
            BINARY,
            "--scenario", "KIVA",
            "--map", MAP_FILE,
            "--solver", "PBS",
            "--agents", str(AGENTS),
            "--simulation_timesteps", str(SIM_TIMESTEPS),
            "--planning_window", str(PLANNING_WINDOW),
            "--planning_horizon", str(PLANNING_HORIZON),
            "--seed", str(it["seed"]),
            "--threads", str(it["threads"]),
            "--parallel", "on",
            "--vis_radius", str(it["V"]),
            "--task_zoning", "on" if it["zoned"] else "off",
            "--cross_zone_prob", "0.05",
            "--run_id", rid,
            "--output_dir", RAW_DIR,
            "--output", out_dir,
        ]

        t0 = time.time()
        with open(log_file, "w") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT)
        dt = time.time() - t0

        if proc.returncode != 0:
            print(f"[{idx+1}/{total}] {rid} FAILED ({dt:.2f}s)")
            sys.exit(1)

        paths_src = os.path.join(RAW_DIR, "paths.txt")
        if os.path.isfile(paths_src):
            os.makedirs(out_dir, exist_ok=True)
            shutil.move(paths_src, paths_file)

        ok, msg = verify_paths(paths_file)
        if not ok:
            print(f"[{idx+1}/{total}] {rid} COLLISION ({msg})")
            sys.exit(1)

        print(f"[{idx+1}/{total}] {rid} OK ({dt:.2f}s)")

    print(f"All {total} runs finished in {(time.time() - t_start)/60:.2f} minutes.")


if __name__ == "__main__":
    main()
