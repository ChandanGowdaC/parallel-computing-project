#!/usr/bin/env python3
"""
Independent Collision-Freedom Verifier (Phase 1 / C2).
Validates vertex conflicts and edge (swap) conflicts across all agents
for every executed timestep from paths.txt.
Exits with 0 if 100% collision-free; exits with 1 on ANY conflict.
"""

import sys
import os

def verify_paths(path_file):
    if not os.path.exists(path_file):
        print(f"[VERIFIER ERROR] File not found: {path_file}", file=sys.stderr)
        return False, ["File not found"]

    with open(path_file, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]

    if not lines:
        print(f"[VERIFIER ERROR] Empty path file: {path_file}", file=sys.stderr)
        return False, ["Empty file"]

    num_agents = int(lines[0])
    agent_paths = {}
    max_t = 0

    for agent_idx in range(num_agents):
        if agent_idx + 1 >= len(lines):
            break
        raw_path = lines[agent_idx + 1]
        steps = [s for s in raw_path.split(';') if s.strip()]
        trajectory = {}
        for s in steps:
            parts = s.split(',')
            if len(parts) >= 3:
                loc = int(parts[0])
                t = int(parts[2])
                trajectory[t] = loc
                if t > max_t:
                    max_t = t
        agent_paths[agent_idx] = trajectory

    violations = []

    def get_agent_loc(traj, t):
        if t in traj:
            return traj[t]
        if traj:
            max_k = max(traj.keys())
            if t > max_k:
                return traj[max_k] # Holds at final location
        return -1

    # Check every timestep t
    for t in range(max_t + 1):
        # 1. Vertex collision check
        occ = {}
        for a_id, traj in agent_paths.items():
            loc = get_agent_loc(traj, t)
            if loc < 0:
                continue  # Negative location means off-grid / dummy holding
            if loc in occ:
                other_a = occ[loc]
                violations.append(
                    f"Vertex collision at t={t}: agent {other_a} and agent {a_id} both occupy location {loc}"
                )
            else:
                occ[loc] = a_id

        # 2. Edge swap conflict check between t and t+1
        if t < max_t:
            for a1 in range(num_agents):
                traj1 = agent_paths.get(a1, {})
                loc1_t = get_agent_loc(traj1, t)
                loc1_next = get_agent_loc(traj1, t + 1)
                if loc1_t < 0 or loc1_next < 0 or loc1_t == loc1_next:
                    continue

                for a2 in range(a1 + 1, num_agents):
                    traj2 = agent_paths.get(a2, {})
                    loc2_t = get_agent_loc(traj2, t)
                    loc2_next = get_agent_loc(traj2, t + 1)
                    if loc2_t < 0 or loc2_next < 0 or loc2_t == loc2_next:
                        continue

                    # Swap check: a1 moves loc1_t -> loc1_next, a2 moves loc2_t -> loc2_next
                    if loc1_t == loc2_next and loc2_t == loc1_next:
                        violations.append(
                            f"Edge swap collision between t={t} and t={t+1}: agent {a1} ({loc1_t}->{loc1_next}) "
                            f"and agent {a2} ({loc2_t}->{loc2_next})"
                        )

    if violations:
        print(f"[VERIFIER FAILED] {len(violations)} collisions found in {path_file}:", file=sys.stderr)
        for v in violations[:10]:
            print(f"  - {v}", file=sys.stderr)
        if len(violations) > 10:
            print(f"  ... and {len(violations) - 10} more", file=sys.stderr)
        return False, violations
    else:
        print(f"[VERIFIER PASSED] Verified {num_agents} agents up to t={max_t}. 0 collisions found.")
        return True, []

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_paths.txt or directory>")
        sys.exit(2)
    
    target = sys.argv[1]
    if os.path.isdir(target):
        # Scan for all paths.txt files in directory
        path_files = []
        for root, dirs, files in os.walk(target):
            for file in files:
                if file == "paths.txt" or file.endswith("_paths.txt"):
                    path_files.append(os.path.join(root, file))
        if not path_files:
            print(f"No paths.txt files found in directory {target}")
            sys.exit(0)
        
        all_passed = True
        for pf in sorted(path_files):
            print(f"Verifying {pf}...")
            passed, _ = verify_paths(pf)
            if not passed:
                all_passed = False
        sys.exit(0 if all_passed else 1)
    else:
        success, _ = verify_paths(target)
        sys.exit(0 if success else 1)
