"""Tests for standalone daily and monthly HTML risk reports."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from html_report import (  # noqa: E402
    main as html_report_main,
    generate_daily_html_report,
    generate_monthly_html_report,
)
from score import (  # noqa: E402
    FEATURE_RANGES,
    RISK_WEIGHTS,
    classify_risk_score,
    compute_feature_contributions,
    compute_row_score,
)


class _HTMLSmokeParser(HTMLParser):
    pass


def sample_frame() -> pd.DataFrame:
    dates = pd.date_range("2026-07-01", periods=37, freq="D")
    scores = ([0.18, 0.24, 0.33, 0.42] * 10)[:37]
    scores[-2:] = [0.39, 0.35]
    scores[-4] = float("nan")
    frame = pd.DataFrame(
        {
            "temperature_2m_max": [30.0] * 37,
            "DTR": [10.0] * 34 + [14.0, 15.0, 16.0],
            "delta_P": [1.0] * 35 + [-4.0, 2.0],
            "dew_point_2m_mean": [12.0] * 37,
            "pm2_5": [8.0] * 35 + [float("nan"), float("nan")],
            "pm10": [14.0] * 35 + [float("nan"), float("nan")],
            "no2": [18.0] * 35 + [float("nan"), float("nan")],
            "Kp_daily_max": [float("nan")] * 37,
            "pm2_5_roll7d": [8.0] * 37,
            "risk_score": scores,
            "is_forecast": [None] * 35 + [True, True],
        },
        index=dates,
    )
    frame.loc[dates[34], "temperature_2m_max"] = 39.2
    frame["risk_tier"] = frame["risk_score"].map(classify_risk_score)
    return frame


class HTMLReportTests(unittest.TestCase):
    def test_daily_report_contains_expected_sections_and_tiers(self):
        frame = sample_frame()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = generate_daily_html_report(
                frame,
                temp_dir,
                location_label="Springfield <test & place>, Example State, 12345",
                generated_at=datetime(2026, 8, 6, 8, 30),
            )
            html = output.read_text(encoding="utf-8")

        self.assertEqual(
            output.name,
            "kockázati_jelentés_10nap_SPR_2026-08-04.html",
        )
        self.assertIn(
            "copd-vs-weather · Springfield &lt;test &amp; place&gt;, Example State, 12345",
            html,
        )
        self.assertIn('lang="hu"', html)
        self.assertIn("10 napos környezeti kockázati jelentés", html)
        self.assertIn("Rövid összefoglaló", html)
        self.assertIn("Közérzet-emlékeztető", html)
        self.assertIn("forecast-row alert", html)
        self.assertIn("LK hiányzik", html)
        self.assertIn("alsó becslések", html)
        self.assertIn("abszolút hőterhelést nem méri", html)
        self.assertNotIn("GFZ Potsdam Kp", html)
        self.assertIn("Springfield &lt;test &amp; place&gt;", html)
        self.assertEqual(html.count('<tr class="'), 10)
        for tier in ("low", "moderate", "high", "very_high", "unknown"):
            self.assertIn(f"tier-{tier}", html)
        _HTMLSmokeParser().feed(html)

    def test_monthly_report_excludes_forecast_and_contains_trends(self):
        frame = sample_frame()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = generate_monthly_html_report(
                frame,
                temp_dir,
                location_label="Springfield, Example State, 12345",
            )
            html = output.read_text(encoding="utf-8")

        self.assertEqual(
            output.name,
            "kockázati_jelentés_30nap_SPR_2026-08.html",
        )
        self.assertIn("30 napos környezeti kockázati áttekintés", html)
        self.assertIn(
            "copd-vs-weather · Springfield, Example State, 12345 — 30 napos áttekintés",
            html,
        )
        self.assertNotIn("forecast-badge", html.split("<style>", 1)[-1].split("</style>", 1)[-1])
        self.assertIn("Heti bontás", html)
        self.assertIn("Napi kockázati pontszám", html)
        self.assertIn("PM₂,₅ 7 napos gördülő átlag", html)
        self.assertIn("DTR 30 napos trend", html)
        self.assertIn("Kiemelt események", html)
        self.assertIn("driver-pair", html)
        self.assertIn("Mérsékelt+ napok", html)
        _HTMLSmokeParser().feed(html)

    def test_report_rejects_missing_required_columns(self):
        frame = pd.DataFrame({"risk_score": [0.2]}, index=[pd.Timestamp("2026-01-01")])
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "risk_tier"):
                generate_daily_html_report(frame, temp_dir)

    def test_cli_requires_explicit_location_label(self):
        with patch("sys.argv", ["html_report.py", "both"]):
            with self.assertRaises(SystemExit) as error:
                html_report_main()
        self.assertEqual(error.exception.code, 2)

    def test_cli_generates_both_reports_with_supplied_location_label(self):
        frame = sample_frame()
        daily_path = Path("daily.html")
        monthly_path = Path("monthly.html")
        with (
            patch("sys.argv", [
                "html_report.py",
                "both",
                "--location-label",
                "Springfield",
            ]),
            patch("html_report.pd.read_csv", return_value=frame),
            patch(
                "html_report.generate_daily_html_report",
                return_value=daily_path,
            ) as daily_report,
            patch(
                "html_report.generate_monthly_html_report",
                return_value=monthly_path,
            ) as monthly_report,
        ):
            self.assertEqual(html_report_main(), 0)

        daily_report.assert_called_once()
        monthly_report.assert_called_once()
        self.assertEqual(daily_report.call_args.kwargs["location_label"], "Springfield")
        self.assertEqual(monthly_report.call_args.kwargs["location_label"], "Springfield")

    def test_feature_contributions_preserve_score(self):
        row = pd.Series(
            {
                "delta_P": -4.0,
                "DTR": 15.0,
                "dew_point_2m_mean": 5.0,
                "pm2_5": float("nan"),
                "no2": float("nan"),
                "pm10": float("nan"),
                "Kp_daily_max": float("nan"),
            }
        )
        contributions = compute_feature_contributions(row, RISK_WEIGHTS, FEATURE_RANGES)
        score = compute_row_score(row, RISK_WEIGHTS, FEATURE_RANGES)
        self.assertAlmostEqual(sum(contributions.values()), score)
        self.assertEqual(max(contributions, key=contributions.get), "DTR")


if __name__ == "__main__":
    unittest.main()
