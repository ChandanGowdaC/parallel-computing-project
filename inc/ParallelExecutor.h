#pragma once
#include <vector>
#include <future>
#include <functional>
#include <memory>
#include <algorithm>
#include <stdexcept>
#include <chrono>
#include "ThreadPool.h"

// ParallelExecutor: A reusable parallel primitive utility designed for GD-RHCR.
// Provides parallel_for, parallel_map, and task batch dispatch.
// Falls back to deterministic sequential execution when num_threads <= 1.
class ParallelExecutor {
public:
    explicit ParallelExecutor(size_t num_threads = 1)
        : thread_count(num_threads > 0 ? num_threads : 1) {
        if (thread_count > 1) {
            pool = std::make_unique<ThreadPool>(thread_count);
        }
    }

    ~ParallelExecutor() = default;

    // Delete copy, allow move
    ParallelExecutor(const ParallelExecutor&) = delete;
    ParallelExecutor& operator=(const ParallelExecutor&) = delete;
    ParallelExecutor(ParallelExecutor&&) = default;
    ParallelExecutor& operator=(ParallelExecutor&&) = default;

    size_t get_num_threads() const {
        return thread_count;
    }

    bool is_parallel() const {
        return thread_count > 1 && pool != nullptr;
    }

    // Enqueue an individual function and receive a std::future
    template<class F, class... Args>
    auto enqueue(F&& f, Args&&... args) 
#if __cplusplus >= 201703L
        -> std::future<typename std::invoke_result<F, Args...>::type>
#else
        -> std::future<typename std::result_of<F(Args...)>::type>
#endif
    {
        if (!pool) {
            throw std::runtime_error("Cannot enqueue on a sequential ParallelExecutor (num_threads <= 1)");
        }
        return pool->enqueue(std::forward<F>(f), std::forward<Args>(args)...);
    }

    // Parallel loop over index range [start, end)
    template<typename Func>
    void parallel_for(size_t start, size_t end, Func&& func) {
        if (start >= end) return;
        size_t total = end - start;

        // If single threaded or single item, execute sequentially
        if (thread_count <= 1 || !pool || total == 1) {
            for (size_t i = start; i < end; ++i) {
                func(i);
            }
            return;
        }

        // Chunking
        size_t chunks = std::min(thread_count, total);
        size_t chunk_size = (total + chunks - 1) / chunks;

        std::vector<std::future<void>> futures;
        futures.reserve(chunks);

        for (size_t c = 0; c < chunks; ++c) {
            size_t chunk_start = start + c * chunk_size;
            size_t chunk_end = std::min(chunk_start + chunk_size, end);
            if (chunk_start >= chunk_end) break;

            futures.emplace_back(pool->enqueue([chunk_start, chunk_end, &func]() {
                for (size_t i = chunk_start; i < chunk_end; ++i) {
                    func(i);
                }
            }));
        }

        for (auto& fut : futures) {
            fut.get();
        }
    }

    // Parallel map: transform a vector of Input to vector of Output in parallel
    template<typename InputType, typename TransformFunc>
    auto parallel_map(const std::vector<InputType>& inputs, TransformFunc&& func) 
#if __cplusplus >= 201703L
        -> std::vector<typename std::invoke_result<TransformFunc, const InputType&>::type>
#else
        -> std::vector<typename std::result_of<TransformFunc(const InputType&)>::type>
#endif
    {
#if __cplusplus >= 201703L
        using OutputType = typename std::invoke_result<TransformFunc, const InputType&>::type;
#else
        using OutputType = typename std::result_of<TransformFunc(const InputType&)>::type;
#endif
        size_t n = inputs.size();
        std::vector<OutputType> results(n);
        if (n == 0) return results;

        if (thread_count <= 1 || !pool || n == 1) {
            for (size_t i = 0; i < n; ++i) {
                results[i] = func(inputs[i]);
            }
            return results;
        }

        std::vector<std::future<OutputType>> futures;
        futures.reserve(n);

        for (size_t i = 0; i < n; ++i) {
            futures.emplace_back(pool->enqueue([&inputs, &func, i]() -> OutputType {
                return func(inputs[i]);
            }));
        }

        for (size_t i = 0; i < n; ++i) {
            results[i] = futures[i].get();
        }

        return results;
    }

private:
    size_t thread_count;
    std::unique_ptr<ThreadPool> pool;
};
