"""Telemetry payload construction shared by simulator instances."""

from __future__ import annotations

from datetime import datetime, timezone

from .config import SimulatorConfig
from .sensors import NormalSensorSimulator


def build_payload(
    config: SimulatorConfig, sensors: NormalSensorSimulator
) -> dict[str, str | float | bool]:
    """Take sensor readings and build the documented JSON message."""
    return {
        "device_id": config.device_id,
        "device_type": config.device_type,
        **sensors.read(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
