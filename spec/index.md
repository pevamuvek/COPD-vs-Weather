# COPD vs Weather Specification

This directory contains a split specification for the `copd-vs-weather` project. Use this index to navigate the component-level requirements.

## Navigation

- [Overview](overview.md) — project context and architecture
- [Concept](concept.md) — human-facing project purpose and design
- [Config](config.md) — constants, date range, and output path setup
- [Fetchers](fetchers.md) — weather, air quality, geomagnetic index retrieval, and feature engineering
- [Main](main.md) — orchestration, merge strategy, and CSV/report saving
- [Report](report.md) — quality report generation behavior
- [HTML risk reports](report_html.md) — daily and monthly standalone report behavior
- [Dependencies](dependencies.md) — runtime environment and execution instructions

## How to use

1. Start with `overview.md` to understand the project concept and goals.
2. Read each module specification for exact implementation requirements.
3. Rebuild the `src/` package by implementing the files described in each linked page.

## Notes

- The generated code must write outputs to `data/` relative to the repository root.
- The package should include the `src/` modules and HTML stylesheet listed in `overview.md`.
