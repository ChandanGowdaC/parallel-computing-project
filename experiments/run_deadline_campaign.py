#!/usr/bin/env python3
"""
run_deadline_campaign.py — Deadline-Aware Replanning & Real-Time Coupling Experiments.

Matrix:
1. Arrival Rate Sweep (Lambda):
   - N = 400 (maps/tiled/kiva_4x2.map)
   - Workloads: Uniform and Zoned (cross_zone_prob = 0.05)
   - Variants:
       - V0 (centralized sequential RHCR, p=1)
       - V1 (GD-RHCR 1 thread, V*=1)
       - V2 (GD-RHCR 4 threads, V*=1)
   - Arrival rates (6 levels): lambda in [0.2, 0.5, 0.8, 1.2, 1.6, 2.0]
   - Tau levels:
       - tau_1 = 0.012 s (tight budget: 60 ms)
       - tau_2 = 0.020 s (moderate budget: 100 ms)
       - tau_3 = 0.050 s (loose control: 250 ms)
   - Policy: EDF
   - Reporting seeds: [42, 100, 2026, 3141, 5926]

2. Scheduling Policy Comparison:
   - Policies: FIFO, EDF, DEADLINE_AWARE
   - Variant: V2 (4 threads, V*=1)
   - Workload: Zoned
   - Arrival rates: [0.5, 1.2, 2.0]
   - Tau: tau_1 = 0.012 s
   - Reporting seeds: [42, 100, 2026, 3141, 5926]
"""

import os
import sys
import subprocess
import csv
import time
import shutil
import random
import numpy as np
from collections import defaultdict

os.environ["MPLCONFIGDIR"] = "/tmp/mpl"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
from scripts.verify_collision_freedom import verify_paths

BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")

REPORTING_SEEDS = [42, 100, 2026, 3141, 5926]
MAP_FILE = "maps/tiled/kiva_4x2.map"
AGENTS = 400
SIM_TIMESTEPS = 250
PLANNING_WINDOW = 10
PLANNING_HORIZON = 5
DEADLINE_FACTOR = 2.0


def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def bootstrap_ci(data, stat_fn=np.median, n_boot=2000, alpha=0.05):
    if not data:
        return 0.0, 0.0, 0.0
    if len(data) == 1:
        return float(data[0]), float(data[0]), float(data[0])
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


def run_experiment(item, git_commit):
    run_id = item["run_id"]
    csv_file = os.path.join(RAW_DIR, f"run_{run_id}.csv")
    out_dir = os.path.join(RAW_DIR, run_id)
    paths_file = os.path.join(out_dir, "paths.txt")
    log_file = os.path.join(LOG_DIR, f"{run_id}.log")

    if os.path.isfile(csv_file) and os.path.isfile(paths_file):
        ok, msg = verify_paths(paths_file)
        if ok:
            return True, "Resumed"

    cmd = [
        BINARY,
        "--scenario", "KIVA",
        "--solver", "PBS",
        "--map", MAP_FILE,
        "--agents", str(AGENTS),
        "--simulation_timesteps", str(SIM_TIMESTEPS),
        "--planning_window", str(PLANNING_WINDOW),
        "--planning_horizon", str(PLANNING_HORIZON),
        "--seed", str(item["seed"]),
        "--run_id", run_id,
        "--output_dir", RAW_DIR,
        "--output", out_dir,
        "--git_commit", git_commit,
        "--deadline", "on",
        "--deadline_factor", str(DEADLINE_FACTOR),
        "--task_arrival_rate", str(item["arrival_rate"]),
        "--scheduling_policy", item["policy"],
        "--realtime_coupling", "on",
        "--planning_tau", str(item["tau"]),
    ]

    if item["zoned"]:
        cmd.extend(["--task_zoning", "on", "--cross_zone_prob", "0.05"])
    else:
        cmd.extend(["--task_zoning", "off"])

    if item["variant"] == "V0":
        cmd.extend(["--parallel", "off", "--vis_radius", "0", "--threads", "1"])
    elif item["variant"] == "V1":
        cmd.extend(["--parallel", "on", "--vis_radius", "1", "--threads", "1"])
    elif item["variant"] == "V2":
        cmd.extend(["--parallel", "on", "--vis_radius", "1", "--threads", "4"])

    with open(log_file, "w") as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)

    if proc.returncode != 0:
        return False, f"Exit code {proc.returncode}"

    paths_src = os.path.join(RAW_DIR, "paths.txt")
    if os.path.isfile(paths_src):
        os.makedirs(out_dir, exist_ok=True)
        shutil.move(paths_src, paths_file)

    ok, msg = verify_paths(paths_file)
    if not ok:
        return False, f"Collision: {msg}"

    return True, "Success"


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(AGG_DIR, exist_ok=True)

    git_commit = get_git_commit()
    print("=" * 80)
    print("      DEADLINE EXPERIMENTS & REAL-TIME PLANNING COUPLING")
    print(f"  Commit: {git_commit}")
    print("=" * 80)

    work_items = []

    # 1. Main Arrival Rate Sweep (interleaved seed-by-seed)
    lambda_levels = [0.2, 0.5, 0.8, 1.2, 1.6, 2.0]
    tau_levels = [0.012, 0.020, 0.050]

    for seed in REPORTING_SEEDS:
        for wl in ["uniform", "zoned"]:
            is_zoned = (wl == "zoned")
            for tau in tau_levels:
                for lam in lambda_levels:
                    for var in ["V0", "V1", "V2"]:
                        rid = f"dl_swp_{var}_{wl}_tau{int(tau*1000)}ms_lam{int(lam*10)}_s{seed}"
                        work_items.append({
                            "type": "sweep",
                            "run_id": rid,
                            "seed": seed,
                            "workload": wl,
                            "zoned": is_zoned,
                            "variant": var,
                            "arrival_rate": lam,
                            "tau": tau,
                            "policy": "EDF",
                        })

    # 2. Policy Comparison
    policy_lambdas = [0.5, 1.2, 2.0]
    for seed in REPORTING_SEEDS:
        for pol in ["FIFO", "EDF", "DEADLINE_AWARE"]:
            for lam in policy_lambdas:
                rid = f"dl_pol_{pol}_lam{int(lam*10)}_s{seed}"
                work_items.append({
                    "type": "policy",
                    "run_id": rid,
                    "seed": seed,
                    "workload": "zoned",
                    "zoned": True,
                    "variant": "V2",
                    "arrival_rate": lam,
                    "tau": 0.012,
                    "policy": pol,
                })

    print(f"Total deadline experiment runs: {len(work_items)}")
    total = len(work_items)
    t_start = time.time()
    success_count = 0

    for idx, item in enumerate(work_items):
        elapsed = time.time() - t_start
        rate = (idx / elapsed) if elapsed > 0 else 0
        rem_s = ((total - idx) / rate) if rate > 0 else 0
        print(f"[{idx+1}/{total} | {rem_s/60:.1f}m left] {item['run_id']} ... ", end="", flush=True)

        t0 = time.time()
        ok, msg = run_experiment(item, git_commit)
        dt = time.time() - t0

        if ok:
            print(f"OK ({dt:.2f}s, {msg})")
            success_count += 1
        else:
            print(f"FAILED ({dt:.2f}s, {msg})")
            sys.exit(1)

    print(f"\nAll {total} runs finished in {(time.time() - t_start)/60:.2f} minutes.")
    aggregate_deadline_results(git_commit)


def aggregate_deadline_results(git_commit):
    print("\n--- Aggregating Deadline Results ---")
    # Process sweep runs
    sweep_summary = os.path.join(AGG_DIR, "deadline_sweep_summary.csv")
    sweep_fieldnames = [
        "git_commit", "workload", "tau_ms", "arrival_rate", "variant",
        "deadline_satisfaction_med", "deadline_satisfaction_ci_low", "deadline_satisfaction_ci_high",
        "avg_tardiness_med", "avg_tardiness_ci_low", "avg_tardiness_ci_high",
        "throughput_med", "throughput_ci_low", "throughput_ci_high",
        "solver_ms_med", "solver_ms_ci_low", "solver_ms_ci_high"
    ]

    sweep_data = defaultdict(lambda: defaultdict(list))
    for seed in REPORTING_SEEDS:
        for wl in ["uniform", "zoned"]:
            for tau in [0.012, 0.020, 0.050]:
                for lam in [0.2, 0.5, 0.8, 1.2, 1.6, 2.0]:
                    for var in ["V0", "V1", "V2"]:
                        rid = f"dl_swp_{var}_{wl}_tau{int(tau*1000)}ms_lam{int(lam*10)}_s{seed}"
                        f_csv = os.path.join(RAW_DIR, f"run_{rid}.csv")
                        if not os.path.isfile(f_csv):
                            continue
                        with open(f_csv) as rf:
                            row = next(csv.DictReader(rf))
                            key = (wl, int(tau * 1000), lam, var)
                            sweep_data[key]["ds"].append(float(row.get("deadline_satisfaction_rate", 0.0)))
                            sweep_data[key]["tard"].append(float(row.get("avg_tardiness", 0.0)))
                            sweep_data[key]["tp"].append(float(row.get("throughput", 0.0)))
                            sweep_data[key]["solv"].append(float(row.get("solver_runtime_ms", 0.0)))

    sweep_rows = []
    for key, metrics in sweep_data.items():
        wl, tau_ms, lam, var = key
        ds_m, ds_l, ds_h = bootstrap_ci(metrics["ds"])
        td_m, td_l, td_h = bootstrap_ci(metrics["tard"])
        tp_m, tp_l, tp_h = bootstrap_ci(metrics["tp"])
        sv_m, sv_l, sv_h = bootstrap_ci(metrics["solv"])
        sweep_rows.append({
            "git_commit": git_commit,
            "workload": wl,
            "tau_ms": tau_ms,
            "arrival_rate": lam,
            "variant": var,
            "deadline_satisfaction_med": round(ds_m, 4),
            "deadline_satisfaction_ci_low": round(ds_l, 4),
            "deadline_satisfaction_ci_high": round(ds_h, 4),
            "avg_tardiness_med": round(td_m, 2),
            "avg_tardiness_ci_low": round(td_l, 2),
            "avg_tardiness_ci_high": round(td_h, 2),
            "throughput_med": round(tp_m, 4),
            "throughput_ci_low": round(tp_l, 4),
            "throughput_ci_high": round(tp_h, 4),
            "solver_ms_med": round(sv_m, 2),
            "solver_ms_ci_low": round(sv_l, 2),
            "solver_ms_ci_high": round(sv_h, 2),
        })

    with open(sweep_summary, "w", newline="") as wf:
        writer = csv.DictWriter(wf, fieldnames=sweep_fieldnames)
        writer.writeheader()
        writer.writerows(sweep_rows)

    # Process policy comparison runs
    pol_summary = os.path.join(AGG_DIR, "deadline_policy_summary.csv")
    pol_fieldnames = [
        "git_commit", "policy", "arrival_rate",
        "deadline_satisfaction_med", "deadline_satisfaction_ci_low", "deadline_satisfaction_ci_high",
        "avg_tardiness_med", "avg_tardiness_ci_low", "avg_tardiness_ci_high",
        "throughput_med", "throughput_ci_low", "throughput_ci_high"
    ]
    pol_data = defaultdict(lambda: defaultdict(list))
    for seed in REPORTING_SEEDS:
        for pol in ["FIFO", "EDF", "DEADLINE_AWARE"]:
            for lam in [0.5, 1.2, 2.0]:
                rid = f"dl_pol_{pol}_lam{int(lam*10)}_s{seed}"
                f_csv = os.path.join(RAW_DIR, f"run_{rid}.csv")
                if not os.path.isfile(f_csv):
                    continue
                with open(f_csv) as rf:
                    row = next(csv.DictReader(rf))
                    key = (pol, lam)
                    pol_data[key]["ds"].append(float(row.get("deadline_satisfaction_rate", 0.0)))
                    pol_data[key]["tard"].append(float(row.get("avg_tardiness", 0.0)))
                    pol_data[key]["tp"].append(float(row.get("throughput", 0.0)))

    pol_rows = []
    for key, metrics in pol_data.items():
        pol, lam = key
        ds_m, ds_l, ds_h = bootstrap_ci(metrics["ds"])
        td_m, td_l, td_h = bootstrap_ci(metrics["tard"])
        tp_m, tp_l, tp_h = bootstrap_ci(metrics["tp"])
        pol_rows.append({
            "git_commit": git_commit,
            "policy": pol,
            "arrival_rate": lam,
            "deadline_satisfaction_med": round(ds_m, 4),
            "deadline_satisfaction_ci_low": round(ds_l, 4),
            "deadline_satisfaction_ci_high": round(ds_h, 4),
            "avg_tardiness_med": round(td_m, 2),
            "avg_tardiness_ci_low": round(td_l, 2),
            "avg_tardiness_ci_high": round(td_h, 2),
            "throughput_med": round(tp_m, 4),
            "throughput_ci_low": round(tp_l, 4),
            "throughput_ci_high": round(tp_h, 4),
        })

    with open(pol_summary, "w", newline="") as wf:
        writer = csv.DictWriter(wf, fieldnames=pol_fieldnames)
        writer.writeheader()
        writer.writerows(pol_rows)

    print("Deadline aggregation complete.")


if __name__ == "__main__":
    main()
