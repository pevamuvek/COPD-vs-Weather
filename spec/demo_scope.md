# Demo scope — two audiences

This document defines what the demo version of `copd-vs-weather` must produce
and what is out of scope for now. It is intended as a brief brief for Copilot
and as a README section for GitHub.

---

## What the demo does

The demo pipeline runs once and produces three outputs:

1. `data/environmental_data.csv` — historical + 2-day forecast, all features including
   `risk_score`, `risk_tier`, and `is_forecast`.
2. `data/data_quality_report.txt` — completeness table plus a plain-language
   3-row risk summary for today + 2 days ahead.
3. Console output — a short human-readable summary printed at the end of `main.py`.

No web server, no database, no trained model, no login.

---

## Audience A — personal demo (one patient, one location)

**Who:** A non-technical person who wants to know whether the next day or two
looks risky for a COPD patient living in Budapest.

**How to run:**
```
python code\main.py
```

**What they see at the end of the run:**

```
--- Risk outlook ---
Today (2025-06-01):   LOW      0.28  Conditions stable
Tomorrow (2025-06-02): MODERATE 0.51  Pressure drop expected (-3.1 hPa)
Day after (2025-06-03): HIGH    0.72  Pressure drop + elevated PM2.5
```

**What they do with it:** Check before planning outdoor activity or deciding
whether to have medication at hand.

**Requirements to support this audience:**
- The console output must be readable without opening any file.
- Risk labels must be in plain language, not variable names.
- The location label from `config.py` must appear in the output so it is clear
  whose address the data refers to.

---

## Audience B — GitHub / open science

**Who:** Researchers, developers, or COPD patients in other cities who want to
run the same pipeline for their own location.

**What they need to change:** Only two values in `config.py`:
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
| `code/score.py` | New — composite risk index |
| `code/fetchers.py` | Add `fetch_weather_forecast()` and lag columns |
| `code/main.py` | Add forecast concat, `compute_risk_score` call, console summary |
| `code/report.py` | Add risk summary section |
| `docs/score.md` | New — specification for `score.py` |
| `README.md` | New or update — audience B entry point |

No new dependencies beyond `requests`, `pandas`, and `numpy`.
