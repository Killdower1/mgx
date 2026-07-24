"""
Revenue Alert Engine v4 — clean, no Problem Booth mixing.
Problem Booth summary sent as separate message.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta
import sys
import os

BASE = "/var/www/difotoin-dashboard"
DAILY_PATH = os.path.join(BASE, "streamlit_template/data/api_cache/daily_summary.json")
MAPPING_PATH = os.path.join(BASE, "streamlit_template/data/difotoin_outlet_mapping.csv")
PROBLEM_PATH = os.path.join(BASE, "problem_booth_cache_light.json")

KNOWN_AREAS = ["Jakarta", "Bali", "Jogja", "Bogor", "Bekasi",
               "Tangerang", "Samarinda", "Semarang", "Bandung",
               "Karanganyar", "Makassar", "Depok", "Malang", "Cilegon"]

_OUTLET_MAP = {}


def load_outlet_mapping():
    import csv
    mapping = {}
    with open(MAPPING_PATH) as f:
        for row in csv.DictReader(f):
            name = row.get("outlet_name", "").strip()
            area = row.get("area", "").strip()
            if name and area:
                mapping[name] = area
    return mapping


def load_daily():
    with open(DAILY_PATH) as f:
        data = json.load(f)
    # Backward compat: map old column names to new
    for r in data:
        if "revenue" not in r and "total_revenue" in r:
            r["revenue"] = r["total_revenue"]
        if "total_revenue" not in r and "revenue" in r:
            r["total_revenue"] = r["revenue"]
        for col in ["sessions", "unlocks", "unlocks_paid", "prints", "conversion_rate", "print_rate"]:
            if col not in r:
                r[col] = 0
    return data


def load_problems():
    """Load problem booth data for open problems summary."""
    try:
        with open(PROBLEM_PATH) as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return cache.get("records", [])


def get_area(outlet, mapping):
    area = mapping.get(outlet, "")
    if area:
        return area
    for known in KNOWN_AREAS:
        if known.lower() in outlet.lower():
            return known
    return "Lainnya"


def analyse(data, mapping):
    outlet_rev = defaultdict(lambda: defaultdict(float))
    area_outlets = defaultdict(set)

    for r in data:
        d = r.get("date", "")[:10]
        if not d:
            continue
        outlet = r.get("outlet_name", "").strip()
        rev = float(r.get("total_revenue", 0))
        area = get_area(outlet, mapping)
        outlet_rev[outlet][d] += rev
        area_outlets[area].add(outlet)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today.strftime("%Y-%m-%d")
    all_dates = sorted(set(d for o in outlet_rev.values() for d in o.keys()))
    available = [d for d in all_dates if d <= today_str]

    if len(available) < 7:
        return [], [], []

    last_3 = available[-3:]
    compare_dates = []
    for d in last_3:
        dt = datetime.strptime(d, "%Y-%m-%d")
        compare_dates.append((dt - timedelta(days=7)).strftime("%Y-%m-%d"))

    alerts = []
    for area in sorted(area_outlets.keys()):
        area_recent = sum(outlet_rev[o].get(d, 0) for o in area_outlets[area] for d in last_3)
        area_compare = sum(outlet_rev[o].get(d, 0) for o in area_outlets[area] for d in compare_dates)
        if area_compare <= 0:
            continue
        area_drop = (area_recent - area_compare) / area_compare * 100
        if area_drop >= -8:
            continue

        outlet_drops = []
        for outl in area_outlets[area]:
            rev_recent = sum(outlet_rev[outl].get(d, 0) for d in last_3)
            rev_compare = sum(outlet_rev[outl].get(d, 0) for d in compare_dates)
            if rev_compare <= 0:
                continue
            o_drop = (rev_recent - rev_compare) / rev_compare * 100
            loss = rev_compare - rev_recent
            if loss > 0:
                outlet_drops.append({
                    "outlet": outl,
                    "drop_pct": round(o_drop, 1),
                    "loss": round(loss),
                    "recent": round(rev_recent),
                    "compare": round(rev_compare),
                })

        outlet_drops.sort(key=lambda x: x["loss"], reverse=True)
        alerts.append({
            "area": area,
            "drop_pct": round(area_drop, 1),
            "recent": round(area_recent),
            "compare": round(area_compare),
            "loss": round(area_compare - area_recent),
            "recent_dates": last_3,
            "compare_dates": compare_dates,
            "outlets": outlet_drops,
        })

    alerts.sort(key=lambda x: x["drop_pct"])
    return alerts, last_3, compare_dates


def _fmt_date(d):
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return f"{dt.day} {months[dt.month]}"
    except:
        return d


def format_revenue_alert(alerts, recent_dates, compare_dates, daily_data):
    """WhatsApp message: revenue alert only — no problem booth."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    r_start = _fmt_date(recent_dates[0])
    r_end = _fmt_date(recent_dates[-1])
    c_start = _fmt_date(compare_dates[0])
    c_end = _fmt_date(compare_dates[-1])

    if not alerts:
        return (f"✅ *Revenue Check* — {now}\n"
                f"📅 {r_start}-{r_end} vs {c_start}-{c_end}\n"
                f"Semua normal. Tidak ada penurunan.")

    lines = [f"🚨 *Revenue Alert* — {now}\n"
             f"📅 {r_start}-{r_end} vs {c_start}-{c_end}\n"]

    total_loss = 0
    for a in alerts:
        icon = "🔴" if a["drop_pct"] < -15 else ("🟡" if a["drop_pct"] < -10 else "🟠")
        total_loss += a["loss"]
        lines.append(f"{icon} *{a['area']}* — turun {abs(a['drop_pct']):.0f}%  (-Rp{a['loss']:,.0f})")
        lines.append(f"   Rp{a['compare']/1e6:.1f}jt → Rp{a['recent']/1e6:.1f}jt")

        for o in a["outlets"][:10]:
            lines.append(f"   📉 {o['outlet']}: -{abs(o['drop_pct']):.0f}% (-Rp{o['loss']:,.0f})")
        lines.append("")

    total_compare = sum(a["compare"] for a in alerts)
    total_outlets = sum(len(a["outlets"]) for a in alerts)
    lines.append(f"📊 *Total:* Rp{total_loss:,.0f} dari Rp{total_compare:,.0f}")
    lines.append(f"📍 {len(alerts)} area | {total_outlets} outlet terdampak")


    # Funnel summary
    recent_sessions = sum(r.get("sessions", 0) for r in daily_data if r.get("date", "") in recent_dates)
    recent_unlocks = sum(r.get("unlocks", 0) for r in daily_data if r.get("date", "") in recent_dates)
    recent_prints = sum(r.get("prints", 0) for r in daily_data if r.get("date", "") in recent_dates)
    
    conv_rate = (recent_unlocks / recent_sessions * 100) if recent_sessions > 0 else 0
    print_rate = (recent_prints / recent_unlocks * 100) if recent_unlocks > 0 else 0
    
    lines.append("")
    lines.append("📊 *Funnel Summary (Last 3 Days)*")
    lines.append(f"   📸 Sessions: {recent_sessions:,}")
    lines.append(f"   🔓 Unlocks: {recent_unlocks:,} ({conv_rate:.1f}%)")
    lines.append(f"   🖨️ Prints: {recent_prints:,} ({print_rate:.1f}%)")
    return "\n".join(lines)


def format_problem_summary(records):
    """WhatsApp message: open problem booth summary in table format."""
    global _OUTLET_MAP
    try:
        with open(os.path.join(BASE, "booth_to_outlet.json")) as f:
            _OUTLET_MAP = json.load(f)
    except:
        _OUTLET_MAP = {}
    open_statuses = {"open", "on the way", "reopen", "", "uncompleted"}
    open_problems = [r for r in records if str(r.get("status", "")).strip().lower() in open_statuses]

    if not open_problems:
        return "✅ *Problem Booth*\nTidak ada problem open saat ini."

    # Sort by date (newest first)
    open_problems.sort(key=lambda r: str(r.get("tanggal_foto", ""))[:19], reverse=True)

    lines = ["🔧 *Problem Booth — Belum Selesai ({})*\n".format(len(open_problems))]

    # Group by branch/area
    by_area = defaultdict(list)
    for r in open_problems:
        branch = str(r.get("branch", "") or "-").strip()
        by_area[branch].append(r)

    for area in sorted(by_area.keys(), key=lambda a: -len(by_area[a])):
        probs = by_area[area]
        lines.append(f"\n📍 *{area}* ({len(probs)})")
        lines.append("```")
        lines.append(f"{'Outlet':<22} {'Problem':<18} {'Status':<12} Tgl")
        lines.append("-" * 64)
        for r in probs[:8]:
            name = str(r.get("nama_tempat", "") or "?")[:21]
            # Use mapped outlet name if available
            mapped = _OUTLET_MAP.get(name, "")
            if mapped:
                display = mapped[:21]
            else:
                display = name
            tipe = str(r.get("tipeproblem", "") or "-")[:17]
            raw_status = str(r.get("status", "") or "-").strip().lower()
            if raw_status in ("open", "on the way", "reopen"):
                status = "Open"
            else:
                status = "Blm Selesai"
            tgl = str(r.get("tanggal_foto", ""))[:10]
            lines.append(f"{display:<22} {tipe:<18} {status:<12} {tgl}")
        if len(probs) > 8:
            lines.append(f"...dan {len(probs)-8} lainnya")
        lines.append("```")

    return "\n".join(lines)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "revenue"

    data = load_daily()
    mapping = load_outlet_mapping()

    if mode == "problems":
        records = load_problems()
        print(format_problem_summary(records))
    else:
        alerts, recent_dates, compare_dates = analyse(data, mapping)
        print(format_revenue_alert(alerts, recent_dates, compare_dates, data))


if __name__ == "__main__":
    main()
