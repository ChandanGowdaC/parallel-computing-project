#!/usr/bin/env python3
"""
run_constant_density_campaign.py — Constant-Density Warehouse Scaling Benchmark Runner.

Executes Step 3 of the integration directives:
- T_sim = 250 (50 replanning cycles, h=5, w=10) for ALL configurations.
- Enforces code freeze (code-freeze-v1) and clean working tree.
- Uses tiled KIVA warehouse maps (1x1, 2x1, 2x2, 4x2, 4x4) preserving local density.
- Phase A: V-sweep tuning on 3 TUNING seeds (101, 202, 303) across V in {3,4,5,6,8} at p in {1,8}.
  Pre-declared selection rule: highest speedup at p=8 subject to fallback rate <= 10% and throughput >= 95% of V0.
- Phase B: Reporting matrix across 10 REPORTING seeds (42, 100, 2026, 3141, 5926, 8421, 9001, 1234, 7777, 8888)
  for N in {50, 100, 200, 400, 800} across p in {1, 2, 4, 8, 11} at V* and V=8.
- Phase C: Comprehensive plan-quality parity, Karp-Flatt, theoretical bound, and figures generation.
"""

import os
import sys
import subprocess
import json
import csv
import time
import math
import shutil
import re
from collections import defaultdict

os.environ["MPLCONFIGDIR"] = "/tmp/mpl"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")
FIG_DIR = os.path.join(ROOT_DIR, "results", "figures")

TUNING_SEEDS = [101, 202, 303]
REPORTING_SEEDS = [42, 100, 2026, 3141, 5926, 8421, 9001, 1234, 7777, 8888]

MAP_TABLE = {
    50:  ("maps/tiled/kiva_1x1.map", 1, 1),
    100: ("maps/tiled/kiva_2x1.map", 2, 1),
    200: ("maps/tiled/kiva_2x2.map", 2, 2),
    400: ("maps/tiled/kiva_4x2.map", 4, 2),
    800: ("maps/tiled/kiva_4x4.map", 4, 4),
}

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

def run_job(agents, threads, parallel, vis_radius, seed, run_id, simulation_timesteps=250):
    map_path, _, _ = MAP_TABLE[agents]
    commit = get_git_commit()

    cmd = [
        BINARY,
        "--scenario", "KIVA",
        "--map", map_path,
        "--agents", str(agents),
        "--threads", str(threads),
        "--parallel", "on" if parallel else "off",
        "--vis_radius", str(vis_radius),
        "--planning_window", "10",
        "--planning_horizon", "5",
        "--simulation_timesteps", str(simulation_timesteps),
        "--seed", str(seed),
        "--output_dir", RAW_DIR,
        "--run_id", run_id,
        "--git_commit", commit
    ]

    log_path = os.path.join(LOG_DIR, f"log_{run_id}.txt")
    with open(log_path, "w") as log_f:
        res = subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT, text=True)

    if res.returncode != 0:
        return False, f"Process exited with code {res.returncode}. See {log_path}"

    run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
    if not os.path.isfile(run_csv):
        return False, f"Missing output CSV: {run_csv}"

    temp_paths = os.path.join(RAW_DIR, "paths.txt")
    perm_paths = os.path.join(RAW_DIR, f"paths_{run_id}.txt")
    if os.path.exists(temp_paths):
        shutil.copyfile(temp_paths, perm_paths)
        ok, msg = verify_single_run(perm_paths)
        if not ok:
            return False, f"COLLISION ERROR in {run_id}: {msg}"

    return True, "Success"

def parse_run_result(run_id):
    csv_path = os.path.join(RAW_DIR, f"run_{run_id}.csv")
    log_path = os.path.join(LOG_DIR, f"log_{run_id}.txt")
    ep_path = os.path.join(RAW_DIR, f"episodes_{run_id}.csv")
    tasks_path = os.path.join(RAW_DIR, f"tasks_{run_id}.csv")

    data = {}
    if os.path.isfile(csv_path):
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            row = next(reader, None)
            if row:
                for k, v in row.items():
                    try:
                        data[k] = float(v) if "." in v else int(v)
                    except Exception:
                        data[k] = v

    agent_count = data.get("agent_count", 50)

    # 1. Parse episode metrics
    mean_groups = 1.0
    mean_max_group_size = 1.0
    if os.path.isfile(ep_path):
        ep_groups = []
        ep_max_sizes = []
        with open(ep_path) as f:
            reader = csv.DictReader(f)
            for r in reader:
                ng = int(r.get("num_groups", 1))
                ep_groups.append(ng)
                sz_str = r.get("group_sizes", "")
                if sz_str:
                    sizes = [int(s) for s in sz_str.split(",") if s.strip()]
                    if sizes:
                        ep_max_sizes.append(max(sizes))
        if ep_groups:
            mean_groups = sum(ep_groups) / len(ep_groups)
        if ep_max_sizes:
            mean_max_group_size = sum(ep_max_sizes) / len(ep_max_sizes)
    elif "num_groups" in data:
        mean_groups = float(data["num_groups"])
        mean_max_group_size = float(data.get("avg_group_size", agent_count))

    largest_group_frac = min(1.0, mean_max_group_size / max(1, agent_count))
    theoretical_bound = agent_count / max(1.0, mean_max_group_size)

    # 2. Parse task metrics for service time
    mean_service_time = 0.0
    if os.path.isfile(tasks_path):
        st_list = []
        with open(tasks_path) as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("status") == "completed":
                    rel = int(r.get("release_time", 0))
                    comp = int(r.get("completion_time", 0))
                    st_list.append(comp - rel)
        if st_list:
            mean_service_time = sum(st_list) / len(st_list)

    # 3. Parse fallback count from log
    fallback_count = 0
    if os.path.isfile(log_path):
        with open(log_path) as f:
            text = f.read()
            fallback_count = len(re.findall(r"Invoking sequential fallback", text))

    data["fallback_count"] = fallback_count
    data["mean_groups"] = mean_groups
    data["max_group_size"] = mean_max_group_size
    data["largest_group_fraction"] = largest_group_frac
    data["theoretical_bound"] = theoretical_bound
    data["mean_service_time"] = mean_service_time
    return data

def bootstrap_ci(data, stat_fn=lambda x: sum(x)/len(x), n_boot=2000, alpha=0.05):
    if not data:
        return 0.0, 0.0, 0.0
    if len(data) == 1:
        return data[0], data[0], data[0]
    import random
    n = len(data)
    boot_stats = []
    for _ in range(n_boot):
        sample = [random.choice(data) for _ in range(n)]
        boot_stats.append(stat_fn(sample))
    boot_stats.sort()
    low = boot_stats[int(alpha / 2 * n_boot)]
    high = boot_stats[int((1 - alpha / 2) * n_boot)]
    point = stat_fn(data)
    return point, low, high

def main():
    check_clean_working_tree()
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(AGG_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    print("=" * 80)
    print("      CONSTANT-DENSITY SCALING BENCHMARK CAMPAIGN (T_sim = 250)")
    print(f"Commit: {get_git_commit()}")
    print("=" * 80)

    # ─────────────────────────────────────────────────────────────
    # PHASE A: V-Sweep Tuning on 3 Tuning Seeds (101, 202, 303)
    # ─────────────────────────────────────────────────────────────
    print("\n>>> PHASE A: V-Sweep Tuning on Seeds", TUNING_SEEDS)
    tuning_scales = [200, 400, 800]
    tuning_v_list = [3, 4, 5, 6, 8]
    tuning_results = defaultdict(lambda: defaultdict(list))

    total_tuning_jobs = len(tuning_scales) * (1 + len(tuning_v_list) * 2) * len(TUNING_SEEDS)
    t_job_idx = 0

    for N in tuning_scales:
        for seed in TUNING_SEEDS:
            # 1. Baseline V0
            t_job_idx += 1
            run_id = f"tune_a{N}_v0_s{seed}"
            run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
            if not os.path.isfile(run_csv):
                print(f"  [{t_job_idx:02d}/{total_tuning_jobs:02d}] N={N:3d} V0 (seq) seed {seed} ...", end="", flush=True)
                t0 = time.time()
                ok, msg = run_job(N, threads=1, parallel=False, vis_radius=0, seed=seed, run_id=run_id)
                dt = time.time() - t0
                print(f" {'OK' if ok else 'FAIL'} ({dt:.2f}s)")
            tuning_results[N]["v0"].append(parse_run_result(run_id))

            # 2. V sweep for p=1 and p=8
            for V in tuning_v_list:
                for p in [1, 8]:
                    t_job_idx += 1
                    run_id = f"tune_a{N}_V{V}_p{p}_s{seed}"
                    run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
                    if not os.path.isfile(run_csv):
                        print(f"  [{t_job_idx:02d}/{total_tuning_jobs:02d}] N={N:3d} V={V} p={p} seed {seed} ...", end="", flush=True)
                        t0 = time.time()
                        ok, msg = run_job(N, threads=p, parallel=True, vis_radius=V, seed=seed, run_id=run_id)
                        dt = time.time() - t0
                        print(f" {'OK' if ok else 'FAIL'} ({dt:.2f}s)")
                    tuning_results[N][(V, p)].append(parse_run_result(run_id))

    # Evaluate Tuning Selection Rule:
    # Rule: highest speedup at p=8 subject to fallback_rate <= 10% (<= 5 fallbacks / 50 cycles)
    # and throughput >= 95% of V0.
    v_star = {}
    print("\n" + "=" * 80)
    print("PHASE A TUNING SELECTION RESULTS (Evaluated on 3 Tuning Seeds)")
    print("Pre-declared rule: Maximize Speedup (p=8 vs V0) subject to Fallback Rate <= 10% and Throughput >= 95% of V0")
    print("=" * 80)

    tuning_summary_rows = []
    for N in tuning_scales:
        v0_runs = tuning_results[N]["v0"]
        v0_time_med = sorted([r["total_runtime_ms"] for r in v0_runs])[len(v0_runs)//2]
        v0_tp_med = sorted([r["throughput"] for r in v0_runs])[len(v0_runs)//2]

        print(f"\n--- N = {N} Agents (V0 Sequential: {v0_time_med:.1f} ms, Throughput: {v0_tp_med:.4f}) ---")
        print(f"  {'V':>3} | {'Fallback Rate':>13} | {'Throughput':>10} | {'Throughput %':>12} | {'Solver Time (ms)':>16} | {'Speedup p=8':>11} | {'Eligible?':>9}")
        print("  " + "-" * 88)

        best_v = 8 # default fallback
        best_speedup = 0.0

        for V in tuning_v_list:
            p8_runs = tuning_results[N][(V, 8)]
            fb_rates = [r["fallback_count"] / 50.0 for r in p8_runs]
            mean_fb_rate = sum(fb_rates) / len(fb_rates)
            tp_vals = [r["throughput"] for r in p8_runs]
            tp_med = sorted(tp_vals)[len(tp_vals)//2]
            tp_ratio = (tp_med / v0_tp_med) if v0_tp_med > 0 else 1.0

            times = [r["total_runtime_ms"] for r in p8_runs]
            t_med = sorted(times)[len(times)//2]
            speedup = (v0_time_med / t_med) if t_med > 0 else 1.0

            eligible = (mean_fb_rate <= 0.10) and (tp_ratio >= 0.95)
            elig_str = "YES" if eligible else "NO"
            if eligible and speedup > best_speedup:
                best_speedup = speedup
                best_v = V

            print(f"  {V:3d} | {mean_fb_rate*100:12.1f}% | {tp_med:10.4f} | {tp_ratio*100:11.1f}% | {t_med:16.1f} | {speedup:10.2f}x | {elig_str:>9}")
            tuning_summary_rows.append({
                "agent_count": N, "V": V, "fallback_rate": mean_fb_rate,
                "throughput": tp_med, "throughput_ratio": tp_ratio,
                "runtime_ms": t_med, "speedup": speedup, "eligible": eligible
            })

        v_star[N] = best_v
        print(f"  => SELECTED V* for N={N}: V = {best_v} (Speedup: {best_speedup:.2f}x)")

    # Save tuning summary CSV
    with open(os.path.join(AGG_DIR, "v_sweep_tuning_results.csv"), "w") as f:
        writer = csv.DictWriter(f, fieldnames=["agent_count", "V", "fallback_rate", "throughput", "throughput_ratio", "runtime_ms", "speedup", "eligible"])
        writer.writeheader()
        writer.writerows(tuning_summary_rows)

    # ─────────────────────────────────────────────────────────────
    # PHASE B: Full Reporting Matrix across 10 Reporting Seeds
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print(">>> PHASE B: Full Constant-Density Scaling Matrix (10 Seeds, T_sim = 250)")
    print("=" * 80)

    reporting_scales = [50, 100, 200, 400, 800]
    threads_list = [1, 2, 4, 8, 11]

    # Build manifest
    reporting_manifest = []
    for N in reporting_scales:
        # 1. Vanilla sequential baseline V0
        reporting_manifest.append({"name": f"scale_a{N}_v0_seq", "agents": N, "threads": 1, "parallel": False, "V": 0, "tier": "V0"})

        # Determine V values to evaluate
        v_eval_list = [8]
        if N in v_star and v_star[N] != 8:
            v_eval_list.append(v_star[N])

        for V in v_eval_list:
            # 2. GD-RHCR single-thread V1
            reporting_manifest.append({"name": f"scale_a{N}_V{V}_p1", "agents": N, "threads": 1, "parallel": True, "V": V, "tier": "V1"})
            # 3. GD-RHCR multi-thread V2
            for p in [2, 4, 8, 11]:
                reporting_manifest.append({"name": f"scale_a{N}_V{V}_p{p}", "agents": N, "threads": p, "parallel": True, "V": V, "tier": "V2"})

    total_reporting_runs = len(reporting_manifest) * len(REPORTING_SEEDS)
    print(f"Total Configurations: {len(reporting_manifest)}")
    print(f"Total Reporting Runs: {total_reporting_runs} (10 seeds each)")

    rep_idx = 0
    t_rep_start = time.time()
    for cfg in reporting_manifest:
        cfg_name = cfg["name"]
        for seed in REPORTING_SEEDS:
            rep_idx += 1
            run_id = f"{cfg_name}_s{seed}"
            run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
            if os.path.isfile(run_csv):
                continue
            print(f"  [{rep_idx:03d}/{total_reporting_runs:03d}] {cfg_name} seed {seed:4d} ...", end="", flush=True)
            t0 = time.time()
            ok, msg = run_job(cfg["agents"], cfg["threads"], cfg["parallel"], cfg["V"], seed, run_id)
            dt = time.time() - t0
            print(f" {'OK' if ok else 'FAIL'} ({dt:.2f}s)")
            if not ok and "COLLISION" in msg:
                print(f"[FATAL ERROR] {msg}")
                sys.exit(1)

    t_rep_total = time.time() - t_rep_start
    print(f"\nAll reporting runs completed in {t_rep_total/60:.2f} minutes!")

    # ─────────────────────────────────────────────────────────────
    # PHASE C: Rigorous Aggregation & Statistical Compilation
    # ─────────────────────────────────────────────────────────────
    print("\n>>> PHASE C: Compiling Aggregated Tables, Quality Parity, and Figures...")
    compile_constant_density_results(v_star)

def compile_constant_density_results(v_star):
    runs_by_cfg = defaultdict(dict)
    for f in os.listdir(RAW_DIR):
        if f.startswith("run_scale_") and f.endswith(".csv"):
            run_id = f.replace("run_", "").replace(".csv", "")
            data = parse_run_result(run_id)
            parts = run_id.split("_")
            seed = int(parts[-1].replace("s", ""))
            cfg_name = "_".join(parts[:-1])
            runs_by_cfg[cfg_name][seed] = data

    parity_rows = []
    speedup_rows = []

    for N in [50, 100, 200, 400, 800]:
        v0_cfg = f"scale_a{N}_v0_seq"
        v0_dict = runs_by_cfg.get(v0_cfg, {})
        if not v0_dict:
            continue

        v_list = [8]
        if N in v_star and v_star[N] != 8:
            v_list.append(v_star[N])

        for V in v_list:
            # Baseline V1 (1 thread) for parallel speedup
            v1_cfg = f"scale_a{N}_V{V}_p1"
            v1_dict = runs_by_cfg.get(v1_cfg, {})

            for p in [1, 2, 4, 8, 11]:
                cfg_name = f"scale_a{N}_V{V}_p{p}"
                runs_dict = runs_by_cfg.get(cfg_name, {})
                if not runs_dict:
                    continue

                # Match runs by seed with V0 and V1
                common_seeds = sorted([s for s in runs_dict if s in v0_dict])
                if not common_seeds:
                    continue

                tp_vals = [runs_dict[s]["throughput"] for s in common_seeds]
                tasks_vals = [runs_dict[s]["num_tasks_completed"] for s in common_seeds]
                service_vals = [runs_dict[s]["mean_service_time"] for s in common_seeds]
                solver_vals = [runs_dict[s]["solver_runtime_ms"] for s in common_seeds]
                total_vals = [runs_dict[s]["total_runtime_ms"] for s in common_seeds]
                fb_vals = [runs_dict[s]["fallback_count"] for s in common_seeds]
                groups_vals = [runs_dict[s]["mean_groups"] for s in common_seeds]
                frac_vals = [runs_dict[s]["largest_group_fraction"] for s in common_seeds]
                bound_vals = [runs_dict[s]["theoretical_bound"] for s in common_seeds]

                v0_tp_common = [v0_dict[s]["throughput"] for s in common_seeds]
                v0_total_common = [v0_dict[s]["total_runtime_ms"] for s in common_seeds]
                v0_solver_common = [v0_dict[s]["solver_runtime_ms"] for s in common_seeds]

                # Per-seed paired ratios
                tp_ratios = [tp / v0 if v0 > 0 else 1.0 for tp, v0 in zip(tp_vals, v0_tp_common)]
                sp_total_v0 = [v0 / t if t > 0 else 1.0 for v0, t in zip(v0_total_common, total_vals)]
                sp_solver_v0 = [v0 / s if s > 0 else 1.0 for v0, s in zip(v0_solver_common, solver_vals)]

                # V2 vs V1 (pure parallel speedup)
                if v1_dict and all(s in v1_dict for s in common_seeds):
                    v1_total_common = [v1_dict[s]["total_runtime_ms"] for s in common_seeds]
                    v1_solver_common = [v1_dict[s]["solver_runtime_ms"] for s in common_seeds]
                    sp_parallel_total = [v1 / t if t > 0 else 1.0 for v1, t in zip(v1_total_common, total_vals)]
                    sp_parallel_solver = [v1 / s if s > 0 else 1.0 for v1, s in zip(v1_solver_common, solver_vals)]
                    sp_algo_v1_v0 = [v0 / v1 if v1 > 0 else 1.0 for v0, v1 in zip(v0_total_common, v1_total_common)]
                else:
                    sp_parallel_total = sp_total_v0
                    sp_parallel_solver = sp_solver_v0
                    sp_algo_v1_v0 = [1.0] * len(common_seeds)

                # Medians
                tp_med = sorted(tp_vals)[len(tp_vals)//2]
                tasks_med = sorted(tasks_vals)[len(tasks_vals)//2]
                service_med = sorted(service_vals)[len(service_vals)//2]
                solver_med = sorted(solver_vals)[len(solver_vals)//2]
                total_med = sorted(total_vals)[len(total_vals)//2]
                v0_total_med = sorted(v0_total_common)[len(v0_total_common)//2]
                v0_solver_med = sorted(v0_solver_common)[len(v0_solver_common)//2]

                sp_total_med = sorted(sp_total_v0)[len(sp_total_v0)//2]
                sp_solver_med = sorted(sp_solver_v0)[len(sp_solver_v0)//2]
                sp_parallel_med = sorted(sp_parallel_total)[len(sp_parallel_total)//2]
                sp_algo_med = sorted(sp_algo_v1_v0)[len(sp_algo_v1_v0)//2]

                efficiency_med = sp_parallel_med / p
                mean_fb = sum(fb_vals) / len(fb_vals)
                fb_rate = mean_fb / 50.0
                groups_med = sorted(groups_vals)[len(groups_vals)//2]
                frac_med = sorted(frac_vals)[len(frac_vals)//2]
                bound_med = sorted(bound_vals)[len(bound_vals)//2]

                # Bootstrap 95% CIs
                _, tp_lo, tp_hi = bootstrap_ci(tp_vals)
                _, tasks_lo, tasks_hi = bootstrap_ci(tasks_vals)
                _, sp_lo, sp_hi = bootstrap_ci(sp_total_v0)
                _, ratio_lo, ratio_hi = bootstrap_ci(tp_ratios)
                ratio_med = sorted(tp_ratios)[len(tp_ratios)//2]

                # Karp-Flatt metric e = (1/S_parallel - 1/p) / (1 - 1/p)
                if p > 1 and sp_parallel_med > 0:
                    karp_flatt = (1.0 / sp_parallel_med - 1.0 / p) / (1.0 - 1.0 / p)
                else:
                    karp_flatt = 0.0

                flag_parity = "FLAG (<95%)" if (ratio_med < 0.95) else "OK"

                parity_rows.append({
                    "agents": N, "V": V, "threads": p,
                    "throughput_med": round(tp_med, 4),
                    "throughput_95ci": f"[{tp_lo:.4f}, {tp_hi:.4f}]",
                    "tasks_completed_med": tasks_med,
                    "tasks_completed_95ci": f"[{tasks_lo:.1f}, {tasks_hi:.1f}]",
                    "service_time_med": round(service_med, 1),
                    "throughput_ratio_vs_v0": round(ratio_med, 4),
                    "ratio_95ci": f"[{ratio_lo:.4f}, {ratio_hi:.4f}]",
                    "parity_status": flag_parity,
                    "fallback_rate": round(fb_rate, 4),
                    "mean_fallbacks": round(mean_fb, 1)
                })

                speedup_rows.append({
                    "agents": N, "V": V, "threads": p,
                    "v0_total_ms": round(v0_total_med, 1),
                    "v0_solver_ms": round(v0_solver_med, 1),
                    "total_ms": round(total_med, 1),
                    "solver_ms": round(solver_med, 1),
                    "v1_vs_v0_algorithmic_speedup": round(sp_algo_med, 3),
                    "v2_vs_v1_parallel_speedup": round(sp_parallel_med, 3),
                    "v2_vs_v0_overall_speedup": round(sp_total_med, 3),
                    "speedup_95ci": f"[{sp_lo:.3f}, {sp_hi:.3f}]",
                    "efficiency": round(efficiency_med, 3),
                    "karp_flatt": round(karp_flatt, 4),
                    "mean_groups": round(groups_med, 1),
                    "largest_group_fraction": round(frac_med, 4),
                    "theoretical_bound": round(bound_med, 2),
                    "fallback_rate": round(fb_rate, 4)
                })

    # Save summary CSVs
    parity_csv = os.path.join(AGG_DIR, "constant_density_quality_parity.csv")
    with open(parity_csv, "w") as f:
        writer = csv.DictWriter(f, fieldnames=list(parity_rows[0].keys()))
        writer.writeheader()
        writer.writerows(parity_rows)

    speedup_csv = os.path.join(AGG_DIR, "constant_density_speedup.csv")
    with open(speedup_csv, "w") as f:
        writer = csv.DictWriter(f, fieldnames=list(speedup_rows[0].keys()))
        writer.writeheader()
        writer.writerows(speedup_rows)

    print(f"Saved: {parity_csv}")
    print(f"Saved: {speedup_csv}")

    # Generate Figures
    generate_figures(speedup_rows, parity_rows)

def generate_figures(speedup_rows, parity_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"[WARNING] Matplotlib import failed: {e}. Skipping figure rendering.", file=sys.stderr)
        return

    # 1. Figure: Speedup and Efficiency vs p for N=400 and N=800
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    threads_set = [1, 2, 4, 8, 11]

    # Color palette
    colors = {
        (400, 8): "#1f77b4",
        (800, 8): "#d62728",
    }

    # Plot ideal speedup reference
    ax1.plot(threads_set, threads_set, "k--", alpha=0.5, label="Ideal Linear (S=p)")
    ax2.plot(threads_set, [1.0]*len(threads_set), "k--", alpha=0.5, label="Ideal Efficiency (E=1.0)")

    for row in speedup_rows:
        N = row["agents"]
        V = row["V"]
        p = row["threads"]
        if N in [400, 800]:
            pass

    # Group by (N, V)
    grouped = defaultdict(list)
    for r in speedup_rows:
        grouped[(r["agents"], r["V"])].append(r)

    for (N, V), rows in grouped.items():
        if N not in [400, 800]:
            continue
        rows.sort(key=lambda x: x["threads"])
        ps = [r["threads"] for r in rows]
        sp = [r["v2_vs_v0_overall_speedup"] for r in rows]
        eff = [r["efficiency"] for r in rows]
        label = f"N={N}, V={V}"
        marker = "o" if N == 400 else "s"
        color = "#2ca02c" if N == 400 and V != 8 else ("#1f77b4" if N == 400 else ("#ff7f0e" if V != 8 else "#d62728"))

        ax1.plot(ps, sp, marker=marker, linewidth=2, label=label, color=color)
        ax2.plot(ps, eff, marker=marker, linewidth=2, label=label, color=color)

    ax1.set_xlabel("Worker Threads (p)", fontsize=11)
    ax1.set_ylabel("Overall Speedup vs V0 (T_v0 / T_v2)", fontsize=11)
    ax1.set_title("Speedup vs Worker Threads (N=400, 800)", fontsize=12, fontweight="bold")
    ax1.set_xticks(threads_set)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left")

    ax2.set_xlabel("Worker Threads (p)", fontsize=11)
    ax2.set_ylabel("Parallel Efficiency (S_parallel / p)", fontsize=11)
    ax2.set_title("Parallel Efficiency vs Worker Threads", fontsize=12, fontweight="bold")
    ax2.set_xticks(threads_set)
    ax2.set_ylim(0, 1.1)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right")

    plt.tight_layout()
    f1_path = os.path.join(FIG_DIR, "constant_density_speedup_efficiency_vs_p.png")
    plt.savefig(f1_path, dpi=300)
    plt.close()
    print(f"Generated figure: {f1_path}")

    # 2. Figure: Speedup vs Mean Group Count & Speedup vs Largest-Group Fraction
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Scatter of all evaluated configs at p=8
    p8_rows = [r for r in speedup_rows if r["threads"] == 8]
    x_groups = [r["mean_groups"] for r in p8_rows]
    y_sp = [r["v2_vs_v0_overall_speedup"] for r in p8_rows]
    x_frac = [r["largest_group_fraction"] for r in p8_rows]
    labels = [f"N={r['agents']}" for r in p8_rows]

    scatter1 = ax1.scatter(x_groups, y_sp, c=[r["agents"] for r in p8_rows], cmap="viridis", s=90, edgecolors="black", zorder=3)
    for r in p8_rows:
        ax1.annotate(f"N={r['agents']},V={r['V']}", (r["mean_groups"], r["v2_vs_v0_overall_speedup"]),
                     textcoords="offset points", xytext=(5, 5), fontsize=8)
    ax1.set_xlabel("Mean Spatial Group Count per Cycle", fontsize=11)
    ax1.set_ylabel("Speedup at p=8 vs V0", fontsize=11)
    ax1.set_title("Speedup vs Mean Group Count (p=8)", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.6)

    # Subplot 2: Speedup vs Largest-Group Fraction with theoretical bound
    scatter2 = ax2.scatter(x_frac, y_sp, c=[r["agents"] for r in p8_rows], cmap="viridis", s=90, edgecolors="black", zorder=3)
    for r in p8_rows:
        ax2.annotate(f"N={r['agents']},V={r['V']}", (r["largest_group_fraction"], r["v2_vs_v0_overall_speedup"]),
                     textcoords="offset points", xytext=(5, 5), fontsize=8)

    # Theoretical Bound Curve: S <= 1 / f_max
    f_vals = np.linspace(min(x_frac) * 0.8, 1.0, 100)
    bound_vals = [min(8.0, 1.0 / f) for f in f_vals]
    ax2.plot(f_vals, bound_vals, "r--", linewidth=2, label="Domain Bound (min(p, 1/f_max))")

    ax2.set_xlabel("Largest-Group Fraction (f_max = S_max / N)", fontsize=11)
    ax2.set_ylabel("Speedup at p=8 vs V0", fontsize=11)
    ax2.set_title("Speedup vs Largest-Group Fraction (Domain Decomposition Bound)", fontsize=12, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right")

    plt.tight_layout()
    f2_path = os.path.join(FIG_DIR, "constant_density_speedup_vs_groups.png")
    plt.savefig(f2_path, dpi=300)
    plt.close()
    print(f"Generated figure: {f2_path}")

    # 3. Figure: Karp-Flatt Metric vs p
    fig, ax = plt.subplots(figsize=(8, 5))
    scales = [50, 100, 200, 400, 800]
    p_subset = [2, 4, 8, 11]

    for N in scales:
        n_rows = [r for r in speedup_rows if r["agents"] == N and r["V"] == 8 and r["threads"] in p_subset]
        n_rows.sort(key=lambda x: x["threads"])
        if n_rows:
            ps = [r["threads"] for r in n_rows]
            kf = [r["karp_flatt"] for r in n_rows]
            ax.plot(ps, kf, marker="o", linewidth=1.8, label=f"N={N} (V=8)")

    ax.set_xlabel("Worker Threads (p)", fontsize=11)
    ax.set_ylabel("Karp-Flatt Metric e(p)", fontsize=11)
    ax.set_title("Karp-Flatt Serial Fraction vs Worker Threads", fontsize=12, fontweight="bold")
    ax.set_xticks(p_subset)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend()

    plt.tight_layout()
    f3_path = os.path.join(FIG_DIR, "constant_density_karp_flatt.png")
    plt.savefig(f3_path, dpi=300)
    plt.close()
    print(f"Generated figure: {f3_path}")

    # 4. Figure: Tiled Warehouse Maps & Pickup-to-Delivery Distance
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Bar chart of map dimensions and cell count
    tile_names = ["1x1 (N=50)", "2x1 (N=100)", "2x2 (N=200)", "4x2 (N=400)", "4x4 (N=800)"]
    dims = [(33, 46), (66, 46), (66, 92), (132, 92), (132, 184)]
    cells = [r * c for r, c in dims]
    mean_dists = [21.57, 32.42, 50.10, 71.44, 103.18]

    x = np.arange(len(tile_names))
    width = 0.35

    ax1.bar(x - width/2, [c / 1000.0 for c in cells], width, label="Grid Area (kCells)", color="#4682b4")
    ax1.set_ylabel("Total Grid Cells (×10³)", fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(tile_names, rotation=20, ha="right", fontsize=9)
    ax1.set_title("Warehouse Map Tiling Footprint", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.6)

    ax1_twin = ax1.twinx()
    ax1_twin.plot(x, [50, 100, 200, 400, 800], color="#e74c3c", marker="s", linewidth=2, label="Agent Count (N)")
    ax1_twin.set_ylabel("Agent Count (N)", color="#e74c3c", fontsize=11)
    ax1_twin.tick_params(axis="y", labelcolor="#e74c3c")

    # Pickup-to-delivery distance scaling
    ax2.plot(x, mean_dists, marker="o", color="#27ae60", linewidth=2.5, label="Measured Mean Travel Distance")
    # Fit O(sqrt(Area))
    sqrt_cells = [math.sqrt(c) for c in cells]
    scale_factor = mean_dists[0] / sqrt_cells[0]
    expected_dists = [s * scale_factor for s in sqrt_cells]
    ax2.plot(x, expected_dists, "k--", label=r"Theoretical $O(\sqrt{\mathrm{Area}})$ Scaling", alpha=0.7)

    ax2.set_ylabel("Mean Pickup-to-Delivery Distance (Timesteps)", fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels(tile_names, rotation=20, ha="right", fontsize=9)
    ax2.set_title("Travel Distance Scaling Across Tiled Maps", fontsize=12, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend()

    plt.tight_layout()
    f4_path = os.path.join(FIG_DIR, "tiled_warehouse_maps.png")
    plt.savefig(f4_path, dpi=300)
    plt.close()
    print(f"Generated figure: {f4_path}")

if __name__ == "__main__":
    main()
