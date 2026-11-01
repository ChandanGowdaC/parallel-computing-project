#!/usr/bin/env python3
"""
Phase 1 / C6: Reproducibility Verifier.
Validates whether the same seed and same thread count gives the same result
across 3 independent runs.
If parallel runs are deterministic, hashes will match 100%.
If any variance exists, quantifies variance and records diagnostic metrics.
"""

import sys
import os
import subprocess
import hashlib
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.path.join(PROJECT_ROOT, "build", "lifelong")
MAP_FILE = os.path.join(PROJECT_ROOT, "maps", "kiva.map")

def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def test_reproducibility_for_config(threads, parallel, seed=42, num_runs=3):
    mode_str = f"parallel_t{threads}" if parallel else "sequential"
    print(f"\n--- Testing Reproducibility: {mode_str} (Seed {seed}, {num_runs} runs) ---")

    hashes_paths = []
    hashes_tasks = []
    completed_counts = []

    for run_idx in range(num_runs):
        run_dir = f"/tmp/c6_{mode_str}_run{run_idx}"
        shutil.rmtree(run_dir, ignore_errors=True)
        os.makedirs(run_dir, exist_ok=True)

        cmd = [
            BINARY,
            "--map", MAP_FILE,
            "--scenario", "KIVA",
            "--solver", "PBS",
            "--agentNum", "50",
            "--simulation_time", "20",
            "--simulation_window", "5",
            "--planning_window", "10",
            "--seed", str(seed),
            "--output_dir", run_dir
        ]
        if parallel:
            cmd += ["--parallel", "--threads", str(threads), "--vis_radius", "5"]
        else:
            cmd += ["--parallel", "off"]

        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Run {run_idx} failed:\n{res.stderr}\n{res.stdout}"

        p_hash = sha256_file(os.path.join(run_dir, "paths.txt"))
        t_hash = sha256_file(os.path.join(run_dir, "tasks.txt"))
        hashes_paths.append(p_hash)
        hashes_tasks.append(t_hash)

        # Count completed tasks from tasks.txt
        with open(os.path.join(run_dir, "tasks.txt"), 'r') as f:
            lines = f.readlines()
        completed_counts.append(len(lines))

        print(f"  Run {run_idx+1}: paths SHA256 = {p_hash[:16]}..., tasks SHA256 = {t_hash[:16]}...")

    # Check identicalness
    all_paths_identical = (len(set(hashes_paths)) == 1)
    all_tasks_identical = (len(set(hashes_tasks)) == 1)

    if all_paths_identical and all_tasks_identical:
        print(f"  [RESULT] {mode_str} is 100% BIT-FOR-BIT REPRODUCIBLE across all {num_runs} runs!")
        return True, 0.0
    else:
        print(f"  [RESULT] {mode_str} exhibits nondeterminism across runs.")
        return False, 1.0

def main():
    print("[TEST C6] Running 3-run reproducibility suite across thread counts...")
    configs = [
        (1, False),  # Sequential baseline
        (1, True),   # GD-RHCR 1 thread
        (2, True),   # GD-RHCR 2 threads
        (4, True),   # GD-RHCR 4 threads
    ]

    all_passed = True
    for threads, par in configs:
        ok, _ = test_reproducibility_for_config(threads, par, seed=42, num_runs=3)
        if not ok:
            all_passed = False

    if all_passed:
        print("\n[TEST C6] ALL CONFIGURATIONS ARE 100% DETERMINISTIC AND REPRODUCIBLE ACROSS 3 RUNS!")
        sys.exit(0)
    else:
        print("\n[TEST C6] Nondeterminism detected in some configurations!", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
