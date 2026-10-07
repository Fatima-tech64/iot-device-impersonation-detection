"""Safe, predefined telemetry scenarios for identity-impersonation demonstrations."""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any

from simulator.device_simulator.sensors import NormalSensorSimulator

SCENARIOS = ("NORMAL", "ABNORMAL_SENSOR", "ABNORMAL_FREQUENCY", "IMPERSONATION", "CUSTOM")


class ScenarioGenerator:
    """Generate telemetry only; this module performs no network actions."""

    def __init__(
        self,
        scenario: str,
        device_id: str,
        *,
        temperature: float | None = None,
        humidity: float | None = None,
        motion: bool | None = None,
        interval: float | None = None,
        rng: random.Random | None = None,
    ) -> None:
        scenario = scenario.upper()
        if scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of: {', '.join(SCENARIOS)}")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id must not be empty")
        if interval is not None and (not math.isfinite(interval) or interval <= 0):
            raise ValueError("interval must be a positive number")
        for name, value, lower, upper in (
            ("temperature", temperature, -40, 80),
            ("humidity", humidity, 0, 100),
        ):
            if value is not None and (not math.isfinite(value) or not lower <= value <= upper):
                raise ValueError(f"{name} must be between {lower} and {upper}")

        self.scenario = scenario
        self.device_id = device_id
        self._sensor = NormalSensorSimulator(rng)
        self._custom_temperature = temperature
        self._custom_humidity = humidity
        self._custom_motion = motion

        default_intervals = {
            "NORMAL": 5.0,
            "ABNORMAL_SENSOR": 5.0,
            "ABNORMAL_FREQUENCY": 0.5,
            "IMPERSONATION": 0.5,
            "CUSTOM": 5.0,
        }
        if scenario in {"NORMAL", "ABNORMAL_SENSOR", "CUSTOM"} and interval is not None:
            self.interval = interval
        else:
            self.interval = default_intervals[scenario]

    def next_payload(self) -> dict[str, str | float | bool]:
        """Return the next message in the normal simulator's JSON schema."""
        if self.scenario in {"NORMAL", "ABNORMAL_FREQUENCY"}:
            readings = self._sensor.read()
        elif self.scenario == "ABNORMAL_SENSOR":
            readings = {"temperature": 42.0, "humidity": 95.0, "motion": False}
        elif self.scenario == "IMPERSONATION":
            readings = {"temperature": 42.0, "humidity": 95.0, "motion": True}
        else:
            readings = self._sensor.read()
            if self._custom_temperature is not None:
                readings["temperature"] = round(self._custom_temperature, 1)
            if self._custom_humidity is not None:
                readings["humidity"] = round(self._custom_humidity, 1)
            if self._custom_motion is not None:
                readings["motion"] = self._custom_motion

        return {
            "device_id": self.device_id,
            "device_type": "environment_sensor",
            **readings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

