"""Transparent, profile-based checks for IoT telemetry behaviour.

Scoring: five checks are worth 20 points each. A check that passes earns 20;
a failed or unevaluable check earns 0. A score of 100 is NORMAL. Any lower
score is SUSPICIOUS, so one failed check (80 points) is visibly flagged.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .device_registry import DeviceRegistry


_CHECK_FIELDS = (
    "identity_valid",
    "temperature_valid",
    "humidity_valid",
    "message_rate_valid",
    "motion_valid",
)
_POINTS_PER_CHECK = 20


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


class BehaviorVerifier:
    """Compare telemetry with trusted profiles and return structured results.

    The verifier retains the latest valid timestamp for each device so callers
    can pass messages in sequence. For each interval, accepted bounds are
    expected_interval ± 50% (inclusive). A device's first message has no prior
    interval to compare, so its rate check passes if its timestamp is valid.
    """

    def __init__(self, registry: DeviceRegistry, interval_tolerance: float = 0.5) -> None:
        if not 0 <= interval_tolerance < 1:
            raise ValueError("interval_tolerance must be in [0, 1)")
        self.registry = registry
        self.interval_tolerance = interval_tolerance
        self._last_seen: dict[str, datetime] = {}

    def verify(self, telemetry: dict[str, Any]) -> dict[str, Any]:
        """Validate one telemetry object and return check flags, score, and status."""
        device_id = telemetry.get("device_id") if isinstance(telemetry, dict) else None
        device_id = device_id if isinstance(device_id, str) else ""
        profile = self.registry.get_profile(device_id) if device_id else None
        identity_valid = profile is not None and profile.get("status") == "trusted"

        if profile is None:
            temperature_valid = False
            humidity_valid = False
            message_rate_valid = False
            message_frequency = 0.0
            motion_valid = False
        else:
            temperature_valid = self._in_range(
                telemetry.get("temperature"), profile["temperature_range"]
            )
            humidity_valid = self._in_range(
                telemetry.get("humidity"), profile["humidity_range"]
            )
            motion_valid = self._motion_matches(
                telemetry.get("motion"), profile["expected_motion_behavior"]
            )
            message_rate_valid, message_frequency = self._check_interval(
                device_id, telemetry.get("timestamp"), profile["expected_interval"]
            )

        result: dict[str, Any] = {
            "device_id": device_id,
            "identity_valid": identity_valid,
            "temperature_valid": temperature_valid,
            "humidity_valid": humidity_valid,
            "message_rate_valid": message_rate_valid,
            "message_frequency": message_frequency,
            "motion_valid": motion_valid,
        }
        result["behaviour_score"] = sum(
            _POINTS_PER_CHECK for field in _CHECK_FIELDS if result[field]
        )
        result["status"] = "NORMAL" if result["behaviour_score"] == 100 else "SUSPICIOUS"
        return result

    @staticmethod
    def _in_range(value: Any, expected_range: dict[str, Any]) -> bool:
        number = _as_number(value)
        return (
            number is not None
            and expected_range["min"] <= number <= expected_range["max"]
        )

    @staticmethod
    def _motion_matches(value: Any, expected: str) -> bool:
        if not isinstance(value, bool):
            return False
        if expected == "intermittent":
            return True
        if expected == "usually_inactive":
            return value is False
        if expected == "frequent":
            return value is True
        return False

    def _check_interval(
        self, device_id: str, timestamp_value: Any, expected: Any
    ) -> tuple[bool, float]:
        timestamp = _parse_timestamp(timestamp_value)
        expected_seconds = _as_number(expected)
        if timestamp is None or expected_seconds is None or expected_seconds <= 0:
            return False, 0.0

        previous = self._last_seen.get(device_id)
        if previous is None:
            self._last_seen[device_id] = timestamp
            return True, round(1 / expected_seconds, 6)

        elapsed = (timestamp - previous).total_seconds()
        lower = expected_seconds * (1 - self.interval_tolerance)
        upper = expected_seconds * (1 + self.interval_tolerance)
        valid = lower <= elapsed <= upper
        # Do not let an out-of-order timestamp move the baseline backwards.
        if elapsed > 0:
            self._last_seen[device_id] = timestamp
        frequency = round(1 / elapsed, 6) if elapsed > 0 else 0.0
        return valid, frequency
