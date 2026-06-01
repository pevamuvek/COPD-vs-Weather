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

    # Forecast and risk summary
    if "risk_score" in df.columns:
        import pandas as pd
        from score import RISK_WEIGHTS
        import numpy as np
        
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
                lines.append(f"{date.date():<12} {score_str:>12} {tier_str:>10}")
            
            # Identify primary driver on peak day
            peak_day = df_forecast_view.loc[df_forecast_view['risk_score'].idxmax()]
            peak_score = peak_day['risk_score']
            
            if pd.notna(peak_score):
                # Recompute normalized components to find the highest contributor
                peak_features = {}
                is_hist = ~df.get("is_forecast", False)
                
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

    report = "\n".join(lines)
    print("\n" + report)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Report saved → {path}")
