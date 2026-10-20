#!/usr/bin/env python3
"""
generate_stub_data.py — Generates realistic synthetic experiment data
for testing the analysis/plotting pipeline before the actual RHCR solver is ready.

Person D — Week 1 deliverable: harness skeleton with stub data.

Usage:
    python3 generate_stub_data.py [--output-dir ../results/raw] [--num-seeds 5]

The generated data models realistic parallel computing behavior:
  - Sequential runtime scales linearly with agent count
  - Parallel runtime shows sub-linear speedup with diminishing returns
  - Deadline satisfaction degrades with higher arrival rates
  - Throughput improves with parallelism but plateaus
"""

import os
import csv
import json
import random
import math
import argparse
from datetime import datetime, timezone


def generate_run_id(map_name, mode, agents, threads, rate, vr, policy, seed):
    return f"{map_name}_{mode}_a{agents}_t{threads}_r{rate}_v{vr}_p{policy}_s{seed}"


def simulate_sequential_runtime(agents, rate, base_ms=50.0):
    """Model: runtime grows super-linearly with agents, linearly with rate."""
    return base_ms * (agents ** 1.35) * (1 + 0.2 * rate) + random.gauss(0, base_ms * 0.1)


def simulate_parallel_runtime(seq_runtime, threads, agents, vr):
    """
    Model Amdahl's law with overhead:
      parallel_fraction depends on visibility radius (more groups → more parallelism)
      communication overhead grows with thread count
    """
    # More agents relative to vr → more groups → better parallelism
    group_count = max(1, int(agents / (vr * 3 + 1)))
    effective_groups = min(group_count, threads)
    
    parallel_fraction = min(0.92, 0.6 + 0.03 * math.log2(max(1, effective_groups)))
    serial_fraction = 1.0 - parallel_fraction
    
    # Amdahl's law
    speedup = 1.0 / (serial_fraction + parallel_fraction / effective_groups)
    
    # Communication overhead
    overhead = 1.0 + 0.02 * threads + 0.001 * threads * math.log2(max(1, agents))
    
    runtime = (seq_runtime / speedup) * overhead + random.gauss(0, seq_runtime * 0.03)
    return max(runtime, seq_runtime * 0.08), group_count, effective_groups


def simulate_deadline_satisfaction(agents, rate, is_parallel, threads=1):
    """Model: satisfaction drops with load, improves with parallelism."""
    base_satisfaction = 0.95 - 0.08 * rate - 0.0002 * agents
    if is_parallel:
        base_satisfaction += 0.04 * math.log2(max(1, threads))
    base_satisfaction = max(0.1, min(0.99, base_satisfaction))
    return base_satisfaction + random.gauss(0, 0.02)


def simulate_throughput(agents, rate, runtime_ms, is_parallel, threads=1):
    """Model: throughput = tasks completed / time."""
    sim_timesteps = 5000
    tasks_generated = int(rate * sim_timesteps * (1 + 0.1 * random.random()))
    
    capacity = agents * 0.8
    if is_parallel:
        capacity *= (1 + 0.15 * math.log2(max(1, threads)))
    
    tasks_completed = int(min(tasks_generated, capacity * sim_timesteps / 1000))
    tasks_completed = max(1, tasks_completed + int(random.gauss(0, tasks_completed * 0.05)))
    
    throughput = tasks_completed / sim_timesteps
    return tasks_generated, tasks_completed, throughput


def generate_task_data(run_id, num_tasks, agents, rate, satisfaction_rate, policy):
    """Generate per-task CSV rows."""
    tasks = []
    map_size = 40  # approximate kiva map size
    
    for i in range(num_tasks):
        release_time = int(random.expovariate(rate / 100) * 100) if rate > 0 else i * 10
        deadline_window = random.randint(50, 300)
        deadline = release_time + deadline_window
        
        completed = random.random() < min(0.98, satisfaction_rate + 0.05)
        on_time = random.random() < satisfaction_rate if completed else False
        
        if completed:
            base_completion = release_time + int(deadline_window * random.uniform(0.3, 1.2))
            if on_time:
                completion_time = min(base_completion, deadline - random.randint(1, 20))
            else:
                completion_time = deadline + random.randint(1, 100)
            tardiness = max(0, completion_time - deadline)
            status = "completed" if on_time else "overdue"
        else:
            completion_time = -1
            tardiness = 0
            status = random.choice(["in_progress", "unassigned"])
        
        tasks.append({
            "run_id": run_id,
            "task_id": i,
            "release_time": release_time,
            "deadline": deadline,
            "pickup_x": random.randint(0, map_size),
            "pickup_y": random.randint(0, map_size),
            "delivery_x": random.randint(0, map_size),
            "delivery_y": random.randint(0, map_size),
            "assigned_agent": random.randint(0, agents - 1) if status != "unassigned" else -1,
            "completion_time": completion_time,
            "tardiness": tardiness,
            "status": status,
            "scheduling_policy": policy,
        })
    return tasks


def generate_episode_data(run_id, num_episodes, num_groups, agents, is_parallel, threads):
    """Generate per-episode CSV rows."""
    episodes = []
    avg_group_size = agents / max(1, num_groups)
    
    for ep in range(num_episodes):
        # Vary group sizes slightly
        sizes = []
        remaining = agents
        for g in range(num_groups - 1):
            sz = max(1, int(avg_group_size + random.gauss(0, avg_group_size * 0.2)))
            sz = min(sz, remaining - (num_groups - g - 1))
            sizes.append(sz)
            remaining -= sz
        sizes.append(remaining)
        
        base_solve = 20.0 * avg_group_size ** 1.2
        group_solve_times = [base_solve * (1 + random.gauss(0, 0.15)) for _ in range(num_groups)]
        
        if is_parallel and threads > 1:
            # Parallel: wall-clock = max of group times (limited by thread count)
            batches = math.ceil(num_groups / threads)
            solve_time = max(group_solve_times) * batches * (1 + 0.05 * random.random())
        else:
            solve_time = sum(group_solve_times)
        
        episodes.append({
            "run_id": run_id,
            "episode_id": ep,
            "timestep": ep * 20,  # every h=20 timesteps
            "num_groups": num_groups,
            "group_sizes": ",".join(str(s) for s in sizes),
            "solve_time_ms": round(solve_time, 2),
            "max_group_solve_ms": round(max(group_solve_times), 2),
            "min_group_solve_ms": round(min(group_solve_times), 2),
            "merge_time_ms": round(random.uniform(0.5, 5.0) * num_groups, 2),
            "inter_group_collisions": random.randint(0, max(0, num_groups - 1) * 2),
        })
    return episodes


def main():
    parser = argparse.ArgumentParser(description="Generate stub experiment data for pipeline testing")
    parser.add_argument("--output-dir", default="../results/raw", help="Output directory for CSV files")
    parser.add_argument("--num-seeds", type=int, default=5, help="Number of random seeds")
    parser.add_argument("--small", action="store_true", help="Generate small dataset for quick testing")
    args = parser.parse_args()
    
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Parameters
    maps = [("kiva", "KIVA")]
    solver = "ECBS"
    h, w = 20, 10
    sim_timesteps = 5000
    
    if args.small:
        thread_counts = [1, 2, 4]
        agent_counts = [50, 100, 200]
        arrival_rates = [0.5, 1.0, 2.0]
        visibility_radii = [10.0]
        seeds = list(range(42, 42 + min(args.num_seeds, 3)))
        policies = ["FIFO"]
    else:
        thread_counts = [1, 2, 4, 8, 16]
        agent_counts = [50, 100, 200, 400, 800]
        arrival_rates = [0.2, 0.5, 1.0, 2.0, 5.0]
        visibility_radii = [5.0, 10.0, 20.0]
        seeds = list(range(42, 42 + args.num_seeds))
        policies = ["FIFO", "EDF", "DEADLINE_AWARE"]
    
    # Collect all run-level rows for the combined summary
    all_runs = []
    total_runs = 0
    
    for map_name, scenario in maps:
        for agents in agent_counts:
            for rate in arrival_rates:
                for policy in policies:
                    for seed in seeds:
                        random.seed(seed + agents + int(rate * 1000))
                        
                        # ── Sequential baseline ──
                        seq_runtime = simulate_sequential_runtime(agents, rate)
                        seq_satisfaction = simulate_deadline_satisfaction(agents, rate, False)
                        seq_gen, seq_comp, seq_throughput = simulate_throughput(
                            agents, rate, seq_runtime, False
                        )
                        
                        run_id = generate_run_id(map_name, "sequential", agents, 1, rate, 0.0, policy, seed)
                        num_episodes = sim_timesteps // h
                        
                        # Tardiness stats
                        overdue_count = int(seq_gen * (1 - min(1, seq_satisfaction)))
                        avg_tard = random.uniform(5, 50) if overdue_count > 0 else 0
                        max_tard = avg_tard * random.uniform(2, 5) if overdue_count > 0 else 0
                        
                        run_row = {
                            "run_id": run_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "map_name": map_name,
                            "scenario": scenario,
                            "solver": solver,
                            "solver_mode": "sequential",
                            "thread_count": 1,
                            "agent_count": agents,
                            "task_arrival_rate": rate,
                            "planning_horizon_h": h,
                            "planning_window_w": w,
                            "visibility_radius_v": 0.0,
                            "seed": seed,
                            "simulation_timesteps": sim_timesteps,
                            "total_runtime_ms": round(seq_runtime, 2),
                            "solver_runtime_ms": round(seq_runtime * 0.85, 2),
                            "num_replan_episodes": num_episodes,
                            "num_tasks_generated": seq_gen,
                            "num_tasks_completed": seq_comp,
                            "throughput": round(seq_throughput, 4),
                            "num_groups": 1,
                            "avg_group_size": float(agents),
                            "max_group_solve_ms": round(seq_runtime / num_episodes, 2),
                            "num_collisions": 0,
                            "deadline_satisfaction_rate": round(min(1, max(0, seq_satisfaction)), 4),
                            "avg_tardiness": round(avg_tard, 2),
                            "max_tardiness": round(max_tard, 2),
                            "num_tasks_overdue": overdue_count,
                            "scheduling_policy": policy,
                        }
                        all_runs.append(run_row)
                        
                        # Write run CSV
                        _write_run_csv(output_dir, run_id, run_row)
                        
                        # Write task CSV
                        tasks = generate_task_data(run_id, seq_gen, agents, rate, seq_satisfaction, policy)
                        _write_task_csv(output_dir, run_id, tasks)
                        
                        # Write episode CSV
                        episodes = generate_episode_data(run_id, num_episodes, 1, agents, False, 1)
                        _write_episode_csv(output_dir, run_id, episodes)
                        
                        total_runs += 1
                        
                        # ── Parallel runs ──
                        for threads in thread_counts:
                            if threads == 1:
                                continue  # skip — same as sequential
                            for vr in visibility_radii:
                                random.seed(seed + agents + int(rate * 1000) + threads * 100 + int(vr))
                                
                                par_runtime, num_groups, eff_groups = simulate_parallel_runtime(
                                    seq_runtime, threads, agents, vr
                                )
                                par_satisfaction = simulate_deadline_satisfaction(
                                    agents, rate, True, threads
                                )
                                par_gen, par_comp, par_throughput = simulate_throughput(
                                    agents, rate, par_runtime, True, threads
                                )
                                
                                p_run_id = generate_run_id(map_name, "parallel", agents, threads, rate, vr, policy, seed)
                                
                                p_overdue = int(par_gen * (1 - min(1, par_satisfaction)))
                                p_avg_tard = random.uniform(3, 35) if p_overdue > 0 else 0
                                p_max_tard = p_avg_tard * random.uniform(2, 4) if p_overdue > 0 else 0
                                
                                p_run_row = {
                                    "run_id": p_run_id,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "map_name": map_name,
                                    "scenario": scenario,
                                    "solver": solver,
                                    "solver_mode": "parallel",
                                    "thread_count": threads,
                                    "agent_count": agents,
                                    "task_arrival_rate": rate,
                                    "planning_horizon_h": h,
                                    "planning_window_w": w,
                                    "visibility_radius_v": vr,
                                    "seed": seed,
                                    "simulation_timesteps": sim_timesteps,
                                    "total_runtime_ms": round(par_runtime, 2),
                                    "solver_runtime_ms": round(par_runtime * 0.85, 2),
                                    "num_replan_episodes": num_episodes,
                                    "num_tasks_generated": par_gen,
                                    "num_tasks_completed": par_comp,
                                    "throughput": round(par_throughput, 4),
                                    "num_groups": num_groups,
                                    "avg_group_size": round(agents / max(1, num_groups), 1),
                                    "max_group_solve_ms": round(par_runtime / num_episodes * 1.3, 2),
                                    "num_collisions": random.randint(0, num_groups * 3),
                                    "deadline_satisfaction_rate": round(min(1, max(0, par_satisfaction)), 4),
                                    "avg_tardiness": round(p_avg_tard, 2),
                                    "max_tardiness": round(p_max_tard, 2),
                                    "num_tasks_overdue": p_overdue,
                                    "scheduling_policy": policy,
                                }
                                all_runs.append(p_run_row)
                                
                                _write_run_csv(output_dir, p_run_id, p_run_row)
                                
                                p_tasks = generate_task_data(p_run_id, par_gen, agents, rate, par_satisfaction, policy)
                                _write_task_csv(output_dir, p_run_id, p_tasks)
                                
                                p_episodes = generate_episode_data(
                                    p_run_id, num_episodes, num_groups, agents, True, threads
                                )
                                _write_episode_csv(output_dir, p_run_id, p_episodes)
                                
                                total_runs += 1
    
    # Write combined summary
    summary_path = os.path.join(output_dir, "..", "experiment_summary.csv")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    
    if all_runs:
        fieldnames = list(all_runs[0].keys())
        with open(summary_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_runs)
    
    print(f"✓ Generated {total_runs} experiment runs in {output_dir}")
    print(f"  Summary: {summary_path}")


def _write_run_csv(output_dir, run_id, row):
    path = os.path.join(output_dir, f"run_{run_id}.csv")
    fieldnames = list(row.keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def _write_task_csv(output_dir, run_id, tasks):
    if not tasks:
        return
    path = os.path.join(output_dir, f"tasks_{run_id}.csv")
    fieldnames = list(tasks[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tasks)


def _write_episode_csv(output_dir, run_id, episodes):
    if not episodes:
        return
    path = os.path.join(output_dir, f"episodes_{run_id}.csv")
    fieldnames = list(episodes[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(episodes)


if __name__ == "__main__":
    main()
