#pragma once
#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <sstream>
#include "Task.h"

// Standardized experiment metrics schema (Person D contract)
// Written to by Person A (runner), Person B (deadline/task metrics), and Person C (parallel solver)
struct RunMetrics {
    std::string timestamp = "";
    std::string scenario = "";
    std::string map_name = "";
    std::string solver_name = "";
    int num_agents = 0;
    int num_threads = 1;
    bool parallel_enabled = false;
    int vis_radius = 0;
    int simulation_window = 0;     // h
    int planning_window = 0;       // w
    int simulation_time = 0;
    int cutoff_time = 0;
    int seed = 0;
    double wall_clock_runtime = 0.0;
    int tasks_finished = 0;
    double throughput = 0.0;       // tasks_finished / simulation_time
    
    // Deadline-aware metrics (Person B)
    int tasks_total = 0;
    int tasks_on_time = 0;
    int tasks_overdue = 0;
    double deadline_satisfaction_rate = 0.0; // on_time / total
    double avg_tardiness = 0.0;
    int max_tardiness = 0;

    // Output CSV header
    static std::string get_csv_header() {
        return "timestamp,scenario,map,solver,agents,threads,parallel,vis_radius,sim_window,plan_window,sim_time,cutoff,seed,wall_runtime_sec,tasks_finished,throughput,tasks_total,tasks_on_time,tasks_overdue,deadline_satisfaction_rate,avg_tardiness,max_tardiness";
    }

    // Output CSV row
    std::string to_csv_row() const {
        std::ostringstream ss;
        ss << timestamp << ","
           << scenario << ","
           << map_name << ","
           << solver_name << ","
           << num_agents << ","
           << num_threads << ","
           << (parallel_enabled ? "true" : "false") << ","
           << vis_radius << ","
           << simulation_window << ","
           << planning_window << ","
           << simulation_time << ","
           << cutoff_time << ","
           << seed << ","
           << std::fixed << std::setprecision(4) << wall_clock_runtime << ","
           << tasks_finished << ","
           << std::fixed << std::setprecision(4) << throughput << ","
           << tasks_total << ","
           << tasks_on_time << ","
           << tasks_overdue << ","
           << std::fixed << std::setprecision(4) << deadline_satisfaction_rate << ","
           << std::fixed << std::setprecision(4) << avg_tardiness << ","
           << max_tardiness;
        return ss.str();
    }

    // Save summary row to CSV (creates header if file does not exist)
    void append_to_csv(const std::string& filepath) const {
        bool exists = false;
        {
            std::ifstream test(filepath);
            exists = test.good();
        }
        std::ofstream out(filepath, std::ios::app);
        if (!exists) {
            out << get_csv_header() << "\n";
        }
        out << to_csv_row() << "\n";
        out.close();
    }

    // Save summary to JSON
    void save_to_json(const std::string& filepath) const {
        std::ofstream out(filepath);
        out << "{\n"
            << "  \"timestamp\": \"" << timestamp << "\",\n"
            << "  \"scenario\": \"" << scenario << "\",\n"
            << "  \"map\": \"" << map_name << "\",\n"
            << "  \"solver\": \"" << solver_name << "\",\n"
            << "  \"num_agents\": " << num_agents << ",\n"
            << "  \"num_threads\": " << num_threads << ",\n"
            << "  \"parallel_enabled\": " << (parallel_enabled ? "true" : "false") << ",\n"
            << "  \"vis_radius\": " << vis_radius << ",\n"
            << "  \"simulation_window\": " << simulation_window << ",\n"
            << "  \"planning_window\": " << planning_window << ",\n"
            << "  \"simulation_time\": " << simulation_time << ",\n"
            << "  \"cutoff_time\": " << cutoff_time << ",\n"
            << "  \"seed\": " << seed << ",\n"
            << "  \"wall_clock_runtime\": " << wall_clock_runtime << ",\n"
            << "  \"tasks_finished\": " << tasks_finished << ",\n"
            << "  \"throughput\": " << throughput << ",\n"
            << "  \"tasks_total\": " << tasks_total << ",\n"
            << "  \"tasks_on_time\": " << tasks_on_time << ",\n"
            << "  \"tasks_overdue\": " << tasks_overdue << ",\n"
            << "  \"deadline_satisfaction_rate\": " << deadline_satisfaction_rate << ",\n"
            << "  \"avg_tardiness\": " << avg_tardiness << ",\n"
            << "  \"max_tardiness\": " << max_tardiness << "\n"
            << "}\n";
        out.close();
    }
};

// Helper for exporting individual task completion records
inline void save_tasks_csv(const std::string& filepath, const std::vector<Task>& tasks, int current_time) {
    std::ofstream out(filepath);
    out << "task_id,pickup_loc,delivery_loc,release_time,deadline,finish_time,tardiness,status\n";
    for (const auto& t : tasks) {
        out << t.id << ","
            << t.pickup_loc << ","
            << t.delivery_loc << ","
            << t.release_time << ","
            << t.deadline << ","
            << t.finish_time << ","
            << t.tardiness(current_time) << ","
            << to_string(t.status) << "\n";
    }
    out.close();
}
