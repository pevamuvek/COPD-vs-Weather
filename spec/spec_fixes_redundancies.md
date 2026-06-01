# Spec fixes — redundancies and orphaned content

These are targeted edits to existing documentation files.
Each item states the file, the exact problem, and the action required.

---

## Fix 1 — `overview.md`: remove duplicate block

**Problem:** The entire content of `overview.md` from line 9 onward is repeated verbatim.
The Navigation section and the Project structure section both appear twice.

**Action:** Delete the second occurrence of both sections (lines 30–49 in the current file).

The file after the fix should contain:
- The two-paragraph introduction (keep as-is).
- One Navigation section.
- One Project structure section.

---

## Fix 2 — `main.md`: remove unspecified cofactor references

**Problem:** The "Dataset purpose" section lists two items that have no specification
in any other file and cannot be implemented:

> - support later clinical cofactors such as `viral_cofactor` and uncertain event flags

**Action:** Replace that bullet with:

> - preserve all calendar days so non-event periods are available for model training

This keeps the intent (complete time series) without implying unspecified columns exist.

---

## Fix 3 — navigation footers: scope correction

**Problem:** `concept.md` and `config.md` both end with identical navigation footers
listing Overview, Fetchers, and Main. These are generic and do not reflect each file's
actual relationships.

**Action:**

- `concept.md` footer: keep Overview only. Concept has no implementation dependency.
  ```
  ## Navigation
  - [Overview](overview.md)
  ```

- `config.md` footer: keep Overview, Fetchers, Main — these are the correct consumers.
  No change needed here; the current footer is accurate.

---

## Fix 4 — `concept.md`: align feature list with `fetchers.md`

**Problem:** `concept.md` lists rolling averages as applying to all environmental
features, but `fetchers.md` specifies that rolling averages apply only to
`pm2_5`, `pm10`, `no2`, and `Kp_daily_max` — not to `delta_P` or `DTR`.

This creates a mismatch: a reader of `concept.md` would expect rolling averages
on pressure and temperature too.

**Action (two options — pick one):**

Option A (preferred for demo): Update `concept.md` to be accurate:
> - rolling averages over 3, 7, and 14 days applied to pollution and geomagnetic
>   indicators; explicit lag columns for pressure and temperature shocks

Option B: Update `fetchers.md` to also compute rolling means for `delta_P` and `DTR`.
This is a larger code change and is not required for the demo scope.

---

## Fix 5 — `concept.md`: update stated scope

**Problem:** The Purpose section says:

> "It is designed to collect and organize daily environmental exposures, not to perform
> modeling itself."

After the additions in `spec_additions_predictive.md`, the pipeline will produce
`risk_score` and `risk_tier` columns, which is a form of scoring, not just collection.

**Action:** Replace that sentence with:

> "It is designed to collect and organise daily environmental exposures and compute
> a transparent daily risk score. It does not perform statistical modeling or machine
> learning; the risk score is a weighted index intended for human review."

This keeps the statement accurate without overstating the pipeline's capabilities.
