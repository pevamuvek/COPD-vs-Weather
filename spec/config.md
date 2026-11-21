# `config.py`

This module provides runtime location/date resolution and output paths for the pipeline.

No data fetching or environmental-data transformation belongs here. Its responsibilities are:

- resolve a location at runtime through the CLI, environment, or interactive prompt
- set a fixed start date and a dynamic end date
- construct the `data/` directory path relative to the repository root
- create the directory when the module is imported
- expose output file paths for CSV and report generation

## Why this module exists

A separate configuration module keeps runtime constants centralized and removes hard-coded values from the pipeline logic. This also makes the pipeline easier to reuse or extend with new coordinates or output names.

## Imports

- `Path` from `pathlib`
- `date` and `datetime` from `datetime`
- `ZoneInfo` from `zoneinfo`

## Constants

- No hardcoded location or default location
- `START_DATE = "2020-01-01"`
- `END_DATE = date.today().isoformat()` for the independent, global Kp workflow
- `get_end_date(location)` returns the current date in the resolved location's IANA timezone for the core environmental pipeline

## Output directory and file paths

- `DATA_DIR = Path(__file__).resolve().parent.parent / "data"`
- `DATA_DIR.mkdir(parents=True, exist_ok=True)`
- `REPORT_DIR = DATA_DIR / "reports"`
- `REPORT_DIR.mkdir(parents=True, exist_ok=True)`
- `OUTPUT_CSV = DATA_DIR / "environmental_data.csv"`
- `OUTPUT_REPORT = DATA_DIR / "data_quality_report.txt"`
- `OUTPUT_KP_CSV = DATA_DIR / "kp_daily.csv"` — standalone Kp export; not written by the core pipeline

## Notes

- `END_DATE` is the computer-local current date for the independent Kp workflow.
- The core environmental pipeline calls `get_end_date(location)` so its requested end date matches the resolved location's local calendar day.
- Creating `DATA_DIR` on import simplifies execution and avoids directory errors during output writes.

## Navigation

- [Overview](overview.md)
- [Fetchers](fetchers.md)
- [Main](main.md)
