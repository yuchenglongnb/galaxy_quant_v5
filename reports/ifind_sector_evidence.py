"""Normalize iFinD MCP sector evidence without creating candidate validation rows."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from analyzers.context.prior_day_outcome_features import PriorDayOutcomeFeatureBuilder


PROVIDER_KEY = "ifind_mcp"


def build_sector_record(
    sector_name,
    date_start,
    date_end,
    period_return_pct=None,
    daily_amount=None,
    source_tool="mcp__hexin_ifind_ds_index_mcp__sector_data",
    field_coverage=None,
    notes=None,
):
    daily_amount = daily_amount or {}
    ordered = sorted((str(key), value) for key, value in daily_amount.items())
    amount_start = _number(ordered[0][1]) if ordered else None
    amount_end = _number(ordered[-1][1]) if ordered else None
    amount_change = None
    if amount_start not in (None, 0) and amount_end is not None:
        amount_change = round((amount_end / amount_start - 1.0) * 100.0, 4)
    classification = PriorDayOutcomeFeatureBuilder.classify_price_turnover(
        period_return_pct, amount_change
    )
    return {
        "date_start": str(date_start),
        "date_end": str(date_end),
        "sector_name": str(sector_name),
        "period_return_pct": _number(period_return_pct),
        "daily_amount": {key: _number(value) for key, value in ordered},
        "amount_start": amount_start,
        "amount_end": amount_end,
        "amount_change_pct": amount_change,
        "price_turnover_confirmation": classification,
        "provider": PROVIDER_KEY,
        "validation_level": "sector_only",
        "source_tool": source_tool,
        "field_coverage": field_coverage or [],
        "data_quality": "usable_sector_only" if classification != "insufficient_sector_evidence" else "partial",
        "notes": notes or [],
    }


def write_evidence(records, output_root):
    root = Path(output_root)
    if "reports" not in root.parts or "validation" in root.parts:
        raise ValueError("iFinD sector evidence must remain under reports and outside candidate validation")
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "sector_evidence.json"
    csv_path = root / "sector_evidence.csv"
    payload = {
        "provider": PROVIDER_KEY,
        "validation_level": "sector_only",
        "candidate_level_data": False,
        "records": records,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = [
        "date_start", "date_end", "sector_name", "period_return_pct", "amount_start",
        "amount_end", "amount_change_pct", "price_turnover_confirmation", "provider",
        "validation_level", "source_tool", "data_quality",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({key: row.get(key) for key in fields})
    return json_path, csv_path


def _number(value):
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
