"""MQTT publishing loop for the simulated device."""

from __future__ import annotations

import json
import threading

from .config import SimulatorConfig
from .payload import build_payload
from .sensors import NormalSensorSimulator


class DeviceSimulator:
    """Publish sensor snapshots for one configured device identity."""

    def __init__(
        self,
        config: SimulatorConfig,
        sensors: NormalSensorSimulator | None = None,
    ) -> None:
        # Import the transport dependency only when a real MQTT simulator is started.
        import paho.mqtt.client as mqtt

        self.config = config
        self.sensors = sensors or NormalSensorSimulator()
        self._connected = threading.Event()
        self._connection_error: str | None = None
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            protocol=mqtt.MQTTv311,
        )
        if config.mqtt_username:
            self._client.username_pw_set(config.mqtt_username, config.mqtt_password)
        self._client.on_connect = self._on_connect

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            self._connection_error = str(reason_code)
        else:
            self._connected.set()

    def build_payload(self) -> dict[str, str | float | bool]:
        """Take sensor readings and build the documented JSON message."""
        return build_payload(self.config, self.sensors)

    def run(self) -> None:
        """Connect and publish until interrupted, then disconnect cleanly."""
        print(
            f"Connecting {self.config.client_id} to "
            f"{self.config.mqtt_host}:{self.config.mqtt_port}..."
        )
        self._client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=60)
        self._client.loop_start()
        try:
            if not self._connected.wait(timeout=10):
                detail = f" ({self._connection_error})" if self._connection_error else ""
                raise TimeoutError(f"Could not connect to MQTT broker within 10 seconds{detail}")
            print(
                f"Connected. Publishing to '{self.config.topic}' "
                f"every {self.config.publish_interval:g}s."
            )

            while True:
                payload = self.build_payload()
                message = json.dumps(payload, separators=(",", ":"))
                result = self._client.publish(self.config.topic, message, qos=1)
                result.wait_for_publish(timeout=5)
                if not result.is_published():
                    raise RuntimeError("MQTT publish did not complete")
                print(f"Published to {self.config.topic}: {json.dumps(payload)}", flush=True)
                threading.Event().wait(self.config.publish_interval)
        finally:
            self._client.disconnect()
            self._client.loop_stop()
            print("Simulator stopped; MQTT connection closed.")
