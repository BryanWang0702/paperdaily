import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import local_app


class TestLocalSchedule(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("Asia/Shanghai")

    def test_latest_due_slot_follows_two_daily_slots(self):
        cases = [
            (datetime(2026, 8, 16, 4, 0, tzinfo=self.tz), "2026-08-15T20:30:00+08:00"),
            (datetime(2026, 8, 16, 6, 0, tzinfo=self.tz), "2026-08-16T05:30:00+08:00"),
            (datetime(2026, 8, 16, 19, 0, tzinfo=self.tz), "2026-08-16T05:30:00+08:00"),
            (datetime(2026, 8, 16, 21, 0, tzinfo=self.tz), "2026-08-16T20:30:00+08:00"),
        ]
        for now, expected in cases:
            with self.subTest(now=now):
                slot = local_app._latest_due_slot(now, ["05:30", "20:30"])
                self.assertEqual(slot.isoformat(), expected)

    def test_completed_slot_skips_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "local_state.json"
            latest = root / "site" / "data" / "latest.json"
            latest.parent.mkdir(parents=True)
            latest.write_text("{}", encoding="utf-8")
            state.write_text(
                json.dumps({
                    "last_successful_slot": "2026-08-16T05:30:00+08:00",
                    "last_successful_config_hash": "same",
                }),
                encoding="utf-8",
            )
            config = {
                "timezone": "Asia/Shanghai",
                "local": {
                    "refresh_mode": "scheduled",
                    "refresh_times": ["05:30", "20:30"],
                    "refresh_on_config_change": True,
                },
            }
            now = datetime(2026, 8, 16, 19, 0, tzinfo=self.tz)
            with patch.object(local_app, "STATE_FILE", state), patch.object(local_app, "LATEST_SITE_DATA", latest):
                should_refresh, slot, _ = local_app._refresh_decision(config, now, config_hash="same")
            self.assertFalse(should_refresh)
            self.assertEqual(slot.hour, 5)
            self.assertEqual(slot.minute, 30)

    def test_config_change_triggers_refresh_even_when_slot_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "local_state.json"
            latest = root / "site" / "data" / "latest.json"
            latest.parent.mkdir(parents=True)
            latest.write_text("{}", encoding="utf-8")
            state.write_text(
                json.dumps({
                    "last_successful_slot": "2026-08-16T05:30:00+08:00",
                    "last_successful_config_hash": "old-hash",
                }),
                encoding="utf-8",
            )
            config = {
                "timezone": "Asia/Shanghai",
                "local": {
                    "refresh_mode": "scheduled",
                    "refresh_times": ["05:30", "20:30"],
                    "refresh_on_config_change": True,
                },
            }
            now = datetime(2026, 8, 16, 19, 0, tzinfo=self.tz)
            with patch.object(local_app, "STATE_FILE", state), patch.object(local_app, "LATEST_SITE_DATA", latest):
                should_refresh, slot, reason = local_app._refresh_decision(config, now, config_hash="new-hash")
            self.assertTrue(should_refresh)
            self.assertEqual(slot.hour, 5)
            self.assertIn("config.yaml changed", reason)

    def test_config_change_does_not_override_never_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "local_state.json"
            latest = root / "site" / "data" / "latest.json"
            latest.parent.mkdir(parents=True)
            latest.write_text("{}", encoding="utf-8")
            state.write_text(json.dumps({"last_successful_config_hash": "old"}), encoding="utf-8")
            config = {
                "timezone": "Asia/Shanghai",
                "local": {
                    "refresh_mode": "never",
                    "refresh_times": ["05:30", "20:30"],
                    "refresh_on_config_change": True,
                },
            }
            now = datetime(2026, 8, 16, 19, 0, tzinfo=self.tz)
            with patch.object(local_app, "STATE_FILE", state), patch.object(local_app, "LATEST_SITE_DATA", latest):
                should_refresh, _, reason = local_app._refresh_decision(config, now, config_hash="new")
            self.assertFalse(should_refresh)
            self.assertIn("refresh_mode is never", reason)

    def test_new_slot_triggers_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "local_state.json"
            latest = root / "site" / "data" / "latest.json"
            latest.parent.mkdir(parents=True)
            latest.write_text("{}", encoding="utf-8")
            state.write_text(
                json.dumps({
                    "last_successful_slot": "2026-08-16T05:30:00+08:00",
                    "last_successful_config_hash": "same",
                }),
                encoding="utf-8",
            )
            config = {
                "timezone": "Asia/Shanghai",
                "local": {"refresh_mode": "scheduled", "refresh_times": ["05:30", "20:30"]},
            }
            now = datetime(2026, 8, 16, 21, 0, tzinfo=self.tz)
            with patch.object(local_app, "STATE_FILE", state), patch.object(local_app, "LATEST_SITE_DATA", latest):
                should_refresh, slot, _ = local_app._refresh_decision(config, now, config_hash="same")
            self.assertTrue(should_refresh)
            self.assertEqual(slot.hour, 20)
            self.assertEqual(slot.minute, 30)

    def test_missing_local_data_forces_first_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "local_state.json"
            latest = root / "site" / "data" / "latest.json"
            config = {
                "timezone": "Asia/Shanghai",
                "local": {"refresh_mode": "never", "refresh_times": ["05:30", "20:30"]},
            }
            now = datetime(2026, 8, 16, 19, 0, tzinfo=self.tz)
            with patch.object(local_app, "STATE_FILE", state), patch.object(local_app, "LATEST_SITE_DATA", latest):
                should_refresh, _, reason = local_app._refresh_decision(config, now, config_hash="hash")
            self.assertTrue(should_refresh)
            self.assertIn("no local dashboard data", reason)


if __name__ == "__main__":
    unittest.main()
