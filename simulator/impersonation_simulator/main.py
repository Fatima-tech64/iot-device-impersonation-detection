"""MQTT command-line runner for safe identity-impersonation scenarios."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import uuid

from dotenv import load_dotenv

from simulator.device_simulator.config import load_config
from .scenarios import SCENARIOS, ScenarioGenerator


def _optional_float(value: str | None) -> float | None:
    return None if value is None or value == "" else float(value)


def _optional_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("motion must be true or false")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Publish clearly labeled safe IoT impersonation demonstration telemetry."
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default=os.getenv("IMPSIM_SCENARIO", "IMPERSONATION").upper(),
        help="predefined telemetry scenario (default: IMPERSONATION)",
    )
    parser.add_argument(
        "--device-id",
        default=os.getenv("IMPSIM_CLAIMED_DEVICE_ID", os.getenv("SIM_DEVICE_ID", "IOT-001")),
        help="registered device ID to claim in simulated telemetry",
    )
    parser.add_argument("--temperature", type=float, default=_optional_float(os.getenv("IMPSIM_TEMPERATURE")))
    parser.add_argument("--humidity", type=float, default=_optional_float(os.getenv("IMPSIM_HUMIDITY")))
    parser.add_argument("--motion", type=_optional_bool, default=_optional_bool(os.getenv("IMPSIM_MOTION")))
    parser.add_argument("--interval", type=float, default=_optional_float(os.getenv("IMPSIM_INTERVAL")), help="publish interval override for CUSTOM; NORMAL/ABNORMAL_SENSOR use SIM_PUBLISH_INTERVAL")
    return parser.parse_args(argv)


class MqttScenarioPublisher:
    """Publish generated telemetry to the same topic pattern as the main simulator."""

    def __init__(self, broker_config, generator: ScenarioGenerator) -> None:
        import paho.mqtt.client as mqtt

        self.generator = generator
        self.topic = broker_config.mqtt_topic_template.format(device_id=generator.device_id)
        client_id = f"impersonation-sim-{uuid.uuid4().hex[:10]}"
        self._connected = threading.Event()
        self._connection_error: str | None = None
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        if broker_config.mqtt_username:
            self._client.username_pw_set(
                broker_config.mqtt_username, broker_config.mqtt_password
            )
        self._client.on_connect = self._on_connect
        self._host = broker_config.mqtt_host
        self._port = broker_config.mqtt_port
        self._client_id = client_id

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            self._connection_error = str(reason_code)
        else:
            self._connected.set()

    def run(self) -> None:
        marker = f"[SAFE SIMULATION][SCENARIO={self.generator.scenario}]"
        print(
            f"{marker} Claiming device_id={self.generator.device_id}; "
            "no real attack techniques are used."
        )
        print(f"{marker} Connecting to {self._host}:{self._port}; topic='{self.topic}'.")
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.loop_start()
        try:
            if not self._connected.wait(timeout=10):
                detail = f" ({self._connection_error})" if self._connection_error else ""
                raise TimeoutError(f"Could not connect to MQTT broker within 10 seconds{detail}")
            print(
                f"{marker} Connected as separate MQTT client '{self._client_id}'. "
                f"Publishing every {self.generator.interval:g}s."
            )
            while True:
                payload = self.generator.next_payload()
                result = self._client.publish(
                    self.topic, json.dumps(payload, separators=(",", ":")), qos=1
                )
                result.wait_for_publish(timeout=5)
                if not result.is_published():
                    raise RuntimeError("MQTT publish did not complete")
                print(f"{marker} Published to {self.topic}: {json.dumps(payload)}", flush=True)
                threading.Event().wait(self.generator.interval)
        finally:
            self._client.disconnect()
            self._client.loop_stop()
            print(f"{marker} Simulator stopped; MQTT connection closed.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        broker_config = load_config()
        generator = ScenarioGenerator(
            args.scenario,
            args.device_id,
            temperature=args.temperature,
            humidity=args.humidity,
            motion=args.motion,
            interval=(args.interval if args.scenario == "CUSTOM" else broker_config.publish_interval if args.scenario in {"NORMAL", "ABNORMAL_SENSOR"} else None),
        )
        MqttScenarioPublisher(broker_config, generator).run()
    except KeyboardInterrupt:
        print("\n[SAFE SIMULATION] Shutdown requested.")
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        print(f"[SAFE SIMULATION] Simulator error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

