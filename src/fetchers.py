import requests
import pandas as pd
import numpy as np

KP_URL = "https://www.gfz-potsdam.de/fileadmin/gfz/sec33/ap_kp_data/Kp_ap_since_1932.txt"
KP_FALLBACK_URL = "https://kp.gfz-potsdam.de/app/json/?start={start}&end={end}&index=Kp&status=def"


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


def fetch_kp_index(start: str, end: str) -> pd.DataFrame:
    """Fetch 3-hourly Kp index and aggregate to daily max/mean."""
    print("  → Fetching Kp-index from GFZ Potsdam…")

    e_json = None
    try:
        url = KP_FALLBACK_URL.format(start=start, end=end)
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        data = r.json()

        df = pd.DataFrame({
            "datetime": pd.to_datetime(data["datetime"]),
            "Kp":       data["Kp"],
        })
        df["date"] = df["datetime"].dt.normalize()
        daily = (
            df.groupby("date")["Kp"]
            .agg(Kp_daily_max="max", Kp_daily_mean="mean")
        )
        print(f"     Kp rows (JSON API): {len(daily)}")
        return daily

    except Exception as e:
        e_json = e
        print(f"     JSON API failed ({e_json}), trying bulk text file…")

    try:
        r = requests.get(KP_URL, timeout=120)
        r.raise_for_status()
        lines = [l for l in r.text.splitlines() if l and not l.startswith("#")]
        records = []
        for line in lines:
            parts = line.split()
            if len(parts) < 14:
                continue
            try:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                kp_vals = [float(parts[7 + i]) / 10 for i in range(8)]
                for i, kp in enumerate(kp_vals):
                    dt = pd.Timestamp(year=year, month=month, day=day, hour=i * 3)
                    records.append({"datetime": dt, "Kp": kp})
            except Exception:
                continue

        df = pd.DataFrame(records)
        df = df[(df["datetime"] >= start) & (df["datetime"] <= end)]
        df["date"] = df["datetime"].dt.normalize()
        daily = (
            df.groupby("date")["Kp"]
            .agg(Kp_daily_max="max", Kp_daily_mean="mean")
        )
        print(f"     Kp rows (bulk file): {len(daily)}")
        return daily

    except Exception as e_bulk:
        print(f"     ⚠ Both Kp sources failed. Kp columns will be NaN.\n"
              f"       JSON error : {e_json}\n"
              f"       Bulk error : {e_bulk}")
        idx = pd.date_range(start=start, end=end, freq="D", name="date")
        return pd.DataFrame({"Kp_daily_max": np.nan, "Kp_daily_mean": np.nan}, index=idx)


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
