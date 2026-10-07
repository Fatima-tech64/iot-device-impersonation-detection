"""Pipeline incoming telemetry through validation, detection, and event logging."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .actuator import Actuator, SimulatedActuator
from .device_registry import DeviceRegistry
from .impersonation_detector import ImpersonationDetector
from .message_schema import PayloadValidationError, parse_and_validate_payload


class SecurityEventLogger:
    """Append one JSON security event per line to a local log file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def write(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as event_file:
                event_file.write(line + "\n")


class SecurityEngine:
    """Run the complete local security decision pipeline for MQTT messages."""

    def __init__(
        self,
        registry: DeviceRegistry,
        event_logger: SecurityEventLogger,
        detector: ImpersonationDetector | None = None,
        actuator: Actuator | None = None,
        cloud_publisher: Any | None = None,
    ) -> None:
        self.registry = registry
        self.event_logger = event_logger
        self.detector = detector or ImpersonationDetector(registry)
        self.actuator = actuator or SimulatedActuator()
        self.cloud_publisher = cloud_publisher

    def process_message(self, topic: str, payload: bytes | str) -> dict[str, Any]:
        """Process one MQTT payload; malformed input becomes a logged event."""
        try:
            telemetry = parse_and_validate_payload(payload)
        except PayloadValidationError as exc:
            event = self._invalid_payload_event(topic, payload, str(exc))
        else:
            event = self.detector.detect(telemetry)
            event["telemetry"] = {
                key: telemetry[key]
                for key in ("temperature", "humidity", "motion", "timestamp")
            }
            if event["classification"] == "SUSPICIOUS_BEHAVIOUR":
                event["classification"] = "SUSPICIOUS"
            event["event_type"] = "TELEMETRY_SECURITY_ASSESSMENT"
            event["topic"] = topic

        try:
            event["actuator_response"] = self.actuator.respond(event["classification"])
        except Exception as exc:
            event["actuator_response"] = {"backend": "unavailable", "error": str(exc)}
            print(f"Actuator response failed: {exc}", flush=True)

        self._emit(event)
        if self.cloud_publisher is not None:
            try:
                self.cloud_publisher.publish_event(event)
            except Exception as exc:
                # Cloud errors are isolated from local detection, actuation, and logging.
                print(f"Cloud publish failed; local event is retained: {exc}", flush=True)
        return event

    def _invalid_payload_event(
        self, topic: str, payload: bytes | str, reason: str
    ) -> dict[str, Any]:
        device_id = ""
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")
        if isinstance(payload, str):
            try:
                candidate = json.loads(payload)
                if isinstance(candidate, dict) and isinstance(candidate.get("device_id"), str):
                    device_id = candidate["device_id"]
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            "event_type": "INVALID_TELEMETRY",
            "device_id": device_id,
            "classification": "SUSPICIOUS",
            "risk_score": 100,
            "risk_level": "CRITICAL",
            "factors": {"payload_validation": 100},
            "reasons": [f"Telemetry payload rejected: {reason}"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
        }

    def _emit(self, event: dict[str, Any]) -> None:
        print("\n=== IoT SECURITY EVENT ===", flush=True)
        print(json.dumps(event, indent=2, ensure_ascii=False), flush=True)
        try:
            self.event_logger.write(event)
        except OSError as exc:
            # A log-path problem should be visible but must not kill MQTT intake.
            print(f"Security event log write failed: {exc}", flush=True)

