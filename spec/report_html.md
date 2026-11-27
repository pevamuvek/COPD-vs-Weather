# HTML risk reports

The HTML report generator creates standalone Hungarian summaries from the scored
pipeline DataFrame or `data/environmental_data.csv`. It uses only the existing
Python and pandas dependencies; CSS is embedded into each output file.

## Commands

```powershell
python src/html_report.py daily --location-label "Springfield"
python src/html_report.py monthly --location-label "Springfield"
python src/html_report.py both --location-label "Springfield"
```

`both` is the positional period argument; use `python src/html_report.py both`,
not `python src/html_report.py -both`. The main pipeline writes both reports
after it saves the CSV. Rebuilding from a CSV requires `--location-label`
because location labels are not persisted in the CSV or a separate metadata file.
Use a city, district, or postcode label, not a street address.

An optional CSV path and `--output-dir` may be supplied. The normal pipeline run
automatically creates both reports with the resolved place label.

## Outputs

- `data/reports/kockázati_jelentés_10nap_<code>_YYYY-MM-DD.html`
- `data/reports/kockázati_jelentés_30nap_<code>_YYYY-MM.html`

The three-letter code is derived from the first place-name component of the
label, transliterated to ASCII and uppercased. The full label remains in report
content; the postcode is appended to the label when geocoding returns one.

The date comes from the last non-forecast row, not the computer clock.

## Daily report

The daily version selects the last eight non-forecast rows (the previous seven
days plus today) and up to two subsequent forecast rows. It contains:

1. risk outlook and four metric cards;
2. an interactive chart for risk score, maximum/minimum temperature, DTR,
   pressure change, dew point, precipitation, maximum wind speed, and a shared
   pollutant lane with PM₂,₅, PM₁₀, and NO₂ lines, with tier-coloured score
   points and a selectable daily metrics card;
3. a detailed table with DTR and pressure flags;
4. risk-score contribution bars showing each driver's average and period peak;
5. a short Hungarian narrative and forecast-data caveat;
6. extreme-heat, wellbeing, and clinical-disclaimer notes.

Forecast rows are highlighted when their tier is `moderate`, `high`, or
`very_high`, when DTR is at least 13 °C, or when absolute pressure change is at
least 3 hPa.

## Monthly report

The monthly version selects the last 30 non-forecast rows. It contains summary
cards, ISO-week aggregation, a full detail table, CSS-only risk/PM/DTR trends,
an interactive metric chart and selectable daily metrics card, automatically
detected notable events, average/peak driver bars, and a wellbeing comparison
prompt. The chart uses the same metric lanes as the daily report.

Both chart views use compact, evenly spaced daily targets (about 36 px per day
in the 10-day report and 32 px per day in the 30-day report), with at least
28 px per selectable day. Month-transition labels use separate month and day
lines. When a chart does not fit its container, horizontal scrolling stays
inside the chart frame rather than expanding the page.

The chart lanes follow this order: risk score, maximum/minimum temperature,
DTR, pressure change, dew point, precipitation, maximum wind speed, and the
shared pollutant lane. The selected-day card keeps PM₂,₅, PM₁₀, and NO₂ as
separate rows in the canonical metric order. The temperature lane shows
maximum and minimum as separate series. Each lane has its own scale; the three
pollutant lines share a concentration scale. Missing observations leave gaps
rather than interpolated values. The maximum-temperature line is red. The
temperature max/min and PM₂,₅/PM₁₀ lines use 70% of the standard line width;
PM₂,₅/PM₁₀ point markers are half-sized.

The risk-driver bars use the same fixed 0–1 scale as the risk score: a full
bar is 1.000 score points, so width is directly proportional to the displayed
contribution value. Each factor shows its base score weight; the effective
weight is renormalized per day when inputs are missing. The average is
calculated over days when that feature is available. The date at the end of
the row marks the first day with that factor's maximum contribution. In both
reports, the faded bar shows that peak. The driver chart displays four of the
score's six inputs, so its bars are not percentages that sum to the whole score.

## Tier display

The HTML generator derives display tiers from `risk_score` through the
production classifier. The canonical tier names, cutoffs, and calibration
basis are defined in [Risk scoring](score.md). Driver text and bars
use the same fixed feature normalization and partial-weight rescaling as
`score.py`.

## Formatting and safety

- Language and narrative text are Hungarian.
- Decimal values use a comma separator.
- Dynamic text is HTML-escaped.
- Reports include UTF-8 metadata, responsive and print CSS, status text in
  addition to color, and reduced-motion rules.
- Google Fonts are linked in the document head, with system font fallbacks.
- The result is a heuristic environmental indicator, not a validated clinical
  instrument or a substitute for medical advice.

## Navigation

- [Report](report.md)
- [Main](main.md)
- [Config](config.md)
- [Dependencies](dependencies.md)
