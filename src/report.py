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

    report = "\n".join(lines)
    print("\n" + report)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Report saved → {path}")
