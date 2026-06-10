"""
Daily composite risk score for COPD environmental stressors.

Combines normalized stressor signals into a transparent 0–1 index
suitable for non-technical users and public dashboard display.
"""

import pandas as pd
import numpy as np

# Feature weights (reflecting clinical grounding from Márovics et al. 2024)
RISK_WEIGHTS = {
    "delta_P": 0.25,
    "DTR": 0.20,
    "dew_point_2m_mean": 0.15,
    "pm2_5": 0.15,
    "no2": 0.10,
    "pm10": 0.05,
    "Kp_daily_max": 0.10,
}

# Fixed reference ranges for normalization [min, max]
FEATURE_RANGES = {
    "delta_P": (0, 20),
    "DTR": (0, 25),
    "dew_point_2m_mean": (-20, 30),
    "pm2_5": (0, 75),
    "no2": (0, 100),
    "pm10": (0, 150),
    "Kp_daily_max": (0, 9),
}

RISK_TIER_LABELS = {
    "low": "Low risk",
    "moderate": "Moderate risk",
    "high": "High risk",
    "unknown": "Insufficient data",
}


def compute_row_score(row, feature_weights, feature_ranges):
    """
    Compute risk score for a single row using available features.
    
    Missing features contribute zero weight — they do not block scoring.
    A row with only weather features scores on weather features alone.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for feature, weight in feature_weights.items():
        value = row.get(feature)
        if value is None or pd.isna(value):
            continue  # skip missing features, do not add weight

        # Use absolute value for delta_P
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


def get_missing_features(row, feature_weights):
    """Return list of missing features for a given row."""
    missing = []
    for feature in feature_weights.keys():
        value = row.get(feature)
        if value is None or pd.isna(value):
            missing.append(feature)
    return missing


def compute_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily composite risk score from normalized stressor signals.
    
    Scores every row using available features. Missing features contribute
    zero to the composite score — they do not block scoring.
    
    Returns df with added columns: risk_score, risk_tier, risk_label.
    Stores missing_features_log in df.attrs for quality reporting.
    """
    df = df.copy()
    
    # Initialize result columns
    risk_scores = []
    risk_tiers = []
    risk_labels = []
    missing_features_log = []
    
    for idx, row in df.iterrows():
        # Compute score using available features
        score = compute_row_score(row, RISK_WEIGHTS, FEATURE_RANGES)
        risk_scores.append(score)
        
        # Assign risk tier and label
        if pd.isna(score):
            risk_tiers.append("unknown")
            risk_labels.append(RISK_TIER_LABELS["unknown"])
        elif score < 0.34:
            risk_tiers.append("low")
            risk_labels.append(RISK_TIER_LABELS["low"])
        elif score <= 0.66:
            risk_tiers.append("moderate")
            risk_labels.append(RISK_TIER_LABELS["moderate"])
        else:
            risk_tiers.append("high")
            risk_labels.append(RISK_TIER_LABELS["high"])
        
        # Track missing features for quality reporting
        missing = get_missing_features(row, RISK_WEIGHTS)
        missing_features_log.append(missing)
    
    df["risk_score"] = risk_scores
    df["risk_tier"] = risk_tiers
    df["risk_label"] = risk_labels
    
    # Store missing features log for quality report
    df.attrs["missing_features_log"] = missing_features_log
    
    return df
