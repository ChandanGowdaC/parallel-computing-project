cmake_minimum_required(VERSION 3.10)
project(lifelong CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Release")
endif()

# Suppress boost cmake policy warning if cmake >= 3.30
if(POLICY CMP0167)
    cmake_policy(SET CMP0167 NEW)
endif()

# macOS Homebrew auto-detection for Apple Silicon and Intel Macs
if(APPLE)
    if(EXISTS "/opt/homebrew")
        list(PREPEND CMAKE_PREFIX_PATH "/opt/homebrew")
    elseif(EXISTS "/usr/local")
        list(PREPEND CMAKE_PREFIX_PATH "/usr/local")
    endif()
endif()

include_directories("${CMAKE_CURRENT_SOURCE_DIR}/inc")
include_directories("${CMAKE_CURRENT_SOURCE_DIR}/metrics")

# Find Threads
find_package(Threads REQUIRED)

# Find Boost
find_package(Boost 1.49.0 REQUIRED COMPONENTS program_options system filesystem)
include_directories(${Boost_INCLUDE_DIRS})

set(SOURCES
    src/BasicGraph.cpp
    src/BasicSystem.cpp
    src/BeeGraph.cpp
    src/BeeSystem.cpp
    src/DeadlineMetrics.cpp
    src/DeadlineScheduler.cpp
    src/ECBS.cpp
    src/ECBSNode.cpp
    src/ID.cpp
    src/KivaGraph.cpp
    src/KivaSystem.cpp
    src/LRAStar.cpp
    src/MAPFSolver.cpp
    src/OnlineGraph.cpp
    src/OnlineSystem.cpp
    src/PBS.cpp
    src/PBSNode.cpp
    src/PathTable.cpp
    src/PriorityGraph.cpp
    src/ReservationTable.cpp
    src/SIPP.cpp
    src/SingleAgentSolver.cpp
    src/SortingGraph.cpp
    src/SortingSystem.cpp
    src/StateTimeAStar.cpp
    src/States.cpp
    src/TaskGenerator.cpp
    src/WHCAStar.cpp
    src/common.cpp
    src/driver.cpp
)

# Main simulation executable
add_executable(lifelong ${SOURCES})
target_link_libraries(lifelong PRIVATE ${Boost_LIBRARIES} Threads::Threads)

# Unit / verification tests
enable_testing()

# 1. ThreadPool primitive test
add_executable(test_thread_pool "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_thread_pool.cpp")
target_link_libraries(test_thread_pool PRIVATE Threads::Threads)
add_test(NAME ThreadPoolTest COMMAND test_thread_pool)

# Person C visibility grouping, parallel solve dispatch, and plan merge test
add_executable(test_gd_rhcr "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_gd_rhcr.cpp")
target_link_libraries(test_gd_rhcr PRIVATE Threads::Threads)
add_test(NAME GDRHCRTest COMMAND test_gd_rhcr)

# 2. ParallelExecutor wrapper test
add_executable(test_parallel_executor "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_parallel_executor.cpp")
target_link_libraries(test_parallel_executor PRIVATE Threads::Threads)
add_test(NAME ParallelExecutorTest COMMAND test_parallel_executor)

# 3. Day One Interfaces contract test
add_executable(test_interfaces "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_interfaces.cpp")
target_link_libraries(test_interfaces PRIVATE Threads::Threads)
add_test(NAME InterfacesTest COMMAND test_interfaces)

# 4. Person B Deadline Workload test
add_executable(test_deadline_workload
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_deadline_workload.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/TaskGenerator.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/DeadlineScheduler.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/DeadlineMetrics.cpp"
)
target_link_libraries(test_deadline_workload PRIVATE Threads::Threads)
add_test(NAME DeadlineWorkloadTest COMMAND test_deadline_workload)

# 5. GD-RHCR group solve dispatch test (asserts total_dispatched_group_solves > 0)
set(ENGINE_SOURCES ${SOURCES})
list(FILTER ENGINE_SOURCES EXCLUDE REGEX ".*/driver\\.cpp$")
add_executable(test_gd_rhcr_dispatch
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_gd_rhcr_dispatch.cpp"
    ${ENGINE_SOURCES}
)
target_link_libraries(test_gd_rhcr_dispatch PRIVATE ${Boost_LIBRARIES} Threads::Threads)
add_test(NAME GDRHCRDispatchTest COMMAND test_gd_rhcr_dispatch WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")

# 6. Real-time planning-budget coupling test (slowed planner misses more deadlines)
add_executable(test_realtime_coupling
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_realtime_coupling.cpp"
    ${ENGINE_SOURCES}
)
target_link_libraries(test_realtime_coupling PRIVATE ${Boost_LIBRARIES} Threads::Threads)
add_test(NAME RealtimeCouplingTest COMMAND test_realtime_coupling WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")

# 7. Phase 1 / C4 Group Partition Test
add_executable(test_c4_group_partition
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_c4_group_partition.cpp"
)
target_link_libraries(test_c4_group_partition PRIVATE Threads::Threads)
add_test(NAME C4GroupPartitionTest COMMAND test_c4_group_partition WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")

