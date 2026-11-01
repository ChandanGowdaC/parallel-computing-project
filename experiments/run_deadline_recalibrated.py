#!/usr/bin/env python3
"""
run_deadline_recalibrated.py — Deadline Recalibration Campaign (Step B).

Matrix:
- Agents: N = 400 (maps/tiled/kiva_4x2.map)
- Workloads: Uniform and Zoned (cross_zone_prob = 0.05)
- Variants:
    - V0 (centralized sequential RHCR, p=1)
    - V1 (GD-RHCR 1 thread, V*=1)
    - V2 (GD-RHCR 4 threads, V*=1)
- Policy: EDF
- Deadline formula: deadline = release + k * shortest_path_dist + c
  Calibrated parameters: k = 3.0, c = 100
- Arrival rate lambda (4 levels: under, near, over, heavily over capacity):
  lambda in [0.2, 0.5, 1.0, 2.0]
- Planning tau (2 levels per workload):
  tau_1 = 0.020 s (tight budget: 100 ms; V0 overruns, V2 fits)
  tau_2 = 0.060 s (relaxed control budget: 300 ms)
- Reporting seeds (5 seeds): [42, 100, 2026, 3141, 5926]
Total runs = 2 workloads * 2 taus * 4 lambdas * 3 variants * 5 seeds = 240 runs.
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
DEADLINE_K = 3.0
DEADLINE_C = 100


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
            return True, "Resumed", False

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
        "--deadline_factor", str(DEADLINE_K),
        "--deadline_slack_c", str(DEADLINE_C),
        "--task_arrival_rate", str(item["arrival_rate"]),
        "--scheduling_policy", "EDF",
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

    # Check for congestion abort in log
    aborted = False
    if os.path.isfile(log_file):
        with open(log_file) as lf:
            log_content = lf.read()
            if "congested" in log_content.lower() or "abort" in log_content.lower():
                aborted = True

    if proc.returncode != 0 and not aborted:
        return False, f"Exit code {proc.returncode}", aborted

    paths_src = os.path.join(RAW_DIR, "paths.txt")
    if os.path.isfile(paths_src):
        os.makedirs(out_dir, exist_ok=True)
        shutil.move(paths_src, paths_file)

    if os.path.isfile(paths_file):
        ok, msg = verify_paths(paths_file)
        if not ok:
            return False, f"Collision: {msg}", aborted

    return True, "Success", aborted


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(AGG_DIR, exist_ok=True)

    git_commit = get_git_commit()
    print(f"[RECALIBRATED CAMPAIGN] Git commit: {git_commit}")

    # Build matrix: interleaved execution
    matrix = []
    lambdas = [0.2, 0.5, 1.0, 2.0]
    taus = [0.020, 0.060]
    workloads = [("uniform", False), ("zoned", True)]
    variants = ["V0", "V1", "V2"]

    for seed in REPORTING_SEEDS:
        for wl_name, is_zoned in workloads:
            for tau in taus:
                for lam in lambdas:
                    for var in variants:
                        tau_ms = int(tau * 1000)
                        lam_id = int(lam * 10)
                        rid = f"dl_recal_{var}_{wl_name}_tau{tau_ms}ms_lam{lam_id}_s{seed}"
                        matrix.append({
                            "run_id": rid,
                            "seed": seed,
                            "workload": wl_name,
                            "zoned": is_zoned,
                            "tau": tau,
                            "tau_ms": tau_ms,
                            "arrival_rate": lam,
                            "variant": var,
                        })

    total_runs = len(matrix)
    print(f"[RECALIBRATED CAMPAIGN] Total planned runs: {total_runs}")

    abort_counts = defaultdict(int)
    start_time = time.time()

    for idx, item in enumerate(matrix, 1):
        ok, msg, aborted = run_experiment(item, git_commit)
        if aborted:
            abort_counts[(item["variant"], item["workload"], item["tau_ms"])] += 1
        status = "ABORT" if aborted else ("OK" if ok else "FAIL")
        if idx % 10 == 0 or idx == total_runs or not ok:
            elapsed = time.time() - start_time
            rate = idx / elapsed if elapsed > 0 else 0
            eta = (total_runs - idx) / rate if rate > 0 else 0
            print(f"[{idx}/{total_runs}] {item['run_id']} -> {status} ({msg}) | Elapsed: {elapsed:.1f}s, ETA: {eta:.1f}s")

    print("\n[RECALIBRATED CAMPAIGN] Abort counts summary:")
    for k, v in sorted(abort_counts.items()):
        print(f"  {k}: {v} aborted runs")

    # Aggregation
    summary_file = os.path.join(AGG_DIR, "deadline_recalibrated_summary.csv")
    fieldnames = [
        "git_commit", "workload", "tau_ms", "arrival_rate", "variant",
        "deadline_satisfaction_med", "deadline_satisfaction_ci_low", "deadline_satisfaction_ci_high",
        "avg_tardiness_med", "avg_tardiness_ci_low", "avg_tardiness_ci_high",
        "throughput_med", "throughput_ci_low", "throughput_ci_high",
        "solver_ms_med", "solver_ms_ci_low", "solver_ms_ci_high",
        "completed_tasks_med", "aborted_runs_count"
    ]

    grouped_data = defaultdict(lambda: defaultdict(list))
    for item in matrix:
        rid = item["run_id"]
        f_csv = os.path.join(RAW_DIR, f"run_{rid}.csv")
        if not os.path.isfile(f_csv):
            continue
        key = (item["workload"], item["tau_ms"], item["arrival_rate"], item["variant"])
        with open(f_csv) as rf:
            row = next(csv.DictReader(rf))
            grouped_data[key]["ds"].append(float(row.get("deadline_satisfaction_rate", 0.0)))
            grouped_data[key]["tard"].append(float(row.get("avg_tardiness", 0.0)))
            grouped_data[key]["tp"].append(float(row.get("throughput", 0.0)))
            grouped_data[key]["solv"].append(float(row.get("solver_runtime_ms", 0.0)))
            grouped_data[key]["comp"].append(float(row.get("num_tasks_completed", 0.0)))

    summary_rows = []
    for key, metrics in sorted(grouped_data.items()):
        wl, tau_ms, lam, var = key
        ds_m, ds_l, ds_h = bootstrap_ci(metrics["ds"])
        td_m, td_l, td_h = bootstrap_ci(metrics["tard"])
        tp_m, tp_l, tp_h = bootstrap_ci(metrics["tp"])
        sv_m, sv_l, sv_h = bootstrap_ci(metrics["solv"])
        comp_m, _, _ = bootstrap_ci(metrics["comp"])
        n_aborted = abort_counts.get((var, wl, tau_ms), 0)

        summary_rows.append({
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
            "completed_tasks_med": round(comp_m, 1),
            "aborted_runs_count": n_aborted
        })

    with open(summary_file, "w", newline="") as wf:
        writer = csv.DictWriter(wf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\n[RECALIBRATED CAMPAIGN] Aggregation complete: {summary_file}")


if __name__ == "__main__":
    main()
