# `fetchers.py`

This module retrieves environmental time series from remote APIs, reshapes them into daily data, and adds rolling statistics.

## Concept

The pipeline uses multiple data sources to capture different environmental dimensions for the same location and date range.

Each fetcher returns a pandas `DataFrame` indexed by date. This design makes data joining predictable and preserves every calendar day across sources.

The final merged dataset is suitable for exploratory analysis, visualization, and modeling where environmental features are aligned by day.

## Data sources

- Open-Meteo daily weather archive for temperature, pressure, dew point, precipitation, and wind.
- Open-Meteo air quality API for hourly pollutant readings aggregated to daily means.
- GFZ Potsdam Kp index data for geomagnetic activity, with a JSON API first and a bulk file fallback.

## Feature rationale

The selected features are informed by COPD environmental risk research and the project conversation log:

- `DTR` highlights diurnal temperature swings, which are linked to respiratory stress in Hungary.
- `delta_P` captures the 24-hour barometric pressure change, a known trigger for COPD exacerbation.
- `pm2_5`, `pm10`, and `no2` represent air pollution stressors that can worsen lung function.
- `Kp_daily_max` and `Kp_daily_mean` introduce a geomagnetic stressor hypothesis, allowing later analysis of solar activity as a secondary trigger.
- rolling averages over 3, 7, and 14 days capture lagged and cumulative environmental exposure patterns.

These variables are consistent with the project’s academic benchmark goals and the data-driven risk window design.

## Imports

- `requests`
- `pandas as pd`
- `numpy as np`

## Constants

- `KP_URL = "https://www.gfz-potsdam.de/fileadmin/gfz/sec33/ap_kp_data/Kp_ap_since_1932.txt"`
- `KP_FALLBACK_URL = "https://kp.gfz-potsdam.de/app/json/?start={start}&end={end}&index=Kp&status=def"`

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

### `fetch_kp_index(start, end)`

Fetches geomagnetic Kp index values and aggregates them to daily summary statistics.

The function must be resilient:

- first attempt the GFZ JSON API
- if that fails, fall back to the bulk text data archive
- if both sources fail, return a date-indexed DataFrame with NaN Kp values

The returned daily DataFrame should contain:

- `Kp_daily_max`
- `Kp_daily_mean`

Why Kp is included:

Geomagnetic activity can be considered an environmental stressor. Including it allows downstream analysis to explore correlations between space weather, air quality, and respiratory outcomes.

### `add_rolling_features(df)`

Adds smoothed indicators to the merged dataset for trend analysis.

The function should:

- compute rolling means for available columns among `pm2_5`, `pm10`, `no2`, and `Kp_daily_max`
- use window sizes 3, 7, and 14 days
- use `min_periods=1` so the first rows are still populated
- add columns named `{column}_roll{window}d`

Rolling averages provide a simple way to capture short- and medium-term environmental trends without introducing excessive lag.

## Navigation

- [Overview](overview.md)
- [Config](config.md)
- [Main](main.md)
