# Parallel Computing Project: Lifelong MAPF & GD-RHCR

An empirical implementation and benchmarking framework for **Group Decentralized Rolling-Horizon Collision Resolution (GD-RHCR)** and deadline-aware lifelong Multi-Agent Path Finding (MAPF), built on the foundation of Jiaoyang Li et al.'s [RHCR](https://github.com/Jiaoyang-Li/RHCR) engine.

---

## Architecture Overview

```
├── .github/workflows/ci.yml       # Automated CI (Linux & macOS)
├── build.sh                       # One-command reproducible build
├── run.sh                         # Execution wrapper (baseline, test, custom args)
├── CMakeLists.txt                 # Modern CMake configuration (>= 3.10)
├── inc/
│   ├── ThreadPool.h               # ThreadPool primitive (progschj/ThreadPool)
│   ├── Task.h                     # Person B Task contract (deadlines, tardiness)
│   ├── SolverInterface.h          # Person A/C Solver contract (GroupPlanningTask)
│   ├── Metrics.h                  # Person D Metrics contract (CSV/JSON schema)
│   └── ...                        # RHCR core headers
├── src/                           # RHCR core sources + driver
├── maps/                          # Warehouse maps (kiva.map, sorting grids)
└── tests/
    └── test_thread_pool.cpp       # ThreadPool unit & concurrency test
```

---

## Quickstart

### 1. Prerequisites

- **macOS**: `brew install boost cmake`
- **Linux (Ubuntu / Debian)**: `sudo apt-get install -y cmake build-essential libboost-all-dev`

### 2. Build

Run the automated build script (handles dependencies, parallel compilation, and Apple Silicon/Linux paths):
```bash
./build.sh
```

Binaries will be placed in `./build/`:
- `./build/lifelong` (Main simulation engine)
- `./build/test_thread_pool` (ThreadPool verification test)

### 3. Verify ThreadPool & Infra

Run the threadpool test suite:
```bash
./run.sh test
# or directly:
./build/test_thread_pool
```

### 4. Run Sequential Baseline

Run the default KIVA warehouse smoke test:
```bash
./run.sh
```

Or run custom experiment parameters:
```bash
# KIVA warehouse scenario with ECBS:
./run.sh --scenario=KIVA -m maps/kiva.map -k 100 --simulation_window=1 --solver=ECBS --suboptimal_bound=1.5 --dummy_paths=1 --seed=0 --simulation_time=50

# Sorting center scenario with PBS:
./run.sh --scenario=SORTING -m maps/sorting_map.grid -k 200 --simulation_window=5 --planning_window=10 --solver=PBS --seed=0 --simulation_time=50
```

---

## Experiment CLI Options (Person A Config System)

| Flag | Short | Default | Description |
|---|---|---|---|
| `--threads` | `-j` | `1` | Number of worker threads for parallel execution |
| `--parallel` | | `false` | Enable parallel planning (GD-RHCR). When `false`, runs sequential baseline |
| `--vis_radius` | `-V` | `5` | Visibility / spatial partitioning radius for GD-RHCR |
| `--deadline` | | `false` | Enable deadline-aware task generation (Person B) |
| `--task_arrival_rate` | | `1.0` | Poisson task arrival rate $\lambda$ |
| `--deadline_factor` | | `2.0` | Deadline tightness multiplier |
| `--csv_metrics` | | `""` | Destination path for summary CSV row (Person D) |
| `--json_metrics` | | `""` | Destination path for summary JSON file (Person D) |
| `--simulation_time` | | `5000` | Total simulation timesteps |
| `--simulation_window` | | `5` | Replanning period $h$ |
| `--planning_window` | | `INT_MAX/2` | Collision-free horizon $w$ |
| `--solver` | | `PBS` | Windowed MAPF solver (`ECBS`, `PBS`, `WHCA`, `LRA`) |
| `--suboptimal_bound` | | `1.0` | Suboptimality factor for ECBS (e.g. 1.5) |

---

## Day One Interface Contracts

To avoid merge conflicts, team members agree on and consume the following header contracts:

1. **`inc/Task.h` (Person B interface)**:
   - Contains `struct Task` with fields `id`, `pickup_loc`, `delivery_loc`, `release_time`, `deadline`, `finish_time`, and `status`.
   - Utility methods `is_completed()`, `is_overdue(t)`, and `tardiness(t)`.

2. **`inc/SolverInterface.h` (Person A / Person C interface)**:
   - Defines `GroupPlanningTask` (group agents, starts, goals, horizon $w$, time limit).
   - Defines `GroupPlanningResult` (paths, solve runtime, success status).
   - `WindowedGroupSolverFn` callable type signature for dispatching to `ThreadPool`.

3. **`inc/Metrics.h` (Person D interface)**:
   - `struct RunMetrics`: Uniform CSV header and row serialization for throughput, speedup, wall-clock runtime, and deadline satisfaction rates.
   - `save_tasks_csv(...)`: Detailed per-task completion logs.

4. **Correctness Flag**:
   - Running with `--parallel 0` guarantees execution against the sequential baseline.

---

## Team Division & Roadmap

- **Person A (Build, Infra & Parallel Primitives)**:
  - Working baseline build on Linux & macOS, `ThreadPool.h` integration and tests, unified CLI argument system, `build.sh` / `run.sh` / CI scripts.
- **Person B (Deadline-Aware Workload)**:
  - Task arrival generator (Poisson), deadline assignment, Earliest-Deadline-First / deadline-recovery scheduling, tardiness logging.
- **Person C (GD-RHCR Parallel Core)**:
  - Spatial visibility grouping algorithm, concurrent group solver dispatch using `ThreadPool`, merging group paths into global plan.
- **Person D (Evaluation & Benchmarking)**:
  - Experiment sweeps over thread count ($1, 2, 4, 8$), agent count ($50 \dots 800$), and arrival rates; speedup curves, throughput comparison vs. paper claims.
