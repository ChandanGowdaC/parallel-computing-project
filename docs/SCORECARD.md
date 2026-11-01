# Experimental Metrics Scorecard (code-freeze-v3)

**Project:** Parallel Deadline-Aware Replanning for Lifelong Multi-Agent Pickup and Delivery in Warehouse Environments  
**System:** Group-Decentralized Rolling-Horizon Collision Resolution (GD-RHCR)  
**Git Provenance:** Base `c8d5b8a` (`code-freeze-v3`), Deadline Recalibration `46b5914`, Tag `final-submission`  
**Hardware Profile:** Apple Silicon M3 Pro (11 physical cores: 5 Performance @ 4.05 GHz + 6 Efficiency @ 2.0 GHz; 18 GB Unified Memory; Darwin 27.0.0 arm64)  
**Full Horizon:** $T_{\mathrm{sim}} = 250$ timesteps (50 replanning cycles, $h=5, w=10$).  
**Statistical Rigor:** All values reported with medians and 95% bootstrap confidence intervals ($n_{\mathrm{boot}} = 2000$).

---

## 1. Run Count & Independent Verification Reconciliation

| Campaign / Benchmark | Map & Scale | Configurations Evaluated | Total Runs | Horizon Verified | Collisions Found | Source Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Timing Reconciliation Probe** | Tiled KIVA ($N=400$) | $V \in \{1, 2, 3\}$, $p \in \{1, 4, 8\}$, Uniform & Zoned, 3 tuning seeds | 54 | 54 (100%) | 0 | `docs/DECISIONS.md` (D-020) |
| **Sparse Sorting Center Sweep** | Sorting Map ($77 \times 37$) | $N \in \{25, 50, 100, 200\}$, $V \in \{6, 10\}$, $p \in \{1, 2, 4, 8, 11\}$, 5 seeds | 220 | 220 (100%) | 0 | `results/aggregated/sorting_sparse_summary.csv` |
| **Constant-Density Scaling Matrix** | Tiled KIVA ($N \in \{100, 400, 800\}$) | $V^*=1$ ($p \in \{1, 2, 4, 5, 8, 11\}$) + $V=8$ ($p \in \{1, 8\}$) + $V_0$, 5 seeds | 270 | 270 (100%) | 0 | `results/aggregated/reporting_scaling_summary.csv` |
| **Initial Deadline & Policy Sweep** | Tiled KIVA ($N=400$) | $\tau \in \{12, 20, 50\}\,\mathrm{ms}$, $\lambda \in [0.2, 2.0]$, FIFO/EDF/DA, 5 seeds | 585 | 585 (100%) | 0 | `results/aggregated/deadline_sweep_summary.csv` |
| **Recalibrated Deadline Campaign** | Tiled KIVA ($N=400$) | $k=3, c=100$, $\tau \in \{20, 60\}\,\mathrm{ms}$, $\lambda \in [0.2, 2.0]$, $V_0/V_1/V_2$, 5 seeds | 240 | 240 (100%) | 0 | `results/aggregated/deadline_recalibrated_summary.csv` |
| **Grand Total** | Full Experimental Matrix | All campaigns and sweeps | **1,369** | **1,369 (100%)** | **0** | Verified by independent checker |

*(Note on previous counts: 1,075 runs referred to the three reporting matrices $220 + 270 + 585 = 1,075$, omitting the 54 tuning probe runs; adding the 54 tuning runs gives 1,129 runs; adding the final 240 recalibration runs yields 1,369 runs).*

---

## 2. Claims-vs-Evidence Mapping

| Claim Stated in Presentation / Report | Quantitative Finding | Supporting Table / Figure | Underlying Data File |
| :--- | :--- | :--- | :--- |
| **C1. Algorithmic Decomposition Benefit** | $S_{\mathrm{alg}} = 2.14\times\text{--}5.69\times$ at $N \ge 400$ ($V^*=1$ vs $V_0$) | Table 5.1, Figure 5 | `results/aggregated/reporting_scaling_summary.csv` |
| **C2. Hardware Multi-Threading Speedup** | $S_{\mathrm{thread}} = 1.41\times\text{--}1.51\times$ at $p=4$ ($V_2$ vs $V_1$) | Table 5.1, Figure 1 | `results/aggregated/reporting_scaling_summary.csv` |
| **C3. Small-Instance Decomposition Slowdown** | $N=100$ incurs net slowdown ($S_{\mathrm{total}} = 0.86\times$ [0.79, 1.12] Uniform) | Table 5.1, Headline Table | `results/aggregated/reporting_scaling_summary.csv` |
| **C4. Graham-Brent Span Limitation** | $p=2 \to 4$ speedup plateaus because $W/S \approx 1.43\text{--}1.66$ | Table 2.2, Figure 2 | `docs/DECISIONS.md` (D-020) |
| **C5. Density Collapse Boundary** | Performance collapses between 4.7% and 9.4% density ($S_{\mathrm{total}} = 0.75\times$) | Table 4.1, Figure 4 | `results/aggregated/sorting_sparse_summary.csv` |
| **C6. Apple Silicon Core Asymmetry** | Scaling peaks at $p=4\text{--}5$; $p \ge 8$ Karp-Flatt surges to $0.99$ (E-core hypothesis) | Section 3, Figure 1, Figure 3 | `results/aggregated/reporting_scaling_summary.csv` |
| **C7. Real-Time Planning Latency** | Parallel replanning reduces per-cycle planning latency in simulation ($9\text{--}12\,\mathrm{ms}$ vs $>100\,\mathrm{ms}$) | Section 6, Figure 6 | `results/aggregated/deadline_recalibrated_summary.csv` |
| **C8. Plan-Quality Throughput Parity** | Parallel GD-RHCR preserves $97.8\%–101.1\%$ of centralized throughput | Table 5.1 | `results/aggregated/reporting_scaling_summary.csv` |

---

## 3. Metric Scorecard: Groups A through E

### Group A: Verification & Reproducibility Parity
- **Independent Full-Horizon Collision Rate:** **0.0%** ($0$ collisions across all $1,369$ runs, $T_{\mathrm{sim}}=250$; Source: `scripts/verify_collision_freedom.py`).
- **Sequential Equivalence Gate ($V_0$ vs Vanilla RHCR):** **100% bit-for-bit identical** (SHA-256 match, $n=3$ seeds; Source: `tests/test_c1_determinism.py`).
- **Concurrency & Memory Safety:** **0 data races, 0 heap leaks** under ThreadSanitizer & AddressSanitizer at $p \in \{2, 4, 8\}$; Source: `tests/test_parallel_executor.cpp`.
- **Bit-for-Bit Determinism across Threads:** **100% reproducible** across independent runs at fixed seed; Source: `tests/test_c6_reproducibility.py`.

### Group B: Graham-Brent Analytical Bounds & Timing Waterfall ($N=400, T_{\mathrm{sim}}=250$)
- **Serial Phases Duration ($T_{\mathrm{serial}} = t_{\mathrm{part}} + t_{\mathrm{disp}} + t_{\mathrm{merge}} + t_{\mathrm{rest}}$):** **$85.6\text{--}91.9\,\mathrm{ms}$** ($\approx 2.2\%$ of run planning time).
- **Theoretical Maximum Parallelism ($W/S$):** **$1.43$** (Uniform), **$1.66$** (Zoned) (Source: `docs/DECISIONS.md` D-020).
- **Graham-Brent Bound Compliance ($T_{\mathrm{low}} \le T_{\mathrm{meas}} \le T_{\mathrm{up}}$):** **Verified across all 8 configurations of the timing reconciliation probe** ($N=400$, 54 runs across tuning seeds 101, 202, 303): 8/8 satisfied $T_{\mathrm{low}} \le T_{\mathrm{meas}} \le T_{\mathrm{up}}$ without exception (Source: `docs/DECISIONS.md` D-020).
- **Karp-Flatt Metric Diagnostic vs. Serial Code:** Measured $e(4) = 0.608\text{--}0.627$ and $e(8) = 0.760\text{--}0.994$. The limiter is the **critical-path span ($W/S \approx 1.4\text{--}1.7$)**, not unparallelized serial instructions ($T_{\mathrm{serial}} \approx 2.2\%$). The single largest group accounts for $60\%–74\%$ of the work, forcing threads to wait at the join barrier.

### Group C: Constant-Density Scaling Matrix (Full 6-Row Uniform & Zoned Side-by-Side)

> Reported over 5 reporting seeds `[42, 100, 2026, 3141, 5926]`, $T_{\mathrm{sim}}=250$, 50 replanning cycles. $V^*=1, p=4$. Shown side-by-side to highlight both small-scale slowdown and large-scale acceleration without cherry-picking.

| $N$ | Workload | Planning Time (ms) [95% CI] | $S_{\mathrm{alg}} = \frac{T(V_0)}{T(V_1)}$ [95% CI] | $S_{\mathrm{thread}} = \frac{T(V_1)}{T(V_2)}$ [95% CI] | $S_{\mathrm{total}} = \frac{T(V_0)}{T(V_2)}$ [95% CI] | Fallback Rate % | Throughput Parity vs $V_0$ |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **100** | **Uniform** | 1,894.0 [1419.3, 1966.3] | $0.78\times$ [0.71, 0.94] | $1.11\times$ [1.10, 1.20] | **$0.86\times$ [0.79, 1.12]** | 0.0% | 100.7% [99.2, 101.9] |
| **100** | **Zoned** | 1,027.1 [867.4, 1135.0] | $1.06\times$ [0.94, 1.22] | $1.14\times$ [1.13, 1.18] | **$1.24\times$ [1.08, 1.38]** | 0.0% | 97.8% [97.2, 100.4] |
| **400** | **Uniform** | 3,158.9 [2754.3, 4131.1] | $2.14\times$ [1.74, 2.39] | **$1.51\times$ [1.39, 1.62]** | **$3.24\times$ [2.42, 3.82]** | 8.0% | 100.8% [97.3, 102.8] |
| **400** | **Zoned** | 2,612.1 [2535.6, 3877.3] | $3.31\times$ [2.94, 3.59] | **$1.46\times$ [1.39, 1.51]** | **$4.92\times$ [4.08, 5.14]** | 2.0% | 100.2% [98.5, 101.7] |
| **800** | **Uniform** | 7,853.1 [5605.8, 8162.5] | $2.67\times$ [2.59, 3.22] | **$1.41\times$ [1.34, 1.57]** | **$3.76\times$ [3.47, 5.04]** | 20.0% | 101.1% [100.4, 103.4] |
| **800** | **Zoned** | 5,664.9 [5449.1, 7107.5] | $5.69\times$ [4.86, 6.28] | **$1.41\times$ [1.30, 1.47]** | **$7.93\times$ [6.33, 9.25]** | 4.0% | 99.9% [98.6, 100.3] |

*(At $N=800$ Zoned with $p=2$, $S_{\mathrm{thread}} = 1.42\times$ [1.35, 1.45] and $S_{\mathrm{total}} = 7.98\times$ [6.62, 9.10]; at $p=8$, performance degrades to $4.59\times$ due to Efficiency-core clock skew. The best-case $7.98\times$ is an outcome of the full matrix, not a standalone headline).*

### Group D: Sparse Sorting Center Regime Map ($T_{\mathrm{sim}}=250$, 5 Seeds, $n=5$)
- **Sparse Operating Regime ($N=25, \rho=1.2\%, V=6, p=4$):** $S_{\mathrm{alg}} = 1.87\times$ [1.74, 2.01], $S_{\mathrm{thread}} = 1.58\times$ [1.44, 1.68], **$S_{\mathrm{total}} = 3.02\times$ [2.81, 3.16]**, Fallback: 0.0%, Merges: 0.0%.
- **Optimal Sparse Scaling ($N=50, \rho=2.4\%, V=6, p=4$):** $S_{\mathrm{alg}} = 2.40\times$ [2.08, 2.76], $S_{\mathrm{thread}} = 1.57\times$ [1.45, 1.68], **$S_{\mathrm{total}} = 3.81\times$ [3.33, 4.08]**, Fallback: 0.0%, Merges: 0.0%.
- **Moderate Density ($N=100, \rho=4.7\%, V=6, p=2$):** $S_{\mathrm{alg}} = 1.72\times$ [1.60, 2.21], $S_{\mathrm{thread}} = 1.22\times$ [1.18, 1.29], **$S_{\mathrm{total}} = 2.10\times$ [2.01, 2.79]**, Fallback: 1.2%, Merges: 4.8%.
- **Density Collapse ($N=200, \rho=9.4\%, V=6, p=4$):** $S_{\mathrm{alg}} = 0.75\times$ [0.71, 0.78], $S_{\mathrm{thread}} = 1.00\times$ [0.98, 1.03], **$S_{\mathrm{total}} = 0.75\times$ [0.69, 0.80]**, Fallback: 4.0% [0.0, 4.0], Max Group Frac: 0.945 [0.934, 0.963].  
  *(The sparse-sorting collapse at $N=200, \rho=9.4\%, V=6, p=4$ is characterized by a critical-path span bottleneck: 94.5% of agents coalesce into a single group, yielding $S_{\mathrm{thread}} = 1.00\times$ and $S_{\mathrm{total}} = 0.75\times$ with 4.0% [0.0, 4.0] fallbacks).*

### Group E: Real-Time Replanning Under Deadline Pressure (Exploratory Synthetic Stress Test)
> *Disclaimer: Because V0 relaxed-tau does not reach >=90% satisfaction (reaching 43%–63% due to late-arriving tasks being truncated at T_sim=250), this entire section is strictly exploratory and excluded from headline performance claims.*
- **D1 (Deadline Satisfaction %):** At $\tau=20\,\mathrm{ms}, \lambda=2.0$, $V_0 = 4.0\%$ [0.3, 5.1] vs $V_2 = 19.7\%$ [2.2, 42.4] (Uniform); $V_0 = 17.0\%$ [16.6, 21.4] vs $V_2 = 51.2\%$ [16.8, 54.6] (Zoned).
- **D2 (Max Sustainable $\lambda$ at $\ge 90\%$ Satisfaction):** **None** across all variants ($V_0, V_1, V_2$).
- **D4 (Average Tardiness):** Under tight $\tau=20\,\mathrm{ms}, \lambda=2.0$, $V_0 = 1.28$ vs $V_2 = 0.95$ (Zoned). Under relaxed $\tau=60\,\mathrm{ms}$, finished tasks achieve 100% on-time completion ($0$ overdue completed tasks).
- **Aborted-Run Counts:** **0 aborts across all 240 recalibrated runs**.
- **Statistical Overlap & Absence of Claimed Variant Difference:** Confidence intervals for $V_0$ vs $V_2$ overlap substantially at $n=5$, and no variant difference is claimed. Because $W/S$ was not measured for deadline workloads, speedup bounds are not asserted for this section.
- **Per-Cycle Latency Reconciliation:**
  - Full Scaling Benchmark ($N=400$, 100% active agents): $V_2 = \mathbf{52.2\text{--}63.2\,\mathrm{ms/cycle}}$.
  - Dynamic Poisson Deadline Workload ($N=400$, subset of active agents): $V_2 = \mathbf{9.1\text{--}12.1\,\mathrm{ms/cycle}}$ at $\lambda \in [0.2, 1.0]$.
