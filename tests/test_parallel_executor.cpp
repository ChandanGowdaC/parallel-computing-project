#include <iostream>
#include <vector>
#include <cassert>
#include <chrono>
#include <numeric>
#include "ParallelExecutor.h"
#include "SolverInterface.h"

int main() {
    std::cout << "=== Running ParallelExecutor Verification Tests ===" << std::endl;

    // Test 1: Sequential Fallback (num_threads = 1)
    {
        ParallelExecutor seq_exec(1);
        assert(!seq_exec.is_parallel());
        assert(seq_exec.get_num_threads() == 1);

        std::vector<int> numbers = {1, 2, 3, 4, 5, 6, 7, 8};
        auto squared = seq_exec.parallel_map(numbers, [](int x) { return x * x; });
        assert(squared.size() == 8);
        assert(squared[3] == 16);
        std::cout << "Test 1 (Sequential fallback): PASSED" << std::endl;
    }

    // Test 2: parallel_for with 4 threads
    {
        const size_t size = 1000;
        ParallelExecutor par_exec(4);
        assert(par_exec.is_parallel());
        assert(par_exec.get_num_threads() == 4);

        std::vector<int> data(size, 0);
        par_exec.parallel_for(0, size, [&data](size_t i) {
            data[i] = static_cast<int>(i * 2);
        });

        for (size_t i = 0; i < size; ++i) {
            assert(data[i] == static_cast<int>(i * 2));
        }
        std::cout << "Test 2 (parallel_for): PASSED" << std::endl;
    }

    // Test 3: parallel_map with GroupPlanningTask (Person C workflow mockup)
    {
        ParallelExecutor solver_pool(4);
        std::vector<GroupPlanningTask> group_tasks;
        for (int g = 0; g < 8; ++g) {
            GroupPlanningTask task;
            task.group_id = g;
            task.agent_ids = {g * 2, g * 2 + 1};
            task.time_limit = 10;
            group_tasks.push_back(task);
        }

        // Mock group solver function
        auto mock_solver = [](const GroupPlanningTask& t) -> GroupPlanningResult {
            GroupPlanningResult res;
            res.group_id = t.group_id;
            res.success = true;
            res.runtime = 0.005;
            res.paths.resize(t.agent_ids.size());
            return res;
        };

        auto results = solver_pool.parallel_map(group_tasks, mock_solver);
        assert(results.size() == 8);
        for (int i = 0; i < 8; ++i) {
            assert(results[i].group_id == i);
            assert(results[i].success == true);
            assert(results[i].paths.size() == 2);
        }
        std::cout << "Test 3 (GroupPlanning parallel_map): PASSED" << std::endl;
    }

    // Test 4: Exception propagation
    {
        ParallelExecutor par_exec(2);
        std::vector<int> inputs = {1, 2, 3, 4};
        bool caught = false;
        try {
            par_exec.parallel_map(inputs, [](int x) -> int {
                if (x == 3) throw std::runtime_error("Simulated solver failure");
                return x * 10;
            });
        } catch (const std::runtime_error& e) {
            caught = true;
        }
        assert(caught);
        std::cout << "Test 4 (Exception propagation): PASSED" << std::endl;
    }

    std::cout << "ParallelExecutor Verification: ALL TESTS PASSED!" << std::endl;
    return 0;
}
