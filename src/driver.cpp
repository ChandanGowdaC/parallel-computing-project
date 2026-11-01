#include "KivaSystem.h"
#include "SortingSystem.h"
#include "OnlineSystem.h"
#include "BeeSystem.h"
#include "ID.h"
#include <boost/program_options.hpp>
#include <boost/filesystem.hpp>


void set_parameters(BasicSystem& system, const BasicGraph& G, const boost::program_options::variables_map& vm)
{
	if (vm.count("output_dir"))
		system.outfile = vm["output_dir"].as<std::string>();
	else if (vm.count("output"))
		system.outfile = vm["output"].as<std::string>();
	system.output_dir = system.outfile;

	system.screen = vm["screen"].as<int>();
	system.log = vm["log"].as<bool>();

	if (vm.count("agents"))
		system.num_of_drives = vm["agents"].as<int>();
	else if (vm.count("agentNum"))
		system.num_of_drives = vm["agentNum"].as<int>();

	system.time_limit = vm["cutoffTime"].as<int>();

	if (vm.count("planning_horizon"))
		system.simulation_window = vm["planning_horizon"].as<int>();
	else if (vm.count("simulation_window"))
		system.simulation_window = vm["simulation_window"].as<int>();

	system.planning_window = vm["planning_window"].as<int>();
	system.travel_time_window = vm["travel_time_window"].as<int>();

	if (vm.count("simulation_timesteps"))
		system.simulation_time = vm["simulation_timesteps"].as<int>();
	else if (vm.count("simulation_time"))
		system.simulation_time = vm["simulation_time"].as<int>();

	system.consider_rotation = vm["rotation"].as<bool>();
	system.k_robust = vm["robust"].as<int>();
	system.hold_endpoints = vm["hold_endpoints"].as<bool>();
	system.useDummyPaths = vm["dummy_paths"].as<bool>();
	if (vm.count("seed"))
		system.seed = vm["seed"].as<int>();
	else
		system.seed = (int)time(0);
	srand(system.seed);

	if (vm.count("scenario"))
		system.scenario_name = vm["scenario"].as<std::string>();
	if (vm.count("resume"))
		system.resume = vm["resume"].as<bool>();
	if (vm.count("threads"))
		system.num_threads = vm["threads"].as<int>();
	if (vm.count("parallel"))
		system.parallel = vm["parallel"].as<bool>();
	if (vm.count("sequential_fallback_threshold"))
		system.sequential_fallback_threshold = vm["sequential_fallback_threshold"].as<int>();

	if (vm.count("visibility_radius"))
		system.vis_radius = vm["visibility_radius"].as<int>();
	else if (vm.count("vis_radius"))
		system.vis_radius = vm["vis_radius"].as<int>();

	if (vm.count("deadline"))
		system.deadline_enabled = vm["deadline"].as<bool>();
	if (vm.count("task_arrival_rate"))
		system.task_arrival_rate = vm["task_arrival_rate"].as<double>();
	if (vm.count("deadline_factor"))
		system.deadline_factor = vm["deadline_factor"].as<double>();
	if (vm.count("deadline_slack_c"))
		system.deadline_slack_c = vm["deadline_slack_c"].as<int>();

	if (vm.count("scheduling_policy"))
		system.scheduling_policy = vm["scheduling_policy"].as<std::string>();
	else if (vm.count("policy"))
		system.scheduling_policy = vm["policy"].as<std::string>();

	if (vm.count("run_id"))
		system.run_id = vm["run_id"].as<std::string>();
	if (vm.count("git_commit"))
		system.git_commit = vm["git_commit"].as<std::string>();
	if (vm.count("realtime_coupling"))
		system.realtime_coupling = vm["realtime_coupling"].as<bool>();
	if (vm.count("planning_tau"))
		system.planning_tau = vm["planning_tau"].as<double>();
	if (vm.count("task_zoning"))
		system.task_zoning = vm["task_zoning"].as<bool>();
	if (vm.count("cross_zone_prob"))
		system.cross_zone_prob = vm["cross_zone_prob"].as<double>();

	if (vm.count("tasks_csv"))
		system.tasks_output_csv = vm["tasks_csv"].as<std::string>();
	if (vm.count("snapshot_csv"))
		system.snapshot_output_csv = vm["snapshot_csv"].as<std::string>();
	if (vm.count("csv_metrics"))
		system.csv_metrics_path = vm["csv_metrics"].as<std::string>();
	if (vm.count("json_metrics"))
		system.json_metrics_path = vm["json_metrics"].as<std::string>();

	SolverFactoryConfig sf_config;
	sf_config.mapf_solver = vm["solver"].as<string>();
	sf_config.single_agent_solver = vm["single_agent_solver"].as<string>();
	sf_config.k_robust = vm["robust"].as<int>();
	sf_config.hold_endpoints = vm["hold_endpoints"].as<bool>();
	sf_config.dummy_paths = vm["dummy_paths"].as<bool>();
	if (sf_config.mapf_solver == "PBS")
	{
		sf_config.lazyPriority = vm["lazyP"].as<bool>();
		bool prioritize = vm["prioritize_start"].as<bool>();
		if (sf_config.hold_endpoints || sf_config.dummy_paths)
			prioritize = false;
		sf_config.prioritize_start = prioritize;
		sf_config.CAT = vm["CAT"].as<bool>();
	}
	else if (sf_config.mapf_solver == "ECBS")
	{
		sf_config.potential_function = vm["potential_function"].as<string>();
		sf_config.potential_threshold = vm["potential_threshold"].as<double>();
		sf_config.suboptimal_bound = vm["suboptimal_bound"].as<double>();
	}
	system.solver_factory = std::make_unique<SolverFactory>(G, sf_config);
}


void print_simulation_summary(const BasicSystem& system)
{
	if (system.screen > 0)
	{
		std::cout << "=== Simulation Summary ===" << std::endl;
		std::cout << "Overall runtime: " << system.overall_runtime << " seconds." << std::endl;
		std::cout << "Tasks completed: " << system.num_of_tasks << std::endl;
		if (system.simulation_time > 0)
			std::cout << "Throughput: " << (double)system.num_of_tasks / system.simulation_time << " tasks/timestep" << std::endl;
	}
}


MAPFSolver* set_solver(const BasicGraph& G, const boost::program_options::variables_map& vm)
{
	string solver_name = vm["single_agent_solver"].as<string>();
	SingleAgentSolver* path_planner;
	MAPFSolver* mapf_solver;
	if (solver_name == "ASTAR")
	{
		path_planner = new StateTimeAStar();
	}
	else if (solver_name == "SIPP")
	{
		path_planner = new SIPP();
	}
	else
	{
		cout << "Single-agent solver " << solver_name << "does not exist!" << endl;
		exit(-1);
	}

	solver_name = vm["solver"].as<string>();
	if (solver_name == "ECBS")
	{
		ECBS* ecbs = new ECBS(G, *path_planner);
		ecbs->potential_function = vm["potential_function"].as<string>();
		ecbs->potential_threshold = vm["potential_threshold"].as<double>();
		ecbs->suboptimal_bound = vm["suboptimal_bound"].as<double>();
		mapf_solver = ecbs;
	}
	else if (solver_name == "PBS")
	{
		PBS* pbs = new PBS(G, *path_planner);
		pbs->lazyPriority = vm["lazyP"].as<bool>();
        auto prioritize_start = vm["prioritize_start"].as<bool>();
        if (vm["hold_endpoints"].as<bool>() or vm["dummy_paths"].as<bool>())
            prioritize_start = false;
        pbs->prioritize_start = prioritize_start;
        pbs->setRT(vm["CAT"].as<bool>(), prioritize_start);
		mapf_solver = pbs;
	}
	else if (solver_name == "WHCA")
	{
		mapf_solver = new WHCAStar(G, *path_planner);
	}
	else if (solver_name == "LRA")
	{
		mapf_solver = new LRAStar(G, *path_planner);
	}
	else
	{
		cout << "Solver " << solver_name << "does not exist!" << endl;
		exit(-1);
	}

	if (vm["id"].as<bool>())
	{
		return new ID(G, *path_planner, *mapf_solver);
	}
	else
	{
		return mapf_solver;
	}
}


int main(int argc, char** argv) 
{
	namespace po = boost::program_options;
	// Declare the supported options.
	po::options_description desc("Allowed options");
	desc.add_options()
		("help", "produce help message")
		("scenario", po::value<std::string>()->required(), "scenario (SORTING, KIVA, ONLINE, BEE)")
		("map,m", po::value<std::string>()->required(), "input map file")
		("task", po::value<std::string>()->default_value(""), "input task file")
		("output,o", po::value<std::string>()->default_value("exp/test"), "output folder name")
		("output_dir", po::value<std::string>(), "output folder name (alias for output)")
		("agentNum,k", po::value<int>(), "number of drives")
		("agents", po::value<int>(), "number of drives (alias for agentNum)")
		("cutoffTime,t", po::value<int>()->default_value(60), "cutoff time (seconds)")
		("seed,d", po::value<int>(), "random seed")
		("screen,s", po::value<int>()->default_value(1), "screen option (0: none; 1: results; 2:all)")
		("solver", po::value<string>()->default_value("PBS"), "solver (LRA, PBS, WHCA, ECBS)")
		("id", po::value<bool>()->default_value(false), "independence detection")
		("single_agent_solver", po::value<string>()->default_value("SIPP"), "single-agent solver (ASTAR, SIPP)")
		("lazyP", po::value<bool>()->default_value(false), "use lazy priority")
		("simulation_time", po::value<int>()->default_value(5000), "run simulation")
		("simulation_timesteps", po::value<int>(), "run simulation (alias for simulation_time)")
		("simulation_window", po::value<int>()->default_value(5), "call the planner every simulation_window timesteps")
		("planning_horizon", po::value<int>(), "call the planner every planning_horizon timesteps (alias for simulation_window)")
		("travel_time_window", po::value<int>()->default_value(0), "consider the traffic jams within the given window")
		("planning_window", po::value<int>()->default_value(INT_MAX / 2),
		        "the planner outputs plans with first planning_window timesteps collision-free")
		("potential_function", po::value<string>()->default_value("NONE"), "potential function (NONE, SOC, IC)")
		("potential_threshold", po::value<double>()->default_value(0), "potential threshold")
		("rotation", po::value<bool>()->default_value(false), "consider rotation")
		("robust", po::value<int>()->default_value(0), "k-robust (for now, only work for PBS)")
		("CAT", po::value<bool>()->default_value(false), "use conflict-avoidance table")
		("hold_endpoints", po::value<bool>()->default_value(false),
		        "Hold endpoints from Ma et al, AAMAS 2017")
		("dummy_paths", po::value<bool>()->default_value(false),
				"Find dummy paths from Liu et al, AAMAS 2019")
		("prioritize_start", po::value<bool>()->default_value(true), "Prioritize waiting at start locations")
		("suboptimal_bound", po::value<double>()->default_value(1), "Suboptimal bound for ECBS")
		("log", po::value<bool>()->default_value(false), "save the search trees (and the priority trees)")
		("resume", po::value<bool>()->default_value(false), "resume simulation from existing paths.txt in output folder")
		("threads,j", po::value<int>()->default_value(1), "number of worker threads for parallel execution")
		("parallel", po::value<bool>()->default_value(false)->implicit_value(true), "enable parallel planning (GD-RHCR). When false, runs sequential baseline")
		("sequential_fallback_threshold", po::value<int>()->default_value(0), "group count threshold below which sequential solver is used to avoid parallel overhead")
		("vis_radius,V", po::value<int>()->default_value(5), "visibility/spatial partitioning radius for GD-RHCR")
		("visibility_radius", po::value<int>(), "visibility/spatial partitioning radius (alias for vis_radius)")
		("deadline", po::value<bool>()->default_value(false)->implicit_value(true), "enable deadline-aware task generation (Person B)")
		("task_arrival_rate", po::value<double>()->default_value(1.0), "Poisson task arrival rate lambda")
		("deadline_factor", po::value<double>()->default_value(2.0), "deadline tightness multiplier")
		("deadline_slack_c", po::value<int>()->default_value(0), "additive slack constant c in deadline = release + k*dist + c")
		("policy", po::value<std::string>()->default_value("EDF"), "scheduling policy (FIFO, EDF, DEADLINE_AWARE)")
		("scheduling_policy", po::value<std::string>(), "scheduling policy (alias for policy)")
		("run_id", po::value<std::string>()->default_value(""), "unique experiment run id (Person D)")
		("git_commit", po::value<std::string>()->default_value(""), "git commit hash for provenance tracking")
		("realtime_coupling", po::value<bool>()->default_value(false)->implicit_value(true), "enable real-time planning-budget coupling")
		("planning_tau", po::value<double>()->default_value(0.05), "wall-clock seconds per simulated timestep for budget coupling")
		("task_zoning", po::value<bool>()->default_value(false)->implicit_value(true), "enable zoned task generation")
		("cross_zone_prob", po::value<double>()->default_value(0.05), "probability of cross-zone destination selection")
		("tasks_csv", po::value<std::string>()->default_value(""), "path to output per-task records CSV")
		("snapshot_csv", po::value<std::string>()->default_value(""), "path to output deadline snapshots CSV")
		("csv_metrics", po::value<std::string>()->default_value(""), "path to output summary CSV (Person D)")
		("json_metrics", po::value<std::string>()->default_value(""), "path to output summary JSON (Person D)")
		;
	clock_t start_time = clock();
	po::variables_map vm;
	po::store(po::parse_command_line(argc, argv, desc), vm);

	if (vm.count("help")) {
		std::cout << desc << std::endl;
		return 1;
	}

	po::notify(vm);

	if (!vm.count("agentNum") && !vm.count("agents"))
	{
		std::cerr << "Option agentNum/agents is required" << std::endl;
		return -1;
	}

    // check params
    if (vm["hold_endpoints"].as<bool>() or vm["dummy_paths"].as<bool>())
    {
        if (vm["hold_endpoints"].as<bool>() and vm["dummy_paths"].as<bool>())
        {
            std::cerr << "Hold endpoints and dummy paths cannot be used simultaneously" << endl;
            exit(-1);
        }
        if (vm["simulation_window"].as<int>() != 1)
        {
            std::cerr << "Hold endpoints and dummy paths can only work when the simulation window is 1" << endl;
            exit(-1);
        }
        if (vm["planning_window"].as<int>() < INT_MAX / 2)
        {
            std::cerr << "Hold endpoints and dummy paths cannot work with planning windows" << endl;
            exit(-1);
        }
    }

    // make dictionary
	boost::filesystem::path dir(vm["output"].as<std::string>() +"/");
	boost::filesystem::create_directories(dir);
	if (vm["log"].as<bool>())
	{
		boost::filesystem::path dir1(vm["output"].as<std::string>() + "/goal_nodes/");
		boost::filesystem::path dir2(vm["output"].as<std::string>() + "/search_trees/");
		boost::filesystem::create_directories(dir1);
		boost::filesystem::create_directories(dir2);
	}


	if (vm["scenario"].as<string>() == "KIVA")
	{
		KivaGrid G;
		if (!G.load_map(vm["map"].as<std::string>()))
			return -1;
		MAPFSolver* solver = set_solver(G, vm);
		KivaSystem system(G, *solver);
		set_parameters(system, G, vm);
		G.preprocessing(system.consider_rotation);
		system.simulate(system.simulation_time);
		print_simulation_summary(system);
		return 0;
	}
	else if (vm["scenario"].as<string>() == "SORTING")
	{
		 SortingGrid G;
		 if (!G.load_map(vm["map"].as<std::string>()))
			 return -1;
		 MAPFSolver* solver = set_solver(G, vm);
		 SortingSystem system(G, *solver);
		 assert(!system.hold_endpoints);
		 assert(!system.useDummyPaths);
		 set_parameters(system, G, vm);
		 G.preprocessing(system.consider_rotation);
		 system.simulate(system.simulation_time);
		 print_simulation_summary(system);
		 return 0;
	}
	else if (vm["scenario"].as<string>() == "ONLINE")
	{
		OnlineGrid G;
		if (!G.load_map(vm["map"].as<std::string>()))
			return -1;
		MAPFSolver* solver = set_solver(G, vm);
		OnlineSystem system(G, *solver);
		assert(!system.hold_endpoints);
		assert(!system.useDummyPaths);
		set_parameters(system, G, vm);
		G.preprocessing(system.consider_rotation);
		system.simulate(system.simulation_time);
		print_simulation_summary(system);
		return 0;
	}
	else if (vm["scenario"].as<string>() == "BEE")
	{
		BeeGraph G;
		if (!G.load_map(vm["map"].as<std::string>()))
			return -1;
		MAPFSolver* solver = set_solver(G, vm);
		BeeSystem system(G, *solver);
		assert(!system.hold_endpoints);
		assert(!system.useDummyPaths);
		set_parameters(system, G, vm);
		G.preprocessing(vm["task"].as<std::string>(), system.consider_rotation);
		system.load_task_assignments(vm["task"].as<std::string>());
		system.simulate();
		double runtime = (double)(clock() - start_time)/ CLOCKS_PER_SEC;
		cout << "Overall runtime:			" << runtime << " seconds." << endl;
		// cout << "	Reading from file:		" << G.loading_time + system.loading_time << " seconds." << endl;
		// cout << "	Preprocessing:			" << G.preprocessing_time << " seconds." << endl;
		// cout << "	Writing to file:		" << system.saving_time << " seconds." << endl;
		cout << "Makespan:		" << system.get_makespan() << " timesteps." << endl;
		cout << "Flowtime:		" << system.get_flowtime() << " timesteps." << endl;
		cout << "Flowtime lowerbound:	" << system.get_flowtime_lowerbound() << " timesteps." << endl;
		auto flower_ids = system.get_missed_flower_ids();
		cout << "Missed tasks:";
		for (auto id : flower_ids)
			cout << " " << id;
		cout << endl;
		// cout << "Remaining tasks: " << system.get_num_of_remaining_tasks() << endl;
		cout << "Objective: " << system.get_objective() << endl;
		std::ofstream output;
		output.open(vm["output"].as<std::string>() + "/MAPF_results.txt", std::ios::out);
		output << "Overall runtime: " << runtime << " seconds." << endl;;
		output << "Makespan: " << system.get_makespan() << " timesteps." << endl;
		output << "Flowtime: " << system.get_flowtime() << " timesteps." << endl;
		output << "Flowtime lowerbound: " << system.get_flowtime_lowerbound() << " timesteps." << endl;
		output << "Missed tasks:";
		for (auto id : flower_ids)
			output << " " << id;
		output << endl;
		output << "Objective: " << system.get_objective() << endl;
		output.close();
        return 0;
	}
	else
	{
		cout << "Scenario " << vm["scenario"].as<string>() << "does not exist!" << endl;
		return -1;
	}
}
