/**
 * DeadlineMetrics.cpp — Person B (Deadline-Aware Workload)
 *
 * Accumulates deadline KPIs as the simulation runs and dumps them at the end.
 */

#include "DeadlineMetrics.h"
#include <algorithm>
#include <stdexcept>

// ---------------------------------------------------------------------------
// on_task_generated
// ---------------------------------------------------------------------------
void DeadlineMetrics::on_task_generated(const Task& task) {
    ++tasks_total_;
    if (task.deadline < 0) {
        ++tasks_no_deadline_;
    }
}

// ---------------------------------------------------------------------------
// on_task_completed
// ---------------------------------------------------------------------------
void DeadlineMetrics::on_task_completed(const Task& task, int /*current_timestep*/) {
    if (!task.is_completed()) {
        // Caller did not set finish_time before calling — skip gracefully
        return;
    }

    ++tasks_completed_;

    int tard = task.tardiness(task.finish_time);
    sum_tardiness_ += tard;
    if (tard > max_tardiness_) {
        max_tardiness_ = tard;
    }

    if (task.deadline < 0) {
        // Unconstrained task: no deadline to evaluate against
        return;
    }

    if (!task.is_overdue(task.finish_time)) {
        ++tasks_on_time_;
    } else {
        ++tasks_overdue_;
    }
}

// ---------------------------------------------------------------------------
// snapshot
// ---------------------------------------------------------------------------
void DeadlineMetrics::snapshot(int current_timestep) {
    DeadlineSnapshot s;
    s.timestep                 = current_timestep;
    s.tasks_finished_so_far    = tasks_completed_;
    s.tasks_overdue_so_far     = tasks_overdue_;
    s.deadline_satisfaction_rate = deadline_satisfaction_rate();
    s.avg_tardiness_so_far       = avg_tardiness();
    snapshots_.push_back(s);
}

// ---------------------------------------------------------------------------
// populate_run_metrics
// ---------------------------------------------------------------------------
void DeadlineMetrics::populate_run_metrics(RunMetrics& m) const {
    m.tasks_total                = tasks_total_;
    m.tasks_on_time              = tasks_on_time_;
    m.tasks_overdue              = tasks_overdue_;
    m.deadline_satisfaction_rate = deadline_satisfaction_rate();
    m.avg_tardiness              = avg_tardiness();
    m.max_tardiness              = max_tardiness_;
}

// ---------------------------------------------------------------------------
// save_task_records
// ---------------------------------------------------------------------------
void DeadlineMetrics::save_task_records(const std::string& filepath,
                                        const std::vector<Task>& tasks,
                                        int sim_end) const {
    std::ofstream out(filepath);
    if (!out.is_open()) {
        std::cerr << "[DeadlineMetrics] WARNING: could not open " << filepath
                  << " for writing." << std::endl;
        return;
    }

    out << "task_id,pickup_loc,delivery_loc,release_time,deadline,"
           "finish_time,tardiness,status\n";

    for (const auto& t : tasks) {
        int eval_time = t.is_completed() ? t.finish_time : sim_end;
        out << t.id           << ","
            << t.pickup_loc   << ","
            << t.delivery_loc << ","
            << t.release_time << ","
            << t.deadline     << ","
            << t.finish_time  << ","
            << t.tardiness(eval_time) << ","
            << to_string(t.status) << "\n";
    }
    out.close();
}

// ---------------------------------------------------------------------------
// save_snapshot_series
// ---------------------------------------------------------------------------
void DeadlineMetrics::save_snapshot_series(const std::string& filepath) const {
    std::ofstream out(filepath);
    if (!out.is_open()) {
        std::cerr << "[DeadlineMetrics] WARNING: could not open " << filepath
                  << " for writing." << std::endl;
        return;
    }

    out << "timestep,tasks_finished,tasks_overdue,"
           "deadline_satisfaction_rate,avg_tardiness\n";

    for (const auto& s : snapshots_) {
        out << s.timestep                   << ","
            << s.tasks_finished_so_far      << ","
            << s.tasks_overdue_so_far       << ","
            << std::fixed << std::setprecision(4)
            << s.deadline_satisfaction_rate << ","
            << s.avg_tardiness_so_far       << "\n";
    }
    out.close();
}

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------
double DeadlineMetrics::avg_tardiness() const {
    if (tasks_completed_ == 0) return 0.0;
    return static_cast<double>(sum_tardiness_) / tasks_completed_;
}

double DeadlineMetrics::deadline_satisfaction_rate() const {
    int constrained = tasks_total_ - tasks_no_deadline_;
    if (constrained <= 0) return 1.0; // no deadlines → trivially satisfied
    return static_cast<double>(tasks_on_time_) / constrained;
}
