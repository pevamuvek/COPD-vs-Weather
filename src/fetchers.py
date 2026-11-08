import requests
import pandas as pd
import numpy as np
import time

KP_URL = "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt"
KP_FALLBACK_URL = (
    "https://kp.gfz.de/app/json/?start={start}&end={end}&index=Kp&status=all"
)
KP_COLUMNS = ["Kp_daily_max", "Kp_daily_mean", "Kp_n", "Kp_daily_sum"]


def fetch_weather(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    """Daily weather: temperature min/max, surface pressure, dew point."""
    print("  → Fetching weather data from Open-Meteo…")
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "start_date": start,
        "end_date":   end,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "surface_pressure_mean",
            "dew_point_2m_mean",
            "precipitation_sum",
            "windspeed_10m_max",
        ],
        "timezone": "Europe/Budapest",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    daily = r.json()["daily"]
    df = pd.DataFrame(daily)
    df["date"] = pd.to_datetime(df["time"])
    df = df.drop(columns=["time"])

    df["DTR"] = df["temperature_2m_max"] - df["temperature_2m_min"]
    df["delta_P"] = df["surface_pressure_mean"].diff()

    print(f"     Weather rows: {len(df)}")
    return df.set_index("date")


def fetch_air_quality(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    """Daily air quality: PM2.5, PM10, NO₂ (hourly → daily mean)."""
    print("  → Fetching air quality data from Open-Meteo…")
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": start,
        "end_date":   end,
        "hourly": ["pm2_5", "pm10", "nitrogen_dioxide"],
        "timezone": "Europe/Budapest",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    hourly = r.json()["hourly"]
    df_h = pd.DataFrame(hourly)
    df_h["datetime"] = pd.to_datetime(df_h["time"])
    df_h = df_h.drop(columns=["time"])
    df_h["date"] = df_h["datetime"].dt.normalize()

    df_daily = (
        df_h.groupby("date")[["pm2_5", "pm10", "nitrogen_dioxide"]]
        .mean()
        .rename(columns={"nitrogen_dioxide": "no2"})
    )
    print(f"     AQ rows: {len(df_daily)}")
    return df_daily


def fetch_weather_forecast(lat: float, lon: float, days: int = 3) -> pd.DataFrame:
    """Daily weather forecast: extends today's data 1–2 days ahead."""
    print("  → Fetching weather forecast from Open-Meteo…")
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "surface_pressure_mean",
            "dew_point_2m_mean",
            "precipitation_sum",
            "windspeed_10m_max",
        ],
        "forecast_days": days,
        "timezone": "Europe/Budapest",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    daily = r.json()["daily"]
    df = pd.DataFrame(daily)
    df["date"] = pd.to_datetime(df["time"])
    df = df.drop(columns=["time"])

    df["DTR"] = df["temperature_2m_max"] - df["temperature_2m_min"]
    df["delta_P"] = df["surface_pressure_mean"].diff()
    df["is_forecast"] = True

    print(f"     Forecast rows: {len(df)}")
    return df.set_index("date")


def _get(url: str, timeout: int, tries: int = 3) -> requests.Response:
    """Retry transient server and connection failures; propagate client errors."""
    last_error = None
    for attempt in range(tries):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code >= 500:
                last_error = requests.HTTPError(
                    f"HTTP {response.status_code} for {url}"
                )
            else:
                response.raise_for_status()
                return response
        except (requests.ConnectionError, requests.Timeout) as error:
            last_error = error

        if attempt < tries - 1:
            time.sleep(2 ** attempt)

    if last_error is None:
        raise requests.RequestException("Kp request failed without a response")
    raise last_error


def _parse_kp_bulk(text: str) -> pd.DataFrame:
    """Parse GFZ daily rows into 3-hourly UTC timestamps and Kp values."""
    records = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 15:
            continue
        try:
            year, month, day = map(int, parts[:3])
            values = [float(value) for value in parts[7:15]]
            day_start = pd.Timestamp(year=year, month=month, day=day)
        except (ValueError, OverflowError):
            continue
        for interval, value in enumerate(values):
            records.append((day_start + pd.Timedelta(hours=3 * interval), value))

    return pd.DataFrame(records, columns=["datetime", "Kp"])


def _kp_date_range(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(
        start=pd.Timestamp(start).normalize(),
        end=pd.Timestamp(end).normalize(),
        freq="D",
        name="date",
    )


def _daily_kp(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Aggregate valid 3-hourly Kp readings and retain wholly missing days."""
    valid = df[df["Kp"].ge(0)].copy()
    valid["date"] = valid["datetime"].dt.normalize()
    grouped = valid.groupby("date")["Kp"]
    daily = pd.DataFrame(
        {
            "Kp_daily_max": grouped.max(),
            "Kp_daily_mean": grouped.mean(),
            "Kp_n": grouped.count(),
            "Kp_daily_sum": grouped.sum(),
        }
    ).reindex(_kp_date_range(start, end))
    daily["Kp_n"] = daily["Kp_n"].fillna(0).astype(int)
    daily["Kp_daily_sum"] = daily["Kp_daily_sum"].where(daily["Kp_n"] == 8)
    return daily[KP_COLUMNS]


def _fetch_kp_json(start: str, end: str) -> pd.DataFrame:
    """Fetch JSON in yearly chunks to avoid an oversized API response."""
    frames = []
    current, last = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    while current <= last:
        chunk_end = min(pd.Timestamp(year=current.year, month=12, day=31), last)
        url = KP_FALLBACK_URL.format(
            start=current.strftime("%Y-%m-%dT00:00:00Z"),
            end=chunk_end.strftime("%Y-%m-%dT23:59:59Z"),
        )
        data = _get(url, timeout=60).json()
        frames.append(
            pd.DataFrame(
                {
                    "datetime": pd.to_datetime(data["datetime"], utc=True).tz_convert(None),
                    "Kp": data["Kp"],
                }
            )
        )
        current = chunk_end + pd.Timedelta(days=1)
    return pd.concat(frames, ignore_index=True)


def _validate_kp(df: pd.DataFrame) -> None:
    if df.empty:
        raise ValueError("GFZ returned no Kp readings for the requested range")
    if df["Kp"].max() > 9.01:
        raise ValueError(f"Kp max {df['Kp'].max()} exceeds the expected maximum of 9")


def _missing_kp(start: str, end: str) -> pd.DataFrame:
    result = pd.DataFrame(np.nan, index=_kp_date_range(start, end), columns=KP_COLUMNS)
    result["Kp_n"] = 0
    return result


def fetch_kp_index(start: str, end: str) -> pd.DataFrame:
    """Fetch GFZ Kp readings and aggregate them by UTC day."""
    print("  Fetching Kp-index from GFZ Potsdam...")
    errors = []

    try:
        bulk = _parse_kp_bulk(_get(KP_URL, timeout=120).text)
        bulk = bulk[
            bulk["datetime"].between(
                pd.Timestamp(start).normalize(),
                pd.Timestamp(end).normalize() + pd.Timedelta(days=1)
                - pd.Timedelta(nanoseconds=1),
            )
        ]
        _validate_kp(bulk)
        daily = _daily_kp(bulk, start, end)
        source = "bulk file"
    except Exception as error:
        errors.append(f"bulk file: {error}")
        print(f"     Bulk file failed ({error}), trying JSON API…")
        try:
            json_df = _fetch_kp_json(start, end)
            _validate_kp(json_df)
            daily = _daily_kp(json_df, start, end)
            source = "JSON API"
        except Exception as json_error:
            errors.append(f"JSON API: {json_error}")
            print("     WARNING: All Kp sources failed. Kp values will be missing.")
            for message in errors:
                print(f"       {message}")
            return _missing_kp(start, end)

    incomplete = int((daily["Kp_n"] < 8).sum())
    print(
        f"     Kp rows ({source}): {len(daily)} days, latest "
        f"{daily.index.max().date()}, incomplete days: {incomplete}"
    )
    return daily


def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add 3/7/14-day rolling means for pollution and Kp, plus lag columns for shock features."""
    cols = [c for c in ["pm2_5", "pm10", "no2", "Kp_daily_max"] if c in df.columns]
    for col in cols:
        for window in [3, 7, 14]:
            df[f"{col}_roll{window}d"] = df[col].rolling(window, min_periods=1).mean()

    lag_features = {
        "delta_P": [2, 5, 7, 14],
        "DTR": [2, 7, 14],
    }
    for col, lags in lag_features.items():
        if col in df.columns:
            for lag in lags:
                df[f"{col}_lag{lag}d"] = df[col].shift(lag)

    return df
