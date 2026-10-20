#!/usr/bin/env python3
"""
scripts/plot_deadline_metrics.py — Person B & Person D Evaluation Pipeline

Generates plots and formatted summary tables for deadline-aware MAPF experiments:
  1. Deadline Satisfaction Rate vs. Task Arrival Rate (lambda) across scheduling policies (FIFO, EDF, DEADLINE_AWARE).
  2. Average & Maximum Tardiness vs. Task Arrival Rate.
  3. Rolling Deadline Satisfaction & Cumulative Overdue Tasks over simulation time (from snapshots CSV).
  4. Formatted ASCII summary table for quick terminal inspection.
"""

import os
import sys
import csv
import argparse
from collections import defaultdict

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze & Plot Deadline-Aware Workload Metrics")
    parser.add_argument("--metrics-csv", default="exp/sweep_results.csv",
                        help="Path to summary run metrics CSV (e.g., from sweep_experiments.py)")
    parser.add_argument("--snapshots-csv", default="",
                        help="Path to per-timestep deadline snapshots CSV (optional)")
    parser.add_argument("--output-dir", default="exp/plots",
                        help="Output directory for generated plots")
    return parser.parse_args()

def analyze_summary_csv(csv_path, output_dir):
    if not os.path.isfile(csv_path):
        print(f"[plot_deadline_metrics] File not found: {csv_path}")
        return

    runs = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                runs.append({
                    "scenario": r.get("scenario", "KIVA"),
                    "solver": r.get("solver", "ECBS"),
                    "agents": int(r.get("agents", 0)),
                    "threads": int(r.get("threads", 1)),
                    "parallel": r.get("parallel", "false").lower() == "true",
                    "throughput": float(r.get("throughput", 0.0)),
                    "tasks_total": int(r.get("tasks_total", 0)),
                    "tasks_on_time": int(r.get("tasks_on_time", 0)),
                    "tasks_overdue": int(r.get("tasks_overdue", 0)),
                    "deadline_satisfaction_rate": float(r.get("deadline_satisfaction_rate", 0.0)),
                    "avg_tardiness": float(r.get("avg_tardiness", 0.0)),
                    "max_tardiness": int(r.get("max_tardiness", 0)),
                })
            except (ValueError, KeyError):
                continue

    if not runs:
        print("[plot_deadline_metrics] No valid rows found in CSV.")
        return

    # Print ASCII summary table
    print("\n" + "=" * 92)
    print(f"{'Agents':<8} {'Threads':<8} {'Parallel':<10} {'Total':<8} {'On-Time':<9} {'Overdue':<9} {'Sat Rate':<10} {'Avg Tard':<10} {'Max Tard':<10}")
    print("=" * 92)
    for r in runs:
        par_str = "Yes" if r["parallel"] else "No"
        sat_pct = f"{r['deadline_satisfaction_rate'] * 100.0:.1f}%"
        print(f"{r['agents']:<8} {r['threads']:<8} {par_str:<10} {r['tasks_total']:<8} {r['tasks_on_time']:<9} {r['tasks_overdue']:<9} {sat_pct:<10} {r['avg_tardiness']:<10.2f} {r['max_tardiness']:<10}")
    print("=" * 92 + "\n")

    # Generate Matplotlib plots if available
    try:
        import matplotlib.pyplot as plt
        os.makedirs(output_dir, exist_ok=True)

        # Plot 1: Deadline Satisfaction Rate vs Agents
        agent_counts = sorted(list(set(r["agents"] for r in runs)))
        if len(agent_counts) >= 2:
            plt.figure(figsize=(8, 5))
            sat_rates = [next(r["deadline_satisfaction_rate"] * 100 for r in runs if r["agents"] == a) for a in agent_counts]
            plt.plot(agent_counts, sat_rates, "s-", color="#2b5c8f", linewidth=2, markersize=7)
            plt.title("Deadline Satisfaction Rate vs. Agent Count")
            plt.xlabel("Number of Agents (k)")
            plt.ylabel("Deadline Satisfaction Rate (%)")
            plt.ylim(0, 105)
            plt.grid(True, linestyle="--", alpha=0.6)
            p1 = os.path.join(output_dir, "deadline_satisfaction_vs_agents.png")
            plt.savefig(p1, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"Saved plot: {p1}")

            # Plot 2: Average Tardiness vs Agents
            plt.figure(figsize=(8, 5))
            avg_tards = [next(r["avg_tardiness"] for r in runs if r["agents"] == a) for a in agent_counts]
            plt.plot(agent_counts, avg_tards, "o-", color="#d95f02", linewidth=2, markersize=7)
            plt.title("Average Task Tardiness vs. Agent Count")
            plt.xlabel("Number of Agents (k)")
            plt.ylabel("Average Tardiness (timesteps)")
            plt.grid(True, linestyle="--", alpha=0.6)
            p2 = os.path.join(output_dir, "avg_tardiness_vs_agents.png")
            plt.savefig(p2, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"Saved plot: {p2}")

    except ImportError:
        print("[plot_deadline_metrics] matplotlib not installed. Skipping PNG generation.")

def analyze_snapshots_csv(snap_path, output_dir):
    if not snap_path or not os.path.isfile(snap_path):
        return

    timesteps = []
    finished = []
    overdue = []
    sat_rates = []

    with open(snap_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                timesteps.append(int(r["timestep"]))
                finished.append(int(r["tasks_finished"]))
                overdue.append(int(r["tasks_overdue"]))
                sat_rates.append(float(r["deadline_satisfaction_rate"]) * 100.0)
            except (ValueError, KeyError):
                continue

    if not timesteps:
        return

    try:
        import matplotlib.pyplot as plt
        os.makedirs(output_dir, exist_ok=True)

        fig, ax1 = plt.subplots(figsize=(9, 5))

        color = "#1b9e77"
        ax1.set_xlabel("Simulation Timestep")
        ax1.set_ylabel("Cumulative Finished Tasks", color=color)
        ax1.plot(timesteps, finished, color=color, linewidth=2, label="Tasks Finished")
        ax1.plot(timesteps, overdue, color="#d95f02", linestyle="--", linewidth=2, label="Tasks Overdue")
        ax1.tick_params(axis="y", labelcolor=color)
        ax1.grid(True, linestyle="--", alpha=0.5)

        ax2 = ax1.twinx()
        color = "#7570b3"
        ax2.set_ylabel("Rolling Satisfaction Rate (%)", color=color)
        ax2.plot(timesteps, sat_rates, color=color, linewidth=2, linestyle=":", label="Satisfaction %")
        ax2.tick_params(axis="y", labelcolor=color)
        ax2.set_ylim(0, 105)

        plt.title("Lifelong MAPF: Task Completion & Deadline Satisfaction Over Time")
        fig.tight_layout()
        p = os.path.join(output_dir, "deadline_time_series.png")
        plt.savefig(p, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Saved time-series plot: {p}")

    except ImportError:
        pass

def main():
    args = parse_args()
    analyze_summary_csv(args.metrics_csv, args.output_dir)
    if args.snapshots_csv:
        analyze_snapshots_csv(args.snapshots_csv, args.output_dir)

if __name__ == "__main__":
    main()
