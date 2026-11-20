"""Tests for the Kp-independent risk score."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from score import (  # noqa: E402
    FEATURE_RANGES,
    RISK_CUTOFFS,
    RISK_WEIGHTS,
    classify_risk_score,
    compute_row_score,
)


class RiskScoreTests(unittest.TestCase):
    def test_weights_are_normalized_and_exclude_kp(self):
        self.assertAlmostEqual(sum(RISK_WEIGHTS.values()), 1.0)
        self.assertNotIn("Kp_daily_max", RISK_WEIGHTS)
        self.assertNotIn("Kp_daily_max", FEATURE_RANGES)

    def test_kp_does_not_change_score(self):
        row = pd.Series(
            {
                "delta_P": -4.0,
                "DTR": 15.0,
                "dew_point_2m_mean": 5.0,
                "pm2_5": 10.0,
                "pm10": 20.0,
                "no2": 15.0,
                "Kp_daily_max": 9.0,
            }
        )
        without_kp = row.drop(labels="Kp_daily_max")

        self.assertAlmostEqual(
            compute_row_score(row, RISK_WEIGHTS, FEATURE_RANGES),
            compute_row_score(without_kp, RISK_WEIGHTS, FEATURE_RANGES),
        )
        self.assertTrue(
            pd.isna(
                compute_row_score(
                    pd.Series({"Kp_daily_max": 9.0}),
                    RISK_WEIGHTS,
                    FEATURE_RANGES,
                )
            )
        )

    def test_tier_cutoffs_match_recalibrated_percentiles(self):
        self.assertEqual(RISK_CUTOFFS, (0.2229342593, 0.3014978395, 0.3772552469))
        self.assertEqual(classify_risk_score(RISK_CUTOFFS[0]), "moderate")
        self.assertEqual(classify_risk_score(RISK_CUTOFFS[1]), "high")
        self.assertEqual(classify_risk_score(RISK_CUTOFFS[2]), "high")
        self.assertEqual(classify_risk_score(float("nan")), "unknown")


if __name__ == "__main__":
    unittest.main()
