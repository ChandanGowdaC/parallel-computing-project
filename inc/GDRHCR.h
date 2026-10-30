#pragma once

#include <algorithm>
#include <functional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "BasicGraph.h"
#include "ParallelExecutor.h"
#include "SolverInterface.h"

struct GroupPlanningConfig {
    int simulation_window = 1;
    int planning_window = 1;
    int time_limit = 1;
    int k_robust = 0;
};

// Make deterministic connected components in the visibility graph over the
// requested agents. DistanceFn receives two map-cell IDs and returns their
// spatial distance; the BasicGraph overload below uses RHCR's Manhattan metric.
template <typename DistanceFn>
std::vector<std::vector<int>> partition_agent_groups(
    const std::vector<State>& starts,
    std::vector<int> agent_ids,
    int visibility_radius,
    DistanceFn distance) {
    if (visibility_radius < 0) {
        throw std::invalid_argument("visibility radius must be non-negative");
    }
    std::sort(agent_ids.begin(), agent_ids.end());
    if (std::adjacent_find(agent_ids.begin(), agent_ids.end()) != agent_ids.end()) {
        throw std::invalid_argument("agent IDs must be unique");
    }
    for (const int id : agent_ids) {
        if (id < 0 || static_cast<std::size_t>(id) >= starts.size()) {
            throw std::out_of_range("agent ID is outside the start-state array");
        }
        if (starts[id].location < 0) {
            throw std::invalid_argument("agent start location must be a valid map cell");
        }
    }

    std::vector<bool> visited(agent_ids.size(), false);
    std::vector<std::vector<int>> groups;
    for (std::size_t seed = 0; seed < agent_ids.size(); ++seed) {
        if (visited[seed]) {
            continue;
        }
        std::vector<std::size_t> pending(1, seed);
        std::vector<int> group;
        visited[seed] = true;
        while (!pending.empty()) {
            const std::size_t current = pending.back();
            pending.pop_back();
            const int current_id = agent_ids[current];
            group.push_back(current_id);

            for (std::size_t candidate = 0; candidate < agent_ids.size(); ++candidate) {
                if (visited[candidate]) {
                    continue;
                }
                const int candidate_id = agent_ids[candidate];
                const int separation = distance(
                    starts[current_id].location, starts[candidate_id].location);
                if (separation < 0) {
                    throw std::invalid_argument("distance function returned a negative value");
                }
                if (separation <= visibility_radius) {
                    visited[candidate] = true;
                    pending.push_back(candidate);
                }
            }
        }
        std::sort(group.begin(), group.end());
        groups.push_back(std::move(group));
    }
    return groups;
}

inline std::vector<std::vector<int>> partition_agent_groups(
    const BasicGraph& graph,
    const std::vector<State>& starts,
    const std::vector<int>& agent_ids,
    int visibility_radius) {
    for (const int id : agent_ids) {
        if (id < 0 || static_cast<std::size_t>(id) >= starts.size() ||
            starts[id].location < 0 || starts[id].location >= graph.size()) {
            throw std::out_of_range("agent start location is outside the map");
        }
    }
    return partition_agent_groups(
        starts, agent_ids, visibility_radius,
        [&graph](int left, int right) {
            return graph.get_Manhattan_distance(left, right);
        });
}

inline std::vector<GroupPlanningTask> make_group_planning_tasks(
    const std::vector<std::vector<int>>& groups,
    const std::vector<State>& starts,
    const std::vector<std::vector<std::pair<int, int>>>& goals,
    const GroupPlanningConfig& config) {
    if (starts.size() != goals.size()) {
        throw std::invalid_argument("start and goal arrays must have the same size");
    }
    if (config.simulation_window <= 0 || config.planning_window <= 0 ||
        config.time_limit <= 0 || config.k_robust < 0) {
        throw std::invalid_argument("window, time limit, and robustness settings are invalid");
    }

    std::vector<GroupPlanningTask> tasks;
    tasks.reserve(groups.size());
    std::unordered_set<int> assigned_agents;
    for (std::size_t group_index = 0; group_index < groups.size(); ++group_index) {
        if (groups[group_index].empty()) {
            throw std::invalid_argument("agent groups must not be empty");
        }
        GroupPlanningTask task;
        task.group_id = static_cast<int>(group_index);
        task.simulation_window = config.simulation_window;
        task.planning_window = config.planning_window;
        task.time_limit = config.time_limit;
        task.k_robust = config.k_robust;
        for (const int id : groups[group_index]) {
            if (id < 0 || static_cast<std::size_t>(id) >= starts.size()) {
                throw std::out_of_range("agent ID is outside the start/goal arrays");
            }
            if (!assigned_agents.insert(id).second) {
                throw std::invalid_argument("an agent cannot appear in multiple groups");
            }
            task.agent_ids.push_back(id);
            task.starts.push_back(starts[id]);
            task.goals.push_back(goals[id]);
        }
        tasks.push_back(std::move(task));
    }
    return tasks;
}

// The supplied solver must use independent solver state per invocation (or
// otherwise be thread-safe). In production, capture a factory and construct a
// fresh MAPFSolver and SingleAgentSolver inside each invocation.
inline std::vector<GroupPlanningResult> solve_group_tasks(
    const std::vector<GroupPlanningTask>& tasks,
    const WindowedGroupSolverFn& group_solver,
    std::size_t thread_count) {
    if (!group_solver) {
        throw std::invalid_argument("group solver callback must be set");
    }
    std::unordered_set<int> group_ids;
    for (const auto& task : tasks) {
        if (!group_ids.insert(task.group_id).second) {
            throw std::invalid_argument("group IDs must be unique");
        }
    }

    ParallelExecutor executor(thread_count);
    return executor.parallel_map(tasks, [&group_solver](const GroupPlanningTask& task) {
        return group_solver(task);
    });
}

inline bool validate_joint_paths(
    const std::vector<Path>& paths,
    std::string* error_message = nullptr) {
    const auto fail = [error_message](const std::string& message) {
        if (error_message != nullptr) {
            *error_message = message;
        }
        return false;
    };
    for (std::size_t first = 0; first < paths.size(); ++first) {
        for (std::size_t second = first + 1; second < paths.size(); ++second) {
            const std::size_t common_length = std::min(paths[first].size(), paths[second].size());
            for (std::size_t time = 0; time < common_length; ++time) {
                const int first_location = paths[first][time].location;
                const int second_location = paths[second][time].location;
                if (first_location == second_location) {
                    return fail("two agents occupy the same cell in the merged plan");
                }
                if (time + 1 < common_length &&
                    first_location == paths[second][time + 1].location &&
                    second_location == paths[first][time + 1].location) {
                    return fail("two agents traverse the same edge in opposite directions");
                }
            }
        }
    }
    if (error_message != nullptr) {
        error_message->clear();
    }
    return true;
}

// Merge by original agent ID. On failure, merged_paths is left unchanged.
// For a partial replan, initialize merged_paths with the previous global plan;
// paths belonging to agents outside the tasks are preserved.
inline bool merge_group_results(
    const std::vector<GroupPlanningTask>& tasks,
    const std::vector<GroupPlanningResult>& results,
    std::size_t total_agents,
    std::vector<Path>& merged_paths,
    std::string* error_message = nullptr) {
    const auto fail = [error_message](const std::string& message) {
        if (error_message != nullptr) {
            *error_message = message;
        }
        return false;
    };
    if (merged_paths.size() != 0 && merged_paths.size() != total_agents) {
        return fail("existing global plan size does not match the agent count");
    }
    if (tasks.size() != results.size()) {
        return fail("there must be exactly one result per group task");
    }

    std::unordered_map<int, const GroupPlanningTask*> task_by_id;
    std::unordered_set<int> expected_agents;
    for (const auto& task : tasks) {
        if (!task_by_id.emplace(task.group_id, &task).second) {
            return fail("group task IDs must be unique");
        }
        if (task.agent_ids.size() != task.starts.size() ||
            task.agent_ids.size() != task.goals.size()) {
            return fail("group task agent, start, and goal counts do not match");
        }
        for (const int id : task.agent_ids) {
            if (id < 0 || static_cast<std::size_t>(id) >= total_agents) {
                return fail("group task contains an invalid global agent ID");
            }
            if (!expected_agents.insert(id).second) {
                return fail("an agent appears in more than one group task");
            }
        }
    }

    std::unordered_set<int> result_ids;
    std::vector<Path> candidate = merged_paths;
    if (candidate.empty()) {
        candidate.resize(total_agents);
    }
    for (const auto& result : results) {
        const auto task_it = task_by_id.find(result.group_id);
        if (task_it == task_by_id.end() || !result_ids.insert(result.group_id).second) {
            return fail("group result ID is unknown or repeated");
        }
        const GroupPlanningTask& task = *task_it->second;
        if (!result.success) {
            return fail(result.error_message.empty() ? "a group solver failed" : result.error_message);
        }
        if (result.paths.size() != task.agent_ids.size()) {
            return fail("group result path count does not match its agent count");
        }
        for (std::size_t local_id = 0; local_id < task.agent_ids.size(); ++local_id) {
            if (result.paths[local_id].empty()) {
                return fail("group result contains an empty path");
            }
            candidate[task.agent_ids[local_id]] = result.paths[local_id];
        }
    }
    if (result_ids.size() != task_by_id.size()) {
        return fail("one or more group results are missing");
    }
    std::string collision_error;
    if (!validate_joint_paths(candidate, &collision_error)) {
        return fail(collision_error);
    }

    merged_paths.swap(candidate);
    if (error_message != nullptr) {
        error_message->clear();
    }
    return true;
}
