"""Rule-based detection of possible IoT device impersonation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .behaviour import BehaviorVerifier
from .device_registry import DeviceRegistry
from .risk_scoring import RiskScorer, RiskWeights


_BEHAVIOUR_CHECKS = (
    ("temperature_valid", "Temperature outside the registered range"),
    ("humidity_valid", "Humidity outside the registered range"),
    ("message_rate_valid", "Abnormal message frequency or timestamp"),
    ("motion_valid", "Motion does not match the registered behaviour"),
)


@dataclass(frozen=True)
class DetectionThresholds:
    """Classification thresholds; risk is 100 minus behaviour_score."""

    possible_impersonation_risk: int = 10
    high_risk_score: int = 40
    high_risk_anomaly_count: int = 3

    def __post_init__(self) -> None:
        values = (self.possible_impersonation_risk, self.high_risk_score, self.high_risk_anomaly_count)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("Detection thresholds must be integers")
        if not 0 <= self.possible_impersonation_risk <= 100:
            raise ValueError("possible_impersonation_risk must be between 0 and 100")
        if not 0 <= self.high_risk_score <= 100:
            raise ValueError("high_risk_score must be between 0 and 100")
        if self.high_risk_score < self.possible_impersonation_risk:
            raise ValueError("high_risk_score must be at least possible_impersonation_risk")
        if not 2 <= self.high_risk_anomaly_count <= len(_BEHAVIOUR_CHECKS):
            raise ValueError("high_risk_anomaly_count must be between 2 and 4")


class ImpersonationDetector:
    """Assess each message and emit a structured, explainable security event.

    Risk is a transparent inverse of the behaviour score. Unknown device IDs
    receive risk 100 and are classified separately. For registered devices,
    possible impersonation starts at the configured risk threshold. High risk
    requires both the configured risk score and a configured count of failed
    behavioural checks. These are indicators for review, not proof of intent.
    """

    def __init__(
        self,
        registry: DeviceRegistry,
        thresholds: DetectionThresholds | None = None,
        behaviour_verifier: BehaviorVerifier | None = None,
        risk_weights: RiskWeights | None = None,
    ) -> None:
        self.registry = registry
        self.thresholds = thresholds or DetectionThresholds()
        self.behaviour_verifier = behaviour_verifier or BehaviorVerifier(registry)
        self.risk_scorer = RiskScorer(risk_weights)

    def detect(self, telemetry: dict[str, Any]) -> dict[str, Any]:
        """Return one security event for the provided telemetry message."""
        device_id = telemetry.get("device_id") if isinstance(telemetry, dict) else None
        device_id = device_id if isinstance(device_id, str) else ""
        profile = self.registry.get_profile(device_id) if device_id else None
        verification = self.behaviour_verifier.verify(telemetry)
        risk_assessment = self.risk_scorer.score(
            verification, profile_available=profile is not None
        )
        risk_score = risk_assessment["risk_score"]
        reasons = list(risk_assessment["reasons"])

        if profile is None:
            classification = "UNKNOWN_DEVICE"
        else:
            failed_checks = [
                field for field, _reason in _BEHAVIOUR_CHECKS if not verification[field]
            ]

            if not reasons:
                classification = "TRUSTED"
            elif (
                risk_score >= self.thresholds.high_risk_score
                and len(failed_checks) >= self.thresholds.high_risk_anomaly_count
            ):
                classification = "HIGH_RISK_IMPERSONATION"
            elif risk_score >= self.thresholds.possible_impersonation_risk:
                classification = "POSSIBLE_IMPERSONATION"
            else:
                # Covers a trusted ID with a single issue when a caller raises
                # the possible-impersonation threshold above its risk score.
                classification = "SUSPICIOUS_BEHAVIOUR"

        return {
            "device_id": device_id,
                "classification": classification,
                "risk_score": risk_score,
                "risk_level": risk_assessment["risk_level"],
                "factors": risk_assessment["factors"],
                "reasons": reasons,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "behaviour_checks": verification,
        }
