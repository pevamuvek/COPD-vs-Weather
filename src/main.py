"""
COPD Environmental Data Pipeline
=================================
Location         : resolved from a place name or postcode
Default range    : 2020-01-01 → today

Data sources
------------
1. Open-Meteo Historical Weather API  – temperature, pressure, dew point
2. Open-Meteo Air Quality API         – PM2.5, PM10, NO₂

Kp-index data is fetched independently by running ``python src\\kp_analysis.py``.

Engineered features
-------------------
- DTR        : Diurnal Temperature Range  (T_max − T_min)
- delta_P    : Barometric pressure change over 24 h  (ΔP)
- Rolling averages: 3, 7, 14-day windows for PM2.5, PM10, and NO₂

Output
------
../data/environmental_data.csv  – one row per day, datetime index
../data/data_quality_report.txt – coverage & missing value summary
../data/reports/               – 10-day and 30-day Hungarian HTML reports
"""

import argparse

import pandas as pd
from config import get_end_date, get_location, START_DATE, OUTPUT_CSV, OUTPUT_REPORT, REPORT_DIR
from fetchers import fetch_weather, fetch_air_quality, fetch_weather_forecast, add_rolling_features
from location import LocationError
from html_report import generate_daily_html_report, generate_monthly_html_report
from report import quality_report
from score import compute_risk_score


def main():
    parser = argparse.ArgumentParser(description="COPD Environmental Data Pipeline")
    parser.add_argument("--place")
    parser.add_argument("--choice", type=int, default=0)
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--tz")
    args = parser.parse_args()

    try:
        location = get_location(args)
        end_date = get_end_date(location)
    except LocationError as error:
        parser.error(str(error))

    print(f"\nLocation : {location.label}")
    print(f"Coordinates : {location.latitude:.2f}, {location.longitude:.2f}")
    print(f"Timezone : {location.timezone}")
    print(f"\n{'='*60}")
    print("COPD Environmental Data Pipeline")
    print(f"Location : {location.label}")
    print(f"Period   : {START_DATE} → {end_date}")
    print(f"{'='*60}\n")

    df_weather = fetch_weather(location, START_DATE, end_date)
    df_aq = fetch_air_quality(location, START_DATE, end_date)

    print("\n  → Merging datasets (outer join on date)…")
    df = df_weather.join(df_aq, how="outer")

    df_forecast = fetch_weather_forecast(location)
    df = pd.concat([df, df_forecast])
    df = df[~df.index.duplicated(keep='first')]

    df = add_rolling_features(df)
    df = compute_risk_score(df)
    df.attrs['location_label'] = location.label

    base_cols = [
        "temperature_2m_max", "temperature_2m_min", "DTR",
        "surface_pressure_mean", "delta_P", "dew_point_2m_mean",
        "precipitation_sum", "windspeed_10m_max",
        "pm2_5", "pm10", "no2",
    ]
    score_cols = [c for c in ["risk_score", "risk_tier", "risk_label", "is_forecast"] if c in df.columns]
    roll_cols = [c for c in df.columns if "roll" in c]
    df = df[[c for c in base_cols if c in df.columns] + score_cols + roll_cols]

    df.index.name = "date"
    df.to_csv(OUTPUT_CSV)
    print(f"  ✓ Data saved  → {OUTPUT_CSV}  ({len(df)} rows × {len(df.columns)} cols)")

    quality_report(df, OUTPUT_REPORT)
    daily_report_path = generate_daily_html_report(
        df, output_dir=REPORT_DIR, location_label=location.label
    )
    monthly_report_path = generate_monthly_html_report(
        df, output_dir=REPORT_DIR, location_label=location.label
    )
    print(f"  HTML report saved -> {daily_report_path}")
    print(f"  HTML report saved -> {monthly_report_path}")

    print("\nDone. ✓\n")
    return df


if __name__ == "__main__":
    main()
