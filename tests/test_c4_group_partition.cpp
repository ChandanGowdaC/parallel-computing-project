#include <iostream>
#include <cassert>
#include <vector>
#include <cmath>
#include <algorithm>
#include "GDRHCR.h"

namespace {

int l1_dist(int x1, int x2) {
    return std::abs(x1 - x2);
}

void test_radius_boundary() {
    std::cout << "  Testing radius boundary conditions..." << std::endl;
    const int V = 5;
    // Agent 0 at 0, Agent 1 at 5 (dist = 5 == V -> connected)
    // Agent 2 at 11 (dist from 1 is 6 > V -> disconnected)
    std::vector<State> starts = {State(0, 0), State(5, 0), State(11, 0)};
    std::vector<int> ids = {0, 1, 2};

    auto groups = partition_agent_groups(starts, ids, V, l1_dist);
    assert(groups.size() == 2);
    assert((groups[0] == std::vector<int>{0, 1}));
    assert((groups[1] == std::vector<int>{2}));

    // If V is reduced to 4, Agent 0 and 1 should now disconnect
    auto groups_v4 = partition_agent_groups(starts, ids, 4, l1_dist);
    assert(groups_v4.size() == 3);
    assert((groups_v4[0] == std::vector<int>{0}));
    assert((groups_v4[1] == std::vector<int>{1}));
    assert((groups_v4[2] == std::vector<int>{2}));
}

void test_dynamic_merge_mid_run() {
    std::cout << "  Testing dynamic group merging mid-run..." << std::endl;
    const int V = 4;

    // Cycle 0: Agents far apart (distance = 8 > V -> 2 groups)
    std::vector<State> starts_c0 = {State(0, 0), State(8, 0)};
    auto g_c0 = partition_agent_groups(starts_c0, {0, 1}, V, l1_dist);
    assert(g_c0.size() == 2);
    assert((g_c0[0] == std::vector<int>{0}));
    assert((g_c0[1] == std::vector<int>{1}));

    // Cycle 1: Agents move towards each other: 0 -> 2, 1 -> 5 (distance = 3 <= V -> merged into 1 group)
    std::vector<State> starts_c1 = {State(2, 0), State(5, 0)};
    auto g_c1 = partition_agent_groups(starts_c1, {0, 1}, V, l1_dist);
    assert(g_c1.size() == 1);
    assert((g_c1[0] == std::vector<int>{0, 1}));
}

void test_dynamic_split_mid_run() {
    std::cout << "  Testing dynamic group splitting mid-run..." << std::endl;
    const int V = 4;

    // Cycle 0: Agents close together (distance = 2 <= V -> 1 group)
    std::vector<State> starts_c0 = {State(4, 0), State(6, 0)};
    auto g_c0 = partition_agent_groups(starts_c0, {0, 1}, V, l1_dist);
    assert(g_c0.size() == 1);
    assert((g_c0[0] == std::vector<int>{0, 1}));

    // Cycle 1: Agents move apart: 0 -> 1, 1 -> 9 (distance = 8 > V -> split into 2 groups)
    std::vector<State> starts_c1 = {State(1, 0), State(9, 0)};
    auto g_c1 = partition_agent_groups(starts_c1, {0, 1}, V, l1_dist);
    assert(g_c1.size() == 2);
    assert((g_c1[0] == std::vector<int>{0}));
    assert((g_c1[1] == std::vector<int>{1}));
}

void test_transitive_connectivity_and_partition() {
    std::cout << "  Testing transitive chain connectivity..." << std::endl;
    const int V = 3;
    // Chain: 0 -- 3 -- 6 -- 9 (all pairwise step 3 <= V -> 1 single group {0, 1, 2, 3})
    std::vector<State> starts = {State(0, 0), State(3, 0), State(6, 0), State(9, 0)};
    auto groups = partition_agent_groups(starts, {0, 1, 2, 3}, V, l1_dist);
    assert(groups.size() == 1);
    assert((groups[0] == std::vector<int>{0, 1, 2, 3}));

    // Break the link: Agent 2 moves from 6 to 15:
    // 0 -- 3 (dist 3 <= V) and 9 (dist from 3 is 6 > V, from 15 is 6 > V) and 15
    starts[2] = State(15, 0);
    auto broken = partition_agent_groups(starts, {0, 1, 2, 3}, V, l1_dist);
    assert(broken.size() == 3);
    assert((broken[0] == std::vector<int>{0, 1})); // 0 and 3
    assert((broken[1] == std::vector<int>{2}));    // 15
    assert((broken[2] == std::vector<int>{3}));    // 9
}

void test_zero_radius_isolation() {
    std::cout << "  Testing V=0 isolation (every agent is its own group)..." << std::endl;
    std::vector<State> starts = {State(0, 0), State(1, 0), State(2, 0), State(3, 0)};
    auto groups = partition_agent_groups(starts, {0, 1, 2, 3}, 0, l1_dist);
    assert(groups.size() == 4);
    for (int i = 0; i < 4; ++i) {
        assert(groups[i].size() == 1);
        assert(groups[i][0] == i);
    }
}

} // namespace

int main() {
    std::cout << "[TEST C4] Running comprehensive group partition tests..." << std::endl;
    test_radius_boundary();
    test_dynamic_merge_mid_run();
    test_dynamic_split_mid_run();
    test_transitive_connectivity_and_partition();
    test_zero_radius_isolation();
    std::cout << "[TEST C4] All group partition tests PASSED!" << std::endl;
    return 0;
}
