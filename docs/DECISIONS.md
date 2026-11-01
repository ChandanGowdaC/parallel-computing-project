# Engineering Decisions & Architecture Log

This document records all architectural choices, assumptions, trade-offs, and integration fixes across the GD-RHCR project.

---

## Decision Log

### D-001: Target Hardware Environment & Thread Configuration
* **Date:** 2026-10-30
* **Context:** The experiment campaign requires profiling on target hardware without fabricating or extrapolating performance curves.
* **Hardware Profile:**
  - **Processor:** Apple M3 Pro
  - **Physical Cores:** 11 total (5 Performance cores + 6 Efficiency cores)
  - **Logical Cores:** 11 (Apple Silicon does not feature SMT / Hyperthreading)
  - **Memory:** 18 GB Unified Memory (LPDDR5)
  - **Operating System:** macOS Darwin 27.0.0 (arm64)
  - **Compiler:** Apple clang version 21.0.0 (`clang-2100.3.34.2`)
  - **Optimization Flags:** `-O3 -DNDEBUG` (CMake Release)
* **Decision:**
  - Thread counts evaluated: $p \in \{1, 2, 4, 8, 11\}$ as physical scaling, with $p = 16$ included specifically to measure oversubscription overhead on an 11-core topology.
  - SMT/Turbo note: No SMT present. Heterogeneous architecture (P-cores vs. E-cores) will naturally exhibit non-linear scaling past 5 threads when tasks spill over to E-cores. This will be analyzed transparently in Phase 4 rather than smoothed out.

---

### D-002: Real-Time Planning Budget Coupling Model
* **Date:** 2026-10-30
* **Context:** In synchronous discrete lifelong MAPF simulations, simulated timesteps advance by window $h$ regardless of wall-clock planning time $T_{\text{plan}}$. Under this naive model, a planner taking 10 seconds per cycle finishes at the exact same simulated timestep as a planner taking 10 milliseconds, making deadline satisfaction completely decoupled from parallel speedup.
* **Mechanism:**
  - Define planning time budget per replan cycle $h$:
    $$B_{\text{plan}} = h \times \tau$$
    where $\tau$ is the wall-clock time budget per simulated timestep (e.g., $\tau = 0.05$ s, yielding $B = 0.5$ s for $h = 10$).
  - If $T_{\text{plan}} \le B_{\text{plan}}$, planning completes within budget; agents execute new plans immediately at timestep $t$.
  - If $T_{\text{plan}} > B_{\text{plan}}$ (budget overrun), agents cannot receive new plans in time. The system records a budget violation, and agents must wait / buffer for overrun timesteps:
    $$\Delta t_{\text{overrun}} = \left\lceil \frac{T_{\text{plan}} - B_{\text{plan}}}{\tau} \right\rceil$$
    This delay directly defers physical movement, increasing task delivery latency and inducing tardiness on tight deadlines.
  - **Ground Rule Adherence:** Applied identically to all variants ($V0$ sequential baseline, $V1$ single-thread GD-RHCR, and $V2$ multi-thread GD-RHCR) to ensure fair comparison.

---

### D-003: Thread-Local MAPF Solver Factory for Safe Concurrency
* **Date:** 2026-10-30
* **Context:** Base RHCR solvers (`PBS`, `ECBS`, `SIPP`, `StateTimeAStar`) contain mutable internal state (e.g., search trees, conflict lists, reservation tables). Calling a shared solver across multiple threads causes fatal data races.
* **Decision:**
  - The underlying map graph (`BasicGraph` / `KivaGrid`) is read-only during planning and safe to share across threads.
  - For parallel group execution, we employ a thread-safe factory pattern: each worker thread / group task instantiates its own `MAPFSolver` and `SingleAgentSolver` instances on demand.
  - Thread pool workers execute isolated group sub-problems without locking or shared memory contention.

---

### D-004: Fallback Solver and Merge Conflict Resolution
* **Date:** 2026-10-30
* **Context:** When visibility radius $V < 2w$, agents in different spatial groups might generate overlapping trajectories near component boundaries. Furthermore, an individual group solve may reach its timeout.
* **Decision:**
  - GD-RHCR validates all merged paths using `validate_joint_paths()`.
  - If all groups succeed and zero collisions exist, the parallel plan is committed.
  - If any group times out or an inter-group conflict is detected, the planner invokes the sequential fallback solver (standard RHCR sequential solve on the full instance or conflicting subset), logs a fallback event in metrics, and commits the conflict-free fallback paths.
  - Guaranteed invariant: Executed paths are 100% collision-free at all timesteps.

---

### D-005: CLI & Metrics Schema Harmonization
* **Date:** 2026-10-30
* **Context:** Incompatibilities exist between:
  1. `driver.cpp` options vs. `run_experiments.sh` flags (`--agents` vs. `--agentNum`, `--simulation_timesteps` vs. `--simulation_time`, `--planning_horizon` vs. `--simulation_window`, etc.).
  2. `Metrics.h` vs. `metrics/metrics_logger.h` vs. `analysis/aggregate_results.py`.
* **Decision:**
  - Update `driver.cpp` Boost Program Options to accept standard aliases (`--agents` alongside `-k`/`--agentNum`, `--simulation_timesteps` alongside `--simulation_time`, `--planning_horizon` alongside `--simulation_window`, `--visibility_radius` alongside `--vis_radius`, etc.).
  - Unify metrics logging to produce the exact schema defined in `metrics_schema.json` and consumed by `aggregate_results.py` and `plot_results.py`.
  - Remove synthetic stub data and generate all summary tables and plots directly from real execution traces.

---

### D-006: Feasibility Probe Findings on Spatial Group Distribution (Percolation)
* **Date:** 2026-10-30
* **Context:** Step 2 feasibility probe on KIVA warehouse map ($33 \times 46$, 1,278 walkable cells) across $N \in \{100, 400, 800\}$ and $V \in \{2, 4, 6, 8, 10, 15, 20\}$ (where $w = 10$, so $V = 2w = 20$).
* **Empirical Findings:**
  1. **At theoretical bound $V = 2w = 20$:** A single giant connected component forms for all density levels. For $N = 400$ and $N = 800$, the largest group holds **100% of all agents** (1 group of size 400 or 800).
  2. **At moderate radius $V \in [4, 10]$:** Percolation occurs rapidly due to high warehouse density. For $N = 400$ (density ~31%) and $N = 800$ (density ~63%), the largest group holds **100% of all agents** for any $V \ge 4$.
  3. **Multi-group decomposition:** Meaningful group decomposition only occurs when:
     - Agent count is small ($N = 100$, $V \le 4$, yielding 23–68 groups with mean size 1.5–4.4); OR
     - Visibility radius is small ($V = 2$, yielding ~32 groups at $N = 400$ with max group size ~140, largest fraction 35%).
* **Consequence for GD-RHCR:**
  - If $V \ge 2w = 20$ is strictly required, group decentralization on dense maps devolves into a single monolithic group, eliminating parallel speedup.
  - To achieve thread-level speedup via spatial decomposition on dense warehouse maps, $V$ must be set to small values ($V \in \{2, 3, 5\}$), relying on the merge collision verifier and sequential fallback to handle inter-group boundary conflicts.

---

### D-007: Domain Workload Scope and macOS Execution Profile
* **Date:** 2026-10-30
* **Workload Scope:**
  - **KIVA Warehouse (`KivaSystem`):** Full lifelong MAPD domain with Poisson task arrivals, per-task deadlines, and scheduling policies (FIFO, EDF, DEADLINE_AWARE).
  - **Sorting Center (`SortingSystem`):** Used exclusively for parallel throughput and scaling benchmarks ($E_1, E_3$) without deadline tracking, testing high-agent coordination on open sortation layouts.
* **macOS Platform Execution Profile:**
  - **CPU Pinning:** macOS Darwin does not support POSIX thread affinity (`pthread_setaffinity_np` / `taskset`). Threads are scheduled across Apple M3 Pro's 5 Performance and 6 Efficiency cores by the Darwin kernel. To compensate for cross-core scheduling noise, all primary benchmark configurations will evaluate $\ge 10$ independent random seeds, reporting median and interquartile range (IQR).
  - **Determinism Coupling Rule:** Real-time planning-budget coupling (`--realtime_coupling`) is strictly disabled (`off`) for all Phase 1 determinism and equivalence tests (C1) to prevent clock jitter from affecting path equivalence.
  - **Thermal & Power Tracking:** Experiment harnesses log power source (AC power verified) and thermal throttle states before and after benchmark batches.

---

### D-008: Fine-Grained Per-Plan-Cycle Timing Breakdown
* **Date:** 2026-10-30
* **Context:** To isolate parallel bottlenecks, every replanning episode must report an exact, microsecond-resolution wall-clock breakdown without observer distortion.
* **Instrumentation Added:**
  - $t_{\text{partition}}$: Time for `partition_agent_groups()` BFS/connected-components.
  - $t_{\text{dispatch}}$: Time to generate `GroupPlanningTask` structs and enqueue them into `ThreadPool`.
  - $t_{\text{solve\_min}}, t_{\text{solve\_mean}}, t_{\text{solve\_max}}$: Solvers' individual execution runtimes across worker threads.
  - $t_{\text{barrier\_wait}}$: Coordinator/worker synchronization idle wait time at the thread-pool barrier.
  - $t_{\text{merge}}$: Time to merge group candidate trajectories and verify vertex/edge collision freedom.
  - $t_{\text{serial\_rest}}$: All remaining serial overhead outside the parallel solve phase (including graph/agent updates and sequential fallback if triggered).
* **Metrics Schema Integration:**
  - Updated `metrics/metrics_logger.h` (`struct EpisodeMetrics`), `metrics/metrics_schema.json` (`episode_level_csv`), and `BasicSystem::solve_gd_rhcr()` to log all breakdown components into `episodes_<run_id>.csv`.

---

### D-009: Phase 2 Parallel Performance Engineering Optimizations
* **Date:** 2026-10-30
* **Systematic Optimizations Applied (in prescribed prompt order):**
  1. **False Sharing & Cache-Line Contention:**
     - Aligned `queue_mutex`, `condition`, `stop`, and `tasks` in `inc/ThreadPool.h` with `alignas(64)`.
     - Aligned `ParallelExecutionStats` with `alignas(64)` to isolate coordinator timers from worker CPU cache lines.
  2. **Lock Contention on Thread-Pool Queue:**
     - Replaced individual $O(n)$ lock acquisitions with `ThreadPool::enqueue_bulk()`: all $n$ group closures are enqueued under a single `std::unique_lock<std::mutex>`, followed by a single `condition.notify_all()`.
     - *Measured Result:* Dispatch time $t_{\text{disp}}$ on SORTING 200 agents (8 threads) dropped from $0.103\text{ ms}$ to $0.027\text{ ms}$ (**3.8x reduction**).
  3. **Memory Allocation Contention:**
     - Replaced per-task dynamic heap allocation (`make_unique<SIPP>()` / `make_unique<PBS>()`) with `thread_local` solver instances.
     - Workers reset internal state via `mapf.clear()` and `mapf.initial_constraints.clear()`, avoiding hundreds of global allocator (`malloc`/`free`) locks per simulation second.
  4. **Load Imbalance & Longest Processing Time First (LPT) Scheduling:**
     - Sorted group tasks descending by agent count (`task.agent_ids.size()` descending, with deterministic `group_id` tie-breaking).
     - Heavy groups begin executing immediately on the first available threads while lighter groups fill remaining capacity, reducing barrier starvation.
  5. **Persistent Thread Pool:**
     - Verified `ParallelExecutor` persistence across all simulation cycles in `BasicSystem`. Worker threads are spawned once upon initialization and joined only at system shutdown.
  6. **Excessive Copying & $O(N \cdot w)$ Spacetime Collision Checking:**
     - Replaced $O(N^2 \cdot w)$ all-pairs path comparison loop in `validate_joint_paths()` with an $O(N \cdot w)$ spacetime occupancy hash map for vertex and edge-swap conflict detection.
     - *Measured Result:* Merge validation time $t_{\text{merge}}$ on 400 agents dropped from $3.2\text{ ms}$ to $0.169\text{ ms}$ (**19x reduction**).
  7. **Sequential-Fallback Threshold (Variant V3):**
     - Added `--sequential_fallback_threshold <int>` flag. When spatial grouping produces $\le K$ groups, GD-RHCR executes sequentially, eliminating thread dispatch and merge validation overhead on configurations with minimal concurrency.

#### Before vs. After Optimization Summary Table

| Metric / Component | Workload Configuration | Before Optimization | After Optimization | Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Dispatch Time $t_{\text{disp}}$** | SORTING $N=200, p=8$ | $0.103\text{ ms}$ | $0.027\text{ ms}$ | **$3.8\times$ faster** |
| **Merge Validation $t_{\text{merge}}$** | SORTING $N=400, p=4$ | $3.20\text{ ms}$ | $0.169\text{ ms}$ | **$18.9\times$ faster** |
| **Heap Allocations per Replan** | KIVA $N=100$, 5 groups | $\sim 10$ heap allocations | $0$ (thread-local reuse) | **100% eliminated** |
| **Phase 1 Correctness Suite** | Automated Tests C1–C6 | 6/6 Passed (100%) | 6/6 Passed (100%) | **Full Equivalence & Zero Violations** |
| **Deterministic Reproducibility**| Seed 42, 3 runs across 1T/2T/4T | Byte-identical | Byte-identical | **100% Reproducible** |

---

### D-010: Holding Time Invariant at Final Goal in PBS, ECBS, and ReservationTable
* **Date:** 2026-10-31
* **Context:** In lifelong MAPD with dynamic tasks (Module B), an agent may reach its delivery goal before the planning window expires ($t < w$). In simulation (`BasicSystem::move()`), agents that reach their destination remain stationary at their final location for the remainder of the window.
* **Root Cause of Collision Bug:**
  - Base RHCR was written assuming synthetic infinite tasks where paths always exceed $w$, so `paths[k]->size() >= window + 1` was presumed true for all agents.
  - When `hold_endpoints == false`, `PBS::find_conflicts` and `ECBS::find_conflicts` only checked conflicts up to `min(size1, size2)`. Timesteps past the end of the shorter agent's path were never checked.
  - Furthermore, `ReservationTable::insertPath2CT` only added constraints up to `path.back().timestep + 1 + k_robust`, rather than holding through the end of the collision window `window`.
  - Consequently, at the PBS root node, another agent was planned to pass directly through the first agent's final location at $t > size1$, leading to simulation collisions in `move()`.
* **Fix Applied:**
  1. `ReservationTable::insertPath2CT`: Updated to reserve `ct[prev->location]` up to `max(window, path.back().timestep) + 1 + k_robust`.
  2. `PBS::find_conflicts` & `ECBS::find_conflicts`: Added check when `size1 != size2` to verify that the longer agent does not occupy the stationary agent's final location `paths[a1_]->back().location` for any $t \in [\min(size1, size2), \max(size1, size2))$.
  3. `GDRHCR::validate_joint_paths`: Updated spacetime occupancy validation to treat agents with $t \ge paths[a].size()$ as occupying `paths[a].back().location`.
* **Verification:** Confirmed 0 collisions across all 50-agent KIVA debug runs, and Phase 1 test suite C1–C6 passing 100%.

---

### D-011: Edge-Swap Conflict Resolution in LRAStar Fallback Solver
* **Date:** 2026-10-31
* **Context:** In large agent instances ($N \ge 400$) on dense maps, PBS search tree size can exceed the 60-second cutoff time. Upon timeout, base RHCR falls back to `LRAStar::resolve_conflicts()`.
* **Root Cause of Collision Bug:**
  - In `LRAStar::resolve_conflicts()`, when $k_{\text{robust}} = 0$, `curr_locations` was unpopulated, and LRA* only evaluated vertex collisions across paths.
  - No edge-swap validation existed, allowing two agents to exchange positions in opposing directions at the same timestep ($(u \to v)$ and $(v \to u)$).
* **Fix Applied:**
  - Added `edge_moves` tracking `(u << 32) | v` in `inc/LRAStar.h` and `src/LRAStar.cpp`.
  - Prior to moving an agent from $prev\_loc$ to $loc$, LRA* checks if $(loc \to prev\_loc)$ was already claimed in the current timestep. If so, a wait step is forced, eliminating edge swap conflicts.
* **Verification:** Test run on $N=400$, seed 100 where PBS timed out at timestep 30 succeeded through timestep 50 with 0 collisions.

---

### D-012: Campaign Pipeline Resume Mode & Automated Figure Generation
* **Date:** 2026-10-31
* **Context:** The pre-registered campaign spans 84 configurations and 580 executions. Long simulation runs require fault-tolerance against interruptions without restarting completed, verified configurations from scratch.
* **Decision:**
  - `experiments/run_full_campaign.py` implements a robust resume check: existing `run_*.csv` and `paths_*.txt` files are verified for collision-freedom. Valid runs are preserved, while any corrupted traces are automatically re-run.
  - Automated post-execution pipeline: Upon campaign completion, the script automatically triggers `analysis/aggregate_results.py` and `analysis/generate_figures.py` to produce final CSV summaries and publication-ready vector SVGs in `results/figures/`.

---

### D-013: Provenance Audit, Commit-Keyed Resume Mode, and Constant-Density Scaling Design
* **Date:** 2026-10-31
* **Context:** Rigorous audit of experiment provenance, verifier horizon, and spatial scaling limitations.
* **Audit Findings & Actions:**
  1. **Provenance Invalidation:**
     - 71 runs generated on 2026-10-30 under commit `69c2217` (`e1_kiva_a100_*` and `e1_kiva_a400_t1_s42`) predated bug fixes D-010 (PBS/ECBS endpoint holding) and D-011 (LRAStar edge-swap resolution).
     - These 71 runs were formally invalidated and deleted from `results/raw/`.
     - The remaining 509 runs were confirmed to be produced under commit `2bd958e`.
  2. **Self-Describing Provenance & Resume Keying:**
     - Added `git_commit` column to `metrics/metrics_schema.json`, `RunConfig`, `metrics_logger.h`, `BasicSystem`, and CLI option `--git_commit` in `driver.cpp`.
     - Updated `experiments/run_full_campaign.py` resume mode to check `run_commit == current_commit`. Any run file lacking a matching commit hash is automatically invalidated and re-run.
  3. **Verifier Horizon & Stationary Holding:**
     - Simulation horizon $T_{\text{sim}} = 50$, $h = 5$, $w = 10$, yielding 10 replan episodes per run.
     - `scripts/verify_collision_freedom.py` verifies all executed timesteps $t \in [0, \max_t]$.
     - Identified that 50 steps is too short for deadline workloads due to 20–30 timestep average travel times (yielding only 1–3 completions per agent and discrete quantization noise). Lengthened deadline horizon to $T_{\text{sim}} = 250$ (50 replanning episodes) for steady-state queue dynamics.
     - Enhanced `verify_collision_freedom.py` to explicitly enforce stationary holding at the final goal location for agents whose paths finish before $\max_t$.
  4. **Constant-Density Warehouse Scaling Design:**
     - Fixed-dimension warehouse maps suffer from spatial percolation as $N$ grows ($N=400$ on fixed $33\times 46$ reaches 31% density, merging all agents into 1 group).
     - Implemented `scripts/tile_maps.py` to tile KIVA warehouse map $1\times 1$ ($N=50$), $2\times 1$ ($N=100$), $2\times 2$ ($N=200$), $4\times 2$ ($N=400$), and $4\times 4$ ($N=800$), strictly preserving agent density ($N/\text{Area} = 50/1518 \approx 0.0329$).
     - Preserves linear group scaling ($4.6 \to 39.0$ groups at $V=4$) and drops largest-group fraction ($46\% \to 16\%$), isolating parallel core scaling from density percolation.






