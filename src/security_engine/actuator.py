"""Hardware-independent actuator commands for the security engine."""

from __future__ import annotations

from typing import Any, Protocol


class Actuator(Protocol):
    """Interface for an actuator adapter (console simulation or ESP32 bridge)."""

    def respond(self, classification: str) -> dict[str, Any]:
        """Apply a decision and return a serializable description of the action."""
        ...


class SimulatedActuator:
    """Represent LED and buzzer actions in the console without hardware access."""

    BUZZER_PULSE_MS = 500

    _RESPONSES = {
        "TRUSTED": ("GREEN", "OFF", 0),
        "SUSPICIOUS": ("YELLOW", "OFF", 0),
        "UNKNOWN_DEVICE": ("YELLOW", "OFF", 0),
        "POSSIBLE_IMPERSONATION": ("RED", "PULSE", BUZZER_PULSE_MS),
        "HIGH_RISK_IMPERSONATION": ("RED", "ON", None),
    }

    def respond(self, classification: str) -> dict[str, Any]:
        """Translate a security classification into a simulated actuator state."""
        led_color, buzzer_state, duration_ms = self._RESPONSES.get(
            classification, self._RESPONSES["SUSPICIOUS"]
        )
        response = {
            "backend": "console_simulation",
            "led": {"state": "ON", "color": led_color},
            "buzzer": {"state": buzzer_state, "duration_ms": duration_ms},
        }
        duration_text = f" ({duration_ms} ms)" if duration_ms is not None else ""
        print(
            f"SIMULATED ACTUATORS: LED={led_color}, "
            f"BUZZER={buzzer_state}{duration_text} [{classification}]",
            flush=True,
        )
        return response
