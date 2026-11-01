#pragma once
#include "BasicSystem.h"
#include "KivaGraph.h"

class KivaSystem :
	public BasicSystem
{
public:
	KivaSystem(const KivaGrid& G, MAPFSolver& solver);
	~KivaSystem();

	void simulate(int simulation_time);


private:
	const KivaGrid& G;
	unordered_set<int> held_endpoints;

	std::vector<int> agent_home_zone;
	std::vector<std::vector<int>> zone_endpoints;
	std::vector<std::vector<int>> other_zone_endpoints;
	int tile_h = 33;
	int tile_w = 46;
	int num_zones_c = 1;
	int total_zones = 1;

	void init_zones();
	int get_location_zone(int loc) const;
	int sample_zoned_endpoint(int agent_id, int current_loc);

	void initialize();
	void initialize_start_locations();
	void initialize_goal_locations();
	void update_goal_locations();
};

