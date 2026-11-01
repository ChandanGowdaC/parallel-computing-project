#!/usr/bin/env python3
"""
plot_publication_figures.py — Generates publication-ready figures (PNG + PDF)
for the final evaluation report.
"""

import os
os.environ["MPLCONFIGDIR"] = "/tmp/mpl"
import sys
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")
FIG_DIR = os.path.join(ROOT_DIR, "results", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.titlesize": 14,
    "lines.linewidth": 2,
    "lines.markersize": 7,
})


def plot_fig1_speedup_vs_p():
    """Fig 1: Speedup vs p with P/E core boundary at p=5."""
    summary_file = os.path.join(AGG_DIR, "reporting_scaling_summary.csv")
    if not os.path.isfile(summary_file):
        return

    rows = []
    with open(summary_file) as f:
        rows = list(csv.DictReader(f))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)

    for ax_idx, wl in enumerate(["uniform", "zoned"]):
        ax = axes[ax_idx]
        title_wl = "Uniform Workload" if wl == "uniform" else "Zoned Workload (Local Trips)"
        ax.set_title(f"{title_wl} (N=400, V*=1)")

        # Filter N=400, V=1
        cur = [r for r in rows if r["agents"] == "400" and r["workload"] == wl and r["V"] == "1"]
        if not cur:
            continue

        cur = sorted(cur, key=lambda x: int(x["p"]))
        p_vals = [int(r["p"]) for r in cur]
        s_tot = [float(r["S_total_med"]) for r in cur]
        s_tot_l = [float(r["S_total_ci_low"]) for r in cur]
        s_tot_h = [float(r["S_total_ci_high"]) for r in cur]

        s_th = [float(r["S_thread_med"]) for r in cur]
        s_th_l = [float(r["S_thread_ci_low"]) for r in cur]
        s_th_h = [float(r["S_thread_ci_high"]) for r in cur]

        s_alg = float(cur[0]["S_alg_med"])

        # Max parallelism bound W/S
        ws_bound = 1.55 if wl == "uniform" else 1.60

        # Plot curves
        ax.errorbar(p_vals, s_tot, yerr=[np.array(s_tot)-np.array(s_tot_l), np.array(s_tot_h)-np.array(s_tot)],
                    label=r"$S_{\mathrm{total}} = T(V_0)/T(V_2)$ (Overall)", color="#1f77b4", marker="o", capsize=3)
        ax.errorbar(p_vals, s_th, yerr=[np.array(s_th)-np.array(s_th_l), np.array(s_th_h)-np.array(s_th)],
                    label=r"$S_{\mathrm{thread}} = T(V_1)/T(V_2)$ (Parallel)", color="#2ca02c", marker="s", capsize=3)
        ax.axhline(s_alg, color="#ff7f0e", linestyle="--", label=rf"$S_{{\mathrm{{alg}}}} = T(V_0)/T(V_1) = {s_alg:.2f}\times$")
        ax.axhline(ws_bound, color="purple", linestyle="-.", label=rf"Max Parallelism $W/S \approx {ws_bound:.2f}\times$")

        # P-Core / E-Core boundary
        ax.axvline(5, color="red", linestyle=":", alpha=0.8, linewidth=1.8)
        ax.text(5.1, ax.get_ylim()[0] + 0.15 * (ax.get_ylim()[1] - ax.get_ylim()[0]) if ax.get_ylim()[1] > 1 else 1.2,
                "M3 Pro P-Core Cap (p=5)\nE-Core Spillover (Hypothesis)", color="red", fontsize=9, fontweight="bold")

        ax.set_xlabel("Worker Threads (p)")
        if ax_idx == 0:
            ax.set_ylabel("Speed Ratio (vs Baseline)")
        ax.set_xticks([1, 2, 4, 5, 8, 11])
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig1_speedup_vs_p_pe_boundary.png"), dpi=300)
    plt.savefig(os.path.join(FIG_DIR, "fig1_speedup_vs_p_pe_boundary.pdf"))
    plt.close()
    print("Saved fig1_speedup_vs_p_pe_boundary.png/.pdf")


def plot_fig2_work_span_bounds():
    """Fig 2: Graham-Brent Bounds vs Measured."""
    # Data from Step A reconciled table
    configs = ["Uni V=2 p=4", "Uni V=2 p=8", "Uni V=3 p=4", "Uni V=3 p=8",
               "Zon V=2 p=4", "Zon V=2 p=8", "Zon V=3 p=4", "Zon V=3 p=8"]
    t_low = [3882.37, 4344.25, 5759.46, 6257.17, 2730.18, 3963.81, 3426.72, 4671.08]
    t_meas = [4065.90, 4458.82, 5909.01, 6309.15, 2864.22, 4036.55, 3530.31, 4688.20]
    t_up = [4555.69, 5179.09, 6264.04, 6997.56, 4025.49, 5957.41, 4887.91, 6672.02]

    x = np.arange(len(configs))
    fig, ax = plt.subplots(figsize=(11, 5))

    ax.plot(x, t_low, label=r"Lower Bound $T_{\mathrm{low}} = T_{\mathrm{serial}} + \max(W/p, S)$",
            color="#2ca02c", linestyle="--", marker="v")
    ax.plot(x, t_meas, label=r"Measured Planning Wall Time $T_{\mathrm{meas}}$",
            color="#1f77b4", linewidth=2.5, marker="o")
    ax.plot(x, t_up, label=r"Brent Upper Bound $T_{\mathrm{up}} = T_{\mathrm{serial}} + (W-S)/p + S$",
            color="#d62728", linestyle="--", marker="^")
    ax.fill_between(x, t_low, t_up, color="#2ca02c", alpha=0.15, label="Feasible Analytical Region")

    ax.set_xticks(x)
    ax.set_xticklabels(configs, rotation=25, ha="right")
    ax.set_ylabel("Planning Time per Run (ms)")
    ax.set_title("Graham-Brent Analytical Bounds vs Measured Planning Latency (N=400, T_sim=250)")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig2_work_span_bounds.png"), dpi=300)
    plt.savefig(os.path.join(FIG_DIR, "fig2_work_span_bounds.pdf"))
    plt.close()
    print("Saved fig2_work_span_bounds.png/.pdf")


def plot_fig3_karp_flatt():
    """Fig 3: Karp-Flatt Serial Fraction vs Threads."""
    fig, ax = plt.subplots(figsize=(7, 4.5))

    p = np.array([4, 8])
    # Values from Step A Table 2
    e_uni_v2 = [0.627, 0.760]
    e_uni_v3 = [0.732, 0.832]
    e_zon_v2 = [0.608, 0.994]
    e_zon_v3 = [0.659, 0.986]

    ax.plot(p, e_uni_v2, marker="o", label="Uniform (V=2)", color="#1f77b4")
    ax.plot(p, e_uni_v3, marker="s", label="Uniform (V=3)", color="#aec7e8", linestyle="--")
    ax.plot(p, e_zon_v2, marker="^", label="Zoned (V=2)", color="#2ca02c")
    ax.plot(p, e_zon_v3, marker="d", label="Zoned (V=3)", color="#98df8a", linestyle="--")

    ax.set_xlabel("Worker Threads (p)")
    ax.set_ylabel("Karp-Flatt Serial Fraction e(p)")
    ax.set_title("Empirical Karp-Flatt Metric: Scaling Saturation Mechanism")
    ax.set_xticks([4, 8])
    ax.set_ylim(0.4, 1.05)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower right")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig3_karp_flatt_serial_fraction.png"), dpi=300)
    plt.savefig(os.path.join(FIG_DIR, "fig3_karp_flatt_serial_fraction.pdf"))
    plt.close()
    print("Saved fig3_karp_flatt_serial_fraction.png/.pdf")


def plot_fig4_density_regime_map():
    """Fig 4: Density Regime Map across Sorting, KIVA Uniform, KIVA Zoned."""
    fig, ax = plt.subplots(figsize=(8, 5))

    # Sorting Center (Sparse)
    densities_sorting = [1.2, 2.4, 4.7, 9.4]
    speedup_sorting = [3.02, 3.81, 2.10, 0.75]
    ax.plot(densities_sorting, speedup_sorting, marker="o", color="#2ca02c",
            label="Sorting Center (Open floor, V=6, p=4)", linewidth=2.5)

    # KIVA Warehouse (Dense, 31% nominal density)
    # At N=400: nominal density 31.3%
    ax.scatter([31.3], [3.21], color="#1f77b4", marker="s", s=120, label="KIVA Tiled Uniform (N=400, V*=1, p=4)")
    ax.scatter([31.3], [5.07], color="#9467bd", marker="^", s=140, label="KIVA Tiled Zoned (N=400, V*=1, p=4)")

    # Mark percolation threshold
    ax.axvspan(0, 5.0, color="#2ca02c", alpha=0.12, label="Sparse Non-Percolating Regime (Density <= 5%)")
    ax.axvspan(5.0, 35.0, color="#d62728", alpha=0.08, label="Percolation Barrier (Density > 5%)")
    ax.axvline(5.0, color="#d62728", linestyle=":", linewidth=2)
    ax.text(5.2, 4.5, "Percolation Threshold (~5%)\nGiant Component Forms", color="#d62728", fontsize=9, fontweight="bold")

    ax.set_xlabel("Warehouse Floor Density (% Walkable Cells Occupied)")
    ax.set_ylabel("Total System Speedup S_total vs Vanilla RHCR")
    ax.set_title("Empirical Regime Map: Speedup vs Agent Density")
    ax.set_ylim(0.5, 5.5)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig4_density_regime_map.png"), dpi=300)
    plt.savefig(os.path.join(FIG_DIR, "fig4_density_regime_map.pdf"))
    plt.close()
    print("Saved fig4_density_regime_map.png/.pdf")


def plot_fig5_constant_density_scaling_N():
    """Fig 5: Constant-density scaling across N in {100, 400, 800}."""
    summary_file = os.path.join(AGG_DIR, "reporting_scaling_summary.csv")
    if not os.path.isfile(summary_file):
        return

    rows = []
    with open(summary_file) as f:
        rows = list(csv.DictReader(f))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)

    for ax_idx, wl in enumerate(["uniform", "zoned"]):
        ax = axes[ax_idx]
        title_wl = "Uniform Workload" if wl == "uniform" else "Zoned Workload"
        ax.set_title(f"Constant-Density Scaling: {title_wl} (V*=1, p=4)")

        # Filter p=4 and p=8, V=1
        cur = [r for r in rows if r["workload"] == wl and r["V"] == "1" and r["p"] == "4"]
        cur_p8 = [r for r in rows if r["workload"] == wl and r["V"] == "1" and r["p"] == "8"]
        if not cur:
            continue

        cur = sorted(cur, key=lambda x: int(x["agents"]))
        cur_p8 = sorted(cur_p8, key=lambda x: int(x["agents"])) if cur_p8 else []

        n_vals = [int(r["agents"]) for r in cur]
        s_tot = [float(r["S_total_med"]) for r in cur]
        s_tot_l = [float(r["S_total_ci_low"]) for r in cur]
        s_tot_h = [float(r["S_total_ci_high"]) for r in cur]

        s_alg = [float(r["S_alg_med"]) for r in cur]
        s_alg_l = [float(r["S_alg_ci_low"]) for r in cur]
        s_alg_h = [float(r["S_alg_ci_high"]) for r in cur]

        s_th = [float(r["S_thread_med"]) for r in cur]
        s_th_l = [float(r["S_thread_ci_low"]) for r in cur]
        s_th_h = [float(r["S_thread_ci_high"]) for r in cur]

        ax.errorbar(n_vals, s_tot, yerr=[np.array(s_tot)-np.array(s_tot_l), np.array(s_tot_h)-np.array(s_tot)],
                    label=r"$S_{\mathrm{total}} = T(V_0)/T(V_2)$ (p=4)", color="#1f77b4", marker="o", capsize=3)

        if cur_p8:
            s_tot_8 = [float(r["S_total_med"]) for r in cur_p8]
            ax.plot(n_vals, s_tot_8, label=r"$S_{\mathrm{total}}$ (p=8, E-core)", color="#9467bd", marker="d", linestyle=":")

        ax.errorbar(n_vals, s_alg, yerr=[np.array(s_alg)-np.array(s_alg_l), np.array(s_alg_h)-np.array(s_alg)],
                    label=r"$S_{\mathrm{alg}} = T(V_0)/T(V_1)$ (Decomp)", color="#ff7f0e", marker="s", capsize=3)
        ax.errorbar(n_vals, s_th, yerr=[np.array(s_th)-np.array(s_th_l), np.array(s_th_h)-np.array(s_th)],
                    label=r"$S_{\mathrm{thread}} = T(V_1)/T(V_2)$ (Parallel p=4)", color="#2ca02c", marker="^", capsize=3)

        ax.set_xlabel("Number of Agents (N)")
        if ax_idx == 0:
            ax.set_ylabel("Speed Ratio (vs Baseline)")
        ax.set_xticks([100, 400, 800])
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig5_constant_density_scaling_N.png"), dpi=300)
    plt.savefig(os.path.join(FIG_DIR, "fig5_constant_density_scaling_N.pdf"))
    plt.close()
    print("Saved fig5_constant_density_scaling_N.png/.pdf")


def plot_fig6_deadline_arrival_rate_sweep():
    """Fig 6: Deadline Satisfaction % and Tardiness vs Arrival Rate Lambda."""
    summary_file = os.path.join(AGG_DIR, "deadline_sweep_summary.csv")
    if not os.path.isfile(summary_file):
        return

    rows = []
    with open(summary_file) as f:
        rows = list(csv.DictReader(f))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Panel 1: Satisfaction vs lambda at tight tau = 12ms
    ax1 = axes[0]
    ax1.set_title(r"Deadline Satisfaction vs Arrival Rate ($\tau = 12\,\mathrm{ms}$, Zoned)")
    for var, color, marker in [("V0", "#d62728", "o"), ("V1", "#ff7f0e", "s"), ("V2", "#2ca02c", "^")]:
        cur = [r for r in rows if r["workload"] == "zoned" and r["tau_ms"] == "12" and r["variant"] == var]
        if not cur:
            continue
        cur = sorted(cur, key=lambda x: float(x["arrival_rate"]))
        lams = [float(r["arrival_rate"]) for r in cur]
        sat = [float(r["deadline_satisfaction_med"]) for r in cur]
        sat_l = [float(r["deadline_satisfaction_ci_low"]) for r in cur]
        sat_h = [float(r["deadline_satisfaction_ci_high"]) for r in cur]
        lbl = f"{var} (Centralized)" if var == "V0" else (f"{var} (GD-RHCR 1-th)" if var == "V1" else f"{var} (GD-RHCR 4-th)")
        ax1.errorbar(lams, sat, yerr=[np.array(sat)-np.array(sat_l), np.array(sat_h)-np.array(sat)],
                     label=lbl, color=color, marker=marker, capsize=3)

    ax1.set_xlabel(r"Task Arrival Rate $\lambda$ (tasks/step)")
    ax1.set_ylabel("Deadline Satisfaction Rate (%)")
    ax1.set_ylim(-5, 105)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="lower left")

    # Panel 2: Average Tardiness vs lambda
    ax2 = axes[1]
    ax2.set_title(r"Average Task Tardiness vs Arrival Rate ($\tau = 12\,\mathrm{ms}$, Zoned)")
    for var, color, marker in [("V0", "#d62728", "o"), ("V1", "#ff7f0e", "s"), ("V2", "#2ca02c", "^")]:
        cur = [r for r in rows if r["workload"] == "zoned" and r["tau_ms"] == "12" and r["variant"] == var]
        if not cur:
            continue
        cur = sorted(cur, key=lambda x: float(x["arrival_rate"]))
        lams = [float(r["arrival_rate"]) for r in cur]
        tard = [float(r["avg_tardiness_med"]) for r in cur]
        tard_l = [float(r["avg_tardiness_ci_low"]) for r in cur]
        tard_h = [float(r["avg_tardiness_ci_high"]) for r in cur]
        lbl = f"{var} (Centralized)" if var == "V0" else (f"{var} (GD-RHCR 1-th)" if var == "V1" else f"{var} (GD-RHCR 4-th)")
        ax2.errorbar(lams, tard, yerr=[np.array(tard)-np.array(tard_l), np.array(tard_h)-np.array(tard)],
                     label=lbl, color=color, marker=marker, capsize=3)

    ax2.set_xlabel(r"Task Arrival Rate $\lambda$ (tasks/step)")
    ax2.set_ylabel("Average Tardiness (timesteps)")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig6_deadline_arrival_rate_sweep.png"), dpi=300)
    plt.savefig(os.path.join(FIG_DIR, "fig6_deadline_arrival_rate_sweep.pdf"))
    plt.close()
    print("Saved fig6_deadline_arrival_rate_sweep.png/.pdf")


def plot_fig7_policy_comparison():
    """Fig 7: Policy Comparison (FIFO vs EDF vs DEADLINE_AWARE)."""
    summary_file = os.path.join(AGG_DIR, "deadline_policy_summary.csv")
    if not os.path.isfile(summary_file):
        return

    rows = []
    with open(summary_file) as f:
        rows = list(csv.DictReader(f))

    fig, ax = plt.subplots(figsize=(8, 5))
    policies = ["FIFO", "EDF", "DEADLINE_AWARE"]
    colors = ["#1f77b4", "#2ca02c", "#ff7f0e"]

    for pol, col in zip(policies, colors):
        cur = [r for r in rows if r["policy"] == pol]
        if not cur:
            continue
        cur = sorted(cur, key=lambda x: float(x["arrival_rate"]))
        lams = [float(r["arrival_rate"]) for r in cur]
        sat = [float(r["deadline_satisfaction_med"]) for r in cur]
        sat_l = [float(r["deadline_satisfaction_ci_low"]) for r in cur]
        sat_h = [float(r["deadline_satisfaction_ci_high"]) for r in cur]
        ax.errorbar(lams, sat, yerr=[np.array(sat)-np.array(sat_l), np.array(sat_h)-np.array(sat)],
                    label=f"Policy: {pol}", color=col, marker="o", capsize=3, linewidth=2)

    ax.set_xlabel(r"Task Arrival Rate $\lambda$ (tasks/step)")
    ax.set_ylabel("Deadline Satisfaction Rate (%)")
    ax.set_title(r"Scheduling Policy Comparison (Zoned, $\tau = 12\,\mathrm{ms}$, V2 4-th)")
    ax.set_ylim(-5, 105)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower left")

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "fig7_policy_comparison.png"), dpi=300)
    plt.savefig(os.path.join(FIG_DIR, "fig7_policy_comparison.pdf"))
    plt.close()
    print("Saved fig7_policy_comparison.png/.pdf")


def main():
    plot_fig1_speedup_vs_p()
    plot_fig2_work_span_bounds()
    plot_fig3_karp_flatt()
    plot_fig4_density_regime_map()
    plot_fig5_constant_density_scaling_N()
    plot_fig6_deadline_arrival_rate_sweep()
    plot_fig7_policy_comparison()
    print("Publication figures generation attempted.")


if __name__ == "__main__":
    main()
