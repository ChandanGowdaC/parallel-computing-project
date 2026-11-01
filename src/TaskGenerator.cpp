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
                             int min_deadline_slack,
                             int deadline_slack_c)
    : endpoints_(endpoints),
      seed_(seed),
      arrival_rate_(arrival_rate),
      deadline_factor_(deadline_factor),
      min_deadline_slack_(min_deadline_slack),
      deadline_slack_c_(deadline_slack_c),
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

void TaskGenerator::set_zoning(bool enabled, double cross_zone_prob, int tile_h, int tile_w, int map_width, int map_height) {
    task_zoning_ = enabled;
    cross_zone_prob_ = cross_zone_prob;
    tile_h_ = tile_h;
    tile_w_ = tile_w;
    num_zones_c_ = std::max(1, map_width / tile_w_);
    int num_zones_r = std::max(1, map_height / tile_h_);
    total_zones_ = std::max(1, num_zones_r * num_zones_c_);

    zone_endpoints_.assign(total_zones_, std::vector<int>());
    other_zone_endpoints_.assign(total_zones_, std::vector<int>());

    for (int ep : endpoints_) {
        int r = ep / map_width;
        int c = ep % map_width;
        int zr = r / tile_h_;
        int zc = c / tile_w_;
        int zid = zr * num_zones_c_ + zc;
        if (zid >= 0 && zid < total_zones_) {
            zone_endpoints_[zid].push_back(ep);
        }
    }

    for (int z = 0; z < total_zones_; ++z) {
        for (int ep : endpoints_) {
            int r = ep / map_width;
            int c = ep % map_width;
            int zr = r / tile_h_;
            int zc = c / tile_w_;
            int zid = zr * num_zones_c_ + zc;
            if (zid != z) {
                other_zone_endpoints_[z].push_back(ep);
            }
        }
    }
}

// ---------------------------------------------------------------------------
// make_task (private)
// ---------------------------------------------------------------------------
Task TaskGenerator::make_task(int release_time, int map_width, int /*map_height*/) {
    int pickup = -1;
    int delivery = -1;

    if (task_zoning_ && total_zones_ > 1) {
        int z = rng_() % total_zones_;
        if (!zone_endpoints_[z].empty()) {
            pickup = zone_endpoints_[z][rng_() % zone_endpoints_[z].size()];
        } else {
            pickup = endpoints_[endpoint_dist_(rng_)];
        }

        std::uniform_real_distribution<double> udist(0.0, 1.0);
        bool home = (udist(rng_) >= cross_zone_prob_);
        if (home && !zone_endpoints_[z].empty()) {
            delivery = zone_endpoints_[z][rng_() % zone_endpoints_[z].size()];
            int tries = 0;
            while (delivery == pickup && zone_endpoints_[z].size() > 1 && tries < 50) {
                delivery = zone_endpoints_[z][rng_() % zone_endpoints_[z].size()];
                tries++;
            }
        } else if (!other_zone_endpoints_[z].empty()) {
            delivery = other_zone_endpoints_[z][rng_() % other_zone_endpoints_[z].size()];
            int tries = 0;
            while (delivery == pickup && other_zone_endpoints_[z].size() > 1 && tries < 50) {
                delivery = other_zone_endpoints_[z][rng_() % other_zone_endpoints_[z].size()];
                tries++;
            }
        } else {
            delivery = endpoints_[endpoint_dist_(rng_)];
        }
    } else {
        // Draw pickup and delivery from endpoints (must be distinct)
        int pickup_idx    = endpoint_dist_(rng_);
        int delivery_idx  = endpoint_dist_(rng_);
        int attempts      = 0;
        while (delivery_idx == pickup_idx && attempts < 100) {
            delivery_idx = endpoint_dist_(rng_);
            ++attempts;
        }
        pickup   = endpoints_[pickup_idx];
        delivery = endpoints_[delivery_idx];
    }

    // Compute minimum feasible travel time as Manhattan distance
    int min_travel = manhattan_distance(pickup, delivery, map_width);
    // Deadline formula: release + k * shortest_path_dist + c
    int slack = static_cast<int>(std::ceil(deadline_factor_ * min_travel)) + deadline_slack_c_;
    if (deadline_slack_c_ == 0 && slack < min_deadline_slack_) {
        slack = min_deadline_slack_;
    }
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
