"""Generate standalone Hungarian daily and monthly COPD risk reports."""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

import pandas as pd

from config import OUTPUT_CSV, REPORT_DIR
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
SCORE_Y_RANGE = (0.0, 1.0)
LANE_MIN_DAY_STEP_PX = 28
LANE_DAILY_DAY_STEP_PX = 36
LANE_MONTHLY_DAY_STEP_PX = 31.5
METRIC_ORDER = (
    "risk_score",
    "temperature",
    "DTR",
    "delta_P",
    "dew_point_2m_mean",
    "precipitation_sum",
    "windspeed_10m_max",
    "pm2_5",
    "pm10",
    "no2",
)
LANE_ORDER = (
    "risk_score",
    "temperature",
    "DTR",
    "delta_P",
    "dew_point_2m_mean",
    "precipitation_sum",
    "windspeed_10m_max",
    "air_quality",
)
CARD_METRIC_LABELS = {
    "temperature": "Hőmérséklet max./min.",
    "DTR": "DTR",
    "delta_P": "Légnyomás-változás",
    "dew_point_2m_mean": "Harmatpont",
    "precipitation_sum": "Csapadék",
    "windspeed_10m_max": "Max. szélsebesség",
    "pm2_5": "PM₂,₅",
    "pm10": "PM₁₀",
    "no2": "NO₂",
}
LANE_DEFINITIONS = {
    "risk_score": {
        "label": "Pontszám",
        "series": (("risk_score", "score"),),
        "fixed_range": SCORE_Y_RANGE,
        "include_zero": False,
    },
    "temperature": {
        "label": "Hőm. max/min (°C)",
        "series": (
            ("temperature_2m_max", "temperature-max"),
            ("temperature_2m_min", "temperature-min"),
        ),
        "include_zero": False,
    },
    "DTR": {
        "label": "DTR (°C)",
        "series": (("DTR", "dtr"),),
        "include_zero": False,
    },
    "delta_P": {
        "label": "ΔP (hPa)",
        "series": (("delta_P", "pressure"),),
        "include_zero": True,
    },
    "dew_point_2m_mean": {
        "label": "Harmatpont (°C)",
        "series": (("dew_point_2m_mean", "dew"),),
        "include_zero": False,
    },
    "precipitation_sum": {
        "label": "Csapadék (mm)",
        "series": (("precipitation_sum", "precipitation"),),
        "include_zero": True,
    },
    "windspeed_10m_max": {
        "label": "Max. szél (km/h)",
        "series": (("windspeed_10m_max", "wind"),),
        "include_zero": True,
    },
    "air_quality": {
        "label": "Légszennyezők (µg/m³)",
        "series": (
            ("pm2_5", "pm25"),
            ("pm10", "pm10"),
            ("no2", "no2"),
        ),
        "include_zero": True,
    },
}


def _location_code(location_label: str) -> str:
    """Derive a three-letter filename code from the place name."""
    place_name = location_label.split(",", 1)[0].strip()
    normalized = unicodedata.normalize("NFKD", place_name)
    ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
    code = re.sub(r"[^A-Za-z]", "", ascii_label).upper()[:3]
    return code if len(code) == 3 else "LOC"
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
    "no2": "Nitrogén-dioxid (NO₂)",
    "pm10": "Szálló por (PM10)",
}
DRIVER_CSS = {
    "DTR": "driver-dtr",
    "pm2_5": "driver-pm",
    "delta_P": "driver-dp",
    "dew_point_2m_mean": "driver-dew",
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


def _with_unit(value, unit: str, decimals: int = 1, signed: bool = False) -> str:
    formatted = _number(value, decimals, signed)
    return formatted if formatted == "—" else f"{formatted} {unit}"


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


def _lane_chart_records(rows: pd.DataFrame, today) -> list[dict]:
    records = []
    forecast_mask = _forecast_mask(rows)
    today = pd.Timestamp(today) if today is not None else None
    previous_date = None

    for date, row in rows.iterrows():
        date = pd.Timestamp(date)
        is_forecast = bool(forecast_mask.loc[date])
        is_today = today is not None and date == today
        score = pd.to_numeric(row.get("risk_score"), errors="coerce")
        score = None if pd.isna(score) else float(score)

        def with_unit(column: str, unit: str, signed: bool = False) -> str:
            return _with_unit(row.get(column), unit, signed=signed)

        temperature_max = _number(row.get("temperature_2m_max"))
        temperature_min = _number(row.get("temperature_2m_min"))
        temperature_pair = (
            "—"
            if temperature_max == "—" and temperature_min == "—"
            else f"{temperature_max} / {temperature_min} °C"
        )
        card_values = {
            "temperature": temperature_pair,
            "DTR": with_unit("DTR", "°C"),
            "delta_P": with_unit("delta_P", "hPa", signed=True),
            "dew_point_2m_mean": with_unit("dew_point_2m_mean", "°C"),
            "precipitation_sum": with_unit("precipitation_sum", "mm"),
            "windspeed_10m_max": with_unit("windspeed_10m_max", "km/h"),
            "pm2_5": with_unit("pm2_5", "µg/m³"),
            "pm10": with_unit("pm10", "µg/m³"),
            "no2": with_unit("no2", "µg/m³"),
        }
        card_rows = [
            [CARD_METRIC_LABELS[key], card_values[key]]
            for key in METRIC_ORDER
            if key in CARD_METRIC_LABELS
        ]
        note = (
            "Alsó becslés: PM és NO₂ hiányzik"
            if is_forecast
            else ""
        )
        has_new_month = (
            previous_date is None
            or date.month != previous_date.month
            or date.year != previous_date.year
        )
        month_label = MONTHS_HU[date.month] if has_new_month else None
        day_label = f"{date.day}."
        short_label = (
            f"{month_label} {day_label}" if month_label else day_label
        )
        tier = _tier(row)
        badge_text = "Ma" if is_today else "Előrejelzés" if is_forecast else ""
        badge_class = (
            "lane-card-badge badge-today"
            if is_today
            else "lane-card-badge badge-forecast"
            if is_forecast
            else "lane-card-badge"
        )
        status_parts = [short_label]
        if is_today:
            status_parts.append("ma")
        elif is_forecast:
            status_parts.append("előrejelzés")
        status_parts.extend((f"pontszám {_score(score)}", TIER_LABELS_HU[tier].lower()))
        records.append(
            {
                "date_label": _hu_date(date, include_year=True),
                "short_label": short_label,
                "month_label": month_label,
                "day_label": day_label,
                "score_text": _score(score),
                "score": score,
                "tier_key": tier,
                "tier_label": TIER_LABELS_HU[tier],
                "badge_text": badge_text,
                "badge_class": badge_class,
                "status_text": ", ".join(status_parts),
                "is_forecast": is_forecast,
                "is_today": is_today,
                "card_rows": card_rows,
                "note": note,
            }
        )
        previous_date = date

    return records


def _lane_scale(
    rows: pd.DataFrame,
    columns: str | Iterable[str],
    fixed_range: tuple[float, float] | None = None,
    include_zero: bool = False,
) -> tuple[float | None, float | None, str, str]:
    if fixed_range is not None:
        low, high = fixed_range
        return low, high, _number(low, 2), _number(high, 2)

    if isinstance(columns, str):
        columns = (columns,)
    values_by_column = [
        pd.to_numeric(rows[column], errors="coerce")
        for column in columns
        if column in rows
    ]
    values = (
        pd.concat(values_by_column, ignore_index=True)
        if values_by_column
        else pd.Series(dtype=float)
    ).dropna()
    if values.empty:
        return None, None, "—", "—"

    actual_low, actual_high = float(values.min()), float(values.max())
    low, high = actual_low, actual_high
    if include_zero:
        low, high = min(low, 0.0), max(high, 0.0)
    elif low == high:
        padding = max(abs(low) * 0.1, 0.5)
        low, high = low - padding, high + padding

    tick_low, tick_high = low, high
    if actual_low == actual_high and not include_zero:
        tick_low = tick_high = actual_low
    return low, high, _number(tick_low), _number(tick_high)


def _lane_chart(rows: pd.DataFrame, today) -> str:
    records = _lane_chart_records(rows, today)
    day_count = len(records)
    default_index = day_count - 1
    for index, record in enumerate(records):
        if record["is_today"]:
            default_index = index
            break

    render_scale = 600 / 640
    target_day_step = (
        LANE_MONTHLY_DAY_STEP_PX if day_count > 10 else LANE_DAILY_DAY_STEP_PX
    )
    day_step_units = math.ceil(
        max(LANE_MIN_DAY_STEP_PX, target_day_step) / render_scale
    )
    plot_left, plot_right_margin = 150, 12
    lanes = []
    lane_top = 16
    for metric_key in LANE_ORDER:
        lane = LANE_DEFINITIONS[metric_key]
        lane_height = 60 if metric_key == "risk_score" else 46
        lanes.append((metric_key, lane, lane_top, lane_top + lane_height))
        lane_top += lane_height + 10

    plot_bottom = lanes[-1][3]
    month_label_y = plot_bottom + 24
    day_label_y = plot_bottom + 42
    view_width = plot_left + day_count * day_step_units + plot_right_margin
    view_height = day_label_y + 18
    render_width = round(view_width * render_scale)
    render_height = round(view_height * render_scale)
    plot_right = view_width - plot_right_margin
    plot_width = plot_right - plot_left
    day_step = plot_width / day_count
    x_positions = [plot_left + day_step * (index + 0.5) for index in range(day_count)]

    lane_markup = []
    points = []
    hit_columns = []
    for metric_key, lane, top, bottom in lanes:
        label = lane["label"]
        series = lane["series"]
        columns = tuple(column for column, _ in series)
        low, high, tick_low, tick_high = _lane_scale(
            rows,
            columns,
            fixed_range=lane.get("fixed_range"),
            include_zero=lane["include_zero"],
        )
        center_y = (top + bottom) / 2
        lane_markup.append(
            f'<text class="lane-label" data-metric="{metric_key}" '
            f'x="8" y="{center_y + 4:.1f}">'
            f"{escape(label)}</text>"
            f'<text class="lane-axis-text" x="{plot_left - 8}" y="{top + 4}" '
            f'text-anchor="end">{escape(tick_high)}</text>'
            f'<text class="lane-axis-text" x="{plot_left - 8}" y="{bottom + 4}" '
            f'text-anchor="end">{escape(tick_low)}</text>'
            f'<line class="lane-boundary" x1="{plot_left}" y1="{top}" '
            f'x2="{plot_right}" y2="{top}"></line>'
            f'<line class="lane-boundary" x1="{plot_left}" y1="{bottom}" '
            f'x2="{plot_right}" y2="{bottom}"></line>'
        )

        if (
            metric_key == "delta_P"
            and low is not None
            and high is not None
            and low <= 0 <= high
        ):
            zero_y = bottom - (0 - low) / (high - low) * (bottom - top)
            lane_markup.append(
                f'<line class="lane-zero-line" x1="{plot_left}" y1="{zero_y:.2f}" '
                f'x2="{plot_right}" y2="{zero_y:.2f}"></line>'
            )

        for column, series_id in series:
            values = []
            for index, (_, row) in enumerate(rows.iterrows()):
                value = pd.to_numeric(row.get(column), errors="coerce")
                if low is None or high is None or pd.isna(value):
                    values.append(None)
                    continue
                if high == low:
                    y = (top + bottom) / 2
                else:
                    y = bottom - (float(value) - low) / (high - low) * (bottom - top)
                values.append(
                    {
                        "index": index,
                        "x": x_positions[index],
                        "y": y,
                        "is_forecast": records[index]["is_forecast"],
                        "tier_key": records[index]["tier_key"],
                    }
                )

            for previous, current in zip(values, values[1:]):
                if previous is None or current is None:
                    continue
                forecast_segment = previous["is_forecast"] or current["is_forecast"]
                line_classes = f"lane-series-line lane-{series_id}-line"
                if forecast_segment:
                    line_classes += " forecast-segment"
                lane_markup.append(
                    f'<path class="{line_classes}" data-lane="{column}" '
                    f'data-start-index="{previous["index"]}" '
                    f'data-end-index="{current["index"]}" '
                    f'd="M{previous["x"]:.2f},{previous["y"]:.2f} '
                    f'L{current["x"]:.2f},{current["y"]:.2f}"></path>'
                )

            for point in values:
                if point is None:
                    continue
                selected = point["index"] == default_index
                if series_id == "score":
                    point_classes = (
                        f'lane-point lane-score-point tier-{point["tier_key"]}'
                    )
                    radius = 8 if selected else 5
                elif series_id in {"pm25", "pm10"}:
                    point_classes = f"lane-point lane-{series_id}-point"
                    radius = 3 if selected else 2
                else:
                    point_classes = f"lane-point lane-{series_id}-point"
                    radius = 6 if selected else 4
                if point["is_forecast"]:
                    point_classes += " forecast-point"
                if selected:
                    point_classes += " is-selected"
                points.append(
                    f'<circle class="{point_classes}" data-lane="{column}" '
                    f'data-index="{point["index"]}" cx="{point["x"]:.2f}" '
                    f'cy="{point["y"]:.2f}" r="{radius}"></circle>'
                )

    x_labels = []
    for index, (record, x) in enumerate(zip(records, x_positions)):
        if record["month_label"]:
            x_labels.append(
                f'<text class="lane-x-month-label" data-index="{index}" '
                f'x="{x:.2f}" y="{month_label_y}" text-anchor="middle">'
                f'{escape(record["month_label"])}</text>'
            )
        x_labels.append(
            f'<text class="lane-x-label" data-index="{index}" x="{x:.2f}" '
            f'y="{day_label_y}" text-anchor="middle">'
            f'{escape(record["day_label"])}</text>'
        )

    selected_x = x_positions[default_index]
    selection_line = (
        f'<line class="lane-selected-line" x1="{selected_x:.2f}" '
        f'x2="{selected_x:.2f}" y1="8" y2="{plot_bottom}"></line>'
    )
    for index, x in enumerate(x_positions):
        hit_columns.append(
            f'<rect class="lane-hit-column" data-index="{index}" '
            f'data-center="{x:.2f}" x="{plot_left + index * day_step:.2f}" '
            f'y="8" width="{day_step:.2f}" height="{plot_bottom - 8}"></rect>'
        )

    tier_legend = "".join(
        f'<span class="lane-legend-item"><span class="lane-legend-dot tier-{tier}">'
        f"</span>{escape(label)}</span>"
        for tier, label in TIER_LABELS_HU.items()
    )
    temperature_legend = (
        '<span class="lane-legend-item"><span class="lane-legend-line '
        'lane-temperature-max-line"></span>Max. hőmérséklet</span>'
        '<span class="lane-legend-item"><span class="lane-legend-line '
        'lane-temperature-min-line"></span>Min. hőmérséklet</span>'
    )
    air_quality_legend = (
        '<span class="lane-legend-item"><span class="lane-legend-line '
        'lane-pm25-line"></span>PM₂,₅</span>'
        '<span class="lane-legend-item"><span class="lane-legend-line '
        'lane-pm10-line"></span>PM₁₀</span>'
        '<span class="lane-legend-item"><span class="lane-legend-line '
        'lane-no2-line"></span>NO₂</span>'
    )
    legend = (
        '<div class="lane-legend">'
        + temperature_legend
        + air_quality_legend
        + tier_legend
        + '<span class="lane-legend-item"><span class="lane-legend-ring"></span>'
        "üres karika = előrejelzés</span></div>"
    )

    selected = records[default_index]
    card_rows = "".join(
        f'<div class="lane-card-row"><dt>{escape(label)}</dt>'
        f'<dd class="lane-card-value">{escape(value)}</dd></div>'
        for label, value in selected["card_rows"]
    )
    card = (
        '<aside class="lane-card" aria-label="Kiválasztott nap adatai">'
        '<div class="lane-card-heading">'
        f'<strong data-card-date>{escape(selected["date_label"])}</strong>'
        f'<span class="{selected["badge_class"]}" data-card-badge>'
        f'{escape(selected["badge_text"])}</span>'
        "</div>"
        '<div class="lane-card-score">'
        f'<span class="lane-card-score-value" data-card-score>'
        f'{escape(selected["score_text"])}</span>'
        f'<span class="tier-pill tier-{selected["tier_key"]}" '
        f'data-card-tier>{escape(selected["tier_label"])}</span>'
        "</div>"
        f'<dl class="lane-card-rows">{card_rows}</dl>'
        '<div class="lane-card-note"><strong>Megjegyzés</strong>'
        f'<span data-card-note>{escape(selected["note"])}</span></div>'
        "</aside>"
    )
    json_data = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    json_data = json_data.replace("</", "<\\/")
    return (
        '<div class="lane-chart">'
        '<div class="lane-chart-layout"><div class="lane-chart-main">'
        '<div class="lane-chart-frame">'
        f'<svg class="lane-chart-svg" width="{render_width}" height="{render_height}" '
        f'style="min-width:{render_width}px" '
        f'viewBox="0 0 {view_width} {view_height}" tabindex="0" role="application" '
        'aria-label="Napi kockázati és időjárási adatok" '
        'aria-describedby="lane-chart-status" '
        f'data-selected-index="{default_index}">'
        + "".join(lane_markup)
        + selection_line
        + "".join(points)
        + "".join(x_labels)
        + "".join(hit_columns)
        + "</svg></div>"
        + legend
        + "</div>"
        + card
        + '</div><div class="visually-hidden" id="lane-chart-status" '
        'aria-live="polite"></div>'
        f'<script type="application/json" class="chart-data">{json_data}</script>'
        "<script>"
        "(function(){"
        'var root=document.currentScript.parentElement;'
        'var data=JSON.parse(root.querySelector(".chart-data").textContent);'
        'var svg=root.querySelector(".lane-chart-svg");'
        'var frame=root.querySelector(".lane-chart-frame");'
        'var columns=Array.from(svg.querySelectorAll(".lane-hit-column"));'
        'var selectionLine=svg.querySelector(".lane-selected-line");'
        'var cardDate=root.querySelector("[data-card-date]");'
        'var cardBadge=root.querySelector("[data-card-badge]");'
        'var cardScore=root.querySelector("[data-card-score]");'
        'var cardTier=root.querySelector("[data-card-tier]");'
        'var cardValues=Array.from(root.querySelectorAll(".lane-card-value"));'
        'var cardNote=root.querySelector("[data-card-note]");'
        'var status=root.querySelector("#lane-chart-status");'
        'var pinnedIndex=Number(svg.getAttribute("data-selected-index"));'
        'var activeIndex=pinnedIndex;'
        "function render(index, announce){"
        "var day=data[index];"
        "activeIndex=index;"
        'svg.setAttribute("data-selected-index",String(index));'
        'selectionLine.setAttribute("x1",columns[index].getAttribute("data-center"));'
        'selectionLine.setAttribute("x2",columns[index].getAttribute("data-center"));'
        'cardDate.textContent=day.date_label;'
        "cardBadge.textContent=day.badge_text;"
        "cardBadge.className=day.badge_class;"
        'cardScore.textContent=day.score_text;'
        'cardTier.textContent=day.tier_label;'
        'cardTier.className="tier-pill tier-"+day.tier_key;'
        "day.card_rows.forEach(function(row,index){"
        "cardValues[index].textContent=row[1];"
        "});"
        'cardNote.textContent=day.note;'
        'svg.querySelectorAll(".lane-point").forEach(function(point){'
        'var selected=Number(point.getAttribute("data-index"))===index;'
        'point.classList.toggle("is-selected",selected);'
        'if(point.classList.contains("lane-score-point"))'
        'point.setAttribute("r",selected?"8":"5");'
        'else if(point.classList.contains("lane-pm25-point")||'
        'point.classList.contains("lane-pm10-point"))'
        'point.setAttribute("r",selected?"3":"2");'
        'else point.setAttribute("r",selected?"6":"4");'
        "});"
        "if(announce){"
        "status.textContent=day.status_text;"
        "}"
        "}"
        "function keepColumnVisible(index){"
        "var rect=columns[index].getBoundingClientRect();"
        "var bounds=frame.getBoundingClientRect();"
        "if(rect.left<bounds.left)frame.scrollLeft-=bounds.left-rect.left;"
        "else if(rect.right>bounds.right)frame.scrollLeft+=rect.right-bounds.right;"
        "}"
        "function choose(index,pin){"
        "index=Math.max(0,Math.min(data.length-1,index));"
        "if(pin)pinnedIndex=index;"
        "render(index,true);"
        "keepColumnVisible(index);"
        "}"
        'svg.addEventListener("pointermove",function(event){'
        'if(event.pointerType!=="mouse")return;'
        'var hit=event.target.closest(".lane-hit-column");'
        'if(hit)choose(Number(hit.getAttribute("data-index")),false);'
        "});"
        'svg.addEventListener("pointerleave",function(event){'
        'if(event.pointerType==="mouse")render(pinnedIndex,true);'
        "});"
        'svg.addEventListener("click",function(event){'
        'var hit=event.target.closest(".lane-hit-column");'
        'if(hit)choose(Number(hit.getAttribute("data-index")),true);'
        "});"
        'svg.addEventListener("pointerdown",function(event){'
        'if(event.pointerType!=="touch")return;'
        'var hit=event.target.closest(".lane-hit-column");'
        'if(hit)choose(Number(hit.getAttribute("data-index")),true);'
        "});"
        'svg.addEventListener("keydown",function(event){'
        "var next=pinnedIndex;"
        'if(event.key==="ArrowLeft")next-=1;'
        'else if(event.key==="ArrowRight")next+=1;'
        'else if(event.key==="Home")next=0;'
        'else if(event.key==="End")next=data.length-1;'
        "else return;"
        "event.preventDefault();"
        "choose(next,true);"
        "});"
        "render(pinnedIndex,true);"
        "})();"
        "</script></div>"
    )


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
            notes.append("Levegőminőség hiányzik")
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
        (
            date,
            compute_feature_contributions(row, RISK_WEIGHTS, FEATURE_RANGES),
        )
        for date, row in rows.iterrows()
    ]
    stats = []
    for feature in DRIVER_FEATURES:
        values = [
            (date, contributions[feature])
            for date, contributions in contribution_rows
            if feature in contributions
        ]
        peak_date, peak = (
            max(values, key=lambda item: item[1]) if values else (None, 0)
        )
        stats.append(
            {
                "feature": feature,
                "average": (
                    sum(value for _, value in values) / len(values)
                    if values
                    else 0
                ),
                "peak": peak,
                "peak_date": peak_date,
            }
        )
    return stats


def _drivers(rows: pd.DataFrame) -> str:
    stats = _driver_stats(rows)
    rendered = []
    for item in stats:
        feature = item["feature"]
        average_width = max(0, min(100, item["average"] * 100))
        peak_width = max(0, min(100, item["peak"] * 100))
        if item["peak_date"] is None:
            value_parts = ["Nincs adat", "Csúcs dátuma: —"]
        else:
            value_parts = [
                f"Átlag: {_number(item['average'], 3)} pont",
                f"Csúcs: {_number(item['peak'], 3)} pont",
                f"Csúcs dátuma: "
                f"{_hu_date(item['peak_date'], include_year=True)}",
            ]
        value_markup = "".join(
            f"<span>{escape(part)}</span>" for part in value_parts
        )
        tracks = (
            '<div class="driver-pair">'
            f'<div class="driver-track"><div class="driver-fill {DRIVER_CSS[feature]}" style="width:{average_width:.1f}%"></div></div>'
            f'<div class="driver-track driver-peak"><div class="driver-fill {DRIVER_CSS[feature]}" style="width:{peak_width:.1f}%"></div></div>'
            "</div>"
        )
        rendered.append(
            '<div class="driver-row">'
            '<div class="driver-label">'
            f"<strong>{escape(DRIVER_LABELS[feature])}</strong>"
            f'<span class="driver-weight">Pontszámsúly: '
            f'{_number(RISK_WEIGHTS[feature] * 100, 1)}%</span></div>{tracks}'
            f'<span class="driver-value">{value_markup}</span></div>'
        )
    legend = (
        '<div class="driver-legend">'
        '<span class="driver-legend-item"><span class="driver-legend-swatch">'
        "</span>Átlag</span>"
        '<span class="driver-legend-item"><span class="driver-legend-swatch '
        'driver-peak-swatch"></span>Időszaki csúcs</span>'
        + "</div>"
    )
    scale_note = (
        '<p class="driver-scale-note">A sávhossz közvetlenül arányos a '
        'pontszám-hozzájárulással: a teljes sáv 1,000 pontot jelent a 0–1-es '
        'skálán. Az átlag csak az adott tényezővel rendelkező napokra '
        'vonatkozik. A „Csúcs dátuma” a legnagyobb napi hozzájárulás első '
        'előfordulása. A megjelenített pontszámsúly az alapmodell súlya; a '
        'modell a rendelkezésre álló bemenetek súlyait naponta '
        'újranormalizálja. Csak négy bemeneti tényező szerepel itt, ezért a '
        'sávok nem adják ki a teljes pontszámot.'
        "</p>"
    )
    return scale_note + legend + '<div class="drivers">' + "".join(rendered) + "</div>"


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
        + (
            f" ({_number(contribution, 3)} pont-hozzájárulás)."
            if contribution is not None
            else "."
        )
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
    location_label: str = "Selected location",
    report_city: str | None = None,
    generated_at: datetime | None = None,
) -> Path:
    """Generate the 10-day (8 historical + today + 2 forecast) HTML report."""
    frame = _prepare_frame(df)
    rows, today, forecast = _daily_slice(frame)
    generated_at = generated_at or datetime.now()
    report_city = report_city or location_label
    subtitle = (
        f"{_hu_date(rows.index[0], True)} – {_hu_date(rows.index[-1], True)} · "
        f"Elmúlt 7 nap + mai nap ({_hu_date(today)}) + 2 napos előrejelzés"
    )
    body = (
        '<section class="panel">'
        + _daily_info(rows, today, forecast)
        + _daily_cards(rows, today, forecast)
        + "</section>"
        '<section class="panel"><h2>Napi kockázati trend</h2>'
        + _lane_chart(rows, today)
        + "</section>"
        '<section class="panel"><h2>Részletes napi adatok</h2>'
        + _table(rows, today=today)
        + "</section>"
        '<section class="panel"><h2>Kockázati hajtóerők — átlag és csúcs</h2>'
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
        "10 napos környezeti kockázati jelentés",
        f"copd-vs-weather · {report_city}",
        subtitle,
        body,
        footer,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    location_code = _location_code(location_label)
    output_path = output_dir / (
        f"kockázati_jelentés_10nap_{location_code}_{today:%Y-%m-%d}.html"
    )
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
    location_label: str = "Selected location",
    report_city: str | None = None,
    generated_at: datetime | None = None,
) -> Path:
    """Generate a 30-historical-day overview HTML report."""
    frame = _prepare_frame(df)
    rows = _monthly_slice(frame)
    today = rows.index[-1]
    generated_at = generated_at or datetime.now()
    report_city = report_city or location_label
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
        + _lane_chart(rows, today)
        + "</section>"
        '<section class="panel"><h2>Kiemelt események</h2>'
        + _monthly_events(rows)
        + "</section>"
        '<section class="panel"><h2>Kockázati hajtóerők — átlag és csúcs</h2>'
        + _drivers(rows)
        + _wellbeing(monthly=True)
        + "</section>"
    )
    subtitle = f"{_hu_date(rows.index[0], True)} – {_hu_date(rows.index[-1], True)}"
    footer = (
        f"copd-vs-weather pipeline · Készült: {generated_at:%Y-%m-%d %H:%M} · "
        f"Helyszín: {location_label} · Adatok: Open-Meteo, GFZ Potsdam"
    )
    html = _page(
        "30 napos környezeti kockázati áttekintés",
        f"copd-vs-weather · {report_city} — 30 napos áttekintés",
        subtitle,
        body,
        footer,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    end_date = rows.index[-1]
    location_code = _location_code(location_label)
    output_path = output_dir / (
        f"kockázati_jelentés_30nap_{location_code}_{end_date:%Y-%m}.html"
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="COPD HTML kockázati jelentés készítése.")
    parser.add_argument("period", choices=("daily", "monthly", "both"))
    parser.add_argument("csv_path", nargs="?", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    parser.add_argument(
        "--location-label",
        required=True,
        help="Place label for the report, such as a city or district (no street address)",
    )
    args = parser.parse_args()
    try:
        df = pd.read_csv(args.csv_path)
        paths = []
        if args.period in {"daily", "both"}:
            paths.append(generate_daily_html_report(
                df,
                args.output_dir,
                location_label=args.location_label,
            ))
        if args.period in {"monthly", "both"}:
            paths.append(generate_monthly_html_report(
                df,
                args.output_dir,
                location_label=args.location_label,
            ))
    except (FileNotFoundError, ValueError, pd.errors.EmptyDataError) as exc:
        print(f"HIBA: {exc}")
        return 2
    for path in paths:
        print(f"HTML jelentés mentve -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
