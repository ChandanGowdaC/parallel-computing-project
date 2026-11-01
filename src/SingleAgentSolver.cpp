#include "SingleAgentSolver.h"


double SingleAgentSolver::compute_h_value(const BasicGraph& G, int curr, int goal_id,
                             const vector<pair<int, int> >& goal_location) const
{
    if (goal_location.empty() || goal_id >= (int)goal_location.size())
        return 0;

    double h = 0.0;
    auto it = G.heuristics.find(goal_location[goal_id].first);
    if (it != G.heuristics.end()) {
        h = it->second[curr];
    } else {
        h = G.get_Manhattan_distance(goal_location[goal_id].first, curr);
    }

    goal_id++;
    while (goal_id < (int) goal_location.size())
    {
        auto it2 = G.heuristics.find(goal_location[goal_id].first);
        if (it2 != G.heuristics.end()) {
            h += it2->second[goal_location[goal_id - 1].first];
        } else {
            h += G.get_Manhattan_distance(goal_location[goal_id].first, goal_location[goal_id - 1].first);
        }
        goal_id++;
    }
    return h;
}
