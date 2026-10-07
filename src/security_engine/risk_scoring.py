"""Explainable weighted risk scoring for IoT telemetry checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RiskWeights:
    """Maximum points contributed by each failed check; weights must total 100."""

    identity: int = 40
    temperature: int = 15
    humidity: int = 15
    message_frequency: int = 20
    motion: int = 10

    def __post_init__(self) -> None:
        values = (
            self.identity,
            self.temperature,
            self.humidity,
            self.message_frequency,
            self.motion,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("Risk weights must be non-negative integers")
        if sum(values) != 100:
            raise ValueError("Risk weights must add up to 100")


_FACTOR_RULES = (
    ("temperature", "temperature_valid", "Temperature outside the registered range"),
    ("humidity", "humidity_valid", "Humidity outside the registered range"),
    ("message_frequency", "message_rate_valid", "Abnormal message frequency or timestamp"),
    ("motion", "motion_valid", "Motion does not match the registered behaviour"),
)


class RiskScorer:
    """Turn behaviour verification flags into a weighted 0–100 risk result.

    A failed check contributes its full configured weight. Passing checks
    contribute zero. When a device has no registry profile, only identity is
    scored; profile-dependent sensor checks are unevaluable rather than
    assumed anomalous.
    """

    def __init__(self, weights: RiskWeights | None = None) -> None:
        self.weights = weights or RiskWeights()

    def score(
        self,
        behaviour_checks: dict[str, Any],
        *,
        profile_available: bool = True,
    ) -> dict[str, Any]:
        """Return total score, band, factor points, and human-readable reasons."""
        factors = {
            "identity": 0,
            "temperature": 0,
            "humidity": 0,
            "message_frequency": 0,
            "motion": 0,
        }
        reasons: list[str] = []

        if not behaviour_checks.get("identity_valid", False):
            factors["identity"] = self.weights.identity
            reasons.append("Device identity is unknown or its registered status is not trusted")

        if profile_available:
            for factor, check, reason in _FACTOR_RULES:
                if not behaviour_checks.get(check, False):
                    factors[factor] = getattr(self.weights, factor)
                    reasons.append(reason)

        risk_score = sum(factors.values())
        return {
            "risk_score": risk_score,
            "risk_level": risk_level(risk_score),
            "factors": factors,
            "reasons": reasons,
        }


def risk_level(score: int) -> str:
    """Map an integer score to the documented risk band."""
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("Risk score must be an integer between 0 and 100")
    if score <= 29:
        return "LOW"
    if score <= 59:
        return "MEDIUM"
    if score <= 79:
        return "HIGH"
    return "CRITICAL"
