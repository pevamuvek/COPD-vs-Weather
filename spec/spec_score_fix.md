# `score.py` — Partial Feature Scoring

This document records the implemented partial-feature scoring behavior. The
current risk-tier cutoffs are documented in
[report_html.md](report_html.md#four-tier-display); the earlier three-tier
thresholds in this historical fix proposal have been replaced.

**Project:** copd-vs-weather
**Scope:** Weighted environmental index; no statistical or machine-learning model

---

## Problem

Forecast rows can have valid weather features (DTR, delta_P, dew_point_2m_mean)
while AQ and Kp features are unavailable. The partial-scoring behavior below
allows those rows to be scored using their available features.

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
| `< 0.220` | `low` | Low Risk |
| `0.220` to `< 0.300` | `moderate` | Moderate Risk |
| `0.300` to `0.380` | `high` | High Risk |
| `> 0.380` | `very_high` | Very High Risk |
| NaN | `unknown` | Insufficient data |

The boundaries are anchored to the observed distribution of scores in the
2015–2026 historical dataset, approximately the 28th, 72nd, and 93rd
percentiles. They are heuristic thresholds, not clinically validated limits.

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
2026-06-11: scored on weather features only (pm2_5, pm10, no2, Kp unavailable)
2026-06-12: scored on weather features only (pm2_5, pm10, no2, Kp unavailable)
```

---

## Expected behavior

- Forecast rows with available score features receive a score, tier, and label.
- A row with all score features missing receives a NaN score and `unknown` tier.
- Scores remain within the 0–1 range.
- The quality report identifies unavailable score features for forecast rows.
