# Parallel Computing Project: Lifelong MAPF & GD-RHCR

An empirical implementation and benchmarking framework for **Group Decentralized Rolling-Horizon Collision Resolution (GD-RHCR)** and deadline-aware lifelong Multi-Agent Path Finding (MAPF), built on the foundation of Jiaoyang Li et al.'s [RHCR](https://github.com/Jiaoyang-Li/RHCR) engine.

---

## Architecture Overview

```
├── .github/workflows/ci.yml       # Automated CI (Linux & macOS)
├── Dockerfile                     # Containerized environment (Ubuntu 22.04 LTS)
├── build.sh                       # One-command reproducible build
├── run.sh                         # Execution wrapper (baseline, tests, custom args)
├── CMakeLists.txt                 # Modern CMake configuration (>= 3.10)
├── inc/
│   ├── ThreadPool.h               # ThreadPool primitive (progschj/ThreadPool)
│   ├── ParallelExecutor.h         # Reusable parallel primitive utility (Person A/C)
│   ├── Task.h                     # Task contract (deadlines, tardiness) (Person B)
│   ├── TaskGenerator.h            # Poisson arrival & deadline generator (Person B)
│   ├── DeadlineScheduler.h        # Scheduling policies (FIFO, EDF, Urgency) (Person B)
│   ├── DeadlineMetrics.h          # Deadline KPIs & snapshot tracker (Person B)
│   ├── SolverInterface.h          # Solver contract (GroupPlanningTask) (Person A/C)
│   ├── Metrics.h                  # Metrics contract (CSV/JSON schema) (Person D)
│   └── ...                        # RHCR core headers
├── src/                           # RHCR core sources + TaskGenerator + DeadlineScheduler + driver
├── maps/                          # Warehouse maps (kiva.map, sorting grids)
├── scripts/
│   ├── sweep_experiments.py       # Experiment sweeper across threads and agents
│   ├── plot_results.py            # Metrics analysis and speedup plot generator
│   └── plot_deadline_metrics.py   # Deadline satisfaction & tardiness plotter (Person B/D)
└── tests/
    ├── test_thread_pool.cpp       # ThreadPool unit & concurrency test
    ├── test_parallel_executor.cpp # ParallelExecutor unit & parallel_map test
    ├── test_interfaces.cpp        # Day One contract validation tests
    └── test_deadline_workload.cpp # Person B deadline workload & policy test suite
```

---

## Quickstart

### 1. Prerequisites

- **macOS**: `brew install boost cmake`
- **Linux (Ubuntu / Debian)**: `sudo apt-get install -y cmake build-essential libboost-all-dev python3`
- **Docker** (alternative): `docker build -t gd-rhcr . && docker run --rm -it gd-rhcr`

### 2. Build

Run the automated build script (handles dependencies, parallel compilation, and Apple Silicon/Linux paths):
```bash
./build.sh
```

Binaries will be placed in `./build/`:
- `./build/lifelong` (Main simulation engine)
- `./build/test_thread_pool` (ThreadPool verification test)
- `./build/test_parallel_executor` (ParallelExecutor verification test)
- `./build/test_interfaces` (Interface contracts validation test)

### 3. Run All Unit & Interface Tests

Run all test suites with a single command:
```bash
./run.sh test
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

## Parallel Primitives (`ParallelExecutor`)

[`inc/ParallelExecutor.h`](inc/ParallelExecutor.h) provides a thread pool wrapper designed specifically for GD-RHCR:
- `parallel_for(start, end, func)`: Runs loop iterations concurrently across the pool.
- `parallel_map(inputs, func)`: Concurrently transforms a collection of inputs (e.g. `std::vector<GroupPlanningTask>`) into outputs (e.g. `std::vector<GroupPlanningResult>`).
- Fallback: When `num_threads == 1`, runs sequentially without thread overhead.

```cpp
#include "ParallelExecutor.h"

ParallelExecutor executor(4); // 4 worker threads
auto results = executor.parallel_map(group_tasks, [](const GroupPlanningTask& task) {
    // Solves windowed MAPF for this group in parallel
    return solve_group(task);
});
```

---

## Automated Experiment Sweeper & Analysis (Person D)

Person A provides automated experiment sweeper and plotting tools in `scripts/`:

```bash
# 1. Run multi-threaded scaling sweep:
python3 scripts/sweep_experiments.py --scenario KIVA --solver ECBS --threads 1 2 4 8 --agents 50 100 200 --sim-time 20

# 2. Analyze speedup, efficiency, and generate summary plots:
python3 scripts/plot_results.py --csv exp/sweep_results.csv
```

Outputs:
- Terminal markdown table with Runtime, Speedup ($S_p = T_1 / T_p$), and Parallel Efficiency ($E_p = S_p / p$).
- Speedup curves and throughput charts in `exp/plots/`.

---

## Experiment CLI Options (Person A Config System)

| Flag | Short | Default | Description |
|---|---|---|---|
| `--threads` | `-j` | `1` | Number of worker threads for parallel execution |
| `--parallel` | | `false` | Enable parallel planning (GD-RHCR). When `false`, runs sequential baseline |
| `--vis_radius` | `-V` | `5` | Visibility / spatial partitioning radius for GD-RHCR |
| `--deadline` | | `false` | Enable deadline-aware task generation (Person B) |
| `--task_arrival_rate` | | `1.0` | Poisson task arrival rate $\lambda$ (tasks/timestep) |
| `--deadline_factor` | | `2.0` | Deadline tightness multiplier $\alpha \ge 1.0$ |
| `--policy` | | `EDF` | Task scheduling policy: `FIFO`, `EDF`, `DEADLINE_AWARE` (Person B) |
| `--tasks_csv` | | `""` | Path for per-task completion records CSV (Person B) |
| `--snapshot_csv` | | `""` | Path for rolling deadline snapshots time series (Person B) |
| `--csv_metrics` | | `""` | Destination path for summary CSV row (Person D) |
| `--json_metrics` | | `""` | Destination path for summary JSON file (Person D) |
| `--resume` | | `false` | Resume simulation from existing `paths.txt` in output folder |
| `--simulation_time` | | `5000` | Total simulation timesteps |
| `--simulation_window` | | `5` | Replanning period $h$ |
| `--planning_window` | | `INT_MAX/2` | Collision-free horizon $w$ |
| `--solver` | | `PBS` | Windowed MAPF solver (`ECBS`, `PBS`, `WHCA`, `LRA`) |
| `--suboptimal_bound` | | `1.0` | Suboptimality factor for ECBS (e.g. 1.5) |

---

## Deadline-Aware Workload & Scheduling (Person B)

Person B implements dynamic, deadline-constrained task generation and real-time scheduling on top of RHCR:

### 1. Workload Generator (`inc/TaskGenerator.h`)
- **Poisson Arrival Process**: Inter-arrival times drawn from $Exp(\lambda)$, modeling stochastic order arrivals in fulfillment warehouses.
- **Randomized Deadline Windows**:
  $$\text{min\_travel} = \text{Manhattan}(p, d)$$
  $$\text{slack} = \max(\text{min\_slack}, \lceil \alpha \times \text{min\_travel} \rceil)$$
  $$\text{deadline} = \text{release\_time} + \text{slack}$$
  where $\alpha =$ `deadline_factor` controls deadline tightness.

### 2. Real-Time Scheduling Policies (`inc/DeadlineScheduler.h`)
- **FIFO** (First-In-First-Out): Assigns unassigned tasks ordered by `release_time`.
- **EDF** (Earliest-Deadline-First): Prioritizes tasks with earliest absolute deadlines (optimal single-channel real-time policy).
- **DEADLINE_AWARE** (Least Slack First / Urgency Score): Computes per-agent urgency accounting for travel distance from current agent location:
  $$\text{urgency} = (\text{deadline} - t) - (\text{dist}(\text{agent}, \text{pickup}) + \text{dist}(\text{pickup}, \text{delivery}))$$
  Tasks with minimum remaining slack after estimated travel are scheduled first.

### 3. Performance Metrics & Tracking (`inc/DeadlineMetrics.h`)
- **Deadline Satisfaction Rate**: $\frac{\text{tasks\_on\_time}}{\text{tasks\_total}}$
- **Task Tardiness**: $\max(0, \text{finish\_time} - \text{deadline})$ (average and maximum).
- **Per-Task Record CSV**: `task_id, pickup, delivery, release_time, deadline, finish_time, tardiness, status`.
- **Time-Series Snapshots**: Rolling completion and deadline satisfaction recorded every simulation window.

### 4. Running & Plotting Deadline Experiments
```bash
# Run simulation with deadline-aware workload and EDF policy:
./run.sh --scenario=KIVA -m maps/kiva.map -k 100 --solver=ECBS \
  --deadline=1 --task_arrival_rate=2.0 --deadline_factor=1.8 --policy=EDF \
  --csv_metrics=exp/deadline_results.csv --tasks_csv=exp/tasks.csv --snapshot_csv=exp/snapshots.csv

# Generate deadline analysis plots and summary table:
python3 scripts/plot_deadline_metrics.py \
  --metrics-csv exp/deadline_results.csv \
  --snapshots-csv exp/snapshots.csv \
  --output-dir exp/plots
```

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
  - Working baseline build on Linux & macOS, `ThreadPool.h` & `ParallelExecutor.h` integration and tests, unified CLI argument system, `build.sh` / `run.sh` / CI scripts, automated experiment sweeper.
- **Person B (Deadline-Aware Workload)**:
  - Task arrival generator (Poisson), deadline assignment, Earliest-Deadline-First / deadline-recovery scheduling, tardiness logging.
- **Person C (GD-RHCR Parallel Core)**:
  - Spatial visibility grouping algorithm, concurrent group solver dispatch using `ParallelExecutor`, merging group paths into global plan.
- **Person D (Evaluation & Benchmarking)**:
  - Experiment sweeps over thread count ($1, 2, 4, 8$), agent count ($50 \dots 800$), and arrival rates; speedup curves, throughput comparison vs. paper claims.
