#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# run_experiments.sh — GD-RHCR Experiment Harness
# Person D — Evaluation & Benchmarking
#
# Sweeps across thread count × agent count × arrival rate × seed
# and logs results to results/raw/ in the schema from metrics_schema.json.
#
# Usage:
#   ./run_experiments.sh                  # full sweep
#   ./run_experiments.sh --quick          # quick sanity check
#   ./run_experiments.sh --sequential     # sequential-only baseline
#   ./run_experiments.sh --parallel       # parallel-only runs
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BINARY="${PROJECT_ROOT}/build/lifelong"
RESULTS_DIR="${PROJECT_ROOT}/results/raw"
LOG_DIR="${PROJECT_ROOT}/results/logs"
SUMMARY_FILE="${PROJECT_ROOT}/results/experiment_summary.csv"

# Default sweep parameters
MAPS=("kiva")
MAP_FILES=("maps/kiva.map")
SCENARIOS=("KIVA")
SOLVER="ECBS"
PLANNING_H=20
PLANNING_W=10
SIM_TIMESTEPS=5000
TIMEOUT=300

# Full sweep parameters (overridden by --quick)
THREAD_COUNTS=(1 2 4 8 16)
AGENT_COUNTS=(50 100 200 400 800)
ARRIVAL_RATES=(0.2 0.5 1.0 2.0 5.0)
VISIBILITY_RADII=(5.0 10.0 20.0)
SEEDS=(42 123 456 789 1024)
SOLVER_MODES=("sequential" "parallel")
POLICIES=("FIFO" "EDF" "DEADLINE_AWARE")

# Max parallel experiment runners
MAX_PARALLEL=4

# ─── Parse CLI args ─────────────────────────────────────────────
QUICK=false
MODE_FILTER=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK=true
            THREAD_COUNTS=(1 2 4)
            AGENT_COUNTS=(50 100)
            ARRIVAL_RATES=(1.0)
            SEEDS=(42)
            SIM_TIMESTEPS=500
            VISIBILITY_RADII=(10.0)
            POLICIES=("FIFO")
            echo ">>> Quick-test mode enabled"
            shift ;;
        --sequential)
            MODE_FILTER="sequential"
            echo ">>> Sequential-only mode"
            shift ;;
        --parallel)
            MODE_FILTER="parallel"
            echo ">>> Parallel-only mode"
            shift ;;
        --dry-run)
            DRY_RUN=true
            echo ">>> Dry-run mode — commands printed but not executed"
            shift ;;
        --threads)
            IFS=',' read -ra THREAD_COUNTS <<< "$2"
            shift 2 ;;
        --agents)
            IFS=',' read -ra AGENT_COUNTS <<< "$2"
            shift 2 ;;
        --seeds)
            IFS=',' read -ra SEEDS <<< "$2"
            shift 2 ;;
        --timeout)
            TIMEOUT="$2"
            shift 2 ;;
        --binary)
            BINARY="$2"
            shift 2 ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick          Run quick sanity check (small sweep)"
            echo "  --sequential     Only run sequential experiments"
            echo "  --parallel       Only run parallel experiments"
            echo "  --dry-run        Print commands without executing"
            echo "  --threads N,M,.. Override thread counts (comma-separated)"
            echo "  --agents N,M,..  Override agent counts (comma-separated)"
            echo "  --seeds N,M,..   Override seeds (comma-separated)"
            echo "  --timeout SEC    Per-run timeout in seconds"
            echo "  --binary PATH    Path to the lifelong binary"
            exit 0 ;;
        *)
            echo "Unknown argument: $1"
            exit 1 ;;
    esac
done

# ─── Preflight checks ───────────────────────────────────────────
if [[ "$DRY_RUN" == false ]]; then
    if [[ ! -x "$BINARY" ]]; then
        echo "ERROR: Binary not found or not executable: $BINARY"
        echo "  Build RHCR first:  cd build && cmake .. && make -j\$(nproc)"
        exit 1
    fi
fi

mkdir -p "$RESULTS_DIR" "$LOG_DIR"

# ─── Summary CSV header ─────────────────────────────────────────
if [[ ! -f "$SUMMARY_FILE" ]]; then
    echo "run_id,timestamp,map_name,scenario,solver,solver_mode,\
thread_count,agent_count,task_arrival_rate,\
planning_horizon_h,planning_window_w,visibility_radius_v,seed,\
simulation_timesteps,total_runtime_ms,solver_runtime_ms,\
num_replan_episodes,num_tasks_generated,num_tasks_completed,\
throughput,num_groups,avg_group_size,max_group_solve_ms,\
num_collisions,deadline_satisfaction_rate,\
avg_tardiness,max_tardiness,num_tasks_overdue,\
scheduling_policy,exit_code" > "$SUMMARY_FILE"
fi

# ─── Counters ────────────────────────────────────────────────────
TOTAL=0
COMPLETED=0
FAILED=0
SKIPPED=0
RUNNING_PIDS=()

count_total_experiments() {
    local count=0
    for mode in "${SOLVER_MODES[@]}"; do
        [[ -n "$MODE_FILTER" && "$mode" != "$MODE_FILTER" ]] && continue
        for map_idx in "${!MAPS[@]}"; do
            for agents in "${AGENT_COUNTS[@]}"; do
                for rate in "${ARRIVAL_RATES[@]}"; do
                    for policy in "${POLICIES[@]}"; do
                        for seed in "${SEEDS[@]}"; do
                            if [[ "$mode" == "sequential" ]]; then
                                count=$((count + 1))
                            else
                                for threads in "${THREAD_COUNTS[@]}"; do
                                    [[ "$threads" -eq 1 ]] && continue  # skip 1-thread parallel (= sequential)
                                    for vr in "${VISIBILITY_RADII[@]}"; do
                                        count=$((count + 1))
                                    done
                                done
                            fi
                        done
                    done
                done
            done
        done
    done
    echo "$count"
}

TOTAL=$(count_total_experiments)
echo "═══════════════════════════════════════════════════════════════"
echo "  GD-RHCR Experiment Sweep"
echo "  Total experiments to run: $TOTAL"
echo "  Results directory: $RESULTS_DIR"
echo "  Binary: $BINARY"
echo "  Timeout: ${TIMEOUT}s per run"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─── Wait for job slot ───────────────────────────────────────────
wait_for_slot() {
    while [[ ${#RUNNING_PIDS[@]} -ge $MAX_PARALLEL ]]; do
        local new_pids=()
        for pid in "${RUNNING_PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                new_pids+=("$pid")
            fi
        done
        RUNNING_PIDS=("${new_pids[@]}")
        if [[ ${#RUNNING_PIDS[@]} -ge $MAX_PARALLEL ]]; then
            sleep 1
        fi
    done
}

# ─── Run a single experiment ────────────────────────────────────
run_single() {
    local map_name="$1"
    local map_file="$2"
    local scenario="$3"
    local mode="$4"
    local threads="$5"
    local agents="$6"
    local rate="$7"
    local vr="$8"
    local seed="$9"
    local policy="${10}"

    local run_id="${map_name}_${mode}_a${agents}_t${threads}_r${rate}_v${vr}_p${policy}_s${seed}"

    # Skip if result already exists
    if [[ -f "${RESULTS_DIR}/run_${run_id}.csv" ]]; then
        echo "  [SKIP] ${run_id} — already completed"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    local log_file="${LOG_DIR}/${run_id}.log"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build command
    local cmd="${BINARY}"
    cmd+=" -m ${map_file}"
    cmd+=" -k ${agents}"
    cmd+=" --scenario=${scenario}"
    cmd+=" --solver=${SOLVER}"
    cmd+=" --seed=${seed}"
    cmd+=" --simulation_timesteps=${SIM_TIMESTEPS}"
    cmd+=" --planning_horizon=${PLANNING_H}"
    cmd+=" --planning_window=${PLANNING_W}"
    cmd+=" --task_arrival_rate=${rate}"
    cmd+=" --scheduling_policy=${policy}"
    cmd+=" --output_dir=${RESULTS_DIR}"
    cmd+=" --run_id=${run_id}"

    if [[ "$mode" == "parallel" ]]; then
        cmd+=" --parallel"
        cmd+=" --threads=${threads}"
        cmd+=" --visibility_radius=${vr}"
    fi

    if [[ "$DRY_RUN" == true ]]; then
        echo "  [DRY] ${run_id}"
        echo "        ${cmd}"
        return 0
    fi

    echo "  [RUN]  ${run_id}"

    # Execute with timeout
    local start_ns
    start_ns=$(date +%s%N)

    set +e
    timeout "${TIMEOUT}s" bash -c "${cmd}" > "${log_file}" 2>&1
    local exit_code=$?
    set -e

    local end_ns
    end_ns=$(date +%s%N)
    local elapsed_ms=$(( (end_ns - start_ns) / 1000000 ))

    if [[ $exit_code -eq 0 ]]; then
        COMPLETED=$((COMPLETED + 1))
        echo "  [DONE] ${run_id}  (${elapsed_ms}ms)"
    elif [[ $exit_code -eq 124 ]]; then
        FAILED=$((FAILED + 1))
        echo "  [TIMEOUT] ${run_id}  (exceeded ${TIMEOUT}s)"
    else
        FAILED=$((FAILED + 1))
        echo "  [FAIL] ${run_id}  (exit code: ${exit_code})"
    fi

    # If the binary doesn't write its own run CSV, write a fallback row
    if [[ ! -f "${RESULTS_DIR}/run_${run_id}.csv" ]]; then
        echo "${run_id},${timestamp},${map_name},${scenario},${SOLVER},${mode},\
${threads},${agents},${rate},\
${PLANNING_H},${PLANNING_W},${vr},${seed},\
${SIM_TIMESTEPS},${elapsed_ms},-1,\
-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,\
${policy},${exit_code}" >> "$SUMMARY_FILE"
    fi
}

# ─── Main sweep loop ────────────────────────────────────────────
run_count=0

for mode in "${SOLVER_MODES[@]}"; do
    [[ -n "$MODE_FILTER" && "$mode" != "$MODE_FILTER" ]] && continue

    for map_idx in "${!MAPS[@]}"; do
        local_map="${MAPS[$map_idx]}"
        local_map_file="${MAP_FILES[$map_idx]}"
        local_scenario="${SCENARIOS[$map_idx]}"

        for agents in "${AGENT_COUNTS[@]}"; do
            for rate in "${ARRIVAL_RATES[@]}"; do
                for policy in "${POLICIES[@]}"; do
                    for seed in "${SEEDS[@]}"; do
                        if [[ "$mode" == "sequential" ]]; then
                            run_count=$((run_count + 1))
                            echo "[${run_count}/${TOTAL}] ${mode} | agents=${agents} rate=${rate} policy=${policy} seed=${seed}"
                            run_single "$local_map" "$local_map_file" "$local_scenario" \
                                       "$mode" 1 "$agents" "$rate" 0.0 "$seed" "$policy"
                        else
                            for threads in "${THREAD_COUNTS[@]}"; do
                                [[ "$threads" -eq 1 ]] && continue
                                for vr in "${VISIBILITY_RADII[@]}"; do
                                    run_count=$((run_count + 1))
                                    echo "[${run_count}/${TOTAL}] ${mode} | threads=${threads} agents=${agents} rate=${rate} vr=${vr} policy=${policy} seed=${seed}"
                                    run_single "$local_map" "$local_map_file" "$local_scenario" \
                                               "$mode" "$threads" "$agents" "$rate" "$vr" "$seed" "$policy"
                                done
                            done
                        fi
                    done
                done
            done
        done
    done
done

# ─── Final report ───────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Sweep complete!"
echo "  Total:     ${TOTAL}"
echo "  Completed: ${COMPLETED}"
echo "  Failed:    ${FAILED}"
echo "  Skipped:   ${SKIPPED}"
echo "  Results:   ${RESULTS_DIR}"
echo "  Summary:   ${SUMMARY_FILE}"
echo "═══════════════════════════════════════════════════════════════"
