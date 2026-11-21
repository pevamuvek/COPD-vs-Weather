from pathlib import Path
from datetime import date, datetime
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from location import (
    ResolvedLocation,
    LocationError,
    resolve_location,
    resolve_location_interactive,
)

START_DATE = "2020-01-01"
END_DATE = date.today().isoformat()          # update to a fixed date if needed

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR = DATA_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = DATA_DIR / "environmental_data.csv"
OUTPUT_REPORT = DATA_DIR / "data_quality_report.txt"
OUTPUT_KP_CSV = DATA_DIR / "kp_daily.csv"


def get_end_date(location: ResolvedLocation) -> str:
    try:
        return datetime.now(ZoneInfo(location.timezone)).date().isoformat()
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise LocationError(
            f"Unsupported location timezone: {location.timezone}"
        ) from error


def get_location(args=None) -> ResolvedLocation:
    place = getattr(args, "place", None) if args is not None else None
    choice = getattr(args, "choice", 0) if args is not None else 0
    lat = getattr(args, "lat", None) if args is not None else None
    lon = getattr(args, "lon", None) if args is not None else None
    tz = getattr(args, "tz", None) if args is not None else None

    if place:
        return resolve_location(query=place, choice=choice)
    if lat is not None or lon is not None:
        return resolve_location(lat=lat, lon=lon, tz=tz)

    env_lat = os.getenv("COPD_LAT")
    env_lon = os.getenv("COPD_LON")
    env_tz = os.getenv("COPD_TZ")
    if env_lat is not None or env_lon is not None or env_tz is not None:
        if env_lat is None or env_lon is None or env_tz is None:
            raise LocationError(
                "COPD_LAT, COPD_LON and COPD_TZ must all be set together."
            )
        try:
            return resolve_location(
                lat=float(env_lat),
                lon=float(env_lon),
                tz=env_tz,
            )
        except ValueError as error:
            raise LocationError("COPD_LAT and COPD_LON must be valid numbers.") from error

    try:
        return resolve_location_interactive()
    except EOFError:
        raise LocationError(
            "No location was provided in a non-interactive session."
        ) from None
