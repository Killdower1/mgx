import sys
from pathlib import Path
import json
from collections import defaultdict
import datetime
import os

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ / "nicegui_template"))

from services import difotoin_api_adapter as api  # noqa: E402

RAW_BY_MONTH_DIR = PROJ / "streamlit_template" / "data" / "api_cache" / "raw_by_month"


def ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def atomic_save_json(obj, path: Path):
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


def merge_period_transactions(period: str, txns: list[dict]) -> tuple[int, int, int]:
    path = RAW_BY_MONTH_DIR / f"{period}.json"
    existing = []
    if path.exists():
        with open(path) as f:
            existing = json.load(f)
    before = len(existing)
    by_id = {str(t.get("id")): t for t in existing if t.get("id")}
    for txn in txns:
        tx_id = str(txn.get("id", ""))
        if tx_id:
            by_id[tx_id] = txn
    merged = list(by_id.values())
    merged.sort(key=lambda t: (str(t.get("date", "")), str(t.get("id", ""))))
    atomic_save_json(merged, path)
    return before, len(merged), len(merged) - before


def dates_to_fetch(days_back=3):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days_back)
    d = start
    out = []
    while d <= today:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def recent_completed_dates(days=3):
    today = datetime.date.today()
    return [(today - datetime.timedelta(days=i)).isoformat() for i in range(days, 0, -1)]


def fetch_recent_days(token, days_back=3):
    by_period = defaultdict(list)
    ok_all = True
    for day in dates_to_fetch(days_back=days_back):
        txns, msg = api.fetch_all_transactions(start_date=day, end_date=day, per_page=100, token=token)
        if "Error" in msg or msg.startswith("HTTP "):
            print("[%s] %s: API ERROR %s" % (ts(), day, msg))
            ok_all = False
            continue
        total = sum(float(t.get("processed_gross_amount", 0) or 0) for t in txns)
        print("[%s] %s: fetched %s txns, revenue=Rp %s" % (ts(), day, len(txns), f"{total:,.0f}"))
        for txn in txns:
            period = str(txn.get("date", day))[:7]
            by_period[period].append(txn)

    changed = []
    for period, txns in sorted(by_period.items()):
        before, after, added = merge_period_transactions(period, txns)
        changed.append(period)
        print("[%s] %s: raw_by_month %s -> %s (%+d)" % (ts(), period, before, after, added))
    return ok_all, changed


def audit_recent_daily(token, days=3, threshold=1000):
    daily_path = PROJ / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"
    dashboard = defaultdict(float)
    if daily_path.exists():
        with open(daily_path) as f:
            for row in json.load(f):
                day = str(row.get("date", ""))[:10]
                if day:
                    dashboard[day] += float(row.get("revenue", 0) or 0)

    ok_all = True
    lines = []
    for day in recent_completed_dates(days=days):
        txns, msg = api.fetch_all_transactions(start_date=day, end_date=day, per_page=100, token=token)
        if "Error" in msg or msg.startswith("HTTP "):
            ok_all = False
            lines.append(f"{day}: API ERROR {msg}")
            continue
        live = sum(float(t.get("processed_gross_amount", 0) or 0) for t in txns)
        dash = dashboard.get(day, 0.0)
        diff = dash - live
        status = "OK" if abs(diff) <= threshold else "MISMATCH"
        ok_all = ok_all and status == "OK"
        lines.append(f"{day}: live=Rp {live:,.0f} dashboard=Rp {dash:,.0f} diff={diff:+,.0f} txns={len(txns)} {status}")
    return ok_all, "\n".join(lines)


print("[%s] Starting OOM-safe daily sales sync..." % ts())

token = api.authenticate()
if not token:
    print("[%s] SYNC FAILED: Gagal autentikasi" % ts())
    sys.exit(1)

fetch_ok, changed_periods = fetch_recent_days(token, days_back=3)

print("[%s] Rebuilding changed caches from raw_by_month (incremental only)..." % ts())
ok_rebuild, msg_rebuild = api.rebuild_all_from_raw_safe(force_all=False, max_files_per_batch=3)
for line in msg_rebuild.split("\n"):
    if line.strip():
        print("[%s]   %s" % (ts(), line))

print("[%s] Auditing recent completed days..." % ts())
ok_audit, audit_msg = audit_recent_daily(token, days=3)
for line in audit_msg.split("\n"):
    if line.strip():
        print("[%s]   %s" % (ts(), line))

if fetch_ok and ok_rebuild and ok_audit:
    print("[%s] SYNC OK" % ts())
    sys.exit(0)

print("[%s] SYNC MISMATCH/FAILED fetch_ok=%s rebuild_ok=%s audit_ok=%s changed=%s" % (ts(), fetch_ok, ok_rebuild, ok_audit, changed_periods))
sys.exit(1)
