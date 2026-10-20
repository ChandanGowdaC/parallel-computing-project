#!/usr/bin/env python3
"""
Person A & D Experiment Sweep Harness
Runs multi-threaded scaling benchmarks across thread counts, agent counts, and scenarios.
Logs results into a centralized CSV for speedup and throughput evaluation.
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BIN_PATH = os.path.join(PROJECT_ROOT, "build", "lifelong")

def parse_args():
    parser = argparse.ArgumentParser(description="GD-RHCR & Lifelong MAPF Experiment Sweep Harness")
    parser.add_argument("--binary", default=BIN_PATH, help="Path to lifelong executable")
    parser.add_argument("--scenario", default="KIVA", choices=["KIVA", "SORTING"], help="Simulation scenario")
    parser.add_argument("--map", default=os.path.join(PROJECT_ROOT, "maps", "kiva.map"), help="Map file path")
    parser.add_argument("--solver", default="ECBS", choices=["ECBS", "PBS", "WHCA"], help="MAPF solver")
    parser.add_argument("--threads", nargs="+", type=int, default=[1, 2, 4], help="List of thread counts to test")
    parser.add_argument("--agents", nargs="+", type=int, default=[50, 100], help="List of agent counts to test")
    parser.add_argument("--sim-time", type=int, default=15, help="Simulation timesteps per run")
    parser.add_argument("--sim-window", type=int, default=1, help="Replanning window h")
    parser.add_argument("--suboptimal-bound", type=float, default=1.5, help="ECBS suboptimal bound")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    parser.add_argument("--output-csv", default=os.path.join(PROJECT_ROOT, "exp", "sweep_results.csv"), help="CSV output path")
    parser.add_argument("--smoke", action="store_true", help="Quick test run with small parameters")
    return parser.parse_args()

def run_single(binary, scenario, map_file, solver, agents, threads, sim_time, sim_window, subopt, seed, output_csv):
    out_dir = os.path.join(PROJECT_ROOT, "exp", f"run_k{agents}_t{threads}")
    cmd = [
        binary,
        f"--scenario={scenario}",
        "-m", map_file,
        "-k", str(agents),
        f"--solver={solver}",
        f"--simulation_time={sim_time}",
        f"--simulation_window={sim_window}",
        f"--suboptimal_bound={subopt}",
        "--dummy_paths=1",
        f"--seed={seed}",
        f"--threads={threads}",
        f"-o", out_dir,
        f"--csv_metrics={output_csv}"
    ]
    
    print(f"Running: agents={agents}, threads={threads}, solver={solver}...")
    start_t = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_t
    
    if res.returncode != 0:
        print(f"  [ERROR] Exit code {res.returncode}")
        print(res.stderr[:300])
        return False
    else:
        print(f"  [SUCCESS] Finished in {elapsed:.2f}s")
        return True

def main():
    args = parse_args()
    
    if not os.path.isfile(args.binary):
        print(f"Binary not found at {args.binary}. Running build.sh first...")
        build_res = subprocess.run([os.path.join(PROJECT_ROOT, "build.sh")])
        if build_res.returncode != 0:
            print("Build failed. Exiting.")
            sys.exit(1)

    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)

    threads_list = [1, 2] if args.smoke else args.threads
    agents_list = [20] if args.smoke else args.agents
    sim_time = 5 if args.smoke else args.sim_time

    print("==================================================")
    print("  Starting Experiment Sweep")
    print(f"  Scenario: {args.scenario} | Solver: {args.solver}")
    print(f"  Threads:  {threads_list}")
    print(f"  Agents:   {agents_list}")
    print(f"  CSV:      {args.output_csv}")
    print("==================================================")

    for a in agents_list:
        for t in threads_list:
            run_single(
                binary=args.binary,
                scenario=args.scenario,
                map_file=args.map,
                solver=args.solver,
                agents=a,
                threads=t,
                sim_time=sim_time,
                sim_window=args.sim_window,
                subopt=args.suboptimal_bound,
                seed=args.seed,
                output_csv=args.output_csv
            )

    print("\n==================================================")
    print(f"  Sweep Complete! Results logged to: {args.output_csv}")
    print("==================================================")

if __name__ == "__main__":
    main()
