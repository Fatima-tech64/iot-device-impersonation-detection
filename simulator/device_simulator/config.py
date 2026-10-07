"""Configuration loading for the IoT device simulator."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class SimulatorConfig:
    device_id: str
    device_type: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_topic_template: str
    publish_interval: float

    @property
    def topic(self) -> str:
        return self.mqtt_topic_template.format(device_id=self.device_id)

    @property
    def client_id(self) -> str:
        return f"esp32-simulator-{self.device_id}"


def load_config() -> SimulatorConfig:
    """Load settings from .env/environment variables with beginner-friendly defaults."""
    load_dotenv()

    device_id = os.getenv("SIM_DEVICE_ID", "IOT-001").strip()
    if not device_id:
        raise ValueError("SIM_DEVICE_ID must not be empty")

    topic_template = os.getenv(
        "MQTT_TOPIC_TEMPLATE", "iot/devices/{device_id}/telemetry"
    ).strip()
    try:
        topic = topic_template.format(device_id=device_id)
    except (KeyError, ValueError) as exc:
        raise ValueError(
            "MQTT_TOPIC_TEMPLATE must be a valid format string; use {device_id} for the device ID"
        ) from exc
    if not topic:
        raise ValueError("MQTT topic must not be empty")

    try:
        port = int(os.getenv("MQTT_PORT", "1883"))
        interval = float(os.getenv("SIM_PUBLISH_INTERVAL", "5"))
    except ValueError as exc:
        raise ValueError("MQTT_PORT and SIM_PUBLISH_INTERVAL must be numeric") from exc
    if not 1 <= port <= 65535:
        raise ValueError("MQTT_PORT must be between 1 and 65535")
    if interval <= 0:
        raise ValueError("SIM_PUBLISH_INTERVAL must be greater than zero")

    return SimulatorConfig(
        device_id=device_id,
        device_type=os.getenv("SIM_DEVICE_TYPE", "environment_sensor").strip(),
        mqtt_host=os.getenv("MQTT_HOST", "localhost").strip(),
        mqtt_port=port,
        mqtt_username=os.getenv("MQTT_USERNAME") or None,
        mqtt_password=os.getenv("MQTT_PASSWORD") or None,
        mqtt_topic_template=topic_template,
        publish_interval=interval,
    )
