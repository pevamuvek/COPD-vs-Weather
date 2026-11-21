"""Privacy-preserving location resolution."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


class LocationError(ValueError):
    """Raised when a location cannot be resolved safely."""


@dataclass(frozen=True)
class ResolvedLocation:
    label: str
    latitude: float
    longitude: float
    timezone: str


def round_coords(lat: float, lon: float, decimals: int = 2) -> tuple[float, float]:
    return round(float(lat), decimals), round(float(lon), decimals)


def _get_geocoding(url: str, params: dict, timeout: int = 15, tries: int = 3):
    last_error = None
    for attempt in range(tries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout):
            last_error = requests.RequestException(
                "Location search failed due to a connection or timeout error."
            )
        except requests.RequestException:
            raise requests.RequestException("Location search failed.") from None
        else:
            if response.status_code >= 500:
                last_error = requests.HTTPError(
                    f"Location search failed with HTTP {response.status_code}."
                )
            elif response.status_code >= 400:
                raise requests.HTTPError(
                    f"Location search failed with HTTP {response.status_code}."
                )
            else:
                return response

        if attempt < tries - 1:
            time.sleep(2 ** attempt)

    if last_error is None:
        raise requests.RequestException("Location search failed")
    raise last_error from None


def search_places(query: str, count: int = 5, language: str = "en") -> list[dict]:
    response = _get_geocoding(
        GEOCODING_URL,
        {"name": query, "count": count, "language": language, "format": "json"},
    )
    data = response.json()
    results = data.get("results")
    return results if isinstance(results, list) else []


def looks_like_street_address(text: str) -> bool:
    street_words = (
        "utca", "út", " tér", "ter ", "körút", "street", "st.",
        "road", "avenue", "lane",
    )
    lowered = text.lower()
    has_number = bool(re.search(r"\d", lowered))
    has_street_word = any(word in lowered for word in street_words)
    return has_number and has_street_word


def _candidate_label(result: dict) -> str:
    parts = []
    for key in ("name", "admin1", "country"):
        value = result.get(key)
        if value:
            text = str(value).strip()
            if text and text not in parts:
                parts.append(text)
    postcodes = result.get("postcodes")
    if isinstance(postcodes, (list, tuple)):
        postcode = next(
            (str(value).strip() for value in postcodes if value and str(value).strip()),
            None,
        )
    elif postcodes:
        postcode = str(postcodes).strip()
    else:
        postcode = result.get("postcode")
        postcode = str(postcode).strip() if postcode else None
    if postcode and postcode not in parts:
        parts.append(postcode)
    return ", ".join(parts) or "Unnamed place"


def _location_from_result(result: dict) -> ResolvedLocation:
    result_lat = result.get("latitude")
    result_lon = result.get("longitude")
    timezone = result.get("timezone")
    if result_lat is None or result_lon is None or not timezone:
        raise LocationError("The selected location did not include coordinates or timezone.")

    latitude, longitude = round_coords(result_lat, result_lon)
    return ResolvedLocation(
        label=_candidate_label(result),
        latitude=latitude,
        longitude=longitude,
        timezone=str(timezone),
    )


def resolve_location(
    query: str | None = None,
    choice: int = 0,
    lat: float | None = None,
    lon: float | None = None,
    tz: str | None = None,
) -> ResolvedLocation:
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            raise LocationError("Both latitude and longitude are required.")
        if not tz:
            raise LocationError("Timezone is required with latitude and longitude.")
        latitude, longitude = round_coords(lat, lon)
        return ResolvedLocation(
            label="Selected coordinates",
            latitude=latitude,
            longitude=longitude,
            timezone=tz.strip(),
        )

    if not query or not query.strip():
        raise LocationError("No place or coordinates were provided.")
    if looks_like_street_address(query):
        raise LocationError("Enter a city, district or postcode, not a street address.")

    try:
        results = search_places(query)
    except requests.RequestException:
        raise LocationError("Location search failed. Check the connection and try again.") from None
    if not results:
        raise LocationError("No location results found.")
    if choice < 0 or choice >= len(results):
        raise LocationError("The selected location choice is not available.")

    return _location_from_result(results[choice])


def resolve_location_interactive() -> ResolvedLocation:
    for attempt in range(3):
        try:
            query = input("Enter a city, district or postcode: ").strip()
        except EOFError:
            raise LocationError(
                "No location was provided in a non-interactive session."
            ) from None

        if looks_like_street_address(query):
            print("Enter a city, district or postcode instead.")
            continue

        try:
            results = search_places(query)
        except requests.RequestException:
            raise LocationError(
                "Location search failed. Check the connection and try again."
            ) from None

        if not results:
            print("No locations found. Try another city, district or postcode.")
            continue

        candidates = results[:5]
        for index, result in enumerate(candidates, start=1):
            latitude, longitude = round_coords(
                result.get("latitude"), result.get("longitude")
            )
            print(f"{index}. {_candidate_label(result)} ({latitude:.2f}, {longitude:.2f})")

        try:
            choice_text = input("Choose a number: ").strip()
        except EOFError:
            raise LocationError("Location selection ended in a non-interactive session.") from None
        try:
            choice = int(choice_text) - 1
            if choice < 0 or choice >= len(candidates):
                raise LocationError("Choose a number from the displayed list.")
            location = _location_from_result(candidates[choice])
        except (ValueError, LocationError) as error:
            print(str(error))
            continue

        try:
            confirmed = input("Confirm this location? (y/n): ").strip().lower()
        except EOFError:
            raise LocationError("Location confirmation ended in a non-interactive session.") from None
        if confirmed in {"y", "yes"}:
            return location

    raise LocationError("Location resolution stopped after 3 attempts.")
