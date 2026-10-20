#pragma once
#include <string>
#include <vector>
#include <iostream>

// Status of a task in the lifelong MAPF system
enum class TaskStatus {
    UNASSIGNED = 0,
    ASSIGNED   = 1,
    COMPLETED  = 2,
    OVERDUE    = 3
};

inline std::string to_string(TaskStatus status) {
    switch (status) {
        case TaskStatus::UNASSIGNED: return "UNASSIGNED";
        case TaskStatus::ASSIGNED:   return "ASSIGNED";
        case TaskStatus::COMPLETED:  return "COMPLETED";
        case TaskStatus::OVERDUE:    return "OVERDUE";
        default:                     return "UNKNOWN";
    }
}

// Contract defined for Person B (Task Workload & Deadlines)
// Consumed by Person A (System), Person C (Solver), and Person D (Metrics)
struct Task {
    int id = -1;                // Unique task identifier
    int pickup_loc = -1;        // Pickup node/location in graph
    int delivery_loc = -1;      // Delivery/goal node in graph
    int release_time = 0;       // Timestep when task arrives / becomes available
    int deadline = -1;          // Timestep by which task should be delivered (-1 = unconstrained)
    int assigned_agent = -1;    // ID of agent servicing this task (-1 = unassigned)
    int finish_time = -1;       // Timestep when task reached delivery_loc (-1 = incomplete)
    TaskStatus status = TaskStatus::UNASSIGNED;

    Task() = default;

    Task(int id, int pickup, int delivery, int release, int deadline = -1)
        : id(id), pickup_loc(pickup), delivery_loc(delivery),
          release_time(release), deadline(deadline), assigned_agent(-1),
          finish_time(-1), status(TaskStatus::UNASSIGNED) {}

    // Check if task is finished
    bool is_completed() const {
        return finish_time >= 0;
    }

    // Check if task is overdue at a given timestep
    bool is_overdue(int current_timestep) const {
        if (deadline < 0) return false;
        if (is_completed()) return finish_time > deadline;
        return current_timestep > deadline;
    }

    // Compute tardiness: max(0, completion_time - deadline)
    int tardiness(int current_timestep) const {
        if (deadline < 0) return 0;
        int eval_time = is_completed() ? finish_time : current_timestep;
        return (eval_time > deadline) ? (eval_time - deadline) : 0;
    }
};
