#include <iostream>
#include <cassert>
#include <memory>
#include "KivaGraph.h"
#include "KivaSystem.h"
#include "PBS.h"
#include "SIPP.h"
#include "SolverFactory.h"

int main() {
    std::cout << "[TEST] Running GD-RHCR group solve dispatch test..." << std::endl;

    KivaGrid G;
    bool loaded = G.load_map("maps/kiva.map");
    assert(loaded && "Failed to load maps/kiva.map");

    SIPP single_agent;
    PBS mapf(G, single_agent);
    KivaSystem system(G, mapf);

    // Configure system with parallel execution enabled
    system.num_of_drives = 20;
    system.parallel = true;
    system.num_threads = 2;
    system.vis_radius = 5;
    system.simulation_window = 5;
    system.planning_window = 10;
    system.time_limit = 10;
    system.seed = 42;
    system.outfile = "/tmp/test_gd_rhcr_dispatch";

    SolverFactoryConfig sf_config;
    sf_config.mapf_solver = "PBS";
    sf_config.single_agent_solver = "SIPP";
    sf_config.prioritize_start = true;
    system.solver_factory = std::make_unique<SolverFactory>(G, sf_config);

    G.preprocessing(system.consider_rotation);
    system.simulate(10); // Run 2 planning cycles (t=0, t=5)

    std::cout << "[TEST] Total dispatched group solves: " << system.total_dispatched_group_solves << std::endl;

    // Requirement: Test must fail if --parallel on dispatches zero group solves
    assert(system.total_dispatched_group_solves > 0 && "FATAL: --parallel was enabled but zero group solves were dispatched!");

    std::cout << "[TEST] GD-RHCR group dispatch assertion PASSED! ("
              << system.total_dispatched_group_solves << " solves dispatched)" << std::endl;
    return 0;
}
