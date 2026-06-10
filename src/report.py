import pandas as pd
import numpy as np
from score import RISK_WEIGHTS

def historical_context(df: pd.DataFrame) -> list[str]:
    """Generate historical baseline stats for forecast comparison."""
    lines = []
    
    # Filter historical rows only, drop forecast
    hist = df[~df["is_forecast"].fillna(False).astype(bool)].copy()
    hist = hist[pd.notna(hist["risk_score"])]
    
    if len(hist) == 0:
        return ["No historical risk scores available for context."]
    
    # Last 30 and 90 days
    last_30 = hist.tail(30)
    last_90 = hist.tail(90)
    
    avg_30 = last_30["risk_score"].mean()
    avg_90 = last_90["risk_score"].mean()
    
    max_30_score = last_30["risk_score"].max()
    max_30_date = last_30["risk_score"].idxmax()
    
    mod_plus_30 = (last_30["risk_score"] >= 0.34).sum()
    mod_plus_90 = (last_90["risk_score"] >= 0.34).sum()
    
    def tier(score):
        if score < 0.34: return "low"
        elif score <= 0.66: return "moderate"
        else: return "high"
    
    lines.append("HISTORICAL CONTEXT")
    lines.append("-" * 35)
    lines.append(f"30-day avg  : {avg_30:.2f} ({tier(avg_30)})")
    lines.append(f"90-day avg  : {avg_90:.2f} ({tier(avg_90)})")
    lines.append(f"Recent high : {max_30_score:.2f} on {str(max_30_date.date())}")
    lines.append(f"Moderate+   : {mod_plus_30}/30 days last month, {mod_plus_90}/90 last quarter")
    lines.append("")
    
    return lines
def quality_report(df, path):
    lines = []
    lines.append("=" * 60)
    lines.append("COPD ENVIRONMENTAL DATA — QUALITY REPORT")
    lines.append(f"Location : {df.attrs.get('location_label', 'Unknown')}")
    lines.append(f"Period   : {df.index.min().date()} → {df.index.max().date()}")
    lines.append(f"Total days: {len(df)}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{'Column':<35} {'Non-null':>8} {'Missing%':>9}")
    lines.append("-" * 55)
    for col in df.columns:
        nn = df[col].notna().sum()
        pct = (df[col].isna().sum() / len(df)) * 100
        lines.append(f"{col:<35} {nn:>8}   {pct:>7.1f}%")
    lines.append("")
    lines.append("Notes:")
    lines.append("  delta_P row 0 is NaN by design (no prior day).")
    lines.append("  Kp NaN = GFZ source unavailable; add manually if needed.")
    lines.append("  Rolling windows use min_periods=1 to avoid leading NaNs.")

    # Compute 30-day mean for trend arrows
    hist = df[~df["is_forecast"].fillna(False).astype(bool)]
    hist = hist[pd.notna(hist["risk_score"])]
    hist_scores_mean = hist.tail(30)["risk_score"].mean()

    # Add historical context block
    lines += historical_context(df)
    
    # Forecast and risk summary
    if "risk_score" in df.columns:
        
        lines.append("")
        lines.append("FORECAST AND RISK SUMMARY")
        lines.append("-" * 55)
        
        forecast_rows = (df.get("is_forecast", False) == True).sum()
        lines.append(f"Forecast rows: {forecast_rows}")
        lines.append("")
        
        df_forecast_view = df.loc[df.get("is_forecast", False) == True].sort_index()
        if len(df_forecast_view) == 0:
            df_sorted = df.sort_index()
            df_forecast_view = df_sorted.iloc[-3:]
        else:
            df_forecast_view = df_forecast_view.head(3)
        
        if len(df_forecast_view) > 0:
            lines.append(f"{'Date':<12} {'Risk score':>12} {'Tier':>10}")
            lines.append("-" * 35)
            for date, row in df_forecast_view.iterrows():
                score_str = f"{row['risk_score']:.2f}" if pd.notna(row['risk_score']) else "NaN"
                tier_str = str(row.get('risk_tier', 'N/A'))
                avg_30 = hist_scores_mean
                if pd.notna(row['risk_score']):
                    if row['risk_score'] > avg_30 + 0.05:
                        trend = "↑"
                    elif row['risk_score'] < avg_30 - 0.05:
                        trend = "↓"
                    else:
                        trend = "→"
                else:
                    trend = ""
                lines.append(f"{str(date.date()):<12} {score_str:>12} {tier_str:>10}  {trend}")
            
            # Display data coverage notes for forecast rows
            if "missing_features_log" in df.attrs:
                missing_features_log = df.attrs["missing_features_log"]
                lines.append("")
                lines.append("Data coverage (forecast rows):")
                
                # Get indices of forecast rows in the original dataframe
                forecast_indices = df[df.get("is_forecast", False) == True].index.tolist()
                for date, idx_in_view in zip(df_forecast_view.index, df_forecast_view.index):
                    # Find position of this date in the full dataframe
                    pos_in_full_df = df.index.get_loc(date)
                    if pos_in_full_df < len(missing_features_log):
                        missing = missing_features_log[pos_in_full_df]
                        if missing:
                            available = [f for f in RISK_WEIGHTS.keys() if f not in missing]
                            lines.append(f"  {date.date()}: scored on {', '.join(available) if available else 'no features'} ({', '.join(missing)} unavailable)")
            
            valid_scores = df_forecast_view['risk_score'].dropna()
            if len(valid_scores) > 0:
                # Identify primary driver on peak day
                peak_day = df_forecast_view.loc[valid_scores.idxmax()]
                peak_score = peak_day['risk_score']
                
                if pd.notna(peak_score):
                    # Recompute normalized components to find the highest contributor
                    peak_features = {}
                    is_hist = ~df["is_forecast"].fillna(False).astype(bool)
                    
                    for feature, weight in RISK_WEIGHTS.items():
                        if feature not in df.columns or pd.isna(peak_day[feature]):
                            continue
                        
                        value = abs(peak_day[feature]) if feature == "delta_P" else peak_day[feature]
                        hist_values = df.loc[is_hist, feature].copy()
                        if feature == "delta_P":
                            hist_values = hist_values.abs()
                        
                        if len(hist_values) > 0 and not hist_values.isna().all():
                            hist_min = hist_values.min()
                            hist_max = hist_values.max()
                            if hist_max != hist_min:
                                normalized = (value - hist_min) / (hist_max - hist_min)
                                normalized = min(1.0, max(0.0, normalized))
                                peak_features[feature] = normalized * weight
                    
                    if peak_features:
                        top_driver = max(peak_features, key=peak_features.get)
                        driver_value = peak_day[top_driver]
                        
                        if top_driver == "delta_P":
                            lines.append(f"\nElevated risk expected. Pressure change of {driver_value:.1f} hPa is the primary driver.")
                        else:
                            lines.append(f"\nElevated risk expected. {top_driver} = {driver_value:.1f} is the primary driver.")
            else:
                lines.append("\nNo valid forecast risk score is available for the selected days.")

    report = "\n".join(lines)
    print("\n" + report)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Report saved → {path}")
