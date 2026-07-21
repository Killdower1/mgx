#!/usr/bin/env python3
"""Backfill paid/done sales transactions into raw_by_month and rebuild affected caches."""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nicegui_template"))

from services import difotoin_api_adapter as api  # noqa: E402

RAW_BY_MONTH_DIR = ROOT / "streamlit_template" / "data" / "api_cache" / "raw_by_month"


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def day_range(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def atomic_save_json(obj, path: Path) -> None:
    tmp = str(path) + ".tmp." + str(os.getpid())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w") as f:
            json.dump(obj, f, indent=2, default=str)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load_month(period: str) -> list[dict]:
    path = RAW_BY_MONTH_DIR / f"{period}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def merge_month(period: str, new_txns: list[dict], dry_run: bool = False) -> tuple[int, int, int]:
    existing = load_month(period)
    before = len(existing)
    by_id = {str(t.get("id")): t for t in existing if t.get("id")}
    for txn in new_txns:
        tx_id = str(txn.get("id", ""))
        if tx_id:
            by_id[tx_id] = txn
    merged = list(by_id.values())
    merged.sort(key=lambda t: (str(t.get("date", "")), str(t.get("id", ""))))
    after = len(merged)
    added = after - before
    if not dry_run:
        atomic_save_json(merged, RAW_BY_MONTH_DIR / f"{period}.json")
    return before, after, added


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-rebuild", action="store_true")
    args = parser.parse_args()

    start = parse_day(args.start)
    end = parse_day(args.end)
    if end > today:
        end = today
    if end < start:
        print("ERROR: end before start", file=sys.stderr)
        return 2

    token = api.authenticate()
    if not token:
        print("ERROR: API auth failed", file=sys.stderr)
        return 2

    by_period: dict[str, list[dict]] = {}
    print(f"Backfill {start}..{end} dry_run={args.dry_run}")
    for d in day_range(start, end):
        day = d.isoformat()
        txns, msg = api.fetch_all_transactions(start_date=day, end_date=day, per_page=args.per_page, token=token)
        if "Error" in msg or msg.startswith("HTTP "):
            print(f"ERROR {day}: {msg}", file=sys.stderr)
            return 3
        total = sum(float(t.get("processed_gross_amount", 0) or 0) for t in txns)
        print(f"{day}: fetched {len(txns):,} txns, revenue=Rp {total:,.0f}")
        for txn in txns:
            period = str(txn.get("date", day))[:7]
            by_period.setdefault(period, []).append(txn)

    changed_periods = []
    for period, txns in sorted(by_period.items()):
        before, after, added = merge_month(period, txns, dry_run=args.dry_run)
        changed_periods.append(period)
        print(f"{period}: raw_by_month {before:,} -> {after:,} ({added:+,})")

    if args.dry_run or args.skip_rebuild:
        return 0

    if changed_periods:
        ok, msg = api.rebuild_all_from_raw_safe(force_all=False, max_files_per_batch=3)
        print(msg)
        return 0 if ok else 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
