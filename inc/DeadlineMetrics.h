#pragma once
/**
 * DeadlineMetrics.h — Person B (Deadline-Aware Workload)
 *
 * Accumulates and reports deadline-specific metrics throughout the simulation.
 * This is Person B's contribution to the RunMetrics struct (inc/Metrics.h)
 * agreed upon on Day 1 with Person D.
 *
 * Tracked per-simulation:
 *   - tasks_total            : all tasks generated
 *   - tasks_on_time          : completed before or at deadline
 *   - tasks_overdue          : completed after deadline (or not completed)
 *   - tasks_no_deadline      : tasks generated without a deadline (unconstrained)
 *   - deadline_satisfaction_rate = tasks_on_time / (tasks_total - tasks_no_deadline)
 *   - sum_tardiness / avg_tardiness / max_tardiness
 *   - per-timestep snapshot vector for time-series plots (Person D)
 *
 * Per-task record (written to CSV by save_task_records()):
 *   task_id, release_time, deadline, finish_time, tardiness, status
 *
 * Thread safety: NOT thread-safe. The simulation main loop calls these methods
 * from a single thread.  Person C's parallel groups write their Task completions
 * back to the main thread before these methods are called.
 */

#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <sstream>
#include "Task.h"
#include "Metrics.h"

// Per-timestep snapshot for time-series output (consumed by Person D's plotter)
struct DeadlineSnapshot {
    int    timestep;
    int    tasks_finished_so_far;
    int    tasks_overdue_so_far;
    double deadline_satisfaction_rate; // rolling
    double avg_tardiness_so_far;
};

class DeadlineMetrics {
public:
    DeadlineMetrics() = default;

    /**
     * Register a newly generated task. Call when TaskGenerator emits a task.
     * Increments tasks_total; does not affect completion counters.
     */
    void on_task_generated(const Task& task);

    /**
     * Register a task completion event.
     * Updates on_time / overdue counters and tardiness accumulators.
     *
     * @param task              The completed task (finish_time must be set).
     * @param current_timestep  Simulation timestep at which completion was detected.
     */
    void on_task_completed(const Task& task, int current_timestep);

    /**
     * Called once per simulation window to snapshot rolling metrics.
     * Used by Person D to produce time-series plots.
     */
    void snapshot(int current_timestep);

    /**
     * Compute final summary and populate the deadline-related fields of a
     * RunMetrics struct (defined in inc/Metrics.h).  Call at end of simulation.
     */
    void populate_run_metrics(RunMetrics& m) const;

    /**
     * Write per-task records to a CSV file.
     * Columns: task_id, pickup_loc, delivery_loc, release_time, deadline,
     *          finish_time, tardiness, status
     *
     * @param filepath  Output CSV path.
     * @param tasks     All tasks (including incomplete ones at end of simulation).
     * @param sim_end   End-of-simulation timestep for computing tardiness of
     *                  incomplete tasks.
     */
    void save_task_records(const std::string& filepath,
                           const std::vector<Task>& tasks,
                           int sim_end) const;

    /**
     * Write the per-timestep snapshot time series to a CSV.
     * Columns: timestep, tasks_finished, tasks_overdue, deadline_satisfaction_rate,
     *          avg_tardiness
     */
    void save_snapshot_series(const std::string& filepath) const;

    // --- Accessors (for unit tests) ---
    int    tasks_total()      const { return tasks_total_; }
    int    tasks_on_time()    const { return tasks_on_time_; }
    int    tasks_overdue()    const { return tasks_overdue_; }
    int    tasks_no_deadline()const { return tasks_no_deadline_; }
    int    max_tardiness()    const { return max_tardiness_; }
    double avg_tardiness()    const;
    double deadline_satisfaction_rate() const;

    const std::vector<DeadlineSnapshot>& snapshots() const { return snapshots_; }

private:
    int tasks_total_       = 0;
    int tasks_on_time_     = 0;
    int tasks_overdue_     = 0;
    int tasks_no_deadline_ = 0;
    int tasks_completed_   = 0;  // on_time + overdue

    long long sum_tardiness_ = 0;
    int       max_tardiness_ = 0;

    std::vector<DeadlineSnapshot> snapshots_;
};
