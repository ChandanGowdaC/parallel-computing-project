#include "BasicSystem.h"
#include <stdlib.h>
#include <boost/tokenizer.hpp>
#include <numeric>
#include <cmath>


BasicSystem::BasicSystem(const BasicGraph& G, MAPFSolver& solver): G(G), solver(solver), num_of_tasks(0) {}

BasicSystem::~BasicSystem() {}


// TODO: implement the random instance generator
/*bool BasicSystem::load_config(std::string fname)
{
    std::string line;
    std::ifstream myfile(fname.c_str());
    if (!myfile.is_open()) {
        std::cout << "Config file " << fname << " does not exist. " << std::endl;
        return false;
    }
    getline(myfile, line);
    boost::char_separator<char> sep(" ");
    boost::tokenizer<boost::char_separator<char> > tok(line, sep);
    boost::tokenizer<boost::char_separator<char> >::iterator beg = tok.begin();
    duration = atoi((*beg).c_str());
    getline(myfile, line);
    tok.assign(line, sep);
    fiducial = atoi((*beg).c_str());
    getline(myfile, line);
    tok.assign(line, sep);
    double length = atoi((*beg).c_str()) / fiducial;
    getline(myfile, line);
    tok.assign(line, sep);
    double width = atoi((*beg).c_str()) / fiducial;
    getline(myfile, line);
    tok.assign(line, sep);
    double v_max = atoi((*beg).c_str()) * duration / fiducial / 1000;
    getline(myfile, line);
    tok.assign(line, sep);
    double a_max = atoi((*beg).c_str()) * duration * duration / fiducial / 1000000;
    getline(myfile, line);
    tok.assign(line, sep);
    double rotate90 = atoi((*beg).c_str()) / duration;
    getline(myfile, line);
    tok.assign(line, sep);
    int rotate180 = atoi((*beg).c_str()) / duration;
    getline(myfile, line);
    tok.assign(line, sep);
    planning_window = atoi((*beg).c_str()) / duration;
    getline(myfile, line);
    tok.assign(line, sep);
    simulation_time = atoi((*beg).c_str()) / duration;

    myfile.close();
return true;

}
bool BasicSystem::generate_random_MAPF_instance()
{
    std::cout << "*** Generating instance " << seed << " ***" << std::endl;
    clock_t t = std::clock();
    // initialize_start_locations();
    // initialize_goal_locations();
    double runtime = (std::clock() - t) / CLOCKS_PER_SEC;
    std::cout << "Done! (" << runtime << " s)" << std::endl;
    // print_MAPF_instance();
    
    return true;
}


void BasicSystem::print_MAPF_instance() const
{
    std::cout << "*** instance " << seed << " ***" << std::endl;
    for (int k = 0; k < (int)starts.size(); k++)
    {
        cout << "Agent " << k << ": " << starts[k];
        for (int goal : goal_locations[k])
            cout << "->" << goal;
        cout << endl;
    }
}


void BasicSystem::save_MAPF_instance(std::string fname) const
{
    std::ofstream stats;
    stats.open(fname, std::ios::app);
    stats << starts.size();
    for (int k = 0; k < (int)starts.size(); k++)
    {
        stats << k << "," << starts[k].location;
        for (int goal : goal_locations[k])
            cout << "," << goal;
        cout << endl;
    }
    stats.close();
}

bool BasicSystem::read_MAPF_instance(std::string fname)
{
    std::string line;
    std::ifstream myfile(fname.c_str());
    if (!myfile.is_open()) {
        std::cout << "MAPF instance file " << fname << " does not exist. " << std::endl;
        return false;
    }

    std::cout << "*** Reading instance " << fname << " ***" << std::endl;

    getline(myfile, line);
    boost::char_separator<char> sep(",");
    boost::tokenizer<boost::char_separator<char> > tok(line, sep);
    boost::tokenizer<boost::char_separator<char> >::iterator beg = tok.begin();
    this->num_of_drives = atoi((*beg).c_str()); // read number of cols
    this->starts.resize(num_of_drives);
    this->goal_locations.resize(num_of_drives);

    for (int i = 0; i < num_of_drives; i++) {
        getline(myfile, line);
        boost::tokenizer<boost::char_separator<char> > tok(line, sep);
        beg = tok.begin();
        beg++; // skip id
        starts[i] = State(std::atoi(beg->c_str()));
        goal_locations[i].emplace_back(std::atoi(beg->c_str()));
    }

    myfile.close();
    return true;
}


bool BasicSystem::run()
{
	bool sol = pbs.run(starts, goal_locations, time_limit, vector<Path>(), PriorityGraph());
	pbs.save_results(outfile, std::to_string(num_of_drives) + "," + std::to_string(seed));
	pbs.best_node->priorities.save_as_digraph("goal_node.gv");
	return sol;
}
*/

bool BasicSystem::load_locations()
{
	string fname = G.map_name + "_rotation=" + std::to_string(consider_rotation) +
		"_" + std::to_string(num_of_drives) + ".agents";
    std::ifstream myfile (fname.c_str());
    if (!myfile.is_open())
		return false;

    string line;
    getline (myfile,line);
    boost::char_separator<char> sep(",");

    if (atoi(line.c_str()) != num_of_drives)
    {
        cout << "The agent file does not match the settings." << endl;
        exit(-1);
    }
    for (int k = 0; k < num_of_drives; k++)
    {
        getline (myfile, line);
        boost::tokenizer< boost::char_separator<char> > tok(line, sep);
        boost::tokenizer< boost::char_separator<char> >::iterator beg=tok.begin();
        // starts
        int start_loc = atoi((*beg).c_str());
        beg++;
        int start_orient = atoi((*beg).c_str());
        beg++;
        starts[k] = State(start_loc, 0, start_orient);
        paths[k].emplace_back(starts[k]);
        finished_tasks[k].push_back(std::make_pair(start_loc, 0));
        // goals
        int goal = atoi((*beg).c_str());
        goal_locations[k].emplace_back(goal, 0);
    }
    myfile.close();
	return true;
}


void BasicSystem::update_start_locations()
{
    for (int k = 0; k < num_of_drives; k++)
    {
        starts[k] = State(paths[k][timestep].location, 0, paths[k][timestep].orientation);
    }
}


void BasicSystem::update_paths(const std::vector<Path*>& MAPF_paths, int max_timestep = INT_MAX)
{
    for (int k = 0; k < num_of_drives; k++)
    {
        int length = min(max_timestep, (int) MAPF_paths[k]->size());
        paths[k].resize(timestep + length);
        for (int t = 0; t < length; t++)
        {
            if (MAPF_paths[k]->at(t).location < 0)
                paths[k][timestep + t] = State(-starts[k].location - 1, timestep + t, starts[k].orientation);
            else
            {
                paths[k][timestep + t] = MAPF_paths[k]->at(t);
                paths[k][timestep + t].timestep = timestep + t;
            }
        }
    }
}

void BasicSystem::update_paths(const std::vector<Path>& MAPF_paths, int max_timestep = INT_MAX)
{
    for (int k = 0; k < num_of_drives; k++)
    {
        int length = min(max_timestep, (int) MAPF_paths[k].size());
        paths[k].resize(timestep + length);
        for (int t = 0; t < length; t++)
        {
            paths[k][timestep + t] = MAPF_paths[k][t];
            paths[k][timestep + t].timestep = timestep + t;
        }
    }
}

void BasicSystem::update_initial_paths(vector<Path>& initial_paths) const
{
    initial_paths.clear();
    initial_paths.resize(num_of_drives);
    for (int k = 0; k < num_of_drives; k++)
    {
        // check whether the path traverse every goal locations
        int i = (int)goal_locations[k].size() - 1;
        int j = (int)paths[k].size() - 1;
        while (i >= 0 && j >= 0)
        {
            while (j >= 0 && paths[k][j].location != goal_locations[k][i].first &&
			paths[k][j].timestep >= goal_locations[k][i].second)
                j--;
            i--;
        }
        if (j < 0)
            continue;
          
        if ((int) paths[k].size() <= timestep + planning_window)
            continue;

        initial_paths[k].resize(paths[k].size() - timestep);
        for (int t = 0; t < (int)initial_paths[k].size(); t++)
        {
            initial_paths[k][t] = paths[k][timestep + t];
            initial_paths[k][t].timestep = t;
        }
    }
}

void BasicSystem::update_initial_constraints(list< tuple<int, int, int> >& initial_constraints) const
{
    initial_constraints.clear();
    for (int k = 0; k < num_of_drives; k++)
    {
        int prev_location = -1;
        for (int t = timestep; t > max(0, timestep - k_robust); t--)
        {
            int curr_location = paths[k][t].location;
            if (curr_location < 0)
                continue;
            else if (curr_location != prev_location)
            {
                initial_constraints.emplace_back(k, curr_location, t + k_robust + 1 - timestep);
                prev_location = curr_location;
            }
        }
    }
}


bool BasicSystem::check_collisions(const vector<Path>& input_paths) const
{
	for (int a1 = 0; a1 < (int)input_paths.size(); a1++)
	{
		for (int a2 = a1 + 1; a2 < (int)input_paths.size(); a2++)
		{
			// TODO: add k-robust
			size_t min_path_length = input_paths[a1].size() < input_paths[a2].size() ? input_paths[a1].size() : input_paths[a2].size();
			for (size_t timestep = 0; timestep < min_path_length; timestep++)
			{
				int loc1 = input_paths[a1].at(timestep).location;
				int loc2 = input_paths[a2].at(timestep).location;
				if (loc1 == loc2)
					return true;
				else if (timestep < min_path_length - 1
					&& loc1 == input_paths[a2].at(timestep + 1).location
					&& loc2 == input_paths[a1].at(timestep + 1).location)
					return true;
			}
			if ((hold_endpoints || useDummyPaths) && input_paths[a1].size() != input_paths[a2].size())
			{
				int a1_ = input_paths[a1].size() < input_paths[a2].size() ? a1 : a2;
				int a2_ = input_paths[a1].size() < input_paths[a2].size() ? a2 : a1;
				int loc1 = input_paths[a1_].back().location;
				for (size_t timestep = min_path_length; timestep < input_paths[a2_].size(); timestep++)
				{
					int loc2 = input_paths[a2_].at(timestep).location;
					if (loc1 == loc2)
						return true;
				}
			}
		}
	}
	return false;
}

bool BasicSystem::congested() const
{
	if (simulation_window <= 1)
		return false;
    int wait_agents = 0;
    int active_agents = 0;
    for (int k = 0; k < num_of_drives; ++k)
    {
        if (deadline_enabled && k < (int)agent_active_task.size() && agent_active_task[k] == -1)
            continue; // Idle agents without assigned tasks are not congested

        active_agents++;
        int t = 0;
        while (t < simulation_window && paths[k][timestep].location == paths[k][timestep + t].location &&
                paths[k][timestep].orientation == paths[k][timestep + t].orientation)
            t++;
        if (t == simulation_window)
            wait_agents++;
    }
    if (active_agents == 0)
        return false;
    return wait_agents > active_agents / 2;
}

// move all agents from start_timestep to end_timestep
// return a list of finished tasks
list<tuple<int, int, int>> BasicSystem::move()
{
    int start_timestep = timestep;
    int end_timestep = timestep + simulation_window;

	list<tuple<int, int, int>> finished_tasks; // <agent_id, location, timestep>

    for (int t = start_timestep; t <= end_timestep; t++)
    {
        for (int k = 0; k < num_of_drives; k++) {
            // Agents waits at its current locations if no future paths are assigned
            while ((int) paths[k].size() <= t)
            { // This should not happen?
                State final_state = paths[k].back();
                paths[k].emplace_back(final_state.location, final_state.timestep + 1, final_state.orientation);
            }
        }
    }


    for (int t = start_timestep; t <= end_timestep; t++)
    {
        for (int k = 0; k < num_of_drives; k++)
        {
            State curr = paths[k][t];

            /* int wait_times = 0; // wait time at the current location
            while (wait_times < t && paths[k][t - wait_times] != curr)
            {
                wait_times++;
            }*/

            // remove goals if necessary
            if ((!hold_endpoints || paths[k].size() == t + 1) && !goal_locations[k].empty() && 
				curr.location == goal_locations[k].front().first &&
				curr.timestep >= goal_locations[k].front().second) // the agent finish its current task
            {
                goal_locations[k].erase(goal_locations[k].begin());
                if (!deadline_enabled || (k < (int)agent_active_task.size() && agent_active_task[k] != -1))
                {
				    finished_tasks.emplace_back(k, curr.location, t);
                }
            }

            // check whether the move is valid
            if (t > 0)
            {
                State prev = paths[k][t - 1];

                if (curr.location == prev.location)
                {
                    if (G.get_rotate_degree(prev.orientation, curr.orientation) == 2)
                    {
                        cout << "Drive " << k << " rotates 180 degrees from " << prev << " to " << curr << endl;
                        save_results();
                        exit(-1);
                    }
                }
                else if (consider_rotation)
                {
                    if (prev.orientation != curr.orientation)
					{
						cout << "Drive " << k << " rotates while moving from " << prev << " to " << curr << endl;
						save_results();
						exit(-1);
					}
					else if ( !G.valid_move(prev.location, prev.orientation) ||
                        prev.location + G.move[prev.orientation] != curr.location)
                    {
                        cout << "Drive " << k << " jump from " << prev << " to " << curr << endl;
                        save_results();
                        exit(-1);
                    }
                }
				else
				{
					int dir = G.get_direction(prev.location, curr.location);
					if (dir < 0 || !G.valid_move(prev.location, dir))
					{
						cout << "Drive " << k << " jump from " << prev << " to " << curr << endl;
						save_results();
						exit(-1);
					}
				}
            }

            // Check whether this move has conflicts with other agents
			if (G.types[curr.location] != "Magic")
			{
				for (int j = k + 1; j < num_of_drives; j++)
				{
					for (int i = max(0, t - k_robust); i <= min(t + k_robust, end_timestep); i++)
					{
						if ((int)paths[j].size() <= i)
							break;
						if (paths[j][i].location == curr.location)
						{
							cout << "Drive " << k << " at " << curr << " has a conflict with drive " << j
								<< " at " << paths[j][i] << endl;
							save_results(); //TODO: write termination reason to files
							exit(-1);
						}
					}
				}
			}
        }
    }
    return finished_tasks;
}


void BasicSystem::add_partial_priorities(const vector<Path>& initial_paths, PriorityGraph& initial_priorities) const
{
    list<int> low_priorities;
    list<int> high_priorities;
    for (int k = 0; k < num_of_drives; k++)
    {
        if (initial_paths[k].empty())
            low_priorities.push_back(k);
        else
            high_priorities.push_back(k);
    }

    for (auto low : low_priorities)
    {
        for (auto high : high_priorities)
            initial_priorities.add(low, high);
    }
}

void BasicSystem::save_results()
{
	if (overall_runtime <= 0.0)
	{
		std::chrono::duration<double> elapsed = std::chrono::high_resolution_clock::now() - sim_start_time;
		overall_runtime = elapsed.count();
	}
	if (screen)
		std::cout << "*** Saving " << seed << " ***" << std::endl;
    clock_t t = std::clock();
    std::ofstream output;

    // settings
    output.open(outfile + "/config.txt", std::ios::out);
    output << "map: " << G.map_name << std::endl
        << "#drives: " << num_of_drives << std::endl
        << "seed: " << seed << std::endl
        << "solver: " << solver.get_name() << std::endl
        << "time_limit: " << time_limit << std::endl
        << "simulation_window: " << simulation_window << std::endl
        << "planning_window: " << planning_window << std::endl
        << "simulation_time: " << simulation_time << std::endl
        << "robust: " << k_robust << std::endl
        << "rotate: " << consider_rotation << std::endl
        << "use_dummy_paths: " << useDummyPaths << std::endl
        << "hold_endpoints: " << hold_endpoints << std::endl;

    output.close();

    // tasks
    output.open(outfile + "/tasks.txt", std::ios::out);
    output << num_of_drives << std::endl;
    for (int k = 0; k < num_of_drives; k++)
    {
        int prev = finished_tasks[k].front().first;
        for (auto task : finished_tasks[k])
        {
            output << task.first << "," << task.second << ",";
            if (task.second != 0) {
                auto it = G.heuristics.find(task.first);
                output << (it != G.heuristics.end() ? it->second[prev] : G.get_Manhattan_distance(task.first, prev));
            }
            output << ";";
            prev = task.first;
        }
        for (auto goal : goal_locations[k]) // tasks that have not been finished yet
        {
            output << goal.first << ",-1,;";
        }
        output << std::endl;
    }
    output.close();

    // paths
    output.open(outfile + "/paths.txt", std::ios::out);
    output << num_of_drives << std::endl;
    for (int k = 0; k < num_of_drives; k++)
    {
        for (auto p : paths[k])
        {
            if (p.timestep <= timestep)
                output << p << ";";
        }
        output << std::endl;
    }
    output.close();

    // Export metrics if specified (Person D)
    if (!csv_metrics_path.empty() || !json_metrics_path.empty())
    {
        RunMetrics metrics;
        auto now_c = std::chrono::system_clock::now();
        auto in_time_t = std::chrono::system_clock::to_time_t(now_c);
        std::stringstream ss;
        ss << std::put_time(std::localtime(&in_time_t), "%Y-%m-%d %H:%M:%S");
        metrics.timestamp = ss.str();
        metrics.scenario = scenario_name;
        metrics.map_name = G.map_name;
        metrics.solver_name = solver.get_name();
        metrics.num_agents = num_of_drives;
        metrics.num_threads = num_threads;
        metrics.parallel_enabled = parallel;
        metrics.vis_radius = vis_radius;
        metrics.simulation_window = simulation_window;
        metrics.planning_window = planning_window;
        metrics.simulation_time = simulation_time;
        metrics.cutoff_time = time_limit;
        metrics.seed = seed;
        metrics.wall_clock_runtime = overall_runtime;
        metrics.tasks_finished = num_of_tasks;
        metrics.throughput = (simulation_time > 0) ? ((double)num_of_tasks / simulation_time) : 0.0;

        if (deadline_enabled)
        {
            deadline_metrics.populate_run_metrics(metrics);
        }

        if (!csv_metrics_path.empty())
            metrics.append_to_csv(csv_metrics_path);
        if (!json_metrics_path.empty())
            metrics.save_to_json(json_metrics_path);
    }

    if (deadline_enabled)
    {
        std::string task_file = tasks_output_csv.empty() ? (outfile + "/deadline_tasks.csv") : tasks_output_csv;
        deadline_metrics.save_task_records(task_file, task_pool, simulation_time);
        std::string snap_file = snapshot_output_csv.empty() ? (outfile + "/deadline_snapshots.csv") : snapshot_output_csv;
        deadline_metrics.save_snapshot_series(snap_file);
    }

    saving_time = (std::clock() - t) / CLOCKS_PER_SEC;
    overall_runtime = std::chrono::duration<double>(std::chrono::high_resolution_clock::now() - sim_start_time).count();
    finish_metrics_logging();
	if (screen)
		std::cout << "Done! (" << saving_time << " s)" << std::endl;
}


void BasicSystem::init_metrics_logger()
{
    if (output_dir.empty())
        output_dir = outfile;
    if (output_dir.empty())
        output_dir = "results/raw";

    metrics::RunConfig config;
    config.map_name = G.map_name;
    auto slash_pos = config.map_name.rfind('/');
    if (slash_pos != std::string::npos)
        config.map_name = config.map_name.substr(slash_pos + 1);

    config.scenario = scenario_name.empty() ? "KIVA" : scenario_name;
    config.solver = solver.get_name();
    config.solver_mode = parallel ? "parallel" : "sequential";
    config.thread_count = parallel ? num_threads : 1;
    config.agent_count = num_of_drives;
    config.task_arrival_rate = deadline_enabled ? task_arrival_rate : 0.0;
    config.planning_horizon_h = simulation_window;
    config.planning_window_w = planning_window;
    config.visibility_radius_v = parallel ? vis_radius : 0.0;
    config.seed = seed;
    config.scheduling_policy = deadline_enabled ? scheduling_policy : "NONE";
    config.git_commit = git_commit;

    metrics_logger = std::make_unique<metrics::MetricsLogger>(output_dir, config, run_id);
}

void BasicSystem::finish_metrics_logging()
{
    if (!metrics_logger)
        return;

    metrics::RunMetrics r;
    r.simulation_timesteps = simulation_time;
    r.total_runtime_ms = overall_runtime * 1000.0;
    r.solver_runtime_ms = total_solver_time * 1000.0;
    r.num_replan_episodes = num_replan_episodes;
    r.num_tasks_generated = task_pool.size();
    r.num_tasks_completed = num_of_tasks;
    r.throughput = (simulation_time > 0) ? ((double)num_of_tasks / simulation_time) : 0.0;
    r.num_groups = (num_replan_episodes > 0) ? std::max(1, total_group_count_sum / num_replan_episodes) : 1;
    r.avg_group_size = (r.num_groups > 0) ? ((double)num_of_drives / r.num_groups) : num_of_drives;
    r.max_group_solve_ms = max_group_solve_time_overall * 1000.0;
    r.num_collisions = total_collisions;

    if (deadline_enabled)
    {
        r.deadline_satisfaction_rate = deadline_metrics.deadline_satisfaction_rate();
        r.avg_tardiness = deadline_metrics.avg_tardiness();
        r.max_tardiness = deadline_metrics.max_tardiness();
        r.num_tasks_overdue = deadline_metrics.tasks_overdue();

        for (const auto& t : task_pool)
        {
            metrics::TaskMetrics tm;
            tm.task_id = t.id;
            tm.release_time = t.release_time;
            tm.deadline = t.deadline;
            tm.pickup_x = t.pickup_loc % G.cols;
            tm.pickup_y = t.pickup_loc / G.cols;
            tm.delivery_x = t.delivery_loc % G.cols;
            tm.delivery_y = t.delivery_loc / G.cols;
            tm.assigned_agent = t.assigned_agent;
            tm.completion_time = t.finish_time;
            tm.tardiness = t.tardiness(simulation_time);
            tm.status = to_string(t.status);
            tm.scheduling_policy = scheduling_policy;
            metrics_logger->logTaskMetrics(tm);
        }
    }
    else
    {
        r.deadline_satisfaction_rate = 1.0;
        r.avg_tardiness = 0.0;
        r.max_tardiness = 0;
        r.num_tasks_overdue = 0;
    }

    metrics_logger->logRunMetrics(r);
    metrics_logger->finalize();
}

void BasicSystem::update_travel_times(unordered_map<int, double>& travel_times)
{
    if (travel_time_window <= 0)
        return;

    travel_times.clear();
    unordered_map<int, int> count;

    int t_min = max(0, timestep - travel_time_window);
    if (t_min >= timestep)
        return;
    for (auto path : paths)
    {
        int t = timestep;
        while (t >= t_min)
        {
            int loc = path[t].location;
            int dir = path[t].orientation;
            int wait = 0;
            while (t > wait && path[t - 1 - wait].location == loc && path[t - 1 - wait].orientation == dir)
                wait++;
            auto it = travel_times.find(loc);
            if (it == travel_times.end())
            {
                travel_times[loc] = wait;
                count[loc] = 1;
            }
            else
            {
                travel_times[loc] += wait;
                count[loc] += 1;
            }
            t = t - 1 - wait;
        }
    }

    for (auto it : count)
    {
        if (it.second > 1)
        {
            travel_times[it.first] /= it.second;
        }
    }
}


void BasicSystem::apply_planning_delay(int delta_t)
{
    if (delta_t <= 0)
        return;

    for (int k = 0; k < num_of_drives; ++k)
    {
        if (timestep >= (int)paths[k].size())
            continue;

        State current = paths[k][timestep];
        std::vector<State> future_states;
        for (int t = timestep + 1; t < (int)paths[k].size(); ++t)
        {
            future_states.push_back(paths[k][t]);
        }

        paths[k].resize(timestep + 1 + delta_t + future_states.size());
        for (int s = 1; s <= delta_t; ++s)
        {
            paths[k][timestep + s] = State(current.location, timestep + s, current.orientation);
        }
        for (size_t i = 0; i < future_states.size(); ++i)
        {
            paths[k][timestep + 1 + delta_t + i] = future_states[i];
            paths[k][timestep + 1 + delta_t + i].timestep = timestep + 1 + delta_t + i;
        }
    }
}

void BasicSystem::solve()
{
    auto t_start = std::chrono::steady_clock::now();

    if (parallel && solver_factory)
    {
        solve_gd_rhcr();
    }
    else
    {
        solve_sequential();
    }

    auto t_end = std::chrono::steady_clock::now();
    double t_plan = std::chrono::duration<double>(t_end - t_start).count();

    if (realtime_coupling && planning_tau > 0.0)
    {
        double budget = simulation_window * planning_tau;
        if (t_plan > budget)
        {
            int delta_t = static_cast<int>(std::ceil((t_plan - budget) / planning_tau));
            budget_violations++;
            total_budget_overrun_time += (t_plan - budget);
            std::cout << "[RealTime-Coupling] Budget overrun at timestep " << timestep
                      << ": plan took " << t_plan * 1000.0 << " ms (budget " << budget * 1000.0 
                      << " ms). Delaying execution by " << delta_t << " timesteps." << std::endl;
            apply_planning_delay(delta_t);
        }
    }
}

void BasicSystem::run_sequential_solve_core()
{
    LRA_called = false;
	LRAStar lra(G, solver.path_planner);
	lra.simulation_window = simulation_window;
	lra.k_robust = k_robust;
	solver.clear();
	if (solver.get_name() == "LRA")
	{
		// predict travel time
		unordered_map<int, double> travel_times;
		update_travel_times(solver.travel_times);

		bool sol = solver.run(starts, goal_locations, time_limit);
		update_paths(solver.solution);
	}
	else if (solver.get_name() == "WHCA")
	{
		update_initial_constraints(solver.initial_constraints);

		bool sol = solver.run(starts, goal_locations, time_limit);
		if (sol)
		{
			update_paths(solver.solution);
		}
		else
		{
			lra.resolve_conflicts(solver.solution);
			update_paths(lra.solution);
		}
	}
	 else // PBS or ECBS
	 {
		 //PriorityGraph initial_priorities;
		 update_initial_constraints(solver.initial_constraints);

		 // solve
		 if (hold_endpoints || useDummyPaths)
		 {
			 vector<State> new_starts;
			 vector< vector<pair<int, int> > > new_goal_locations;
			 for (int i : new_agents)
			 {
				 new_starts.emplace_back(starts[i]);
				 new_goal_locations.emplace_back(goal_locations[i]);
			 }
			 vector<Path> planned_paths(num_of_drives);
			 solver.initial_rt.clear();
			 auto p = new_agents.begin();
			 for (int i = 0; i < num_of_drives; i++)
			 {
                 planned_paths[i].resize(paths[i].size() - timestep);
                 for (int t = 0; t < (int)planned_paths[i].size(); t++)
                 {
                     planned_paths[i][t] = paths[i][timestep + t];
                     planned_paths[i][t].timestep = t;
                 }
				 if (p == new_agents.end() || *p != i)
				 {
					 solver.initial_rt.insertPath2CT(planned_paths[i]);
				 }
				 else
					 ++p;
			 }
			 if (!new_agents.empty())
			 {
				 bool sol;
                if (timestep == 0)
                    sol = solver.run(new_starts, new_goal_locations, 10 * time_limit);
                else
                    sol = solver.run(new_starts, new_goal_locations, time_limit);
                if (sol)
				 {
					 auto pt = solver.solution.begin();
					 for (int i : new_agents)
					 {
						 planned_paths[i] = *pt;
						 ++pt;
					 }
					 if (check_collisions(planned_paths))
					 {
						 cout << "COLLISIONS!" << endl;
						 exit(-1);
					 }
				 }
				 else
				 {
					 sol = solve_by_WHCA(planned_paths, new_starts, new_goal_locations);
                     assert(sol);
				 }
			 }
			 // lra.resolve_conflicts(planned_paths, k_robust);
			 update_paths(planned_paths);
		 }
		 else
		 {
			 bool sol = solver.run(starts, goal_locations, time_limit);
			 if (sol)
			 {
				 if (log)
					 solver.save_constraints_in_goal_node(outfile + "/goal_nodes/" + std::to_string(timestep) + ".gv");
				 update_paths(solver.solution);
			 }
			 else
			 {
				 lra.resolve_conflicts(solver.solution);
				 update_paths(lra.solution);
			 }
		 }
		 if (log)
			 solver.save_search_tree(outfile + "/search_trees/" + std::to_string(timestep) + ".gv");

	 }
	 solver.save_results(outfile + "/solver.csv", std::to_string(timestep) + "," 
										+ std::to_string(num_of_drives) + "," + std::to_string(seed));
}

void BasicSystem::solve_sequential()
{
    auto t_seq_start = std::chrono::steady_clock::now();
    run_sequential_solve_core();
    auto t_seq_end = std::chrono::steady_clock::now();
    double seq_solve_ms = std::chrono::duration<double, std::milli>(t_seq_end - t_seq_start).count();
    total_solver_time += seq_solve_ms / 1000.0;
    num_replan_episodes++;
    total_group_count_sum += 1;
    max_group_solve_time_overall = std::max(max_group_solve_time_overall, seq_solve_ms / 1000.0);

    if (metrics_logger) {
        metrics::EpisodeMetrics em;
        em.episode_id = episode_count++;
        em.timestep = timestep;
        em.num_groups = 1;
        em.group_sizes = std::to_string(num_of_drives);
        em.solve_time_ms = seq_solve_ms;
        em.max_group_solve_ms = seq_solve_ms;
        em.min_group_solve_ms = seq_solve_ms;
        em.mean_group_solve_ms = seq_solve_ms;
        em.t_partition_ms = 0.0;
        em.t_dispatch_ms = 0.0;
        em.t_barrier_wait_ms = 0.0;
        em.merge_time_ms = 0.0;
        em.t_serial_rest_ms = 0.0;
        em.inter_group_collisions = 0;
        metrics_logger->logEpisodeMetrics(em);
    }
}

void BasicSystem::solve_gd_rhcr()
{
    if (hold_endpoints || useDummyPaths || solver.get_name() == "LRA")
    {
        solve_sequential();
        return;
    }

    auto t_cycle_start = std::chrono::steady_clock::now();

    // 1. All agents to plan
    std::vector<int> agent_ids(num_of_drives);
    std::iota(agent_ids.begin(), agent_ids.end(), 0);

    // 2. Spatial partitioning into connected components
    auto t_part_start = std::chrono::steady_clock::now();
    auto groups = partition_agent_groups(G, starts, agent_ids, vis_radius);
    auto t_part_end = std::chrono::steady_clock::now();
    double t_part_ms = std::chrono::duration<double, std::milli>(t_part_end - t_part_start).count();

    // Check sequential fallback threshold if configured
    if (sequential_fallback_threshold > 0 && (int)groups.size() <= sequential_fallback_threshold) {
        std::cout << "[GD-RHCR] Group count (" << groups.size() << ") <= fallback threshold ("
                  << sequential_fallback_threshold << "). Running sequentially." << std::endl;
        solve_sequential();
        return;
    }

    // Log groups and dispatched solves per cycle
    std::cout << "[GD-RHCR] Cycle at timestep " << timestep << ": " 
              << groups.size() << " groups, " << groups.size() << " dispatched solves" << std::endl;

    // 3. Create group planning tasks
    auto t_tasks_start = std::chrono::steady_clock::now();
    GroupPlanningConfig gp_config;
    gp_config.simulation_window = simulation_window;
    gp_config.planning_window = planning_window;
    gp_config.time_limit = (timestep == 0) ? 10 * time_limit : time_limit;
    gp_config.k_robust = k_robust;

    auto tasks = make_group_planning_tasks(groups, starts, goal_locations, gp_config);

    // Sort tasks in descending order of size (LPT scheduling to minimize makespan / barrier wait)
    std::sort(tasks.begin(), tasks.end(), [](const GroupPlanningTask& a, const GroupPlanningTask& b) {
        if (a.agent_ids.size() != b.agent_ids.size()) {
            return a.agent_ids.size() > b.agent_ids.size();
        }
        return a.group_id < b.group_id; // deterministic tie-breaker
    });

    auto t_tasks_end = std::chrono::steady_clock::now();
    double t_make_tasks_ms = std::chrono::duration<double, std::milli>(t_tasks_end - t_tasks_start).count();

    // 4. Ensure persistent parallel executor exists
    if (!parallel_executor) {
        parallel_executor = std::make_unique<ParallelExecutor>(num_threads > 0 ? num_threads : 1);
    }

    // 5. Concurrent execution
    auto res_pair = parallel_executor->parallel_map_timed(tasks, [this](const GroupPlanningTask& task) {
        GroupPlanningResult res;
        res.group_id = task.group_id;
        auto t0 = std::chrono::steady_clock::now();

        thread_local std::pair<std::unique_ptr<MAPFSolver>, std::unique_ptr<SingleAgentSolver>> tl_solver;
        thread_local const BasicGraph* tl_graph = nullptr;
        if (!tl_solver.first || tl_graph != &this->G) {
            tl_solver = this->solver_factory->create();
            tl_graph = &this->G;
        }
        auto& mapf = *tl_solver.first;
        mapf.clear();
        mapf.initial_constraints.clear();
        mapf.window = task.planning_window;
        mapf.k_robust = task.k_robust;
        mapf.screen = 0;

        if (task.k_robust > 0) {
            for (size_t local_idx = 0; local_idx < task.agent_ids.size(); ++local_idx) {
                int global_id = task.agent_ids[local_idx];
                int prev_location = -1;
                for (int t = this->timestep; t > std::max(0, this->timestep - task.k_robust); t--) {
                    int curr_location = this->paths[global_id][t].location;
                    if (curr_location < 0) continue;
                    if (curr_location != prev_location) {
                        mapf.initial_constraints.emplace_back(static_cast<int>(local_idx), curr_location, t + task.k_robust + 1 - this->timestep);
                        prev_location = curr_location;
                    }
                }
            }
        }

        bool sol = mapf.run(task.starts, task.goals, task.time_limit);
        auto t1 = std::chrono::steady_clock::now();
        res.runtime = std::chrono::duration<double>(t1 - t0).count();
        res.success = sol;
        if (sol) {
            res.paths = mapf.solution;
        } else {
            res.error_message = "Solver failed or timed out for group " + std::to_string(task.group_id);
        }
        return res;
    });
    auto& results = res_pair.first;
    auto& pstats = res_pair.second;

    double t_dispatch_ms = t_make_tasks_ms + pstats.dispatch_time_ms;
    double t_solve_wall_ms = pstats.wall_time_ms;
    double t_barrier_wait_ms = pstats.barrier_wait_ms;

    // 6. Compute group statistics
    double min_group_ms = 1e9, max_group_ms = 0.0, sum_group_ms = 0.0;
    for (const auto& r : results) {
        double r_ms = r.runtime * 1000.0;
        if (r_ms < min_group_ms) min_group_ms = r_ms;
        if (r_ms > max_group_ms) max_group_ms = r_ms;
        sum_group_ms += r_ms;
    }
    double mean_group_ms = results.empty() ? 0.0 : (sum_group_ms / results.size());
    if (results.empty()) {
        min_group_ms = 0.0;
        max_group_ms = 0.0;
    }

    // 7. Merge and validate
    auto t_merge_start = std::chrono::steady_clock::now();
    std::vector<Path> candidate(num_of_drives);
    std::string merge_error;
    bool merge_success = merge_group_results(tasks, results, num_of_drives, candidate, &merge_error, planning_window);
    auto t_merge_end = std::chrono::steady_clock::now();
    double t_merge_ms = std::chrono::duration<double, std::milli>(t_merge_end - t_merge_start).count();

    // 8. Commit or sequential fallback
    int inter_group_collisions = 0;
    double t_fallback_ms = 0.0;
    if (!merge_success) {
        std::cout << "[GD-RHCR] Merge/Solve failed at timestep " << timestep 
                  << ": " << merge_error << ". Invoking sequential fallback." << std::endl;
        if (merge_error.find("cell") != std::string::npos || merge_error.find("edge") != std::string::npos) {
            inter_group_collisions = 1;
        }
        num_fallback_invocations++;
        // Fallback to sequential solve
        auto t_fb_start = std::chrono::steady_clock::now();
        run_sequential_solve_core();
        auto t_fb_end = std::chrono::steady_clock::now();
        t_fallback_ms = std::chrono::duration<double, std::milli>(t_fb_end - t_fb_start).count();
        total_solver_time += (t_solve_wall_ms + t_fallback_ms) / 1000.0;
        num_replan_episodes++;
    } else {
        update_paths(candidate);
        std::ofstream stats(outfile + "/solver.csv", std::ios::app);
        if (stats.is_open()) {
            stats << (t_solve_wall_ms / 1000.0) << ",0,0,0,0,0,0,0,0," 
                  << std::to_string(timestep) + "," + std::to_string(num_of_drives) + "," + std::to_string(seed)
                  << std::endl;
        }
        num_replan_episodes++;
        total_solver_time += t_solve_wall_ms / 1000.0;
    }

    total_group_count_sum += groups.size();
    total_dispatched_group_solves += tasks.size();
    max_group_solve_time_overall = std::max(max_group_solve_time_overall, max_group_ms / 1000.0);
    total_collisions += inter_group_collisions;

    std::string group_sizes_str;
    for (size_t i = 0; i < groups.size(); ++i) {
        if (i > 0) group_sizes_str += ",";
        group_sizes_str += std::to_string(groups[i].size());
    }

    auto t_cycle_end = std::chrono::steady_clock::now();
    double t_cycle_total_ms = std::chrono::duration<double, std::milli>(t_cycle_end - t_cycle_start).count();
    double t_serial_rest_ms = std::max(0.0, t_cycle_total_ms - (t_part_ms + t_dispatch_ms + t_solve_wall_ms + t_merge_ms));

    if (metrics_logger) {
        metrics::EpisodeMetrics em;
        em.episode_id = episode_count++;
        em.timestep = timestep;
        em.num_groups = static_cast<int>(groups.size());
        em.group_sizes = group_sizes_str;
        em.solve_time_ms = t_solve_wall_ms + t_fallback_ms;
        em.max_group_solve_ms = max_group_ms;
        em.min_group_solve_ms = min_group_ms;
        em.mean_group_solve_ms = mean_group_ms;
        em.t_partition_ms = t_part_ms;
        em.t_dispatch_ms = t_dispatch_ms;
        em.t_barrier_wait_ms = t_barrier_wait_ms;
        em.merge_time_ms = t_merge_ms;
        em.t_serial_rest_ms = t_serial_rest_ms;
        em.inter_group_collisions = inter_group_collisions;
        metrics_logger->logEpisodeMetrics(em);
    }
}

bool BasicSystem::solve_by_WHCA(vector<Path>& planned_paths,
	const vector<State>& new_starts, const vector< vector<pair<int, int> > >& new_goal_locations)
{
	WHCAStar whca(G, solver.path_planner);
    whca.k_robust = k_robust;
    whca.window = INT_MAX;
    whca.hold_endpoints = hold_endpoints || useDummyPaths;
    whca.screen = screen;
	whca.initial_rt.hold_endpoints = true;
	whca.initial_rt.map_size = G.size();
	whca.initial_rt.k_robust = k_robust;
	whca.initial_rt.window = INT_MAX;
	whca.initial_rt.copy(solver.initial_rt);
    whca.initial_solution.resize(new_starts.size());
    if (whca.hold_endpoints)
    {
        if (timestep == 0)
        {
            for (int i = 0; i < (int)new_starts.size(); i++)
                whca.initial_solution[i].emplace_back(starts[i]); // hold initial location
        }
        else
        {
            whca.initial_solution.clear();
            for (auto agent : new_agents)
                whca.initial_solution.emplace_back(planned_paths[agent]); // hold old paths
        }
    }
	bool sol = false;
    if (timestep == 0)
    {
        sol = whca.run(new_starts, new_goal_locations, 10 * time_limit);
    }
    else
    {

        sol = whca.run(new_starts, new_goal_locations, time_limit);
    }
	whca.save_results(outfile + "/solver.csv", std::to_string(timestep) + ","
		+ std::to_string(num_of_drives) + "," + std::to_string(seed));
    if (sol)
    {
        auto pt = whca.solution.begin();
        for (int i : new_agents)
        {
            planned_paths[i] = *pt;
            ++pt;
        }
    }
	whca.clear();
	return sol;
}

void BasicSystem::initialize_solvers()
{
	sim_start_time = std::chrono::high_resolution_clock::now();
	solver.k_robust = k_robust;
	solver.window = planning_window;
	solver.hold_endpoints = hold_endpoints || useDummyPaths;
	solver.screen = screen;

	solver.initial_rt.hold_endpoints = true;
	solver.initial_rt.map_size = G.size();
	solver.initial_rt.k_robust = k_robust;
	solver.initial_rt.window = INT_MAX;

	if (parallel)
	{
		parallel_executor = std::make_unique<ParallelExecutor>(num_threads > 0 ? num_threads : 1);
	}

	init_metrics_logger();
}

bool BasicSystem::load_records()
{
	if (!resume)
		return false;

	boost::char_separator<char> sep1(";");
	boost::char_separator<char> sep2(",");
	string line;

	// load paths
	std::ifstream myfile(outfile + "/paths.txt");

	if (!myfile.is_open())
			return false;

	timestep = INT_MAX;
	getline(myfile, line);
	if (atoi(line.c_str()) != num_of_drives)
	{
		cout << "The path file does not match the settings." << endl;
		exit(-1);
	}
	for (int k = 0; k < num_of_drives; k++)
	{
		getline(myfile, line);
		boost::tokenizer< boost::char_separator<char> > tok1(line, sep1);
		for (auto task : tok1)
		{
			boost::tokenizer< boost::char_separator<char> > tok2(task, sep2);
			boost::tokenizer< boost::char_separator<char> >::iterator beg = tok2.begin();
			int loc = atoi((*beg).c_str());
			beg++;
			int orientation = atoi((*beg).c_str());
			beg++;
			int time = atoi((*beg).c_str());
			paths[k].emplace_back(loc, time, orientation);
		}
		timestep = min(timestep, paths[k].back().timestep);
	}
	myfile.close();

	// pick the timestep
	timestep = int((timestep - 1) / simulation_window) * simulation_window; //int((timestep - 1) / simulation_window) * simulation_window;

	// load tasks
	myfile.open(outfile + "/tasks.txt");
	if (!myfile.is_open())
		return false;

	getline(myfile, line);
	if (atoi(line.c_str()) != num_of_drives)
	{
		cout << "The task file does not match the settings." << endl;
		exit(-1);
	}
	for (int k = 0; k < num_of_drives; k++)
	{
		getline(myfile, line);
		boost::tokenizer< boost::char_separator<char> > tok1(line, sep1);
		for (auto task : tok1)
		{
			boost::tokenizer< boost::char_separator<char> > tok2(task, sep2);
			boost::tokenizer< boost::char_separator<char> >::iterator beg = tok2.begin();
			int loc = atoi((*beg).c_str());
			beg++;
			int time = atoi((*beg).c_str());
			if (time >= 0 && time <= timestep)
			{
				finished_tasks[k].emplace_back(loc, time);
				timestep = max(timestep, time);
			}
			else
			{
				goal_locations[k].emplace_back(loc, 0);
			}
		}
	}
	myfile.close();
	return true;
}

