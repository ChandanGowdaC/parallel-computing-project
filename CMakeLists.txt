cmake_minimum_required(VERSION 3.10)
project(lifelong)

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

include_directories("inc")

# Find Threads
find_package(Threads REQUIRED)

# Find Boost
find_package(Boost 1.49.0 REQUIRED COMPONENTS program_options system filesystem)
include_directories(${Boost_INCLUDE_DIRS})

file(GLOB SOURCES "src/*.cpp")

# Main simulation executable
add_executable(lifelong ${SOURCES})
target_link_libraries(lifelong PRIVATE ${Boost_LIBRARIES} Threads::Threads)

# Unit / verification tests
enable_testing()
add_executable(test_thread_pool tests/test_thread_pool.cpp)
target_link_libraries(test_thread_pool PRIVATE Threads::Threads)
add_test(NAME ThreadPoolTest COMMAND test_thread_pool)
