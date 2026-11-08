# Spec additions — predictive features

These additions extend the existing pipeline to support a 1–2 day forward risk signal.
They are scoped for a demo that a non-technical user can read and that can be published on GitHub.

Each section maps to one existing or new specification file and states exactly what must be added or changed.

---

## 1. `fetchers.md` — add `fetch_weather_forecast()`

Add a new function after `fetch_air_quality`.

### Purpose

Extends the daily DataFrame beyond today using Open-Meteo's free forecast endpoint.
This is what makes a 1–2 day risk preview possible without any machine learning.

### Signature

```python
fetch_weather_forecast(lat, lon, days=3)
```

### Behaviour

- Print a progress message for visibility.
- Call the Open-Meteo forecast endpoint:
  `https://api.open-meteo.com/v1/forecast`
  with `daily` parameter requesting the same fields used in `fetch_weather`:
  `temperature_2m_max`, `temperature_2m_min`, `surface_pressure_mean`,
  `dew_point_2m_mean`, `precipitation_sum`, `windspeed_10m_max`.
- Set `forecast_days` to `days` (default 3 to cover today + 2 ahead).
- Parse the JSON response and convert `time` to a datetime index named `date`.
- Compute derived features identically to `fetch_weather`:
  - `DTR = temperature_2m_max - temperature_2m_min`
  - `delta_P = surface_pressure_mean.diff()`
- Add a boolean column `is_forecast = True` on every row.
- Return the DataFrame indexed by `date`.

### Integration point

In `main.py`, after the historical merge, concatenate the forecast rows:

```python
df = pd.concat([df, forecast_df])
df = df[~df.index.duplicated(keep='first')]
```

This ensures today is not doubled if the archive already contains it.

### Requirements

- No new dependencies. Uses `requests` and `pandas` already in the project.
- `is_forecast` must be preserved in `OUTPUT_CSV` so downstream tools can filter it.
- `delta_P` will be NaN on the first forecast day if it immediately follows the last
  archive day; this is acceptable and must be noted in `report.py`.

---

## 2. `fetchers.md` — explicit lag columns (CSV retention still pending)

### Purpose

Rolling averages smooth the signal but lose the timing information the Pécs Study (2024)
identified as clinically relevant: pressure and temperature shocks 2–14 days before
an exacerbation. Named lag columns make this window explicit and inspectable.

### Change to `add_rolling_features(df)`

After computing rolling means, add explicit lag columns for the two primary shock features:

| New column        | Source column          | Lag |
|-------------------|------------------------|-----|
| `delta_P_lag2d`   | `delta_P`              | 2 days |
| `delta_P_lag5d`   | `delta_P`              | 5 days |
| `delta_P_lag7d`   | `delta_P`              | 7 days |
| `delta_P_lag14d`  | `delta_P`              | 14 days |
| `DTR_lag2d`       | `DTR`                  | 2 days |
| `DTR_lag7d`       | `DTR`                  | 7 days |
| `DTR_lag14d`      | `DTR`                  | 14 days |

Use `df[col].shift(n)` for each lag. NaN values on the first N rows are expected and correct.

### Requirements

- Only add a lag column when the source column is present in `df`; use `if col in df.columns`.
- Column naming must follow the pattern `{source_col}_lag{n}d` exactly for downstream
  compatibility.
- The feature builder computes these columns, but the current `main.py` output
selection omits them from the CSV. Persisting them after the rolling mean
columns remains an implementation requirement if downstream analysis needs
them.

---

## 3. Daily environmental risk score and tiers

The original score design in this proposal has been superseded by the current
implementation in `src/score.py` and its specification in
[spec_score_fix.md](spec_score_fix.md). The current score uses the fixed feature
weights and reference ranges documented there, scores with available features,
and is an environmental index—not an event probability or a learned model.

The current four-tier cutoffs are anchored to the observed score distribution
in the 2015–2026 historical dataset:

| Tier | `risk_score` |
|---|---|
| `low` | `< 0.220` |
| `moderate` | `0.220` to `< 0.300` |
| `high` | `0.300` to `0.380` |
| `very_high` | `> 0.380` |
| `unknown` | Score is missing |

These are heuristic, distribution-based thresholds, not clinically validated
limits. The tier definitions are also specified in
[report_html.md](report_html.md#four-tier-display).

---

## 4. `report.md` — extend quality report with forecast and risk summary

### Addition to `quality_report(df, path)`

After the existing completeness table, add a second section:

**Forecast and risk summary**

- How many rows have `is_forecast == True`.
- The `risk_tier` and `risk_score` for today and the next two forecast days,
  formatted as a small table:

  ```
  Date         Risk score   Tier
  2025-06-01   0.71         high
  2025-06-02   0.58         moderate
  2025-06-03   0.44         moderate
  ```

- A one-line plain-language note: e.g.
  `"Elevated risk expected tomorrow. Pressure drop of -4.2 hPa is the primary driver."`

This note is the output intended for a non-technical reader (demo audience A).

### Requirements

- The risk summary section must only be written if `risk_score` is present in `df`.
  If `score.py` has not been run, the report falls back to the existing behaviour silently.
- The plain-language note must identify the single highest-weighted contributing feature
  by inspecting which normalised component contributed most to the score on the peak day.

---

## 5. `main.md` — orphaned references (resolved)

The following items previously appeared in the "Dataset purpose" section of
`main.md` without specifications:

- `viral_cofactor` — remove from the bullet list or add a stub specification.
- `uncertain event flags` — same.

Both references have been removed from `main.md`. They can be reconsidered
after an event-labeling approach is defined.
