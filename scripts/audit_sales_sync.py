#!/usr/bin/env python3
"""Audit live Difotoin API sales against dashboard daily cache."""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nicegui_template"))

from services import difotoin_api_adapter as api  # noqa: E402

DAILY_SUMMARY_PATH = ROOT / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def day_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_dashboard_totals() -> dict[str, float]:
    totals: dict[str, float] = {}
    if not DAILY_SUMMARY_PATH.exists():
        return totals
    with open(DAILY_SUMMARY_PATH) as f:
        rows = json.load(f)
    for row in rows:
        day = str(row.get("date", ""))[:10]
        if not day:
            continue
        totals[day] = totals.get(day, 0.0) + float(row.get("revenue", 0) or 0)
    return totals


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=(today - timedelta(days=7)).isoformat())
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--threshold", type=float, default=1000.0)
    parser.add_argument("--exclude-today", action="store_true", help="Skip current partial day")
    args = parser.parse_args()

    start = parse_day(args.start)
    end = parse_day(args.end)
    if args.exclude_today and end >= today:
        end = today - timedelta(days=1)
    if end < start:
        print("No completed dates to audit")
        return 0

    token = api.authenticate()
    if not token:
        print("ERROR: API auth failed", file=sys.stderr)
        return 2

    dashboard = load_dashboard_totals()
    failed = False
    print(f"{'Date':<12} {'Live API':>16} {'Dashboard':>16} {'Diff':>16} {'Txns':>8} Status")
    print("-" * 82)
    for d in day_range(start, end):
        day = d.isoformat()
        txns, msg = api.fetch_all_transactions(start_date=day, end_date=day, per_page=100, token=token)
        if "Error" in msg or msg.startswith("HTTP "):
            print(f"{day:<12} ERROR {msg}")
            failed = True
            continue
        live = sum(float(t.get("processed_gross_amount", 0) or 0) for t in txns)
        dash = dashboard.get(day, 0.0)
        diff = dash - live
        ok = abs(diff) <= args.threshold
        failed = failed or not ok
        status = "OK" if ok else "MISMATCH"
        print(f"{day:<12} Rp {live:12,.0f} Rp {dash:12,.0f} {diff:+16,.0f} {len(txns):8d} {status}")
    print("-" * 82)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
