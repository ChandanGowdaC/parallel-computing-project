#!/usr/bin/env python3
"""
run_step4_probe.py — Step 4 Probe and Go/No-Go Gate Benchmark.

Matrix:
- Map: maps/tiled/kiva_4x2.map (132x92, N=400)
- Tuning seeds only: [101, 202, 303]
- T_sim = 250 (50 cycles, h=5, w=10)
- Two workloads:
  1. Uniform (task_zoning off)
  2. Zoned (task_zoning on, cross_zone_prob=0.05)
- Configurations per workload:
  - V0 (vanilla sequential, p=1)
  - GD-RHCR V in {3, 4, 5, 8}, p in {1, 8}
- Total runs: 3 seeds * 2 workloads * 9 configs = 54 runs.
"""

import os
import sys
import subprocess
import csv
import time
import shutil
import numpy as np
from collections import defaultdict

os.environ["MPLCONFIGDIR"] = "/tmp/mpl"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")

TUNING_SEEDS = [101, 202, 303]
AGENTS = 400
MAP_FILE = "maps/tiled/kiva_4x2.map"
VIS_RADII = [3, 4, 5, 8]
THREAD_COUNTS = [1, 8]
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
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(AGG_DIR, exist_ok=True)

    git_commit = get_git_commit()
    print("=" * 80)
    print("      STEP 4 PROBE BENCHMARK: TILED KIVA N=400 (T_sim = 250)")
    print(f"  Commit: {git_commit}")
    print(f"  Map: {MAP_FILE} (132x92)")
    print(f"  Tuning Seeds ({len(TUNING_SEEDS)}): {TUNING_SEEDS}")
    print("=" * 80)

    work_items = []
    for seed in TUNING_SEEDS:
        for workload in ["uniform", "zoned"]:
            is_zoned = (workload == "zoned")
            # V0
            run_id_v0 = f"probe_kiva400_v0_{workload}_s{seed}"
            work_items.append({
                "type": "V0",
                "workload": workload,
                "zoned": is_zoned,
                "vis_radius": 0,
                "threads": 1,
                "parallel": False,
                "seed": seed,
                "run_id": run_id_v0
            })
            for v in VIS_RADII:
                for p in THREAD_COUNTS:
                    v_type = "V1" if p == 1 else "V2"
                    run_id_p = f"probe_kiva400_{v_type}_V{v}_{workload}_t{p}_s{seed}"
                    work_items.append({
                        "type": v_type,
                        "workload": workload,
                        "zoned": is_zoned,
                        "vis_radius": v,
                        "threads": p,
                        "parallel": True,
                        "seed": seed,
                        "run_id": run_id_p
                    })

    total_runs = len(work_items)
    print(f"Total planned probe runs: {total_runs}")

    run_records = []
    completed = 0
    t0_probe = time.time()

    for item in work_items:
        completed += 1
        run_id = item["run_id"]
        out_subdir = os.path.join(RAW_DIR, run_id)
        run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
        ep_csv = os.path.join(RAW_DIR, f"episodes_{run_id}.csv")

        # Reuse if matching commit
        if os.path.isfile(run_csv) and os.path.isfile(ep_csv):
            try:
                with open(run_csv) as f:
                    r = csv.DictReader(f)
                    row = next(r)
                    if row.get("git_commit") == git_commit:
                        item["metrics"] = row
                        run_records.append(item)
                        print(f"[{completed:2d}/{total_runs}] [REUSED] {run_id}")
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
            "--parallel", "on" if item["parallel"] else "off",
            "--vis_radius", str(item["vis_radius"]),
            "--task_zoning", "on" if item["zoned"] else "off",
            "--cross_zone_prob", "0.05",
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
            print(f"[{completed:2d}/{total_runs}] [FAIL returncode={p.returncode}] {run_id}")
            continue

        paths_src = os.path.join(RAW_DIR, "paths.txt")
        paths_dst = os.path.join(out_subdir, "paths.txt")
        if os.path.isfile(paths_src):
            shutil.move(paths_src, paths_dst)

        ok, msg = verify_single_run(paths_dst)
        if not ok:
            print(f"[{completed:2d}/{total_runs}] [COLLISION DETECTED in {run_id}]: {msg}", file=sys.stderr)
            sys.exit(1)

        if os.path.isfile(run_csv):
            with open(run_csv) as f:
                r = csv.DictReader(f)
                row = next(r)
                item["metrics"] = row
                run_records.append(item)
                wall_ms = float(row.get("total_runtime_ms", t_elapsed * 1000))
                solv_ms = float(row.get("solver_runtime_ms", 0.0))
                print(f"[{completed:2d}/{total_runs}] {run_id:<40} wall={wall_ms:7.1f}ms solv={solv_ms:7.1f}ms ok")

        time.sleep(0.05)

    t_total = time.time() - t0_probe
    print("=" * 80)
    print(f"Step 4 Probe finished in {t_total:.1f} s ({len(run_records)}/{total_runs} runs)")
    print("=" * 80)

    # ─────────────────────────────────────────────────────────────
    # Compile Probe Metrics
    # ─────────────────────────────────────────────────────────────
    v0_solv = {}
    v0_tp = {}
    v1_solv = {}

    for item in run_records:
        m = item["metrics"]
        wl = item["workload"]
        seed = item["seed"]
        v = item["vis_radius"]
        v_type = item["type"]
        solv = float(m["solver_runtime_ms"])
        tp = float(m["throughput"])

        if v_type == "V0":
            v0_solv[(wl, seed)] = solv
            v0_tp[(wl, seed)] = tp
        elif v_type == "V1":
            v1_solv[(wl, v, seed)] = solv

    # Group by (workload, V, p)
    summary_rows = []
    for wl in ["uniform", "zoned"]:
        for v in VIS_RADII:
            # We care about p=8 for speedup vs V0, and p=1 for V1/V0
            sp_v0_list = []
            v1_v0_list = []
            local_merge_rate_list = []
            global_fallback_rate_list = []
            largest_frac_list = []
            tp_ratio_list = []
            solver_ms_list = []

            for item in run_records:
                if item["workload"] == wl and item["vis_radius"] == v and item["threads"] == 8 and item["type"] == "V2":
                    seed = item["seed"]
                    m = item["metrics"]
                    run_id = item["run_id"]
                    solv = float(m["solver_runtime_ms"])
                    tp = float(m["throughput"])
                    solver_ms_list.append(solv)

                    # Speedup vs V0
                    if (wl, seed) in v0_solv and solv > 0:
                        sp_v0_list.append(v0_solv[(wl, seed)] / solv)

                    # V1 / V0 overhead
                    if (wl, seed) in v0_solv and (wl, v, seed) in v1_solv and v0_solv[(wl, seed)] > 0:
                        v1_v0_list.append(v1_solv[(wl, v, seed)] / v0_solv[(wl, seed)])

                    # Throughput ratio vs V0
                    if (wl, seed) in v0_tp and v0_tp[(wl, seed)] > 0:
                        tp_ratio_list.append(tp / v0_tp[(wl, seed)])

                    # Read episodes CSV
                    ep_csv = os.path.join(RAW_DIR, f"episodes_{run_id}.csv")
                    ep_merges = 0
                    ep_fallbacks = 0
                    ep_largest_fracs = []
                    total_eps = 0

                    if os.path.isfile(ep_csv):
                        with open(ep_csv) as f:
                            r = csv.DictReader(f)
                            for row in r:
                                total_eps += 1
                                if int(row.get("merges_performed", 0)) > 0 or float(row.get("local_resolve_time_ms", 0)) > 0:
                                    ep_merges += 1
                                if int(row.get("global_fallback_invoked", 0)) == 1:
                                    ep_fallbacks += 1
                                gs_str = row.get("group_sizes", "")
                                if gs_str:
                                    sizes = [int(s) for s in gs_str.split(",") if s.strip()]
                                    if sizes:
                                        ep_largest_fracs.append(max(sizes) / float(AGENTS))

                    local_merge_rate_list.append((ep_merges / float(total_eps)) if total_eps > 0 else 0.0)
                    global_fallback_rate_list.append((ep_fallbacks / float(total_eps)) if total_eps > 0 else 0.0)
                    largest_frac_list.append(float(np.mean(ep_largest_fracs)) if ep_largest_fracs else 1.0)

            # Compute stats
            sp_med, sp_low, sp_high = bootstrap_ci(sp_v0_list, np.median)
            ov_med, ov_low, ov_high = bootstrap_ci(v1_v0_list, np.median)
            lm_med, lm_low, lm_high = bootstrap_ci([x * 100.0 for x in local_merge_rate_list], np.median)
            gf_med, gf_low, gf_high = bootstrap_ci([x * 100.0 for x in global_fallback_rate_list], np.median)
            lf_med, lf_low, lf_high = bootstrap_ci(largest_frac_list, np.median)
            tp_med, tp_low, tp_high = bootstrap_ci(tp_ratio_list, np.median)
            solv_med, solv_low, solv_high = bootstrap_ci(solver_ms_list, np.median)

            summary_rows.append({
                "workload": wl,
                "V": v,
                "solv_ms_med": solv_med,
                "solv_ms_low": solv_low,
                "solv_ms_high": solv_high,
                "speedup_v0_med": sp_med,
                "speedup_v0_low": sp_low,
                "speedup_v0_high": sp_high,
                "v1_v0_med": ov_med,
                "v1_v0_low": ov_low,
                "v1_v0_high": ov_high,
                "local_merge_med": lm_med,
                "local_merge_low": lm_low,
                "local_merge_high": lm_high,
                "fallback_med": gf_med,
                "fallback_low": gf_low,
                "fallback_high": gf_high,
                "largest_frac_med": lf_med,
                "largest_frac_low": lf_low,
                "largest_frac_high": lf_high,
                "tp_ratio_med": tp_med,
                "tp_ratio_low": tp_low,
                "tp_ratio_high": tp_high
            })

    # Write summary CSV
    out_csv = os.path.join(AGG_DIR, "step4_probe_summary.csv")
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        for r in summary_rows:
            writer.writerow(r)

    print(f"\nSaved Step 4 Probe Summary to: {out_csv}\n")

if __name__ == "__main__":
    main()
