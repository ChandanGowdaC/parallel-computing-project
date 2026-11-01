#!/usr/bin/env python3
"""
analyze_reconciliation_probe.py — Step A & B reconciliation analysis.
"""

import os
import csv
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_DIR = os.path.join(ROOT_DIR, "results", "raw")
SEEDS = [101, 202, 303]


def main():
    print("=" * 110)
    print("      STEP A: RECONCILED WATERFALL & WORK/SPAN BOUND TABLE (N=400, T_sim=250)")
    print("=" * 110)

    # 1. First get V0 and V1 baselines
    # V0
    v0_solv = {"uniform": {}, "zoned": {}}
    v0_plan = {"uniform": {}, "zoned": {}}
    v0_tot  = {"uniform": {}, "zoned": {}}
    v0_tp   = {"uniform": {}, "zoned": {}}

    for wl in ["uniform", "zoned"]:
        for s in SEEDS:
            f = os.path.join(RAW_DIR, f"run_probe_kiva400_v0_{wl}_s{s}.csv")
            with open(f) as fp:
                r = next(csv.DictReader(fp))
                v0_solv[wl][s] = float(r["solver_runtime_ms"])
                v0_tot[wl][s]  = float(r["total_runtime_ms"])
                v0_tp[wl][s]   = float(r["throughput"])
                v0_plan[wl][s] = float(r["solver_runtime_ms"]) # For V0, plan = solv

    # V1 for V in {1, 2, 3}
    v1_plan = {}
    v1_solv = {}
    for wl in ["uniform", "zoned"]:
        for V in [1, 2, 3]:
            v1_plan[(wl, V)] = {}
            v1_solv[(wl, V)] = {}
            for s in SEEDS:
                rid = f"reconcile_kiva400_V1_V{V}_{wl}_t1_s{s}"
                f_run = os.path.join(RAW_DIR, f"run_{rid}.csv")
                f_ep = os.path.join(RAW_DIR, f"episodes_{rid}.csv")
                with open(f_run) as fp:
                    r = next(csv.DictReader(fp))
                    v1_solv[(wl, V)][s] = float(r["solver_runtime_ms"])
                with open(f_ep) as ef:
                    ep_rows = list(csv.DictReader(ef))
                    plan_ms = sum(
                        float(e["t_partition_ms"]) + float(e["t_dispatch_ms"]) +
                        float(e["merge_time_ms"]) + float(e["solve_time_ms"]) +
                        float(e["t_serial_rest_ms"])
                        for e in ep_rows
                    )
                    v1_plan[(wl, V)][s] = plan_ms

    # Table 1: Waterfall breakdown
    print("\n--- TABLE 1: RECONCILED WATERFALL BREAKDOWN (Per Run, Medians over Seeds 101, 202, 303) ---")
    header1 = (
        "{:<8} | {:<1} | {:<1} | {:<8} | {:<7} | {:<8} | {:<7} | {:<7} | {:<10} | {:<10} | {:<10} | {:<9} | {:<10}"
    ).format(
        "Workload", "V", "p", "Part(ms)", "Disp(ms)", "Merge(ms)", "Rest(ms)", "Fallb(ms)", "Serial(ms)", "ParWall(ms)", "Plan(ms)", "Total(ms)", "Uninst(ms)"
    )
    print(header1)
    print("-" * len(header1))

    # We want N=400, V in {2, 3}, uniform and zoned, p in {4, 8}
    reconciled_data = {}
    for wl in ["uniform", "zoned"]:
        for V in [2, 3]:
            for p in [4, 8]:
                parts, disps, merges, rests, fbs, serials, par_walls, plans, totals, uninsts = (
                    [], [], [], [], [], [], [], [], [], []
                )
                works, spans, t_lows, t_ups = [], [], [], []

                for s in SEEDS:
                    rid = f"reconcile_kiva400_V2_V{V}_{wl}_t{p}_s{s}"
                    f_run = os.path.join(RAW_DIR, f"run_{rid}.csv")
                    f_ep = os.path.join(RAW_DIR, f"episodes_{rid}.csv")

                    with open(f_run) as fp:
                        r = next(csv.DictReader(fp))
                        tot_ms = float(r["total_runtime_ms"])

                    run_part = 0.0
                    run_disp = 0.0
                    run_merge = 0.0
                    run_rest = 0.0
                    run_fb = 0.0
                    run_par_wall = 0.0
                    run_work = 0.0
                    run_span = 0.0

                    with open(f_ep) as ef:
                        for e in csv.DictReader(ef):
                            t_part = float(e["t_partition_ms"])
                            t_disp = float(e["t_dispatch_ms"])
                            t_mrg  = float(e["merge_time_ms"])
                            t_solv = float(e["solve_time_ms"])
                            t_rst  = float(e["t_serial_rest_ms"])
                            t_fb   = float(e["global_fallback_time_ms"])

                            # Task work and span
                            # mean_group_solve_ms * tasks = work, max_group_solve_ms = span
                            w_cyc = float(e["mean_group_solve_ms"]) * float(e.get("num_groups", 1)) # approx or exact from worker busy
                            # Exact work is sum of worker busy
                            pw = e.get("per_worker_busy_ms", "")
                            if pw:
                                wtimes = [float(x) for x in pw.split(";") if x.strip()]
                                w_cyc = sum(wtimes)
                            s_cyc = float(e["max_group_solve_ms"])

                            run_part += t_part
                            run_disp += t_disp
                            run_merge += t_mrg
                            run_rest += t_rst
                            run_fb += t_fb
                            run_par_wall += (t_solv - t_fb)
                            run_work += w_cyc
                            run_span += s_cyc

                    run_serial = run_part + run_disp + run_merge + run_rest + run_fb
                    run_plan = run_serial + run_par_wall
                    run_uninst = tot_ms - run_plan

                    # Correct bounds
                    # T_low = T_serial + max(Work/p, Span)
                    # T_up  = T_serial + (Work - Span)/p + Span
                    t_low = run_serial + max(run_work / p, run_span)
                    t_up  = run_serial + (run_work - run_span) / p + run_span

                    parts.append(run_part)
                    disps.append(run_disp)
                    merges.append(run_merge)
                    rests.append(run_rest)
                    fbs.append(run_fb)
                    serials.append(run_serial)
                    par_walls.append(run_par_wall)
                    plans.append(run_plan)
                    totals.append(tot_ms)
                    uninsts.append(run_uninst)
                    works.append(run_work)
                    spans.append(run_span)
                    t_lows.append(t_low)
                    t_ups.append(t_up)

                key = (wl, V, p)
                reconciled_data[key] = {
                    "part": np.median(parts),
                    "disp": np.median(disps),
                    "merge": np.median(merges),
                    "rest": np.median(rests),
                    "fb": np.median(fbs),
                    "serial": np.median(serials),
                    "par_wall": np.median(par_walls),
                    "plan": np.median(plans),
                    "total": np.median(totals),
                    "uninst": np.median(uninsts),
                    "work": np.median(works),
                    "span": np.median(spans),
                    "t_low": np.median(t_lows),
                    "t_up": np.median(t_ups),
                }

                d = reconciled_data[key]
                print(
                    "{:<8} | {:<1} | {:<1} | {:>8.2f} | {:>7.2f} | {:>8.2f} | {:>7.2f} | {:>7.2f} | {:>10.2f} | {:>10.2f} | {:>10.2f} | {:>9.2f} | {:>10.2f}".format(
                        wl, V, p, d["part"], d["disp"], d["merge"], d["rest"], d["fb"],
                        d["serial"], d["par_wall"], d["plan"], d["total"], d["uninst"]
                    )
                )

    # Table 2: Work/Span Corrected Bounds & Verification
    print("\n--- TABLE 2: CORRECTED WORK/SPAN BOUNDS & MEASURED VERIFICATION (N=400, T_sim=250) ---")
    header2 = "{:<8} | {:<1} | {:<1} | {:<10} | {:<10} | {:<10} | {:<10} | {:<10} | {:<8} | {:<8} | {:<10}".format(
        "Workload", "V", "p", "Work(ms)", "Span(ms)", "T_low(ms)", "T_meas(ms)", "T_up(ms)", "S_thread", "Karp-Flatt", "In Bounds?"
    )
    print(header2)
    print("-" * len(header2))

    for wl in ["uniform", "zoned"]:
        for V in [2, 3]:
            for p in [4, 8]:
                d = reconciled_data[(wl, V, p)]
                # S_thread = T_plan(V1) / T_plan(V2)
                v1_pl = np.median([v1_plan[(wl, V)][s] for s in SEEDS])
                s_thread = v1_pl / d["plan"]
                
                # Karp-Flatt: e = (1/S_thread - 1/p) / (1 - 1/p)
                e = (1.0 / s_thread - 1.0 / p) / (1.0 - 1.0 / p)

                # Check bounds: T_low <= T_meas <= T_up
                in_bounds = (d["t_low"] <= d["plan"] <= d["t_up"])
                in_bounds_str = "YES" if in_bounds else f"NO (dev={d['plan']-d['t_up']:+.1f})"

                print("{:<8} | {:<1} | {:<1} | {:>10.2f} | {:>10.2f} | {:>10.2f} | {:>10.2f} | {:>10.2f} | {:>7.2f}x | {:>10.3f} | {:<10}".format(
                    wl, V, p, d["work"], d["span"], d["t_low"], d["plan"], d["t_up"], s_thread, e, in_bounds_str
                ))

    # Table 3: Step B Tuning additions for V in {1, 2, 3} (and earlier probe V in {4, 5, 8})
    print("\n--- TABLE 3: STEP B TUNING ADDITIONS & V* EVALUATION (N=400, T_sim=250) ---")
    header3 = "{:<8} | {:<1} | {:<1} | {:<10} | {:<10} | {:<10} | {:<10} | {:<12} | {:<10}".format(
        "Workload", "V", "p", "Plan(ms)", "S_alg", "S_thread", "S_total", "Fallback Rate", "TP vs V0"
    )
    print(header3)
    print("-" * len(header3))

    for wl in ["uniform", "zoned"]:
        v0_pl_med = np.median([v0_plan[wl][s] for s in SEEDS])
        v0_tp_med = np.median([v0_tp[wl][s] for s in SEEDS])

        for V in [1, 2, 3]:
            # V1 baseline
            v1_pl_med = np.median([v1_plan[(wl, V)][s] for s in SEEDS])
            s_alg = v0_pl_med / v1_pl_med

            for p in [1, 4, 8]:
                plans, tps, fbs = [], [], []
                for s in SEEDS:
                    v_type = "V1" if p == 1 else "V2"
                    rid = f"reconcile_kiva400_{v_type}_V{V}_{wl}_t{p}_s{s}"
                    f_run = os.path.join(RAW_DIR, f"run_{rid}.csv")
                    f_ep = os.path.join(RAW_DIR, f"episodes_{rid}.csv")

                    with open(f_run) as fp:
                        r = next(csv.DictReader(fp))
                        tps.append(float(r["throughput"]))

                    with open(f_ep) as ef:
                        ep_rows = list(csv.DictReader(ef))
                        pl_ms = sum(
                            float(e["t_partition_ms"]) + float(e["t_dispatch_ms"]) +
                            float(e["merge_time_ms"]) + float(e["solve_time_ms"]) +
                            float(e["t_serial_rest_ms"])
                            for e in ep_rows
                        )
                        fb_cnt = sum(1 for e in ep_rows if int(e.get("global_fallback_invoked", 0)) > 0)
                        fbs.append(fb_cnt / len(ep_rows) * 100.0)
                        plans.append(pl_ms)

                pl_med = np.median(plans)
                tp_med = np.median(tps)
                fb_med = np.median(fbs)

                s_th = v1_pl_med / pl_med
                s_tot = v0_pl_med / pl_med
                tpr = tp_med / v0_tp_med

                print("{:<8} | {:<1} | {:<1} | {:>10.2f} | {:>9.2f}x | {:>9.2f}x | {:>9.2f}x | {:>11.1f}% | {:>9.3f}x".format(
                    wl, V, p, pl_med, s_alg, s_th, s_tot, fb_med, tpr
                ))


if __name__ == "__main__":
    main()
