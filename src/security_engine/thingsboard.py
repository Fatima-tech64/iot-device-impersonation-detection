"""Optional ThingsBoard Cloud integration over its standard MQTT device API."""

from __future__ import annotations

import json
import os
import queue
import uuid
from dataclasses import dataclass
from typing import Any


TELEMETRY_TOPIC = "v1/devices/me/telemetry"


@dataclass(frozen=True)
class ThingsBoardSettings:
    host: str
    access_token: str
    port: int = 8883
    use_tls: bool = True
    telemetry_topic: str = TELEMETRY_TOPIC
    qos: int = 1
    keepalive: int = 60

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("THINGSBOARD_HOST must be set when cloud integration is enabled")
        if not self.access_token.strip():
            raise ValueError("THINGSBOARD_ACCESS_TOKEN must be set when cloud integration is enabled")
        if not 1 <= self.port <= 65535:
            raise ValueError("THINGSBOARD_PORT must be between 1 and 65535")
        if self.qos not in (0, 1, 2):
            raise ValueError("THINGSBOARD_QOS must be 0, 1, or 2")
        if not self.telemetry_topic.strip():
            raise ValueError("THINGSBOARD_TELEMETRY_TOPIC must not be empty")

    @classmethod
    def from_environment(cls) -> "ThingsBoardSettings":
        """Read cloud connection settings without embedding credentials in code."""
        try:
            port = int(os.getenv("THINGSBOARD_PORT", "8883"))
            qos = int(os.getenv("THINGSBOARD_QOS", "1"))
            keepalive = int(os.getenv("THINGSBOARD_KEEPALIVE", "60"))
        except ValueError as exc:
            raise ValueError("ThingsBoard port, QoS, and keepalive must be integers") from exc
        tls_value = os.getenv("THINGSBOARD_USE_TLS", "true").strip().lower()
        if tls_value not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("THINGSBOARD_USE_TLS must be true or false")
        return cls(
            host=os.getenv("THINGSBOARD_HOST", "").strip(),
            access_token=os.getenv("THINGSBOARD_ACCESS_TOKEN", "").strip(),
            port=port,
            use_tls=tls_value in {"true", "1", "yes"},
            telemetry_topic=os.getenv("THINGSBOARD_TELEMETRY_TOPIC", TELEMETRY_TOPIC).strip(),
            qos=qos,
            keepalive=keepalive,
        )


def build_cloud_telemetry(event: dict[str, Any]) -> dict[str, Any]:
    """Map a local security event to ThingsBoard time-series keys."""
    telemetry = event.get("telemetry", {})
    checks = event.get("behaviour_checks", {})
    classification = event.get("classification", "SUSPICIOUS")
    payload: dict[str, Any] = {
        "device_id": event.get("device_id", ""),
        "risk_score": event.get("risk_score", 100),
        "risk_level": event.get("risk_level", "CRITICAL"),
        "device_status": classification,
        "impersonation_detected": classification in {
            "POSSIBLE_IMPERSONATION", "HIGH_RISK_IMPERSONATION"
        },
        # Unit is messages per second (Hz). First reading uses the registered
        # expected rate; subsequent readings use the measured timestamp delta.
        "message_frequency": checks.get("message_frequency", 0.0),
    }
    for field in ("temperature", "humidity", "motion"):
        if field in telemetry:
            payload[field] = telemetry[field]

    if classification != "TRUSTED":
        payload["security_event"] = classification
        payload["security_reasons"] = "; ".join(event.get("reasons", []))
    return payload


class ThingsBoardMqttPublisher:
    """Non-blocking cloud publisher; local processing never depends on it."""

    def __init__(self, settings: ThingsBoardSettings) -> None:
        import paho.mqtt.client as mqtt

        self.settings = settings
        self._active = False
        self._pending: queue.Queue[str] = queue.Queue(maxsize=1000)
        client_id = f"security-engine-tb-{uuid.uuid4().hex[:10]}"
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        self._client.username_pw_set(settings.access_token)
        if settings.use_tls:
            # Uses the system trust store to verify the ThingsBoard Cloud TLS certificate.
            self._client.tls_set()
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._host = settings.host
        self._port = settings.port

    def start(self) -> None:
        """Start a reconnecting MQTT network loop without blocking local intake."""
        self._active = True
        print(
            f"Starting ThingsBoard MQTT publisher at {self._host}:{self._port} "
            f"(TLS={self.settings.use_tls})...",
            flush=True,
        )
        self._client.connect_async(self._host, self._port, keepalive=self.settings.keepalive)
        self._client.loop_start()

    def publish_event(self, event: dict[str, Any]) -> bool:
        """Publish available telemetry and security event fields if connected."""
        message = json.dumps(build_cloud_telemetry(event), separators=(",", ":"))
        if not self._active or not self._client.is_connected():
            return self._queue_for_cloud(message)
        return self._send(message, requeue_on_error=True)

    def stop(self) -> None:
        """Stop the cloud MQTT client gracefully."""
        self._active = False
        self._client.disconnect()
        self._client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            print(f"ThingsBoard MQTT connection failed: {reason_code}", flush=True)
            return
        print("Connected to ThingsBoard MQTT.", flush=True)
        while True:
            try:
                message = self._pending.get_nowait()
            except queue.Empty:
                break
            if not self._send(message, requeue_on_error=True):
                break

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ) -> None:
        if reason_code.is_failure and self._active:
            print(
                f"ThingsBoard disconnected ({reason_code}); reconnect will be attempted.",
                flush=True,
            )

    def _queue_for_cloud(self, message: str) -> bool:
        try:
            self._pending.put_nowait(message)
        except queue.Full:
            print(
                "ThingsBoard is unavailable and its pending queue is full; "
                "the event remains in the local log.",
                flush=True,
            )
            return False
        print(
            "ThingsBoard is unavailable; event queued for retry and remains in the local log.",
            flush=True,
        )
        return True

    def _send(self, message: str, *, requeue_on_error: bool) -> bool:
        try:
            result = self._client.publish(
                self.settings.telemetry_topic, message, qos=self.settings.qos
            )
        except Exception as exc:
            print(f"ThingsBoard publish failed; local event is retained: {exc}", flush=True)
            return self._queue_for_cloud(message) if requeue_on_error else False
        if result.rc != 0:
            print(
                f"ThingsBoard publish was not queued (rc={result.rc}); "
                "local event is retained.",
                flush=True,
            )
            return self._queue_for_cloud(message) if requeue_on_error else False
        return True
