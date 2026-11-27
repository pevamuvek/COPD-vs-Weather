"""Tests for standalone daily and monthly HTML risk reports."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from datetime import datetime
from html.parser import HTMLParser
from html import unescape
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from html_report import (  # noqa: E402
    _lane_chart,
    _daily_slice,
    _drivers,
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
            "temperature_2m_min": [18.0] * 37,
            "DTR": [10.0] * 34 + [14.0, 15.0, 16.0],
            "delta_P": [1.0] * 35 + [-4.0, 2.0],
            "dew_point_2m_mean": [12.0] * 37,
            "precipitation_sum": [float(index % 5) for index in range(37)],
            "windspeed_10m_max": [12.0 + index % 4 for index in range(37)],
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
        self.assertIn("Légnyomás-változás", html)
        self.assertIn("Csapadék", html)
        self.assertIn("NO₂", html)
        self.assertIn("Levegőminőség hiányzik", html)
        self.assertIn("alsó becslések", html)
        self.assertIn("abszolút hőterhelést nem méri", html)
        self.assertIn("Kockázati hajtóerők — átlag és csúcs", html)
        self.assertIn("Időszaki csúcs", html)
        self.assertEqual(html.count('<div class="driver-pair">'), 4)
        self.assertNotIn("GFZ Potsdam Kp", html)
        self.assertIn("Springfield &lt;test &amp; place&gt;", html)
        self.assertEqual(html.count('<tr class="'), 10)
        self.assertIn('class="lane-chart-svg"', html)
        self.assertNotIn("data-tooltip=", html)
        self.assertIn(
            ".lane-chart-svg { display: block; width: auto; min-width: 0; height: auto; }",
            html,
        )
        self.assertIn("height: 362px", html)
        self.assertIn("@media (min-width: 980px)", html)
        _HTMLSmokeParser().feed(html)

    def test_daily_lane_chart_data_geometry_and_interactions(self):
        frame = sample_frame()
        dates = frame.index
        frame.loc[dates[27:32], "risk_score"] = [0.1, 0.25, 0.35, 0.5, float("nan")]
        frame["risk_tier"] = frame["risk_score"].map(classify_risk_score)
        frame.loc[dates[30], "DTR"] = float("nan")
        frame.loc[dates[32], "temperature_2m_min"] = float("nan")
        frame.loc[dates[29], "pm2_5"] = float("nan")
        frame.loc[dates[30], "pm10"] = float("nan")
        frame.loc[dates[31], "no2"] = float("nan")
        frame["latitude"] = 47.123456
        frame["longitude"] = 19.123456

        with tempfile.TemporaryDirectory() as temp_dir:
            output = generate_daily_html_report(
                frame,
                temp_dir,
                location_label="Springfield",
                generated_at=datetime(2026, 8, 6, 8, 30),
            )
            html = output.read_text(encoding="utf-8")

        chart_data = re.search(
            r'<script type="application/json" class="chart-data">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(chart_data)
        raw_json = chart_data.group(1)
        self.assertNotIn("</script>", raw_json.lower())
        records = json.loads(raw_json)
        self.assertEqual(len(records), 10)
        self.assertTrue(all(len(record["card_rows"]) == 9 for record in records))
        expected_card_order = [
            "Hőmérséklet max./min.",
            "DTR",
            "Légnyomás-változás",
            "Harmatpont",
            "Csapadék",
            "Max. szélsebesség",
            "PM₂,₅",
            "PM₁₀",
            "NO₂",
        ]
        self.assertTrue(
            all(
                [label for label, _ in record["card_rows"]] == expected_card_order
                for record in records
            )
        )
        lane_labels = re.findall(
            r'<text class="lane-label" data-metric="[^"]+" '
            r'x="8" y="[^"]+">(.*?)</text>',
            html,
        )
        self.assertEqual(
            [unescape(label) for label in lane_labels],
            [
                "Pontszám",
                "Hőm. max/min (°C)",
                "DTR (°C)",
                "ΔP (hPa)",
                "Harmatpont (°C)",
                "Csapadék (mm)",
                "Max. szél (km/h)",
                "Légszennyezők (µg/m³)",
            ],
        )
        self.assertIn(">PM₂,₅</span>", html)
        self.assertIn(">PM₁₀</span>", html)
        self.assertIn(">NO₂</span>", html)
        self.assertIn("pontszám", records[7]["status_text"])
        self.assertNotIn('hidden', re.search(r'<aside class="lane-card".*?</aside>', html).group())
        self.assertNotIn("— µg/m³", html)
        self.assertNotIn("47.123456", html)
        self.assertNotIn("19.123456", html)

        selected = re.search(r'data-selected-index="(\d+)"', html)
        self.assertIsNotNone(selected)
        self.assertEqual(int(selected.group(1)), 7)
        self.assertEqual(html.count('class="lane-hit-column"'), 10)

        labels = re.findall(
            r'<text class="lane-x-label" data-index="(\d+)" '
            r'x="([\d.]+)" y="(\d+)" text-anchor="middle">(.*?)</text>',
            html,
        )
        self.assertEqual([int(index) for index, _, _, _ in labels], list(range(10)))
        self.assertEqual(
            [unescape(label) for _, _, _, label in labels],
            [record["day_label"] for record in records],
        )
        month_labels = re.findall(
            r'<text class="lane-x-month-label" data-index="(\d+)" '
            r'x="([\d.]+)" y="(\d+)" text-anchor="middle">(.*?)</text>',
            html,
        )
        self.assertEqual(
            [
                (int(index), unescape(label))
                for index, _, _, label in month_labels
            ],
            [
                (index, record["month_label"])
                for index, record in enumerate(records)
                if record["month_label"]
            ],
        )
        x_positions = [float(x) for _, x, _, _ in labels]
        steps = [right - left for left, right in zip(x_positions, x_positions[1:])]
        self.assertTrue(all(abs(step - steps[0]) < 0.02 for step in steps))
        svg_geometry = re.search(
            r'<svg class="lane-chart-svg" width="(\d+)" height="\d+" '
            r'style="min-width:(\d+)px" viewBox="0 0 (\d+) (\d+)"',
            html,
        )
        self.assertIsNotNone(svg_geometry)
        render_width, min_width, view_width, _ = map(
            int, svg_geometry.groups()
        )
        self.assertEqual(render_width, min_width)
        rendered_steps = [step * render_width / view_width for step in steps]
        self.assertGreaterEqual(min(rendered_steps), 28)
        self.assertGreaterEqual(min(rendered_steps), 35)
        self.assertLess(max(rendered_steps), 37)

        for tier in ("low", "moderate", "high", "very_high"):
            self.assertRegex(
                html,
                rf'<circle class="lane-point lane-score-point tier-{tier}(?: [^"]*)?"',
            )
        self.assertIn('"tier_key":"unknown"', raw_json)
        self.assertIn('class="lane-legend-dot tier-unknown"', html)
        self.assertRegex(html, r'lane-score-point tier-[^"]+ forecast-point')
        self.assertIn(".lane-point.forecast-point { fill: var(--surface); }", html)
        self.assertNotRegex(
            html,
            r'lane-point[^"]*forecast-point[^"]*fill:\s*var\(--accent\)',
        )
        self.assertIn(".lane-temperature-max-line { stroke: #B42318; }", html)
        self.assertIn(
            ".lane-temperature-max-line, .lane-temperature-min-line, "
            ".lane-pm25-line, .lane-pm10-line { stroke-width: 1.4; }",
            html,
        )
        self.assertIn(
            ".lane-point.lane-pm25-point, .lane-point.lane-pm10-point "
            "{ stroke-width: 1; }",
            html,
        )
        self.assertIn(
            ".lane-point.is-selected.lane-pm25-point, "
            ".lane-point.is-selected.lane-pm10-point { stroke-width: 1.5; }",
            html,
        )

        dtr_points = re.findall(
            r'<circle class="[^"]*lane-dtr-point[^"]*" data-lane="DTR" '
            r'data-index="(\d+)"',
            html,
        )
        self.assertNotIn("3", dtr_points)
        dtr_segments = re.findall(
            r'<path class="[^"]*lane-dtr-line[^"]*" data-lane="DTR" '
            r'data-start-index="(\d+)" data-end-index="(\d+)"',
            html,
        )
        self.assertEqual(len(dtr_segments), 7)
        self.assertFalse(any("3" in (start, end) for start, end in dtr_segments))
        chart_points = re.findall(
            r'<circle class="[^"]+" data-lane="([^"]+)" '
            r'data-index="(\d+)" cx="([\d.]+)"',
            html,
        )
        point_lanes = {lane for lane, _, _ in chart_points}
        self.assertEqual(
            point_lanes,
            {
                "risk_score",
                "temperature_2m_max",
                "temperature_2m_min",
                "DTR",
                "delta_P",
                "dew_point_2m_mean",
                "precipitation_sum",
                "windspeed_10m_max",
                "pm2_5",
                "pm10",
                "no2",
            },
        )
        centers = {
            int(index): float(center)
            for index, center in re.findall(
                r'<rect class="lane-hit-column" data-index="(\d+)" '
                r'data-center="([\d.]+)"',
                html,
            )
        }
        for _, index, x in chart_points:
            self.assertAlmostEqual(float(x), centers[int(index)], places=2)

        pollutant_y = {
            lane: float(y)
            for lane, y in re.findall(
                r'<circle class="[^"]+" data-lane="(pm2_5|pm10|no2)" '
                r'data-index="0" cx="[\d.]+" cy="([\d.]+)"',
                html,
            )
        }
        self.assertGreater(pollutant_y["pm2_5"], pollutant_y["pm10"])
        self.assertGreater(pollutant_y["pm10"], pollutant_y["no2"])
        for pollutant_series in ("pm25", "pm10"):
            self.assertRegex(
                html,
                rf'<circle class="[^"]*lane-{pollutant_series}-point[^"]*" '
                r'data-lane="[^"]+" data-index="0" cx="[\d.]+" '
                r'cy="[\d.]+" r="2"></circle>',
            )
            self.assertRegex(
                html,
                rf'<circle class="[^"]*lane-{pollutant_series}-point[^"]*" '
                r'data-lane="[^"]+" data-index="7" cx="[\d.]+" '
                r'cy="[\d.]+" r="3"></circle>',
            )
        self.assertIn('point.setAttribute("r",selected?"3":"2");', html)

        point_indices = {
            lane: {int(index) for point_lane, index, _ in chart_points if point_lane == lane}
            for lane in ("pm2_5", "pm10", "no2")
        }
        temperature_point_indices = {
            lane: {
                int(index)
                for point_lane, index, _ in chart_points
                if point_lane == lane
            }
            for lane in ("temperature_2m_max", "temperature_2m_min")
        }
        self.assertIn(5, temperature_point_indices["temperature_2m_max"])
        self.assertNotIn(5, temperature_point_indices["temperature_2m_min"])
        for lane, missing_index in (("pm2_5", 2), ("pm10", 3), ("no2", 4)):
            self.assertNotIn(missing_index, point_indices[lane])
            self.assertNotIn(8, point_indices[lane])
            self.assertNotIn(9, point_indices[lane])
            segments = re.findall(
                rf'<path class="[^"]+" data-lane="{lane}" '
                r'data-start-index="(\d+)" data-end-index="(\d+)"',
                html,
            )
            self.assertFalse(
                any(
                    missing_index in (int(start), int(end))
                    or int(start) >= 8
                    or int(end) >= 8
                    for start, end in segments
                )
            )
        self.assertRegex(
            html,
            r'lane-temperature-max-point forecast-point',
        )
        self.assertRegex(
            html,
            r'lane-temperature-max-line forecast-segment',
        )
        self.assertRegex(html, r'lane-wind-point forecast-point')
        self.assertRegex(html, r'lane-wind-line forecast-segment')
        final_card_values = dict(records[-1]["card_rows"])
        self.assertEqual(final_card_values["PM₂,₅"], "—")
        self.assertEqual(final_card_values["PM₁₀"], "—")
        self.assertEqual(final_card_values["NO₂"], "—")
        self.assertIn("Alsó becslés: PM és NO₂ hiányzik", records[-1]["note"])

        rows, _, _ = _daily_slice(frame.drop(columns=["latitude", "longitude"]))
        no_today_chart = _lane_chart(rows.tail(3), None)
        self.assertIn('data-selected-index="2"', no_today_chart)
        self.assertIn('tabindex="0"', html)
        self.assertEqual(html.count('tabindex="0"'), 1)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('event.key==="ArrowLeft"', html)
        self.assertIn('event.key==="ArrowRight"', html)
        self.assertIn('event.key==="Home"', html)
        self.assertIn('event.key==="End"', html)

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
        self.assertIn('class="lane-chart-svg"', html)
        self.assertEqual(
            html.count('class="lane-label" data-metric="air_quality"'),
            1,
        )
        for pollutant in ("pm2_5", "pm10", "no2"):
            points = re.findall(
                rf'<circle class="[^"]+" data-lane="{pollutant}"',
                html,
            )
            segments = re.findall(
                rf'<path class="[^"]+" data-lane="{pollutant}"',
                html,
            )
            self.assertEqual(len(points), 30)
            self.assertEqual(len(segments), 29)
        self.assertIn("pointermove", html)
        self.assertIn("Kiemelt események", html)
        self.assertIn("Kockázati hajtóerők — átlag és csúcs", html)
        self.assertEqual(html.count('<div class="driver-pair">'), 4)
        self.assertIn("Mérsékelt+ napok", html)
        self.assertEqual(html.count('class="lane-hit-column"'), 30)

        chart_data = re.search(
            r'<script type="application/json" class="chart-data">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(chart_data)
        records = json.loads(chart_data.group(1))
        self.assertEqual(len(records), 30)
        self.assertTrue(all(not record["is_forecast"] for record in records))
        self.assertTrue(records[-1]["is_today"])
        self.assertEqual(
            int(re.search(r'data-selected-index="(\d+)"', html).group(1)),
            29,
        )
        svg_geometry = re.search(
            r'<svg class="lane-chart-svg" width="(\d+)" height="\d+" '
            r'style="min-width:(\d+)px" viewBox="0 0 (\d+) (\d+)"',
            html,
        )
        self.assertIsNotNone(svg_geometry)
        render_width, min_width, view_width, _ = map(
            int, svg_geometry.groups()
        )
        self.assertEqual(render_width, min_width)
        chart_centers = [
            float(center)
            for center in re.findall(
                r'<rect class="lane-hit-column" data-index="\d+" '
                r'data-center="([\d.]+)"',
                html,
            )
        ]
        chart_steps = [
            right - left
            for left, right in zip(chart_centers, chart_centers[1:])
        ]
        self.assertTrue(
            all(abs(step - chart_steps[0]) < 0.02 for step in chart_steps)
        )
        rendered_steps = [
            step * render_width / view_width for step in chart_steps
        ]
        self.assertGreaterEqual(min(rendered_steps), 28)
        self.assertGreaterEqual(min(rendered_steps), 31)
        self.assertLess(max(rendered_steps), 33)

        month_labels = re.findall(
            r'<text class="lane-x-month-label" data-index="(\d+)" '
            r'x="([\d.]+)" y="(\d+)" text-anchor="middle">(.*?)</text>',
            html,
        )
        self.assertEqual(
            [
                (int(index), unescape(label))
                for index, _, _, label in month_labels
            ],
            [
                (index, record["month_label"])
                for index, record in enumerate(records)
                if record["month_label"]
            ],
        )
        for index, x, _, _ in month_labels:
            self.assertAlmostEqual(
                float(x),
                chart_centers[int(index)],
                places=2,
            )
        self.assertEqual(len(chart_centers), 30)
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

    def test_driver_bars_show_weights_and_max_contribution_date(self):
        rows = pd.DataFrame(
            [
                {
                    "delta_P": 10.0,
                    "DTR": 12.5,
                    "dew_point_2m_mean": 5.0,
                    "pm2_5": 37.5,
                    "no2": 50.0,
                    "pm10": 75.0,
                },
                {
                    "delta_P": 20.0,
                    "DTR": 25.0,
                    "dew_point_2m_mean": -20.0,
                    "pm2_5": 75.0,
                    "no2": 100.0,
                    "pm10": 150.0,
                },
            ],
            index=pd.to_datetime(["2026-08-01", "2026-08-02"]),
        )

        driver_html = _drivers(rows)
        self.assertIn(
            'class="driver-fill driver-dp" style="width:20.8%"',
            driver_html,
        )
        self.assertIn(
            'class="driver-fill driver-dp" style="width:27.8%"',
            driver_html,
        )
        self.assertIn("Átlag: 0,208 pont", driver_html)
        self.assertIn("Pontszámsúly: 27,8%", driver_html)
        self.assertIn("Csúcs: 0,278 pont", driver_html)
        self.assertIn("Csúcs dátuma: 2026. aug. 2.", driver_html)
        self.assertIn("teljes sáv 1,000 pont", driver_html)
        self.assertIn("Időszaki csúcs", driver_html)
        self.assertNotIn("Hiány:", driver_html)

        partial_rows = rows.copy()
        partial_rows.loc[pd.Timestamp("2026-08-02"), "DTR"] = float("nan")
        partial_html = _drivers(partial_rows)
        self.assertIn(
            'class="driver-fill driver-dtr" style="width:11.1%"',
            partial_html,
        )
        self.assertIn("Csúcs dátuma: 2026. aug. 1.", partial_html)

        zero_rows = rows.copy()
        zero_rows["DTR"] = 0.0
        zero_html = _drivers(zero_rows)
        self.assertIn(
            'class="driver-fill driver-dtr" style="width:0.0%"',
            zero_html,
        )
        self.assertIn("Csúcs dátuma: 2026. aug. 1.", zero_html)

        no_data_rows = rows.copy()
        no_data_rows["DTR"] = float("nan")
        no_data_html = _drivers(no_data_rows)
        self.assertIn("Nincs adat", no_data_html)
        self.assertIn("Csúcs dátuma: —", no_data_html)


if __name__ == "__main__":
    unittest.main()
