#include "KivaSystem.h"
#include "WHCAStar.h"
#include "ECBS.h"
#include "LRAStar.h"
#include "PBS.h"

KivaSystem::KivaSystem(const KivaGrid& G, MAPFSolver& solver): BasicSystem(G, solver), G(G) {}


KivaSystem::~KivaSystem()
{
}

void KivaSystem::initialize()
{
	initialize_solvers();

	starts.resize(num_of_drives);
	goal_locations.resize(num_of_drives);
	paths.resize(num_of_drives);
	finished_tasks.resize(num_of_drives);
	if (deadline_enabled)
	{
		task_generator = std::make_unique<TaskGenerator>(G.endpoints, seed, task_arrival_rate, deadline_factor);
		if (task_zoning) {
			int th = (G.rows >= 33 && (G.rows % 33 == 0)) ? 33 : G.rows;
			int tw = (G.cols >= 46 && (G.cols % 46 == 0)) ? 46 : G.cols;
			task_generator->set_zoning(true, cross_zone_prob, th, tw, G.cols, G.rows);
		}
		task_scheduler = std::make_unique<DeadlineScheduler>(parse_scheduling_policy(scheduling_policy));
		agent_active_task.assign(num_of_drives, -1);
	}
	bool succ = load_records(); // continue simulating from the records
	if (!succ)
	{
		timestep = 0;
		succ = load_locations();
		if (!succ)
		{
			cout << "Randomly generating initial locations" << endl;
			initialize_start_locations();
			init_zones();
			initialize_goal_locations();
		}
		else
		{
			init_zones();
		}
	}
	else
	{
		init_zones();
	}
}

void KivaSystem::init_zones()
{
	tile_h = (G.rows >= 33 && (G.rows % 33 == 0)) ? 33 : G.rows;
	tile_w = (G.cols >= 46 && (G.cols % 46 == 0)) ? 46 : G.cols;
	num_zones_c = std::max(1, G.cols / tile_w);
	int num_zones_r = std::max(1, G.rows / tile_h);
	total_zones = std::max(1, num_zones_r * num_zones_c);

	zone_endpoints.assign(total_zones, std::vector<int>());
	other_zone_endpoints.assign(total_zones, std::vector<int>());

	for (int ep : G.endpoints) {
		int zid = get_location_zone(ep);
		if (zid >= 0 && zid < total_zones) {
			zone_endpoints[zid].push_back(ep);
		}
	}

	for (int z = 0; z < total_zones; ++z) {
		for (int ep : G.endpoints) {
			int zid = get_location_zone(ep);
			if (zid != z) {
				other_zone_endpoints[z].push_back(ep);
			}
		}
	}

	agent_home_zone.assign(num_of_drives, 0);
	for (int k = 0; k < num_of_drives; ++k) {
		int loc = starts[k].location;
		agent_home_zone[k] = get_location_zone(loc);
	}
}

int KivaSystem::get_location_zone(int loc) const
{
	if (loc < 0 || loc >= G.size() || G.cols <= 0 || tile_h <= 0 || tile_w <= 0) return 0;
	int r = loc / G.cols;
	int c = loc % G.cols;
	int zr = r / tile_h;
	int zc = c / tile_w;
	int zid = zr * num_zones_c + zc;
	if (zid < 0 || zid >= total_zones) return 0;
	return zid;
}

int KivaSystem::sample_zoned_endpoint(int agent_id, int current_loc)
{
	if (!task_zoning || total_zones <= 1) {
		int next = G.endpoints[rand() % (int)G.endpoints.size()];
		while (next == current_loc && G.endpoints.size() > 1) {
			next = G.endpoints[rand() % (int)G.endpoints.size()];
		}
		return next;
	}

	int hz = (agent_id >= 0 && agent_id < (int)agent_home_zone.size()) ? agent_home_zone[agent_id] : 0;
	double p = static_cast<double>(rand()) / static_cast<double>(RAND_MAX);
	bool use_home = (p >= cross_zone_prob);

	if (use_home && !zone_endpoints[hz].empty()) {
		int next = zone_endpoints[hz][rand() % zone_endpoints[hz].size()];
		int tries = 0;
		while (next == current_loc && zone_endpoints[hz].size() > 1 && tries < 50) {
			next = zone_endpoints[hz][rand() % zone_endpoints[hz].size()];
			tries++;
		}
		return next;
	} else if (!other_zone_endpoints[hz].empty()) {
		int next = other_zone_endpoints[hz][rand() % other_zone_endpoints[hz].size()];
		int tries = 0;
		while (next == current_loc && other_zone_endpoints[hz].size() > 1 && tries < 50) {
			next = other_zone_endpoints[hz][rand() % other_zone_endpoints[hz].size()];
			tries++;
		}
		return next;
	}

	int next = G.endpoints[rand() % (int)G.endpoints.size()];
	while (next == current_loc && G.endpoints.size() > 1) {
		next = G.endpoints[rand() % (int)G.endpoints.size()];
	}
	return next;
}

void KivaSystem::initialize_start_locations()
{
	// Choose random start locations
	// Any non-obstacle locations can be start locations
	// Start locations should be unique
	std::vector<bool> used(G.size(), false);
	for (int k = 0; k < num_of_drives; k++)
	{
		int orientation = -1;
		if (consider_rotation)
		{
			orientation = rand() % 4;
		}
		int loc = -1;
		if (k < (int)G.agent_home_locations.size())
		{
			loc = G.agent_home_locations[k];
		}
		else
		{
			do {
				loc = rand() % G.size();
			} while (used[loc] || G.types[loc] == "Obstacle");
		}
		used[loc] = true;
		starts[k] = State(loc, 0, orientation);
		paths[k].emplace_back(starts[k]);
		finished_tasks[k].emplace_back(loc, 0);
	}
}


void KivaSystem::initialize_goal_locations()
{
	if (hold_endpoints || useDummyPaths)
		return;
	if (deadline_enabled)
		return; // Handled dynamically by TaskGenerator & DeadlineScheduler in update_goal_locations()
	// Choose random goal locations
	// Goal locations are not necessarily unique
	for (int k = 0; k < num_of_drives; k++)
	{
		int goal = sample_zoned_endpoint(k, starts[k].location);
		goal_locations[k].emplace_back(goal, 0);
		total_trip_length += G.get_Manhattan_distance(starts[k].location, goal);
		total_trips_sampled++;
	}
}



void KivaSystem::update_goal_locations()
{
    if (!LRA_called)
        new_agents.clear();
	if (hold_endpoints)
	{
		unordered_map<int, int> held_locations; // <location, agent id>
		for (int k = 0; k < num_of_drives; k++)
		{
			int curr = paths[k][timestep].location; // current location
			if (goal_locations[k].empty())
			{
				int next = sample_zoned_endpoint(k, curr);
				while (next == curr || held_endpoints.find(next) != held_endpoints.end())
				{
					next = sample_zoned_endpoint(k, curr);
				}
				goal_locations[k].emplace_back(next, 0);
				held_endpoints.insert(next);
				total_trip_length += G.get_Manhattan_distance(curr, next);
				total_trips_sampled++;
			}
			if (paths[k].back().location == goal_locations[k].back().first &&  // agent already has paths to its goal location
				paths[k].back().timestep >= goal_locations[k].back().second) // after its release time
			{
				int agent = k;
				int loc = goal_locations[k].back().first;
				auto it = held_locations.find(loc);
				while (it != held_locations.end()) // its start location has been held by another agent
				{
					int removed_agent = it->second;
					if (goal_locations[removed_agent].back().first != loc)
						cout << "BUG" << endl;
					new_agents.remove(removed_agent); // another agent cannot move to its new goal location
					cout << "Agent " << removed_agent << " has to wait for agent " << agent << " because of location " << loc << endl;
					held_locations[loc] = agent; // this agent has to keep holding this location
					agent = removed_agent;
					loc = paths[agent][timestep].location; // another agent's start location
					it = held_locations.find(loc);
				}
				held_locations[loc] = agent;
			}
			else // agent does not have paths to its goal location yet
			{
				if (held_locations.find(goal_locations[k].back().first) == held_locations.end()) // if the goal location has not been held by other agents
				{
					held_locations[goal_locations[k].back().first] = k; // hold this goal location
					new_agents.emplace_back(k); // replan paths for this agent later
					continue;
				}
				// the goal location has already been held by other agents 
				// so this agent has to keep holding its start location instead
				int agent = k;
				int loc = curr;
				cout << "Agent " << agent << " has to wait for agent " << held_locations[goal_locations[k].back().first] << " because of location " <<
					goal_locations[k].back().first << endl;
				auto it = held_locations.find(loc);
				while (it != held_locations.end()) // its start location has been held by another agent
				{
					int removed_agent = it->second;
					if (goal_locations[removed_agent].back().first != loc)
						cout << "BUG" << endl;
					new_agents.remove(removed_agent); // another agent cannot move to its new goal location
					cout << "Agent " << removed_agent << " has to wait for agent " << agent << " because of location " << loc << endl;
					held_locations[loc] = agent; // this agent has to keep holding its start location
					agent = removed_agent;
					loc = paths[agent][timestep].location; // another agent's start location
					it = held_locations.find(loc);
				}
				held_locations[loc] = agent;// this agent has to keep holding its start location
			}
		}
	}
	else
	{
		if (deadline_enabled && task_generator && task_scheduler)
		{
			// 1. Generate new Poisson arrivals for current timestep
			auto arrivals = task_generator->generate_arrivals(timestep, G.cols, G.rows);
			for (const auto& t : arrivals)
			{
				task_pool.push_back(t);
				deadline_metrics.on_task_generated(t);
			}

			// 2. Identify idle agents needing assignment
			std::vector<int> idle_agents;
			std::vector<int> agent_locations(num_of_drives);
			for (int k = 0; k < num_of_drives; ++k)
			{
				agent_locations[k] = paths[k][timestep].location;
				if (agent_active_task[k] == -1 && goal_locations[k].empty())
				{
					idle_agents.push_back(k);
				}
			}

			// 3. Assign tasks using configured policy (FIFO, EDF, DEADLINE_AWARE)
			if (!idle_agents.empty())
			{
				auto assignments = task_scheduler->assign_tasks(
					task_pool, idle_agents, agent_locations, timestep, G.cols);

				for (const auto& pair : assignments)
				{
					int agent_id = pair.first;
					int task_id = pair.second;
					agent_active_task[agent_id] = task_id;
					const auto& t = task_pool[task_id];
					int curr = paths[agent_id][timestep].location;
					if (curr != t.pickup_loc)
					{
						goal_locations[agent_id].emplace_back(t.pickup_loc, 0);
					}
					goal_locations[agent_id].emplace_back(t.delivery_loc, 0);
				}
			}

			// Ensure every agent has at least one goal (stay in place for planning window if idle)
			for (int k = 0; k < num_of_drives; ++k)
			{
				if (goal_locations[k].empty())
				{
					goal_locations[k].emplace_back(paths[k][timestep].location, planning_window);
				}
			}

			// 4. Update status of unassigned/active tasks and record snapshot
			task_scheduler->update_task_statuses(task_pool, timestep);
			deadline_metrics.snapshot(timestep);
		}
		else
		{
			for (int k = 0; k < num_of_drives; k++)
			{
				int curr = paths[k][timestep].location; // current location
				if (useDummyPaths)
				{
					if (goal_locations[k].empty())
					{
						goal_locations[k].emplace_back(G.agent_home_locations[k], 0);
					}
					if (goal_locations[k].size() == 1)
					{
						int next;
						do {
							next = G.endpoints[rand() % (int)G.endpoints.size()];
						} while (next == curr);
						goal_locations[k].emplace(goal_locations[k].begin(), next, 0);
						new_agents.emplace_back(k);
					}
				}
				else
				{
					pair<int, int> goal; // The last goal location
					if (goal_locations[k].empty())
					{
						goal = make_pair(curr, 0);
					}
					else
					{
						goal = goal_locations[k].back();
					}
					double min_timesteps = G.get_Manhattan_distance(goal.first, curr); // G.heuristics.at(goal)[curr];
					while (min_timesteps <= simulation_window)
						// The agent might finish its tasks during the next planning horizon
					{
						// assign a new task
						pair<int, int> next;
						if (G.types[goal.first] == "Endpoint" || G.types[goal.first] == "Home" || G.types[goal.first] == "Travel")
						{
							next = make_pair(sample_zoned_endpoint(k, goal.first), 0);
						}
						else
						{
							std::cout << "ERROR in update_goal_function()" << std::endl;
							std::cout << "The fiducial type should not be " << G.types[curr] << std::endl;
							exit(-1);
						}
						goal_locations[k].emplace_back(next);
						int trip_dist = G.get_Manhattan_distance(next.first, goal.first);
						total_trip_length += trip_dist;
						total_trips_sampled++;
						min_timesteps += trip_dist;
						goal = next;
					}
				}
			}
		}
	}

}


void KivaSystem::simulate(int simulation_time)
{
	std::cout << "*** Simulating " << seed << " ***" << std::endl;
	this->simulation_time = simulation_time;
	initialize();

	for (; timestep < simulation_time; timestep += simulation_window)
	{
		std::cout << "Timestep " << timestep << std::endl;

		update_start_locations();
		update_goal_locations();
		solve();

		// move drives
		auto new_finished_tasks = move();
		std::cout << new_finished_tasks.size() << " tasks has been finished" << std::endl;

		// update tasks
		for (auto task : new_finished_tasks)
		{
			int id, loc, t;
			std::tie(id, loc, t) = task;
			finished_tasks[id].emplace_back(loc, t);
			if (hold_endpoints)
				held_endpoints.erase(loc);

			if (deadline_enabled && id >= 0 && id < (int)agent_active_task.size())
			{
				int tid = agent_active_task[id];
				if (tid >= 0 && tid < (int)task_pool.size())
				{
					if (loc == task_pool[tid].delivery_loc)
					{
						task_pool[tid].finish_time = t;
						task_pool[tid].status = TaskStatus::COMPLETED;
						deadline_metrics.on_task_completed(task_pool[tid], t);
						agent_active_task[id] = -1; // marked idle for next replan
						num_of_tasks++;
					}
				}
			}
			else if (!deadline_enabled)
			{
				num_of_tasks++;
			}
		}

		if (congested())
		{
			cout << "***** Too many traffic jams ***" << endl;
			break;
		}
	}

	update_start_locations();
	double mean_trip_len = total_trips_sampled > 0 ? (total_trip_length / total_trips_sampled) : 0.0;
	std::cout << "[TripMetrics] Total trips sampled: " << total_trips_sampled
	          << ", Mean trip length: " << mean_trip_len << std::endl;
	std::cout << std::endl << "Done!" << std::endl;
	save_results();
}

