/**
 * metrics_logger.h — Thread-safe CSV metrics logger for GD-RHCR experiments.
 *
 * Person D's interface contract implementation.
 * Persons B (task layer) and C (parallel core) include this to write metrics.
 *
 * Usage:
 *   MetricsLogger logger("results/raw", run_config);
 *   logger.logRunMetrics(run_data);
 *   logger.logTaskMetrics(task_data);
 *   logger.logEpisodeMetrics(episode_data);
 *   logger.finalize();   // flushes and closes all files
 */

#ifndef METRICS_LOGGER_H
#define METRICS_LOGGER_H

#include <string>
#include <fstream>
#include <mutex>
#include <vector>
#include <chrono>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <filesystem>

namespace metrics {

// ─────────────────────────────────────────────
// Data structures matching metrics_schema.json
// ─────────────────────────────────────────────

struct RunConfig {
    std::string map_name;
    std::string scenario;        // "KIVA" or "SORTING"
    std::string solver;          // "PBS", "ECBS", "WHCA"
    std::string solver_mode;     // "sequential" or "parallel"
    int thread_count       = 1;
    int agent_count        = 100;
    double task_arrival_rate = 1.0;
    int planning_horizon_h = 20;
    int planning_window_w  = 10;
    double visibility_radius_v = 0.0;  // 0 = off (sequential)
    int seed               = 42;

    // Generates a unique run_id from config
    std::string makeRunId() const {
        std::ostringstream oss;
        oss << map_name << "_" << solver_mode << "_a" << agent_count
            << "_t" << thread_count << "_s" << seed;
        return oss.str();
    }
};

struct RunMetrics {
    int simulation_timesteps      = 0;
    double total_runtime_ms       = 0.0;
    double solver_runtime_ms      = 0.0;
    int num_replan_episodes       = 0;
    int num_tasks_generated       = 0;
    int num_tasks_completed       = 0;
    double throughput             = 0.0;
    int num_groups                = 1;
    double avg_group_size         = 0.0;
    double max_group_solve_ms     = 0.0;
    int num_collisions            = 0;
    double deadline_satisfaction_rate = 0.0;
    double avg_tardiness          = 0.0;
    double max_tardiness          = 0.0;
    int num_tasks_overdue         = 0;
};

struct TaskMetrics {
    int task_id             = -1;
    int release_time        = 0;
    int deadline            = 0;
    int pickup_x            = 0;
    int pickup_y            = 0;
    int delivery_x          = 0;
    int delivery_y          = 0;
    int assigned_agent      = -1;
    int completion_time     = -1;
    int tardiness           = 0;
    std::string status;          // "completed", "overdue", "in_progress", "unassigned"
    std::string scheduling_policy; // "FIFO", "EDF", "DEADLINE_AWARE"
};

struct EpisodeMetrics {
    int episode_id                = 0;
    int timestep                  = 0;
    int num_groups                = 1;
    std::string group_sizes;      // comma-separated
    double solve_time_ms          = 0.0;
    double max_group_solve_ms     = 0.0;
    double min_group_solve_ms     = 0.0;
    double merge_time_ms          = 0.0;
    int inter_group_collisions    = 0;
};


// ─────────────────────────────────────────────
// Logger class
// ─────────────────────────────────────────────

class MetricsLogger {
public:
    /**
     * @param output_dir  Directory to write CSV files into (e.g., "results/raw")
     * @param config      Run configuration — used to generate run_id and populate config columns
     */
    MetricsLogger(const std::string& output_dir, const RunConfig& config)
        : config_(config), run_id_(config.makeRunId()), output_dir_(output_dir)
    {
        // Create output directory if needed
        std::filesystem::create_directories(output_dir);

        // Capture start timestamp
        auto now = std::chrono::system_clock::now();
        auto time_t_now = std::chrono::system_clock::to_time_t(now);
        std::ostringstream ts;
        ts << std::put_time(std::gmtime(&time_t_now), "%Y-%m-%dT%H:%M:%SZ");
        timestamp_ = ts.str();

        // Open task-level CSV
        std::string task_path = output_dir_ + "/tasks_" + run_id_ + ".csv";
        task_file_.open(task_path);
        if (task_file_.is_open()) {
            task_file_ << "run_id,task_id,release_time,deadline,"
                       << "pickup_x,pickup_y,delivery_x,delivery_y,"
                       << "assigned_agent,completion_time,tardiness,"
                       << "status,scheduling_policy\n";
        }

        // Open episode-level CSV
        std::string ep_path = output_dir_ + "/episodes_" + run_id_ + ".csv";
        episode_file_.open(ep_path);
        if (episode_file_.is_open()) {
            episode_file_ << "run_id,episode_id,timestep,num_groups,group_sizes,"
                          << "solve_time_ms,max_group_solve_ms,min_group_solve_ms,"
                          << "merge_time_ms,inter_group_collisions\n";
        }
    }

    ~MetricsLogger() {
        finalize();
    }

    // ── Per-task logging (called by Person B's task tracker) ──
    void logTaskMetrics(const TaskMetrics& t) {
        std::lock_guard<std::mutex> lock(task_mutex_);
        if (!task_file_.is_open()) return;
        task_file_ << run_id_ << ","
                   << t.task_id << ","
                   << t.release_time << ","
                   << t.deadline << ","
                   << t.pickup_x << "," << t.pickup_y << ","
                   << t.delivery_x << "," << t.delivery_y << ","
                   << t.assigned_agent << ","
                   << t.completion_time << ","
                   << t.tardiness << ","
                   << t.status << ","
                   << t.scheduling_policy << "\n";
    }

    // ── Per-episode logging (called by Person C's parallel core) ──
    void logEpisodeMetrics(const EpisodeMetrics& e) {
        std::lock_guard<std::mutex> lock(episode_mutex_);
        if (!episode_file_.is_open()) return;
        episode_file_ << run_id_ << ","
                      << e.episode_id << ","
                      << e.timestep << ","
                      << e.num_groups << ","
                      << "\"" << e.group_sizes << "\","
                      << e.solve_time_ms << ","
                      << e.max_group_solve_ms << ","
                      << e.min_group_solve_ms << ","
                      << e.merge_time_ms << ","
                      << e.inter_group_collisions << "\n";
    }

    // ── Run-level summary (called once at end of run) ──
    void logRunMetrics(const RunMetrics& r) {
        std::string run_path = output_dir_ + "/run_" + run_id_ + ".csv";
        std::ofstream run_file(run_path);
        if (!run_file.is_open()) {
            std::cerr << "[MetricsLogger] ERROR: Cannot open " << run_path << "\n";
            return;
        }

        // Header
        run_file << "run_id,timestamp,map_name,scenario,solver,solver_mode,"
                 << "thread_count,agent_count,task_arrival_rate,"
                 << "planning_horizon_h,planning_window_w,visibility_radius_v,seed,"
                 << "simulation_timesteps,total_runtime_ms,solver_runtime_ms,"
                 << "num_replan_episodes,num_tasks_generated,num_tasks_completed,"
                 << "throughput,num_groups,avg_group_size,max_group_solve_ms,"
                 << "num_collisions,deadline_satisfaction_rate,"
                 << "avg_tardiness,max_tardiness,num_tasks_overdue\n";

        // Data row
        run_file << run_id_ << ","
                 << timestamp_ << ","
                 << config_.map_name << ","
                 << config_.scenario << ","
                 << config_.solver << ","
                 << config_.solver_mode << ","
                 << config_.thread_count << ","
                 << config_.agent_count << ","
                 << config_.task_arrival_rate << ","
                 << config_.planning_horizon_h << ","
                 << config_.planning_window_w << ","
                 << config_.visibility_radius_v << ","
                 << config_.seed << ","
                 << r.simulation_timesteps << ","
                 << r.total_runtime_ms << ","
                 << r.solver_runtime_ms << ","
                 << r.num_replan_episodes << ","
                 << r.num_tasks_generated << ","
                 << r.num_tasks_completed << ","
                 << r.throughput << ","
                 << r.num_groups << ","
                 << r.avg_group_size << ","
                 << r.max_group_solve_ms << ","
                 << r.num_collisions << ","
                 << r.deadline_satisfaction_rate << ","
                 << r.avg_tardiness << ","
                 << r.max_tardiness << ","
                 << r.num_tasks_overdue << "\n";

        run_file.close();
        std::cout << "[MetricsLogger] Run metrics saved to " << run_path << "\n";
    }

    // ── Flush and close all files ──
    void finalize() {
        {
            std::lock_guard<std::mutex> lock(task_mutex_);
            if (task_file_.is_open()) {
                task_file_.flush();
                task_file_.close();
            }
        }
        {
            std::lock_guard<std::mutex> lock(episode_mutex_);
            if (episode_file_.is_open()) {
                episode_file_.flush();
                episode_file_.close();
            }
        }
    }

    const std::string& getRunId() const { return run_id_; }

private:
    RunConfig config_;
    std::string run_id_;
    std::string output_dir_;
    std::string timestamp_;

    std::ofstream task_file_;
    std::mutex task_mutex_;

    std::ofstream episode_file_;
    std::mutex episode_mutex_;
};

} // namespace metrics

#endif // METRICS_LOGGER_H
