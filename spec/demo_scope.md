# Demo scope — two audiences

This document defines what the demo version of `copd-vs-weather` must produce
and what is out of scope for now. It is intended as a brief brief for Copilot
and as a README section for GitHub.

---

## What the demo does

The demo pipeline runs once and produces four outputs:

1. `data/environmental_data.csv` — historical data plus up to two forecast days,
   selected weather and air-quality features, `risk_score`, `risk_tier`, and
   `is_forecast`. Pressure and DTR lag columns are computed but currently omitted
   from this CSV; Kp is exported separately.
2. `data/data_quality_report.txt` — completeness table, forecast-row count,
   date/score/tier table for available forecast rows, feature-coverage notes,
   and a primary-driver note when a forecast score is available.
3. `data/reports/kockázati_jelentés_YYYY-MM-DD.html` — a Hungarian daily risk
   report covering the previous seven days, today, and up to two forecast days.
4. Console output — pipeline progress and an echo of the text quality report
   (the same report is saved as output 2).

No web server, no database, no trained model, no login.

---

## Audience A — personal demo (one patient, one location)

**Who:** A non-technical person who wants to know whether the next day or two
looks risky for a COPD patient living in Budapest.

**How to run:**
```
python src\main.py
```

**What they see at the end of the run:** The console shows the quality report's
date/score/tier table for available forecast rows, feature-coverage notes, and
a primary-driver note. It does not print a separate Today/Tomorrow outlook.
Under the current tier cutoffs, example scores map as follows: `0.20` → LOW,
`0.28` → MODERATE, and `0.51` or `0.72` → VERY HIGH.

**What they do with it:** Use the environmental information as context for
reviewing conditions. It is not a basis for medication changes or other medical
decisions.

**Requirements to support this audience:**
- The console quality report must be readable without opening a file.
- It must show dates, risk scores, tiers, feature-coverage notes, and the
  primary-driver note when available.
- The location label from `config.py` must appear in the output so it is clear
  whose address the data refers to.

---

## Audience B — GitHub / open science

**Who:** Researchers, developers, or COPD patients in other cities who want to
run the same pipeline for their own location.

**What they need to change:** The location settings in `config.py`:
```python
LAT = 47.5999       # replace with their coordinates
LON = 19.0616
LOCATION_LABEL = "1039 Budapest, Sarkadi Imre utca 6"  # replace with their address
```

**What the README must communicate:**
- What the project does in two sentences.
- The three output files and what they contain.
- The four-line install + run sequence.
- A note that the risk score is a weighted environmental index, not a
  medical diagnosis, and that it has not been validated in a clinical trial.
- An invitation to open an issue or PR if they run it for a different location.

**Requirements to support this audience:**
- No hardcoded Budapest-specific logic outside `config.py`.
- `START_DATE` defaults to `"2020-01-01"` but is overridable via `config.py`
  without touching any other file.
- The risk weight constants in `score.py` must be in a named dict at the top
  of the file with a comment explaining each weight.

---

## What is explicitly out of scope for the demo

These items are documented for later phases and must not block the demo build:

| Feature | Reason deferred |
|---------|-----------------|
| EESZT discharge summary parsing | Requires private patient data |
| OCR / NLP for ICD-10 extraction | Requires private patient data |
| Random Forest / XGBoost model | Requires labeled event data first |
| Bootstrap validation | Requires labeled event data first |
| `viral_cofactor` column | Unspecified; deferred to Phase 2 |
| Web dashboard or app | Out of scope for CLI demo |
| Real-time alerts / notifications | Out of scope for CLI demo |
| Multi-patient support | Out of scope for single-patient demo |

---

## Minimal file additions for the demo

To go from the current spec to a working demo, only these files need to be
created or modified (beyond the existing five):

| File | Action |
|------|--------|
| `src/score.py` | Composite risk index |
| `src/fetchers.py` | Forecast retrieval and derived features |
| `src/main.py` | Pipeline orchestration and report calls |
| `src/report.py` | Text quality and risk summary |
| `src/html_report.py` | Daily and monthly HTML reports |
| `src/report_html.css` | Responsive embedded report styles |
| `spec/report_html.md` | HTML report specification |
| `README.md` | New or update — audience B entry point |

No new dependencies beyond `requests`, `pandas`, and `numpy`.
