#!/usr/bin/env python3
"""
Phase 1 / C1: Determinism and Equivalence Verifier.
Validates that with --parallel off, outputs match vanilla RHCR
byte-for-byte on the same seeds (paths.txt, tasks.txt, throughput, completed tasks).
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

def test_seed(seed, agents=50, sim_time=20):
    dir_vanilla = f"/tmp/c1_vanilla_s{seed}"
    dir_paroff = f"/tmp/c1_paroff_s{seed}"
    shutil.rmtree(dir_vanilla, ignore_errors=True)
    shutil.rmtree(dir_paroff, ignore_errors=True)
    os.makedirs(dir_vanilla, exist_ok=True)
    os.makedirs(dir_paroff, exist_ok=True)

    base_args = [
        BINARY,
        "--map", MAP_FILE,
        "--scenario", "KIVA",
        "--solver", "PBS",
        "--agentNum", str(agents),
        "--simulation_time", str(sim_time),
        "--simulation_window", "5",
        "--planning_window", "10",
        "--seed", str(seed),
    ]

    # 1. Vanilla RHCR (no parallel flag)
    cmd_vanilla = base_args + ["--output_dir", dir_vanilla]
    p1 = subprocess.run(cmd_vanilla, capture_output=True, text=True)
    assert p1.returncode == 0, f"Vanilla run failed on seed {seed}:\n{p1.stderr}\n{p1.stdout}"

    # 2. Parallel OFF
    cmd_paroff = base_args + ["--parallel", "off", "--output_dir", dir_paroff]
    p2 = subprocess.run(cmd_paroff, capture_output=True, text=True)
    assert p2.returncode == 0, f"Parallel-off run failed on seed {seed}:\n{p2.stderr}\n{p2.stdout}"

    # Check paths.txt
    paths_v = os.path.join(dir_vanilla, "paths.txt")
    paths_p = os.path.join(dir_paroff, "paths.txt")
    assert os.path.exists(paths_v) and os.path.exists(paths_p), "paths.txt missing!"
    hash_paths_v = sha256_file(paths_v)
    hash_paths_p = sha256_file(paths_p)

    # Check tasks.txt
    tasks_v = os.path.join(dir_vanilla, "tasks.txt")
    tasks_p = os.path.join(dir_paroff, "tasks.txt")
    assert os.path.exists(tasks_v) and os.path.exists(tasks_p), "tasks.txt missing!"
    hash_tasks_v = sha256_file(tasks_v)
    hash_tasks_p = sha256_file(tasks_p)

    if hash_paths_v != hash_paths_p:
        print(f"[FAIL] paths.txt mismatch on seed {seed}!", file=sys.stderr)
        return False
    if hash_tasks_v != hash_tasks_p:
        print(f"[FAIL] tasks.txt mismatch on seed {seed}!", file=sys.stderr)
        return False

    print(f"  [PASS] Seed {seed}: byte-identical match (paths hash: {hash_paths_v[:12]}..., tasks hash: {hash_tasks_v[:12]}...)")
    return True

def main():
    print("[TEST C1] Testing determinism and equivalence across multiple seeds...")
    seeds = [42, 100, 2026]
    all_passed = True
    for s in seeds:
        if not test_seed(s):
            all_passed = False

    if all_passed:
        print("[TEST C1] ALL SEEDS PASSED BYTE-IDENTICAL EQUIVALENCE!")
        sys.exit(0)
    else:
        print("[TEST C1] EQUIVALENCE TEST FAILED!", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
