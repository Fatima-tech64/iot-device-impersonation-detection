"""JSON payload parsing and basic telemetry schema validation."""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any


REQUIRED_FIELDS = {
    "device_id",
    "device_type",
    "temperature",
    "humidity",
    "motion",
    "timestamp",
}


class PayloadValidationError(ValueError):
    """Raised when incoming telemetry cannot be safely evaluated."""


def parse_and_validate_payload(payload: bytes | str) -> dict[str, Any]:
    """Decode JSON and validate required fields, types, and basic sensor limits."""
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    except UnicodeDecodeError as exc:
        raise PayloadValidationError("payload is not valid UTF-8") from exc
    try:
        data = json.loads(decoded)
    except (json.JSONDecodeError, TypeError) as exc:
        raise PayloadValidationError("payload is not valid JSON") from exc
    if not isinstance(data, dict):
        raise PayloadValidationError("JSON payload must be an object")

    missing = sorted(REQUIRED_FIELDS - data.keys())
    if missing:
        raise PayloadValidationError(f"missing required fields: {', '.join(missing)}")

    for field in ("device_id", "device_type"):
        if not isinstance(data[field], str) or not data[field].strip():
            raise PayloadValidationError(f"{field} must be a non-empty string")

    for field, minimum, maximum in (
        ("temperature", -40.0, 80.0),
        ("humidity", 0.0, 100.0),
    ):
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PayloadValidationError(f"{field} must be a number")
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise PayloadValidationError(
                f"{field} must be between {minimum:g} and {maximum:g}"
            )

    if not isinstance(data["motion"], bool):
        raise PayloadValidationError("motion must be a boolean")

    timestamp = data["timestamp"]
    if not isinstance(timestamp, str):
        raise PayloadValidationError("timestamp must be an ISO 8601 string")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PayloadValidationError("timestamp must be a valid ISO 8601 value") from exc
    if parsed_timestamp.tzinfo is None:
        raise PayloadValidationError("timestamp must include a timezone")

    return data
