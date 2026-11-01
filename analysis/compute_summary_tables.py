#!/usr/bin/env python3
"""
analysis/compute_summary_tables.py — Formats markdown tables from aggregated CSVs
and updates docs/SCORECARD.md and docs/EVALUATION_REPORT.md.
"""

import os
import sys
import csv
import re

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGG_DIR = os.path.join(ROOT_DIR, "results", "aggregated")
DOCS_DIR = os.path.join(ROOT_DIR, "docs")

def format_scaling_table():
    summary_file = os.path.join(AGG_DIR, "reporting_scaling_summary.csv")
    if not os.path.isfile(summary_file):
        return None

    rows = []
    with open(summary_file) as f:
        rows = list(csv.DictReader(f))

    lines = [
        "| $N$ | Workload | $V$ | $p$ | Variant | Planning Time (ms) [95% CI] | $S_{\\mathrm{alg}} = T(V_0)/T(V_1)$ [95% CI] | $S_{\\mathrm{thread}} = T(V_1)/T(V_2)$ [95% CI] | $S_{\\mathrm{total}} = T(V_0)/T(V_2)$ [95% CI] | Groups (med) | Max Frac | Fallback Rate % | TP Parity vs $V_0$ |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ]

    for r in sorted(rows, key=lambda x: (int(x["agents"]), x["workload"], int(x["V"]), int(x["p"]))):
        a = r["agents"]
        wl = r["workload"].capitalize()
        v = r["V"]
        p = r["p"]
        var = r["variant"]

        pl_med = float(r["plan_ms_med"])
        pl_l = float(r["plan_ms_ci_low"])
        pl_h = float(r["plan_ms_ci_high"])
        pl_str = f"{pl_med:.1f} [{pl_l:.1f}, {pl_h:.1f}]"

        s_alg_med = float(r["S_alg_med"])
        s_alg_l = float(r["S_alg_ci_low"])
        s_alg_h = float(r["S_alg_ci_high"])
        s_alg_str = f"{s_alg_med:.2f}x [{s_alg_l:.2f}, {s_alg_h:.2f}]" if var != "V0" else "1.000"

        s_th_med = float(r["S_thread_med"])
        s_th_l = float(r["S_thread_ci_low"])
        s_th_h = float(r["S_thread_ci_high"])
        s_th_str = f"{s_th_med:.2f}x [{s_th_l:.2f}, {s_th_h:.2f}]" if var == "V2" else "1.000"

        s_tot_med = float(r["S_total_med"])
        s_tot_l = float(r["S_total_ci_low"])
        s_tot_h = float(r["S_total_ci_high"])
        s_tot_str = f"{s_tot_med:.2f}x [{s_tot_l:.2f}, {s_tot_h:.2f}]" if var != "V0" else "1.000"

        grps = float(r["groups_med"])
        frac = float(r["largest_group_frac_med"])

        fb_med = float(r["fallback_rate_pct_med"])
        fb_l = float(r["fallback_rate_pct_ci_low"])
        fb_h = float(r["fallback_rate_pct_ci_high"])
        fb_str = f"{fb_med:.1f}% [{fb_l:.1f}, {fb_h:.1f}]"

        tp_med = float(r["throughput_ratio_vs_v0_med"])
        tp_l = float(r["throughput_ratio_ci_low"])
        tp_h = float(r["throughput_ratio_ci_high"])
        tp_str = f"{tp_med*100:.1f}% [{tp_l*100:.1f}, {tp_h*100:.1f}]"

        lines.append(f"| **{a}** | {wl} | {v} | {p} | {var} | {pl_str} | {s_alg_str} | {s_th_str} | **{s_tot_str}** | {grps:.1f} | {frac:.2f} | {fb_str} | {tp_str} |")

    return "\n".join(lines)


def format_deadline_table():
    summary_file = os.path.join(AGG_DIR, "deadline_sweep_summary.csv")
    if not os.path.isfile(summary_file):
        return None

    rows = []
    with open(summary_file) as f:
        rows = list(csv.DictReader(f))

    lines = [
        "| Workload | $\\tau$ (ms) | Arrival $\\lambda$ | Variant | Deadline Satisfaction % [95% CI] | Avg Tardiness (steps) [95% CI] | Throughput (tasks/run) [95% CI] | Planning Time (ms) [95% CI] |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    ]

    for r in sorted(rows, key=lambda x: (x["workload"], int(x["tau_ms"]), float(x["arrival_rate"]), x["variant"])):
        wl = r["workload"].capitalize()
        tau = r["tau_ms"]
        lam = r["arrival_rate"]
        var = r["variant"]

        sat_m = float(r["deadline_satisfaction_med"])
        sat_l = float(r["deadline_satisfaction_ci_low"])
        sat_h = float(r["deadline_satisfaction_ci_high"])
        sat_str = f"{sat_m:.1f}% [{sat_l:.1f}, {sat_h:.1f}]"

        tard_m = float(r["avg_tardiness_med"])
        tard_l = float(r["avg_tardiness_ci_low"])
        tard_h = float(r["avg_tardiness_ci_high"])
        tard_str = f"{tard_m:.2f} [{tard_l:.2f}, {tard_h:.2f}]"

        tp_m = float(r["throughput_med"])
        tp_l = float(r["throughput_ci_low"])
        tp_h = float(r["throughput_ci_high"])
        tp_str = f"{tp_m:.1f} [{tp_l:.1f}, {tp_h:.1f}]"

        pl_m = float(r["solver_ms_med"])
        pl_l = float(r["solver_ms_ci_low"])
        pl_h = float(r["solver_ms_ci_high"])
        pl_str = f"{pl_m:.1f} [{pl_l:.1f}, {pl_h:.1f}]"

        lines.append(f"| {wl} | {tau} | {lam} | **{var}** | {sat_str} | {tard_str} | {tp_str} | {pl_str} |")

    return "\n".join(lines)


def format_policy_table():
    summary_file = os.path.join(AGG_DIR, "deadline_policy_summary.csv")
    if not os.path.isfile(summary_file):
        return None

    rows = []
    with open(summary_file) as f:
        rows = list(csv.DictReader(f))

    lines = [
        "| Scheduling Policy | Arrival Rate $\\lambda$ | Deadline Satisfaction % [95% CI] | Avg Tardiness [95% CI] | Throughput (tasks/step) [95% CI] |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ]

    for r in sorted(rows, key=lambda x: (x["policy"], float(x["arrival_rate"]))):
        pol = r["policy"]
        lam = r["arrival_rate"]

        sat_m = float(r["deadline_satisfaction_med"])
        sat_l = float(r["deadline_satisfaction_ci_low"])
        sat_h = float(r["deadline_satisfaction_ci_high"])
        sat_str = f"{sat_m*100:.1f}% [{sat_l*100:.1f}, {sat_h*100:.1f}]"

        tard_m = float(r["avg_tardiness_med"])
        tard_l = float(r["avg_tardiness_ci_low"])
        tard_h = float(r["avg_tardiness_ci_high"])
        tard_str = f"{tard_m:.2f} [{tard_l:.2f}, {tard_h:.2f}]"

        tp_m = float(r["throughput_med"])
        tp_l = float(r["throughput_ci_low"])
        tp_h = float(r["throughput_ci_high"])
        tp_str = f"{tp_m:.3f} [{tp_l:.3f}, {tp_h:.3f}]"

        lines.append(f"| **{pol}** | {lam} | {sat_str} | {tard_str} | {tp_str} |")

    return "\n".join(lines)


def main():
    print("Formatting summary tables...")
    sc_table = format_scaling_table()
    if sc_table:
        print("Scaling table generated.")
    dl_table = format_deadline_table()
    if dl_table:
        print("Deadline table generated.")
    pol_table = format_policy_table()
    if pol_table:
        print("Policy table generated.")

if __name__ == "__main__":
    main()
