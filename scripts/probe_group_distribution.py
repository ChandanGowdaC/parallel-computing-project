#!/usr/bin/env python3
"""
probe_group_distribution.py — Feasibility probe for GD-RHCR group-size distribution.

Evaluates spatial connected components on the KIVA map (33x46, 1278 walkable cells)
at 100, 400, and 800 agents for multiple visibility radii V in {2, 4, 6, 8, 10, 15, 20},
where w = 10, so V = 2w = 20 is the theoretical collision-free threshold.

Computes:
  - Number of groups
  - Mean group size
  - Max group size
  - Largest-group fraction (max_size / N)
"""

import sys
import random
from collections import deque, defaultdict


def load_kiva_map(map_path):
    with open(map_path, 'r') as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    
    rows, cols = map(int, lines[0].split(','))
    num_endpoints = int(lines[1])
    num_home = int(lines[2])
    
    grid = lines[4:]
    endpoints = []
    home_stations = []
    walkable = []
    
    for r in range(rows):
        for c in range(cols):
            loc = r * cols + c
            char = grid[r][c]
            if char == '@':
                continue
            walkable.append(loc)
            if char == 'e':
                endpoints.append(loc)
            elif char == 'r':
                home_stations.append(loc)
                
    return rows, cols, walkable, endpoints, home_stations


def manhattan_distance(loc1, loc2, cols):
    r1, c1 = divmod(loc1, cols)
    r2, c2 = divmod(loc2, cols)
    return abs(r1 - r2) + abs(c1 - c2)


def partition_groups(locations, cols, V):
    """
    Connected components over locations with distance <= V.
    Exact match to GDRHCR.h partition_agent_groups().
    """
    n = len(locations)
    visited = [False] * n
    groups = []
    
    for i in range(n):
        if visited[i]:
            continue
        group = []
        queue = deque([i])
        visited[i] = True
        
        while queue:
            curr = queue.popleft()
            group.append(curr)
            curr_loc = locations[curr]
            
            for j in range(n):
                if not visited[j]:
                    dist = manhattan_distance(curr_loc, locations[j], cols)
                    if dist <= V:
                        visited[j] = True
                        queue.append(j)
                        
        groups.append(group)
        
    return groups


def sample_kiva_locations(num_agents, walkable, endpoints, home_stations, seed, mode="realistic"):
    """
    Generate realistic agent locations on KIVA:
    In KIVA lifelong MAPF, agents begin at home stations (up to 192) and endpoints,
    then travel between endpoints and workstations.
    """
    rng = random.Random(seed)
    
    if mode == "initial":
        # Initial placement matches KivaSystem::initialize_start_locations
        shuffled_home = list(home_stations)
        rng.shuffle(shuffled_home)
        
        locations = []
        used = set()
        for k in range(num_agents):
            if k < len(shuffled_home):
                loc = shuffled_home[k]
            else:
                available = [w for w in walkable if w not in used]
                loc = rng.choice(available)
            used.add(loc)
            locations.append(loc)
        return locations
        
    elif mode == "dynamic":
        # During operation, agents are dispersed across endpoints, highways, and stations
        # Endpoints have higher density as agents pick/drop, while others are on travel lanes
        chosen = rng.sample(walkable, num_agents)
        return chosen


def run_probe():
    map_path = "maps/kiva.map"
    rows, cols, walkable, endpoints, home_stations = load_kiva_map(map_path)
    
    print(f"Loaded KIVA map: {rows}x{cols} ({rows*cols} cells)")
    print(f"Walkable cells: {len(walkable)}, Endpoints: {len(endpoints)}, Home stations: {len(home_stations)}")
    print("=" * 80)
    
    agent_counts = [100, 400, 800]
    radii = [2, 4, 6, 8, 10, 15, 20]  # w = 10, so V = 2w = 20
    seeds = [42, 123, 456, 789, 1024]
    
    results = {}
    
    for mode in ["initial", "dynamic"]:
        print(f"\nEvaluating mode: {mode.upper()} distribution")
        print("-" * 80)
        print(f"{'Agents':>6} | {'V':>4} | {'Groups':>7} | {'Mean Size':>10} | {'Max Size':>9} | {'Largest Frac':>13} | Giant Group?")
        print("-" * 80)
        
        for agents in agent_counts:
            for V in radii:
                grp_counts = []
                mean_sizes = []
                max_sizes = []
                largest_fracs = []
                
                for s in seeds:
                    locs = sample_kiva_locations(agents, walkable, endpoints, home_stations, s, mode=mode)
                    groups = partition_groups(locs, cols, V)
                    sizes = [len(g) for g in groups]
                    
                    grp_counts.append(len(groups))
                    mean_sizes.append(sum(sizes) / len(groups))
                    max_sizes.append(max(sizes))
                    largest_fracs.append(max(sizes) / agents)
                    
                avg_grp = sum(grp_counts) / len(grp_counts)
                avg_mean_sz = sum(mean_sizes) / len(mean_sizes)
                avg_max_sz = sum(max_sizes) / len(max_sizes)
                avg_frac = sum(largest_fracs) / len(largest_fracs)
                
                is_giant = "YES (>80%)" if avg_frac >= 0.8 else ("PARTIAL (50-80%)" if avg_frac >= 0.5 else "NO (<50%)")
                print(f"{agents:6d} | {V:4d} | {avg_grp:7.1f} | {avg_mean_sz:10.1f} | {avg_max_sz:9.1f} | {avg_frac*100:12.1f}% | {is_giant}")
                
                results[(mode, agents, V)] = {
                    "groups": avg_grp,
                    "mean_size": avg_mean_sz,
                    "max_size": avg_max_sz,
                    "frac": avg_frac
                }
                
    print("=" * 80)
    return results


if __name__ == "__main__":
    run_probe()
