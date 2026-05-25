# `report.py`

This module creates a human-readable quality report for the final merged dataset.

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
   - `Kp` may be missing if the GFZ source was unavailable
   - rolling features are computed with `min_periods=1`
4. Print the report text to stdout for immediate feedback.
5. Write the report to the provided `path` using UTF-8 encoding.
6. Print the saved path after writing.

Why UTF-8?

Writing the report in UTF-8 ensures it can be opened reliably across platforms and avoids encoding issues when the content contains non-ASCII text.

## Navigation

- [Overview](overview.md)
- [Main](main.md)
- [Dependencies](dependencies.md)
