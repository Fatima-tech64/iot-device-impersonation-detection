"""Basic offline checks for the normal sensor simulator."""

import json
import random
import unittest
from datetime import datetime

from simulator.device_simulator.config import SimulatorConfig
from simulator.device_simulator.payload import build_payload
from simulator.device_simulator.sensors import NormalSensorSimulator


class SensorSimulatorTests(unittest.TestCase):
    def test_sensor_readings_have_expected_types_and_ranges(self):
        sensors = NormalSensorSimulator(random.Random(7))
        for _ in range(100):
            reading = sensors.read()
            self.assertIsInstance(reading["temperature"], float)
            self.assertIsInstance(reading["humidity"], float)
            self.assertIsInstance(reading["motion"], bool)
            self.assertGreaterEqual(reading["temperature"], 18.0)
            self.assertLessEqual(reading["temperature"], 32.0)
            self.assertGreaterEqual(reading["humidity"], 30.0)
            self.assertLessEqual(reading["humidity"], 80.0)

    def test_payload_schema_and_json_encoding(self):
        config = SimulatorConfig(
            device_id="IOT-001",
            device_type="environment_sensor",
            mqtt_host="localhost",
            mqtt_port=1883,
            mqtt_username=None,
            mqtt_password=None,
            mqtt_topic_template="iot/devices/{device_id}/telemetry",
            publish_interval=5,
        )
        payload = build_payload(config, NormalSensorSimulator(random.Random(1)))
        decoded = json.loads(json.dumps(payload))

        self.assertEqual(decoded["device_id"], "IOT-001")
        self.assertEqual(decoded["device_type"], "environment_sensor")
        self.assertEqual(
            set(decoded),
            {"device_id", "device_type", "temperature", "humidity", "motion", "timestamp"},
        )
        datetime.fromisoformat(decoded["timestamp"])
        self.assertEqual(config.topic, "iot/devices/IOT-001/telemetry")


if __name__ == "__main__":
    unittest.main()
