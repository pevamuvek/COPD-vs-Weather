# `score.py` — Kp-Independent Risk Scoring

This document defines the Kp-independent weighted environmental index,
including partial-feature scoring and the empirical tier boundaries.

**Project:** copd-vs-weather
**Scope:** Weighted environmental index; no statistical or machine-learning model

---

## Problem

Forecast rows can have valid weather features (DTR, delta_P, dew_point_2m_mean)
while air-quality features are unavailable. The partial-scoring behavior below
allows those rows to be scored using their available features. Kp is not an
input to this score; it is fetched and analyzed independently.

---

## Required behaviour

Score every row using whatever features are available.  
Missing features are skipped and the remaining weights are rescaled; they do not block scoring.
A row with only weather features scores on weather features alone.  
A row with weather + AQ scores on both.  
A fully populated row scores on everything.

---

## Scoring logic

### Feature weights

These weights are the previous non-Kp weights divided by their previous total
of 0.90. They now sum to 1.0; this is a heuristic environmental index, not a
clinically validated model.

The common normalization of all six weights does not by itself change a row's
score because the available weights are also rescaled per row. Excluding Kp is
the change that alters the score. Partial rows still use only their available
features, so coverage must be considered when interpreting comparisons.

| Feature | Weight |
|---|---|
| `delta_P` (absolute value, hPa) | `5/18` (0.2777777778) |
| `DTR` (°C) | `2/9` (0.2222222222) |
| `dew_point_2m_mean` (°C, inverted — lower is riskier) | `1/6` (0.1666666667) |
| `pm2_5` (µg/m³) | `1/6` (0.1666666667) |
| `no2` (µg/m³) | `1/9` (0.1111111111) |
| `pm10` (µg/m³) | `1/18` (0.0555555556) |

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

        if feature == "delta_P":
            value = abs(value)

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
| `< 0.2229342593` | `low` | Low Risk |
| `0.2229342593` to `< 0.3014978395` | `moderate` | Moderate Risk |
| `0.3014978395` to `0.3772552469` | `high` | High Risk |
| `> 0.3772552469` | `very_high` | Very High Risk |
| NaN | `unknown` | Insufficient data |

The boundaries are the 28th, 72nd, and 93rd percentiles of the Kp-free score
computed on 2,516 non-forecast daily rows from 2020-01-01 through 2026-11-20.
Linear percentile interpolation gives cutoffs of 0.2229342593, 0.3014978395,
and 0.3772552469. These are distribution-based heuristic thresholds, not
clinically validated limits. Recalculate and document them if the weights,
feature ranges, scoring behavior, or historical baseline changes.

---

## Output columns

`score.py` must populate these three columns for every row where at least one feature is non-null:

- `risk_score` — float, 0–1
- `risk_tier` — string: `low` / `moderate` / `high` / `very_high` / `unknown`
- `risk_label` — display label corresponding to the assigned tier

---

## Data coverage note in output

When forecast rows are scored on partial features, add a note to the quality report indicating which features were missing. Example:

```
2026-06-11: scored on weather features only (pm2_5, pm10, no2 unavailable)
2026-06-12: scored on weather features only (pm2_5, pm10, no2 unavailable)
```

---

## Expected behavior

- Forecast rows with available score features receive a score, tier, and label.
- A row with all score features missing receives a NaN score and `unknown` tier.
- Scores remain within the 0–1 range.
- The quality report identifies unavailable score features for forecast rows.
