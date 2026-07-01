"""
Revenue Alert Engine — analyse daily transaction data for drops >10%.
Outputs WhatsApp-ready alert messages.

For each area: compare last 3 days vs same weekdays in previous week.
If drop >8%: generate alert with top offender outlets.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta
import sys
import os

# ── Paths ──
BASE = "/var/www/difotoin-dashboard"
DAILY_PATH = os.path.join(BASE, "streamlit_template/data/api_cache/daily_summary.json")
MAPPING_PATH = os.path.join(BASE, "streamlit_template/data/difotoin_outlet_mapping.csv")

# ── Known areas for fallback matching ──
KNOWN_AREAS = ["Jakarta", "Bali", "Jogja", "Bogor", "Bekasi",
               "Tangerang", "Samarinda", "Semarang", "Bandung",
               "Karanganyar", "Makassar", "Depok", "Malang", "Cilegon"]


def load_outlet_mapping():
    import csv
    mapping = {}
    with open(MAPPING_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("outlet_name", "").strip()
            area = row.get("area", "").strip()
            if name and area:
                mapping[name] = area
    return mapping


def load_daily():
    with open(DAILY_PATH) as f:
        return json.load(f)


def get_area(outlet, mapping):
    """Get area for an outlet, with fallback guessing."""
    area = mapping.get(outlet, "")
    if area:
        return area
    for known in KNOWN_AREAS:
        if known.lower() in outlet.lower():
            return known
    return "Lainnya"


def analyse(data, mapping):
    area_daily = defaultdict(float)  # (area, date) -> revenue
    outlet_daily = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    for r in data:
        d = r.get("date", "")[:10]
        if not d:
            continue
        outlet = r.get("outlet_name", "").strip()
        rev = float(r.get("total_revenue", 0))
        area = get_area(outlet, mapping)
        area_daily[(area, d)] += rev
        outlet_daily[area][d][outlet] += rev

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today.strftime("%Y-%m-%d")

    all_dates = sorted(set(d for (_, d) in area_daily.keys()))
    available = [d for d in all_dates if d <= today_str]

    if len(available) < 7:
        return ["Data harian belum cukup (min 7 hari)."]

    last_3 = available[-3:]
    compare_dates = []
    for d in last_3:
        dt = datetime.strptime(d, "%Y-%m-%d")
        compare_dates.append((dt - timedelta(days=7)).strftime("%Y-%m-%d"))

    alerts = []
    areas = sorted(set(a for (a, _) in area_daily.keys() - {("Lainnya", "")}) - {"Lainnya"})

    for area in areas:
        rev_recent = sum(area_daily.get((area, d), 0) for d in last_3)
        rev_compare = sum(area_daily.get((area, d), 0) for d in compare_dates)

        if rev_compare <= 0:
            continue

        drop_pct = (rev_recent - rev_compare) / rev_compare * 100

        if drop_pct < -8:
            # Find top offender outlets
            outlet_drops = []
            for d in last_3:
                dt = datetime.strptime(d, "%Y-%m-%d")
                prev_d = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
                day_data = outlet_daily[area].get(d, {})
                for outl, rev_d in day_data.items():
                    prev_rev = outlet_daily[area].get(prev_d, {}).get(outl, 0)
                    if prev_rev > 0:
                        o_drop = (rev_d - prev_rev) / prev_rev * 100
                        outlet_drops.append((outl, o_drop, rev_d, prev_rev))

            outlet_drops.sort(key=lambda x: (x[3] - x[2]), reverse=True)
            top = outlet_drops[:3]

            offenders = []
            for outl, o_drop, rev_d, prev_rev in top:
                loss = prev_rev - rev_d
                offenders.append(f"{outl} ( -{abs(o_drop):.0f}% | -Rp{loss:,.0f} )")

            rev_compare / 1_000_000
            rev_recent / 1_000_000

            alerts.append({
                "type": "revenue_drop",
                "area": area,
                "drop_pct": round(drop_pct, 1),
                "recent": rev_recent,
                "compare": rev_compare,
                "loss": rev_compare - rev_recent,
                "offenders": offenders,
                "severity": "SEVERE" if drop_pct < -15 else ("WARNING" if drop_pct < -10 else "MILD"),
            })

    alerts.sort(key=lambda x: x["drop_pct"])
    return alerts


def format_message(alerts, is_test=False):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    header = "🧪 *TEST Revenue Alert*" if is_test else "🚨 *Revenue Alert*"
    
    if not alerts:
        msg = f"{header} — {now}\n\n✅ Tidak ada penurunan signifikan dalam 3 hari terakhir. Semua area normal."
        return msg
    
    lines = [f"{header} — {now}\n"]
    
    for a in alerts[:5]:
        icon = "🔴" if a["severity"] == "SEVERE" else ("🟡" if a["severity"] == "WARNING" else "🟠")
        area = a["area"]
        drop = abs(a["drop_pct"])
        rev_recent_m = a["recent"] / 1_000_000
        rev_compare_m = a["compare"] / 1_000_000
        
        lines.append(f"{icon} *{area}* — revenue turun {drop:.0f}%")
        lines.append(f"   Rp{rev_compare_m:.1f}jt → Rp{rev_recent_m:.1f}jt")
        
        if a["offenders"]:
            lines.append("   Penurunan terbesar:")
            for o in a["offenders"]:
                lines.append(f"   • {o}")
        lines.append("")
    
    if len(alerts) > 5:
        lines.append(f"...dan {len(alerts) - 5} area lainnya.\n")
    
    total_loss = sum(a["loss"] for a in alerts)
    total_compare = sum(a["compare"] for a in alerts)
    lines.append(f"📊 Total dampak: Rp{total_loss:,.0f} dari Rp{total_compare:,.0f}")

    return "\n".join(lines)


def main():
    data = load_daily()
    mapping = load_outlet_mapping()
    alerts = analyse(data, mapping)
    
    is_test = "--test" in sys.argv
    msg = format_message(alerts, is_test)
    print(msg)
    return msg


if __name__ == "__main__":
    main()
