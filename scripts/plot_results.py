#!/usr/bin/env python3
"""
Person A & D Result Analysis & Plotting Tool
Computes Speedup (T1 / Tp), Parallel Efficiency (Sp / p), and Throughput.
Generates both ASCII terminal summary tables and PNG figures (if matplotlib is available).
"""

import os
import sys
import csv
import argparse
from collections import defaultdict

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze and Plot RHCR / GD-RHCR Experiment Metrics")
    parser.add_argument("--csv", default="exp/sweep_results.csv", help="Path to input metrics CSV")
    parser.add_argument("--output-dir", default="exp/plots", help="Directory to save generated plots")
    return parser.parse_args()

def analyze_metrics(csv_path):
    if not os.path.isfile(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    # Group runs by (scenario, map, solver, agents)
    grouped = defaultdict(dict)
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                agents = int(row["agents"])
                threads = int(row["threads"])
                runtime = float(row["wall_runtime_sec"])
                throughput = float(row["throughput"])
                scenario = row.get("scenario", "KIVA")
                solver = row.get("solver", "ECBS")
                key = (scenario, solver, agents)
                grouped[key][threads] = {
                    "runtime": runtime,
                    "throughput": throughput
                }
            except (ValueError, KeyError) as e:
                continue

    print("\n" + "=" * 78)
    print(f"{'Scenario':<10} {'Solver':<8} {'Agents':<8} {'Threads':<8} {'Runtime(s)':<12} {'Speedup':<10} {'Efficiency':<10}")
    print("=" * 78)

    for (scenario, solver, agents), thread_data in sorted(grouped.items()):
        base_runtime = thread_data.get(1, {}).get("runtime", None)
        for t in sorted(thread_data.keys()):
            run = thread_data[t]
            rt = run["runtime"]
            if base_runtime and base_runtime > 0:
                speedup = base_runtime / rt
                eff = (speedup / t) * 100.0
                sp_str = f"{speedup:.2f}x"
                eff_str = f"{eff:.1f}%"
            else:
                sp_str = "1.00x" if t == 1 else "N/A"
                eff_str = "100.0%" if t == 1 else "N/A"

            print(f"{scenario:<10} {solver:<8} {agents:<8} {t:<8} {rt:<12.3f} {sp_str:<10} {eff_str:<10}")
        print("-" * 78)

    # Attempt to plot if matplotlib is available
    try:
        import matplotlib.pyplot as plt
        os.makedirs("exp/plots", exist_ok=True)

        for (scenario, solver, agents), thread_data in grouped.items():
            threads = sorted(thread_data.keys())
            if len(threads) < 2:
                continue
            base_runtime = thread_data.get(1, {}).get("runtime", thread_data[threads[0]]["runtime"])
            speedups = [base_runtime / thread_data[t]["runtime"] for t in threads]

            plt.figure(figsize=(8, 5))
            plt.plot(threads, speedups, "o-", label=f"Observed ({agents} agents)")
            plt.plot(threads, threads, "--", color="gray", label="Ideal Linear Speedup")
            plt.title(f"Speedup vs. Worker Threads ({scenario}, {solver}, k={agents})")
            plt.xlabel("Worker Threads (p)")
            plt.ylabel("Speedup (T1 / Tp)")
            plt.grid(True, linestyle="--", alpha=0.6)
            plt.legend()
            plot_path = f"exp/plots/speedup_{scenario}_{solver}_k{agents}.png"
            plt.savefig(plot_path, dpi=150)
            plt.close()
            print(f"Saved speedup plot to: {plot_path}")

    except ImportError:
        print("\nNote: matplotlib not found. ASCII table generated above. Install matplotlib for PNG charts.")

def main():
    args = parse_args()
    analyze_metrics(args.csv)

if __name__ == "__main__":
    main()
