import sys
from pathlib import Path
import json
from collections import defaultdict

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ / "nicegui_template"))

from services import difotoin_api_adapter as api
import datetime

def ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print("[%s] Starting per-period sync..." % ts())

ok, msg = api.sync_current_month(per_page=50)
print("[%s] %s" % (ts(), msg))

missing = api.get_missing_periods()
if missing:
    print("Masih ada %d periode missing. Coba fetch 1: %s" % (len(missing), missing[0]))
    ok2, msg2 = api.fetch_period(missing[0], per_page=50)
    print("[%s] %s" % (ts(), msg2))
else:
    print("Semua periode lengkap!")

print("[%s] Rebuilding dashboard cache..." % ts())
ok3, msg3 = api.build_dashboard_from_raw()
print("[%s] Dashboard: %s" % (ts(), msg3))

# SYNC REPORT
print()
print("=" * 95)
print("SYNC REPORT - Perbandingan Revenue per Periode")
print("=" * 95)

RAW_DIR = Path("/var/www/difotoin-dashboard/streamlit_template/data/api_cache/raw_by_month")
raw_totals = {}
for f in sorted(RAW_DIR.glob("*.json")):
    period = f.stem
    with open(f) as fh:
        txns = json.load(fh)
    total = sum(float(t.get("processed_gross_amount", 0) or 0) for t in txns)
    raw_totals[period] = total

rs = api.load_rs_outlet_summary()
rs_totals = defaultdict(float)
for r in rs:
    rs_totals[r["periode"]] += r["total_revenue"]

dash = api.load_dashboard_summary()
dash_totals = defaultdict(float)
for d in dash:
    dash_totals[d["periode"]] += d["total_revenue"]

all_p = sorted(set(list(raw_totals.keys()) + list(rs_totals.keys()) + list(dash_totals.keys())))

print("%-12s %18s %18s %18s %12s  Status" % ("Periode", "Raw", "RS Cache", "Dashboard", "Selisih"))
print("-" * 95)

grand_raw = 0
grand_rs = 0
grand_dash = 0
all_ok = True

for p in all_p:
    rv = raw_totals.get(p, 0)
    rsv = rs_totals.get(p, 0)
    dv = dash_totals.get(p, 0)
    selisih = dv - rv
    
    grand_raw += rv
    grand_rs += rsv
    grand_dash += dv
    
    status = "OK" if abs(selisih) < 1000 else "SELISIH!"
    if status == "SELISIH!":
        all_ok = False
    
    print("%-12s Rp %14.0f Rp %14.0f Rp %14.0f %+10.0f  %s" % (p, rv, rsv, dv, selisih, status))

print("-" * 95)
total_selisih = grand_raw - grand_dash
print("%-12s Rp %14.0f Rp %14.0f Rp %14.0f %+10.0f  %s" % (
    "TOTAL", grand_raw, grand_rs, grand_dash, total_selisih,
    "OK" if abs(total_selisih) < 1000 else "SELISIH!"))

print()
print("[%s] Sync selesai. Status: %s" % (ts(), "SEMUA OK" if all_ok else "ADA SELISIH - cek log"))

sys.exit(0)
