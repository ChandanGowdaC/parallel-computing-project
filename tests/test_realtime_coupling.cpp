#include <iostream>
#include <cassert>
#include <memory>
#include "KivaGraph.h"
#include "KivaSystem.h"
#include "PBS.h"
#include "SIPP.h"
#include "SolverFactory.h"

int main() {
    std::cout << "[TEST] Running Real-Time Planning Budget Coupling test..." << std::endl;

    KivaGrid G;
    bool loaded = G.load_map("maps/kiva.map");
    assert(loaded && "Failed to load maps/kiva.map");

    // --- Run 1: Generous budget (tau = 1.0s, B = 5.0s) -> Zero overruns ---
    int completed_normal = 0;
    int budget_violations_normal = 0;
    {
        SIPP single_agent;
        PBS mapf(G, single_agent);
        KivaSystem system(G, mapf);

        system.num_of_drives = 20;
        system.simulation_window = 5;
        system.planning_window = 10;
        system.time_limit = 10;
        system.seed = 42;
        system.outfile = "/tmp/test_rt_normal";

        system.deadline_enabled = true;
        system.task_arrival_rate = 1.0;
        system.deadline_factor = 2.0;
        system.scheduling_policy = "EDF";

        system.realtime_coupling = true;
        system.planning_tau = 1.0; // 1 second per tick (5 seconds per window)

        SolverFactoryConfig sf_config;
        sf_config.mapf_solver = "PBS";
        sf_config.single_agent_solver = "SIPP";
        sf_config.prioritize_start = true;
        system.solver_factory = std::make_unique<SolverFactory>(G, sf_config);

        G.preprocessing(system.consider_rotation);
        system.simulate(35);

        completed_normal = system.num_of_tasks;
        budget_violations_normal = system.budget_violations;
        std::cout << "[TEST] Normal run completed tasks: " << completed_normal
                  << ", budget violations: " << budget_violations_normal << std::endl;
        assert(budget_violations_normal == 0 && "Normal run with generous budget should have zero budget violations!");
        assert(completed_normal > 0 && "Normal run should have completed tasks!");
    }

    // --- Run 2: Severely restricted budget (tau = 1e-6 s) -> Severe overruns and stalled execution ---
    int completed_slowed = 0;
    int budget_violations_slowed = 0;
    {
        SIPP single_agent;
        PBS mapf(G, single_agent);
        KivaSystem system(G, mapf);

        system.num_of_drives = 20;
        system.simulation_window = 5;
        system.planning_window = 10;
        system.time_limit = 10;
        system.seed = 42;
        system.outfile = "/tmp/test_rt_slowed";

        system.deadline_enabled = true;
        system.task_arrival_rate = 1.0;
        system.deadline_factor = 2.0;
        system.scheduling_policy = "EDF";

        system.realtime_coupling = true;
        system.planning_tau = 0.000001; // 1 microsecond per tick -> guaranteed overrun

        SolverFactoryConfig sf_config;
        sf_config.mapf_solver = "PBS";
        sf_config.single_agent_solver = "SIPP";
        sf_config.prioritize_start = true;
        system.solver_factory = std::make_unique<SolverFactory>(G, sf_config);

        G.preprocessing(system.consider_rotation);
        system.simulate(35);

        completed_slowed = system.num_of_tasks;
        budget_violations_slowed = system.budget_violations;
        std::cout << "[TEST] Slowed run completed tasks: " << completed_slowed
                  << ", budget violations: " << budget_violations_slowed << std::endl;
        assert(budget_violations_slowed > 0 && "Slowed run must trigger budget violations!");
        assert(completed_slowed < completed_normal && "Slowed planner must complete fewer tasks / miss more deadlines than normal planner!");
    }

    std::cout << "[TEST] Real-Time Planning Budget Coupling test PASSED!" << std::endl;
    return 0;
}
