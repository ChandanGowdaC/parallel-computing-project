# Pre-Registered Experiment Matrix & Evaluation Campaign Plan

## 1. Experimental Methodology & Hardware Ground Truth
* **Platform:** Apple M3 Pro (11 physical cores: 5 Performance cores + 6 Efficiency cores, no SMT), 18 GB Unified Memory, macOS Darwin 27.0.0, Apple clang 21.0.0 (`-O3 -DNDEBUG`).
* **Timing & Clocks:** Monotonic wall-clock timing via `std::chrono::steady_clock`. All reported summary metrics use **median** and **interquartile range (IQR)** across 10 independent random seeds (`seeds: 42, 100, 2026, 3141, 5926, 8421, 9001, 1234, 7777, 8888`).
* **Fairness Guarantee:** Baselines ($V_0$) and parallel variants ($V_1, V_2$) run with identical compiler flags, identical maps, identical random seeds, and identical monotonic timing routines.
* **Separation of Effects:**
  - **Algorithmic Effect ($V_1$ vs. $V_0$):** GD-RHCR with 1 worker thread vs. vanilla sequential RHCR. Quantifies the algorithmic overhead or benefit of spatial graph partitioning, boundary merge validation, and sequential fallback without any thread concurrency.
  - **Parallel Scaling Effect ($V_2$ vs. $V_1$):** GD-RHCR with $p \in \{2, 4, 8, 11, 16\}$ threads vs. single-threaded GD-RHCR ($V_1$). Strictly measures parallel speedup, hardware efficiency, load balancing, and thread-pool scaling.

---

## 2. Pre-Registered Experiment Priority Matrix

### **Tier 1 (Core Milestones — Highest Priority)**

#### **E1: Strong Scaling Benchmark**
* **Workload:** Fixed agent counts on KIVA fulfillment map ($33 \times 46$) and Sorting Center map ($37 \times 77$).
* **Configurations:**
  - KIVA ($N = 200, 400$, $V = 5$, $h = 5$, $w = 10$)
  - Sorting Center ($N = 400, 800$, $V = 5$, $h = 5$, $w = 10$)
* **Threads:** $p \in \{1, 2, 4, 8, 11, 16\}$ (where 11 = all physical cores, 16 = oversubscription test)
* **Metrics:** Total solver time, per-cycle plan latency breakdown ($t_{\text{part}}, t_{\text{solve}}, t_{\text{merge}}$), speedup $S_p = T_1 / T_p$, parallel efficiency $E_p = S_p / p$.

#### **E3: Problem-Size Scaling & Crossover Point**
* **Workload:** Fixed thread counts ($p \in \{1, 4, 8\}$) sweeping agent count $N \in \{25, 50, 100, 200, 400, 600, 800\}$.
* **Goal:** Identify the exact crossover point where parallel task dispatch and thread synchronization overhead dominate vs. where parallel speedup pays off.
* **Metrics:** Per-plan latency, throughput (tasks/timestep), and speedup curve.

#### **E6: Fallback Solver and Merge Ablation**
* **Workload:** KIVA with $N = 100$ and $N = 400$ across $V \in \{2, 5, 10\}$.
* **Goal:** Quantify the frequency of inter-group boundary conflicts, the invocation rate of sequential fallback, and the runtime cost of merge verification.
* **Metrics:** Number of fallbacks invoked, post-merge collision count (invariant = 0), fraction of CPU cycles spent in fallback vs. parallel solve.

#### **E7: Real-Time Planning Budget Coupling**
* **Workload:** KIVA with deadline-aware workload ($N = 50$, Poisson arrival $\lambda = 1.0$, deadline factor $2.0$).
* **Coupling Settings:** $\tau \in \{0.001, 0.005, 0.01, 0.05, 0.1\}$ seconds per tick.
* **Goal:** Empirically demonstrate how parallel replanning speedup directly translates into reduced wall-clock overruns, reduced agent stalls, higher throughput, and lower task tardiness.
* **Metrics:** Budget violations, total delay timesteps, deadline satisfaction rate, avg/max tardiness.

#### **E8: Memory & Resource Characterization**
* **Workload:** Peak resident set size (RSS), heap allocation churn, and scaling across $p \in \{1, 2, 4, 8, 11\}$.
* **Metrics:** Peak memory (MB), per-cycle allocation time, worker thread idle/barrier times.

---

### **Tier 2 (Structural Sensitivity)**

#### **E4: Visibility Radius ($V$) Sensitivity**
* **Workload:** KIVA ($N = 100, 400$), fixed threads $p = 4$.
* **Radii Swept:** $V \in \{2, 3, 5, 8, 15, 20\}$.
* **Metrics:** Group count distribution (mean, max), largest-group fraction, inter-group boundary conflict rate, total planning time.

---

### **Tier 3 (Extended Domain Scaling — Reduced Execution)**

#### **E2: Weak Scaling (Reduced)**
* **Workload:** 50 agents per thread on Sorting Center ($p \in \{1, 2, 4, 8\}$, $N \in \{50, 100, 200, 400\}$).
* **Metrics:** Weak scaling efficiency $E_{\text{weak}} = T_1(N_0) / T_p(p \cdot N_0)$.

#### **E5: Scheduling Policy Comparison under Load (Reduced)**
* **Workload:** KIVA with $N = 50$, comparing `FIFO`, `EDF`, and `DEADLINE_AWARE` across arrival rates $\lambda \in \{0.5, 1.0, 2.0\}$.
* **Metrics:** Deadline satisfaction rate, average tardiness, completed tasks.

---

## 3. Runtime & Smoke-Run Estimates

| Execution Phase | Scope | Total Runs | Est. Time per Run | Total Est. Wall Time |
| :--- | :--- | :--- | :--- | :--- |
| **Smoke Run** | 1 seed, $T = 20$, Tier 1 subset (E1, E3, E7) | 18 configurations | 0.05 – 0.5 s | **~1.5 minutes** |
| **Tier 1 Full Campaign** | 10 seeds, $T = 50$, E1 + E3 + E6 + E7 + E8 | ~120 runs | 0.2 – 2.0 s | **~25 minutes** |
| **Tier 2 Campaign** | 10 seeds, $T = 50$, E4 radius sweep | ~30 runs | 0.2 – 1.5 s | **~8 minutes** |
| **Tier 3 Campaign** | 5 seeds, $T = 50$, Reduced E2 + E5 | ~35 runs | 0.2 – 2.0 s | **~10 minutes** |
| **Total Campaign** | Full pre-registered matrix | **~185 runs** | — | **~45 minutes** |
