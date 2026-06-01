"""
COPD Environmental Data Pipeline
=================================
Patient location : Sarkadi Imre utca 6, 1039 Budapest, Hungary
Coordinates      : 47.5999° N, 19.0616° E
Default range    : 2020-01-01 → today

Data sources
------------
1. Open-Meteo Historical Weather API  – temperature, pressure, dew point
2. Open-Meteo Air Quality API         – PM2.5, PM10, NO₂
3. GFZ Potsdam Kp-index               – 3-hour geomagnetic activity → daily max/mean

Engineered features
-------------------
- DTR        : Diurnal Temperature Range  (T_max − T_min)
- delta_P    : Barometric pressure change over 24 h  (ΔP)
- Rolling averages: 3, 7, 14-day windows for PM2.5, PM10, NO₂, Kp_max
- Kp_daily_max / Kp_daily_mean : aggregated from 3-h resolution

Output
------
../data/environmental_data.csv  – one row per day, datetime index
../data/data_quality_report.txt – coverage & missing value summary
"""

import pandas as pd
from config import LAT, LON, LOCATION_LABEL, START_DATE, END_DATE, OUTPUT_CSV, OUTPUT_REPORT
from fetchers import fetch_weather, fetch_air_quality, fetch_weather_forecast, fetch_kp_index, add_rolling_features
from report import quality_report
from score import compute_risk_score


def main():
    print(f"\n{'='*60}")
    print("COPD Environmental Data Pipeline")
    print(f"Location : {LOCATION_LABEL}")
    print(f"Period   : {START_DATE} → {END_DATE}")
    print(f"{'='*60}\n")

    df_weather = fetch_weather(LAT, LON, START_DATE, END_DATE)
    df_aq = fetch_air_quality(LAT, LON, START_DATE, END_DATE)
    df_kp = fetch_kp_index(START_DATE, END_DATE)

    print("\n  → Merging datasets (outer join on date)…")
    df = df_weather.join(df_aq, how="outer")
    df = df.join(df_kp, how="outer")

    df_forecast = fetch_weather_forecast(LAT, LON)
    df = pd.concat([df, df_forecast])
    df = df[~df.index.duplicated(keep='first')]

    df = add_rolling_features(df)
    df = compute_risk_score(df)
    df.attrs['location_label'] = LOCATION_LABEL

    base_cols = [
        "temperature_2m_max", "temperature_2m_min", "DTR",
        "surface_pressure_mean", "delta_P", "dew_point_2m_mean",
        "precipitation_sum", "windspeed_10m_max",
        "pm2_5", "pm10", "no2",
        "Kp_daily_max", "Kp_daily_mean",
    ]
    roll_cols = [c for c in df.columns if "roll" in c]
    df = df[[c for c in base_cols if c in df.columns] + roll_cols]

    df.index.name = "date"
    df.to_csv(OUTPUT_CSV)
    print(f"  ✓ Data saved  → {OUTPUT_CSV}  ({len(df)} rows × {len(df.columns)} cols)")

    quality_report(df, OUTPUT_REPORT)

    print("\nDone. ✓\n")
    return df


if __name__ == "__main__":
    main()
