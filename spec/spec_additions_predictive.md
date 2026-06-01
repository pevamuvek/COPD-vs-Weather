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

## 2. `fetchers.md` — extend `add_rolling_features()` with explicit lag columns

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
- These columns must appear in the CSV after the rolling mean columns.

---

## 3. New file: `score.md` — daily composite risk index

Add `code/score.py` and its specification `docs/score.md`.

### Purpose

Translates the multi-feature daily DataFrame into a single 0–1 risk score per day.
This is the output a non-technical user (or a GitHub visitor) can understand at a glance.
No machine learning is required for the demo version; the score is a transparent
weighted sum of normalised stressor signals.

### Function: `compute_risk_score(df)`

#### Input

The fully merged and feature-engineered DataFrame produced by `main.py`.

#### Algorithm (demo version — no model required)

1. Select the following input columns (skip any that are NaN or missing):
   - `delta_P` (absolute value — direction does not matter, magnitude does)
   - `DTR`
   - `pm2_5_roll3d`
   - `no2_roll3d`
   - `dew_point_2m_mean`

2. For each column, compute a min-max normalisation using the historical range
   (i.e. the rows where `is_forecast == False` or column is absent):
   ```
   normalised = (x - x_hist_min) / (x_hist_max - x_hist_min)
   ```
   Clip to [0, 1].

3. Apply fixed weights (sum to 1.0):

   | Feature            | Weight | Rationale |
   |--------------------|--------|-----------|
   | `abs(delta_P)`     | 0.30   | Primary pressure shock trigger |
   | `DTR`              | 0.25   | Temperature fluctuation stress (Pécs Study) |
   | `pm2_5_roll3d`     | 0.20   | Cumulative fine particle load |
   | `no2_roll3d`       | 0.15   | Pollution–front synergy |
   | `dew_point_2m_mean`| 0.10   | Humid heat discomfort |

4. Compute `risk_score = weighted_sum` of available normalised inputs,
   re-normalising weights to 1.0 if any input is missing.

5. Add three columns to `df`:
   - `risk_score` (float, 0–1)
   - `risk_tier` (string: `"low"` < 0.35, `"moderate"` 0.35–0.65, `"high"` > 0.65)
   - `risk_label` (human-readable string for display, e.g. `"Low — conditions stable"`)

6. Return the updated DataFrame.

#### Output columns

| Column        | Type   | Range  | Description |
|---------------|--------|--------|-------------|
| `risk_score`  | float  | 0–1    | Composite daily risk index |
| `risk_tier`   | string | —      | `low` / `moderate` / `high` |
| `risk_label`  | string | —      | Plain-language summary |

### Integration point in `main.py`

After `add_rolling_features`, call:

```python
from score import compute_risk_score
df = compute_risk_score(df)
```

### Requirements

- No new dependencies beyond `pandas` and `numpy`.
- Weights must be defined as a named constant dict at the top of `score.py`
  so they are easy to update after model fitting.
- The function must not raise an exception if some input columns are missing;
  it must degrade gracefully by skipping missing features.
- The normalisation baseline must use only historical rows (`is_forecast == False`)
  to prevent future values from contaminating the scale.

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

## 5. `main.md` — remove orphaned references

The following items appear in the "Dataset purpose" section of `main.md` but have no
specification anywhere in the project. They must either be specified or removed to keep
the spec implementable:

- `viral_cofactor` — remove from the bullet list or add a stub specification.
- `uncertain event flags` — same.

**Recommended action for demo scope:** remove both references from `main.md`.
They can be re-added later when the EESZT label pipeline is specified.
