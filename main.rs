// [Transpiler API] Connecting to gemini-3.5-flash-lite...
use std::time::Instant;

struct Lcg {
    value: u32,
}

impl Lcg {
    fn new(seed: u32) -> Self {
        Self { value: seed }
    }

    #[inline(always)]
    fn next(&mut self) -> u32 {
        self.value = self.value.wrapping_mul(1664525).wrapping_add(1013904223);
        self.value
    }
}

fn max_subarray_sum(n: usize, seed: u32, min_val: i32, max_val: i32) -> i64 {
    let mut lcg_gen = Lcg::new(seed);
    let range_size = (max_val - min_val + 1) as u32;
    
    let mut random_numbers = Vec::with_capacity(n);
    for _ in 0..n {
        let val = (lcg_gen.next() % range_size) as i32 + min_val;
        random_numbers.push(val as i64);
    }

    let mut max_sum = i64::MIN;
    for i in 0..n {
        let mut current_sum: i64 = 0;
        for j in i..n {
            current_sum += random_numbers[j];
            if current_sum > max_sum {
                max_sum = current_sum;
            }
        }
    }
    max_sum
}

fn total_max_subarray_sum(n: usize, initial_seed: u32, min_val: i32, max_val: i32) -> i64 {
    let mut total_sum: i64 = 0;
    let mut lcg_gen = Lcg::new(initial_seed);
    for _ in 0..20 {
        let seed = lcg_gen.next();
        total_sum += max_subarray_sum(n, seed, min_val, max_val);
    }
    total_sum
}

fn main() {
    let n = 10000;
    let initial_seed = 42;
    let min_val = -10;
    let max_val = 10;

    let start_time = Instant::now();
    let result = total_max_subarray_sum(n, initial_seed, min_val, max_val);
    let end_time = Instant::now();

    let duration = end_time.duration_since(start_time).as_secs_f64();

    println!("Total Maximum Subarray Sum (20 runs): {}", result);
    println!("Execution Time: {:.6} seconds", duration);
}