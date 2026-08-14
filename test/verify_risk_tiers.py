"""Verify risk-tier assignments in the generated pipeline CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "environmental_data.csv"
REQUIRED_COLUMNS = {"risk_score", "risk_tier"}
ALLOWED_TIERS = {"low", "moderate", "high", "very_high", "unknown"}
RISK_CUTOFFS = (0.220, 0.300, 0.380)


def expected_risk_tier(score: float) -> str:
    """Classify a score independently from the production implementation."""
    if pd.isna(score):
        return "unknown"

    comparison_score = round(float(score), 12)
    if comparison_score < RISK_CUTOFFS[0]:
        return "low"
    if comparison_score < RISK_CUTOFFS[1]:
        return "moderate"
    if comparison_score <= RISK_CUTOFFS[2]:
        return "high"
    return "very_high"


def verify_pipeline_output(csv_path: str | Path = DEFAULT_CSV_PATH) -> bool:
    """Print tier statistics and return whether all assignments are valid."""
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"Pipeline output not found: {csv_path}")

    df = pd.read_csv(csv_path)
    missing_columns = REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required CSV columns: {missing}")

    print("=== RISK TIER DISTRIBUTION VERIFICATION ===")
    counts = df["risk_tier"].value_counts(dropna=False)
    percentages = df["risk_tier"].value_counts(normalize=True, dropna=False) * 100
    summary = pd.DataFrame(
        {"Count": counts, "Percentage (%)": percentages.round(1)}
    )
    print(summary)

    print("\n=== SCORE RANGE BY TIER ===")
    ranges = df.groupby("risk_tier", dropna=False)["risk_score"].agg(
        ["min", "mean", "max", "count"]
    )
    print(ranges)

    actual_tiers = df["risk_tier"].astype("string")
    expected_tiers = df["risk_score"].map(expected_risk_tier).astype("string")
    invalid_tier_mask = actual_tiers.isna() | ~actual_tiers.isin(ALLOWED_TIERS)
    mismatch_mask = actual_tiers.isna() | actual_tiers.ne(expected_tiers)
    invalid_score_mask = df["risk_score"].notna() & ~df["risk_score"].between(0, 1)

    is_valid = not (
        invalid_tier_mask.any()
        or mismatch_mask.any()
        or invalid_score_mask.any()
    )

    print("\n=== VALIDATION RESULT ===")
    if is_valid:
        print(f"PASS: all {len(df):,} rows have valid risk-tier assignments.")
        return True

    print("FAIL: pipeline output contains validation errors.")
    print(f"Invalid or missing tier values: {int(invalid_tier_mask.sum()):,}")
    print(f"Score/tier mismatches: {int(mismatch_mask.sum()):,}")
    print(f"Scores outside 0-1: {int(invalid_score_mask.sum()):,}")

    if mismatch_mask.any():
        mismatches = df.loc[mismatch_mask, ["risk_score", "risk_tier"]].copy()
        mismatches["expected_risk_tier"] = expected_tiers[mismatch_mask]
        print("\nFirst 10 score/tier mismatches:")
        print(mismatches.head(10).to_string(index=False))

    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify risk tiers in a generated environmental-data CSV."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"CSV to verify (default: {DEFAULT_CSV_PATH})",
    )
    args = parser.parse_args()

    try:
        return 0 if verify_pipeline_output(args.csv_path) else 1
    except (FileNotFoundError, ValueError, pd.errors.EmptyDataError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
