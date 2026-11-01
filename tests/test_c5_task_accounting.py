#!/usr/bin/env python3
"""
Phase 1 / C5: Task Accounting Reconciliation Verifier.
Verifies that every generated task is either:
  1. Completed (finish_time >= 0, status == COMPLETED)
  2. Still pending/unassigned/in-progress within deadline (finish_time == -1, deadline >= T_end)
  3. Overdue and uncompleted at the end (finish_time == -1, deadline < T_end)
Ensures exact reconciliation across multiple scheduling policies and arrival rates:
N_generated == N_completed + N_pending + N_overdue_uncompleted
"""

import sys
import os
import csv
import subprocess
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(PROJECT_ROOT, "build", "lifelong")
MAP_FILE = os.path.join(PROJECT_ROOT, "maps", "kiva.map")

def test_accounting(policy, arrival_rate, deadline_factor, seed=42, sim_time=50):
    run_dir = f"/tmp/test_c5_{policy}_r{arrival_rate}_s{seed}"
    shutil.rmtree(run_dir, ignore_errors=True)
    os.makedirs(run_dir, exist_ok=True)

    cmd = [
        BINARY,
        "--map", MAP_FILE,
        "--scenario", "KIVA",
        "--solver", "PBS",
        "--agentNum", "25",
        "--simulation_time", str(sim_time),
        "--simulation_window", "5",
        "--planning_window", "10",
        "--seed", str(seed),
        "--deadline",
        "--task_arrival_rate", str(arrival_rate),
        "--deadline_factor", str(deadline_factor),
        "--scheduling_policy", policy,
        "--output_dir", run_dir
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Run failed for {policy}:\n{res.stderr}\n{res.stdout}"

    # Find the generated CSVs
    run_csvs = [f for f in os.listdir(run_dir) if f.startswith("run_") and f.endswith(".csv")]
    task_csvs = [f for f in os.listdir(run_dir) if f.startswith("tasks_") and f.endswith(".csv")]

    assert len(run_csvs) == 1, f"Expected 1 run CSV, found {run_csvs}"
    assert len(task_csvs) == 1, f"Expected 1 task CSV, found {task_csvs}"

    # 1. Parse run-level metrics
    with open(os.path.join(run_dir, run_csvs[0]), 'r') as f:
        reader = csv.DictReader(f)
        run_row = next(reader)
        n_gen_metric = int(run_row["num_tasks_generated"])
        n_comp_metric = int(run_row["num_tasks_completed"])

    # 2. Parse task-level rows
    tasks = []
    with open(os.path.join(run_dir, task_csvs[0]), 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tasks.append(row)

    total_tasks = len(tasks)
    assert total_tasks == n_gen_metric, f"Task count mismatch: CSV has {total_tasks} rows, but run metric says {n_gen_metric}"

    n_completed = 0
    n_pending = 0
    n_overdue_uncompleted = 0

    seen_ids = set()
    for t in tasks:
        t_id = int(t["task_id"])
        assert t_id not in seen_ids, f"Duplicate task_id {t_id} detected!"
        seen_ids.add(t_id)

        completion_time = int(t["completion_time"])
        deadline = int(t["deadline"])
        status = t["status"]

        if completion_time >= 0:
            assert status == "COMPLETED", f"Task {t_id} has completion time {completion_time} but status is {status}"
            n_completed += 1
        else:
            assert completion_time == -1, f"Invalid incomplete time: {completion_time}"
            if deadline >= sim_time:
                n_pending += 1
            else:
                n_overdue_uncompleted += 1

    # Exact reconciliation checks
    reconciled_sum = n_completed + n_pending + n_overdue_uncompleted
    assert reconciled_sum == total_tasks, (
        f"Reconciliation failure: completed ({n_completed}) + pending ({n_pending}) + "
        f"overdue-uncompleted ({n_overdue_uncompleted}) = {reconciled_sum} != total ({total_tasks})"
    )
    assert n_completed == n_comp_metric, (
        f"Completed count mismatch: parsed {n_completed} vs run_metrics {n_comp_metric}"
    )

    print(f"  [PASS] Policy {policy:<14} (lambda={arrival_rate}): "
          f"Generated={total_tasks:2d} | Completed={n_completed:2d} | "
          f"Pending={n_pending:2d} | OverdueUncompleted={n_overdue_uncompleted:2d} -> Exact Reconciliation Verified.")
    return True

def main():
    print("[TEST C5] Running task accounting reconciliation verification across policies...")
    configs = [
        ("FIFO", 1.0, 2.0),
        ("EDF", 1.0, 2.0),
        ("DEADLINE_AWARE", 1.0, 2.0),
        ("EDF", 2.0, 1.5),
        ("DEADLINE_AWARE", 0.5, 2.5),
    ]

    all_ok = True
    for policy, rate, factor in configs:
        if not test_accounting(policy, rate, factor):
            all_ok = False

    if all_ok:
        print("[TEST C5] ALL TASK ACCOUNTING RECONCILIATIONS PASSED EXACTLY!")
        sys.exit(0)
    else:
        print("[TEST C5] TASK ACCOUNTING RECONCILIATION FAILED!", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
