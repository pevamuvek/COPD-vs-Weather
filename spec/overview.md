# COPD vs Weather Specification Overview

This project builds a reproducible Python pipeline that collects daily environmental data for a Budapest location and prepares it for COPD-weather analysis.

The pipeline is intentionally focused on data quality and reproducibility. It is not a model training system; it produces a scored dataset, a quality report, and standalone Hungarian HTML risk summaries.

For a concept-level explanation of the clinical context, data sources, and scientific motivation, see [Concept](concept.md).

## Navigation

- [Concept](concept.md)
- [Config](config.md)
- [Fetchers](fetchers.md)
- [Main](main.md)
- [Report](report.md)
- [HTML risk reports](report_html.md)
- [Dependencies](dependencies.md)

## Project structure

The regenerated project must include the following files:

- `src/__init__.py`
- `src/config.py`
- `src/fetchers.py`
- `src/score.py`
- `src/report.py`
- `src/html_report.py`
- `src/report_html.css`
- `src/main.py`

The runtime output directory is created under `data/` relative to the repository root.
