#!/usr/bin/env bash
set -e

# Person A - Unified Execution Script
# Runs sequential baseline, parallel GD-RHCR, or threadpool unit tests

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_PATH="${PROJECT_ROOT}/build/lifelong"
TEST_BIN="${PROJECT_ROOT}/build/test_thread_pool"

# If binaries are missing, run build.sh first
if [[ ! -x "${BIN_PATH}" || ! -x "${TEST_BIN}" ]]; then
    echo "Executables not found. Running build.sh first..."
    "${PROJECT_ROOT}/build.sh"
fi

# Shortcut to run all unit tests
if [[ "$1" == "--test" || "$1" == "test" || "$1" == "-t" ]]; then
    echo "=================================================="
    echo "  Running All Verification & Regression Tests"
    echo "=================================================="
    echo "[1/3] Running ThreadPool verification..."
    "${PROJECT_ROOT}/build/test_thread_pool"
    echo ""
    echo "[2/3] Running ParallelExecutor verification..."
    "${PROJECT_ROOT}/build/test_parallel_executor"
    echo ""
    echo "[3/3] Running Day One Interfaces contract verification..."
    "${PROJECT_ROOT}/build/test_interfaces"
    echo ""
    echo "=================================================="
    echo "  ALL VERIFICATION TESTS PASSED SUCCESSFULLY!"
    echo "=================================================="
    exit 0
fi

# If no arguments provided, run a baseline smoke test
if [[ $# -eq 0 ]]; then
    echo "=================================================="
    echo "No arguments provided. Running default baseline:"
    echo "  Map: maps/kiva.map"
    echo "  Agents: 50"
    echo "  Scenario: KIVA"
    echo "  Solver: ECBS (w=1.5)"
    echo "  Simulation time: 10 steps"
    echo "=================================================="
    exec "${BIN_PATH}" \
        --scenario=KIVA \
        -m "${PROJECT_ROOT}/maps/kiva.map" \
        -k 50 \
        --simulation_window=1 \
        --solver=ECBS \
        --suboptimal_bound=1.5 \
        --dummy_paths=1 \
        --seed=0 \
        --simulation_time=10 \
        -o "${PROJECT_ROOT}/exp/smoke_test" \
        --csv_metrics="${PROJECT_ROOT}/exp/metrics.csv"
else
    exec "${BIN_PATH}" "$@"
fi
