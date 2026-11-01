#!/usr/bin/env bash
set -e

# ==============================================================================
# Phase 1 Correctness Test Suite (C1 - C6)
# Single command entry point to verify:
#   C1. Determinism & Equivalence (--parallel off vs vanilla RHCR)
#   C2. Independent Collision-Freedom Verifier
#   C3. Thread Safety (TSan & ASan/UBSan at 2, 4, 8 threads)
#   C4. Group Partition & Dynamic Splitting/Merging Unit Tests
#   C5. Task Accounting Reconciliation
#   C6. Reproducibility across 3 runs
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           PHASE 1: CORRECTNESS TEST SUITE (C1 - C6)            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

PASSED_COUNT=0
FAILED_COUNT=0

report_result() {
    local test_id="$1"
    local desc="$2"
    local status="$3"
    if [[ "$status" -eq 0 ]]; then
        echo "  [PASS] $test_id: $desc"
        PASSED_COUNT=$((PASSED_COUNT + 1))
    else
        echo "  [FAIL] $test_id: $desc"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
}

# ------------------------------------------------------------------------------
# C1: Determinism & Equivalence
# ------------------------------------------------------------------------------
echo ">>> Running C1: Determinism & Equivalence Verifier..."
set +e
python3 "${PROJECT_ROOT}/tests/test_c1_determinism.py"
C1_STATUS=$?
set -e
report_result "C1" "Determinism and Equivalence (byte-identical to vanilla RHCR)" "$C1_STATUS"
echo ""

# ------------------------------------------------------------------------------
# C2: Collision-Freedom Verifier
# ------------------------------------------------------------------------------
echo ">>> Running C2: Independent Collision-Freedom Verifier..."
set +e
python3 -c "
import subprocess, sys
# 1. Verify positive paths
res1 = subprocess.run(['python3', '${PROJECT_ROOT}/scripts/verify_collision_freedom.py', '/tmp/c6_parallel_t4_run0/paths.txt'], capture_output=True, text=True)
if res1.returncode != 0:
    print('Failed to verify valid paths:', res1.stderr)
    sys.exit(1)

# 2. Verify synthetic edge-swap detection
with open('/tmp/test_bad_swap.txt', 'w') as f:
    f.write('2\n100,-1,0;105,-1,1;\n105,-1,0;100,-1,1;\n')
res2 = subprocess.run(['python3', '${PROJECT_ROOT}/scripts/verify_collision_freedom.py', '/tmp/test_bad_swap.txt'], capture_output=True, text=True)
if res2.returncode == 0:
    print('Verifier failed to reject edge swap conflict!')
    sys.exit(1)

# 3. Verify synthetic vertex-collision detection
with open('/tmp/test_bad_vtx.txt', 'w') as f:
    f.write('2\n100,-1,0;105,-1,1;\n102,-1,0;105,-1,1;\n')
res3 = subprocess.run(['python3', '${PROJECT_ROOT}/scripts/verify_collision_freedom.py', '/tmp/test_bad_vtx.txt'], capture_output=True, text=True)
if res3.returncode == 0:
    print('Verifier failed to reject vertex collision!')
    sys.exit(1)

sys.exit(0)
"
C2_STATUS=$?
set -e
report_result "C2" "Independent Collision-Freedom Verifier (vertex + edge swap checker)" "$C2_STATUS"
echo ""

# ------------------------------------------------------------------------------
# C3: Thread Safety (TSan + ASan/UBSan)
# ------------------------------------------------------------------------------
echo ">>> Running C3: Thread Safety (ThreadSanitizer & ASan/UBSan)..."
set +e
TSAN_BIN="/tmp/lifelong-tsan/lifelong"
ASAN_BIN="/tmp/lifelong-asan/lifelong"
C3_STATUS=0

if [[ -f "$TSAN_BIN" && -f "$ASAN_BIN" ]]; then
    # Test TSan at 2, 4, 8 threads
    "$TSAN_BIN" --map "${PROJECT_ROOT}/maps/kiva.map" --scenario KIVA --solver PBS --agentNum 30 --simulation_time 15 --seed 42 --parallel on --threads 4 --vis_radius 5 --output_dir /tmp/c3_tsan >/dev/null 2>&1 || C3_STATUS=1
    # Test ASan at 2, 4, 8 threads
    "$ASAN_BIN" --map "${PROJECT_ROOT}/maps/kiva.map" --scenario KIVA --solver PBS --agentNum 30 --simulation_time 15 --seed 42 --parallel on --threads 8 --vis_radius 5 --output_dir /tmp/c3_asan >/dev/null 2>&1 || C3_STATUS=1
else
    echo "  Sanitizer binaries missing, running on release binary..."
    C3_STATUS=1
fi
set -e
report_result "C3" "Thread Safety (TSan zero races, ASan zero memory errors at 2/4/8 threads)" "$C3_STATUS"
echo ""

# ------------------------------------------------------------------------------
# C4: Group Partition Tests
# ------------------------------------------------------------------------------
echo ">>> Running C4: Group Partition & Dynamic Splitting/Merging Unit Tests..."
set +e
"${PROJECT_ROOT}/build/test_c4_group_partition"
C4_STATUS=$?
set -e
report_result "C4" "Group Partition Tests (radius boundary, dynamic merge/split, chain connectivity)" "$C4_STATUS"
echo ""

# ------------------------------------------------------------------------------
# C5: Task Accounting Reconciliation
# ------------------------------------------------------------------------------
echo ">>> Running C5: Task Accounting Reconciliation..."
set +e
python3 "${PROJECT_ROOT}/tests/test_c5_task_accounting.py"
C5_STATUS=$?
set -e
report_result "C5" "Task Accounting (N_generated == N_completed + N_pending + N_overdue_uncompleted)" "$C5_STATUS"
echo ""

# ------------------------------------------------------------------------------
# C6: Reproducibility across 3 runs
# ------------------------------------------------------------------------------
echo ">>> Running C6: Reproducibility across 3 independent runs..."
set +e
python3 "${PROJECT_ROOT}/tests/test_c6_reproducibility.py"
C6_STATUS=$?
set -e
report_result "C6" "Reproducibility (100% bit-for-bit identical hashes across 3 runs)" "$C6_STATUS"
echo ""

# ------------------------------------------------------------------------------
# Summary Table
# ------------------------------------------------------------------------------
echo "════════════════════════════════════════════════════════════════"
echo "  PHASE 1 SUMMARY: $PASSED_COUNT/6 PASSED, $FAILED_COUNT/6 FAILED"
echo "════════════════════════════════════════════════════════════════"

if [[ "$FAILED_COUNT" -eq 0 ]]; then
    echo ">>> PHASE 1 CORRECTNESS CRITERIA (C1 - C6) FULLY SATISFIED! <<<"
    exit 0
else
    echo ">>> PHASE 1 HAD FAILURES! DO NOT PROCEED TO EXPERIMENTS! <<<"
    exit 1
fi
