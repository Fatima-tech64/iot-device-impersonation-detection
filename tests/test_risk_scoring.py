"""Unit tests for weighted risk contributions and score bands."""

import unittest

from src.security_engine.risk_scoring import RiskScorer, RiskWeights, risk_level


NORMAL_CHECKS = {
    "identity_valid": True,
    "temperature_valid": True,
    "humidity_valid": True,
    "message_rate_valid": True,
    "motion_valid": True,
}


class RiskScoringTests(unittest.TestCase):
    def test_normal_checks_have_zero_low_risk(self):
        result = RiskScorer().score(NORMAL_CHECKS)
        self.assertEqual(result["risk_score"], 0)
        self.assertEqual(result["risk_level"], "LOW")
        self.assertEqual(sum(result["factors"].values()), 0)
        self.assertEqual(result["reasons"], [])

    def test_each_failed_check_contributes_its_configured_weight(self):
        weights = RiskWeights(identity=10, temperature=30, humidity=20, message_frequency=25, motion=15)
        checks = dict(NORMAL_CHECKS)
        checks.update(
            identity_valid=False,
            temperature_valid=False,
            message_rate_valid=False,
        )
        result = RiskScorer(weights).score(checks)
        self.assertEqual(result["risk_score"], 65)
        self.assertEqual(result["risk_level"], "HIGH")
        self.assertEqual(
            result["factors"],
            {"identity": 10, "temperature": 30, "humidity": 0, "message_frequency": 25, "motion": 0},
        )
        self.assertEqual(len(result["reasons"]), 3)

    def test_unknown_device_only_gets_identity_contribution(self):
        checks = {key: False for key in NORMAL_CHECKS}
        result = RiskScorer().score(checks, profile_available=False)
        self.assertEqual(result["risk_score"], 40)
        self.assertEqual(result["risk_level"], "MEDIUM")
        self.assertEqual(
            result["factors"],
            {"identity": 40, "temperature": 0, "humidity": 0, "message_frequency": 0, "motion": 0},
        )

    def test_risk_level_boundaries(self):
        self.assertEqual([risk_level(score) for score in (0, 29, 30, 59, 60, 79, 80, 100)],
                         ["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "CRITICAL", "CRITICAL"])

    def test_weights_must_be_nonnegative_and_total_100(self):
        with self.assertRaises(ValueError):
            RiskWeights(identity=40, temperature=20, humidity=20, message_frequency=20, motion=20)
        with self.assertRaises(ValueError):
            RiskWeights(identity=-1, temperature=16, humidity=15, message_frequency=20, motion=50)

    def test_invalid_risk_level_input_is_rejected(self):
        with self.assertRaises(ValueError):
            risk_level(101)


if __name__ == "__main__":
    unittest.main()
