"""
Revenue Alert Engine v2 — generates structured data for AI analysis.
Outputs:
- WhatsApp-style alert with specific dates
- Structured JSON data for AI model to analyze
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

KNOWN_AREAS = ["Jakarta", "Bali", "Jogja", "Bogor", "Bekasi",
               "Tangerang", "Samarinda", "Semarang", "Bandung",
               "Karanganyar", "Makassar", "Depok", "Malang", "Cilegon"]


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
        return json.load(f)


def get_area(outlet, mapping):
    area = mapping.get(outlet, "")
    if area:
        return area
    for known in KNOWN_AREAS:
        if known.lower() in outlet.lower():
            return known
    return "Lainnya"


def analyse(data, mapping):
    area_daily = defaultdict(float)
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
        return []

    last_3 = available[-3:]
    compare_dates = []
    for d in last_3:
        dt = datetime.strptime(d, "%Y-%m-%d")
        compare_dates.append((dt - timedelta(days=7)).strftime("%Y-%m-%d"))

    alerts = []
    areas = sorted(set(a for (a, _) in area_daily.keys()) - {"Lainnya"})

    for area in areas:
        rev_recent = sum(area_daily.get((area, d), 0) for d in last_3)
        rev_compare = sum(area_daily.get((area, d), 0) for d in compare_dates)

        if rev_compare <= 0:
            continue

        drop_pct = (rev_recent - rev_compare) / rev_compare * 100

        if drop_pct < -8:
            outlet_drops = []
            for d in last_3:
                dt = datetime.strptime(d, "%Y-%m-%d")
                prev_d = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
                day_data = outlet_daily[area].get(d, {})
                for outl, rev_d in day_data.items():
                    prev_rev = outlet_daily[area].get(prev_d, {}).get(outl, 0)
                    if prev_rev > 0:
                        o_drop = (rev_d - prev_rev) / prev_rev * 100
                        outlet_drops.append({
                            "outlet": outl,
                            "drop_pct": round(o_drop, 1),
                            "recent": round(rev_d),
                            "compare": round(prev_rev),
                            "loss": round(prev_rev - rev_d),
                        })

            outlet_drops.sort(key=lambda x: x["loss"], reverse=True)

            alerts.append({
                "area": area,
                "drop_pct": round(drop_pct, 1),
                "recent": round(rev_recent),
                "compare": round(rev_compare),
                "loss": round(rev_compare - rev_recent),
                "recent_dates": last_3,
                "compare_dates": compare_dates,
                "offenders": outlet_drops[:3],
            })

    alerts.sort(key=lambda x: x["drop_pct"])
    return alerts, available[-3:], compare_dates


def _fmt_date(d):
    """2026-06-25 → 25 Jun"""
    months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return f"{dt.day} {months[dt.month]}"
    except:
        return d


def format_alert_text(alerts, recent_dates, compare_dates):
    """WhatsApp-ready alert text."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    r_start = _fmt_date(recent_dates[0])
    r_end = _fmt_date(recent_dates[-1])
    c_start = _fmt_date(compare_dates[0])
    c_end = _fmt_date(compare_dates[-1])

    if not alerts:
        return (
            f"✅ *Revenue Check* — {now}\n\n"
            f"Tidak ada penurunan signifikan.\n"
            f"Periode: {r_start} - {r_end} vs {c_start} - {c_end}\n"
            f"Semua area dalam batas normal."
        )

    lines = [f"🚨 *Revenue Alert* — {now}"]
    lines.append(f"📅 Periode: *{r_start} - {r_end}* vs *{c_start} - {c_end}*\n")

    for a in alerts[:5]:
        icon = "🔴" if a["drop_pct"] < -15 else ("🟡" if a["drop_pct"] < -10 else "🟠")
        area = a["area"]
        drop = abs(a["drop_pct"])
        rev_recent_m = a["recent"] / 1_000_000
        rev_compare_m = a["compare"] / 1_000_000

        lines.append(f"{icon} *{area}* — revenue turun {drop:.0f}%")
        lines.append(f"   Rp{rev_compare_m:.1f}jt → Rp{rev_recent_m:.1f}jt (-Rp{a['loss']:,.0f})")

        if a["offenders"]:
            lines.append("   🎯 Penurunan terbesar:")
            for o in a["offenders"]:
                lines.append(f"   • {o['outlet']}")
                lines.append(f"     -{abs(o['drop_pct']):.0f}% | -Rp{o['loss']:,.0f}")
        lines.append("")

    if len(alerts) > 5:
        lines.append(f"...dan {len(alerts) - 5} area lainnya.\n")

    total_loss = sum(a["loss"] for a in alerts)
    total_compare = sum(a["compare"] for a in alerts)
    lines.append(f"📊 *Total dampak:* Rp{total_loss:,.0f} dari Rp{total_compare:,.0f}")

    return "\n".join(lines)


def format_analysis_data(alerts, recent_dates, compare_dates):
    """Structured data for AI analysis."""
    r_start = _fmt_date(recent_dates[0])
    r_end = _fmt_date(recent_dates[-1])
    c_start = _fmt_date(compare_dates[0])
    c_end = _fmt_date(compare_dates[-1])

    return {
        "type": "revenue_alert",
        "generated_at": datetime.now().isoformat(),
        "period_recent": {"start": recent_dates[0], "end": recent_dates[-1], "label": f"{r_start} - {r_end}"},
        "period_compare": {"start": compare_dates[0], "end": compare_dates[-1], "label": f"{c_start} - {c_end}"},
        "alerts": alerts,
        "summary": {
            "total_areas_dropping": len(alerts),
            "total_loss": sum(a["loss"] for a in alerts),
            "total_compare_revenue": sum(a["compare"] for a in alerts),
        }
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "text"

    data = load_daily()
    mapping = load_outlet_mapping()
    alerts, recent_dates, compare_dates = analyse(data, mapping)

    if mode == "json":
        # Structured data for AI
        result = format_analysis_data(alerts, recent_dates, compare_dates)
        print(json.dumps(result))
    else:
        # Human-readable WhatsApp text
        msg = format_alert_text(alerts, recent_dates, compare_dates)
        print(msg)


if __name__ == "__main__":
    main()
