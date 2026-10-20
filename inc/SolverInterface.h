#pragma once
#include <vector>
#include <string>
#include <functional>
#include "States.h"
#include "BasicGraph.h"

// Group definition for GD-RHCR (Person C / Person A contract)
// Each group represents a spatially-partitioned subset of agents to be planned concurrently.
struct GroupPlanningTask {
    int group_id;                                        // Unique group index
    std::vector<int> agent_ids;                          // Original global agent IDs
    std::vector<State> starts;                           // Initial states for agents in this group
    std::vector<std::vector<std::pair<int, int>>> goals; // Goal sequence <location, release_time>
    int simulation_window;                               // Replanning window (h)
    int planning_window;                                 // Collision-resolution horizon (w)
    int time_limit;                                      // Timeout per solve in seconds
    int k_robust = 0;                                    // Robustness parameter
};

// Result returned by solving a single group's windowed MAPF problem
struct GroupPlanningResult {
    int group_id;                                        // ID matching GroupPlanningTask
    bool success = false;                                // Whether valid conflict-free paths were found
    double runtime = 0.0;                                // CPU/wall-clock time taken for this group solve (seconds)
    std::vector<Path> paths;                             // Resulting paths (indexed 0..group_size-1)
    std::string error_message = "";                      // Diagnostic message if solve failed
};

// Typedef for a windowed group solver entry point
// Person C will implement this entry point or dispatch to MAPFSolver instances via ThreadPool.
using WindowedGroupSolverFn = std::function<GroupPlanningResult(const GroupPlanningTask&)>;
