#!/usr/bin/env python3
"""
run_reporting_scaling_campaign.py — Step 5 Constant-Density Scaling Benchmark on Reporting Seeds.

Execution Matrix (Amended per Step C):
- Disjoint Reporting Seeds (5 seeds): [42, 100, 2026, 3141, 5926]
- Agent counts: N in {100, 400, 800} on constant-density tiled maps:
    N=100 -> maps/tiled/kiva_2x1.map (66x46)
    N=400 -> maps/tiled/kiva_4x2.map (132x92)
    N=800 -> maps/tiled/kiva_4x4.map (132x184)
- Workloads: Uniform vs Zoned (cross_zone_prob = 0.05)
- Configurations per (N, Workload):
    - V0: Vanilla RHCR sequential (p=1)
    - For V* (selected V*=2):
        - V1: GD-RHCR (p=1)
        - V2: GD-RHCR at p in {2, 4, 5, 8, 11} (p=5 represents physical P-core capacity)
    - For V = 8 (conservative baseline):
        - V1: GD-RHCR (p=1)
        - V2: GD-RHCR (p=8)
  Total configs per (N, workload) = 1 + 6 + 2 = 9 configs.
- Total executions = 5 seeds * 3 agent counts * 2 workloads * 9 configs = 270 runs.
- Simulation horizon: T_sim = 250 (50 replanning cycles, h=5, w=10).
- Interleaved seed-by-seed execution order with cooldown pauses.
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
from scripts.verify_collision_freedom import verify_paths

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


def log_system_state():
    try:
        batt = subprocess.run(["pmset", "-g", "batt"], stdout=subprocess.PIPE, text=True).stdout.strip()
        therm = subprocess.run(["pmset", "-g", "therm"], stdout=subprocess.PIPE, text=True).stdout.strip()
        print(f"[System State] {batt} | {therm}")
    except Exception:
        pass


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

    # Check resume
    if os.path.isfile(csv_file) and os.path.isfile(paths_file):
        ok, msg = verify_paths(paths_file)
        if ok:
            return True, "Resumed"

    cmd = [
        BINARY,
        "--scenario", "KIVA",
        "--solver", "PBS",
        "--map", item["map_file"],
        "--agents", str(item["agents"]),
        "--simulation_timesteps", str(SIM_TIMESTEPS),
        "--planning_window", str(PLANNING_WINDOW),
        "--planning_horizon", str(PLANNING_HORIZON),
        "--seed", str(item["seed"]),
        "--run_id", run_id,
        "--output_dir", RAW_DIR,
        "--output", out_dir,
        "--git_commit", git_commit,
    ]

    if item["zoned"]:
        cmd.extend(["--task_zoning", "on", "--cross_zone_prob", "0.05"])
    else:
        cmd.extend(["--task_zoning", "off"])

    if item["parallel"]:
        cmd.extend([
            "--parallel", "on",
            "--vis_radius", str(item["vis_radius"]),
            "--threads", str(item["threads"])
        ])
    else:
        cmd.extend([
            "--parallel", "off",
            "--vis_radius", "0",
            "--threads", "1"
        ])

    with open(log_file, "w") as lf:
        proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)

    if proc.returncode != 0:
        return False, f"Exit code {proc.returncode}"

    # Move paths file to dedicated dir if needed
    paths_src = os.path.join(RAW_DIR, "paths.txt")
    if os.path.isfile(paths_src):
        os.makedirs(out_dir, exist_ok=True)
        shutil.move(paths_src, paths_file)

    # Verify collision freedom
    ok, msg = verify_paths(paths_file)
    if not ok:
        return False, f"Collision: {msg}"

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
    print("      STEP 5 CONSTANT-DENSITY SCALING BENCHMARK (270 RUNS)")
    print(f"  Git Commit: {git_commit}")
    print(f"  Seeds ({len(REPORTING_SEEDS)}): {REPORTING_SEEDS}")
    log_system_state()
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

                # 2. V* configs (V*=1): p in {1, 2, 4, 5, 8, 11}
                for p in [1, 2, 4, 5, 8, 11]:
                    v_type = "V1" if p == 1 else "V2"
                    run_id = f"scale_kiva{agents}_{v_type}_V1_{workload}_t{p}_s{seed}"
                    work_items.append({
                        "run_id": run_id,
                        "seed": seed,
                        "agents": agents,
                        "map_file": map_file,
                        "workload": workload,
                        "zoned": is_zoned,
                        "type": v_type,
                        "vis_radius": 1,
                        "threads": p,
                        "parallel": True,
                    })

                # 3. V=8 configs: p in {1, 8}
                for p in [1, 8]:
                    v_type = "V1" if p == 1 else "V2"
                    run_id = f"scale_kiva{agents}_{v_type}_V8_{workload}_t{p}_s{seed}"
                    work_items.append({
                        "run_id": run_id,
                        "seed": seed,
                        "agents": agents,
                        "map_file": map_file,
                        "workload": workload,
                        "zoned": is_zoned,
                        "type": v_type,
                        "vis_radius": 8,
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
            sys.exit(1)

        # Cooldown pause on heavy runs
        if item["agents"] == 800 and item["threads"] >= 5:
            time.sleep(1.0)

    print(f"\nExecution finished: {success_count}/{total} succeeded in {(time.time() - t_start)/60:.2f} minutes.")
    log_system_state()

    # Aggregate results
    aggregate_results(git_commit)


def aggregate_results(git_commit):
    print("\n--- Aggregating Results ---")
    data = defaultdict(dict)

    # Configs to aggregate
    configs = []
    for a in [100, 400, 800]:
        for wl in ["uniform", "zoned"]:
            configs.append((a, wl, 0, 1, "V0"))
            for p in [1, 2, 4, 5, 8, 11]:
                configs.append((a, wl, 1, p, "V1" if p == 1 else "V2"))
            for p in [1, 8]:
                configs.append((a, wl, 8, p, "V1" if p == 1 else "V2"))

    for a, wl, v, p, v_type in configs:
        for s in REPORTING_SEEDS:
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
                tot_ms = float(row.get("total_runtime_ms", 0.0))
                tp = float(row.get("throughput", 0.0))

            fb_pct = 0.0
            grps = 0.0
            max_frac = 0.0
            plan_ms = solv_ms
            if os.path.isfile(f_ep):
                with open(f_ep) as ef:
                    ep_rows = list(csv.DictReader(ef))
                    if ep_rows:
                        fb_cnt = sum(1 for e in ep_rows if int(e.get("global_fallback_invoked", 0)) > 0)
                        fb_pct = fb_cnt / len(ep_rows) * 100.0
                        grps = np.mean([float(e.get("groups_before", e.get("num_groups", 1))) for e in ep_rows])
                        max_frac = np.mean([float(e.get("largest_group_frac", 0.0)) for e in ep_rows])
                        plan_ms = sum(
                            float(e["t_partition_ms"]) + float(e["t_dispatch_ms"]) +
                            float(e["merge_time_ms"]) + float(e["solve_time_ms"]) +
                            float(e["t_serial_rest_ms"])
                            for e in ep_rows
                        )

            key = (a, wl, v, p)
            if key not in data:
                data[key] = {}
            data[key][s] = {
                "solver_ms": solv_ms,
                "plan_ms": plan_ms,
                "tot_ms": tot_ms,
                "tp": tp,
                "fb_pct": fb_pct,
                "grps": grps,
                "max_frac": max_frac,
            }

    summary_file = os.path.join(AGG_DIR, "reporting_scaling_summary.csv")
    fieldnames = [
        "git_commit", "agents", "workload", "V", "p", "variant",
        "solver_ms_med", "solver_ms_ci_low", "solver_ms_ci_high",
        "plan_ms_med", "plan_ms_ci_low", "plan_ms_ci_high",
        "total_wall_ms_med", "total_wall_ms_ci_low", "total_wall_ms_ci_high",
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
            v0_data = data.get((a, wl, 0, 1), {})
            v0_times = {s: v0_data[s]["solver_ms"] for s in v0_data}
            v0_tps = {s: v0_data[s]["tp"] for s in v0_data}

            for V in [0, 1, 8]:
                p_list = [1] if V == 0 else ([1, 2, 4, 5, 8, 11] if V == 1 else [1, 8])
                v1_data = data.get((a, wl, V, 1), {})
                v1_times = {s: v1_data[s]["solver_ms"] for s in v1_data}

                for p in p_list:
                    k = (a, wl, V, p)
                    cur_data = data.get(k, {})
                    if not cur_data:
                        continue

                    variant = "V0" if V == 0 else ("V1" if p == 1 else "V2")
                    solv_list = [cur_data[s]["solver_ms"] for s in cur_data]
                    plan_list = [cur_data[s]["plan_ms"] for s in cur_data]
                    tot_list  = [cur_data[s]["tot_ms"] for s in cur_data]
                    fb_list   = [cur_data[s]["fb_pct"] for s in cur_data]
                    grp_list  = [cur_data[s]["grps"] for s in cur_data]
                    frac_list = [cur_data[s]["max_frac"] for s in cur_data]

                    s_tot_list = [v0_times[s] / cur_data[s]["solver_ms"] for s in cur_data if s in v0_times]
                    s_alg_list = [v0_times[s] / v1_times[s] for s in cur_data if s in v0_times and s in v1_times]
                    s_th_list  = [v1_times[s] / cur_data[s]["solver_ms"] for s in cur_data if s in v1_times]
                    tpr_list   = [cur_data[s]["tp"] / v0_tps[s] for s in cur_data if s in v0_tps]

                    s_m, s_l, s_h = bootstrap_ci(solv_list)
                    pl_m, pl_l, pl_h = bootstrap_ci(plan_list)
                    t_m, t_l, t_h = bootstrap_ci(tot_list)
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
                        "plan_ms_med": round(pl_m, 2),
                        "plan_ms_ci_low": round(pl_l, 2),
                        "plan_ms_ci_high": round(pl_h, 2),
                        "total_wall_ms_med": round(t_m, 2),
                        "total_wall_ms_ci_low": round(t_l, 2),
                        "total_wall_ms_ci_high": round(t_h, 2),
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
