"""Tests for the standalone Kp export command."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import kp_analysis  # noqa: E402


class KpAnalysisTests(unittest.TestCase):
    def test_exports_kp_data_without_joining_or_scoring(self):
        data = pd.DataFrame(
            {
                "Kp_daily_max": [2.0],
                "Kp_daily_mean": [1.5],
                "Kp_n": [8],
                "Kp_daily_sum": [12.0],
            },
            index=pd.DatetimeIndex(["2026-01-01"], name="date"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "kp.csv"
            with (
                patch.object(kp_analysis, "fetch_kp_index", return_value=data),
                patch.object(kp_analysis, "OUTPUT_KP_CSV", output_path),
            ):
                result = kp_analysis.main()

            exported = pd.read_csv(output_path)

        self.assertEqual(list(result.columns), list(data.columns))
        self.assertEqual(exported.loc[0, "date"], "2026-01-01")
        self.assertNotIn("risk_score", exported.columns)

    def test_does_not_write_all_missing_kp_data(self):
        data = pd.DataFrame(
            {"Kp_daily_max": [float("nan")], "Kp_n": [0]},
            index=pd.DatetimeIndex(["2026-01-01"], name="date"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "kp.csv"
            with (
                patch.object(kp_analysis, "fetch_kp_index", return_value=data),
                patch.object(kp_analysis, "OUTPUT_KP_CSV", output_path),
            ):
                with self.assertRaisesRegex(RuntimeError, "No valid Kp readings"):
                    kp_analysis.main()

            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
