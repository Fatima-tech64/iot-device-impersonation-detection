"""MQTT subscriber that reconnects and feeds messages to SecurityEngine."""

from __future__ import annotations

from .engine import SecurityEngine


class MqttSecuritySubscriber:
    """Subscribe to a telemetry topic and safely process each delivered message."""

    def __init__(
        self,
        engine: SecurityEngine,
        host: str,
        port: int,
        topic: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        import paho.mqtt.client as mqtt

        self.engine = engine
        self.topic = topic
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="iot-security-engine",
            protocol=mqtt.MQTTv311,
        )
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        if username:
            self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._host = host
        self._port = port

    def start(self) -> None:
        print(
            f"Starting security engine MQTT subscriber at "
            f"{self._host}:{self._port}, topic '{self.topic}'...",
            flush=True,
        )
        self._client.connect_async(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
        print("Security engine MQTT subscriber stopped.", flush=True)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            print(f"MQTT connection failed: {reason_code}", flush=True)
            return
        result, _mid = client.subscribe(self.topic, qos=1)
        if result != 0:
            print(f"MQTT subscription failed for '{self.topic}' (rc={result})", flush=True)
        else:
            print(f"Connected and subscribed to '{self.topic}'.", flush=True)

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ) -> None:
        if reason_code.is_failure:
            print(
                f"MQTT disconnected unexpectedly ({reason_code}); reconnect will be attempted.",
                flush=True,
            )
        else:
            print("MQTT disconnected.", flush=True)

    def _on_message(self, client, userdata, message) -> None:
        try:
            self.engine.process_message(message.topic, message.payload)
        except Exception as exc:  # isolate an unexpected per-message error
            print(f"Message processing error; subscriber remains active: {exc}", flush=True)
