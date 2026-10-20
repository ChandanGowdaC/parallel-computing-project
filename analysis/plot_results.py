#!/usr/bin/env python3
"""
plot_results.py — Generates all publication-quality figures for the GD-RHCR project.

Person D — Plotting & Reporting Pipeline.

Reads aggregated CSVs from results/aggregated/ and produces:
  1. Speedup vs. Thread Count (per agent count)
  2. Efficiency vs. Thread Count
  3. Throughput: Sequential vs. Parallel
  4. Deadline Satisfaction Rate vs. Task Arrival Rate
  5. Tardiness Distribution Comparison
  6. Runtime Breakdown (solver vs. overhead)
  7. Scalability: Runtime vs. Agent Count
  8. Literature Comparison Chart
  9. Scheduling Policy Comparison
  10. Heatmap: Speedup across agents × threads

Usage:
    python3 plot_results.py [--input-dir ../results/aggregated] [--output-dir ../results/figures]
"""

import os
import csv
import argparse
import math
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ─── Style Configuration ──────────────────────────────────────────
plt.rcParams.update({
    "figure.figsize": (10, 7),
    "figure.dpi": 150,
    "font.family": "serif",
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.labelsize": 13,
    "legend.fontsize": 10,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "lines.linewidth": 2,
    "lines.markersize": 8,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})

# Color palette
COLORS = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#4f46e5"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X"]


def load_csv(filepath):
    """Load a CSV file into a list of dicts with auto-casting."""
    rows = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in row:
                try:
                    if "." in str(row[key]):
                        row[key] = float(row[key])
                    else:
                        row[key] = int(row[key])
                except (ValueError, TypeError):
                    pass
            rows.append(row)
    return rows


def filter_rows(rows, **kwargs):
    """Filter rows matching all key=value pairs."""
    result = []
    for row in rows:
        match = True
        for k, v in kwargs.items():
            if row.get(k) != v:
                match = False
                break
        if match:
            result.append(row)
    return result


def savefig(fig, output_dir, name):
    path = os.path.join(output_dir, f"{name}.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {name}.png")


# ═══════════════════════════════════════════════════════════════════
# Plot 1: Speedup vs. Thread Count
# ═══════════════════════════════════════════════════════════════════
def plot_speedup_vs_threads(data, output_dir, rate=1.0, policy="FIFO", vr=10.0):
    """One line per agent count showing speedup vs thread count."""
    fig, ax = plt.subplots()
    
    parallel = [r for r in data if r["solver_mode"] == "parallel"
                and r["task_arrival_rate"] == rate
                and r.get("scheduling_policy", "FIFO") == policy
                and r.get("visibility_radius_v", 10.0) == vr]
    
    # Group by agent_count
    by_agents = defaultdict(list)
    for r in parallel:
        by_agents[r["agent_count"]].append(r)
    
    for idx, (agents, rows) in enumerate(sorted(by_agents.items())):
        rows.sort(key=lambda r: r["thread_count"])
        threads = [r["thread_count"] for r in rows]
        speedups = [r["speedup"] for r in rows]
        
        ax.plot(threads, speedups,
                color=COLORS[idx % len(COLORS)],
                marker=MARKERS[idx % len(MARKERS)],
                label=f"{agents} agents")
    
    # Ideal speedup line
    max_t = max(r["thread_count"] for r in parallel) if parallel else 16
    ideal = list(range(1, max_t + 1))
    ax.plot(ideal, ideal, "--", color="gray", alpha=0.5, label="Ideal (linear)")
    
    ax.set_xlabel("Number of Threads (p)")
    ax.set_ylabel("Speedup (T₁ / Tₚ)")
    ax.set_title(f"Speedup vs. Thread Count (λ={rate}, VR={vr})")
    ax.legend(loc="upper left")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    
    savefig(fig, output_dir, "speedup_vs_threads")


# ═══════════════════════════════════════════════════════════════════
# Plot 2: Efficiency vs. Thread Count
# ═══════════════════════════════════════════════════════════════════
def plot_efficiency_vs_threads(data, output_dir, rate=1.0, policy="FIFO", vr=10.0):
    """Efficiency = Speedup / p. Shows how well parallelism is utilized."""
    fig, ax = plt.subplots()
    
    parallel = [r for r in data if r["solver_mode"] == "parallel"
                and r["task_arrival_rate"] == rate
                and r.get("scheduling_policy", "FIFO") == policy
                and r.get("visibility_radius_v", 10.0) == vr]
    
    by_agents = defaultdict(list)
    for r in parallel:
        by_agents[r["agent_count"]].append(r)
    
    for idx, (agents, rows) in enumerate(sorted(by_agents.items())):
        rows.sort(key=lambda r: r["thread_count"])
        threads = [r["thread_count"] for r in rows]
        efficiencies = [r["efficiency"] for r in rows]
        
        ax.plot(threads, efficiencies,
                color=COLORS[idx % len(COLORS)],
                marker=MARKERS[idx % len(MARKERS)],
                label=f"{agents} agents")
    
    # Ideal efficiency line
    ax.axhline(y=1.0, linestyle="--", color="gray", alpha=0.5, label="Ideal (100%)")
    
    ax.set_xlabel("Number of Threads (p)")
    ax.set_ylabel("Efficiency (Speedup / p)")
    ax.set_title(f"Parallel Efficiency vs. Thread Count (λ={rate}, VR={vr})")
    ax.legend()
    ax.set_ylim(0, 1.2)
    
    savefig(fig, output_dir, "efficiency_vs_threads")


# ═══════════════════════════════════════════════════════════════════
# Plot 3: Throughput Comparison (Sequential vs. Parallel)
# ═══════════════════════════════════════════════════════════════════
def plot_throughput_comparison(data, output_dir, rate=1.0, policy="FIFO"):
    """Bar chart comparing throughput: sequential vs. parallel at different agent counts."""
    fig, ax = plt.subplots()
    
    seq = sorted(filter_rows(data, solver_mode="sequential", task_arrival_rate=rate,
                             scheduling_policy=policy),
                 key=lambda r: r["agent_count"])
    
    # Get best parallel (highest thread count)
    par_all = filter_rows(data, solver_mode="parallel", task_arrival_rate=rate,
                          scheduling_policy=policy)
    
    best_par = {}
    for r in par_all:
        agents = r["agent_count"]
        if agents not in best_par or r["thread_count"] > best_par[agents]["thread_count"]:
            best_par[agents] = r
    par = sorted(best_par.values(), key=lambda r: r["agent_count"])
    
    if not seq or not par:
        return
    
    agents_list = [r["agent_count"] for r in seq]
    x = np.arange(len(agents_list))
    width = 0.35
    
    seq_tp = [r["throughput_mean"] for r in seq]
    par_tp = [best_par.get(a, {}).get("throughput_mean", 0) for a in agents_list]
    
    bars1 = ax.bar(x - width/2, seq_tp, width, label="Sequential", color=COLORS[0], alpha=0.85)
    bars2 = ax.bar(x + width/2, par_tp, width, label="Parallel (best)", color=COLORS[2], alpha=0.85)
    
    ax.set_xlabel("Agent Count")
    ax.set_ylabel("Throughput (tasks/timestep)")
    ax.set_title(f"Throughput: Sequential vs. Parallel (λ={rate})")
    ax.set_xticks(x)
    ax.set_xticklabels(agents_list)
    ax.legend()
    
    # Add improvement percentage labels
    for i, (s, p) in enumerate(zip(seq_tp, par_tp)):
        if s > 0:
            improvement = ((p - s) / s) * 100
            ax.annotate(f"+{improvement:.0f}%",
                       xy=(x[i] + width/2, p),
                       ha="center", va="bottom", fontsize=9, color=COLORS[2])
    
    savefig(fig, output_dir, "throughput_comparison")


# ═══════════════════════════════════════════════════════════════════
# Plot 4: Deadline Satisfaction vs. Arrival Rate
# ═══════════════════════════════════════════════════════════════════
def plot_deadline_vs_rate(data, output_dir, agents=200, policy="FIFO"):
    """Deadline satisfaction rate vs. task arrival rate for different thread configs."""
    fig, ax = plt.subplots()
    
    seq = sorted(filter_rows(data, solver_mode="sequential", agent_count=agents,
                             scheduling_policy=policy),
                 key=lambda r: r["task_arrival_rate"])
    
    if seq:
        rates = [r["task_arrival_rate"] for r in seq]
        sats = [r["deadline_satisfaction_rate_mean"] for r in seq]
        ax.plot(rates, sats, color=COLORS[0], marker=MARKERS[0],
                label="Sequential", linewidth=2.5)
    
    par = filter_rows(data, solver_mode="parallel", agent_count=agents,
                      scheduling_policy=policy)
    
    by_threads = defaultdict(list)
    for r in par:
        by_threads[r["thread_count"]].append(r)
    
    for idx, (threads, rows) in enumerate(sorted(by_threads.items())):
        # Pick one visibility radius
        best_vr = defaultdict(list)
        for r in rows:
            best_vr[r["task_arrival_rate"]].append(r)
        
        rates = []
        sats = []
        for rate_val in sorted(best_vr.keys()):
            best = max(best_vr[rate_val], key=lambda r: r["deadline_satisfaction_rate_mean"])
            rates.append(rate_val)
            sats.append(best["deadline_satisfaction_rate_mean"])
        
        ax.plot(rates, sats,
                color=COLORS[(idx + 1) % len(COLORS)],
                marker=MARKERS[(idx + 1) % len(MARKERS)],
                label=f"Parallel ({threads} threads)")
    
    ax.set_xlabel("Task Arrival Rate (λ)")
    ax.set_ylabel("Deadline Satisfaction Rate")
    ax.set_title(f"Deadline Satisfaction vs. Arrival Rate ({agents} agents)")
    ax.legend()
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(1.0))
    
    savefig(fig, output_dir, "deadline_vs_arrival_rate")


# ═══════════════════════════════════════════════════════════════════
# Plot 5: Tardiness Distribution
# ═══════════════════════════════════════════════════════════════════
def plot_tardiness_comparison(data, output_dir, agents=400, rate=2.0, policy="FIFO"):
    """Bar chart of average tardiness: sequential vs. parallel configurations."""
    fig, ax = plt.subplots()
    
    configs = []
    tardiness_vals = []
    colors = []
    
    seq = filter_rows(data, solver_mode="sequential", agent_count=agents,
                      task_arrival_rate=rate, scheduling_policy=policy)
    if seq:
        configs.append("Sequential")
        tardiness_vals.append(seq[0]["avg_tardiness_mean"])
        colors.append(COLORS[0])
    
    par = filter_rows(data, solver_mode="parallel", agent_count=agents,
                      task_arrival_rate=rate, scheduling_policy=policy)
    par.sort(key=lambda r: r["thread_count"])
    
    for r in par:
        vr = r.get("visibility_radius_v", "?")
        configs.append(f"Par t={r['thread_count']}\nvr={vr}")
        tardiness_vals.append(r["avg_tardiness_mean"])
        colors.append(COLORS[2])
    
    if not configs:
        return
    
    x = np.arange(len(configs))
    bars = ax.bar(x, tardiness_vals, color=colors, alpha=0.85)
    
    ax.set_xlabel("Configuration")
    ax.set_ylabel("Average Tardiness (timesteps)")
    ax.set_title(f"Average Tardiness ({agents} agents, λ={rate})")
    ax.set_xticks(x)
    ax.set_xticklabels(configs, fontsize=9)
    
    for bar, val in zip(bars, tardiness_vals):
        ax.annotate(f"{val:.1f}", xy=(bar.get_x() + bar.get_width()/2, val),
                   ha="center", va="bottom", fontsize=9)
    
    savefig(fig, output_dir, "tardiness_comparison")


# ═══════════════════════════════════════════════════════════════════
# Plot 6: Runtime vs. Agent Count (Scalability)
# ═══════════════════════════════════════════════════════════════════
def plot_runtime_scalability(data, output_dir, rate=1.0, policy="FIFO"):
    """Runtime vs. agent count for sequential and parallel configs."""
    fig, ax = plt.subplots()
    
    seq = sorted(filter_rows(data, solver_mode="sequential", task_arrival_rate=rate,
                             scheduling_policy=policy),
                 key=lambda r: r["agent_count"])
    
    if seq:
        agents = [r["agent_count"] for r in seq]
        runtimes = [r["total_runtime_ms_mean"] for r in seq]
        ax.plot(agents, runtimes, color=COLORS[0], marker=MARKERS[0],
                label="Sequential", linewidth=2.5)
    
    par = filter_rows(data, solver_mode="parallel", task_arrival_rate=rate,
                      scheduling_policy=policy)
    
    by_threads = defaultdict(list)
    for r in par:
        by_threads[r["thread_count"]].append(r)
    
    for idx, (threads, rows) in enumerate(sorted(by_threads.items())):
        # Average across visibility radii
        by_agents = defaultdict(list)
        for r in rows:
            by_agents[r["agent_count"]].append(r["total_runtime_ms_mean"])
        
        agents = sorted(by_agents.keys())
        runtimes = [min(by_agents[a]) for a in agents]  # best vr for each
        
        ax.plot(agents, runtimes,
                color=COLORS[(idx + 1) % len(COLORS)],
                marker=MARKERS[(idx + 1) % len(MARKERS)],
                label=f"Parallel ({threads} threads)")
    
    ax.set_xlabel("Agent Count")
    ax.set_ylabel("Total Runtime (ms)")
    ax.set_title(f"Runtime Scalability (λ={rate})")
    ax.legend()
    ax.set_yscale("log")
    
    savefig(fig, output_dir, "runtime_scalability")


# ═══════════════════════════════════════════════════════════════════
# Plot 7: Scheduling Policy Comparison
# ═══════════════════════════════════════════════════════════════════
def plot_policy_comparison(data, output_dir, agents=200, rate=2.0):
    """Compare scheduling policies on deadline satisfaction."""
    fig, ax = plt.subplots()
    
    policies = set()
    for r in data:
        if "scheduling_policy" in r:
            policies.add(r["scheduling_policy"])
    
    if len(policies) <= 1:
        return
    
    policies = sorted(policies)
    x = np.arange(len(policies))
    width = 0.35
    
    seq_sats = []
    par_sats = []
    
    for policy in policies:
        seq = filter_rows(data, solver_mode="sequential", agent_count=agents,
                          task_arrival_rate=rate, scheduling_policy=policy)
        seq_sats.append(seq[0]["deadline_satisfaction_rate_mean"] if seq else 0)
        
        par = filter_rows(data, solver_mode="parallel", agent_count=agents,
                          task_arrival_rate=rate, scheduling_policy=policy)
        if par:
            best = max(par, key=lambda r: r["deadline_satisfaction_rate_mean"])
            par_sats.append(best["deadline_satisfaction_rate_mean"])
        else:
            par_sats.append(0)
    
    ax.bar(x - width/2, seq_sats, width, label="Sequential", color=COLORS[0], alpha=0.85)
    ax.bar(x + width/2, par_sats, width, label="Parallel (best)", color=COLORS[2], alpha=0.85)
    
    ax.set_xlabel("Scheduling Policy")
    ax.set_ylabel("Deadline Satisfaction Rate")
    ax.set_title(f"Policy Comparison ({agents} agents, λ={rate})")
    ax.set_xticks(x)
    ax.set_xticklabels(policies)
    ax.legend()
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(1.0))
    ax.set_ylim(0, 1.1)
    
    savefig(fig, output_dir, "policy_comparison")


# ═══════════════════════════════════════════════════════════════════
# Plot 8: Speedup Heatmap (Agents × Threads)
# ═══════════════════════════════════════════════════════════════════
def plot_speedup_heatmap(data, output_dir, rate=1.0, policy="FIFO", vr=10.0):
    """Heatmap of speedup: rows = agent counts, cols = thread counts."""
    parallel = filter_rows(data, solver_mode="parallel", task_arrival_rate=rate,
                           scheduling_policy=policy, visibility_radius_v=vr)
    
    if not parallel:
        return
    
    agents_set = sorted(set(r["agent_count"] for r in parallel))
    threads_set = sorted(set(r["thread_count"] for r in parallel))
    
    heatmap = np.zeros((len(agents_set), len(threads_set)))
    
    for r in parallel:
        i = agents_set.index(r["agent_count"])
        j = threads_set.index(r["thread_count"])
        heatmap[i, j] = r["speedup"]
    
    fig, ax = plt.subplots()
    im = ax.imshow(heatmap, cmap="YlOrRd", aspect="auto", interpolation="nearest")
    
    ax.set_xticks(range(len(threads_set)))
    ax.set_xticklabels(threads_set)
    ax.set_yticks(range(len(agents_set)))
    ax.set_yticklabels(agents_set)
    
    ax.set_xlabel("Thread Count")
    ax.set_ylabel("Agent Count")
    ax.set_title(f"Speedup Heatmap (λ={rate}, VR={vr})")
    
    # Annotate cells
    for i in range(len(agents_set)):
        for j in range(len(threads_set)):
            val = heatmap[i, j]
            color = "white" if val > (heatmap.max() * 0.65) else "black"
            ax.text(j, i, f"{val:.2f}x", ha="center", va="center", color=color, fontsize=10)
    
    fig.colorbar(im, ax=ax, label="Speedup")
    
    savefig(fig, output_dir, "speedup_heatmap")


# ═══════════════════════════════════════════════════════════════════
# Plot 9: Literature Comparison
# ═══════════════════════════════════════════════════════════════════
def plot_literature_comparison(data, output_dir):
    """Compare our results with published numbers from GD-RHCR and CPLNS papers."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # ── Panel A: Throughput improvement comparison ──
    methods = ["GD-RHCR\n(Paper)", "CPLNS\n(Paper)", "Our\nImplementation"]
    paper_throughput_improvement = [57.7, 0, 0]  # GD-RHCR claimed 57.7%
    paper_speedup = [24.9, 21.95, 0]  # per-plan computation speedup
    
    # Get our best result
    parallel = [r for r in data if r["solver_mode"] == "parallel"]
    if parallel:
        best = max(parallel, key=lambda r: r.get("speedup", 0))
        our_speedup = best.get("speedup", 1.0)
        
        seq_tp = [r for r in data if r["solver_mode"] == "sequential"
                  and r["agent_count"] == best["agent_count"]
                  and r["task_arrival_rate"] == best["task_arrival_rate"]]
        if seq_tp:
            our_tp_improvement = ((best["throughput_mean"] / seq_tp[0]["throughput_mean"]) - 1) * 100
        else:
            our_tp_improvement = 0
        
        paper_throughput_improvement[2] = our_tp_improvement
        paper_speedup[2] = our_speedup
    
    colors_bar = [COLORS[3], COLORS[4], COLORS[2]]
    
    ax1.bar(methods, paper_throughput_improvement, color=colors_bar, alpha=0.85)
    ax1.set_ylabel("Throughput Improvement (%)")
    ax1.set_title("Throughput Improvement vs. Vanilla RHCR")
    for i, v in enumerate(paper_throughput_improvement):
        if v > 0:
            ax1.text(i, v + 1, f"{v:.1f}%", ha="center", va="bottom", fontweight="bold")
    
    # ── Panel B: Computation speedup comparison ──
    ax2.bar(methods, paper_speedup, color=colors_bar, alpha=0.85)
    ax2.set_ylabel("Per-Plan Computation Speedup (×)")
    ax2.set_title("Computation Cost Reduction")
    for i, v in enumerate(paper_speedup):
        if v > 0:
            ax2.text(i, v + 0.3, f"{v:.1f}×", ha="center", va="bottom", fontweight="bold")
    
    fig.suptitle("Comparison with Published Results", fontsize=15, fontweight="bold")
    plt.tight_layout()
    
    savefig(fig, output_dir, "literature_comparison")


# ═══════════════════════════════════════════════════════════════════
# Plot 10: Visibility Radius Impact
# ═══════════════════════════════════════════════════════════════════
def plot_visibility_radius_impact(data, output_dir, agents=400, rate=1.0, policy="FIFO"):
    """Show how visibility radius affects speedup and group count."""
    par = filter_rows(data, solver_mode="parallel", agent_count=agents,
                      task_arrival_rate=rate, scheduling_policy=policy)
    
    if not par:
        return
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    by_threads = defaultdict(list)
    for r in par:
        by_threads[r["thread_count"]].append(r)
    
    for idx, (threads, rows) in enumerate(sorted(by_threads.items())):
        rows.sort(key=lambda r: r.get("visibility_radius_v", 0))
        vrs = [r.get("visibility_radius_v", 0) for r in rows]
        speedups = [r["speedup"] for r in rows]
        groups = [r.get("num_groups_mean", r.get("num_groups", 1)) for r in rows]
        
        ax1.plot(vrs, speedups,
                 color=COLORS[idx % len(COLORS)],
                 marker=MARKERS[idx % len(MARKERS)],
                 label=f"{threads} threads")
        
        ax2.plot(vrs, groups,
                 color=COLORS[idx % len(COLORS)],
                 marker=MARKERS[idx % len(MARKERS)],
                 label=f"{threads} threads")
    
    ax1.set_xlabel("Visibility Radius (V)")
    ax1.set_ylabel("Speedup")
    ax1.set_title("Speedup vs. Visibility Radius")
    ax1.legend()
    
    ax2.set_xlabel("Visibility Radius (V)")
    ax2.set_ylabel("Number of Groups")
    ax2.set_title("Group Count vs. Visibility Radius")
    ax2.legend()
    
    fig.suptitle(f"Impact of Visibility Radius ({agents} agents, λ={rate})",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    
    savefig(fig, output_dir, "visibility_radius_impact")


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="Generate all experiment figures")
    parser.add_argument("--input-dir", default="../results/aggregated",
                       help="Directory with aggregated CSV files")
    parser.add_argument("--output-dir", default="../results/figures",
                       help="Directory to save generated figures")
    parser.add_argument("--rate", type=float, default=1.0,
                       help="Default arrival rate for single-rate plots")
    parser.add_argument("--agents", type=int, default=200,
                       help="Default agent count for single-agent plots")
    parser.add_argument("--policy", default="FIFO",
                       help="Default scheduling policy for plots")
    args = parser.parse_args()
    
    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Load aggregated data
    agg_path = os.path.join(input_dir, "aggregated_results.csv")
    if not os.path.exists(agg_path):
        print(f"ERROR: {agg_path} not found. Run aggregate_results.py first.")
        return
    
    print(f"Loading data from {agg_path}")
    data = load_csv(agg_path)
    print(f"Loaded {len(data)} aggregated configurations\n")
    
    print("Generating figures...")
    
    # Core parallel computing plots
    plot_speedup_vs_threads(data, output_dir, rate=args.rate, policy=args.policy)
    plot_efficiency_vs_threads(data, output_dir, rate=args.rate, policy=args.policy)
    plot_throughput_comparison(data, output_dir, rate=args.rate, policy=args.policy)
    plot_runtime_scalability(data, output_dir, rate=args.rate, policy=args.policy)
    plot_speedup_heatmap(data, output_dir, rate=args.rate, policy=args.policy)
    
    # Deadline-aware plots
    plot_deadline_vs_rate(data, output_dir, agents=args.agents, policy=args.policy)
    plot_tardiness_comparison(data, output_dir, agents=max(400, args.agents), rate=2.0,
                             policy=args.policy)
    plot_policy_comparison(data, output_dir, agents=args.agents, rate=2.0)
    
    # GD-RHCR specific
    plot_visibility_radius_impact(data, output_dir, agents=max(400, args.agents),
                                 rate=args.rate, policy=args.policy)
    
    # Literature comparison
    plot_literature_comparison(data, output_dir)
    
    print(f"\nAll figures saved to: {output_dir}")


if __name__ == "__main__":
    main()
