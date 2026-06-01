# COPD vs Weather Concept

This document explains the project purpose and design without referring to implementation details.

## Purpose

The `copd-vs-weather` project is a reproducible environmental data pipeline for a COPD risk analysis study anchored on a single patient location in Budapest.

It is designed to collect and organise daily environmental exposures and compute a transparent daily risk score. It does not perform statistical modeling or machine learning; the risk score is a weighted index intended for human review. The resulting dataset is intended to support later clinical risk analysis, event window labeling, and machine learning.

## Data sources and structure

The project combines multiple environmental data streams around a fixed residential location:

- historical weather observations from Open-Meteo
- air quality measurements from Open-Meteo
- geomagnetic activity from GFZ Potsdam’s Kp index

All data is aligned as daily time series so it can be compared with COPD hospitalization risk windows.

## Clinical workflow context

The broader research context includes:

- unstructured discharge summaries from EESZT (Hungarian Electronic Health Service Space)
- OCR and NLP to extract event dates and ICD-10 codes such as J44.x
- manually curated risk windows around COPD admissions

This environment-focused repository supports that work by producing a clean environmental exposure dataset.

## Feature engineering rationale

The pipeline is designed to capture environmental stressors that matter for respiratory risk:

- `ΔP` (barometric pressure change over 24 hours) as a pressure shock indicator
- `DTR` (diurnal temperature range) to reflect temperature fluctuation stress
- dew point to capture humid heat and thermal comfort effects
-  - rolling averages over 3, 7, and 14 days applied to pollution and geomagnetic indicators; explicit lag columns for pressure and temperature shocks
- air pollution indicators for PM2.5, PM10, and NO₂
- daily Kp-derived geomagnetic activity summaries to test secondary stressor hypotheses

## Scientific motivation

This concept is informed by benchmark research and project observations:

- the Pécs Study (2024) emphasizes temperature fluctuations and dew point in Hungary
- a lag effect is expected in the 2–14 day window after an environmental shock
- pollution synergy between NO₂, particulate matter, and weather fronts may trigger exacerbations

## Why it matters

COPD exacerbations often emerge from multiple, interacting environmental stressors.

By capturing these stressors in a structured daily dataset, the project creates a foundation for later risk-window modeling and sensitivity-focused validation.