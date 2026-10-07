"""Independent unit tests for profile-based behaviour verification."""

import unittest
from datetime import datetime, timedelta, timezone

from src.security_engine.behaviour import BehaviorVerifier
from src.security_engine.device_registry import DeviceRegistry


PROFILE = {
    "device_id": "IOT-001",
    "device_type": "environment_sensor",
    "temperature_range": {"min": 20.0, "max": 35.0},
    "humidity_range": {"min": 40.0, "max": 80.0},
    "expected_interval": 5,
    "expected_motion_behavior": "intermittent",
    "status": "trusted",
}


class BehaviorVerifierTests(unittest.TestCase):
    def setUp(self):
        self.verifier = BehaviorVerifier(DeviceRegistry([PROFILE]))
        self.base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def message(self, **changes):
        message = {
            "device_id": "IOT-001",
            "temperature": 28.5,
            "humidity": 61.2,
            "motion": False,
            "timestamp": self.base_time.isoformat(),
        }
        message.update(changes)
        return message

    def test_normal_behaviour(self):
        result = self.verifier.verify(self.message())
        self.assertEqual(result["behaviour_score"], 100)
        self.assertEqual(result["status"], "NORMAL")
        self.assertTrue(all(result[key] for key in (
            "identity_valid", "temperature_valid", "humidity_valid",
            "message_rate_valid", "motion_valid"
        )))

    def test_abnormal_temperature(self):
        result = self.verifier.verify(self.message(temperature=38.0))
        self.assertFalse(result["temperature_valid"])
        self.assertEqual(result["behaviour_score"], 80)
        self.assertEqual(result["status"], "SUSPICIOUS")

    def test_abnormal_humidity(self):
        result = self.verifier.verify(self.message(humidity=25.0))
        self.assertFalse(result["humidity_valid"])
        self.assertEqual(result["behaviour_score"], 80)

    def test_abnormal_message_frequency(self):
        self.verifier.verify(self.message())
        too_soon = (self.base_time + timedelta(seconds=1)).isoformat()
        result = self.verifier.verify(self.message(timestamp=too_soon))
        self.assertFalse(result["message_rate_valid"])
        self.assertEqual(result["behaviour_score"], 80)

    def test_unknown_device(self):
        result = self.verifier.verify(self.message(device_id="IOT-999"))
        self.assertFalse(result["identity_valid"])
        self.assertEqual(result["behaviour_score"], 0)
        self.assertEqual(result["status"], "SUSPICIOUS")

    def test_multiple_simultaneous_anomalies(self):
        result = self.verifier.verify(self.message(
            temperature=40.0,
            humidity=20.0,
            motion="moving",
        ))
        self.assertFalse(result["temperature_valid"])
        self.assertFalse(result["humidity_valid"])
        self.assertFalse(result["motion_valid"])
        self.assertEqual(result["behaviour_score"], 40)
        self.assertEqual(result["status"], "SUSPICIOUS")


if __name__ == "__main__":
    unittest.main()
