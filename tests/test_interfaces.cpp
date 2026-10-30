#include <iostream>
#include <vector>
#include <cassert>
#include <fstream>
#include <sstream>
#include "Task.h"
#include "SolverInterface.h"
#include "Metrics.h"

int main() {
    std::cout << "=== Running Day One Interface Contracts Verification Tests ===" << std::endl;

    // 1. Task Struct Verification
    {
        Task t1(1, 10, 50, 0, 25);
        assert(t1.id == 1);
        assert(t1.pickup_loc == 10);
        assert(t1.delivery_loc == 50);
        assert(t1.release_time == 0);
        assert(t1.deadline == 25);
        assert(!t1.is_completed());
        assert(!t1.is_overdue(20));
        assert(t1.is_overdue(26));
        assert(t1.tardiness(20) == 0);
        assert(t1.tardiness(30) == 5);

        // Mark completed on time
        t1.finish_time = 22;
        t1.status = TaskStatus::COMPLETED;
        assert(t1.is_completed());
        assert(!t1.is_overdue(100)); // finished at 22 <= deadline 25
        assert(t1.tardiness(100) == 0);

        // Mark completed late
        Task t2(2, 12, 55, 5, 20);
        t2.finish_time = 28;
        t2.status = TaskStatus::COMPLETED;
        assert(t2.is_completed());
        assert(t2.is_overdue(100));
        assert(t2.tardiness(100) == 8);

        std::cout << "1. Task Struct Contract: PASSED" << std::endl;
    }

    // 2. Solver Interface Verification
    {
        GroupPlanningTask gtask;
        gtask.group_id = 42;
        gtask.agent_ids = {0, 1, 2};
        gtask.simulation_window = 1;
        gtask.planning_window = 10;
        gtask.time_limit = 30;

        WindowedGroupSolverFn solver_fn = [](const GroupPlanningTask& task) -> GroupPlanningResult {
            GroupPlanningResult res;
            res.group_id = task.group_id;
            res.success = true;
            res.runtime = 0.042;
            res.paths.resize(task.agent_ids.size());
            return res;
        };

        GroupPlanningResult result = solver_fn(gtask);
        assert(result.group_id == 42);
        assert(result.success);
        assert(result.paths.size() == 3);

        std::cout << "2. Solver Interface Contract: PASSED" << std::endl;
    }

    // 3. Metrics Schema Verification
    {
        RunMetrics m;
        m.timestamp = "2026-10-20 12:00:00";
        m.scenario = "KIVA";
        m.map_name = "maps/kiva.map";
        m.solver_name = "ECBS";
        m.num_agents = 100;
        m.num_threads = 4;
        m.parallel_enabled = true;
        m.vis_radius = 5;
        m.simulation_window = 1;
        m.planning_window = 10;
        m.simulation_time = 50;
        m.cutoff_time = 60;
        m.seed = 42;
        m.wall_clock_runtime = 1.2345;
        m.tasks_finished = 30;
        m.throughput = 0.6;
        m.tasks_total = 35;
        m.tasks_on_time = 28;
        m.tasks_overdue = 2;
        m.deadline_satisfaction_rate = 0.80;
        m.avg_tardiness = 1.25;
        m.max_tardiness = 5;

        std::string csv_path = "/tmp/test_contract_metrics.csv";
        std::string json_path = "/tmp/test_contract_metrics.json";
        std::remove(csv_path.c_str());
        std::remove(json_path.c_str());

        m.append_to_csv(csv_path);
        m.save_to_json(json_path);

        // Verify CSV file exists and contains header + row
        std::ifstream csv_in(csv_path);
        assert(csv_in.is_open());
        std::string header, row;
        std::getline(csv_in, header);
        std::getline(csv_in, row);
        assert(!header.empty());
        assert(!row.empty());
        assert(row.find("KIVA") != std::string::npos);
        assert(row.find("true") != std::string::npos); // parallel enabled
        csv_in.close();

        // Verify JSON file exists
        std::ifstream json_in(json_path);
        assert(json_in.is_open());
        std::stringstream ss;
        ss << json_in.rdbuf();
        std::string json_str = ss.str();
        assert(json_str.find("\"scenario\": \"KIVA\"") != std::string::npos);
        assert(json_str.find("\"parallel_enabled\": true") != std::string::npos);
        json_in.close();

        // Verify task detail logging
        std::vector<Task> tasks;
        tasks.emplace_back(1, 10, 20, 0, 15);
        tasks.back().finish_time = 12;
        tasks.back().status = TaskStatus::COMPLETED;

        std::string tasks_csv = "/tmp/test_contract_tasks.csv";
        save_tasks_csv(tasks_csv, tasks, 20);
        std::ifstream tasks_in(tasks_csv);
        assert(tasks_in.is_open());
        std::string t_header, t_row;
        std::getline(tasks_in, t_header);
        std::getline(tasks_in, t_row);
        assert(t_row.find("COMPLETED") != std::string::npos);
        tasks_in.close();

        std::cout << "3. Metrics Serialization Contract: PASSED" << std::endl;
    }

    std::cout << "All Interface Contract Tests: ALL TESTS PASSED!" << std::endl;
    return 0;
}
