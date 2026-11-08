# copd-vs-weather

**A personal data pipeline for environmental COPD risk monitoring — grounded in clinical research, built for real use.**

A family member lives with severe COPD. This project started as a practical question: *can publicly available environmental data help us understand difficult days?* It grew into a structured data engineering and environmental risk-scoring exercise, drawing on peer-reviewed Hungarian epidemiological research and designed with open-source reusability in mind.

---

## What this does

The pipeline fetches daily weather, air quality, and geomagnetic data for a configured location, engineers environmental features, computes a composite risk score, and produces text and Hungarian HTML reports suitable for a non-technical reader.

The score is a weighted environmental index, not a probability or a prediction of a COPD exacerbation. There is currently no event-labeling strategy or statistical/ML model; those are outside the scope of this version.

---

## Clinical grounding

Feature design and lag windows are grounded in the **Pécs Study (2024)**, a Hungarian epidemiological study examining environmental triggers of COPD exacerbations. Key findings that shaped this project:

- **Temperature fluctuation and dew point** are the strongest meteorological predictors of exacerbation in the Hungarian climate
- **Barometric pressure drops** over 24-hour windows are a consistent acute trigger
- **Lagged effects** are clinically significant: the critical observation window is 2–14 days following an environmental shock
- **NO₂ and particulate matter** (PM2.5, PM10) interact synergistically with weather fronts
- **Geomagnetic activity (Kp index)** — added as a candidate co-factor based on geophysics background; its role in physiological stress responses is under-researched and worth monitoring

This is not a generic weather-health dashboard. Feature selection reflects what the literature says matters, not what was easiest to compute.

---

## Pipeline architecture

```
Environmental APIs
  ├── Open-Meteo (historical + forecast)       → fetchers.py
  └── Open-Meteo Air Quality + GFZ Kp          → fetchers.py
          │
          ▼
    Feature Engineering                         → fetchers.py
      ├── ΔP  (barometric pressure Δ, 24h)
      ├── DTR (diurnal temperature range)
      ├── Dew point
      ├── Computes pressure lags (2, 5, 7, 14 days) and DTR lags (2, 7, 14 days)
      └── Rolling means (3, 7, 14 days) for pollution and Kp
          │
          ▼
    Risk Scoring                                → score.py
      └── Composite 0–1 score → Low / Moderate / High / Very High tier
          │
          ▼
    Reports                                     → report.py + html_report.py
      ├── Data-quality text output
      ├── Daily Hungarian HTML report
      └── Optional 30-day HTML overview
```

---

## Technical stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ (tested here with 3.14.5) |
| Data fetching | `requests`, Open-Meteo and GFZ Potsdam APIs/data |
| Feature engineering | `pandas`, `numpy` |
| Statistical/ML modeling (later) | Not implemented; requires event labels and a modeling strategy |
| Model validation (later) | Not implemented; requires a defined model and labeled event data |
| Health data parsing (later) | OCR + NLP on PDF discharge summaries (EESZT format) |
| Output | CSV + quality text + standalone Hungarian HTML reports |

---

## Feature engineering rationale

### ΔP — Barometric pressure change (24h)
The daily pressure difference is computed as a first difference of daily mean surface pressure. The feature builder also computes selected lagged pressure differences; see the lag structure below.

### DTR — Diurnal Temperature Range
The spread between daily high and low temperature is a stronger predictor than mean temperature alone. A hot afternoon followed by a cold night stresses the airways differently than a consistently warm day.

### Rolling averages (3 / 7 / 14-day windows)
Cumulative environmental stress matters independently of acute events. A week of moderate air pollution followed by a pressure drop is a different risk profile than an isolated pressure drop. Rolling means capture this background load.

### Lag structure
The feature builder computes explicit lag columns for selected pressure and temperature features: `delta_P` at 2, 5, 7, and 14 days, and `DTR` at 2, 7, and 14 days. The current pipeline does not retain these lag columns in the saved CSV or use them in the risk score; they do not imply that a model has learned a clinical relationship.

### Risk score and tiers

The current score is a weighted combination of normalized environmental indicators, rescaled over the features available on each day. It is not a probability, a clinical threshold, or a validated prediction. Tier cutoffs are anchored to the observed distribution of scores in the 2015–2026 historical dataset, not to clinical outcomes:

| Tier | Score |
|---|---|
| Low | `< 0.220` |
| Moderate | `0.220` to `< 0.300` |
| High | `0.300` to `0.380` |
| Very High | `> 0.380` |
| Unknown | Score unavailable |

These cutoffs are heuristic and require further evaluation; the event count is low, and a strategy for connecting environmental data to clinical events has not yet been defined.

---

## Data sources

| Source | Data | Cost |
|---|---|---|
| Open-Meteo Historical Weather API | Temperature, pressure, humidity, dew point, wind | Free, no key |
| Open-Meteo Air Quality API | PM2.5, PM10, NO₂ | Free, no key |
| Open-Meteo Forecast API | 1–3 day forecast for risk preview | Free, no key |
| GFZ Potsdam Kp index | 3-hourly geomagnetic index, aggregated by UTC day | Free |
| Open-Meteo Geocoding API | City-name location lookup; not available in this public repository yet | Free, no key |

Clinical event records and EESZT discharge summaries are not fetched or processed by this pipeline. Any future use of patient-derived data would require appropriate privacy controls and local handling.

---

## Future modeling and validation

The low number of COPD exacerbation events is a valid constraint on future analysis, but there is not yet a defined strategy for linking environmental observations to clinical events or modeling that relationship. This project does not currently train or validate a statistical or machine-learning model.

Event labeling, a modeling approach, and an evaluation strategy remain future work. The current weighted environmental score and its tiers should not be interpreted as learned from event data or clinically validated.

---

## Repository structure

```
copd-vs-weather/
├── src/
│   ├── config.py               # Location, date range, output paths
│   ├── fetchers.py             # Environmental APIs and derived features
│   ├── score.py                # Composite risk scoring (0–1, four tiers)
│   ├── report.py               # Text quality report generation
│   ├── html_report.py          # Daily/monthly HTML report generation
│   ├── report_html.css         # Embedded responsive report styling
│   └── main.py                 # Pipeline entry point
├── test/                       # Verification and report tests
├── spec/                       # Component specifications
├── data/                       # Generated data and reports
├── .gitignore
└── README.md
```

---

## Running locally

```bash
git clone https://github.com/pevamuvek/copd-vs-weather
cd copd-vs-weather
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install requests pandas numpy

# Run the pipeline for the location configured in src/config.py
python src/main.py

# Rebuild reports from the existing CSV without refetching data
python src/html_report.py daily
python src/html_report.py monthly
```

No API keys required. All environmental data sources are free and open.

The pipeline writes:

- `data/environmental_data.csv` — merged daily environmental data and scores
- `data/data_quality_report.txt` — coverage, missing-data, and risk summary
- `data/reports/kockázati_jelentés_YYYY-MM-DD.html` — Hungarian daily report

---

## Current pipeline and future public demo

| | Current configured pipeline | Future public demo |
|---|---|---|
| Location | Coordinates and label set in `src/config.py` | City-name lookup is not available in this repository yet |
| Output | CSV, quality text, and Hungarian daily/monthly HTML reports | Not available yet |
| Hosting | Local | Not available yet |
| Audience | Personal environmental monitoring and analysis | Future open-science use |

The current repository is a local command-line pipeline; there is no browser interface or live public demo yet.

---

## Project status

**Work in progress.** Started May 2026. First family test run: June 2026. Target for a fully usable version: end of 2026.

Feedback, ideas, and contributions are welcome — see open issues or start a discussion.

---

## What this project is not

- It is not a clinical decision support tool and should not be used as one
- It does not replace medical advice
- This is a private study project built by someone who is not a doctor — treat it accordingly
- The weighted score is an environmental indicator, not a COPD prediction and not a clinical decision-support tool

The scope is intentionally narrow; the score and its clinical relevance still require evaluation.

---

## Deferred features

The following are documented and out of scope for the current demo phase:

- Multi-patient support
- Clinical event labeling and automated clinical data ingestion
- Statistical/ML modeling and validation (event-linking strategy not yet defined)
- Push notification layer for high-risk days

---

## Why this exists

Two important living creatures in my life have COPD — my father and, over 18 years of horse ownership, several horses. With both, the experience is the same: you watch them fight for air when conditions turn bad, and most of what medicine offers is symptom management after the fact. Prevention is maybe 30% of the picture, and even then you're tweaking between two low points without knowing for certain what the triggers actually are — because there can be thousands, and it's always their combination that matters.

My father is a weather-curious engineer. Over years of living with COPD, he compiled his own observations: weather front situations challenge his wellbeing, and once a negative spiral starts, it tends to end in hospitalisation — three or four times a year over the past three years. He lives alone. He's not one to ask for help. He's also a former small aircraft pilot, which means he's far more likely to check a weather forecast than change his habits.

His doctor's approach gave me the framing: when the spiral starts, adjust medication early — before hitting rock bottom, before calling an ambulance. The question this project asks is simply: *can we see the spiral coming?*

The horses are a further motivation. COPD in horses is poorly understood at the individual level — one year is quiet, another brings acute breakdowns, and owners rarely know even 75% of the personal triggers. Expanding this kind of environmental risk monitoring to equine COPD is a future direction worth pursuing.

---

## How this was built

Built entirely within free tiers — no paid subscriptions, no cloud compute costs.

The idea was drafted in Gemini. Development moved to Claude (Anthropic) for architecture, planning, spec writing, and learning guidance. Code was written and tuned in VS Code with GitHub Copilot, using Claude Sonnet and a secondary model for generation and testing. Specs and code generation ran in parallel, with Claude and Copilot used simultaneously at different layers of the stack.

VS Code and GitHub were both started from zero during this project — learned through doing, with Claude as a guide and S, VIP Human collaborator who helped kick off the VS Code and Copilot setup deserves a mention here too — the right nudge at the right moment matters.

All tool usage was directed by human judgment: the domain knowledge, the research grounding, the feature selection rationale, the decision about what *not* to build, and the instinct that this was worth building at all. The AI tools accelerated execution. Knowing how to direct them effectively is the skill being demonstrated here.

---

## References

Márovics, G., Sándor, B., Sándor, J., Sándor, B., Nagy, S., & Pál, L. (2024). Weather variability and COPD: A risk estimation identified a vulnerable sub-population in Hungary. *PeerJ, 12*, e17255. https://doi.org/10.7717/peerj.17255

Open-Meteo API documentation: https://open-meteo.com/en/docs

ICD-10 J44.x: Chronic obstructive pulmonary disease

---

## Author

Built by **Éva Pudleiner** — a data professional with a background in geospatial analysis, geophysics, and sustainability, applying environmental data methods to a personal and clinical problem.

*This project is part of a public portfolio demonstrating applied data engineering, clinically-grounded feature design, and end-to-end pipeline thinking.*
