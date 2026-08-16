import unittest

from src.billing import add_usage, calculate_cost_cny, normalize_usage


class BillingTests(unittest.TestCase):
    def test_cost_uses_cache_hit_miss_and_output_rates(self):
        usage = {
            "requests": 2,
            "prompt_tokens": 1_500_000,
            "prompt_cache_hit_tokens": 500_000,
            "prompt_cache_miss_tokens": 1_000_000,
            "completion_tokens": 100_000,
            "total_tokens": 1_600_000,
        }
        pricing = {
            "input_cache_hit": 0.02,
            "input_cache_miss": 1.0,
            "output": 2.0,
        }
        self.assertAlmostEqual(calculate_cost_cny(usage, pricing), 1.21, places=6)

    def test_unclassified_prompt_tokens_are_conservatively_misses(self):
        usage = normalize_usage({"prompt_tokens": 1000, "completion_tokens": 200})
        self.assertEqual(usage["prompt_cache_miss_tokens"], 1000)
        self.assertEqual(usage["total_tokens"], 1200)

    def test_usage_accumulates_across_runs(self):
        first = {"requests": 1, "prompt_tokens": 100, "prompt_cache_miss_tokens": 100, "completion_tokens": 20}
        second = {"requests": 2, "prompt_tokens": 200, "prompt_cache_hit_tokens": 50, "prompt_cache_miss_tokens": 150, "completion_tokens": 40}
        total = add_usage(first, second)
        self.assertEqual(total["requests"], 3)
        self.assertEqual(total["prompt_tokens"], 300)
        self.assertEqual(total["prompt_cache_hit_tokens"], 50)
        self.assertEqual(total["prompt_cache_miss_tokens"], 250)
        self.assertEqual(total["completion_tokens"], 60)


if __name__ == "__main__":
    unittest.main()
