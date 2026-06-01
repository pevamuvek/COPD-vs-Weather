# COPD vs Weather Specification Overview

This project builds a reproducible Python pipeline that collects daily environmental data for a Budapest location and prepares it for COPD-weather analysis.

The pipeline is intentionally focused on data quality and reproducibility. It is not a model training system; it is a data-gathering layer that produces a clean dataset and a quality report for further analysis.

For a concept-level explanation of the clinical context, data sources, and scientific motivation, see [Concept](concept.md).

## Navigation

- [Concept](concept.md)
- [Config](config.md)
- [Fetchers](fetchers.md)
- [Main](main.md)
- [Report](report.md)
- [Dependencies](dependencies.md)

## Project structure

The regenerated project must include the following files:

- `code/__init__.py`
- `code/config.py`
- `code/fetchers.py`
- `code/report.py`
- `code/main.py`

The runtime output directory is created under `data/` relative to the repository root.

