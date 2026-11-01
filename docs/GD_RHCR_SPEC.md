# Group-Decentralized Rolling-Horizon Collision Resolution (GD-RHCR) Specification

**Reference Paper:**  
*A Theoretical Framework for Parallel Lifelong MAPF Using Group Decentralized Planning*  
**Authors:** Alex DeWeese, Jiaoyang Li, Guannan Qu (arXiv:2608.17928, Aug 2026)  
**Base System:** Rolling-Horizon Collision Resolution (RHCR; Li et al., AAAI 2021)

---

## 1. Executive Summary & Algorithmic Principle

In lifelong Multi-Agent Path Finding (L-MAPF), $N$ agents continuously receive pickup-and-delivery tasks in an obstacle grid. Standard RHCR plans paths over a lookahead time window $w$ and executes them for a simulation window $h \le w$. Replanning is triggered every $h$ timesteps.

While vanilla RHCR scales better than one-shot MAPF, centralized windowed solvers (such as PBS, ECBS, or WHCA*) experience quadratic or exponential slowdowns as agent density increases, since the joint collision-resolution search space grows combinatorially with $N$.

**GD-RHCR** addresses this bottleneck through spatial decomposition:
1. At replanning timestep $t$, an interaction/visibility graph $\mathcal{G}_{\text{vis}} = (\mathcal{A}, \mathcal{E})$ is constructed over all active agents $\mathcal{A}$. An edge $(i, j) \in \mathcal{E}$ exists if and only if the spatial distance between the initial states of agents $i$ and $j$ satisfies $\text{dist}(s_i, s_j) \le V$.
2. The connected components of $\mathcal{G}_{\text{vis}}$ partition the agents into disjoint groups $\mathcal{G}_1, \mathcal{G}_2, \dots, \mathcal{G}_K$.
3. Each group $\mathcal{G}_k$ solves an independent windowed MAPF instance of size $|\mathcal{G}_k| \ll N$ concurrently on a worker thread pool.
4. The group solutions are merged into a joint plan. If inter-group conflicts occur or any group solver fails, a fallback solver resolves the conflicts.

---

## 2. Core Components: Theory vs. Codebase Audit

### 2.1 Partitioning Rule
* **Paper Theory:** Construct communication/visibility graph where edge $(i, j)$ exists if $\text{dist}(s_i, s_j) \le V$. Compute connected components via BFS/DFS/Union-Find.
* **Code Implementation (`inc/GDRHCR.h`):** `partition_agent_groups()` executes BFS/flood-fill over agent IDs using Manhattan distance on `BasicGraph`. Sorts agent IDs deterministically for reproducibility.
* **Status:** **IMPLEMENTED** (Verified by unit tests in `tests/test_gd_rhcr.cpp`).

### 2.2 Visibility Radius $V$
* **Paper Theory:** 
  - If $V \ge 2w$, agents in different groups are separated by more than $2w$ distance at timestep $t$. Since maximum agent speed is $1$ cell/timestep, agents can move at most $w$ steps during the planning horizon $w$. By the triangle inequality:
    $$\text{dist}(s_i, s_j) \le \text{dist}(s_i, p_i(\tau)) + \text{dist}(p_i(\tau), p_j(\tau)) + \text{dist}(p_j(\tau), s_j) \le 2w$$
    Thus, no inter-group collision is geometrically possible when $V \ge 2w$.
  - If $V < 2w$, inter-group collisions are possible near component boundaries, requiring conflict detection or soft constraints.
* **Code Implementation (`inc/GDRHCR.h`):** Parameter `vis_radius` ($V$) is configurable via CLI. Manhattan distance threshold is applied during partitioning.
* **Status:** **IMPLEMENTED**.

### 2.3 Lazy Evaluation
* **Paper Theory:** Evaluates inter-agent interactions lazily during search; agents only consider constraints or merge groups on-demand when paths overlap.
* **Code Implementation:** Our implementation performs **eager spatial partitioning** at each replanning cycle $h$, plans each component to completion, and performs post-hoc validation.
* **Status:** **PARTIAL / DEVIATION** (Eager partitioning is chosen for determinism, predictable thread dispatch, and zero synchronization during inner search loops).

### 2.4 Soft Constraints
* **Paper Theory:** Groups can maintain soft reservation tables or boundary penalties to discourage agents from straying into buffer regions between groups.
* **Code Implementation:** No soft reservation table is populated across group boundaries. Instead, groups plan independently using their own initial reservation/path tables, and `validate_joint_paths()` checks the merged trajectories.
* **Status:** **MISSING / DEVIATION** (We substitute explicit merge validation and sequential fallback, which guarantees 100% collision freedom without tuning soft penalty weights).

### 2.5 Fallback Solver
* **Paper Theory:** If a group solver times out or inter-group conflicts arise after merging, a fallback solver (e.g., sequential prioritized planning, WHCA*, or joint PBS) is invoked.
* **Code Implementation:**
  - `validate_joint_paths()` correctly detects vertex conflicts ($p_i(t) = p_j(t)$) and edge conflicts ($p_i(t) = p_j(t+1) \land p_i(t+1) = p_j(t)$).
  - In `inc/GDRHCR.h`, `merge_group_results()` returns `false` if conflicts or group failures occur.
  - However, in `src/BasicSystem.cpp`, the parallel dispatch and fallback invocation were **not hooked up** into `BasicSystem::solve()`.
* **Status:** **PARTIAL** (Algorithm defined in header, but integration into the main simulation loop is pending).

### 2.6 Parallel / Asynchronous Execution
* **Paper Theory:** Groups are dispatched asynchronously across available CPU cores.
* **Code Implementation:** `solve_group_tasks()` in `inc/GDRHCR.h` uses `ParallelExecutor::parallel_map()` to distribute tasks across a thread pool with a join barrier.
* **Status:** **IMPLEMENTED** (Fork-join model; thread safety requires independent solver instances per worker).

---

## 3. Implementation Status Matrix

| Component | Paper Specification | Code Status | Notes / Deviations |
| :--- | :--- | :--- | :--- |
| **Agent Partitioning** | Connected components with $\text{dist} \le V$ | **IMPLEMENTED** | Deterministic BFS in `GDRHCR.h` |
| **Visibility Radius $V$** | Configurable spatial radius | **IMPLEMENTED** | Supported via `--vis_radius` CLI flag |
| **Independent Solvers** | Group-local windowed MAPF | **PARTIAL** | Core functions in `GDRHCR.h`; requires thread-safe factory |
| **Fork-Join Parallelism** | Concurrent group solves via thread pool | **IMPLEMENTED** | `ParallelExecutor` wraps `ThreadPool` |
| **Plan Merging** | Stitches per-group trajectories | **IMPLEMENTED** | Verified in `tests/test_gd_rhcr.cpp` |
| **Collision Verifier** | Vertex & edge swap checker | **IMPLEMENTED** | `validate_joint_paths()` checks full horizon |
| **Lazy Evaluation** | On-demand group expansion | **DEVIATION** | Eager partitioning used for determinism |
| **Soft Constraints** | Boundary penalty heuristic | **DEVIATION** | Replaced by strict merge validation + fallback |
| **Fallback Solver** | Fallback on merge conflict/timeout | **PARTIAL** | Needs wiring into `BasicSystem::solve()` |
| **Simulation Loop Integration** | Call GD-RHCR when `--parallel` | **MISSING** | `BasicSystem::solve()` calls only sequential solver |
| **Real-time Planning Budget** | Coupling planning latency to delays | **MISSING** | Required for deadline operational advantage |

---

## 4. Literature Comparison Nuance (Verification of arXiv:2608.17928)

* **Claim in project prompt / notes:** "up to 24.9x lower per-plan cost and 57.7% throughput improvement at 800 agents on a warehouse map."
* **Paper Verification:**
  - The **57.7% throughput improvement** reported in the paper is measured relative to **PIBT (Priority-Inheritance Backtracking)** under high agent density, NOT relative to vanilla sequential RHCR.
  - The **24.9x per-plan speedup** represents the reduction in planning time achieved on multi-core server hardware at 800 agents.
  - In our benchmark report, we will explicitly distinguish between comparisons against the sequential baseline ($V0$), 1-thread GD-RHCR algorithmic baseline ($V1$), and literature benchmarks.
