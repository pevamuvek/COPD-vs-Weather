# `fetchers.py`

This module retrieves environmental time series from remote APIs, reshapes them into daily data, and adds rolling statistics.

## Concept

The pipeline uses multiple data sources to capture different environmental dimensions for the same location and date range.

Each fetcher returns a pandas `DataFrame` indexed by date. This design makes data joining predictable and preserves every calendar day across sources.

The final merged dataset is suitable for exploratory analysis and visualization, with environmental features aligned by day. Statistical or machine-learning modeling is not currently implemented.

## Data sources

- Open-Meteo daily weather archive for temperature, pressure, dew point, precipitation, and wind.
- Open-Meteo daily weather forecast for the 1–2 day forward risk preview.
- Open-Meteo air quality API for hourly pollutant readings aggregated to daily means.
- GFZ Potsdam Kp index data, fetched separately for independent analysis by
  [`kp_analysis.py`](../src/kp_analysis.py).

## Feature rationale

The selected features are informed by COPD environmental risk research and the project conversation log:

- `DTR` highlights diurnal temperature swings, which are linked to respiratory stress in Hungary.
- `delta_P` captures the 24-hour barometric pressure change, a known trigger for COPD exacerbation.
- `pm2_5`, `pm10`, and `no2` represent air pollution stressors that can worsen lung function.
- rolling averages over 3, 7, and 14 days capture pollution exposure patterns.
- Kp summaries are retained in a separate date-indexed dataset and are not inputs
  to the core risk score or its reports.
- explicit pressure and temperature shock lags are computed for analysis: `delta_P_lag2d`, `delta_P_lag5d`, `delta_P_lag7d`, `delta_P_lag14d`, `DTR_lag2d`, `DTR_lag7d`, and `DTR_lag14d`. The current `main.py` output selection does not retain them in the CSV, and they are not inputs to the current risk score.

These variables are consistent with the project’s academic benchmark goals and the data-driven risk window design.

## Imports

- `requests`
- `pandas as pd`
- `numpy as np`
- `time`

## Constants

- `KP_URL = "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt"`
- `KP_FALLBACK_URL = "https://kp.gfz.de/app/json/?start={start}&end={end}&index=Kp&status=all"`

## Functions

### `fetch_weather(lat, lon, start, end)`

Fetches daily weather summary data and derives simple atmospheric features.

The function should:

- print a progress message for visibility
- request the Open-Meteo archive endpoint with the specified coordinates and date range
- request these daily fields: `temperature_2m_max`, `temperature_2m_min`, `surface_pressure_mean`, `dew_point_2m_mean`, `precipitation_sum`, `windspeed_10m_max`
- parse the JSON response and convert `time` to a datetime index named `date`
- compute derived daily features:
  - `DTR = temperature_2m_max - temperature_2m_min`
  - `delta_P = surface_pressure_mean.diff()`
- return the DataFrame indexed by `date`

The derived `delta_P` value is useful as a simple pressure trend indicator. It will be NaN on the first day by design.

### `fetch_air_quality(lat, lon, start, end)`

Retrieves hourly air pollution data and converts it into daily mean values.

The function should:

- print a progress message
- request the Open-Meteo air quality endpoint with hourly fields `pm2_5`, `pm10`, and `nitrogen_dioxide`
- convert the hourly `time` values to pandas datetimes
- normalize timestamps to a daily `date` field
- aggregate mean values by date for each pollutant
- rename `nitrogen_dioxide` to `no2`
- return the daily DataFrame

This step turns granular hourly pollutant measurements into a daily summary that can be joined with weather data on the same time scale.

### `fetch_weather_forecast(lat, lon, days=3)`

Fetches daily weather forecast data for the forward risk preview.

The function should:

- print a progress message for visibility
- request `https://api.open-meteo.com/v1/forecast` with the supplied coordinates
- request these daily fields: `temperature_2m_max`, `temperature_2m_min`, `surface_pressure_mean`, `dew_point_2m_mean`, `precipitation_sum`, `windspeed_10m_max`
- set `forecast_days` to `days`, with a default of `3` to cover today and the next two calendar days
- parse the JSON response and convert `time` to a datetime index named `date`
- compute derived features identically to `fetch_weather`:
  - `DTR = temperature_2m_max - temperature_2m_min`
  - `delta_P = surface_pressure_mean.diff()`
- add `is_forecast = True` on every returned row
- return the DataFrame indexed by `date`

In `main.py`, append forecast rows after the historical merge and remove duplicate dates:

```python
df = pd.concat([df, forecast_df])
df = df[~df.index.duplicated(keep="first")]
```

The forecast merge ensures historical data takes precedence if today is returned by both sources. `is_forecast` must be preserved in `OUTPUT_CSV` so downstream tools can filter forecast rows. The first forecast row can have `delta_P = NaN`; this is acceptable and should be noted in the quality report.

### `fetch_kp_index(start, end)`

Fetches geomagnetic Kp index values and aggregates them to daily summary
statistics for the standalone Kp analysis workflow. The core environmental
pipeline does not call this function or merge the returned data.

The function must be resilient:

- first attempt the GFZ bulk text data archive
- if that fails, fall back to the GFZ JSON API in yearly chunks
- if both sources fail, return a date-indexed DataFrame with NaN Kp summaries
  and `Kp_n = 0`
- aggregate by UTC date, matching the timestamps in the GFZ sources
- count valid 3-hourly readings in `Kp_n`; include dates with no readings as
  incomplete days with `Kp_n = 0`

The returned daily DataFrame should contain:

- `Kp_daily_max`
- `Kp_daily_mean`
- `Kp_n` — valid readings per day (0–8)
- `Kp_daily_sum` — sum when all eight readings are present, otherwise NaN

Keep Kp separate until its independent contribution and report presentation
have been evaluated. See [Independent Kp analysis](kp_analysis.md) for the
export command and future-join requirements. Any later join must be explicit,
keyed by UTC date, and must not silently add Kp to the risk score.

### `add_rolling_features(df)`

Adds smoothed indicators to the merged dataset for trend analysis.

The function should:

- compute rolling means for available columns among `pm2_5`, `pm10`, and `no2`
- use window sizes 3, 7, and 14 days
- use `min_periods=1` so the first rows are still populated
- add columns named `{column}_roll{window}d`

Rolling averages provide a simple way to capture short- and medium-term environmental trends without introducing excessive lag.

The function also computes these lag columns when their source columns are present:

- `delta_P`: 2, 5, 7, and 14 days
- `DTR`: 2, 7, and 14 days

The lag values use `shift()` and are not currently used by
`compute_risk_score()`. They are also omitted by `main.py` when selecting columns
for the saved CSV.

## Navigation

- [Overview](overview.md)
- [Config](config.md)
- [Main](main.md)
