"""Local read-only dashboard and safe controls for existing IoT simulators."""

from __future__ import annotations

import atexit
import json
import os
import socket
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
app = Flask(__name__)

_SCENARIOS: dict[str, tuple[str, ...]] = {
    "NORMAL_OPERATION": ("simulator.device_simulator.main",),
    "SIMULATE_IMPERSONATION": (
        "simulator.impersonation_simulator.main",
        "--scenario", "IMPERSONATION", "--device-id", "IOT-001",
    ),
    "SENSOR_ANOMALY": (
        "simulator.impersonation_simulator.main",
        "--scenario", "ABNORMAL_SENSOR", "--device-id", "IOT-001",
    ),
    "TRAFFIC_ANOMALY": (
        "simulator.impersonation_simulator.main",
        "--scenario", "ABNORMAL_FREQUENCY", "--device-id", "IOT-001",
    ),
}
_process_lock = threading.Lock()
_scenario_process: subprocess.Popen[bytes] | None = None
_scenario_name: str | None = None


def _event_log_path() -> Path:
    configured = Path(os.getenv("SECURITY_EVENT_LOG", "logs/security_events.jsonl"))
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


def load_security_events() -> list[dict[str, Any]]:
    """Load valid security events from the shared engine JSONL log, in file order."""
    path = _event_log_path()
    events: list[dict[str, Any]] = []
    with path.open("rb") as event_file:
        for line in event_file:
            try:
                value = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if (
                isinstance(value, dict)
                and isinstance(value.get("classification"), str)
                and isinstance(value.get("risk_score"), (int, float))
                and isinstance(value.get("timestamp"), str)
            ):
                events.append(value)
    return events


def _timestamp_is_recent(value: Any, seconds: int = 20) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        return False
    age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= seconds


def _broker_status() -> dict[str, str]:
    host = os.getenv("MQTT_HOST", "localhost").strip() or "localhost"
    try:
        port = int(os.getenv("MQTT_PORT", "1883"))
        with socket.create_connection((host, port), timeout=0.5):
            # TCP reachability is observable here; MQTT protocol/auth status is
            # not, so avoid labelling this as an authenticated MQTT connection.
            return {"state": "REACHABLE", "detail": f"TCP {host}:{port} reachable"}
    except (OSError, ValueError) as exc:
        return {"state": "UNAVAILABLE", "detail": f"Broker not reachable: {exc}"}


def _thingsboard_status() -> dict[str, str]:
    enabled = os.getenv("THINGSBOARD_ENABLED", "false").strip().lower() in {
        "true", "1", "yes"
    }
    if not enabled:
        return {"state": "DISABLED", "detail": "Cloud publishing is disabled in configuration"}
    host = os.getenv("THINGSBOARD_HOST", "").strip()
    token_present = bool(os.getenv("THINGSBOARD_ACCESS_TOKEN", "").strip())
    if host and token_present:
        return {
            "state": "CONFIGURED",
            "detail": "Enabled; live connection state is only reported by the security-engine process",
        }
    return {"state": "INCOMPLETE", "detail": "Enabled, but host or access token is not configured"}


def _scenario_state() -> dict[str, Any]:
    with _process_lock:
        running = _scenario_process is not None and _scenario_process.poll() is None
        return {
            "running": running,
            "scenario": _scenario_name if running else None,
        }


def _stop_scenario_process() -> None:
    global _scenario_process, _scenario_name
    with _process_lock:
        process = _scenario_process
        _scenario_process = None
        _scenario_name = None
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


atexit.register(_stop_scenario_process)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    try:
        events = load_security_events()
    except OSError as exc:
        return jsonify({"error": f"Security event log unavailable: {exc}", "state": "LOG_UNAVAILABLE"}), 503
    latest = events[-1] if events else None
    if latest is None:
        return jsonify({"event": None, "state": "WAITING_FOR_TELEMETRY"})
    # Return the exact latest engine event as recorded. Its age does not affect
    # whether it is returned or rendered as the current known security state.
    return jsonify(latest)


@app.get("/api/events")
def api_events():
    try:
        limit = int(request.args.get("limit", "30"))
    except ValueError:
        limit = 30
    limit = max(1, min(limit, 30))
    try:
        events = load_security_events()
    except OSError as exc:
        return jsonify({"error": f"Security event log unavailable: {exc}", "state": "LOG_UNAVAILABLE"}), 503
    return jsonify({"events": list(reversed(events[-limit:]))})


@app.get("/api/health")
def api_health():
    """Expose local service observations separately from the exact event API."""
    try:
        events = load_security_events()
    except OSError as exc:
        return jsonify({"error": f"Security event log unavailable: {exc}", "state": "LOG_UNAVAILABLE"}), 503
    latest = events[-1] if events else None
    event_is_fresh = bool(latest and _timestamp_is_recent(latest.get("timestamp")))
    return jsonify({
        "mqtt_broker": _broker_status(),
        "security_engine": {
            "state": "RECEIVING" if event_is_fresh else "WAITING",
            "detail": "Recent security event received" if event_is_fresh else "Waiting for recent telemetry events",
        },
        "thingsboard": _thingsboard_status(),
        "last_event_recent": event_is_fresh,
        "simulator": _scenario_state(),
    })


@app.post("/api/scenarios/<scenario>")
def start_scenario(scenario: str):
    global _scenario_process, _scenario_name
    scenario = scenario.upper()
    command = _SCENARIOS.get(scenario)
    if command is None:
        return jsonify({"error": "Unknown scenario"}), 404

    _stop_scenario_process()
    log_path = PROJECT_ROOT / "logs" / "frontend_simulator.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("ab") as simulator_log:
            process = subprocess.Popen(
                [sys.executable, "-m", *command],
                cwd=PROJECT_ROOT,
                stdout=simulator_log,
                stderr=subprocess.STDOUT,
            )
    except OSError as exc:
        return jsonify({"error": f"Could not start existing simulator: {exc}"}), 500

    with _process_lock:
        _scenario_process = process
        _scenario_name = scenario
    return jsonify({
        "started": True,
        "scenario": scenario,
        "pid": process.pid,
        "log": "logs/frontend_simulator.log",
        "note": "This starts the existing simulator module; detection remains in the security engine.",
    }), 202


@app.post("/api/scenarios/stop")
def stop_scenario():
    _stop_scenario_process()
    return jsonify({"stopped": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
