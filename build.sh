#!/usr/bin/env bash
set -e

# Person A - Unified Build Script
# Compatible with macOS (Apple Silicon / Intel) and Linux (Ubuntu / Debian / CentOS)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect CPU cores
if command -v nproc &>/dev/null; then
    NUM_CORES=$(nproc)
elif command -v sysctl &>/dev/null; then
    NUM_CORES=$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)
else
    NUM_CORES=4
fi

echo "=================================================="
echo "  Building Lifelong MAPF / GD-RHCR Engine"
echo "  Parallel build using ${NUM_CORES} workers"
echo "=================================================="

# Handle paths with brackets [] which trigger a known CMake glob issue during compiler identification
if [[ "${PROJECT_ROOT}" =~ \[|\] ]]; then
    SAFE_LINK="/tmp/lifelong-src-$(id -u)"
    ln -sfn "${PROJECT_ROOT}" "${SAFE_LINK}"
    BUILD_DIR="/tmp/lifelong-build-$(id -u)"
    SRC_DIR="${SAFE_LINK}"
else
    BUILD_DIR="${PROJECT_ROOT}/build"
    SRC_DIR="${PROJECT_ROOT}"
fi

mkdir -p "${BUILD_DIR}"

CMAKE_ARGS=("-DCMAKE_BUILD_TYPE=Release")
if [[ "$(uname -s)" == "Darwin" && -d "/opt/homebrew" ]]; then
    CMAKE_ARGS+=("-DCMAKE_PREFIX_PATH=/opt/homebrew")
fi

cmake "${CMAKE_ARGS[@]}" -B "${BUILD_DIR}" -S "${SRC_DIR}" "$@"
cmake --build "${BUILD_DIR}" --config Release -j "${NUM_CORES}"

# Ensure binaries are accessible directly in ${PROJECT_ROOT}/build
mkdir -p "${PROJECT_ROOT}/build"
if [[ "${BUILD_DIR}" != "${PROJECT_ROOT}/build" ]]; then
    ln -sfn "${BUILD_DIR}/lifelong" "${PROJECT_ROOT}/build/lifelong"
    ln -sfn "${BUILD_DIR}/test_thread_pool" "${PROJECT_ROOT}/build/test_thread_pool"
    ln -sfn "${BUILD_DIR}/test_parallel_executor" "${PROJECT_ROOT}/build/test_parallel_executor"
    ln -sfn "${BUILD_DIR}/test_interfaces" "${PROJECT_ROOT}/build/test_interfaces"
fi

echo ""
echo "=================================================="
echo "  Build successful!"
echo "  Binaries created:"
echo "    - ${PROJECT_ROOT}/build/lifelong"
echo "    - ${PROJECT_ROOT}/build/test_thread_pool"
echo "    - ${PROJECT_ROOT}/build/test_parallel_executor"
echo "    - ${PROJECT_ROOT}/build/test_interfaces"
echo "=================================================="
