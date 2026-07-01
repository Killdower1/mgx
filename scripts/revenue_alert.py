"""
Revenue Alert Engine v3 — cross-references revenue drops with Problem Booth data.
Shows ALL outlets with drops >8%, correlated with recent problems.
"""
import json
import re
from collections import Counter, defaultdict
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

DAYS_LOOKBACK = 14


def clean_html(text):
    """Remove HTML tags and clean up text."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', str(text))
    text = text.replace('&nbsp;', ' ').replace('\n', ' ')
    # Remove remaining HTML-like artifacts
    text = re.sub(r'class\s*=\s*["\'][^"\']*["\']', '', text)
    text = re.sub(r'read-mode', '', text)
    text = re.sub(r'">', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate at first image tag
    img_idx = text.find('img ')
    if img_idx > 0:
        text = text[:img_idx]
    return text[:100]


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


def load_problems():
    try:
        with open(PROBLEM_PATH) as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}, {}
    records = cache.get("records", [])
    lookup = defaultdict(list)
    problem_names = set()
    for r in records:
        for fname in ["nama_tempat", "nama_full"]:
            name = str(r.get(fname, "") or "").strip().lower()
            if name and name not in ("none", "nan", ""):
                problem_names.add(name)
                lookup[name].append(r)
    return lookup, problem_names


def match_outlet(outlet_name, problem_names, lookup):
    key = outlet_name.strip().lower()
    if not key:
        return []
    for pname in problem_names:
        if pname and len(pname) > 3 and pname in key:
            return lookup[pname]
    for pname in problem_names:
        if pname and len(key) > 3 and key in pname:
            return lookup[pname]
    return []


def get_area(outlet, mapping):
    area = mapping.get(outlet, "")
    if area:
        return area
    for known in KNOWN_AREAS:
        if known.lower() in outlet.lower():
            return known
    return "Lainnya"


def analyse(data, mapping, problem_lookup, problem_names):
    # Build area and outlet daily revenue maps
    outlet_rev = defaultdict(lambda: defaultdict(float))  # outlet -> date -> revenue
    area_outlets = defaultdict(set)  # area -> set of outlets

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

    # For each area, aggregate outlet-level drops
    alerts = []
    areas = sorted(area_outlets.keys())

    for area in areas:
        # Area total
        area_recent = sum(outlet_rev[o].get(d, 0) for o in area_outlets[area] for d in last_3)
        area_compare = sum(outlet_rev[o].get(d, 0) for o in area_outlets[area] for d in compare_dates)
        if area_compare <= 0:
            continue
        area_drop = (area_recent - area_compare) / area_compare * 100
        if area_drop >= -8:
            continue

        # Per-outlet: aggregate across 3 days
        outlet_drops = []
        for outl in area_outlets[area]:
            rev_recent = sum(outlet_rev[outl].get(d, 0) for d in last_3)
            rev_compare = sum(outlet_rev[outl].get(d, 0) for d in compare_dates)
            if rev_compare <= 0:
                continue
            o_drop = (rev_recent - rev_compare) / rev_compare * 100
            loss = rev_compare - rev_recent

            # Only include if actually dropping
            if loss <= 0:
                continue

            # Find recent problems
            problems = match_outlet(outl, problem_names, problem_lookup)
            recent_problems = []
            for p in problems:
                pd = str(p.get("tanggal_foto", ""))[:10]
                if pd:
                    try:
                        pdt = datetime.strptime(pd, "%Y-%m-%d")
                        cmp_start = datetime.strptime(compare_dates[0], "%Y-%m-%d")
                        if abs((pdt - cmp_start).days) <= DAYS_LOOKBACK + 7:
                            recent_problems.append({
                                "date": pd,
                                "tipe": p.get("tipeproblem", ""),
                                "desc": clean_html(p.get("description_problem", "")),
                                "status": p.get("status", ""),
                            })
                    except:
                        pass

            recent_problems.sort(key=lambda x: x["date"], reverse=True)
            p_types = Counter(p["tipe"] for p in recent_problems if p["tipe"])

            outlet_drops.append({
                "outlet": outl,
                "drop_pct": round(o_drop, 1),
                "recent": round(rev_recent),
                "compare": round(rev_compare),
                "loss": round(loss),
                "problems": recent_problems[:3],
                "problem_count": len(recent_problems),
                "top_problems": dict(p_types.most_common(3)),
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


def format_alert_text(alerts, recent_dates, compare_dates):
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
    total_compare = 0
    total_problem_outlets = 0
    total_outlets = 0

    for a in alerts:
        icon = "🔴" if a["drop_pct"] < -15 else ("🟡" if a["drop_pct"] < -10 else "🟠")
        total_loss += a["loss"]
        total_compare += a["compare"]

        lines.append(f"{icon} *{a['area']}* — turun {abs(a['drop_pct']):.0f}%")
        lines.append(f"   Rp{a['compare']/1e6:.1f}jt → Rp{a['recent']/1e6:.1f}jt (-Rp{a['loss']:,.0f})")
        lines.append(f"   {len(a['outlets'])} outlet turun:\n")

        for o in a["outlets"][:12]:  # Max 12 outlets per area
            total_outlets += 1
            icon_o = "🔧" if o["problem_count"] > 0 else "📉"
            lines.append(f"   {icon_o} *{o['outlet']}*")
            lines.append(f"      -{abs(o['drop_pct']):.0f}% | -Rp{o['loss']:,.0f}")

            if o["problems"]:
                total_problem_outlets += 1
                p = o["problems"][0]
                lines.append(f"      ⚠️ {p['tipe']} ({_fmt_date(p['date'])})")
                if p["desc"]:
                    lines.append(f"      \"{p['desc'][:50]}\"")
                if o["problem_count"] > 1:
                    extra = o["problem_count"] - 1
                    lines.append(f"      +{extra} masalah lain dalam 2 minggu")
            lines.append("")

        if len(a["outlets"]) > 12:
            lines.append(f"   ...dan {len(a['outlets']) - 12} outlet lainnya.\n")

    # Footer
    lines.append(f"📊 *Total dampak:* Rp{total_loss:,.0f} dari Rp{total_compare:,.0f}")
    lines.append(f"📍 {len(alerts)} area | {total_outlets} outlet")
    if total_problem_outlets > 0:
        pct = total_problem_outlets / total_outlets * 100
        lines.append(f"🔧 {total_problem_outlets}/{total_outlets} outlet terkait problem booth ({pct:.0f}%)")

    return "\n".join(lines)


def format_analysis_data(alerts, recent_dates, compare_dates):
    r_start = _fmt_date(recent_dates[0])
    r_end = _fmt_date(recent_dates[-1])
    c_start = _fmt_date(compare_dates[0])
    c_end = _fmt_date(compare_dates[-1])
    total_outlets = sum(len(a["outlets"]) for a in alerts)
    total_problem = sum(1 for a in alerts for o in a["outlets"] if o["problem_count"] > 0)
    return {
        "type": "revenue_alert",
        "generated_at": datetime.now().isoformat(),
        "period": f"{r_start}-{r_end} vs {c_start}-{c_end}",
        "alerts": alerts,
        "summary": {
            "areas": len(alerts),
            "total_loss": sum(a["loss"] for a in alerts),
            "total_compare": total_compare,
            "outlets_affected": total_outlets,
            "outlets_with_problems": total_problem,
        }
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "text"
    data = load_daily()
    mapping = load_outlet_mapping()
    problem_lookup, problem_names = load_problems()
    alerts, recent_dates, compare_dates = analyse(data, mapping, problem_lookup, problem_names)

    if mode == "json":
        print(json.dumps(format_analysis_data(alerts, recent_dates, compare_dates)))
    else:
        print(format_alert_text(alerts, recent_dates, compare_dates))


if __name__ == "__main__":
    main()
