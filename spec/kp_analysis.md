# Independent Kp analysis

Kp is collected for exploratory analysis, but it is not part of the core
weather/air-quality pipeline, risk score, or user-facing risk reports. This
separation avoids making Kp-source availability a dependency of the daily
environmental report and allows Kp associations to be examined independently
from a score that would otherwise contain Kp.

## Export command

From the repository root:

```powershell
python src\kp_analysis.py
```

The command calls `fetch_kp_index(START_DATE, END_DATE)` and writes
`data/kp_daily.csv`. The file has one row per UTC date with
`Kp_daily_max`, `Kp_daily_mean`, `Kp_n`, and `Kp_daily_sum`. A fully missing Kp
range is an error for this command and must not be reported as a successful
export.

The regular `python src\main.py` run does not fetch or join Kp.

## Analysis and future join

- Keep the exported Kp dataset separate while examining missingness,
  seasonality, long-term trends, and contemporaneous or lagged associations.
- Exclude forecast rows from historical climatology and correlation analyses.
- Treat all associations as exploratory environmental relationships, not
  evidence of COPD outcomes; clinical event labels are not available.
- Do not add Kp to the risk score or its reports until a separate decision
  documents the rationale, weighting, missing-data behavior, and presentation.
- If a future analysis needs both datasets, join explicitly on UTC date with
  the core environmental data on the left. Preserve the independent Kp export
  and do not silently alter the score.

## Navigation

- [Fetchers](fetchers.md)
- [Main](main.md)
- [Risk scoring](score.md)
