"""Unit tests for possible-impersonation detection decisions."""

import unittest
from datetime import datetime, timezone

from src.security_engine.device_registry import DeviceRegistry
from src.security_engine.impersonation_detector import (
    DetectionThresholds,
    ImpersonationDetector,
)


PROFILE = {
    "device_id": "IOT-001",
    "device_type": "environment_sensor",
    "temperature_range": {"min": 20.0, "max": 35.0},
    "humidity_range": {"min": 40.0, "max": 80.0},
    "expected_interval": 5,
    "expected_motion_behavior": "usually_inactive",
    "status": "trusted",
}


class ImpersonationDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = ImpersonationDetector(DeviceRegistry([PROFILE]))
        self.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()

    def telemetry(self, **updates):
        message = {
            "device_id": "IOT-001",
            "temperature": 28.5,
            "humidity": 61.2,
            "motion": False,
            "timestamp": self.timestamp,
        }
        message.update(updates)
        return message

    def test_registered_device_with_normal_behaviour_is_trusted(self):
        event = self.detector.detect(self.telemetry())
        self.assertEqual(event["classification"], "TRUSTED")
        self.assertEqual(event["risk_score"], 0)
        self.assertEqual(event["reasons"], [])
        self.assertEqual(event["device_id"], "IOT-001")
        datetime.fromisoformat(event["timestamp"])

    def test_unknown_device_is_classified_separately(self):
        event = self.detector.detect(self.telemetry(device_id="IOT-999"))
        self.assertEqual(event["classification"], "UNKNOWN_DEVICE")
        self.assertEqual(event["risk_level"], "MEDIUM")
        self.assertEqual(event["risk_score"], 40)
        self.assertIn("identity is unknown", event["reasons"][0])

    def test_registered_identity_with_significant_mismatch_is_possible_impersonation(self):
        event = self.detector.detect(self.telemetry(temperature=39.0))
        self.assertEqual(event["classification"], "POSSIBLE_IMPERSONATION")
        self.assertEqual(event["risk_score"], 15)
        self.assertIn("Temperature outside the registered range", event["reasons"])

    def test_multiple_severe_anomalies_are_high_risk(self):
        event = self.detector.detect(
            self.telemetry(temperature=40.0, humidity=20.0, motion=True)
        )
        self.assertEqual(event["classification"], "HIGH_RISK_IMPERSONATION")
        self.assertEqual(event["risk_score"], 40)
        self.assertEqual(len(event["reasons"]), 3)

    def test_thresholds_are_configurable_and_validated(self):
        detector = ImpersonationDetector(
            DeviceRegistry([PROFILE]),
            DetectionThresholds(
                possible_impersonation_risk=40,
                high_risk_score=80,
                high_risk_anomaly_count=4,
            ),
        )
        event = detector.detect(self.telemetry(temperature=39.0))
        self.assertEqual(event["classification"], "SUSPICIOUS_BEHAVIOUR")
        with self.assertRaises(ValueError):
            DetectionThresholds(possible_impersonation_risk=80, high_risk_score=60)

    def test_event_includes_structured_behaviour_checks(self):
        event = self.detector.detect(self.telemetry(humidity=90.0))
        self.assertEqual(
            set(event["behaviour_checks"]),
            {
                "device_id", "identity_valid", "temperature_valid", "humidity_valid",
                "message_rate_valid", "message_frequency", "motion_valid",
                "behaviour_score", "status",
            },
        )
        self.assertEqual(event["behaviour_checks"]["status"], "SUSPICIOUS")
        self.assertEqual(event["factors"]["humidity"], 15)


if __name__ == "__main__":
    unittest.main()

