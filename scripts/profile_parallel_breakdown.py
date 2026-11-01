#!/usr/bin/env python3
"""
profile_parallel_breakdown.py — Phase 2 profiling script to measure and report
the per-plan-cycle time breakdown across worker threads:
- t_partition (visibility graph and grouping)
- t_dispatch (task creation and queueing)
- t_solve (min, mean, max across workers)
- t_barrier_wait (coordinator wait / idle time)
- t_merge (conflict check and stitching)
- t_serial_rest (everything not parallelized)
"""

import os
import sys
import subprocess
import csv
import statistics

BINARY = "./build/lifelong"
RESULTS_DIR = "results/profiling_raw"

def run_instance(scenario, map_path, agents, threads, vis_radius, window, horizon, timesteps, seed, run_id):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    cmd = [
        BINARY,
        "--scenario", scenario,
        "--map", map_path,
        "--agents", str(agents),
        "--threads", str(threads),
        "--parallel", "on" if threads > 0 else "off",
        "--vis_radius", str(vis_radius),
        "--planning_window", str(window),
        "--planning_horizon", str(horizon),
        "--simulation_timesteps", str(timesteps),
        "--seed", str(seed),
        "--output_dir", RESULTS_DIR,
        "--run_id", run_id
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"Error running {run_id}: {res.stderr}")
        return None
    
    ep_file = os.path.join(RESULTS_DIR, f"episodes_{run_id}.csv")
    if not os.path.exists(ep_file):
        print(f"Episode file missing: {ep_file}")
        return None
    
    rows = []
    with open(ep_file, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def analyze_episodes(rows):
    if not rows:
        return {}
    
    def col_mean(key):
        vals = [float(r[key]) for r in rows if key in r]
        return statistics.mean(vals) if vals else 0.0

    return {
        "episodes": len(rows),
        "num_groups_mean": col_mean("num_groups"),
        "t_partition_ms": col_mean("t_partition_ms"),
        "t_dispatch_ms": col_mean("t_dispatch_ms"),
        "t_solve_min_ms": col_mean("min_group_solve_ms"),
        "t_solve_mean_ms": col_mean("mean_group_solve_ms"),
        "t_solve_max_ms": col_mean("max_group_solve_ms"),
        "t_barrier_wait_ms": col_mean("t_barrier_wait_ms"),
        "t_merge_ms": col_mean("merge_time_ms"),
        "t_serial_rest_ms": col_mean("t_serial_rest_ms"),
        "t_solve_wall_ms": col_mean("solve_time_ms"),
        "collisions_sum": sum(int(r["inter_group_collisions"]) for r in rows if "inter_group_collisions" in r)
    }

def main():
    configs = [
        # (scenario, map, agents, threads, V, w, h, T, seed)
        ("KIVA", "maps/kiva.map", 100, 1, 5, 10, 5, 30, 42),
        ("KIVA", "maps/kiva.map", 100, 2, 5, 10, 5, 30, 42),
        ("KIVA", "maps/kiva.map", 100, 4, 5, 10, 5, 30, 42),
        ("KIVA", "maps/kiva.map", 100, 8, 5, 10, 5, 30, 42),
        ("KIVA", "maps/kiva.map", 100, 11, 5, 10, 5, 30, 42),
        ("SORTING", "maps/sorting_map.grid", 100, 1, 10, 5, 5, 30, 42),
        ("SORTING", "maps/sorting_map.grid", 100, 2, 10, 5, 5, 30, 42),
        ("SORTING", "maps/sorting_map.grid", 100, 4, 10, 5, 5, 30, 42),
        ("SORTING", "maps/sorting_map.grid", 100, 8, 10, 5, 5, 30, 42),
        ("SORTING", "maps/sorting_map.grid", 100, 11, 10, 5, 5, 30, 42),
    ]

    print(f"{'Config':<28} | {'p':<2} | {'Groups':<6} | {'t_part':<8} | {'t_disp':<8} | {'t_solve_min':<11} | {'t_solve_mean':<12} | {'t_solve_max':<11} | {'t_wait':<8} | {'t_merge':<8} | {'t_rest':<8} | {'t_wall':<8}")
    print("-" * 145)

    summary_rows = []
    for sc, m, ag, th, v, w, h, t, s in configs:
        run_id = f"prof_{sc.lower()}_a{ag}_th{th}_s{s}"
        rows = run_instance(sc, m, ag, th, v, w, h, t, s, run_id)
        stats = analyze_episodes(rows)
        if stats:
            cfg_name = f"{sc} N={ag} V={v}"
            print(f"{cfg_name:<28} | {th:<2} | {stats['num_groups_mean']:<6.1f} | "
                  f"{stats['t_partition_ms']:<8.3f} | {stats['t_dispatch_ms']:<8.3f} | "
                  f"{stats['t_solve_min_ms']:<11.3f} | {stats['t_solve_mean_ms']:<12.3f} | "
                  f"{stats['t_solve_max_ms']:<11.3f} | {stats['t_barrier_wait_ms']:<8.3f} | "
                  f"{stats['t_merge_ms']:<8.3f} | {stats['t_serial_rest_ms']:<8.3f} | "
                  f"{stats['t_solve_wall_ms']:<8.3f}")
            stats["scenario"] = sc
            stats["agents"] = ag
            stats["threads"] = th
            stats["vis_radius"] = v
            summary_rows.append(stats)

    out_csv = os.path.join(RESULTS_DIR, "profiling_breakdown_summary.csv")
    if summary_rows:
        fieldnames = ["scenario", "agents", "threads", "vis_radius", "num_groups_mean", 
                      "t_partition_ms", "t_dispatch_ms", "t_solve_min_ms", "t_solve_mean_ms", 
                      "t_solve_max_ms", "t_barrier_wait_ms", "t_merge_ms", "t_serial_rest_ms", 
                      "t_solve_wall_ms", "collisions_sum"]
        with open(out_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in summary_rows:
                writer.writerow(r)
    print(f"\nProfiling breakdown saved to {out_csv}")

if __name__ == "__main__":
    main()
