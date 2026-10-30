/**
 * DeadlineScheduler.cpp — Person B (Deadline-Aware Workload)
 *
 * Implements three task-assignment policies:
 *
 * FIFO            Sort available (UNASSIGNED, release_time <= now) tasks by
 *                 release_time ascending, assign in that order to idle agents.
 *
 * EDF             Sort by deadline ascending (ties broken by release_time).
 *                 Standard Earliest-Deadline-First — optimal for minimising
 *                 deadline violations on a single-machine / work-conserving system.
 *
 * DEADLINE_AWARE  For each idle agent, pick the task with the lowest urgency
 *                 score, where:
 *                   score = remaining_slack / max(1, dist(agent, pickup))
 *                 Lower score = tighter relative deadline = higher priority.
 *                 Tasks without deadlines get score = INT_MAX (lowest priority).
 *                 This accounts for agent proximity, not just global order.
 */

#include "DeadlineScheduler.h"
#include <algorithm>
#include <numeric>
#include <cmath>
#include <climits>
#include <limits>
#include <stdexcept>

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------
DeadlineScheduler::DeadlineScheduler(SchedulingPolicy policy)
    : policy_(policy) {}

// ---------------------------------------------------------------------------
// assign_tasks
// ---------------------------------------------------------------------------
std::unordered_map<int, int> DeadlineScheduler::assign_tasks(
    std::vector<Task>&       tasks,
    const std::vector<int>&  idle_agents,
    const std::vector<int>&  agent_locations,
    int                      current_timestep,
    int                      map_width) const
{
    std::unordered_map<int, int> assignments; // agent_id -> task_id

    if (idle_agents.empty()) return assignments;

    // Gather indices of tasks that are available (UNASSIGNED, released by now)
    std::vector<int> available;
    available.reserve(tasks.size());
    for (int i = 0; i < static_cast<int>(tasks.size()); ++i) {
        if (tasks[i].status == TaskStatus::UNASSIGNED &&
            tasks[i].release_time <= current_timestep) {
            available.push_back(i);
        }
    }

    if (available.empty()) return assignments;

    // -----------------------------------------------------------------------
    // FIFO and EDF: sort globally, then greedily assign to agents in order
    // -----------------------------------------------------------------------
    if (policy_ == SchedulingPolicy::FIFO || policy_ == SchedulingPolicy::EDF) {
        std::vector<int> sorted_tasks =
            (policy_ == SchedulingPolicy::FIFO)
                ? sort_by_fifo(tasks)   // returns indices into tasks[]
                : sort_by_edf(tasks);

        // Filter to only available indices (sort_by_* returns all UNASSIGNED)
        std::vector<int> sorted_available;
        sorted_available.reserve(available.size());
        for (int idx : sorted_tasks) {
            if (tasks[idx].status == TaskStatus::UNASSIGNED &&
                tasks[idx].release_time <= current_timestep) {
                sorted_available.push_back(idx);
            }
        }

        int n = std::min(static_cast<int>(idle_agents.size()),
                         static_cast<int>(sorted_available.size()));
        for (int i = 0; i < n; ++i) {
            int agent_id = idle_agents[i];
            int task_idx = sorted_available[i];
            tasks[task_idx].assigned_agent = agent_id;
            tasks[task_idx].status         = TaskStatus::ASSIGNED;
            assignments[agent_id]          = tasks[task_idx].id;
        }
        return assignments;
    }

    // -----------------------------------------------------------------------
    // DEADLINE_AWARE: per-agent, find the lowest-urgency-score available task
    // -----------------------------------------------------------------------
    // We track which available task indices have already been claimed this round
    std::vector<bool> claimed(tasks.size(), false);

    for (int agent_id : idle_agents) {
        int agent_loc = (agent_id < static_cast<int>(agent_locations.size()))
                            ? agent_locations[agent_id]
                            : 0;

        double best_score = std::numeric_limits<double>::max();
        int    best_idx   = -1;

        for (int idx : available) {
            if (claimed[idx]) continue;
            double score = urgency_score(tasks[idx], agent_loc,
                                         current_timestep, map_width);
            if (score < best_score) {
                best_score = score;
                best_idx   = idx;
            }
        }

        if (best_idx >= 0) {
            claimed[best_idx]                    = true;
            tasks[best_idx].assigned_agent       = agent_id;
            tasks[best_idx].status               = TaskStatus::ASSIGNED;
            assignments[agent_id]                = tasks[best_idx].id;
        }
    }
    return assignments;
}

// ---------------------------------------------------------------------------
// update_task_statuses
// ---------------------------------------------------------------------------
void DeadlineScheduler::update_task_statuses(std::vector<Task>& tasks,
                                             int current_timestep) const {
    for (auto& t : tasks) {
        // Only mark OVERDUE for tasks that are past their deadline and not done
        if (t.status == TaskStatus::COMPLETED) continue;
        if (t.deadline >= 0 && current_timestep > t.deadline) {
            t.status = TaskStatus::OVERDUE;
        }
    }
}

// ---------------------------------------------------------------------------
// urgency_score (static)
// ---------------------------------------------------------------------------
double DeadlineScheduler::urgency_score(const Task& task,
                                        int agent_location,
                                        int current_timestep,
                                        int map_width) {
    if (task.deadline < 0) {
        // Unconstrained task — lowest priority in deadline-aware mode
        return static_cast<double>(INT_MAX);
    }

    int dist_to_pickup = manhattan_distance(agent_location, task.pickup_loc, map_width);
    int dist_delivery  = manhattan_distance(task.pickup_loc, task.delivery_loc, map_width);
    int total_travel   = dist_to_pickup + dist_delivery;

    // Least Slack First (LSF): remaining slack after estimated travel
    // Lower slack = higher urgency / tighter margin
    return static_cast<double>((task.deadline - current_timestep) - total_travel);
}

// ---------------------------------------------------------------------------
// sort_by_fifo (private)
// ---------------------------------------------------------------------------
std::vector<int> DeadlineScheduler::sort_by_fifo(const std::vector<Task>& tasks) const {
    std::vector<int> indices;
    indices.reserve(tasks.size());
    for (int i = 0; i < static_cast<int>(tasks.size()); ++i) {
        if (tasks[i].status == TaskStatus::UNASSIGNED) {
            indices.push_back(i);
        }
    }
    std::stable_sort(indices.begin(), indices.end(),
        [&tasks](int a, int b) {
            return tasks[a].release_time < tasks[b].release_time;
        });
    return indices;
}

// ---------------------------------------------------------------------------
// sort_by_edf (private)
// ---------------------------------------------------------------------------
std::vector<int> DeadlineScheduler::sort_by_edf(const std::vector<Task>& tasks) const {
    std::vector<int> indices;
    indices.reserve(tasks.size());
    for (int i = 0; i < static_cast<int>(tasks.size()); ++i) {
        if (tasks[i].status == TaskStatus::UNASSIGNED) {
            indices.push_back(i);
        }
    }
    std::stable_sort(indices.begin(), indices.end(),
        [&tasks](int a, int b) {
            const Task& ta = tasks[a];
            const Task& tb = tasks[b];
            // Tasks without deadlines go last
            if (ta.deadline < 0 && tb.deadline < 0)
                return ta.release_time < tb.release_time;
            if (ta.deadline < 0) return false;
            if (tb.deadline < 0) return true;
            if (ta.deadline != tb.deadline)
                return ta.deadline < tb.deadline;
            return ta.release_time < tb.release_time; // tie-break
        });
    return indices;
}

// ---------------------------------------------------------------------------
// sort_by_urgency (private)
// ---------------------------------------------------------------------------
std::vector<int> DeadlineScheduler::sort_by_urgency(
    const std::vector<Task>& tasks,
    int agent_location,
    int current_timestep,
    int map_width) const
{
    std::vector<int> indices;
    indices.reserve(tasks.size());
    for (int i = 0; i < static_cast<int>(tasks.size()); ++i) {
        if (tasks[i].status == TaskStatus::UNASSIGNED) {
            indices.push_back(i);
        }
    }
    std::stable_sort(indices.begin(), indices.end(),
        [&tasks, agent_location, current_timestep, map_width](int a, int b) {
            double sa = urgency_score(tasks[a], agent_location, current_timestep, map_width);
            double sb = urgency_score(tasks[b], agent_location, current_timestep, map_width);
            return sa < sb;
        });
    return indices;
}

// ---------------------------------------------------------------------------
// manhattan_distance (static, private)
// ---------------------------------------------------------------------------
int DeadlineScheduler::manhattan_distance(int loc_a, int loc_b, int map_width) {
    if (map_width <= 0) return 0;
    int row_a = loc_a / map_width;
    int col_a = loc_a % map_width;
    int row_b = loc_b / map_width;
    int col_b = loc_b % map_width;
    return std::abs(row_a - row_b) + std::abs(col_a - col_b);
}
