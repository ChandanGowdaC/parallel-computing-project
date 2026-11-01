#!/usr/bin/env python3
"""
run_v2_probe.py — Step 2 Tuning Probe for V=2 at N=400.
Tuning seeds: [101, 202, 303]
Workloads: uniform, zoned
p in {1, 4, 8}
T_sim = 250 (50 cycles, h=5, w=10)
"""

import os
import sys
import subprocess
import csv
import time
import shutil
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")

TUNING_SEEDS = [101, 202, 303]
AGENTS = 400
MAP_FILE = "maps/tiled/kiva_4x2.map"
V = 2
THREAD_COUNTS = [1, 4, 8]
SIM_TIMESTEPS = 250
PLANNING_WINDOW = 10
PLANNING_HORIZON = 5

def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"

def verify_single_run(paths_file):
    from scripts.verify_collision_freedom import verify_paths
    if not os.path.isfile(paths_file):
        return True, "No paths file"
    return verify_paths(paths_file)

def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    git_commit = get_git_commit()

    work_items = []
    for seed in TUNING_SEEDS:
        for wl in ["uniform", "zoned"]:
            is_zoned = (wl == "zoned")
            for p in THREAD_COUNTS:
                v_type = "V1" if p == 1 else "V2"
                run_id = f"probe_kiva400_{v_type}_V{V}_{wl}_t{p}_s{seed}"
                work_items.append({
                    "type": v_type,
                    "workload": wl,
                    "zoned": is_zoned,
                    "vis_radius": V,
                    "threads": p,
                    "seed": seed,
                    "run_id": run_id
                })

    print(f"Running V=2 probe: {len(work_items)} runs...")
    completed = 0
    t0 = time.time()

    for item in work_items:
        completed += 1
        run_id = item["run_id"]
        out_subdir = os.path.join(RAW_DIR, run_id)
        run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
        ep_csv = os.path.join(RAW_DIR, f"episodes_{run_id}.csv")

        if os.path.isfile(run_csv) and os.path.isfile(ep_csv):
            try:
                with open(run_csv) as f:
                    r = csv.DictReader(f)
                    row = next(r)
                    if row.get("git_commit") == git_commit:
                        print(f"[{completed:2d}/{len(work_items)}] [REUSED] {run_id}")
                        continue
            except Exception:
                pass

        os.makedirs(out_subdir, exist_ok=True)
        cmd = [
            BINARY,
            "--scenario", "KIVA",
            "--map", MAP_FILE,
            "--solver", "PBS",
            "--agents", str(AGENTS),
            "--simulation_timesteps", str(SIM_TIMESTEPS),
            "--planning_window", str(PLANNING_WINDOW),
            "--planning_horizon", str(PLANNING_HORIZON),
            "--seed", str(item["seed"]),
            "--threads", str(item["threads"]),
            "--parallel", "on",
            "--vis_radius", str(V),
            "--task_zoning", "on" if item["zoned"] else "off",
            "--cross_zone_prob", "0.05",
            "--run_id", run_id,
            "--git_commit", git_commit,
            "--output_dir", RAW_DIR
        ]

        log_path = os.path.join(LOG_DIR, f"{run_id}.log")
        with open(log_path, "w") as log_f:
            p = subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT, text=True)

        if p.returncode != 0:
            print(f"[{completed:2d}/{len(work_items)}] [FAIL] {run_id}")
            continue

        paths_src = os.path.join(RAW_DIR, "paths.txt")
        paths_dst = os.path.join(out_subdir, "paths.txt")
        if os.path.isfile(paths_src):
            shutil.move(paths_src, paths_dst)

        ok, msg = verify_single_run(paths_dst)
        if not ok:
            print(f"[COLLISION in {run_id}]: {msg}", file=sys.stderr)
            sys.exit(1)

        with open(run_csv) as f:
            row = next(csv.DictReader(f))
            wall_ms = float(row.get("total_runtime_ms", 0))
            solv_ms = float(row.get("solver_runtime_ms", 0))
            print(f"[{completed:2d}/{len(work_items)}] {run_id:<36} wall={wall_ms:7.1f}ms solv={solv_ms:7.1f}ms ok")

        time.sleep(0.05)

    print(f"V=2 probe complete in {time.time() - t0:.1f} s")

if __name__ == "__main__":
    main()
