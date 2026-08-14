# Spec — `score.py` Fix: Partial Feature Scoring
## Forecast rows must score on available features

**Project:** copd-vs-weather  
**Prepared for:** GitHub Copilot execution  
**Priority:** Blocker — fixes NaN risk scores on forecast rows  

---

## Instructions for Copilot

Do not fetch any URLs. Do not install any packages. Do not run any code.  
Show me the full updated `score.py` before applying anything.  
Wait for approval before writing to disk.

---

## Problem

Forecast rows have valid weather features (DTR, delta_P, dew_point_2m_mean) but missing AQ values (pm2_5, pm10, no2) and missing Kp values. The current scoring logic returns NaN for any row where required columns are NaN, leaving forecast rows unscored.

---

## Required behaviour

Score every row using whatever features are available.  
Missing features contribute zero to the composite score — they do not block scoring.  
A row with only weather features scores on weather features alone.  
A row with weather + AQ scores on both.  
A fully populated row scores on everything.

---

## Scoring logic

### Feature weights

These weights must be preserved exactly — they reflect clinical grounding from Márovics et al. 2024.

| Feature | Weight |
|---|---|
| `delta_P` (absolute value, hPa) | 0.25 |
| `DTR` (°C) | 0.20 |
| `dew_point_2m_mean` (°C, inverted — lower is riskier) | 0.15 |
| `pm2_5` (µg/m³) | 0.15 |
| `no2` (µg/m³) | 0.10 |
| `pm10` (µg/m³) | 0.05 |
| `Kp_daily_max` | 0.10 |

### Normalisation

Each feature is normalised to 0–1 using fixed reference ranges before weighting:

| Feature | Min | Max |
|---|---|---|
| `delta_P` (abs) | 0 | 20 |
| `DTR` | 0 | 25 |
| `dew_point_2m_mean` | -20 | 30 (inverted: score = 1 - normalised) |
| `pm2_5` | 0 | 75 |
| `no2` | 0 | 100 |
| `pm10` | 0 | 150 |
| `Kp_daily_max` | 0 | 9 |

Clip normalised values to [0, 1] before applying weights.

### Partial scoring logic

```python
def compute_row_score(row, feature_weights, feature_ranges):
    total_weight = 0.0
    weighted_sum = 0.0

    for feature, weight in feature_weights.items():
        value = row.get(feature)
        if value is None or pd.isna(value):
            continue  # skip missing features, do not add weight

        min_val, max_val = feature_ranges[feature]
        normalised = (value - min_val) / (max_val - min_val)
        normalised = max(0.0, min(1.0, normalised))

        # Invert dew point: lower dew point = higher risk
        if feature == "dew_point_2m_mean":
            normalised = 1.0 - normalised

        weighted_sum += normalised * weight
        total_weight += weight

    if total_weight == 0:
        return float("nan")  # no scoreable features at all

    # Rescale to available weights so score stays on 0–1 range
    return weighted_sum / total_weight
```

### Risk tier mapping

| Score | Tier | Label |
|---|---|---|
| 0.0 – 0.33 | `low` | Low risk |
| 0.34 – 0.66 | `moderate` | Moderate risk |
| 0.67 – 1.0 | `high` | High risk |
| NaN | `unknown` | Insufficient data |

---

## Output columns

`score.py` must populate these three columns for every row where at least one feature is non-null:

- `risk_score` — float, 0–1
- `risk_tier` — string: `low` / `moderate` / `high` / `unknown`
- `risk_label` — string: `Low risk` / `Moderate risk` / `High risk` / `Insufficient data`

---

## Data coverage note in output

When forecast rows are scored on partial features, add a note to the quality report indicating which features were missing. Example:

```
2026-06-11: scored on weather features only (pm2_5, pm10, no2, Kp unavailable)
2026-06-12: scored on weather features only (pm2_5, pm10, no2, Kp unavailable)
```

---

## Acceptance criteria

Copilot task is complete when:

- [ ] Forecast rows (is_forecast = True) have non-null `risk_score`, `risk_tier`, `risk_label`
- [ ] Historical rows score identically to before (no regression)
- [ ] A row with all features NaN returns `risk_tier = unknown`
- [ ] Score stays within 0–1 range for all rows
- [ ] Quality report notes which features were missing for forecast rows
