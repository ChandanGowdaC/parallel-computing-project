#pragma once
/**
 * DeadlineScheduler.h — Person B (Deadline-Aware Workload)
 *
 * Owns the scheduling policy layer: given a pool of unassigned tasks and a
 * pool of idle agents, it selects which task each agent should take next.
 *
 * Three policies are provided so that Person D can sweep and compare them:
 *
 *   FIFO            — First-In-First-Out by release_time (original RHCR behaviour)
 *   EDF             — Earliest-Deadline-First (classic real-time scheduling)
 *   DEADLINE_AWARE  — Hybrid: urgency score = (deadline - current_time) /
 *                              max(1, estimated_travel_time).  Tasks with lower
 *                              score (tightest relative slack) are scheduled first.
 *                              Falls back to EDF for tasks without deadlines.
 *
 * The scheduler is intentionally stateless between calls — all state lives in
 * the task list (Task.h) and in the BasicSystem (inc/BasicSystem.h).  Person C
 * can call assign_tasks() before launching each group-planning round without
 * any shared-state hazard.
 *
 * Interface contract (Day-1 agreed):
 *   - Input:  mutable ref to vector<Task>, set of idle agent ids, current_timestep
 *   - Output: mapping agent_id → task_id (written into Task::assigned_agent)
 *   - Does NOT modify Task::finish_time or Task::status — that is Person A/C's job.
 */

#include <vector>
#include <unordered_map>
#include <string>
#include "Task.h"

enum class SchedulingPolicy {
    FIFO,
    EDF,
    DEADLINE_AWARE
};

inline SchedulingPolicy parse_scheduling_policy(const std::string& s) {
    if (s == "FIFO")           return SchedulingPolicy::FIFO;
    if (s == "EDF")            return SchedulingPolicy::EDF;
    if (s == "DEADLINE_AWARE") return SchedulingPolicy::DEADLINE_AWARE;
    throw std::invalid_argument("Unknown scheduling policy: " + s);
}

inline std::string to_string(SchedulingPolicy p) {
    switch (p) {
        case SchedulingPolicy::FIFO:           return "FIFO";
        case SchedulingPolicy::EDF:            return "EDF";
        case SchedulingPolicy::DEADLINE_AWARE: return "DEADLINE_AWARE";
        default:                               return "UNKNOWN";
    }
}

class DeadlineScheduler {
public:
    explicit DeadlineScheduler(SchedulingPolicy policy = SchedulingPolicy::EDF);

    /**
     * Assign available tasks to idle agents according to the active policy.
     *
     * @param tasks             Full task pool (mutable; assigned_agent field updated).
     * @param idle_agents       Agent IDs that currently have no pending task.
     * @param agent_locations   Current graph-node location of each agent (indexed by agent id).
     * @param current_timestep  Current simulation timestep.
     * @param map_width         Map width for distance heuristic.
     * @return                  Map from agent_id to assigned task_id.
     *                          Agents that got no task are not in the map.
     */
    std::unordered_map<int, int> assign_tasks(
        std::vector<Task>&       tasks,
        const std::vector<int>&  idle_agents,
        const std::vector<int>&  agent_locations,
        int                      current_timestep,
        int                      map_width) const;

    /**
     * Mark a task as at-risk if its remaining slack falls below a threshold.
     * This is a purely diagnostic pass — it sets TaskStatus::OVERDUE when
     * current_timestep > deadline but task is not yet completed, and leaves
     * COMPLETED/UNASSIGNED tasks unchanged.
     *
     * Called by the simulation loop at each timestep for the metrics tracker.
     */
    void update_task_statuses(std::vector<Task>& tasks, int current_timestep) const;

    /**
     * Compute urgency score for a single task using Least Slack First (LSF).
     * Lower score = more urgent (less slack remaining after travel).
     *
     * score = (deadline - current_time) - (dist(agent, pickup) + dist(pickup, delivery))
     *
     * If task has no deadline (deadline == -1), score = INT_MAX (lowest urgency).
     */
    static double urgency_score(const Task& task,
                                int agent_location,
                                int current_timestep,
                                int map_width);

    SchedulingPolicy get_policy() const { return policy_; }
    void             set_policy(SchedulingPolicy p) { policy_ = p; }

private:
    SchedulingPolicy policy_;

    // Sort indices of `tasks` by FIFO key (release_time)
    std::vector<int> sort_by_fifo(const std::vector<Task>& tasks) const;

    // Sort indices of `tasks` by EDF key (deadline, then release_time)
    std::vector<int> sort_by_edf(const std::vector<Task>& tasks) const;

    // Sort indices of `tasks` by urgency score relative to a specific agent
    std::vector<int> sort_by_urgency(const std::vector<Task>& tasks,
                                     int agent_location,
                                     int current_timestep,
                                     int map_width) const;

    // Manhattan distance helper
    static int manhattan_distance(int loc_a, int loc_b, int map_width);
};
