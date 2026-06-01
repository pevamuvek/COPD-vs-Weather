# `main.py`

This module orchestrates the full pipeline: fetching data, merging sources, adding derived features, saving outputs, and generating the data quality report.

## Concept

The pipeline is designed for reproducible data preparation. It focuses on:

- loading each source independently,
- aligning all data on the same daily index,
- preserving every calendar day using outer joins,
- computing derived trend features,
- writing outputs that are ready for analysis.

This is not a custom modeling pipeline; it is a reliable data preparation layer for environmental and COPD-related analysis.

## Dataset purpose

The merged dataset is intended to support later COPD risk modeling and event-window analysis:

- create labels for hospitalization risk windows (event day plus two prior days)
- preserve all calendar days so non-event periods are available for comparison
- preserve all calendar days so non-event periods are available for model training
- provide a reproducible foundation for Random Forest / XGBoost modeling and bootstrap validation

## Imports

- From `config`: `LAT`, `LON`, `LOCATION_LABEL`, `START_DATE`, `END_DATE`, `OUTPUT_CSV`, `OUTPUT_REPORT`
- From `fetchers`: `fetch_weather`, `fetch_air_quality`, `fetch_weather_forecast`, `fetch_kp_index`, `add_rolling_features`
- From `report`: `quality_report`

## Behavior

### `main()`

1. Print a clear banner describing the pipeline and date range.
2. Load datasets by calling the fetcher functions.
3. Merge the datasets using outer joins on the date index:
   - `weather` joined with `air quality`
   - then joined with `Kp` data
4. Add rolling features to the merged table.
5. Attach the human-readable location label to `df.attrs['location_label']`.
6. Reorder columns for readability, with base features first and rolling features appended.
7. Set the index name to `date`.
8. Write the merged dataset to `OUTPUT_CSV`.
9. Generate the quality report at `OUTPUT_REPORT`.
10. Print summary messages and return the final DataFrame.

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
