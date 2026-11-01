#!/usr/bin/env python3
"""
run_sorting_sparse_campaign.py — Sparse Regime Sorting Center Scaling Benchmark.

Executes Step 3 of the integration directives:
- Map: maps/sorting_map.grid (77x37, open floor sortation layout)
- N in {25, 50, 100, 200}
- V in {6, 10}
- p in {1, 2, 4, 8, 11}
- T_sim = 250 (50 replanning cycles, h=5, w=10)
- 5 Reporting seeds: [42, 100, 2026, 3141, 5926] (disjoint from tuning seeds 101, 202, 303)
- Variants: V0 (vanilla), V1 (GD-RHCR p=1), V2 (GD-RHCR p in {2, 4, 8, 11})
- Total runs: 4 N * [1 + 2 V * 5 p] * 5 seeds = 220 runs.
- Interleaves runs seed-by-seed.
- Enforces code freeze and clean tree.
- Verifies collision-freedom on every run.
- Computes speedup vs V0 and vs V1, efficiency, group metrics, fallback rates with 95% bootstrap CIs.
"""

import os
import sys
import subprocess
import csv
import time
import math
import shutil
import re
from collections import defaultdict
import numpy as np

os.environ["MPLCONFIGDIR"] = "/tmp/mpl"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")

REPORTING_SEEDS = [42, 100, 2026, 3141, 5926]
AGENT_COUNTS = [25, 50, 100, 200]
VIS_RADII = [6, 10]
THREAD_COUNTS = [1, 2, 4, 8, 11]
SIM_TIMESTEPS = 250
PLANNING_WINDOW = 10
PLANNING_HORIZON = 5
MAP_FILE = "maps/sorting_map.grid"

def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"

def check_clean_working_tree():
    try:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        dirty_lines = []
        for line in res.stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            path = line_str[3:].strip()
            if path.startswith("results/") or path.startswith("build/") or path.endswith(".log") or path.startswith("maps/tiled/"):
                continue
            dirty_lines.append(line_str)
        if dirty_lines:
            print("[FATAL ERROR] Code freeze active! Dirty working tree detected:", file=sys.stderr)
            for d in dirty_lines:
                print(f"  {d}", file=sys.stderr)
            print("Commit or stash changes before running benchmark.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[FATAL ERROR] Git status check failed: {e}", file=sys.stderr)
        sys.exit(1)

def verify_single_run(paths_file):
    from scripts.verify_collision_freedom import verify_paths
    if not os.path.isfile(paths_file):
        return True, "No paths file"
    return verify_paths(paths_file)

def bootstrap_ci(data, stat_fn=np.median, n_boot=2000, alpha=0.05):
    if not data:
        return 0.0, 0.0, 0.0
    if len(data) == 1:
        return float(data[0]), float(data[0]), float(data[0])
    import random
    n = len(data)
    boot_stats = []
    for _ in range(n_boot):
        sample = [random.choice(data) for _ in range(n)]
        boot_stats.append(float(stat_fn(sample)))
    boot_stats.sort()
    low = boot_stats[int(alpha / 2 * n_boot)]
    high = boot_stats[int((1 - alpha / 2) * n_boot)]
    point = float(stat_fn(data))
    return point, low, high

def main():
    check_clean_working_tree()
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(AGG_DIR, exist_ok=True)

    git_commit = get_git_commit()
    print("=" * 80)
    print("      SPARSE REGIME SORTING CENTER SCALING CAMPAIGN (T_sim = 250)")
    print(f"  Commit: {git_commit}")
    print(f"  Map: {MAP_FILE} (77x37)")
    print(f"  Agents: {AGENT_COUNTS}")
    print(f"  Radii V: {VIS_RADII}")
    print(f"  Threads p: {THREAD_COUNTS}")
    print(f"  Reporting Seeds ({len(REPORTING_SEEDS)}): {REPORTING_SEEDS}")
    print("=" * 80)

    # Build work queue: interleaved seed-by-seed
    # Per seed: V0, then for each V: V1 (p=1), then V2 (p in 2,4,8,11)
    work_items = []
    for seed in REPORTING_SEEDS:
        for n in AGENT_COUNTS:
            # V0: Vanilla sequential
            run_id_v0 = f"sorting_v0_a{n}_t1_s{seed}"
            work_items.append({
                "type": "V0",
                "agents": n,
                "threads": 1,
                "parallel": False,
                "vis_radius": 0,
                "seed": seed,
                "run_id": run_id_v0
            })
            for v in VIS_RADII:
                # V1: GD-RHCR p=1
                run_id_v1 = f"sorting_v1_V{v}_a{n}_t1_s{seed}"
                work_items.append({
                    "type": "V1",
                    "agents": n,
                    "threads": 1,
                    "parallel": True,
                    "vis_radius": v,
                    "seed": seed,
                    "run_id": run_id_v1
                })
                # V2: GD-RHCR p in {2, 4, 8, 11}
                for p in [2, 4, 8, 11]:
                    run_id_v2 = f"sorting_v2_V{v}_a{n}_t{p}_s{seed}"
                    work_items.append({
                        "type": "V2",
                        "agents": n,
                        "threads": p,
                        "parallel": True,
                        "vis_radius": v,
                        "seed": seed,
                        "run_id": run_id_v2
                    })

    total_runs = len(work_items)
    print(f"Total planned runs: {total_runs}")

    run_records = []
    completed = 0
    t0_campaign = time.time()

    for item in work_items:
        completed += 1
        run_id = item["run_id"]
        out_subdir = os.path.join(RAW_DIR, run_id)
        run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
        ep_csv = os.path.join(RAW_DIR, f"episodes_{run_id}.csv")

        # Resume if already executed under this commit
        if os.path.isfile(run_csv) and os.path.isfile(ep_csv):
            # check commit inside run_csv
            try:
                with open(run_csv) as f:
                    r = csv.DictReader(f)
                    row = next(r)
                    if row.get("git_commit") == git_commit:
                        item["metrics"] = row
                        run_records.append(item)
                        print(f"[{completed:3d}/{total_runs}] [REUSED] {run_id}")
                        continue
            except Exception:
                pass

        os.makedirs(out_subdir, exist_ok=True)
        cmd = [
            BINARY,
            "--scenario", "SORTING",
            "--map", MAP_FILE,
            "--solver", "PBS",
            "--agents", str(item["agents"]),
            "--simulation_timesteps", str(SIM_TIMESTEPS),
            "--planning_window", str(PLANNING_WINDOW),
            "--planning_horizon", str(PLANNING_HORIZON),
            "--seed", str(item["seed"]),
            "--threads", str(item["threads"]),
            "--parallel", "on" if item["parallel"] else "off",
            "--vis_radius", str(item["vis_radius"]),
            "--run_id", run_id,
            "--git_commit", git_commit,
            "--output_dir", RAW_DIR
        ]

        log_path = os.path.join(LOG_DIR, f"{run_id}.log")
        t_start = time.time()
        with open(log_path, "w") as log_f:
            p = subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT, text=True)
        t_elapsed = time.time() - t_start

        if p.returncode != 0:
            print(f"[{completed:3d}/{total_runs}] [FAIL returncode={p.returncode}] {run_id}")
            continue

        # Move paths.txt to subdir for verifier
        paths_src = os.path.join(RAW_DIR, "paths.txt")
        paths_dst = os.path.join(out_subdir, "paths.txt")
        if os.path.isfile(paths_src):
            shutil.move(paths_src, paths_dst)

        # Run verifier
        ok, msg = verify_single_run(paths_dst)
        if not ok:
            print(f"[{completed:3d}/{total_runs}] [COLLISION DETECTED in {run_id}]: {msg}", file=sys.stderr)
            sys.exit(1)

        # Parse run metrics
        if os.path.isfile(run_csv):
            with open(run_csv) as f:
                r = csv.DictReader(f)
                row = next(r)
                item["metrics"] = row
                run_records.append(item)
                wall_ms = float(row.get("total_runtime_ms", t_elapsed * 1000))
                solv_ms = float(row.get("solver_runtime_ms", 0.0))
                print(f"[{completed:3d}/{total_runs}] {run_id:<32} wall={wall_ms:7.1f}ms solv={solv_ms:7.1f}ms ok")
        else:
            print(f"[{completed:3d}/{total_runs}] Missing run CSV: {run_csv}")

        # Thermal pause
        time.sleep(0.05)

    t_total = time.time() - t0_campaign
    print("=" * 80)
    print(f"Campaign finished in {t_total:.1f} s ({len(run_records)}/{total_runs} successful runs)")
    print("=" * 80)

    # ─────────────────────────────────────────────────────────────
    # Aggregation & Analysis
    # ─────────────────────────────────────────────────────────────
    # Group runs by (agents, V, threads, variant_type)
    # Also parse episode metrics for group sizes and fallbacks
    data_by_cfg = defaultdict(lambda: {
        "wall_ms": [],
        "solver_ms": [],
        "throughput": [],
        "tasks": [],
        "mean_group_count": [],
        "largest_group_frac": [],
        "fallback_rate": []
    })

    # Lookup map for pairing: (agents, seed) -> V0 runtime
    v0_wall = {}
    v0_solv = {}
    # (agents, V, seed) -> V1 runtime
    v1_wall = {}
    v1_solv = {}

    for item in run_records:
        m = item["metrics"]
        n = item["agents"]
        seed = item["seed"]
        v = item["vis_radius"]
        p = item["threads"]
        v_type = item["type"]
        run_id = item["run_id"]

        wall = float(m["total_runtime_ms"])
        solv = float(m["solver_runtime_ms"])
        tp = float(m["throughput"])
        tasks = int(m["num_tasks_completed"])

        if v_type == "V0":
            v0_wall[(n, seed)] = wall
            v0_solv[(n, seed)] = solv
        elif v_type == "V1":
            v1_wall[(n, v, seed)] = wall
            v1_solv[(n, v, seed)] = solv

        # Read episodes CSV for group count, largest group fraction, fallback rate
        ep_csv = os.path.join(RAW_DIR, f"episodes_{run_id}.csv")
        ep_group_counts = []
        ep_largest_fracs = []
        ep_fallbacks = []

        if os.path.isfile(ep_csv):
            with open(ep_csv) as f:
                r = csv.DictReader(f)
                for row in r:
                    ng = int(row.get("num_groups", 1))
                    ep_group_counts.append(ng)
                    fb = int(row.get("global_fallback_invoked", 0))
                    ep_fallbacks.append(fb)
                    gs_str = row.get("group_sizes", "")
                    if gs_str:
                        sizes = [int(s) for s in gs_str.split(",") if s.strip()]
                        if sizes:
                            ep_largest_fracs.append(max(sizes) / float(n))
                        else:
                            ep_largest_fracs.append(1.0)
                    else:
                        ep_largest_fracs.append(1.0)

        mean_ng = float(np.mean(ep_group_counts)) if ep_group_counts else 1.0
        mean_lf = float(np.mean(ep_largest_fracs)) if ep_largest_fracs else 1.0
        fb_rate = float(np.mean(ep_fallbacks)) if ep_fallbacks else 0.0

        key = (n, v, p, v_type)
        data_by_cfg[key]["wall_ms"].append(wall)
        data_by_cfg[key]["solver_ms"].append(solv)
        data_by_cfg[key]["throughput"].append(tp)
        data_by_cfg[key]["tasks"].append(tasks)
        data_by_cfg[key]["mean_group_count"].append(mean_ng)
        data_by_cfg[key]["largest_group_frac"].append(mean_lf)
        data_by_cfg[key]["fallback_rate"].append(fb_rate)

    # Compute paired speedups per config
    # Output summary CSV
    summary_path = os.path.join(AGG_DIR, "sorting_sparse_summary.csv")
    with open(summary_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "agents", "V", "p", "variant",
            "solver_ms_med", "solver_ms_ci_low", "solver_ms_ci_high",
            "speedup_v0_med", "speedup_v0_ci_low", "speedup_v0_ci_high",
            "speedup_v1_med", "speedup_v1_ci_low", "speedup_v1_ci_high",
            "efficiency_med", "efficiency_ci_low", "efficiency_ci_high",
            "v1_v0_overhead_med", "v1_v0_overhead_ci_low", "v1_v0_overhead_ci_high",
            "mean_group_count_med", "mean_group_count_ci_low", "mean_group_count_ci_high",
            "largest_group_frac_med", "largest_group_frac_ci_low", "largest_group_frac_ci_high",
            "fallback_rate_pct_med", "fallback_rate_pct_ci_low", "fallback_rate_pct_ci_high",
            "throughput_ratio_v0_med", "throughput_ratio_v0_ci_low", "throughput_ratio_v0_ci_high"
        ])

        for n in AGENT_COUNTS:
            # Baseline V0
            v0_solvs = data_by_cfg[(n, 0, 1, "V0")]["solver_ms"]
            s_med, s_low, s_high = bootstrap_ci(v0_solvs, np.median)
            writer.writerow([
                n, 0, 1, "V0",
                f"{s_med:.2f}", f"{s_low:.2f}", f"{s_high:.2f}",
                "1.00", "1.00", "1.00",
                "1.00", "1.00", "1.00",
                "1.00", "1.00", "1.00",
                "1.00", "1.00", "1.00",
                "1.0", "1.0", "1.0",
                "1.00", "1.00", "1.00",
                "0.0", "0.0", "0.0",
                "1.00", "1.00", "1.00"
            ])

            for v in VIS_RADII:
                for p in THREAD_COUNTS:
                    v_type = "V1" if p == 1 else "V2"
                    cfg_data = data_by_cfg[(n, v, p, v_type)]
                    p_solvs = cfg_data["solver_ms"]
                    if not p_solvs:
                        continue

                    s_med, s_low, s_high = bootstrap_ci(p_solvs, np.median)

                    # Compute paired speedup vs V0
                    sp_v0_list = []
                    sp_v1_list = []
                    eff_list = []
                    v1_v0_list = []
                    tp_ratio_list = []

                    for item in run_records:
                        if item["agents"] == n and item["vis_radius"] == v and item["threads"] == p and item["type"] == v_type:
                            seed = item["seed"]
                            m = item["metrics"]
                            solv = float(m["solver_runtime_ms"])
                            tp = float(m["throughput"])

                            if (n, seed) in v0_solv and solv > 0:
                                sp_v0 = v0_solv[(n, seed)] / solv
                                sp_v0_list.append(sp_v0)
                                eff_list.append(sp_v0 / p)

                            if (n, v, seed) in v1_solv and solv > 0:
                                sp_v1 = v1_solv[(n, v, seed)] / solv
                                sp_v1_list.append(sp_v1)

                            if (n, seed) in v0_solv and (n, v, seed) in v1_solv:
                                v1_v0_list.append(v1_solv[(n, v, seed)] / v0_solv[(n, seed)])

                            # throughput ratio vs V0
                            for v0_item in run_records:
                                if v0_item["agents"] == n and v0_item["seed"] == seed and v0_item["type"] == "V0":
                                    v0_tp = float(v0_item["metrics"]["throughput"])
                                    if v0_tp > 0:
                                        tp_ratio_list.append(tp / v0_tp)

                    sp_v0_med, sp_v0_low, sp_v0_high = bootstrap_ci(sp_v0_list, np.median)
                    sp_v1_med, sp_v1_low, sp_v1_high = bootstrap_ci(sp_v1_list, np.median)
                    eff_med, eff_low, eff_high = bootstrap_ci(eff_list, np.median)
                    ov_med, ov_low, ov_high = bootstrap_ci(v1_v0_list, np.median)
                    tpr_med, tpr_low, tpr_high = bootstrap_ci(tp_ratio_list, np.median)

                    mgc_med, mgc_low, mgc_high = bootstrap_ci(cfg_data["mean_group_count"], np.median)
                    lgf_med, lgf_low, lgf_high = bootstrap_ci(cfg_data["largest_group_frac"], np.median)
                    fb_med, fb_low, fb_high = bootstrap_ci([x * 100.0 for x in cfg_data["fallback_rate"]], np.median)

                    writer.writerow([
                        n, v, p, v_type,
                        f"{s_med:.2f}", f"{s_low:.2f}", f"{s_high:.2f}",
                        f"{sp_v0_med:.3f}", f"{sp_v0_low:.3f}", f"{sp_v0_high:.3f}",
                        f"{sp_v1_med:.3f}", f"{sp_v1_low:.3f}", f"{sp_v1_high:.3f}",
                        f"{eff_med:.3f}", f"{eff_low:.3f}", f"{eff_high:.3f}",
                        f"{ov_med:.3f}", f"{ov_low:.3f}", f"{ov_high:.3f}",
                        f"{mgc_med:.1f}", f"{mgc_low:.1f}", f"{mgc_high:.1f}",
                        f"{lgf_med:.3f}", f"{lgf_low:.3f}", f"{lgf_high:.3f}",
                        f"{fb_med:.1f}", f"{fb_low:.1f}", f"{fb_high:.1f}",
                        f"{tpr_med:.3f}", f"{tpr_low:.3f}", f"{tpr_high:.3f}"
                    ])

    print(f"Saved aggregated summary to: {summary_path}")

if __name__ == "__main__":
    main()
