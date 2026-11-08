# HTML risk reports

The HTML report generator creates standalone Hungarian summaries from the scored
pipeline DataFrame or `data/environmental_data.csv`. It uses only the existing
Python and pandas dependencies; CSS is embedded into each output file.

## Commands

```powershell
python src/html_report.py daily
python src/html_report.py monthly
python src/html_report.py both
```

An optional CSV path and `--output-dir` may be supplied. The normal pipeline run
automatically creates the daily report.

## Outputs

- `data/reports/kockázati_jelentés_YYYY-MM-DD.html`
- `data/reports/havi_jelentés_YYYY-MM.html`

The date comes from the last non-forecast row, not the computer clock.

## Daily report

The daily version selects the last eight non-forecast rows (the previous seven
days plus today) and up to two subsequent forecast rows. It contains:

1. risk outlook and four metric cards;
2. a detailed table with DTR and pressure flags;
3. risk-score-consistent driver contribution bars;
4. a short Hungarian narrative and forecast-data caveat;
5. Kp coverage, extreme-heat, wellbeing, and clinical-disclaimer notes.

Forecast rows are highlighted when their tier is `moderate`, `high`, or
`very_high`, when DTR is at least 13 °C, or when absolute pressure change is at
least 3 hPa.

## Monthly report

The monthly version selects the last 30 non-forecast rows. It contains summary
cards, ISO-week aggregation, a full detail table, CSS-only risk/PM/DTR trends,
automatically detected notable events, average/peak driver bars, and a wellbeing
comparison prompt.

## Four-tier display

| Tier | Hungarian label | Range |
|---|---|---|
| `low` | Alacsony | `< 0.220` |
| `moderate` | Mérsékelt | `0.220` to `< 0.300` |
| `high` | Magas | `0.300` to `0.380` |
| `very_high` | Nagyon magas | `> 0.380` |
| `unknown` | Ismeretlen | missing score |

The HTML generator derives display tiers from `risk_score` through the production
classifier. The cutoffs are anchored to the observed score distribution in the
2015–2026 historical dataset (approximately the 28th, 72nd, and 93rd
percentiles); they are heuristic thresholds, not clinically validated limits.
Driver text and bars use the same fixed feature normalization and partial-weight
rescaling as `score.py`.

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
