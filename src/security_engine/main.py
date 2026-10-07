"""Run the MQTT-connected local IoT security engine."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv

from simulator.device_simulator.config import load_config
from .device_registry import load_registry
from .engine import SecurityEngine, SecurityEventLogger
from .mqtt_client import MqttSecuritySubscriber
from .thingsboard import ThingsBoardMqttPublisher, ThingsBoardSettings


def main() -> int:
    load_dotenv()
    try:
        broker_config = load_config()
        registry_path = Path(os.getenv("DEVICE_REGISTRY_PATH", "config/device_registry.json"))
        log_path = Path(os.getenv("SECURITY_EVENT_LOG", "logs/security_events.jsonl"))
        topic = os.getenv("MQTT_SUBSCRIBE_TOPIC", "").strip()
        if not topic:
            topic = broker_config.mqtt_topic_template.format(device_id="+")

        registry = load_registry(registry_path)
        engine = SecurityEngine(registry, SecurityEventLogger(log_path))
        subscriber = MqttSecuritySubscriber(
            engine=engine,
            host=broker_config.mqtt_host,
            port=broker_config.mqtt_port,
            topic=topic,
            username=broker_config.mqtt_username,
            password=broker_config.mqtt_password,
        )
        subscriber.start()

        cloud_publisher = None
        cloud_enabled = os.getenv("THINGSBOARD_ENABLED", "false").strip().lower() in {
            "true", "1", "yes"
        }
        if cloud_enabled:
            try:
                cloud_publisher = ThingsBoardMqttPublisher(
                    ThingsBoardSettings.from_environment()
                )
                cloud_publisher.start()
                engine.cloud_publisher = cloud_publisher
            except Exception as exc:
                # Cloud setup must never prevent local monitoring from starting.
                print(f"ThingsBoard unavailable; local monitoring continues: {exc}", flush=True)
        else:
            print("ThingsBoard publishing disabled; local monitoring is active.", flush=True)

        print("Press Ctrl+C to stop the security engine.", flush=True)
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nShutdown requested.")
    except (OSError, RuntimeError, TimeoutError, ValueError, ImportError) as exc:
        print(f"Security engine startup error: {exc}", file=sys.stderr)
        return 1
    finally:
        if "cloud_publisher" in locals() and cloud_publisher is not None:
            try:
                cloud_publisher.stop()
            except Exception as exc:
                print(f"ThingsBoard shutdown warning: {exc}", flush=True)
        if "subscriber" in locals():
            try:
                subscriber.stop()
            except Exception as exc:
                print(f"Local MQTT shutdown warning: {exc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
