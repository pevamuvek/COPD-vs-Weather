# `report.py`

This module creates a human-readable quality report for the final merged dataset.

Patient-facing standalone HTML reports are generated separately by
`html_report.py`; see [HTML risk reports](report_html.md).

## Concept

The report documents data completeness and identifies gaps in the merged daily dataset. It is intended to be an audit artifact for anyone reviewing the generated outputs.

The quality report should be easy to read and should clearly show which columns are available and how much missing data exists.

## Behavior

### `quality_report(df, path)`

1. Build a header with:
   - a separator line
   - a title
   - the location label from `df.attrs`
   - the covered period from the date index
   - the total number of days in the dataset
2. Build a summary table for every column in the DataFrame, including:
   - non-null count
   - missing percentage
3. Add explanatory notes for known dataset characteristics:
   - `delta_P` is NaN on the first row because the value needs a prior day
   - rolling features are computed with `min_periods=1`
4. If `risk_score` is present, add a `FORECAST AND RISK SUMMARY` section after the completeness table:
   - report the number of rows with `is_forecast == True`
   - display `Date`, `Risk score`, and `Tier` for up to the first three forecast rows, sorted by date
   - if there are no forecast rows, display the last three rows sorted by date
   - identify unavailable features for forecast rows and retain the partial-score data coverage behavior specified in [Risk scoring](score.md)
   - on the highest-scoring row in the selected table, identify the single feature with the largest normalized weighted contribution to the score and include a one-line plain-language driver note
5. If `risk_score` is absent, omit the forecast and risk summary section silently.
6. Print the report text to stdout for immediate feedback.
7. Write the report to the provided `path` using UTF-8 encoding.
8. Print the saved path after writing.

The driver note must describe the primary available contributor, not the raw highest-weight feature when that feature is missing or has a lower normalized component. For pressure, include the signed `delta_P` value in hPa. Example:

```text
Elevated risk expected. Pressure change of -4.2 hPa is the primary driver.
```

Why UTF-8?

Writing the report in UTF-8 ensures it can be opened reliably across platforms and avoids encoding issues when the content contains non-ASCII text.

## Navigation

- [Overview](overview.md)
- [Main](main.md)
- [Dependencies](dependencies.md)
