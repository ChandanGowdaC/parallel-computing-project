#!/bin/bash
set -euo pipefail

# run_smoke_matrix.sh — Smoke run for Phase 3 pre-registered experiment matrix
# Executes 18 configurations (Seed 42, T=20) across Tier 1 (E1, E3, E7)
# Validates output CSV generation and runs automated collision checker.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BINARY="${ROOT_DIR}/build/lifelong"
RESULTS_DIR="${ROOT_DIR}/results/smoke_raw"
mkdir -p "${RESULTS_DIR}"

echo "================================================================"
echo "          PHASE 3: PRE-REGISTERED SMOKE RUN (18 RUNS)          "
echo "================================================================"

SEED=42
SIM_TIME=20

configs=(
  # E1 Strong Scaling (KIVA N=100, V=5)
  "KIVA maps/kiva.map 100 1 on 5 10 5 e1_kiva_t1"
  "KIVA maps/kiva.map 100 2 on 5 10 5 e1_kiva_t2"
  "KIVA maps/kiva.map 100 4 on 5 10 5 e1_kiva_t4"
  "KIVA maps/kiva.map 100 8 on 5 10 5 e1_kiva_t8"
  "KIVA maps/kiva.map 100 11 on 5 10 5 e1_kiva_t11"
  # E1 Strong Scaling (SORTING N=100, V=10)
  "SORTING maps/sorting_map.grid 100 1 on 10 5 5 e1_sort_t1"
  "SORTING maps/sorting_map.grid 100 2 on 10 5 5 e1_sort_t2"
  "SORTING maps/sorting_map.grid 100 4 on 10 5 5 e1_sort_t4"
  "SORTING maps/sorting_map.grid 100 8 on 10 5 5 e1_sort_t8"
  "SORTING maps/sorting_map.grid 100 11 on 10 5 5 e1_sort_t11"
  # V0 Vanilla Reference Baselines
  "KIVA maps/kiva.map 100 1 off 0 10 5 v0_kiva_seq"
  "SORTING maps/sorting_map.grid 100 1 off 0 5 5 v0_sort_seq"
  # E3 Problem-size scaling
  "SORTING maps/sorting_map.grid 50 4 on 10 5 5 e3_sort_a50_t4"
  "SORTING maps/sorting_map.grid 200 4 on 10 5 5 e3_sort_a200_t4"
  # E6 Fallback / V=2
  "KIVA maps/kiva.map 100 4 on 2 10 5 e6_kiva_v2_t4"
  # V3 Sequential Fallback Threshold
  "SORTING maps/sorting_map.grid 100 4 on 10 5 5 v3_sort_fallback_thresh"
  # E7 Real-Time Coupling (KIVA with deadline)
  "KIVA maps/kiva.map 50 1 on 3 10 5 e7_kiva_rt_t1"
  "KIVA maps/kiva.map 50 4 on 3 10 5 e7_kiva_rt_t4"
)

TOTAL=${#configs[@]}
COUNT=0
FAILURES=0

for cfg in "${configs[@]}"; do
  read -r scenario map agents threads parallel v w h run_id <<< "${cfg}"
  COUNT=$((COUNT + 1))
  printf "[%2d/%2d] Running %-28s ... " "${COUNT}" "${TOTAL}" "${run_id}"

  EXTRA_ARGS=()
  if [[ "${run_id}" == "v3_sort_fallback_thresh" ]]; then
    EXTRA_ARGS+=("--sequential_fallback_threshold" "3")
  fi
  if [[ "${run_id}" =~ ^e7_ ]]; then
    EXTRA_ARGS+=("--deadline" "on" "--realtime_coupling" "on" "--planning_tau" "0.01")
  fi

  OUT_LOG="${RESULTS_DIR}/log_${run_id}.txt"
  if "${BINARY}" \
      --scenario "${scenario}" \
      --map "${map}" \
      --agents "${agents}" \
      --threads "${threads}" \
      --parallel "${parallel}" \
      --vis_radius "${v}" \
      --planning_window "${w}" \
      --planning_horizon "${h}" \
      --simulation_timesteps "${SIM_TIME}" \
      --seed "${SEED}" \
      --output_dir "${RESULTS_DIR}" \
      --run_id "${run_id}" \
      ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} > "${OUT_LOG}" 2>&1; then
    echo "OK"
  else
    echo "FAILED"
    FAILURES=$((FAILURES + 1))
  fi
done

echo ""
echo "=== Verifying Collision-Freedom across all smoke runs ==="
python3 scripts/verify_collision_freedom.py "${RESULTS_DIR}"

echo ""
echo "================================================================"
if [[ ${FAILURES} -eq 0 ]]; then
  echo "SMOKE RUN COMPLETE: ALL ${TOTAL} RUNS SUCCEEDED WITH ZERO FAILURES"
else
  echo "SMOKE RUN FINISHED WITH ${FAILURES} FAILURES"
  exit 1
fi
echo "================================================================"
