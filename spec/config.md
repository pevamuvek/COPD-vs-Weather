# `config.py`

This module contains the static configuration values and output path setup for the pipeline.

It is intentionally simple: no data fetching or transformation belongs here. Its only responsibilities are:

- define the Budapest coordinates used by all API calls
- set a fixed start date and a dynamic end date
- construct the `data/` directory path relative to `code/`
- create the directory when the module is imported
- expose output file paths for CSV and report generation

## Why this module exists

A separate configuration module keeps runtime constants centralized and removes hard-coded values from the pipeline logic. This also makes the pipeline easier to reuse or extend with new coordinates or output names.

## Imports

- `Path` from `pathlib`
- `date` from `datetime`

## Constants

- `LAT = 47.5999`
- `LON = 19.0616`
- `LOCATION_LABEL = "1039 Budapest, Sarkadi Imre utca 6"`
- `START_DATE = "2020-01-01"`
- `END_DATE = date.today().isoformat()`

## Output directory and file paths

- `DATA_DIR = Path(__file__).resolve().parent.parent / "data"`
- `DATA_DIR.mkdir(parents=True, exist_ok=True)`
- `OUTPUT_CSV = DATA_DIR / "environmental_data.csv"`
- `OUTPUT_REPORT = DATA_DIR / "data_quality_report.txt"`

## Notes

- `END_DATE` is computed at runtime so the pipeline can be rerun with an up-to-date period without code changes.
- Creating `DATA_DIR` on import simplifies execution and avoids directory errors during output writes.

## Navigation

- [Overview](overview.md)
- [Fetchers](fetchers.md)
- [Main](main.md)
