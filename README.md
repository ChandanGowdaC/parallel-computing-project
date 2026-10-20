# GD-RHCR: Group Decentralized Rolling-Horizon Collision Resolution

## Parallel Computing Project — Evaluation & Benchmarking (Person D)

This repository contains the **experiment harness, analysis pipeline, and report materials** for evaluating the GD-RHCR implementation on top of the RHCR warehouse MAPF simulator.

## Project Structure

```
pc_project/
├── metrics/                          # Interface contract (D defines, B & C write to)
│   ├── metrics_schema.json           # CSV schema specification
│   └── metrics_logger.h              # C++ header-only logger (thread-safe)
│
├── experiments/                      # Experiment orchestration
│   ├── sweep_config.yaml             # Full parameter sweep configuration
│   └── run_experiments.sh            # Automated experiment runner
│
├── analysis/                         # Python analysis pipeline
│   ├── requirements.txt              # Python dependencies
│   ├── generate_stub_data.py         # Synthetic data generator (Week 1)
│   ├── aggregate_results.py          # Cross-seed aggregation + speedup/efficiency
│   └── plot_results.py               # 10 publication-quality figure generators
│
├── results/                          # Output directories
│   ├── raw/                          # Raw per-run CSV files
│   ├── aggregated/                   # Aggregated summary tables
│   └── figures/                      # Generated PNG figures
│
└── report/                           # Report materials
    ├── evaluation_section.tex        # LaTeX template (evaluation section)
    └── literature_comparison.md      # Reference numbers from papers
```

## Quick Start

### 1. Install Python dependencies
```bash
cd analysis
pip install -r requirements.txt
```

### 2. Generate stub data (Week 1 — before solver is ready)
```bash
python3 generate_stub_data.py --output-dir ../results/raw --small
```

### 3. Aggregate results
```bash
python3 aggregate_results.py --input-dir ../results/raw --output-dir ../results/aggregated
```

### 4. Generate figures
```bash
python3 plot_results.py --input-dir ../results/aggregated --output-dir ../results/figures
```

### 5. Run real experiments (after RHCR is built)
```bash
cd experiments
chmod +x run_experiments.sh
./run_experiments.sh --quick      # sanity check
./run_experiments.sh              # full sweep
```

## Interface Contracts (Day 1 Agreements)

### For Person B (Deadline-Aware Workload)
Include `metrics/metrics_logger.h` in your code and call:
```cpp
metrics::MetricsLogger logger("results/raw", config);
logger.logTaskMetrics(task_data);  // per task
```

### For Person C (GD-RHCR Parallel Core)
Include `metrics/metrics_logger.h` in your code and call:
```cpp
metrics::MetricsLogger logger("results/raw", config);
logger.logEpisodeMetrics(episode_data);  // per replan
logger.logRunMetrics(run_data);          // end of run
```

## Generated Figures

| # | Figure | Description |
|---|--------|-------------|
| 1 | `speedup_vs_threads.png` | Speedup vs. thread count (per agent count) |
| 2 | `efficiency_vs_threads.png` | Parallel efficiency vs. thread count |
| 3 | `throughput_comparison.png` | Throughput: sequential vs. parallel |
| 4 | `deadline_vs_arrival_rate.png` | Deadline satisfaction vs. arrival rate |
| 5 | `tardiness_comparison.png` | Average tardiness comparison |
| 6 | `runtime_scalability.png` | Runtime vs. agent count (log scale) |
| 7 | `policy_comparison.png` | Scheduling policy comparison |
| 8 | `speedup_heatmap.png` | Speedup heatmap: agents × threads |
| 9 | `visibility_radius_impact.png` | Impact of visibility radius on speedup |
| 10 | `literature_comparison.png` | Comparison with published results |

## Literature Reference Numbers

| Source | Metric | Value |
|--------|--------|-------|
| GD-RHCR paper (DeWeese et al., 2026) | Throughput improvement | 57.7% |
| GD-RHCR paper | Per-plan computation speedup | 24.9× |
| CPLNS | Computation speedup | 21.95× |
| TACKLE | Cost improvement | ≥60% |
