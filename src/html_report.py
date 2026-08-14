"""Generate standalone Hungarian daily and monthly COPD risk reports."""

from __future__ import annotations

import argparse
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

import pandas as pd

from config import LOCATION_LABEL, OUTPUT_CSV, REPORT_CITY, REPORT_DIR
from score import (
    FEATURE_RANGES,
    RISK_WEIGHTS,
    classify_risk_score,
    compute_feature_contributions,
)


STYLE_PATH = Path(__file__).with_name("report_html.css")
REQUIRED_COLUMNS = {"risk_score", "risk_tier"}
ELEVATED_TIERS = {"moderate", "high", "very_high"}
TIER_LABELS_HU = {
    "low": "Alacsony",
    "moderate": "Mérsékelt",
    "high": "Magas",
    "very_high": "Nagyon magas",
    "unknown": "Ismeretlen",
}
MONTHS_HU = (
    "",
    "jan.",
    "febr.",
    "márc.",
    "ápr.",
    "máj.",
    "jún.",
    "júl.",
    "aug.",
    "szept.",
    "okt.",
    "nov.",
    "dec.",
)
DRIVER_LABELS = {
    "DTR": "Napi hőingadozás (DTR)",
    "pm2_5": "Szálló por (PM₂,₅)",
    "delta_P": "Légnyomásváltozás (ΔP)",
    "dew_point_2m_mean": "Alacsony harmatpont",
    "Kp_daily_max": "Kp-index",
    "no2": "Nitrogén-dioxid (NO₂)",
    "pm10": "Szálló por (PM10)",
}
DRIVER_CSS = {
    "DTR": "driver-dtr",
    "pm2_5": "driver-pm",
    "delta_P": "driver-dp",
    "dew_point_2m_mean": "driver-dew",
    "Kp_daily_max": "driver-kp",
}
DRIVER_FEATURES = tuple(DRIVER_CSS)


def _prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Hiányzó kötelező oszlopok: {', '.join(sorted(missing))}")

    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        if frame["date"].isna().any():
            raise ValueError("A date oszlop érvénytelen dátumot tartalmaz.")
        frame = frame.set_index("date")
    else:
        frame.index = pd.to_datetime(frame.index, errors="coerce")
        if frame.index.isna().any():
            raise ValueError("A DataFrame indexe érvénytelen dátumot tartalmaz.")

    if frame.empty:
        raise ValueError("Az adathalmaz üres.")
    return frame.sort_index()


def _forecast_mask(df: pd.DataFrame) -> pd.Series:
    if "is_forecast" not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    values = df["is_forecast"]
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(False).astype(bool)
    return values.map(
        lambda value: str(value).strip().lower() in {"true", "1", "yes"}
        if pd.notna(value)
        else False
    ).astype(bool)


def _daily_slice(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp, pd.DataFrame]:
    forecast_mask = _forecast_mask(df)
    historical = df.loc[~forecast_mask].tail(8)
    if historical.empty:
        raise ValueError("A napi jelentéshez nincs történeti adatsor.")
    today = historical.index[-1]
    forecast = df.loc[forecast_mask & (df.index > today)].head(2)
    rows = pd.concat([historical, forecast]).sort_index()
    return rows, today, forecast


def _monthly_slice(df: pd.DataFrame) -> pd.DataFrame:
    rows = df.loc[~_forecast_mask(df)].tail(30)
    if rows.empty:
        raise ValueError("A havi jelentéshez nincs történeti adatsor.")
    return rows


def _tier(row: pd.Series) -> str:
    score = row.get("risk_score")
    if pd.notna(score):
        return classify_risk_score(score)
    tier = str(row.get("risk_tier", "unknown"))
    return tier if tier in TIER_LABELS_HU else "unknown"


def _hu_date(value: pd.Timestamp, include_year: bool = False) -> str:
    value = pd.Timestamp(value)
    if include_year:
        return f"{value.year}. {MONTHS_HU[value.month]} {value.day}."
    return f"{MONTHS_HU[value.month]} {value.day}."


def _number(value, decimals: int = 1, signed: bool = False) -> str:
    if value is None or pd.isna(value):
        return "—"
    spec = f"{'+' if signed else ''}.{decimals}f"
    return format(float(value), spec).replace(".", ",")


def _score(value) -> str:
    return _number(value, 3)


def _row_alert(row: pd.Series) -> bool:
    dtr = row.get("DTR")
    delta_p = row.get("delta_P")
    return (
        _tier(row) in ELEVATED_TIERS
        or (pd.notna(dtr) and float(dtr) >= 13)
        or (pd.notna(delta_p) and abs(float(delta_p)) >= 3)
    )


def _primary_driver(row: pd.Series) -> tuple[str, float] | tuple[None, None]:
    contributions = compute_feature_contributions(row, RISK_WEIGHTS, FEATURE_RANGES)
    if not contributions:
        return None, None
    feature = max(contributions, key=contributions.get)
    return feature, contributions[feature]


def _driver_name(row: pd.Series) -> str:
    feature, _ = _primary_driver(row)
    return DRIVER_LABELS.get(feature, feature or "nem meghatározható")


def _tier_pill(row: pd.Series) -> str:
    tier = _tier(row)
    return (
        f'<span class="tier-pill tier-{tier}">'
        f"{escape(TIER_LABELS_HU[tier])}</span>"
    )


def _longest_streak(mask: Iterable[bool]) -> int:
    longest = current = 0
    for flagged in mask:
        if bool(flagged):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _streak_ranges(rows: pd.DataFrame, mask: pd.Series, minimum: int) -> list[tuple]:
    ranges = []
    start = None
    previous = None
    count = 0
    for date, flagged in mask.items():
        if bool(flagged):
            if start is None:
                start = date
            previous = date
            count += 1
        else:
            if start is not None and count >= minimum:
                ranges.append((start, previous, count))
            start = previous = None
            count = 0
    if start is not None and count >= minimum:
        ranges.append((start, previous, count))
    return ranges


def _flagged_value(value, kind: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    if kind == "dtr":
        dot = '<span class="flag-dot flag-warn" title="DTR ≥ 13 °C"></span>' if value >= 13 else ""
        return f"{_number(value)} {dot}"
    dot = '<span class="flag-dot flag-dp" title="|ΔP| ≥ 3 hPa"></span>' if abs(value) >= 3 else ""
    return f"{_number(value, signed=True)} {dot}"


def _table(rows: pd.DataFrame, today=None, monthly: bool = False) -> str:
    body = []
    previous_week = None
    forecast_mask = _forecast_mask(rows)
    for date, row in rows.iterrows():
        classes = []
        is_forecast = bool(forecast_mask.loc[date])
        tier = _tier(row)
        if today is not None and date == today:
            classes.append("today-row")
        if is_forecast:
            classes.append("forecast-row")
            if _row_alert(row):
                classes.append("alert")
        if monthly:
            iso_week = (date.isocalendar().year, date.isocalendar().week)
            if previous_week is not None and iso_week != previous_week:
                classes.append("week-start")
            previous_week = iso_week
            if pd.notna(row.get("DTR")) and row.get("DTR") >= 13:
                classes.append("dtr-flag")
            if tier == "moderate":
                classes.append("mod-risk")
            elif tier == "high":
                classes.append("high-risk")
            elif tier == "very_high":
                classes.append("very-high-risk")

        date_text = escape(_hu_date(date))
        if is_forecast:
            date_text += '<span class="forecast-badge">Előrejelzés</span>'

        notes = []
        aq_columns = [name for name in ("pm2_5", "pm10", "no2") if name in rows.columns]
        if is_forecast and aq_columns and any(pd.isna(row.get(name)) for name in aq_columns):
            notes.append("LK hiányzik")
        if pd.notna(row.get("temperature_2m_max")) and row.get("temperature_2m_max") > 38:
            notes.append("Hőség")
        if today is not None and date == today:
            notes.append("Mai nap")

        dtr = _number(row.get("DTR")) if monthly else _flagged_value(row.get("DTR"), "dtr")
        delta_p = _number(row.get("delta_P"), signed=True) if monthly else _flagged_value(row.get("delta_P"), "dp")
        body.append(
            f'<tr class="{" ".join(classes)}">'
            f"<td>{date_text}</td>"
            f"<td>{_score(row.get('risk_score'))}</td>"
            f"<td>{_tier_pill(row)}</td>"
            f"<td>{_number(row.get('temperature_2m_max'))}</td>"
            f"<td>{dtr}</td>"
            f"<td>{delta_p}</td>"
            f"<td>{_number(row.get('dew_point_2m_mean'))}</td>"
            f"<td>{_number(row.get('pm2_5'))}</td>"
            f"<td>{escape(', '.join(notes))}</td>"
            "</tr>"
        )

    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Dátum</th><th>Pontszám</th><th>Szint</th><th>Max °C</th>"
        "<th>DTR °C</th><th>ΔP hPa</th><th>Harmatpont °C</th>"
        "<th>PM₂,₅</th><th>Megjegyzés</th>"
        "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _driver_stats(rows: pd.DataFrame) -> list[dict]:
    contribution_rows = [
        compute_feature_contributions(row, RISK_WEIGHTS, FEATURE_RANGES)
        for _, row in rows.iterrows()
    ]
    stats = []
    for feature in DRIVER_FEATURES:
        values = [item[feature] for item in contribution_rows if feature in item]
        missing_pct = 100 * (1 - len(values) / len(rows)) if len(rows) else 100
        stats.append(
            {
                "feature": feature,
                "average": sum(values) / len(values) if values else 0,
                "peak": max(values) if values else 0,
                "missing_pct": missing_pct,
            }
        )
    return stats


def _drivers(rows: pd.DataFrame, paired: bool = False) -> str:
    stats = _driver_stats(rows)
    scale = max((item["peak"] for item in stats), default=0) or 1
    rendered = []
    for item in stats:
        feature = item["feature"]
        average_width = max(4, min(100, item["average"] / scale * 100))
        peak_width = max(4, min(100, item["peak"] / scale * 100))
        missing = item["missing_pct"]
        if missing == 100:
            value_text = "100% hiányzik"
        else:
            value_text = f"átlag {item['average']:.1%} · hiány {missing:.0f}%"
        tracks = (
            '<div class="driver-pair">'
            f'<div class="driver-track"><div class="driver-fill {DRIVER_CSS[feature]}" style="width:{average_width:.1f}%"></div></div>'
            f'<div class="driver-track driver-peak"><div class="driver-fill {DRIVER_CSS[feature]}" style="width:{peak_width:.1f}%"></div></div>'
            "</div>"
            if paired
            else f'<div class="driver-track"><div class="driver-fill {DRIVER_CSS[feature]}" style="width:{average_width:.1f}%"></div></div>'
        )
        rendered.append(
            '<div class="driver-row">'
            f"<strong>{escape(DRIVER_LABELS[feature])}</strong>{tracks}"
            f'<span class="driver-value">{escape(value_text)}</span></div>'
        )
    return '<div class="drivers">' + "".join(rendered) + "</div>"


def _card(label: str, value: str, note: str = "") -> str:
    return (
        '<div class="card">'
        f'<div class="card-label">{escape(label)}</div>'
        f'<div class="card-value">{escape(value)}</div>'
        f'<div class="card-note">{escape(note)}</div>'
        "</div>"
    )


def _daily_cards(rows: pd.DataFrame, today, forecast: pd.DataFrame) -> str:
    today_row = rows.loc[today]
    cards = [
        _card(
            "Ma",
            _score(today_row.get("risk_score")),
            f"DTR {_number(today_row.get('DTR'))} °C · ΔP {_number(today_row.get('delta_P'), signed=True)} hPa",
        )
    ]
    for position, label in enumerate(("Holnap", "Két nap múlva")):
        if position < len(forecast):
            row = forecast.iloc[position]
            cards.append(_card(label, _score(row.get("risk_score")), _driver_name(row)))
        else:
            cards.append(_card(label, "—", "Nincs elérhető előrejelzés"))
    scores = rows["risk_score"].dropna()
    score_range = f"{_score(scores.min())}–{_score(scores.max())}" if len(scores) else "—"
    cards.append(_card("Időszak tartománya", score_range, f"{len(rows)} nap"))
    return '<div class="cards">' + "".join(cards) + "</div>"


def _daily_info(rows: pd.DataFrame, today, forecast: pd.DataFrame) -> str:
    outlook = pd.concat([rows.loc[[today]], forecast])
    forecast_warn = any(_row_alert(row) for _, row in forecast.iterrows())
    scores = outlook["risk_score"].dropna().tolist()
    all_low = all(_tier(row) == "low" for _, row in outlook.iterrows())
    trending_down = len(scores) > 1 and all(right <= left for left, right in zip(scores, scores[1:]))
    if forecast_warn:
        kind, title = "warn", "Fokozott figyelem indokolt"
    elif all_low and trending_down:
        kind, title = "good", "Kedvező, csökkenő kockázati kép"
    else:
        kind, title = "neutral", "Következő napok áttekintése"

    upcoming = forecast if not forecast.empty else rows.loc[[today]]
    peak = upcoming.loc[upcoming["risk_score"].idxmax()] if upcoming["risk_score"].notna().any() else upcoming.iloc[0]
    streak = _longest_streak(rows.get("DTR", pd.Series(index=rows.index, dtype=float)).fillna(0) >= 13)
    return (
        f'<div class="info-box {kind}"><strong>{escape(title)}</strong>'
        '<div class="facts">'
        f"<span>Legmagasabb közelgő pontszám: <b>{_score(peak.get('risk_score'))}</b></span>"
        f"<span>Fő hajtóerő: <b>{escape(_driver_name(peak))}</b></span>"
        f"<span>DTR ≥ 13 °C leghosszabb sorozat: <b>{streak} nap</b></span>"
        "</div></div>"
    )


def _daily_notes(rows: pd.DataFrame, today, forecast: pd.DataFrame) -> str:
    today_row = rows.loc[today]
    feature, contribution = _primary_driver(today_row)
    notes = [
        f"A mai { _score(today_row.get('risk_score')) } kockázati pontszám fő hajtóereje: "
        f"<strong>{escape(DRIVER_LABELS.get(feature, feature or 'nem meghatározható'))}</strong>"
        + (f" ({contribution:.1%} pont-hozzájárulás)." if contribution is not None else ".")
    ]
    if not forecast.empty and forecast["risk_score"].notna().any():
        peak_date = forecast["risk_score"].idxmax()
        peak = forecast.loc[peak_date]
        notes.append(
            f"A következő két nap közül {_hu_date(peak_date)} a legmagasabb előrejelzett "
            f"kockázatú nap ({_score(peak.get('risk_score'))}, {escape(TIER_LABELS_HU[_tier(peak)].lower())})."
        )
    notes.append(
        "PM₂,₅, PM10, NO₂ előrejelzési napokra nem elérhetők — az előrejelzett "
        "pontszámok ezért alsó becslések."
    )
    kp_missing = 100.0
    if "Kp_daily_max" in rows.columns:
        kp_missing = rows["Kp_daily_max"].isna().mean() * 100
    if kp_missing == 100:
        notes.append(
            "A GFZ Potsdam Kp-index forrás 100%-ban hiányzó értékeket ad vissza. "
            "Nyitott adatforrás-hiba, javítása folyamatban."
        )
    else:
        notes.append(f"A Kp-index hiányaránya ebben az időszakban {kp_missing:.0f}%.")
    if "temperature_2m_max" in rows.columns and (rows["temperature_2m_max"] > 38).any():
        notes.append(
            "Legalább egy napon 38 °C feletti maximum várható. A modell a DTR-t pontozza, "
            "az abszolút hőterhelést nem méri külön."
        )
    notes.append(
        "A jelentés heurisztikus környezeti jelzőeszköz, nem validált klinikai műszer és nem helyettesít orvosi tanácsot."
    )
    return '<div class="note-box">' + "".join(f"<p>{note}</p>" for note in notes) + "</div>"


def _wellbeing(monthly: bool = False) -> str:
    prompt = (
        "Hasonlítsd össze a rögzített közérzetpontokat a fenti kiemelt események dátumaival."
        if monthly
        else "Jegyezd fel a mai közérzetedet, hogy később összevethető legyen a környezeti jelekkel."
    )
    dots = "".join(f'<span class="wellbeing-dot">{value}</span>' for value in range(11))
    return (
        '<div class="wellbeing"><strong>Közérzet-emlékeztető</strong>'
        f'<p>{escape(prompt)}</p><div class="wellbeing-scale">{dots}</div>'
        '<div class="muted">0 = nagyon rossz · 10 = kiváló</div></div>'
    )


def _page(title: str, eyebrow: str, subtitle: str, body: str, footer: str) -> str:
    css = STYLE_PATH.read_text(encoding="utf-8")
    return f"""<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&amp;family=JetBrains+Mono:wght@400;600;700&amp;display=swap" rel="stylesheet">
    <style>{css}</style>
</head>
<body><main class="report">
    <header class="panel"><div class="eyebrow">{escape(eyebrow)}</div>
    <h1>{escape(title)}</h1><div class="subtitle">{escape(subtitle)}</div></header>
    {body}
    <footer>{escape(footer)}</footer>
</main></body></html>
"""


def generate_daily_html_report(
    df: pd.DataFrame,
    output_dir: str | Path = REPORT_DIR,
    location_label: str = LOCATION_LABEL,
    report_city: str = REPORT_CITY,
    generated_at: datetime | None = None,
) -> Path:
    """Generate the 8 historical + 2 forecast daily HTML report."""
    frame = _prepare_frame(df)
    rows, today, forecast = _daily_slice(frame)
    generated_at = generated_at or datetime.now()
    subtitle = (
        f"{_hu_date(rows.index[0], True)} – {_hu_date(rows.index[-1], True)} · "
        f"Elmúlt 7 nap + mai nap ({_hu_date(today)}) + 2 napos előrejelzés"
    )
    body = (
        '<section class="panel">'
        + _daily_info(rows, today, forecast)
        + _daily_cards(rows, today, forecast)
        + "</section>"
        '<section class="panel"><h2>Részletes napi adatok</h2>'
        + _table(rows, today=today)
        + "</section>"
        '<section class="panel"><h2>Kockázati hajtóerők</h2>'
        + _drivers(rows)
        + "</section>"
        '<section class="panel"><h2>Rövid összefoglaló</h2>'
        + _daily_notes(rows, today, forecast)
        + _wellbeing()
        + "</section>"
    )
    footer = (
        f"copd-vs-weather pipeline · Készült: {generated_at:%Y-%m-%d %H:%M} · "
        f"Helyszín: {location_label} · Adatok: Open-Meteo, GFZ Potsdam"
    )
    html = _page(
        "Környezeti kockázati jelentés",
        f"copd-vs-weather · {report_city}",
        subtitle,
        body,
        footer,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"kockázati_jelentés_{today:%Y-%m-%d}.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _weekly_table(rows: pd.DataFrame) -> str:
    working = rows.copy()
    iso = working.index.isocalendar()
    working["_iso_year"] = iso.year.to_numpy()
    working["_iso_week"] = iso.week.to_numpy()
    body = []
    for (year, week), group in working.groupby(["_iso_year", "_iso_week"], sort=True):
        scores = group["risk_score"].dropna()
        max_score = scores.max() if len(scores) else float("nan")
        pm_mean = group["pm2_5"].mean() if "pm2_5" in group else float("nan")
        dtr_days = int((group.get("DTR", pd.Series(index=group.index, dtype=float)) >= 13).sum())
        dp_days = int((group.get("delta_P", pd.Series(index=group.index, dtype=float)).abs() >= 3).sum())
        highest = classify_risk_score(max_score)
        body.append(
            "<tr>"
            f"<td>{int(year)}–W{int(week):02d}</td>"
            f"<td>{_score(scores.mean())}</td><td>{_score(max_score)}</td>"
            f"<td>{dtr_days}</td><td>{dp_days}</td><td>{_number(pm_mean)}</td>"
            f'<td><span class="tier-pill tier-{highest}">{escape(TIER_LABELS_HU[highest])}</span></td>'
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Hét</th><th>Átlag score</th>'
        "<th>Max score</th><th>DTR ≥ 13 nap</th><th>ΔP esemény</th>"
        "<th>PM₂,₅ átlag</th><th>Legmagasabb kockázat</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _sparkline(values: pd.Series, tiers: pd.Series | None = None, threshold=None) -> str:
    numeric = pd.to_numeric(values, errors="coerce")
    maximum = numeric.max()
    scale = float(maximum) if pd.notna(maximum) and maximum > 0 else 1.0
    bars = []
    for position, (date, value) in enumerate(numeric.items()):
        height = 3 if pd.isna(value) else max(3, min(44, float(value) / scale * 44))
        css_class = ""
        if tiers is not None:
            tier = tiers.iloc[position]
            css_class = f" tier-{tier if tier in TIER_LABELS_HU else 'unknown'}"
        title = f"{_hu_date(date)}: {_number(value, 3)}"
        bars.append(
            f'<span class="spark-bar{css_class}" style="height:{height:.1f}px" title="{escape(title)}"></span>'
        )
    line = ""
    if threshold is not None:
        bottom = max(0, min(44, float(threshold) / scale * 44))
        line = f'<span class="threshold-line" style="bottom:{bottom:.1f}px" title="Küszöb: {threshold}"></span>'
    return f'<div class="spark-wrap">{line}{"".join(bars)}</div>'


def _monthly_events(rows: pd.DataFrame) -> str:
    events = []
    elevated = rows[rows.apply(lambda row: _tier(row) in ELEVATED_TIERS, axis=1)]
    if not elevated.empty:
        dates = ", ".join(_hu_date(date) for date in elevated.index)
        events.append(f"Emelkedett kockázatú napok: {dates}.")

    dtr = rows.get("DTR", pd.Series(index=rows.index, dtype=float)).fillna(0)
    for start, end, count in _streak_ranges(rows, dtr >= 13, 3):
        events.append(f"DTR ≥ 13 °C sorozat: {_hu_date(start)}–{_hu_date(end)} ({count} nap).")

    delta_p = rows.get("delta_P", pd.Series(index=rows.index, dtype=float))
    for date, value in delta_p[delta_p.abs() >= 5].items():
        events.append(f"Jelentős légnyomásesemény {_hu_date(date)}: {_number(value, signed=True)} hPa.")

    pm = rows.get("pm2_5", pd.Series(index=rows.index, dtype=float)).fillna(0)
    for start, end, count in _streak_ranges(rows, pm > 10, 3):
        events.append(f"PM₂,₅ > 10 µg/m³ sorozat: {_hu_date(start)}–{_hu_date(end)} ({count} nap).")

    if not events:
        events.append("A meghatározott küszöbök szerint nem volt kiemelendő esemény.")
    return '<ul class="event-list">' + "".join(f"<li>{escape(item)}</li>" for item in events) + "</ul>"


def _monthly_cards(rows: pd.DataFrame) -> str:
    elevated = sum(_tier(row) in ELEVATED_TIERS for _, row in rows.iterrows())
    dtr = rows.get("DTR", pd.Series(index=rows.index, dtype=float))
    delta_p = rows.get("delta_P", pd.Series(index=rows.index, dtype=float))
    pm_roll = rows.get("pm2_5_roll7d", rows.get("pm2_5", pd.Series(index=rows.index, dtype=float))).dropna()
    pm_value = pm_roll.iloc[-1] if len(pm_roll) else float("nan")
    cards = [
        _card("Átlagos kockázat", _score(rows["risk_score"].mean())),
        _card("Mérsékelt+ napok", str(elevated)),
        _card("DTR ≥ 13 °C napok", str(int((dtr >= 13).sum()))),
        _card("|ΔP| ≥ 3 hPa napok", str(int((delta_p.abs() >= 3).sum()))),
        _card("PM₂,₅ 7 napos érték", f"{_number(pm_value)} µg/m³"),
        _card("Leghosszabb DTR-sorozat", f"{_longest_streak((dtr >= 13).fillna(False))} nap"),
    ]
    return '<div class="cards">' + "".join(cards) + "</div>"


def generate_monthly_html_report(
    df: pd.DataFrame,
    output_dir: str | Path = REPORT_DIR,
    location_label: str = LOCATION_LABEL,
    report_city: str = REPORT_CITY,
    generated_at: datetime | None = None,
) -> Path:
    """Generate a 30-historical-day monthly overview HTML report."""
    frame = _prepare_frame(df)
    rows = _monthly_slice(frame)
    generated_at = generated_at or datetime.now()
    tiers = rows.apply(_tier, axis=1)
    pm_series = rows.get("pm2_5_roll7d", rows.get("pm2_5", pd.Series(index=rows.index, dtype=float)))
    dtr_series = rows.get("DTR", pd.Series(index=rows.index, dtype=float))
    spark_section = (
        '<div class="spark-section">'
        f"<div><strong>Napi kockázati pontszám</strong>{_sparkline(rows['risk_score'], tiers)}</div>"
        f"<div><strong>PM₂,₅ 7 napos gördülő átlag</strong>{_sparkline(pm_series)}</div>"
        f"<div><strong>DTR 30 napos trend</strong>{_sparkline(dtr_series, threshold=13)}</div>"
        "</div>"
    )
    body = (
        '<section class="panel"><h2>Időszaki összefoglaló</h2>'
        + _monthly_cards(rows)
        + "</section>"
        '<section class="panel"><h2>Heti bontás</h2>'
        + _weekly_table(rows)
        + "</section>"
        '<section class="panel"><h2>30 nap részletes adatai</h2>'
        + _table(rows, monthly=True)
        + "</section>"
        '<section class="panel"><h2>Trendek</h2>'
        + spark_section
        + "</section>"
        '<section class="panel"><h2>Kiemelt események</h2>'
        + _monthly_events(rows)
        + "</section>"
        '<section class="panel"><h2>Hajtóerők — átlag és csúcs</h2>'
        + _drivers(rows, paired=True)
        + _wellbeing(monthly=True)
        + "</section>"
    )
    subtitle = f"{_hu_date(rows.index[0], True)} – {_hu_date(rows.index[-1], True)}"
    footer = (
        f"copd-vs-weather pipeline · Készült: {generated_at:%Y-%m-%d %H:%M} · "
        f"Helyszín: {location_label} · Adatok: Open-Meteo, GFZ Potsdam"
    )
    html = _page(
        "Havi környezeti kockázati áttekintés",
        f"copd-vs-weather · {report_city} — Havi áttekintés",
        subtitle,
        body,
        footer,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    end_date = rows.index[-1]
    output_path = output_dir / f"havi_jelentés_{end_date:%Y-%m}.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="COPD HTML kockázati jelentés készítése.")
    parser.add_argument("period", choices=("daily", "monthly", "both"))
    parser.add_argument("csv_path", nargs="?", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args()
    try:
        df = pd.read_csv(args.csv_path)
        paths = []
        if args.period in {"daily", "both"}:
            paths.append(generate_daily_html_report(df, args.output_dir))
        if args.period in {"monthly", "both"}:
            paths.append(generate_monthly_html_report(df, args.output_dir))
    except (FileNotFoundError, ValueError, pd.errors.EmptyDataError) as exc:
        print(f"HIBA: {exc}")
        return 2
    for path in paths:
        print(f"HTML jelentés mentve -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
