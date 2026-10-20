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

# Find Threads
find_package(Threads REQUIRED)

# Find Boost
find_package(Boost 1.49.0 REQUIRED COMPONENTS program_options system filesystem)
include_directories(${Boost_INCLUDE_DIRS})

file(GLOB SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")

# Main simulation executable
add_executable(lifelong ${SOURCES})
target_link_libraries(lifelong PRIVATE ${Boost_LIBRARIES} Threads::Threads)

# Unit / verification tests
enable_testing()

# 1. ThreadPool primitive test
add_executable(test_thread_pool "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_thread_pool.cpp")
target_link_libraries(test_thread_pool PRIVATE Threads::Threads)
add_test(NAME ThreadPoolTest COMMAND test_thread_pool)

# 2. ParallelExecutor wrapper test
add_executable(test_parallel_executor "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_parallel_executor.cpp")
target_link_libraries(test_parallel_executor PRIVATE Threads::Threads)
add_test(NAME ParallelExecutorTest COMMAND test_parallel_executor)

# 3. Day One Interfaces contract test
add_executable(test_interfaces "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_interfaces.cpp")
target_link_libraries(test_interfaces PRIVATE Threads::Threads)
add_test(NAME InterfacesTest COMMAND test_interfaces)
