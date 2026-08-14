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
    "low": "Low Risk",
    "moderate": "Moderate Risk",
    "high": "High Risk",
    "very_high": "Very High Risk",
    "unknown": "Insufficient data",
}

# Empirically derived boundaries for the 4-tier hybrid risk model.
RISK_CUTOFFS = (0.220, 0.300, 0.380)


def classify_risk_score(score):
    """Return the risk tier for a score using the 4-tier hybrid model."""
    if pd.isna(score):
        return "unknown"

    # Stabilize decimal cutoff comparisons after floating-point normalization.
    comparison_score = round(float(score), 12)
    if comparison_score < RISK_CUTOFFS[0]:
        return "low"
    if comparison_score < RISK_CUTOFFS[1]:
        return "moderate"
    if comparison_score <= RISK_CUTOFFS[2]:
        return "high"
    return "very_high"


def compute_feature_contributions(row, feature_weights, feature_ranges):
    """Return each available feature's rescaled contribution to the score."""
    raw_contributions = {}
    total_weight = 0.0

    for feature, weight in feature_weights.items():
        value = row.get(feature)
        if value is None or pd.isna(value):
            continue

        if feature == "delta_P":
            value = abs(value)

        min_val, max_val = feature_ranges[feature]
        normalised = (value - min_val) / (max_val - min_val)
        normalised = max(0.0, min(1.0, normalised))
        if feature == "dew_point_2m_mean":
            normalised = 1.0 - normalised

        raw_contributions[feature] = normalised * weight
        total_weight += weight

    if total_weight == 0:
        return {}

    return {
        feature: contribution / total_weight
        for feature, contribution in raw_contributions.items()
    }


def compute_row_score(row, feature_weights, feature_ranges):
    """
    Compute risk score for a single row using available features.

    Missing features contribute zero weight — they do not block scoring.
    A row with only weather features scores on weather features alone.
    """
    contributions = compute_feature_contributions(
        row, feature_weights, feature_ranges
    )
    if not contributions:
        return float("nan")
    return sum(contributions.values())

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
        tier = classify_risk_score(score)
        risk_tiers.append(tier)
        risk_labels.append(RISK_TIER_LABELS[tier])
        
        # Track missing features for quality reporting
        missing = get_missing_features(row, RISK_WEIGHTS)
        missing_features_log.append(missing)
    
    df["risk_score"] = risk_scores
    df["risk_tier"] = risk_tiers
    df["risk_label"] = risk_labels
    
    # Store missing features log for quality report
    df.attrs["missing_features_log"] = missing_features_log
    
    return df
