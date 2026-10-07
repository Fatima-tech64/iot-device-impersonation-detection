"""Load and query the trusted IoT device registry."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


_REQUIRED_FIELDS = {
    "device_id",
    "device_type",
    "temperature_range",
    "humidity_range",
    "expected_interval",
    "expected_motion_behavior",
    "status",
}
_VALID_STATUSES = {"trusted", "inactive", "revoked"}
_VALID_MOTION_BEHAVIOURS = {"intermittent", "usually_inactive", "frequent"}


def _valid_range(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"min", "max"}:
        return False
    lower, upper = value["min"], value["max"]
    if (
        isinstance(lower, bool)
        or isinstance(upper, bool)
        or not isinstance(lower, (int, float))
        or not isinstance(upper, (int, float))
    ):
        return False
    return lower <= upper


def validate_profile(profile: Any) -> bool:
    """Return whether a device profile has all required fields and valid values.

    Motion behaviour must be one of: intermittent, usually_inactive, or frequent.
    Status must be trusted, inactive, or revoked.
    """
    if not isinstance(profile, dict) or not _REQUIRED_FIELDS.issubset(profile):
        return False

    device_id = profile["device_id"]
    device_type = profile["device_type"]
    interval = profile["expected_interval"]
    motion = profile["expected_motion_behavior"]
    status = profile["status"]

    return (
        isinstance(device_id, str)
        and bool(device_id.strip())
        and isinstance(device_type, str)
        and bool(device_type.strip())
        and _valid_range(profile["temperature_range"])
        and _valid_range(profile["humidity_range"])
        and not isinstance(interval, bool)
        and isinstance(interval, (int, float))
        and interval > 0
        and motion in _VALID_MOTION_BEHAVIOURS
        and status in _VALID_STATUSES
    )


class DeviceRegistry:
    """In-memory, read-only view of registered device profiles."""

    def __init__(self, profiles: list[dict[str, Any]]) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}
        for index, profile in enumerate(profiles):
            if not validate_profile(profile):
                raise ValueError(f"Invalid or incomplete device profile at devices[{index}]")
            device_id = profile["device_id"]
            if device_id in self._profiles:
                raise ValueError(f"Duplicate device_id in registry: {device_id}")
            self._profiles[device_id] = deepcopy(profile)

    def is_registered(self, device_id: str) -> bool:
        """Return whether the ID appears in the registry, regardless of status."""
        return device_id in self._profiles

    def get_profile(self, device_id: str) -> dict[str, Any] | None:
        """Return a copy of the registered profile, or None when it is unknown."""
        profile = self._profiles.get(device_id)
        return deepcopy(profile) if profile is not None else None


def load_registry(path: str | Path) -> DeviceRegistry:
    """Read and validate registry JSON from the supplied file path."""
    registry_path = Path(path)
    try:
        with registry_path.open("r", encoding="utf-8") as registry_file:
            data = json.load(registry_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Registry file is not valid JSON: {registry_path}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
        raise ValueError("Registry JSON must contain a 'devices' list")
    return DeviceRegistry(data["devices"])

