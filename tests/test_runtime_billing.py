import unittest

from src.runtime_pipeline import _planned_runs_per_day, _public_billing, _reference_run_cost


class TestRuntimeBilling(unittest.TestCase):
    def test_annual_reference_prefers_scheduled_runs(self):
        runs = [
            {"kind": "development", "cost_cny": 1.0, "usage": {"requests": 10}},
            {"kind": "scheduled", "cost_cny": 0.03, "usage": {"requests": 5}},
            {"kind": "scheduled", "cost_cny": 0.05, "usage": {"requests": 5}},
        ]
        self.assertAlmostEqual(_reference_run_cost(runs), 0.04)

    def test_reference_falls_back_to_api_active_runs(self):
        runs = [
            {"kind": "development", "cost_cny": 0.02, "usage": {"requests": 2}},
            {"kind": "development", "cost_cny": 0.04, "usage": {"requests": 4}},
            {"kind": "development", "cost_cny": 0.0, "usage": {"requests": 0}},
        ]
        self.assertAlmostEqual(_reference_run_cost(runs), 0.03)

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
