"""Run deterministic, safe security scenarios from the project root.

This controller evaluates synthetic telemetry locally through the same trusted
registry and rule-based detector used by the security engine. It does not
perform attacks or require an MQTT broker; use the existing simulators and
MQTT security engine for a live end-to-end demonstration.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.security_engine.device_registry import load_registry
from src.security_engine.impersonation_detector import (
    DetectionThresholds,
    ImpersonationDetector,
)


SCENARIOS = (
    "NORMAL_OPERATION",
    "UNKNOWN_DEVICE",
    "SENSOR_ANOMALY",
    "TRAFFIC_ANOMALY",
    "DEVICE_IMPERSONATION",
)

# Scenario outcomes are easier to explain in a college demo with these explicit
# boundaries: ordinary single anomalies are suspicious; combined mismatches
# are possible/high-risk impersonation indicators. Risk points stay unchanged.
DEMO_THRESHOLDS = DetectionThresholds(
    possible_impersonation_risk=40,
    high_risk_score=50,
    high_risk_anomaly_count=3,
)


def build_scenario(scenario: str, *, now: datetime | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Return a plain-language behaviour description and synthetic telemetry."""
    scenario = scenario.upper()
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of: {', '.join(SCENARIOS)}")
    start = now or datetime.now(timezone.utc)
    if start.tzinfo is None:
        raise ValueError("now must include a timezone")

    device_id = "IOT-001"
    interval = 5.0
    temperature, humidity, motion = 27.5, 58.0, False
    description = "Registered identity, in-range room readings, 5-second interval"

    if scenario == "UNKNOWN_DEVICE":
        device_id = "IOT-999"
        description = "Unregistered identity with otherwise ordinary sensor readings"
    elif scenario == "SENSOR_ANOMALY":
        temperature, humidity = 42.0, 95.0
        description = "Registered identity, temperature 42°C and humidity 95%"
    elif scenario == "TRAFFIC_ANOMALY":
        interval = 0.5
        description = "Registered identity, normal sensor readings, 0.5-second interval"
    elif scenario == "DEVICE_IMPERSONATION":
        temperature, humidity, motion, interval = 42.0, 95.0, True, 0.5
        description = (
            "Claims IOT-001 with out-of-range temperature/humidity and rapid messages"
        )

    messages: list[dict[str, Any]] = []
    # The second message gives the verifier a real interval to assess. Other
    # scenarios use the registered 5-second interval; anomaly intervals are
    # intentionally synthetic and do not sleep or generate network traffic.
    for index in range(2):
        messages.append(
            {
                "device_id": device_id,
                "device_type": "environment_sensor",
                "temperature": temperature,
                "humidity": humidity,
                "motion": motion,
                "timestamp": (start + timedelta(seconds=interval * index)).isoformat(),
            }
        )
    return description, messages


def run_scenario(scenario: str, registry_path: str | Path) -> dict[str, Any]:
    """Evaluate a scenario and print its requested demonstration summary."""
    description, messages = build_scenario(scenario)
    registry = load_registry(registry_path)
    detector = ImpersonationDetector(registry, thresholds=DEMO_THRESHOLDS)
    event: dict[str, Any] = {}
    for message in messages:
        event = detector.detect(message)
    # Match the public classification used by SecurityEngine.process_message.
    if event["classification"] == "SUSPICIOUS_BEHAVIOUR":
        event["classification"] = "SUSPICIOUS"

    print(f"Scenario: {scenario.upper()}")
    print(f"Simulated behaviour: {description}")
    print(f"Detection result: {event['classification']}")
    print(f"Risk score: {event['risk_score']}/100 ({event['risk_level']})")
    reasons = event.get("reasons") or ["No rule-based deviations detected"]
    print("Reason for detection:")
    for reason in reasons:
        print(f"  - {reason}")
    return event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a safe, local IoT security demonstration scenario."
    )
    parser.add_argument(
        "scenario",
        choices=SCENARIOS,
        help="predefined scenario to evaluate",
    )
    parser.add_argument(
        "--registry",
        default="config/device_registry.json",
        help="registered-device JSON path (default: config/device_registry.json)",
    )
    args = parser.parse_args(argv)
    try:
        run_scenario(args.scenario, args.registry)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
