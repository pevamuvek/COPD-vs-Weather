# `main.py`

This module orchestrates the full pipeline: fetching data, merging sources, adding derived features, saving outputs, and generating the data quality report.

## Concept

The pipeline is designed for reproducible data preparation. It focuses on:

- loading each source independently,
- aligning all data on the same daily index,
- preserving every calendar day using outer joins,
- computing derived trend features,
- writing outputs that are ready for analysis.

This is not a statistical or machine-learning modeling pipeline; it prepares environmental data and computes a transparent weighted risk index for later analysis.

## Dataset purpose

The merged dataset is intended to support environmental analysis and possible future event-window research:

- clinical event labeling and any approach to linking environmental data with events have not yet been defined
- preserve all calendar days so non-event periods are available for comparison
- low event count is a constraint for future research; model selection and validation are outside the current scope

## Imports

- From `config`: `LAT`, `LON`, `LOCATION_LABEL`, `START_DATE`, `END_DATE`, `OUTPUT_CSV`, `OUTPUT_REPORT`, `REPORT_DIR`
- From `fetchers`: `fetch_weather`, `fetch_air_quality`, `fetch_weather_forecast`, `fetch_kp_index`, `add_rolling_features`
- From `score`: `compute_risk_score`
- From `html_report`: `generate_daily_html_report`
- From `report`: `quality_report`

## Behavior

### `main()`

1. Print a clear banner describing the pipeline and date range.
2. Load datasets by calling the fetcher functions.
3. Merge the datasets using outer joins on the date index:
   - `weather` joined with `air quality`
   - then joined with `Kp` data
4. Append forecast rows and keep the first value for any duplicated date.
5. Add rolling means and compute explicit pressure/temperature lag features.
6. Compute the weighted risk score, risk tier, and risk label.
7. Attach the human-readable location label to `df.attrs['location_label']`.
8. Reorder columns for readability, with base features first and rolling features appended. The current output selection omits the computed pressure/temperature lag columns from the CSV.
9. Set the index name to `date`.
10. Write the merged dataset to `OUTPUT_CSV`.
11. Generate the quality report at `OUTPUT_REPORT`.
12. Generate the daily Hungarian HTML risk report in `REPORT_DIR`.
13. Print summary messages and return the final DataFrame.

Why outer joins?

Outer joins preserve the full date range and prevent loss of days when one source is missing data. This is important for creating a complete environmental record and for later analysis of missingness.

Why `df.attrs`?

The pipeline stores metadata such as the location label in `df.attrs` so that it can be used by `report.py` without changing the CSV schema.

## Script entrypoint

- If the script is executed as `__main__`, call `main()`.

## Navigation

- [Overview](overview.md)
- [Config](config.md)
- [Fetchers](fetchers.md)
- [Report](report.md)
