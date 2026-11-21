"""Offline tests for privacy-preserving location resolution."""

from __future__ import annotations

import sys
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import get_end_date, get_location  # noqa: E402
from location import (  # noqa: E402
    LocationError,
    looks_like_street_address,
    resolve_location,
    resolve_location_interactive,
    round_coords,
    search_places,
)


class MockResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").HTTPError(
                f"HTTP {self.status_code}"
            )


class LocationTests(unittest.TestCase):
    def test_round_coords_negative_values(self):
        self.assertEqual(round_coords(-12.346, 67.891), (-12.35, 67.89))

    def test_search_places_parses_results_and_missing_results(self):
        payload = {
            "results": [{
                "name": "Springfield",
                "admin1": "Example State",
                "country": "Exampleland",
                "latitude": 12.345,
                "longitude": -67.891,
                "timezone": "Example/Zone",
                "postcodes": ["12345", "54321"],
            }]
        }
        with patch("location.requests.get", return_value=MockResponse(payload=payload)):
            results = search_places("Springfield")
            location = resolve_location(query="Springfield")
        self.assertEqual(results[0]["name"], "Springfield")
        self.assertEqual(
            location.label,
            "Springfield, Example State, Exampleland, 12345",
        )

        with patch("location.requests.get", return_value=MockResponse(payload={})):
            self.assertEqual(search_places("Nowhere"), [])

    def test_search_places_retries_5xx_and_propagates_4xx(self):
        retry_response = MockResponse(status_code=503)
        success = MockResponse(payload={"results": []})
        with patch("location.requests.get", side_effect=[retry_response, success]), patch(
            "location.time.sleep"
        ):
            self.assertEqual(search_places("Springfield"), [])

        with patch(
            "location.requests.get",
            return_value=MockResponse(status_code=404),
        ):
            with self.assertRaises(__import__("requests").HTTPError) as error:
                search_places("private query phrase")
        self.assertNotIn("private query phrase", str(error.exception))

        with patch(
            "location.requests.get",
            return_value=MockResponse(status_code=404),
        ):
            with self.assertRaises(LocationError) as error:
                resolve_location(query="private query phrase")
        self.assertNotIn("private query phrase", str(error.exception))

    def test_street_address_heuristic(self):
        self.assertTrue(looks_like_street_address("12 Example Street"))
        self.assertTrue(looks_like_street_address("6 Példa utca"))
        self.assertFalse(looks_like_street_address("Springfield"))
        self.assertFalse(looks_like_street_address("1234"))
        self.assertFalse(looks_like_street_address("1234 Springfield"))

    def test_resolve_coordinates_rounds_and_requires_timezone(self):
        location = resolve_location(lat=-12.346, lon=67.891, tz="Example/Zone")
        self.assertEqual((location.latitude, location.longitude), (-12.35, 67.89))
        with self.assertRaises(LocationError):
            resolve_location(lat=1.0, lon=2.0)
        with self.assertRaises(LocationError):
            resolve_location()

    def test_interactive_selection_uses_displayed_search_result_once(self):
        payload = {
            "results": [{
                "name": "Springfield",
                "admin1": "Example State",
                "country": "Exampleland",
                "latitude": 12.345,
                "longitude": -67.891,
                "timezone": "Example/Zone",
                "postcodes": ["12345"],
            }]
        }
        with (
            patch(
                "location.requests.get",
                return_value=MockResponse(payload=payload),
            ) as get,
            patch("builtins.input", side_effect=["Springfield", "1", "y"]),
            redirect_stdout(StringIO()),
        ):
            location = resolve_location_interactive()

        self.assertEqual(location.label, "Springfield, Example State, Exampleland, 12345")
        get.assert_called_once()

    def test_get_location_noninteractive_without_input(self):
        with patch("config.resolve_location_interactive", side_effect=LocationError(
            "No location was provided in a non-interactive session."
        )):
            with self.assertRaisesRegex(LocationError, "non-interactive"):
                get_location(type("Args", (), {})())

    def test_end_date_uses_resolved_location_timezone(self):
        location = resolve_location(lat=12.34, lon=-56.78, tz="Pacific/Auckland")
        utc_now = datetime(2026, 11, 21, 23, 30, tzinfo=timezone.utc)
        with patch("config.datetime") as datetime_mock:
            datetime_mock.now.side_effect = lambda tz: utc_now.astimezone(tz)
            end_date = get_end_date(location)

        self.assertEqual(end_date, "2026-11-22")


if __name__ == "__main__":
    unittest.main()
