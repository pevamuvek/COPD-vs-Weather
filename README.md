# copd-vs-weather

**A personal data pipeline for environmental COPD risk monitoring — grounded in clinical research, built for real use.**

A family member lives with severe COPD. This project started as a practical question: *can publicly available environmental data predict bad days before they happen?* It grew into a structured data engineering and risk modelling exercise, drawing on peer-reviewed Hungarian epidemiological research and designed with open-source reusability in mind.

---

## What this does

The pipeline fetches daily weather and air quality data for a given location, engineers clinically-motivated features, computes a composite risk score, and produces a plain-language daily summary suitable for a non-technical reader.

Under the hood it is a time-series feature engineering and binary classification problem — predicting whether a given day falls within a COPD exacerbation risk window.

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
  ├── Open-Meteo (historical + forecast)       → weather.py
  └── Open-Meteo Air Quality                   → air_quality.py
          │
          ▼
    Feature Engineering                         → features.py
      ├── ΔP  (barometric pressure Δ, 24h)
      ├── DTR (diurnal temperature range)
      ├── Dew point
      ├── Lag columns (pressure + temp shock, 1–3 day lags)
      └── Rolling averages (3, 7, 14-day windows)
          │
          ▼
    Risk Scoring                                → score.py
      └── Composite 0–1 score → Low / Moderate / High tier
          │
          ▼
    Daily Summary                               → report.py
      ├── Plain-language output (family use)
      └── Structured data output (analysis / demo)
```

---

## Technical stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Data fetching | `requests`, Open-Meteo REST API |
| Feature engineering | `pandas`, `numpy` |
|later: Classification model | `scikit-learn` (Random Forest), `xgboost` |
|later: Validation | Bootstrapping, sensitivity-weighted metrics |
|later: Health data parsing | OCR + NLP on PDF discharge summaries (EESZT format) |
| Output | CSV + plain-language daily summary |

---

## Feature engineering rationale

### ΔP — Barometric pressure change (24h)
Rapid pressure drops trigger bronchoconstriction. A single-point pressure reading carries no predictive signal; the *rate of change* does. This is computed as a 24-hour first difference, with a separate lag-1 and lag-2 column to capture delayed physiological response.

### DTR — Diurnal Temperature Range
The spread between daily high and low temperature is a stronger predictor than mean temperature alone. A hot afternoon followed by a cold night stresses the airways differently than a consistently warm day.

### Rolling averages (3 / 7 / 14-day windows)
Cumulative environmental stress matters independently of acute events. A week of moderate air pollution followed by a pressure drop is a different risk profile than an isolated pressure drop. Rolling means capture this background load.

### Lag structure
The Pécs Study identifies the 2–14 day window as clinically significant. Features are computed not only for the current day but for the preceding 1–3 days, so the model can learn that today's score is partly a function of what happened last Tuesday.

---

## Data sources

| Source | Data | Cost |
|---|---|---|
| Open-Meteo Historical Weather API | Temperature, pressure, humidity, dew point, wind | Free, no key |
| Open-Meteo Air Quality API | PM2.5, PM10, NO₂ | Free, no key |
| Open-Meteo Forecast API | 1–3 day forecast for risk preview | Free, no key |
| Open-Meteo Geocoding API | Location resolution by city name | Free, no key |
| EESZT (Hungarian Electronic Health Service Space) | Discharge summaries (PDF) | Patient-controlled, private |

Health data is never version-controlled. All patient-derived inputs are processed locally and explicitly excluded from the repository via `.gitignore`.

---

## Validation approach

The primary challenge is **low event count**: COPD exacerbations are relatively rare events even in a high-risk individual, producing a dataset with significant class imbalance.

Validation strategy:
- **Bootstrapping** to estimate metric variance without overfitting to a single train/test split
- **Sensitivity-weighted evaluation**: false negatives (missed risk days) are clinically more costly than false positives, so recall on the positive class is the primary metric
- **Feature importance analysis**: Random Forest feature importances are used to verify that the model is learning from clinically plausible signals, not spurious correlations

---

## Repository structure

```
copd-vs-weather/
├── src/
│   ├── fetchers/
│   │   ├── weather.py          # Open-Meteo historical + forecast
│   │   └── air_quality.py      # PM2.5, PM10, NO₂
│   ├── features.py             # Feature engineering (ΔP, DTR, lags, rolling)
│   ├── score.py                # Composite risk scoring (0–1, tiered)
│   ├── report.py               # Plain-language summary generation
│   └── main.py                 # Pipeline entry point
├── config/
│   ├── profiles/
│   │   ├── public.yaml         # Dynamic location (open demo)
│   │   └── family.yaml.example # Template — actual file gitignored
│   └── config.py
├── app.py                      # Streamlit web interface
├── tests/
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Running locally

```bash
git clone https://github.com/pevamuvek/copd-vs-weather
cd copd-vs-weather
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run pipeline (public profile, prompts for location)
python src/main.py

# Run Streamlit app
streamlit run app.py
```

No API keys required. All environmental data sources are free and open.

---

## Two versions, one codebase

| | Family version | Public demo |
|---|---|---|
| Location | Fixed (gitignored config) | Dynamic — browser geolocation, city name, or manual coordinates |
| Output | Plain-language daily summary | Risk dashboard + methodology view |
| Hosting | Private | [Live demo link] |
| Audience | One person with COPD | Anyone curious about the method |

The pipeline code is identical. Only the location configuration and UI copy differ.

---

## Project status

**Work in progress.** Started May 2026. First family test run: June 2026. Target for a fully usable version: July–August 2026.

Feedback, ideas, and contributions are welcome — see open issues or start a discussion.

---

## What this project is not

- It is not a clinical decision support tool and should not be used as one
- It does not replace medical advice
- This is a private study project built by someone who is not a doctor — treat it accordingly
- The model is trained on a single patient's event history — it is a personal risk indicator, not a generalised COPD prediction model

The methodology is designed to be sound. The scope is intentionally narrow.

---

## Deferred features

The following are documented and out of scope for the current demo phase:

- Multi-patient support
- Automated clinical data ingestion (currently manual OCR step)
- Prospective ML model retraining as new event data accumulates
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
