#!/usr/bin/env python3
"""
run_reporting_scaling_campaign.py — Step 5 Constant-Density Scaling Benchmark on Reporting Seeds.

Execution Matrix:
- Disjoint Reporting Seeds (5 seeds): [42, 100, 2026, 3141, 5926]
- Agent counts: N in {100, 400, 800} on constant-density tiled maps:
    N=100 -> maps/tiled/kiva_2x1.map (66x46)
    N=400 -> maps/tiled/kiva_4x2.map (132x92)
    N=800 -> maps/tiled/kiva_4x4.map (132x184)
- Workloads: Uniform vs Zoned (cross_zone_prob = 0.05)
- Configurations per (N, Workload):
    - V0: Vanilla RHCR sequential (p=1)
    - For V* = 2:
        - V1: GD-RHCR (p=1)
        - V2: GD-RHCR (p=2, 4, 8, 11)
    - For V = 8 (conservative baseline):
        - V1: GD-RHCR (p=1)
        - V2: GD-RHCR (p=2, 4, 8, 11)
  Total configs per (N, workload) = 1 + 5 + 5 = 11 configs.
- Total executions = 5 seeds * 3 agent counts * 2 workloads * 11 configs = 330 runs.
- Simulation horizon: T_sim = 250 (50 replanning cycles, h=5, w=10).
- Interleaved seed-by-seed execution order.
- Full-horizon collision verification for every run.
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
BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")

REPORTING_SEEDS = [42, 100, 2026, 3141, 5926]
AGENT_MAPS = {
    100: "maps/tiled/kiva_2x1.map",
    400: "maps/tiled/kiva_4x2.map",
    800: "maps/tiled/kiva_4x4.map",
}
VIS_RADII = [2, 8]  # V*=2 and conservative V=8
THREAD_COUNTS = [1, 2, 4, 8, 11]
SIM_TIMESTEPS = 250
PLANNING_WINDOW = 10
PLANNING_HORIZON = 5


def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def check_git_clean():
    try:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        # Check only tracked file modifications (ignore untracked results/raw)
        lines = [l for l in res.stdout.splitlines() if not l.startswith("??")]
        if lines:
            print("ERROR: Working directory has uncommitted tracked changes:")
            for l in lines:
                print("  ", l)
            return False
        return True
    except Exception as e:
        print(f"Git check failed: {e}")
        return False


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
    ep_file = os.path.join(RAW_DIR, f"episodes_{run_id}.csv")
    paths_file = os.path.join(RAW_DIR, f"paths_{run_id}.txt")
    log_file = os.path.join(LOG_DIR, f"{run_id}.log")

    # Check resume
    if os.path.isfile(csv_file) and os.path.isfile(paths_file):
        ok, msg = verify_single_run(paths_file)
        if ok:
            return True, "Resumed"

    cmd = [
        BINARY,
        "--map", item["map_file"],
        "--agents", str(item["agents"]),
        "--simulation_timesteps", str(SIM_TIMESTEPS),
        "--planning_window", str(PLANNING_WINDOW),
        "--planning_horizon", str(PLANNING_HORIZON),
        "--seed", str(item["seed"]),
        "--output_prefix", run_id,
        "--raw_dir", RAW_DIR,
        "--scenario", "KIVA",
    ]

    if item["zoned"]:
        cmd.extend(["--task_zoning", "on", "--cross_zone_prob", "0.05"])
    else:
        cmd.extend(["--task_zoning", "off"])

    if item["parallel"]:
        cmd.extend([
            "--parallel", "true",
            "--vis_radius", str(item["vis_radius"]),
            "--threads", str(item["threads"])
        ])
    else:
        cmd.extend([
            "--parallel", "false",
            "--vis_radius", "0",
            "--threads", "1"
        ])

    with open(log_file, "w") as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)

    if proc.returncode != 0:
        return False, f"Exit code {proc.returncode}"

    # Verify collision freedom
    ok, msg = verify_single_run(paths_file)
    if not ok:
        return False, f"Collision: {msg}"

    # Inject git commit into CSV
    if os.path.isfile(csv_file):
        rows = []
        with open(csv_file, "r") as rf:
            reader = csv.DictReader(rf)
            fieldnames = list(reader.fieldnames)
            if "git_commit" not in fieldnames:
                fieldnames.append("git_commit")
            for row in reader:
                row["git_commit"] = git_commit
                rows.append(row)
        with open(csv_file, "w", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return True, "Success"


def main():
    if not check_git_clean():
        print("Aborting: dirty git working directory.")
        sys.exit(1)

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(AGG_DIR, exist_ok=True)

    git_commit = get_git_commit()
    print("=" * 80)
    print("      STEP 5 CONSTANT-DENSITY SCALING BENCHMARK (330 RUNS)")
    print(f"  Git Commit: {git_commit}")
    print(f"  Seeds ({len(REPORTING_SEEDS)}): {REPORTING_SEEDS}")
    print("=" * 80)

    # Build work items interleaved seed-by-seed
    work_items = []
    for seed in REPORTING_SEEDS:
        for agents in [100, 400, 800]:
            map_file = AGENT_MAPS[agents]
            for workload in ["uniform", "zoned"]:
                is_zoned = (workload == "zoned")
                
                # 1. V0
                run_id_v0 = f"scale_kiva{agents}_v0_{workload}_s{seed}"
                work_items.append({
                    "run_id": run_id_v0,
                    "seed": seed,
                    "agents": agents,
                    "map_file": map_file,
                    "workload": workload,
                    "zoned": is_zoned,
                    "type": "V0",
                    "vis_radius": 0,
                    "threads": 1,
                    "parallel": False,
                })

                # 2. GD-RHCR configs for V in {2, 8}
                for V in VIS_RADII:
                    for p in THREAD_COUNTS:
                        v_type = "V1" if p == 1 else "V2"
                        run_id = f"scale_kiva{agents}_{v_type}_V{V}_{workload}_t{p}_s{seed}"
                        work_items.append({
                            "run_id": run_id,
                            "seed": seed,
                            "agents": agents,
                            "map_file": map_file,
                            "workload": workload,
                            "zoned": is_zoned,
                            "type": v_type,
                            "vis_radius": V,
                            "threads": p,
                            "parallel": True,
                        })

    print(f"Total scheduled runs: {len(work_items)}")
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

        # Cooldown pause on heavy runs
        if item["agents"] == 800 and item["threads"] >= 8:
            time.sleep(0.5)

    print(f"\nExecution finished: {success_count}/{total} succeeded in {(time.time() - t_start)/60:.2f} minutes.")

    # Aggregate results
    aggregate_results(git_commit)


def aggregate_results(git_commit):
    print("\n--- Aggregating Results ---")
    # Read all run CSVs
    data = defaultdict(dict)
    for item in [
        {"agents": a, "workload": wl, "seed": s, "V": v, "p": p, "v_type": ("V0" if v == 0 else ("V1" if p == 1 else "V2"))}
        for s in REPORTING_SEEDS
        for a in [100, 400, 800]
        for wl in ["uniform", "zoned"]
        for v in [0, 2, 8]
        for p in ([1] if v == 0 else THREAD_COUNTS)
    ]:
        a = item["agents"]
        wl = item["workload"]
        s = item["seed"]
        v = item["V"]
        p = item["p"]
        v_type = item["v_type"]

        if v_type == "V0":
            rid = f"scale_kiva{a}_v0_{wl}_s{s}"
        else:
            rid = f"scale_kiva{a}_{v_type}_V{v}_{wl}_t{p}_s{s}"

        f_csv = os.path.join(RAW_DIR, f"run_{rid}.csv")
        f_ep = os.path.join(RAW_DIR, f"episodes_{rid}.csv")
        if not os.path.isfile(f_csv):
            continue

        with open(f_csv) as rf:
            row = next(csv.DictReader(rf))
            solv_ms = float(row.get("solver_runtime_ms", 0.0))
            tp = float(row.get("throughput", 0.0))
            cost = float(row.get("service_cost", row.get("avg_path_cost", 0.0)))

        fb_pct = 0.0
        grps = 0.0
        max_frac = 0.0
        if os.path.isfile(f_ep):
            with open(f_ep) as ef:
                ep_rows = list(csv.DictReader(ef))
                if ep_rows:
                    fb_cnt = sum(1 for e in ep_rows if int(e.get("global_fallback_invoked", 0)) > 0)
                    fb_pct = fb_cnt / len(ep_rows) * 100.0
                    grps = np.mean([float(e.get("groups_before", e.get("num_groups", 1))) for e in ep_rows])
                    max_frac = np.mean([float(e.get("largest_group_frac", 0.0)) for e in ep_rows])

        key = (a, wl, v, p)
        if key not in data:
            data[key] = {}
        data[key][s] = {
            "solver_ms": solv_ms,
            "tp": tp,
            "cost": cost,
            "fb_pct": fb_pct,
            "grps": grps,
            "max_frac": max_frac,
        }

    summary_file = os.path.join(AGG_DIR, "reporting_scaling_summary.csv")
    fieldnames = [
        "git_commit", "agents", "workload", "V", "p", "variant",
        "solver_ms_med", "solver_ms_ci_low", "solver_ms_ci_high",
        "S_total_med", "S_total_ci_low", "S_total_ci_high",
        "S_alg_med", "S_alg_ci_low", "S_alg_ci_high",
        "S_thread_med", "S_thread_ci_low", "S_thread_ci_high",
        "groups_med", "largest_group_frac_med",
        "fallback_rate_pct_med", "fallback_rate_pct_ci_low", "fallback_rate_pct_ci_high",
        "throughput_ratio_vs_v0_med", "throughput_ratio_ci_low", "throughput_ratio_ci_high"
    ]

    out_rows = []
    for a in [100, 400, 800]:
        for wl in ["uniform", "zoned"]:
            # Baseline V0
            v0_data = data.get((a, wl, 0, 1), {})
            v0_times = {s: v0_data[s]["solver_ms"] for s in v0_data}
            v0_tps = {s: v0_data[s]["tp"] for s in v0_data}

            for V in [0, 2, 8]:
                p_list = [1] if V == 0 else THREAD_COUNTS
                # V1 for this V
                v1_data = data.get((a, wl, V, 1), {})
                v1_times = {s: v1_data[s]["solver_ms"] for s in v1_data}

                for p in p_list:
                    k = (a, wl, V, p)
                    cur_data = data.get(k, {})
                    if not cur_data:
                        continue

                    variant = "V0" if V == 0 else ("V1" if p == 1 else "V2")
                    solv_list = [cur_data[s]["solver_ms"] for s in cur_data]
                    fb_list = [cur_data[s]["fb_pct"] for s in cur_data]
                    grp_list = [cur_data[s]["grps"] for s in cur_data]
                    frac_list = [cur_data[s]["max_frac"] for s in cur_data]

                    s_tot_list = [v0_times[s] / cur_data[s]["solver_ms"] for s in cur_data if s in v0_times]
                    s_alg_list = [v0_times[s] / v1_times[s] for s in cur_data if s in v0_times and s in v1_times]
                    s_th_list = [v1_times[s] / cur_data[s]["solver_ms"] for s in cur_data if s in v1_times]
                    tpr_list = [cur_data[s]["tp"] / v0_tps[s] for s in cur_data if s in v0_tps]

                    s_m, s_l, s_h = bootstrap_ci(solv_list)
                    tot_m, tot_l, tot_h = bootstrap_ci(s_tot_list) if s_tot_list else (1.0, 1.0, 1.0)
                    alg_m, alg_l, alg_h = bootstrap_ci(s_alg_list) if s_alg_list else (1.0, 1.0, 1.0)
                    th_m, th_l, th_h = bootstrap_ci(s_th_list) if s_th_list else (1.0, 1.0, 1.0)
                    fb_m, fb_l, fb_h = bootstrap_ci(fb_list)
                    tp_m, tp_l, tp_h = bootstrap_ci(tpr_list) if tpr_list else (1.0, 1.0, 1.0)

                    out_rows.append({
                        "git_commit": git_commit,
                        "agents": a,
                        "workload": wl,
                        "V": V,
                        "p": p,
                        "variant": variant,
                        "solver_ms_med": round(s_m, 2),
                        "solver_ms_ci_low": round(s_l, 2),
                        "solver_ms_ci_high": round(s_h, 2),
                        "S_total_med": round(tot_m, 3),
                        "S_total_ci_low": round(tot_l, 3),
                        "S_total_ci_high": round(tot_h, 3),
                        "S_alg_med": round(alg_m, 3),
                        "S_alg_ci_low": round(alg_l, 3),
                        "S_alg_ci_high": round(alg_h, 3),
                        "S_thread_med": round(th_m, 3),
                        "S_thread_ci_low": round(th_l, 3),
                        "S_thread_ci_high": round(th_h, 3),
                        "groups_med": round(float(np.median(grp_list)), 1),
                        "largest_group_frac_med": round(float(np.median(frac_list)), 3),
                        "fallback_rate_pct_med": round(fb_m, 2),
                        "fallback_rate_pct_ci_low": round(fb_l, 2),
                        "fallback_rate_pct_ci_high": round(fb_h, 2),
                        "throughput_ratio_vs_v0_med": round(tp_m, 4),
                        "throughput_ratio_ci_low": round(tp_l, 4),
                        "throughput_ratio_ci_high": round(tp_h, 4),
                    })

    with open(summary_file, "w", newline="") as wf:
        writer = csv.DictWriter(wf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Aggregation complete. Output saved to: {summary_file}")


if __name__ == "__main__":
    main()
