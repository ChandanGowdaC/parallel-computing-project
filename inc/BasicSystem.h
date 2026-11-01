#pragma once
#include <chrono>
#include "BasicGraph.h"
#include "States.h"
#include "PriorityGraph.h"
#include "PBS.h"
#include "WHCAStar.h"
#include "ECBS.h"
#include "LRAStar.h"
#include "ThreadPool.h"
#include "Task.h"
#include "Metrics.h"
#include "TaskGenerator.h"
#include "DeadlineScheduler.h"
#include "DeadlineMetrics.h"
#include "metrics_logger.h"
#include "SolverFactory.h"
#include "GDRHCR.h"
#include <memory>


class BasicSystem
{
public:
    // params for MAPF algotithms
	MAPFSolver& solver;
	bool hold_endpoints;
	bool useDummyPaths;
    int time_limit;
    int travel_time_window;
	//string potential_function;
	//double potential_threshold;
	//double suboptimal_bound;
    int screen;
	bool log;
    int num_of_drives;
    int seed;
    int simulation_window;
    int planning_window;
    int simulation_time;
    bool resume = false;

    // Infrastructure & Parallel execution (Person A / Person C)
    int num_threads = 1;
    bool parallel = false;
    int vis_radius = 5;

    // Task zoning configuration
    bool task_zoning = false;
    double cross_zone_prob = 0.05;
    double total_trip_length = 0.0;
    long long total_trips_sampled = 0;

    // Deadline-aware workload configuration (Person B)
    bool deadline_enabled = false;
    double task_arrival_rate = 1.0;
    double deadline_factor = 2.0;
    int deadline_slack_c = 0;
    std::string scheduling_policy = "EDF";
    std::string tasks_output_csv = "";
    std::string snapshot_output_csv = "";

    std::vector<Task> task_pool;
    std::vector<int> agent_active_task; // agent_id -> task_id (-1 if idle)
    DeadlineMetrics deadline_metrics;
    std::unique_ptr<TaskGenerator> task_generator;
    std::unique_ptr<DeadlineScheduler> task_scheduler;

    // Experiment logging (Person D)
    std::string scenario_name = "";
    std::string run_id = "";
    std::string git_commit = "";
    std::string output_dir = "";
    std::string csv_metrics_path = "";
    std::string json_metrics_path = "";
    bool realtime_coupling = false;
    double planning_tau = 0.05;
    double total_solver_time = 0.0;
    int num_replan_episodes = 0;
    int total_collisions = 0;
    int total_group_count_sum = 0;
    double max_group_solve_time_overall = 0.0;
    int total_dispatched_group_solves = 0;
    int num_fallback_invocations = 0;
    int total_local_merges = 0;
    double total_local_resolve_time_ms = 0.0;
    double total_global_fallback_time_ms = 0.0;
    int sequential_fallback_threshold = 0;
    int budget_violations = 0;
    double total_budget_overrun_time = 0.0;
    std::unique_ptr<metrics::MetricsLogger> metrics_logger;
    std::unique_ptr<SolverFactory> solver_factory;
    std::unique_ptr<ParallelExecutor> parallel_executor;
    int episode_count = 0;

    void init_metrics_logger();
    void finish_metrics_logging();
    void solve_gd_rhcr();
    void solve_sequential();
    void run_sequential_solve_core();
    void apply_planning_delay(int delta_t);

    // Track overall wall-clock runtime
    double overall_runtime = 0.0;
    std::chrono::high_resolution_clock::time_point sim_start_time;

    // params for drive model
    bool consider_rotation = false;
    int k_robust = 0;

    BasicSystem(const BasicGraph& G, MAPFSolver& solver);
    ~BasicSystem();

	// TODO
    /*bool load_config(std::string fname);
    bool generate_random_MAPF_instance();
    bool run();
	void print_MAPF_instance() const;
	void save_MAPF_instance(std::string fname) const;
	bool read_MAPF_instance(std::string fname);*/

    // I/O
    std::string outfile;
    void save_results();
	double saving_time = 0; // time for saving results to files, in seconds
    int num_of_tasks; // number of finished tasks

	list<int> new_agents; // used for replanning a subgroup of agents

    // used for MAPF instance
    vector<State> starts;
    vector< vector<pair<int, int> > > goal_locations;
	// unordered_set<int> held_endpoints;
    int timestep;

    // record movements of drives
    std::vector<Path> paths;
    std::vector<std::list<std::pair<int, int> > > finished_tasks; // location + finish time

    bool congested() const;
	bool check_collisions(const vector<Path>& input_paths) const;

    // update
    void update_start_locations();
    void update_travel_times(unordered_map<int, double>& travel_times);
    void update_paths(const std::vector<Path*>& MAPF_paths, int max_timestep);
    void update_paths(const std::vector<Path>& MAPF_paths, int max_timestep);
    void update_initial_paths(vector<Path>& initial_paths) const;
    void update_initial_constraints(list< tuple<int, int, int> >& initial_constraints) const;
    
	void add_partial_priorities(const vector<Path>& initial_paths, PriorityGraph& initial_priorities) const;
	list<tuple<int, int, int>> move(); // return finished tasks
	void solve();
	void initialize_solvers();
	bool load_records();
	bool load_locations();


protected:
	bool solve_by_WHCA(vector<Path>& planned_paths,
		const vector<State>& new_starts, const vector< vector<pair<int, int> > >& new_goal_locations);
    bool LRA_called = false;

private:
	const BasicGraph& G;
};

