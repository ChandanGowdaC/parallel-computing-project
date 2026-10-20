# Literature Comparison — Reference Numbers

## Papers and Claimed Results

| Paper | Method | Key Metric | Value | Agents | Notes |
|-------|--------|-----------|-------|--------|-------|
| DeWeese, Li & Qu (Aug 2026) | GD-RHCR | Throughput improvement over RHCR | **57.7%** | 800 | Warehouse scenario, group-decentralized |
| DeWeese, Li & Qu (Aug 2026) | GD-RHCR | Per-plan computation cost reduction | **24.9×** | 800 | Best case with spatial partitioning |
| Li et al. (2021) | RHCR | Baseline throughput | — | 50–800 | KIVA + sorting maps |
| CPLNS (2024) | Parallel LNS | Computation speedup | **21.95×** | 1000 | Parallel destroy/repair rounds |
| TACKLE / counterfactual-MAPF-LNS | Adaptive LNS | Cost improvement | **≥60%** | 1000+ | On top of MAPF-LNS2 |

## Key Comparisons We Need to Make

### 1. Speedup vs. GD-RHCR Paper (Primary)
- **Their claim**: 24.9× per-plan computation cost with 800 agents
- **Our measurement**: `speedup` column from `speedup_table.csv` at agents=800
- **Expected outcome**: Likely lower due to real implementation overhead (thread management, cache effects, memory contention)
- **If significantly lower**: Report the gap as a legitimate finding — theory vs. practical implementation

### 2. Throughput vs. GD-RHCR Paper (Primary)
- **Their claim**: 57.7% throughput improvement over vanilla RHCR
- **Our measurement**: `throughput_improvement` column from `speedup_table.csv`
- **Calculation**: `(parallel_throughput / sequential_throughput - 1) × 100%`

### 3. Speedup vs. CPLNS (Secondary)
- **Their claim**: 21.95× speedup on 1000-agent instances
- **Our method**: Different (spatial partitioning vs. parallel LNS)
- **Compare**: Our speedup at 800 agents vs. their 21.95× at 1000 agents
- **Note**: Not apples-to-apples; different parallelism strategies

### 4. Deadline Awareness (Novel Contribution by Person B)
- **No direct comparison** exists in the literature for deadline-aware MAPF
- Report absolute numbers: satisfaction rate, tardiness distribution, policy comparison
- This is additional novelty beyond GD-RHCR implementation

## Numbers to Include in the Final Report

```
Our Implementation:
  Max speedup:                  ___× (at ___ agents, ___ threads)
  Average speedup:              ___×
  Max throughput improvement:   ___% (at ___ agents)
  Best efficiency:              ___% (at ___ threads)
  Deadline satisfaction (FIFO): ___% (at λ=___, ___ agents)
  Deadline satisfaction (EDF):  ___% (at λ=___, ___ agents)

Literature Reference:
  GD-RHCR paper speedup:       24.9×
  GD-RHCR paper throughput:    57.7%
  CPLNS speedup:               21.95×
  TACKLE cost improvement:     ≥60%
```

## Citation Format

```bibtex
@article{deweese2026gdrhcr,
  title={Group Decentralized RHCR (GD-RHCR)},
  author={DeWeese, Kevin and Li, Jiaoyang and Qu, Zhongqiang},
  journal={arXiv preprint arXiv:2608.17928},
  year={2026}
}

@inproceedings{li2021rhcr,
  title={Lifelong Multi-Agent Path Finding in Large-Scale Warehouses},
  author={Li, Jiaoyang and others},
  booktitle={AAAI},
  year={2021}
}
```
