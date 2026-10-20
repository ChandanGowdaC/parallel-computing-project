#!/usr/bin/env python3
"""
aggregate_results.py — Parses raw CSV experiment logs and computes summary statistics.

Person D — Data Aggregation Pipeline.

Reads all run_*.csv files from results/raw/ (or experiment_summary.csv),
computes mean/std across seeds, derives speedup/efficiency, and outputs
aggregated tables to results/aggregated/.

Usage:
    python3 aggregate_results.py [--input-dir ../results/raw] [--output-dir ../results/aggregated]
"""

import os
import glob
import csv
import argparse
import statistics
from collections import defaultdict


def load_summary_csv(path):
    """Load the combined experiment_summary.csv."""
    rows = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Cast numeric fields
            for key in row:
                if key in ("run_id", "timestamp", "map_name", "scenario", "solver",
                           "solver_mode", "scheduling_policy", "status"):
                    continue
                try:
                    if "." in str(row[key]):
                        row[key] = float(row[key])
                    else:
                        row[key] = int(row[key])
                except (ValueError, TypeError):
                    pass
            rows.append(row)
    return rows


def load_individual_runs(input_dir):
    """Load all individual run_*.csv files and merge."""
    rows = []
    pattern = os.path.join(input_dir, "run_*.csv")
    for filepath in sorted(glob.glob(pattern)):
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key in row:
                    if key in ("run_id", "timestamp", "map_name", "scenario", "solver",
                               "solver_mode", "scheduling_policy", "status"):
                        continue
                    try:
                        if "." in str(row[key]):
                            row[key] = float(row[key])
                        else:
                            row[key] = int(row[key])
                    except (ValueError, TypeError):
                        pass
                rows.append(row)
    return rows


def group_key(row, fields):
    """Create a hashable group key from specified fields."""
    return tuple(row.get(f, "") for f in fields)


def compute_stats(values):
    """Compute mean, std, min, max, median for a list of numeric values."""
    values = [v for v in values if v is not None and isinstance(v, (int, float))]
    if not values:
        return {"mean": 0, "std": 0, "min": 0, "max": 0, "median": 0, "count": 0}
    return {
        "mean": round(statistics.mean(values), 4),
        "std": round(statistics.stdev(values), 4) if len(values) > 1 else 0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "median": round(statistics.median(values), 4),
        "count": len(values),
    }


def aggregate_runs(rows):
    """
    Aggregate across seeds for each unique configuration.
    Group by: map_name, solver_mode, thread_count, agent_count, task_arrival_rate,
              visibility_radius_v, scheduling_policy
    """
    group_fields = [
        "map_name", "solver_mode", "thread_count", "agent_count",
        "task_arrival_rate", "visibility_radius_v", "scheduling_policy"
    ]
    
    metric_fields = [
        "total_runtime_ms", "solver_runtime_ms", "throughput",
        "deadline_satisfaction_rate", "avg_tardiness", "max_tardiness",
        "num_tasks_generated", "num_tasks_completed", "num_tasks_overdue",
        "num_groups", "avg_group_size", "max_group_solve_ms", "num_collisions",
    ]
    
    groups = defaultdict(list)
    for row in rows:
        key = group_key(row, group_fields)
        groups[key].append(row)
    
    aggregated = []
    for key, group_rows in sorted(groups.items()):
        agg_row = {}
        # Copy group fields
        for i, field in enumerate(group_fields):
            agg_row[field] = key[i]
        
        agg_row["num_seeds"] = len(group_rows)
        
        # Aggregate each metric
        for metric in metric_fields:
            values = [r.get(metric) for r in group_rows]
            stats = compute_stats(values)
            agg_row[f"{metric}_mean"] = stats["mean"]
            agg_row[f"{metric}_std"] = stats["std"]
            agg_row[f"{metric}_min"] = stats["min"]
            agg_row[f"{metric}_max"] = stats["max"]
        
        aggregated.append(agg_row)
    
    return aggregated


def compute_speedup_efficiency(aggregated):
    """
    For each parallel config, compute speedup and efficiency
    relative to the sequential baseline with the same (map, agents, rate, policy).
    """
    # Build lookup for sequential baselines
    seq_lookup = {}
    for row in aggregated:
        if row["solver_mode"] == "sequential":
            key = (row["map_name"], row["agent_count"], row["task_arrival_rate"],
                   row["scheduling_policy"])
            seq_lookup[key] = row["total_runtime_ms_mean"]
    
    for row in aggregated:
        if row["solver_mode"] == "parallel":
            key = (row["map_name"], row["agent_count"], row["task_arrival_rate"],
                   row["scheduling_policy"])
            seq_time = seq_lookup.get(key, None)
            threads = row["thread_count"]
            par_time = row["total_runtime_ms_mean"]
            
            if seq_time and par_time > 0:
                speedup = seq_time / par_time
                efficiency = speedup / threads if threads > 0 else 0
                row["speedup"] = round(speedup, 4)
                row["efficiency"] = round(efficiency, 4)
                row["seq_runtime_ms"] = round(seq_time, 2)
            else:
                row["speedup"] = 1.0
                row["efficiency"] = 1.0
                row["seq_runtime_ms"] = seq_time or 0
        else:
            row["speedup"] = 1.0
            row["efficiency"] = 1.0
            row["seq_runtime_ms"] = row["total_runtime_ms_mean"]
    
    return aggregated


def write_csv(rows, filepath):
    """Write list of dicts to CSV."""
    if not rows:
        print(f"  ⚠ No data to write to {filepath}")
        return
    fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ Wrote {len(rows)} rows to {filepath}")


def generate_speedup_table(aggregated, output_dir):
    """Generate a focused speedup table: agents × threads → speedup."""
    speedup_rows = []
    for row in aggregated:
        if row["solver_mode"] == "parallel":
            speedup_rows.append({
                "agent_count": row["agent_count"],
                "thread_count": row["thread_count"],
                "visibility_radius_v": row["visibility_radius_v"],
                "task_arrival_rate": row["task_arrival_rate"],
                "scheduling_policy": row["scheduling_policy"],
                "seq_runtime_ms": row["seq_runtime_ms"],
                "par_runtime_ms": row["total_runtime_ms_mean"],
                "speedup": row["speedup"],
                "efficiency": row["efficiency"],
                "throughput_improvement": round(
                    (row["throughput_mean"] / max(0.001, 
                     next((r["throughput_mean"] for r in aggregated 
                           if r["solver_mode"] == "sequential" 
                           and r["agent_count"] == row["agent_count"]
                           and r["task_arrival_rate"] == row["task_arrival_rate"]
                           and r["scheduling_policy"] == row["scheduling_policy"]),
                          row["throughput_mean"])) - 1) * 100, 2
                ),
            })
    
    write_csv(speedup_rows, os.path.join(output_dir, "speedup_table.csv"))


def generate_deadline_table(aggregated, output_dir):
    """Generate a focused deadline satisfaction comparison table."""
    deadline_rows = []
    for row in aggregated:
        deadline_rows.append({
            "solver_mode": row["solver_mode"],
            "thread_count": row["thread_count"],
            "agent_count": row["agent_count"],
            "task_arrival_rate": row["task_arrival_rate"],
            "scheduling_policy": row["scheduling_policy"],
            "deadline_satisfaction_rate": row["deadline_satisfaction_rate_mean"],
            "deadline_satisfaction_std": row["deadline_satisfaction_rate_std"],
            "avg_tardiness": row["avg_tardiness_mean"],
            "num_tasks_overdue": row["num_tasks_overdue_mean"],
        })
    
    write_csv(deadline_rows, os.path.join(output_dir, "deadline_table.csv"))


def main():
    parser = argparse.ArgumentParser(description="Aggregate experiment results across seeds")
    parser.add_argument("--input-dir", default="../results/raw", help="Directory with raw CSV files")
    parser.add_argument("--summary", default=None, help="Path to experiment_summary.csv (optional)")
    parser.add_argument("--output-dir", default="../results/aggregated", help="Output directory")
    args = parser.parse_args()
    
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Load data
    if args.summary and os.path.exists(args.summary):
        print(f"Loading summary from {args.summary}")
        rows = load_summary_csv(args.summary)
    else:
        summary_path = os.path.join(os.path.dirname(input_dir), "experiment_summary.csv")
        if os.path.exists(summary_path):
            print(f"Loading summary from {summary_path}")
            rows = load_summary_csv(summary_path)
        else:
            print(f"Loading individual run files from {input_dir}")
            rows = load_individual_runs(input_dir)
    
    print(f"Loaded {len(rows)} experiment runs")
    
    if not rows:
        print("ERROR: No data found. Run generate_stub_data.py first or check paths.")
        return
    
    # Aggregate
    print("\nAggregating across seeds...")
    aggregated = aggregate_runs(rows)
    print(f"  {len(aggregated)} unique configurations")
    
    # Compute speedup & efficiency
    print("Computing speedup and efficiency...")
    aggregated = compute_speedup_efficiency(aggregated)
    
    # Write outputs
    print("\nWriting aggregated tables...")
    write_csv(aggregated, os.path.join(output_dir, "aggregated_results.csv"))
    generate_speedup_table(aggregated, output_dir)
    generate_deadline_table(aggregated, output_dir)
    
    # Print quick summary
    parallel_rows = [r for r in aggregated if r["solver_mode"] == "parallel"]
    if parallel_rows:
        max_speedup = max(r["speedup"] for r in parallel_rows)
        avg_speedup = statistics.mean(r["speedup"] for r in parallel_rows)
        print(f"\n═══ Quick Summary ═══")
        print(f"  Max speedup:     {max_speedup:.2f}x")
        print(f"  Avg speedup:     {avg_speedup:.2f}x")
        
        best = max(parallel_rows, key=lambda r: r["speedup"])
        print(f"  Best config:     {best['agent_count']} agents, "
              f"{best['thread_count']} threads, vr={best['visibility_radius_v']}")
    
    print(f"\nAll outputs in: {output_dir}")


if __name__ == "__main__":
    main()
