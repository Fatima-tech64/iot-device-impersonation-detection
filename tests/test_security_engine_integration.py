"""Integration tests for validation, detection, and local event logging."""

import contextlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from src.security_engine.device_registry import DeviceRegistry
from src.security_engine.engine import SecurityEngine, SecurityEventLogger


PROFILE = {
    "device_id": "IOT-001",
    "device_type": "environment_sensor",
    "temperature_range": {"min": 20.0, "max": 35.0},
    "humidity_range": {"min": 40.0, "max": 80.0},
    "expected_interval": 5,
    "expected_motion_behavior": "intermittent",
    "status": "trusted",
}


class SecurityEngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.log_path = Path(self.temp_dir.name) / "events.jsonl"
        self.engine = SecurityEngine(
            DeviceRegistry([PROFILE]), SecurityEventLogger(self.log_path)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def payload(self, **updates):
        value = {
            "device_id": "IOT-001",
            "device_type": "environment_sensor",
            "temperature": 28.5,
            "humidity": 61.2,
            "motion": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        value.update(updates)
        return json.dumps(value).encode("utf-8")

    def process_quietly(self, payload):
        with contextlib.redirect_stdout(StringIO()):
            return self.engine.process_message(
                "iot/devices/IOT-001/telemetry", payload
            )

    def test_valid_message_runs_full_pipeline_and_is_logged(self):
        event = self.process_quietly(self.payload())
        self.assertEqual(event["classification"], "TRUSTED")
        self.assertEqual(event["risk_score"], 0)
        self.assertTrue(self.log_path.exists())
        logged = json.loads(self.log_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(logged["event_type"], "TELEMETRY_SECURITY_ASSESSMENT")
        self.assertEqual(logged["topic"], "iot/devices/IOT-001/telemetry")

    def test_unknown_device_is_logged_without_crashing(self):
        event = self.process_quietly(self.payload(device_id="IOT-999"))
        self.assertEqual(event["classification"], "UNKNOWN_DEVICE")

    def test_malformed_missing_and_invalid_sensor_messages_are_suspicious(self):
        malformed = self.process_quietly(b"not-json")
        missing = self.process_quietly(b'{"device_id":"IOT-001"}')
        invalid_sensor = self.process_quietly(self.payload(temperature=999))

        self.assertEqual(malformed["classification"], "SUSPICIOUS")
        self.assertEqual(missing["classification"], "SUSPICIOUS")
        self.assertEqual(invalid_sensor["classification"], "SUSPICIOUS")
        self.assertEqual(invalid_sensor["risk_level"], "CRITICAL")
        self.assertEqual(len(self.log_path.read_text(encoding="utf-8").splitlines()), 3)

    def test_bad_message_does_not_prevent_next_message_from_processing(self):
        bad = self.process_quietly(b"{")
        good = self.process_quietly(self.payload())
        self.assertEqual(bad["classification"], "SUSPICIOUS")
        self.assertEqual(good["classification"], "TRUSTED")
        self.assertEqual(len(self.log_path.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
