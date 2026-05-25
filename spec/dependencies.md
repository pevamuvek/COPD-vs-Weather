# Dependencies and Execution

This page explains the runtime environment and how to execute the pipeline.

## Concept

The project is intentionally lightweight. It depends on stable Python packages for HTTP requests and data processing, and it is designed to run from the repository root.

## Python compatibility

- Python 3.10+

## Required packages

Install via pip:

```powershell
python -m pip install requests pandas numpy
```

## Run command

From the repository root `copd-vs-weather`:

```powershell
python code\main.py
```

## Expected outputs

- `data/environmental_data.csv` — merged daily dataset with weather, air quality, Kp, and rolling features
- `data/data_quality_report.txt` — text report summarizing completeness and missing data

## Notes

- Use the same Python interpreter for both `pip` and `python` to avoid environment mismatch.
- If you are using a virtual environment, activate it before installing dependencies and running the script.

## Navigation

- [Overview](overview.md)
- [Main](main.md)
