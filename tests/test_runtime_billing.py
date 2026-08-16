import unittest

from src.runtime_pipeline import (
    _expected_requests_per_full_run,
    _historical_reference_cost,
    _planned_runs_per_day,
    _public_billing,
    _reference_run_cost,
)


class TestRuntimeBilling(unittest.TestCase):
    def test_annual_reference_prefers_scheduled_runs(self):
        runs = [
            {"kind": "development", "cost_cny": 1.0, "usage": {"requests": 10}},
            {"kind": "scheduled", "cost_cny": 0.03, "usage": {"requests": 5}},
            {"kind": "scheduled", "cost_cny": 0.05, "usage": {"requests": 5}},
        ]
        self.assertAlmostEqual(_reference_run_cost(runs), 0.04)

    def test_development_runs_do_not_drive_reference_cost(self):
        runs = [
            {"kind": "development", "cost_cny": 2.0, "usage": {"requests": 10}},
            {"kind": "development", "cost_cny": 3.0, "usage": {"requests": 10}},
        ]
        self.assertAlmostEqual(_reference_run_cost(runs, fallback=0.04), 0.04)

    def test_historical_bootstrap_uses_request_volume_and_batch_sizes(self):
        config = {
            "ai": {
                "max_analyzed": 40,
                "rank_batch_size": 20,
                "summary_batch_size": 5,
            }
        }
        self.assertEqual(_expected_requests_per_full_run(config), 10)
        ledger = {
            "total_cost_cny": 0.220957,
            "total_usage": {"requests": 50},
        }
        self.assertAlmostEqual(_historical_reference_cost(ledger, config), 0.220957 / 5)

    def test_planned_runs_follow_refresh_slots(self):
        config = {"local": {"refresh_times": ["05:30", "20:30"]}}
        self.assertEqual(_planned_runs_per_day(config), 2)

    def test_public_billing_contains_last_total_and_annual(self):
        billing = _public_billing({
            "last_run_cost_cny": 0.03,
            "total_cost_cny": 1.25,
            "average_run_cost_cny": 0.025,
            "annual_estimate_cny": 18.25,
            "planned_runs_per_day": 2,
            "run_count": 12,
        })
        self.assertEqual(billing["last_run_cost_cny"], 0.03)
        self.assertEqual(billing["total_cost_cny"], 1.25)
        self.assertEqual(billing["annual_estimate_cny"], 18.25)


if __name__ == "__main__":
    unittest.main()
