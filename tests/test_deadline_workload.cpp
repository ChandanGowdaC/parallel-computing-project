/**
 * test_deadline_workload.cpp — Unit and Integration Tests for Person B
 *
 * Tests:
 * 1. TaskGenerator: Poisson arrival process, reproducible seeding, Manhattan distance deadlines.
 * 2. DeadlineScheduler: FIFO, EDF, and DEADLINE_AWARE scheduling policies.
 * 3. Status Transitions: UNASSIGNED -> ASSIGNED -> COMPLETED / OVERDUE.
 * 4. DeadlineMetrics: KPIs, on-time vs overdue tracking, tardiness accumulation, snapshot series, and CSV export.
 * 5. Edge cases: empty task pools, unconstrained tasks, multiple idle agents.
 */

#include <iostream>
#include <vector>
#include <cassert>
#include <cmath>
#include <fstream>
#include <sstream>
#include <cstdio>
#include "Task.h"
#include "TaskGenerator.h"
#include "DeadlineScheduler.h"
#include "DeadlineMetrics.h"

void test_task_generator() {
    std::cout << "[Test 1] Testing TaskGenerator..." << std::endl;

    std::vector<int> endpoints = {10, 20, 30, 40, 50};
    int seed = 42;
    double arrival_rate = 2.0;
    double deadline_factor = 2.0;
    int min_slack = 10;

    TaskGenerator gen(endpoints, seed, arrival_rate, deadline_factor, min_slack);

    // Batch generation test
    auto batch = gen.generate_batch(5, 10, 10);
    assert(batch.size() == 5);
    for (const auto& t : batch) {
        assert(t.release_time == 0);
        assert(t.pickup_loc != t.delivery_loc);
        assert(t.deadline >= t.release_time + min_slack);
        assert(t.status == TaskStatus::UNASSIGNED);
        assert(t.assigned_agent == -1);
    }

    // Reproducibility test
    gen.reset();
    auto batch2 = gen.generate_batch(5, 10, 10);
    assert(batch2.size() == 5);
    for (size_t i = 0; i < batch.size(); ++i) {
        assert(batch[i].id == batch2[i].id);
        assert(batch[i].pickup_loc == batch2[i].pickup_loc);
        assert(batch[i].delivery_loc == batch2[i].delivery_loc);
        assert(batch[i].deadline == batch2[i].deadline);
    }

    // Poisson arrival sequence test over time
    gen.reset();
    int total_arrivals = 0;
    for (int t = 0; t < 20; ++t) {
        auto arrivals = gen.generate_arrivals(t, 10, 10);
        for (const auto& task : arrivals) {
            assert(task.release_time == t);
            assert(task.deadline > task.release_time);
            total_arrivals++;
        }
    }
    assert(total_arrivals > 0);
    std::cout << "  -> Generated " << total_arrivals << " Poisson arrivals over 20 timesteps." << std::endl;
    std::cout << "  [PASSED] TaskGenerator" << std::endl;
}

void test_deadline_scheduler_policies() {
    std::cout << "[Test 2] Testing DeadlineScheduler policies (FIFO, EDF, DEADLINE_AWARE)..." << std::endl;

    int map_width = 10;
    // Setup tasks:
    // Task 0: release=0, deadline=50, pickup=12, delivery=18
    // Task 1: release=2, deadline=30, pickup=15, delivery=25
    // Task 2: release=1, deadline=20, pickup=90, delivery=99
    std::vector<Task> base_tasks;
    base_tasks.emplace_back(0, 12, 18, 0, 50);
    base_tasks.emplace_back(1, 15, 25, 2, 30);
    base_tasks.emplace_back(2, 90, 99, 1, 20);

    // 2.1 FIFO policy
    {
        DeadlineScheduler scheduler(SchedulingPolicy::FIFO);
        assert(scheduler.get_policy() == SchedulingPolicy::FIFO);

        std::vector<Task> tasks = base_tasks;
        std::vector<int> idle_agents = {0, 1};
        std::vector<int> agent_locs = {10, 20};

        // At t=2, all 3 tasks are released (release times 0, 2, 1 <= 2)
        auto assign = scheduler.assign_tasks(tasks, idle_agents, agent_locs, 2, map_width);
        assert(assign.size() == 2);
        // FIFO order by release_time: Task 0 (rel 0), Task 2 (rel 1), Task 1 (rel 2)
        // Agent 0 gets Task 0, Agent 1 gets Task 2
        assert(assign[0] == 0);
        assert(assign[1] == 2);
        assert(tasks[0].status == TaskStatus::ASSIGNED);
        assert(tasks[0].assigned_agent == 0);
        assert(tasks[2].status == TaskStatus::ASSIGNED);
        assert(tasks[2].assigned_agent == 1);
        assert(tasks[1].status == TaskStatus::UNASSIGNED);
    }

    // 2.2 EDF policy
    {
        DeadlineScheduler scheduler(SchedulingPolicy::EDF);
        assert(scheduler.get_policy() == SchedulingPolicy::EDF);

        std::vector<Task> tasks = base_tasks;
        std::vector<int> idle_agents = {0, 1};
        std::vector<int> agent_locs = {10, 20};

        // At t=2, deadlines are: Task 2 (d=20), Task 1 (d=30), Task 0 (d=50)
        // Agent 0 gets Task 2, Agent 1 gets Task 1
        auto assign = scheduler.assign_tasks(tasks, idle_agents, agent_locs, 2, map_width);
        assert(assign.size() == 2);
        assert(assign[0] == 2);
        assert(assign[1] == 1);
        assert(tasks[2].assigned_agent == 0);
        assert(tasks[1].assigned_agent == 1);
        assert(tasks[0].status == TaskStatus::UNASSIGNED);
    }

    // 2.3 DEADLINE_AWARE policy (proximity + remaining slack)
    {
        DeadlineScheduler scheduler(SchedulingPolicy::DEADLINE_AWARE);
        assert(scheduler.get_policy() == SchedulingPolicy::DEADLINE_AWARE);

        std::vector<Task> tasks = base_tasks;
        // Agent 0 is at location 90 (right next to Task 2 pickup 90)
        // Agent 1 is at location 12 (right next to Task 0 pickup 12)
        std::vector<int> idle_agents = {0, 1};
        std::vector<int> agent_locs = {90, 12};

        auto assign = scheduler.assign_tasks(tasks, idle_agents, agent_locs, 2, map_width);
        assert(assign.size() == 2);
        // Agent 0 is adjacent to Task 2 -> picks Task 2 (lowest score)
        assert(assign[0] == 2);
        // Agent 1 has remaining choices Task 0 and Task 1
        assert(assign.count(1) == 1);
    }

    std::cout << "  [PASSED] DeadlineScheduler policies" << std::endl;
}

void test_task_status_and_metrics() {
    std::cout << "[Test 3] Testing task status tracking and DeadlineMetrics..." << std::endl;

    DeadlineMetrics metrics;

    Task t1(1, 10, 20, 0, 30);
    Task t2(2, 15, 25, 0, 20);
    Task t3(3, 40, 50, 0, -1); // unconstrained

    metrics.on_task_generated(t1);
    metrics.on_task_generated(t2);
    metrics.on_task_generated(t3);

    assert(metrics.tasks_total() == 3);
    assert(metrics.tasks_no_deadline() == 1);

    // Complete t1 on time (finish=25 <= deadline 30)
    t1.finish_time = 25;
    t1.status = TaskStatus::COMPLETED;
    metrics.on_task_completed(t1, 25);

    // Complete t2 late (finish=35 > deadline 20)
    t2.finish_time = 35;
    t2.status = TaskStatus::COMPLETED;
    metrics.on_task_completed(t2, 35);

    // Complete t3 without deadline
    t3.finish_time = 40;
    t3.status = TaskStatus::COMPLETED;
    metrics.on_task_completed(t3, 40);

    assert(metrics.tasks_on_time() == 1); // t1 (constrained on-time)
    assert(metrics.tasks_overdue() == 1); // t2 (tardiness = 15)
    assert(metrics.max_tardiness() == 15);
    // avg_tardiness = (0 + 15 + 0) / 3 = 5.0
    assert(std::abs(metrics.avg_tardiness() - 5.0) < 1e-4);
    // satisfaction rate among constrained tasks: 1 on-time / 2 constrained = 0.50
    assert(std::abs(metrics.deadline_satisfaction_rate() - 0.50) < 1e-4);

    // Snapshot testing
    metrics.snapshot(25);
    metrics.snapshot(35);
    metrics.snapshot(40);
    assert(metrics.snapshots().size() == 3);

    // Test RunMetrics population
    RunMetrics rm;
    metrics.populate_run_metrics(rm);
    assert(rm.tasks_total == 3);
    assert(rm.tasks_on_time == 1);
    assert(rm.tasks_overdue == 1);
    assert(rm.max_tardiness == 15);
    assert(std::abs(rm.deadline_satisfaction_rate - 0.50) < 1e-4);

    // CSV export test
    std::string task_csv = "test_tasks_out.csv";
    std::string snap_csv = "test_snaps_out.csv";
    std::remove(task_csv.c_str());
    std::remove(snap_csv.c_str());

    std::vector<Task> all_tasks = {t1, t2, t3};
    metrics.save_task_records(task_csv, all_tasks, 50);
    metrics.save_snapshot_series(snap_csv);

    // Verify task CSV content
    std::ifstream in_t(task_csv);
    assert(in_t.is_open());
    std::string line;
    std::getline(in_t, line); // header
    assert(line.find("tardiness") != std::string::npos);
    int row_count = 0;
    while (std::getline(in_t, line)) {
        if (!line.empty()) row_count++;
    }
    assert(row_count == 3);
    in_t.close();
    std::remove(task_csv.c_str());

    // Verify snapshot CSV content
    std::ifstream in_s(snap_csv);
    assert(in_s.is_open());
    std::getline(in_s, line); // header
    assert(line.find("deadline_satisfaction_rate") != std::string::npos);
    row_count = 0;
    while (std::getline(in_s, line)) {
        if (!line.empty()) row_count++;
    }
    assert(row_count == 3);
    in_s.close();
    std::remove(snap_csv.c_str());

    std::cout << "  [PASSED] Task status tracking and DeadlineMetrics" << std::endl;
}

void test_edge_cases() {
    std::cout << "[Test 4] Testing edge cases..." << std::endl;

    DeadlineScheduler scheduler(SchedulingPolicy::EDF);

    // 4.1 Empty tasks
    std::vector<Task> empty_tasks;
    std::vector<int> idle_agents = {0, 1};
    std::vector<int> agent_locs = {10, 20};
    auto assign = scheduler.assign_tasks(empty_tasks, idle_agents, agent_locs, 0, 10);
    assert(assign.empty());

    // 4.2 More agents than tasks
    std::vector<Task> one_task;
    one_task.emplace_back(0, 10, 20, 0, 30);
    assign = scheduler.assign_tasks(one_task, idle_agents, agent_locs, 0, 10);
    assert(assign.size() == 1);
    assert(assign[0] == 0);

    // 4.3 Task not yet released
    std::vector<Task> future_task;
    future_task.emplace_back(0, 10, 20, 10, 30); // released at t=10
    assign = scheduler.assign_tasks(future_task, idle_agents, agent_locs, 5, 10); // current t=5
    assert(assign.empty());

    // 4.4 Status update to OVERDUE
    scheduler.update_task_statuses(future_task, 35);
    assert(future_task[0].status == TaskStatus::OVERDUE);

    std::cout << "  [PASSED] Edge cases" << std::endl;
}

int main() {
    std::cout << "======================================================" << std::endl;
    std::cout << "  Person B — Deadline-Aware Workload Test Suite       " << std::endl;
    std::cout << "======================================================" << std::endl;

    test_task_generator();
    test_deadline_scheduler_policies();
    test_task_status_and_metrics();
    test_edge_cases();

    std::cout << "======================================================" << std::endl;
    std::cout << "  ALL PERSON B WORKLOAD TESTS PASSED SUCCESSFULLY!    " << std::endl;
    std::cout << "======================================================" << std::endl;
    return 0;
}
