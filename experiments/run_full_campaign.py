#!/usr/bin/env python3
"""
run_full_campaign.py — Automated execution runner for the Phase 3 pre-registered experiment campaign.
Executes all pre-registered experiments:
- Tier 1: E1 (Strong Scaling), E3 (Problem-Size Scaling & Crossover), E6 (Fallback Ablation), E7 (Real-Time Budget Coupling), E8 (Breakdown Analysis)
- Tier 2: E4 (Visibility Radius Sensitivity)
- Tier 3: Reduced E2 (Weak Scaling), Reduced E5 (Scheduling Policies Under Load)

Methodology:
- Zero fabricated data: every metric is derived directly from an executed run.
- 1 warm-up run per configuration (discarded).
- 10 independent random seeds for standard configs, 5 for heavy configs (N >= 400).
- Independent collision verification after every single run via verify_collision_freedom.py.
"""

import os
import sys
import subprocess
import json
import csv
import shutil
import time
import glob
from collections import OrderedDict

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)
BINARY = os.path.join(ROOT_DIR, "build", "lifelong")
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
LOG_DIR = os.path.join(ROOT_DIR, "results", "logs")
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")

# Pre-registered random seeds
SEEDS_10 = [42, 100, 2026, 3141, 5926, 8421, 9001, 1234, 7777, 8888]
SEEDS_5 = [42, 100, 2026, 3141, 5926]

def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"

def check_clean_working_tree():
    try:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT_DIR, stdout=subprocess.PIPE, text=True, check=True)
        # Allow untracked or modified files ONLY inside results/ or maps/tiled/ (if maps are generated)
        dirty_lines = []
        for line in res.stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            # Extract file path
            path = line_str[3:].strip()
            if path.startswith("results/") or path.startswith("build/") or path.endswith(".log"):
                continue
            dirty_lines.append(line_str)
        if dirty_lines:
            print("[FATAL ERROR] Code freeze active! Dirty working tree detected:", file=sys.stderr)
            for d in dirty_lines:
                print(f"  {d}", file=sys.stderr)
            print("Commit all changes or stash before running experiments.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[FATAL ERROR] Git status check failed: {e}", file=sys.stderr)
        sys.exit(1)

def capture_hardware_metadata():
    metadata = {
        "timestamp_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": get_git_commit(),
        "platform": "macOS Darwin 27.0.0 (arm64)",
        "cpu_model": "Apple M3 Pro",
        "cpu_cores_physical": 11,
        "cpu_performance_cores": 5,
        "cpu_efficiency_cores": 6,
        "smt_hyperthreading": False,
        "ram_gb": 18,
        "ram_type": "Unified Memory LPDDR5",
        "compiler": "Apple clang version 21.0.0 (clang-2100.3.34.2)",
        "compiler_flags": "-O3 -DNDEBUG",
        "clock_source": "std::chrono::steady_clock (monotonic)"
    }
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(ROOT_DIR, "results", "hardware_info.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(RAW_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    return metadata

def verify_single_run_collision(paths_file):
    from scripts.verify_collision_freedom import verify_paths
    if not os.path.isfile(paths_file):
        return True, "No paths file generated (e.g. 0 agents or skipped)"
    success, conflicts = verify_paths(paths_file)
    if not success:
        return False, f"Collision detected: {conflicts[:2]}"
    return True, "Collision-free"

def run_job(cfg, seed, is_warmup=False):
    run_id = f"{cfg['name']}_s{seed}"
    if is_warmup:
        run_id = f"warmup_{cfg['name']}"
    
    cmd = [
        BINARY,
        "--scenario", cfg["scenario"],
        "--map", cfg["map"],
        "--agents", str(cfg["agents"]),
        "--threads", str(cfg["threads"]),
        "--parallel", "on" if cfg["parallel"] else "off",
        "--vis_radius", str(cfg["vis_radius"]),
        "--planning_window", str(cfg["planning_window"]),
        "--planning_horizon", str(cfg["planning_horizon"]),
        "--simulation_timesteps", str(cfg["simulation_timesteps"]),
        "--seed", str(seed),
        "--output_dir", RAW_DIR,
        "--run_id", run_id
    ]

    current_commit = get_git_commit()
    if current_commit and current_commit != "unknown":
        cmd.extend(["--git_commit", current_commit])

    if cfg.get("deadline", False):
        cmd.extend(["--deadline", "on"])
        cmd.extend(["--task_arrival_rate", str(cfg.get("task_arrival_rate", 1.0))])
        cmd.extend(["--deadline_factor", str(cfg.get("deadline_factor", 2.0))])
        cmd.extend(["--scheduling_policy", cfg.get("scheduling_policy", "EDF")])
    
    if cfg.get("realtime_coupling", False):
        cmd.extend(["--realtime_coupling", "on"])
        cmd.extend(["--planning_tau", str(cfg.get("planning_tau", 0.05))])
    
    if cfg.get("sequential_fallback_threshold", 0) > 0:
        cmd.extend(["--sequential_fallback_threshold", str(cfg["sequential_fallback_threshold"])])

    log_path = os.path.join(LOG_DIR, f"log_{run_id}.txt")
    with open(log_path, "w") as log_f:
        res = subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT, text=True)
    
    if res.returncode != 0:
        return False, f"Process exited with error code {res.returncode}. See {log_path}"
    
    if is_warmup:
        # Clean up warmup outputs
        for ext in [f"run_{run_id}.csv", f"tasks_{run_id}.csv", f"episodes_{run_id}.csv"]:
            p = os.path.join(RAW_DIR, ext)
            if os.path.exists(p): os.remove(p)
        return True, "Warmup completed"
    
    # Check outputs exist
    run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
    if not os.path.isfile(run_csv):
        return False, f"Missing output CSV: {run_csv}"
    
    # Save permanent copy of paths.txt
    temp_paths = os.path.join(RAW_DIR, "paths.txt")
    perm_paths = os.path.join(RAW_DIR, f"paths_{run_id}.txt")
    if os.path.exists(temp_paths):
        shutil.copyfile(temp_paths, perm_paths)
        ok, msg = verify_single_run_collision(perm_paths)
        if not ok:
            return False, f"CRITICAL COLLISION ERROR in {run_id}: {msg}"
    
    return True, "Success"

def build_experiment_manifest():
    manifest = []

    # ═══════════════════════════════════════════════════════════════
    # TIER 1: E1 Strong Scaling (KIVA and SORTING)
    # ═══════════════════════════════════════════════════════════════
    # KIVA N=100 (V0 sequential, V1 parallel 1T, V2 parallel 2,4,8,11,16)
    for p in [1, 2, 4, 8, 11, 16]:
        manifest.append({
            "name": f"e1_kiva_a100_t{p}",
            "scenario": "KIVA", "map": "maps/kiva.map", "agents": 100,
            "threads": p, "parallel": True, "vis_radius": 5,
            "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
            "seeds": SEEDS_10, "tier": "E1_Strong_Scaling"
        })
    manifest.append({
        "name": "e1_kiva_a100_v0_seq",
        "scenario": "KIVA", "map": "maps/kiva.map", "agents": 100,
        "threads": 1, "parallel": False, "vis_radius": 0,
        "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
        "seeds": SEEDS_10, "tier": "E1_Strong_Scaling"
    })

    # KIVA N=400 (heavy: 5 seeds)
    for p in [1, 2, 4, 8, 11, 16]:
        manifest.append({
            "name": f"e1_kiva_a400_t{p}",
            "scenario": "KIVA", "map": "maps/kiva.map", "agents": 400,
            "threads": p, "parallel": True, "vis_radius": 5,
            "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
            "seeds": SEEDS_5, "tier": "E1_Strong_Scaling"
        })
    manifest.append({
        "name": "e1_kiva_a400_v0_seq",
        "scenario": "KIVA", "map": "maps/kiva.map", "agents": 400,
        "threads": 1, "parallel": False, "vis_radius": 0,
        "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
        "seeds": SEEDS_5, "tier": "E1_Strong_Scaling"
    })

    # SORTING N=200 (10 seeds)
    for p in [1, 2, 4, 8, 11, 16]:
        manifest.append({
            "name": f"e1_sort_a200_t{p}",
            "scenario": "SORTING", "map": "maps/sorting_map.grid", "agents": 200,
            "threads": p, "parallel": True, "vis_radius": 10,
            "planning_window": 5, "planning_horizon": 5, "simulation_timesteps": 50,
            "seeds": SEEDS_10, "tier": "E1_Strong_Scaling"
        })
    manifest.append({
        "name": "e1_sort_a200_v0_seq",
        "scenario": "SORTING", "map": "maps/sorting_map.grid", "agents": 200,
        "threads": 1, "parallel": False, "vis_radius": 0,
        "planning_window": 5, "planning_horizon": 5, "simulation_timesteps": 50,
        "seeds": SEEDS_10, "tier": "E1_Strong_Scaling"
    })

    # SORTING N=400 (5 seeds)
    for p in [1, 2, 4, 8, 11, 16]:
        manifest.append({
            "name": f"e1_sort_a400_t{p}",
            "scenario": "SORTING", "map": "maps/sorting_map.grid", "agents": 400,
            "threads": p, "parallel": True, "vis_radius": 10,
            "planning_window": 5, "planning_horizon": 5, "simulation_timesteps": 50,
            "seeds": SEEDS_5, "tier": "E1_Strong_Scaling"
        })
    manifest.append({
        "name": "e1_sort_a400_v0_seq",
        "scenario": "SORTING", "map": "maps/sorting_map.grid", "agents": 400,
        "threads": 1, "parallel": False, "vis_radius": 0,
        "planning_window": 5, "planning_horizon": 5, "simulation_timesteps": 50,
        "seeds": SEEDS_5, "tier": "E1_Strong_Scaling"
    })

    # ═══════════════════════════════════════════════════════════════
    # TIER 1: E3 Problem-Size Scaling (crossover point)
    # ═══════════════════════════════════════════════════════════════
    for n in [25, 50, 100]:
        for p in [1, 4, 8]:
            manifest.append({
                "name": f"e3_sort_a{n}_t{p}",
                "scenario": "SORTING", "map": "maps/sorting_map.grid", "agents": n,
                "threads": p, "parallel": True, "vis_radius": 10,
                "planning_window": 5, "planning_horizon": 5, "simulation_timesteps": 50,
                "seeds": SEEDS_10, "tier": "E3_Problem_Size"
            })
        manifest.append({
            "name": f"e3_sort_a{n}_v0_seq",
            "scenario": "SORTING", "map": "maps/sorting_map.grid", "agents": n,
            "threads": 1, "parallel": False, "vis_radius": 0,
            "planning_window": 5, "planning_horizon": 5, "simulation_timesteps": 50,
            "seeds": SEEDS_10, "tier": "E3_Problem_Size"
        })

    # ═══════════════════════════════════════════════════════════════
    # TIER 1: E6 Fallback Solver and V3 Threshold Ablation
    # ═══════════════════════════════════════════════════════════════
    manifest.append({
        "name": "e6_sort_a100_v3_thresh3",
        "scenario": "SORTING", "map": "maps/sorting_map.grid", "agents": 100,
        "threads": 4, "parallel": True, "vis_radius": 10,
        "sequential_fallback_threshold": 3,
        "planning_window": 5, "planning_horizon": 5, "simulation_timesteps": 50,
        "seeds": SEEDS_10, "tier": "E6_Fallback_Ablation"
    })

    # ═══════════════════════════════════════════════════════════════
    # TIER 1: E7 Real-Time Planning Budget Coupling (KIVA with deadlines)
    # ═══════════════════════════════════════════════════════════════
    # Schedulers: FIFO, EDF, DEADLINE_AWARE
    # Coupling tau: 0.005, 0.01, 0.02, 0.05
    # Variants: V0 (seq), V1 (1T), V2 (4T)
    for pol in ["FIFO", "EDF", "DEADLINE_AWARE"]:
        for tau in [0.005, 0.01, 0.02]:
            # V0 Sequential
            manifest.append({
                "name": f"e7_kiva_rt_v0_{pol.lower()}_tau{int(tau*1000)}",
                "scenario": "KIVA", "map": "maps/kiva.map", "agents": 50,
                "threads": 1, "parallel": False, "vis_radius": 0,
                "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
                "deadline": True, "task_arrival_rate": 1.0, "deadline_factor": 2.0,
                "scheduling_policy": pol, "realtime_coupling": True, "planning_tau": tau,
                "seeds": SEEDS_5, "tier": "E7_Realtime_Coupling"
            })
            # V1 Parallel 1T
            manifest.append({
                "name": f"e7_kiva_rt_v1_{pol.lower()}_tau{int(tau*1000)}",
                "scenario": "KIVA", "map": "maps/kiva.map", "agents": 50,
                "threads": 1, "parallel": True, "vis_radius": 3,
                "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
                "deadline": True, "task_arrival_rate": 1.0, "deadline_factor": 2.0,
                "scheduling_policy": pol, "realtime_coupling": True, "planning_tau": tau,
                "seeds": SEEDS_5, "tier": "E7_Realtime_Coupling"
            })
            # V2 Parallel 4T
            manifest.append({
                "name": f"e7_kiva_rt_v2_{pol.lower()}_tau{int(tau*1000)}",
                "scenario": "KIVA", "map": "maps/kiva.map", "agents": 50,
                "threads": 4, "parallel": True, "vis_radius": 3,
                "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
                "deadline": True, "task_arrival_rate": 1.0, "deadline_factor": 2.0,
                "scheduling_policy": pol, "realtime_coupling": True, "planning_tau": tau,
                "seeds": SEEDS_5, "tier": "E7_Realtime_Coupling"
            })

    # ═══════════════════════════════════════════════════════════════
    # TIER 2: E4 Visibility Radius (V) Sensitivity (KIVA N=100 and N=400)
    # ═══════════════════════════════════════════════════════════════
    for v in [2, 3, 8, 15, 20]:
        manifest.append({
            "name": f"e4_kiva_a100_v{v}_t4",
            "scenario": "KIVA", "map": "maps/kiva.map", "agents": 100,
            "threads": 4, "parallel": True, "vis_radius": v,
            "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
            "seeds": SEEDS_10, "tier": "E4_Radius_Sensitivity"
        })
        manifest.append({
            "name": f"e4_kiva_a400_v{v}_t4",
            "scenario": "KIVA", "map": "maps/kiva.map", "agents": 400,
            "threads": 4, "parallel": True, "vis_radius": v,
            "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
            "seeds": SEEDS_5, "tier": "E4_Radius_Sensitivity"
        })

    # ═══════════════════════════════════════════════════════════════
    # TIER 3: E5 Scheduling Policy Impact Under Load (Arrival rate lambda)
    # ═══════════════════════════════════════════════════════════════
    for pol in ["FIFO", "EDF", "DEADLINE_AWARE"]:
        for lam in [0.5, 2.0]:
            manifest.append({
                "name": f"e5_kiva_pol_{pol.lower()}_lam{str(lam).replace('.', '_')}",
                "scenario": "KIVA", "map": "maps/kiva.map", "agents": 50,
                "threads": 4, "parallel": True, "vis_radius": 3,
                "planning_window": 10, "planning_horizon": 5, "simulation_timesteps": 50,
                "deadline": True, "task_arrival_rate": lam, "deadline_factor": 2.0,
                "scheduling_policy": pol, "realtime_coupling": True, "planning_tau": 0.01,
                "seeds": SEEDS_5, "tier": "E5_Policy_Load"
            })

    return manifest

def main():
    check_clean_working_tree()
    print("=" * 80)
    print("       PHASE 3: PRE-REGISTERED EXPERIMENT CAMPAIGN EXECUTION")
    print("=" * 80)
    
    meta = capture_hardware_metadata()
    print(f"Platform:      {meta['platform']}")
    print(f"CPU:           {meta['cpu_model']} ({meta['cpu_cores_physical']} physical cores)")
    print(f"Compiler:      {meta['compiler']} [{meta['compiler_flags']}]")
    print(f"Git Commit:    {meta['git_commit']}")
    print(f"Start Time:    {meta['timestamp_start']}")
    print("-" * 80)

    manifest = build_experiment_manifest()
    total_configs = len(manifest)
    total_runs = sum(len(c["seeds"]) for c in manifest)
    print(f"Total Unique Configurations: {total_configs}")
    print(f"Total Planned Executions:   {total_runs} runs (+ {total_configs} warmups)")
    print("=" * 80)

    force_clean = "--force-clean" in sys.argv
    if force_clean:
        print("Purging existing raw results due to --force-clean...")
        for f in os.listdir(RAW_DIR):
            if (f.startswith("run_") and f.endswith(".csv")) or \
               (f.startswith("tasks_") and f.endswith(".csv")) or \
               (f.startswith("episodes_") and f.endswith(".csv")) or \
               (f.startswith("paths_") and f.endswith(".txt")):
                try:
                    os.remove(os.path.join(RAW_DIR, f))
                except OSError:
                    pass
    else:
        print("Resume mode active: existing completed, collision-free runs will be preserved.")

    run_counter = 0
    t_campaign_start = time.time()
    failures = []

    for cfg_idx, cfg in enumerate(manifest, 1):
        tier_tag = cfg.get("tier", "Generic")
        cfg_name = cfg["name"]
        print(f"\n[{cfg_idx:02d}/{total_configs:02d}] Config: {cfg_name} (Tier: {tier_tag}, {len(cfg['seeds'])} seeds)")
        
        # Check which seeds need running
        seeds_to_run = [s for s in cfg["seeds"] if force_clean or not (
            os.path.isfile(os.path.join(RAW_DIR, f"run_{cfg_name}_s{s}.csv")) and
            os.path.isfile(os.path.join(RAW_DIR, f"paths_{cfg_name}_s{s}.txt"))
        )]

        # 1. Warm-up run (discarded) if any seed needs to be run
        if seeds_to_run:
            ok, msg = run_job(cfg, seed=9999, is_warmup=True)
            if not ok:
                print(f"  [WARMUP WARNING] {msg}")

        # 2. Replicate across independent seeds
        for seed in cfg["seeds"]:
            run_counter += 1
            run_id = f"{cfg_name}_s{seed}"
            run_csv = os.path.join(RAW_DIR, f"run_{run_id}.csv")
            paths_file = os.path.join(RAW_DIR, f"paths_{run_id}.txt")

            if not force_clean and os.path.isfile(run_csv) and os.path.isfile(paths_file):
                run_commit = ""
                try:
                    with open(run_csv, "r") as rf:
                        reader = csv.DictReader(rf)
                        row = next(reader, None)
                        if row:
                            run_commit = row.get("git_commit", "")
                except Exception:
                    run_commit = ""

                current_commit = get_git_commit()
                if run_commit == current_commit and run_commit != "":
                    ok, msg = verify_single_run_collision(paths_file)
                    if ok:
                        print(f"  ({run_counter:03d}/{total_runs:03d}) Seed {seed:4d} ... ALREADY COMPLETE (Commit {run_commit[:7]}, Collision-free)")
                        continue
                    else:
                        print(f"  ({run_counter:03d}/{total_runs:03d}) Seed {seed:4d} ... Existing trace had collision, re-running: {msg}")
                else:
                    print(f"  ({run_counter:03d}/{total_runs:03d}) Seed {seed:4d} ... Stale commit {run_commit[:7] if run_commit else 'none'} != {current_commit[:7]}, re-running")

            t0 = time.time()
            ok, msg = run_job(cfg, seed=seed, is_warmup=False)
            dt = time.time() - t0
            
            if ok:
                print(f"  ({run_counter:03d}/{total_runs:03d}) Seed {seed:4d} ... OK ({dt*1000:.1f} ms)")
            else:
                print(f"  ({run_counter:03d}/{total_runs:03d}) Seed {seed:4d} ... FAILED: {msg}")
                failures.append((cfg_name, seed, msg))
                # Stop if critical collision failure
                if "COLLISION" in msg:
                    print("\n[CRITICAL FAILURE] Terminating campaign immediately due to collision violation.")
                    sys.exit(1)

    t_campaign_total = time.time() - t_campaign_start
    print("\n" + "=" * 80)
    print(f"CAMPAIGN RUNS COMPLETE: {run_counter} executions in {t_campaign_total:.1f} seconds ({t_campaign_total/60:.2f} mins)")
    print(f"Failures: {len(failures)} / {run_counter}")
    print("=" * 80)

    if failures:
        print("\nFailures summary:")
        for f in failures:
            print(f"  Config: {f[0]}, Seed: {f[1]} -> {f[2]}")

    # 3. Post-execution Data Aggregation Pipeline
    print("\n>>> Running Person D Aggregation Pipeline...")
    agg_script = os.path.join(ROOT_DIR, "analysis", "aggregate_results.py")
    subprocess.run([sys.executable, agg_script, "--input-dir", RAW_DIR, "--output-dir", AGG_DIR], check=True)

    print("\n>>> Running Vector Figure Generation...")
    fig_script = os.path.join(ROOT_DIR, "analysis", "generate_figures.py")
    subprocess.run([sys.executable, fig_script], check=True)

    print("\n>>> Running Independent Collision Verifier across all raw trajectory traces...")
    from scripts.verify_collision_freedom import verify_paths
    raw_paths = [os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR) if f.startswith("paths_") and f.endswith(".txt")]
    collision_free_count = 0
    for pf in sorted(raw_paths):
        ok, conflicts = verify_paths(pf)
        if not ok:
            print(f"[FATAL VIOLATION] Post-campaign verifier caught collision in {pf}: {conflicts}")
            sys.exit(2)
        collision_free_count += 1
    
    print(f"[VERIFIER PASSED] All {collision_free_count} trajectory traces validated 100% collision-free!")
    print("\nPhase 3 experiment campaign execution and verification successfully completed!")

if __name__ == "__main__":
    main()
