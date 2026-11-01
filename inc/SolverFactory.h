#pragma once
#include "BasicGraph.h"
#include "MAPFSolver.h"
#include "SingleAgentSolver.h"
#include "PBS.h"
#include "ECBS.h"
#include "WHCAStar.h"
#include "LRAStar.h"
#include "SIPP.h"
#include "StateTimeAStar.h"
#include <memory>
#include <string>
#include <utility>
#include <stdexcept>

struct SolverFactoryConfig {
    std::string single_agent_solver = "SIPP";
    std::string mapf_solver = "PBS";
    bool lazyPriority = false;
    bool prioritize_start = true;
    bool CAT = false;
    int k_robust = 0;
    double suboptimal_bound = 1.0;
    std::string potential_function = "NONE";
    double potential_threshold = 0.0;
    bool hold_endpoints = false;
    bool dummy_paths = false;
};

// Thread-safe SolverFactory that creates isolated SingleAgentSolver and MAPFSolver instances
// for each parallel group planning task over the immutable BasicGraph.
class SolverFactory {
public:
    SolverFactory(const BasicGraph& G, const SolverFactoryConfig& config)
        : G_(G), config_(config) {}

    std::pair<std::unique_ptr<MAPFSolver>, std::unique_ptr<SingleAgentSolver>> create() const {
        std::unique_ptr<SingleAgentSolver> single_agent;
        if (config_.single_agent_solver == "ASTAR") {
            single_agent = std::make_unique<StateTimeAStar>();
        } else {
            single_agent = std::make_unique<SIPP>();
        }

        std::unique_ptr<MAPFSolver> mapf;
        if (config_.mapf_solver == "ECBS") {
            auto ecbs = std::make_unique<ECBS>(G_, *single_agent);
            ecbs->potential_function = config_.potential_function;
            ecbs->potential_threshold = config_.potential_threshold;
            ecbs->suboptimal_bound = config_.suboptimal_bound;
            mapf = std::move(ecbs);
        } else if (config_.mapf_solver == "PBS") {
            auto pbs = std::make_unique<PBS>(G_, *single_agent);
            pbs->lazyPriority = config_.lazyPriority;
            bool prioritize = config_.prioritize_start;
            if (config_.hold_endpoints || config_.dummy_paths)
                prioritize = false;
            pbs->prioritize_start = prioritize;
            pbs->setRT(config_.CAT, prioritize);
            mapf = std::move(pbs);
        } else if (config_.mapf_solver == "WHCA") {
            mapf = std::make_unique<WHCAStar>(G_, *single_agent);
        } else if (config_.mapf_solver == "LRA") {
            mapf = std::make_unique<LRAStar>(G_, *single_agent);
        } else {
            throw std::invalid_argument("Unknown solver: " + config_.mapf_solver);
        }

        mapf->k_robust = config_.k_robust;
        mapf->hold_endpoints = config_.hold_endpoints || config_.dummy_paths;
        return {std::move(mapf), std::move(single_agent)};
    }

    const SolverFactoryConfig& get_config() const { return config_; }

private:
    const BasicGraph& G_;
    SolverFactoryConfig config_;
};
