"""Tests for environmental data fetch helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fetchers import (  # noqa: E402
    KP_COLUMNS,
    _daily_kp,
    _fetch_kp_json,
    _parse_kp_bulk,
    fetch_kp_index,
)


class KpFetcherTests(unittest.TestCase):
    def test_bulk_parser_uses_decimal_values_and_utc_timestamps(self):
        text = "\n".join(
            [
                "# GFZ data",
                "2026 01 01 0 0.5 1352 10 3.333 2.667 2.333 2.667 3.333 2.667 3.333 3.333",
            ]
        )

        parsed = _parse_kp_bulk(text)

        self.assertEqual(len(parsed), 8)
        self.assertEqual(parsed.loc[0, "Kp"], 3.333)
        self.assertEqual(parsed.loc[1, "datetime"], pd.Timestamp("2026-01-01 03:00"))

    def test_daily_output_counts_all_missing_days_as_incomplete(self):
        readings = pd.DataFrame(
            {
                "datetime": pd.date_range("2026-01-01", periods=8, freq="3h"),
                "Kp": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            }
        )

        daily = _daily_kp(readings, "2026-01-01", "2026-01-02")

        self.assertEqual(list(daily.columns), KP_COLUMNS)
        self.assertEqual(daily.loc["2026-01-01", "Kp_n"], 8)
        self.assertEqual(daily.loc["2026-01-01", "Kp_daily_sum"], 36.0)
        self.assertEqual(daily.loc["2026-01-02", "Kp_n"], 0)
        self.assertTrue(pd.isna(daily.loc["2026-01-02", "Kp_daily_max"]))
        self.assertTrue(pd.isna(daily.loc["2026-01-02", "Kp_daily_sum"]))

    def test_bulk_fetch_reports_completely_missing_days_as_incomplete(self):
        response = type(
            "Response",
            (),
            {
                "text": "\n".join(
                    [
                        "2026 01 01 0 0.5 1352 10 -1 -1 -1 -1 -1 -1 -1 -1",
                        "2026 01 02 1 1.5 1352 11 1 2 3 4 5 6 7 8",
                    ]
                )
            },
        )()

        with patch("fetchers._get", return_value=response):
            daily = fetch_kp_index("2026-01-01", "2026-01-02")

        self.assertEqual(daily.loc["2026-01-01", "Kp_n"], 0)
        self.assertEqual(daily.loc["2026-01-02", "Kp_n"], 8)

    def test_json_timestamps_are_normalized_to_naive_utc(self):
        response = type(
            "Response",
            (),
            {
                "json": lambda self: {
                    "datetime": ["2026-01-01T21:00:00Z", "2026-01-02T00:00:00Z"],
                    "Kp": [2.0, 3.0],
                }
            },
        )()

        with patch("fetchers._get", return_value=response):
            fetched = _fetch_kp_json("2026-01-01", "2026-01-02")

        self.assertEqual(
            list(fetched["datetime"]),
            [pd.Timestamp("2026-01-01 21:00"), pd.Timestamp("2026-01-02 00:00")],
        )


if __name__ == "__main__":
    unittest.main()
