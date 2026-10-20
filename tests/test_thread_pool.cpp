#include <iostream>
#include <vector>
#include <chrono>
#include <atomic>
#include <set>
#include <cassert>
#include "ThreadPool.h"

int main() {
    std::cout << "=== Running ThreadPool Verification Test ===" << std::endl;
    
    const size_t num_threads = 4;
    const size_t num_tasks = 16;
    ThreadPool pool(num_threads);
    
    std::vector<std::future<int>> results;
    std::atomic<int> counter{0};
    std::mutex set_mutex;
    std::set<std::thread::id> active_threads;

    for (size_t i = 0; i < num_tasks; ++i) {
        results.emplace_back(
            pool.enqueue([i, &counter, &set_mutex, &active_threads]() -> int {
                {
                    std::lock_guard<std::mutex> lock(set_mutex);
                    active_threads.insert(std::this_thread::get_id());
                }
                counter.fetch_add(1);
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
                return static_cast<int>(i * i);
            })
        );
    }

    int sum_squares = 0;
    for (size_t i = 0; i < results.size(); ++i) {
        int val = results[i].get();
        assert(val == static_cast<int>(i * i));
        sum_squares += val;
    }

    assert(counter.load() == static_cast<int>(num_tasks));
    std::cout << "Tasks executed: " << counter.load() << "/" << num_tasks << std::endl;
    std::cout << "Unique worker thread IDs observed: " << active_threads.size() << " (pool size: " << num_threads << ")" << std::endl;
    std::cout << "Computed sum of squares: " << sum_squares << std::endl;
    
    // Test exception propagation
    auto exc_future = pool.enqueue([]() -> int {
        throw std::runtime_error("expected test exception");
        return 0;
    });
    
    bool caught = false;
    try {
        exc_future.get();
    } catch (const std::runtime_error& e) {
        caught = true;
    }
    assert(caught);
    std::cout << "Exception propagation test: PASSED" << std::endl;

    std::cout << "ThreadPool Verification: ALL TESTS PASSED!" << std::endl;
    return 0;
}
