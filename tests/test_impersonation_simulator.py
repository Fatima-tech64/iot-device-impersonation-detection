"""Offline tests for safe impersonation telemetry scenarios."""

import json
import unittest

from simulator.impersonation_simulator.scenarios import ScenarioGenerator


class ImpersonationScenarioTests(unittest.TestCase):
    def test_all_predefined_scenarios_use_normal_payload_schema(self):
        for name in ("NORMAL", "ABNORMAL_SENSOR", "ABNORMAL_FREQUENCY", "IMPERSONATION"):
            with self.subTest(scenario=name):
                generator = ScenarioGenerator(name, "IOT-001")
                payload = generator.next_payload()
                self.assertEqual(
                    set(payload),
                    {"device_id", "device_type", "temperature", "humidity", "motion", "timestamp"},
                )
                self.assertEqual(json.loads(json.dumps(payload))["device_id"], "IOT-001")
                self.assertTrue(generator.interval > 0)

    def test_normal_scenario_uses_normal_ranges_and_interval(self):
        generator = ScenarioGenerator("NORMAL", "IOT-001")
        payload = generator.next_payload()
        self.assertGreaterEqual(payload["temperature"], 18.0)
        self.assertLessEqual(payload["temperature"], 32.0)
        self.assertGreaterEqual(payload["humidity"], 30.0)
        self.assertLessEqual(payload["humidity"], 80.0)
        self.assertEqual(generator.interval, 5.0)

    def test_abnormal_sensor_scenario_is_outside_registered_example_ranges(self):
        payload = ScenarioGenerator("ABNORMAL_SENSOR", "IOT-001").next_payload()
        self.assertEqual(payload["temperature"], 42.0)
        self.assertEqual(payload["humidity"], 95.0)

    def test_abnormal_frequency_and_impersonation_use_fast_interval(self):
        self.assertLess(ScenarioGenerator("ABNORMAL_FREQUENCY", "IOT-001").interval, 2.5)
        impersonation = ScenarioGenerator("IMPERSONATION", "IOT-001")
        payload = impersonation.next_payload()
        self.assertEqual(impersonation.interval, 0.5)
        self.assertEqual(payload["temperature"], 42.0)
        self.assertEqual(payload["humidity"], 95.0)
        self.assertTrue(payload["motion"])

    def test_custom_scenario_uses_configured_values(self):
        generator = ScenarioGenerator(
            "CUSTOM", "IOT-123", temperature=37.5, humidity=88.0,
            motion=True, interval=2.0,
        )
        payload = generator.next_payload()
        self.assertEqual(payload["device_id"], "IOT-123")
        self.assertEqual(payload["temperature"], 37.5)
        self.assertEqual(payload["humidity"], 88.0)
        self.assertTrue(payload["motion"])
        self.assertEqual(generator.interval, 2.0)

    def test_invalid_scenario_and_interval_are_rejected(self):
        with self.assertRaises(ValueError):
            ScenarioGenerator("REAL_ATTACK", "IOT-001")
        with self.assertRaises(ValueError):
            ScenarioGenerator("CUSTOM", "IOT-001", interval=0)


if __name__ == "__main__":
    unittest.main()
