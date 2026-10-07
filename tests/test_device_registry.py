"""Unit tests for registry loading, lookup, and profile validation."""

import json
import tempfile
import unittest
from pathlib import Path

from src.security_engine.device_registry import (
    DeviceRegistry,
    load_registry,
    validate_profile,
)


VALID_PROFILE = {
    "device_id": "IOT-001",
    "device_type": "environment_sensor",
    "temperature_range": {"min": 20.0, "max": 35.0},
    "humidity_range": {"min": 40.0, "max": 80.0},
    "expected_interval": 5,
    "expected_motion_behavior": "intermittent",
    "status": "trusted",
}


class DeviceRegistryTests(unittest.TestCase):
    def test_load_and_find_registered_profile(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            registry_file = Path(folder) / "registry.json"
            registry_file.write_text(
                json.dumps({"devices": [VALID_PROFILE]}), encoding="utf-8"
            )

            registry = load_registry(registry_file)

        self.assertTrue(registry.is_registered("IOT-001"))
        self.assertFalse(registry.is_registered("IOT-999"))
        self.assertEqual(registry.get_profile("IOT-001"), VALID_PROFILE)
        self.assertIsNone(registry.get_profile("IOT-999"))

    def test_profile_validator_rejects_missing_and_invalid_values(self):
        self.assertTrue(validate_profile(VALID_PROFILE))

        incomplete = dict(VALID_PROFILE)
        incomplete.pop("expected_interval")
        self.assertFalse(validate_profile(incomplete))

        invalid_range = dict(VALID_PROFILE)
        invalid_range["temperature_range"] = {"min": 40, "max": 20}
        self.assertFalse(validate_profile(invalid_range))

    def test_registry_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, "Duplicate device_id"):
            DeviceRegistry([VALID_PROFILE, dict(VALID_PROFILE)])

    def test_registry_rejects_invalid_profile_when_loading(self):
        incomplete = dict(VALID_PROFILE)
        incomplete.pop("status")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            registry_file = Path(folder) / "registry.json"
            registry_file.write_text(
                json.dumps({"devices": [incomplete]}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "Invalid or incomplete"):
                load_registry(registry_file)


if __name__ == "__main__":
    unittest.main()
