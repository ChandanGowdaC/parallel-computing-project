#pragma once
/**
 * TaskGenerator.h — Person B (Deadline-Aware Workload)
 *
 * Responsible for generating Task objects with:
 *   - Poisson-distributed arrival times (inter-arrival ~ Exp(1/lambda))
 *   - Randomised deadline windows:   deadline = release_time + slack
 *     where slack ~ Uniform[ min_slack, max_slack ]
 *     and min_slack / max_slack are derived from (deadline_factor * Manhattan-distance estimate).
 *
 * Design constraints imposed by Day-1 interface contracts:
 *   - Task struct is defined in inc/Task.h and is consumed by A, C, and D unchanged.
 *   - pickup_loc / delivery_loc are graph endpoint indices drawn from the map.
 *   - release_time is in simulation timesteps, not wall-clock seconds.
 *
 * Usage:
 *   TaskGenerator gen(endpoints, seed, lambda, deadline_factor);
 *   // At each timestep t, call:
 *   std::vector<Task> new_tasks = gen.generate_arrivals(t, num_agents, current_timestamp);
 */

#include <vector>
#include <random>
#include <stdexcept>
#include "Task.h"

class TaskGenerator {
public:
    /**
     * @param endpoints         List of valid pickup/delivery graph-node indices.
     * @param seed              RNG seed for reproducibility (matches --seed CLI flag).
     * @param arrival_rate      Poisson lambda: expected tasks per simulation timestep.
     *                          Use 0 to disable stochastic arrivals (tasks pre-queued only).
     * @param deadline_factor   Multiplier applied to the minimum Manhattan-distance travel
     *                          estimate to set the base slack window.
     *                          E.g. 2.0 means deadline = release + 2*min_travel_time.
     * @param min_deadline_slack Absolute minimum slack (timesteps) regardless of distance.
     */
    TaskGenerator(const std::vector<int>& endpoints,
                  int seed,
                  double arrival_rate,
                  double deadline_factor,
                  int min_deadline_slack = 10);

    /**
     * Generate all tasks that arrive at simulation timestep `t`.
     *
     * Internally, the generator pre-computes the next inter-arrival offset using
     * an Exponential distribution and emits a batch of tasks whenever the
     * accumulated inter-arrival time aligns with the current timestep.
     *
     * @param current_timestep   Current simulation time (integer timestep).
     * @param map_width          Map width, used for Manhattan distance approximation.
     * @param map_height         Map height, used for Manhattan distance approximation.
     * @return                   (Possibly empty) list of newly released Tasks.
     */
    std::vector<Task> generate_arrivals(int current_timestep,
                                        int map_width,
                                        int map_height);

    /**
     * Deterministically pre-generate a fixed batch of N tasks, all with
     * release_time = 0.  Useful for offline/batch benchmarks.
     *
     * @param num_tasks  Total tasks to generate.
     * @param map_width  Map width for distance heuristic.
     * @param map_height Map height for distance heuristic.
     */
    std::vector<Task> generate_batch(int num_tasks,
                                     int map_width,
                                     int map_height);

    /**
     * Reset the internal RNG and task-id counter to the initial seed.
     * Allows re-running the same arrival sequence.
     */
    void reset();

    // Accessors
    double get_arrival_rate()    const { return arrival_rate_; }
    double get_deadline_factor() const { return deadline_factor_; }
    int    get_tasks_generated() const { return next_task_id_; }

private:
    std::vector<int> endpoints_;
    int              seed_;
    double           arrival_rate_;
    double           deadline_factor_;
    int              min_deadline_slack_;

    // RNG state
    std::mt19937                          rng_;
    std::exponential_distribution<double> inter_arrival_dist_;
    std::uniform_int_distribution<int>    endpoint_dist_;

    // Counters
    int    next_task_id_   = 0;
    double next_arrival_t_ = 0.0; // fractional timestep of next arrival

    /**
     * Build a single Task from two distinct endpoint indices.
     * Computes the Manhattan-distance-based deadline slack.
     */
    Task make_task(int release_time, int map_width, int map_height);

    /**
     * Manhattan distance between two endpoint indices using map dimensions.
     * Used as a proxy for minimum travel time when heuristic tables are not
     * available (they are precomputed in KivaGraph but not passed here to
     * keep TaskGenerator map-agnostic).
     */
    static int manhattan_distance(int loc_a, int loc_b, int map_width);
};
