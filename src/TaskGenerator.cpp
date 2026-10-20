/**
 * TaskGenerator.cpp — Person B (Deadline-Aware Workload)
 *
 * Implementation of Poisson-arrival task generation with randomised
 * deadline windows.
 *
 * Inter-arrival time model:
 *   Let lambda = task_arrival_rate (tasks per timestep).
 *   Inter-arrival intervals are drawn from Exp(lambda), so on average
 *   `lambda` tasks arrive per timestep (Poisson process).
 *
 * Deadline model:
 *   For a task with pickup_loc p and delivery_loc d:
 *     min_travel = manhattan_distance(p, d)   (lower bound on travel time)
 *     slack      = max(min_deadline_slack, (int)(deadline_factor * min_travel))
 *     deadline   = release_time + slack
 *
 *   This ensures every task is physically achievable (slack >= min_travel) when
 *   deadline_factor >= 1, and deadline_factor > 1 gives agents some wiggle room.
 */

#include "TaskGenerator.h"
#include <stdexcept>
#include <cmath>
#include <algorithm>

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------
TaskGenerator::TaskGenerator(const std::vector<int>& endpoints,
                             int seed,
                             double arrival_rate,
                             double deadline_factor,
                             int min_deadline_slack)
    : endpoints_(endpoints),
      seed_(seed),
      arrival_rate_(arrival_rate),
      deadline_factor_(deadline_factor),
      min_deadline_slack_(min_deadline_slack),
      rng_(seed),
      inter_arrival_dist_(arrival_rate > 0.0 ? arrival_rate : 1.0),
      endpoint_dist_(0, static_cast<int>(endpoints.size()) - 1)
{
    if (endpoints.empty()) {
        throw std::invalid_argument("TaskGenerator: endpoint list must not be empty.");
    }
    if (deadline_factor < 1.0) {
        throw std::invalid_argument("TaskGenerator: deadline_factor must be >= 1.0 "
                                    "(otherwise tasks are infeasible by construction).");
    }

    // Sample the first inter-arrival time
    if (arrival_rate_ > 0.0) {
        next_arrival_t_ = inter_arrival_dist_(rng_);
    } else {
        // Disabled — only batch generation is used
        next_arrival_t_ = std::numeric_limits<double>::max();
    }
}

// ---------------------------------------------------------------------------
// reset
// ---------------------------------------------------------------------------
void TaskGenerator::reset() {
    rng_.seed(seed_);
    inter_arrival_dist_ = std::exponential_distribution<double>(
        arrival_rate_ > 0.0 ? arrival_rate_ : 1.0);
    endpoint_dist_ = std::uniform_int_distribution<int>(
        0, static_cast<int>(endpoints_.size()) - 1);
    next_task_id_   = 0;
    next_arrival_t_ = (arrival_rate_ > 0.0)
                       ? inter_arrival_dist_(rng_)
                       : std::numeric_limits<double>::max();
}

// ---------------------------------------------------------------------------
// generate_arrivals
// ---------------------------------------------------------------------------
std::vector<Task> TaskGenerator::generate_arrivals(int current_timestep,
                                                   int map_width,
                                                   int map_height) {
    std::vector<Task> arrived;

    if (arrival_rate_ <= 0.0) {
        return arrived; // stochastic arrivals disabled
    }

    // Emit all tasks whose scheduled arrival time falls within [current_timestep, current_timestep+1)
    while (next_arrival_t_ < static_cast<double>(current_timestep + 1)) {
        // release_time is rounded to nearest integer timestep
        int release = current_timestep;
        Task t = make_task(release, map_width, map_height);
        arrived.push_back(t);

        // Advance to next arrival
        next_arrival_t_ += inter_arrival_dist_(rng_);
    }

    return arrived;
}

// ---------------------------------------------------------------------------
// generate_batch
// ---------------------------------------------------------------------------
std::vector<Task> TaskGenerator::generate_batch(int num_tasks,
                                                int map_width,
                                                int map_height) {
    std::vector<Task> batch;
    batch.reserve(num_tasks);
    for (int i = 0; i < num_tasks; ++i) {
        batch.push_back(make_task(0, map_width, map_height));
    }
    return batch;
}

// ---------------------------------------------------------------------------
// make_task (private)
// ---------------------------------------------------------------------------
Task TaskGenerator::make_task(int release_time, int map_width, int /*map_height*/) {
    // Draw pickup and delivery from endpoints (must be distinct)
    int pickup_idx    = endpoint_dist_(rng_);
    int delivery_idx  = endpoint_dist_(rng_);
    int attempts      = 0;
    while (delivery_idx == pickup_idx && attempts < 100) {
        delivery_idx = endpoint_dist_(rng_);
        ++attempts;
    }

    int pickup   = endpoints_[pickup_idx];
    int delivery = endpoints_[delivery_idx];

    // Compute minimum feasible travel time as Manhattan distance
    int min_travel = manhattan_distance(pickup, delivery, map_width);
    // Add pickup-to-delivery plus some buffer for congestion
    int slack = std::max(min_deadline_slack_,
                         static_cast<int>(std::ceil(deadline_factor_ * min_travel)));
    int deadline = release_time + slack;

    Task t(next_task_id_++, pickup, delivery, release_time, deadline);
    return t;
}

// ---------------------------------------------------------------------------
// manhattan_distance (static)
// ---------------------------------------------------------------------------
int TaskGenerator::manhattan_distance(int loc_a, int loc_b, int map_width) {
    if (map_width <= 0) return 0;
    int row_a = loc_a / map_width;
    int col_a = loc_a % map_width;
    int row_b = loc_b / map_width;
    int col_b = loc_b % map_width;
    return std::abs(row_a - row_b) + std::abs(col_a - col_b);
}
