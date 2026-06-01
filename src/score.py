"""
Daily composite risk score for COPD environmental stressors.

Combines normalized stressor signals into a transparent 0–1 index
suitable for non-technical users and public dashboard display.
"""

import pandas as pd
import numpy as np

RISK_WEIGHTS = {
    "delta_P": 0.30,
    "DTR": 0.25,
    "pm2_5_roll3d": 0.20,
    "no2_roll3d": 0.15,
    "dew_point_2m_mean": 0.10,
}

RISK_TIER_LABELS = {
    "low": "Low — conditions stable",
    "moderate": "Moderate — elevated caution advised",
    "high": "High — significant risk, limit outdoor activity",
}


def compute_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute daily composite risk score from normalized stressor signals.
    
    Applies min-max normalization using historical baseline (is_forecast == False),
    then weighted sum with graceful handling of missing features.
    
    Returns df with added columns: risk_score, risk_tier, risk_label.
    """
    df = df.copy()
    
    # Separate historical from forecast for baseline normalization
    if "is_forecast" in df.columns:
        is_hist = ~df["is_forecast"].astype(bool)
    else:
        is_hist = pd.Series(True, index=df.index)
    
    # Initialize result columns
    risk_scores = []
    
    for idx, row in df.iterrows():
        available_features = {}
        available_weights = {}
        
        for feature, weight in RISK_WEIGHTS.items():
            if feature not in df.columns or pd.isna(row[feature]):
                continue
            
            # Use absolute value for delta_P (magnitude matters, not direction)
            value = abs(row[feature]) if feature == "delta_P" else row[feature]
            
            # Get historical range for normalization
            hist_values = df.loc[is_hist, feature].copy()
            if feature == "delta_P":
                hist_values = hist_values.abs()
            
            if len(hist_values) == 0 or hist_values.isna().all():
                continue
            
            hist_min = hist_values.min()
            hist_max = hist_values.max()
            
            # Min-max normalization, clip to [0, 1]
            if hist_max == hist_min:
                normalized = 0.0
            else:
                normalized = (value - hist_min) / (hist_max - hist_min)
                normalized = np.clip(normalized, 0.0, 1.0)
            
            available_features[feature] = normalized
            available_weights[feature] = weight
        
        # Compute weighted sum, re-normalizing weights if features are missing
        if len(available_features) == 0:
            risk_score = np.nan
        else:
            total_weight = sum(available_weights.values())
            risk_score = sum(
                available_features[f] * available_weights[f] / total_weight
                for f in available_features
            )
        
        risk_scores.append(risk_score)
    
    df["risk_score"] = risk_scores
    
    # Assign risk tiers and labels
    df["risk_tier"] = df["risk_score"].apply(
        lambda x: (
            "low" if x < 0.35
            else "high" if x > 0.65
            else "moderate"
        ) if pd.notna(x) else np.nan
    )
    
    df["risk_label"] = df["risk_tier"].map(RISK_TIER_LABELS)
    
    return df
