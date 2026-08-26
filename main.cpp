// [Transpiler API] Connecting to gemini-3.5-flash-lite...
#include <iostream>
#include <chrono>
#include <vector>
#include <cstdint>
#include <algorithm>
#include <limits>
#include <cstdio>

inline uint32_t lcg_next(uint32_t& value) {
    value = (1664525ULL * value + 1013904223ULL) & 0xFFFFFFFF;
    return value;
}

inline int64_t max_subarray_sum(int n, uint32_t seed, int min_val, int max_val) {
    int range_val = max_val - min_val + 1;
    uint32_t current_seed = seed;
    
    std::vector<int> random_numbers(n);
    for (int i = 0; i < n; ++i) {
        current_seed = (1664525ULL * current_seed + 1013904223ULL) & 0xFFFFFFFF;
        random_numbers[i] = static_cast<int>(current_seed % range_val) + min_val;
    }

    int64_t max_sum = std::numeric_limits<int64_t>::min();
    for (int i = 0; i < n; ++i) {
        int64_t current_sum = 0;
        for (int j = i; j < n; ++j) {
            current_sum += random_numbers[j];
            if (current_sum > max_sum) {
                max_sum = current_sum;
            }
        }
    }
    return max_sum;
}

inline int64_t total_max_subarray_sum(int n, uint32_t initial_seed, int min_val, int max_val) {
    int64_t total_sum = 0;
    uint32_t seed = initial_seed;
    for (int i = 0; i < 20; ++i) {
        seed = (1664525ULL * seed + 1013904223ULL) & 0xFFFFFFFF;
        total_sum += max_subarray_sum(n, seed, min_val, max_val);
    }
    return total_sum;
}

int main() {
    int n = 10000;
    uint32_t initial_seed = 42;
    int min_val = -10;
    int max_val = 10;

    auto start_time = std::chrono::high_resolution_clock::now();
    int64_t result = total_max_subarray_sum(n, initial_seed, min_val, max_val);
    auto end_time = std::chrono::high_resolution_clock::now();

    std::chrono::duration<double> elapsed = end_time - start_time;

    std::cout << "Total Maximum Subarray Sum (20 runs): " << result << "\n";
    std::printf("Execution Time: %.6f seconds\n", elapsed.count());

    return 0;
}