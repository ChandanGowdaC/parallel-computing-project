#include "GDRHCR.h"

#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <thread>

namespace {

std::vector<State> make_starts() {
    return {State(0, 0), State(2, 0), State(4, 0), State(20, 0)};
}

void test_visibility_components_are_transitive_and_deterministic() {
    const auto starts = make_starts();
    const std::vector<int> input_ids{3, 2, 0, 1};
    const auto groups = partition_agent_groups(
        starts, input_ids, 2,
        [](int left, int right) { return std::abs(left - right); });
    assert(groups.size() == 2);
    assert((groups[0] == std::vector<int>{0, 1, 2}));
    assert((groups[1] == std::vector<int>{3}));

    const auto reordered = partition_agent_groups(
        starts, std::vector<int>{1, 0, 3, 2}, 2,
        [](int left, int right) { return std::abs(left - right); });
    assert(reordered == groups);
}

void test_group_tasks_preserve_rhcr_contract_fields() {
    const auto starts = make_starts();
    const std::vector<std::vector<std::pair<int, int>>> goals{
        {{10, 0}, {11, 5}}, {{12, 0}}, {{13, 1}}, {{14, 2}}};
    const GroupPlanningConfig config{3, 16, 9, 1};
    const auto groups = partition_agent_groups(
        starts, std::vector<int>{0, 1, 2, 3}, 2,
        [](int left, int right) { return std::abs(left - right); });
    const auto tasks = make_group_planning_tasks(groups, starts, goals, config);

    assert(tasks.size() == 2);
    assert(tasks[0].group_id == 0);
    assert((tasks[0].agent_ids == std::vector<int>{0, 1, 2}));
    assert(tasks[0].starts.size() == 3 && tasks[0].starts[1].location == 2);
    assert(tasks[0].goals[0] == goals[0] && tasks[0].goals[2] == goals[2]);
    assert(tasks[0].simulation_window == 3);
    assert(tasks[0].planning_window == 16);
    assert(tasks[0].time_limit == 9);
    assert(tasks[0].k_robust == 1);
}

void test_parallel_dispatch_merges_by_global_agent_id() {
    const auto starts = make_starts();
    std::vector<std::vector<std::pair<int, int>>> goals(4);
    const GroupPlanningConfig config{1, 10, 5, 0};
    const auto groups = partition_agent_groups(
        starts, std::vector<int>{0, 1, 2, 3}, 2,
        [](int left, int right) { return std::abs(left - right); });
    const auto tasks = make_group_planning_tasks(groups, starts, goals, config);

    std::atomic<int> active(0);
    std::atomic<int> peak(0);
    const WindowedGroupSolverFn solver = [&active, &peak](const GroupPlanningTask& task) {
        const int now_active = ++active;
        int observed_peak = peak.load();
        while (observed_peak < now_active &&
               !peak.compare_exchange_weak(observed_peak, now_active)) {}
        std::this_thread::sleep_for(std::chrono::milliseconds(25));

        GroupPlanningResult result;
        result.group_id = task.group_id;
        result.success = true;
        for (const auto& start : task.starts) {
            Path path;
            path.push_back(start);
            result.paths.push_back(path);
        }
        --active;
        return result;
    };

    const auto results = solve_group_tasks(tasks, solver, 2);
    assert(results.size() == 2);
    assert(peak.load() >= 2);

    std::vector<Path> merged;
    std::string error;
    assert(merge_group_results(tasks, results, starts.size(), merged, &error));
    assert(error.empty());
    assert(merged.size() == starts.size());
    for (std::size_t id = 0; id < starts.size(); ++id) {
        assert(merged[id].size() == 1);
        assert(merged[id][0].location == starts[id].location);
    }
}

void test_merge_failure_is_atomic_and_preserves_unplanned_paths() {
    GroupPlanningTask task;
    task.group_id = 0;
    task.agent_ids.push_back(1);
    task.starts.push_back(State(1, 0));
    task.goals.push_back(std::vector<std::pair<int, int>>(1, std::make_pair(9, 0)));
    task.simulation_window = 1;
    task.planning_window = 4;
    task.time_limit = 5;
    const std::vector<GroupPlanningTask> tasks{task};
    std::vector<Path> merged(3);
    merged[0].push_back(State(0, 0));
    merged[2].push_back(State(2, 0));
    const auto original = merged;
    GroupPlanningResult bad_result;
    bad_result.group_id = 0;
    bad_result.success = true;
    const std::vector<GroupPlanningResult> bad_results{bad_result};
    std::string error;
    assert(!merge_group_results(tasks, bad_results, 3, merged, &error));
    assert(!error.empty());
    assert(merged[0][0].location == original[0][0].location);
    assert(merged[1].empty());
    assert(merged[2][0].location == original[2][0].location);

    GroupPlanningResult good;
    good.group_id = 0;
    good.success = true;
    good.paths.push_back(Path{State(1, 0), State(3, 1)});
    assert(merge_group_results(tasks, {good}, 3, merged, &error));
    assert(merged[0][0].location == 0);
    assert(merged[1].size() == 2 && merged[1][1].location == 3);
    assert(merged[2][0].location == 2);
}

void test_collision_validator_matches_rhcr_window_semantics() {
    std::string error;
    assert(validate_joint_paths(
        {Path{State(0, 0), State(1, 1)}, Path{State(2, 0), State(3, 1)}}, &error));
    assert(error.empty());
    assert(!validate_joint_paths(
        {Path{State(0, 0), State(1, 1)}, Path{State(1, 0), State(0, 1)}}, &error));
    assert(error.find("opposite directions") != std::string::npos);
    assert(!validate_joint_paths(
        {Path{State(4, 0)}, Path{State(4, 0), State(5, 1)}}, &error));
    // RHCR checks only the common path window unless hold-endpoints is enabled.
    assert(validate_joint_paths(
        {Path{State(6, 0)}, Path{State(7, 0), State(6, 1)}}, &error));
}

void test_bad_inputs_and_solver_exceptions_are_reported() {
    bool rejected = false;
    try {
        (void)partition_agent_groups(
            make_starts(), std::vector<int>{0, 0}, 1,
            [](int left, int right) { return std::abs(left - right); });
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    rejected = false;
    try {
        (void)partition_agent_groups(
            make_starts(), std::vector<int>{0}, -1,
            [](int left, int right) { return std::abs(left - right); });
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    rejected = false;
    try {
        const WindowedGroupSolverFn failing = [](const GroupPlanningTask&) -> GroupPlanningResult {
            throw std::runtime_error("worker failure");
        };
        GroupPlanningTask task;
        task.group_id = 0;
        (void)solve_group_tasks(std::vector<GroupPlanningTask>{task}, failing, 2);
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    assert(rejected);
}

} // namespace

int main() {
    test_visibility_components_are_transitive_and_deterministic();
    test_group_tasks_preserve_rhcr_contract_fields();
    test_parallel_dispatch_merges_by_global_agent_id();
    test_merge_failure_is_atomic_and_preserves_unplanned_paths();
    test_collision_validator_matches_rhcr_window_semantics();
    test_bad_inputs_and_solver_exceptions_are_reported();
}
