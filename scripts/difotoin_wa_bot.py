#!/usr/bin/env python3
"""
Difotoin WA Chatbot Handler
Usage: python3 difotoin_wa_bot.py <intent> [date/period]
Intents: penjualan, problem_booth, absen, trend
"""
import sys
import json
import os
from datetime import datetime

BASE = "/var/www/difotoin-dashboard"
DAILY_PATH = os.path.join(BASE, "streamlit_template/data/api_cache/daily_summary.json")
PROBLEM_PATH = os.path.join(BASE, "problem_booth_cache_light.json")
KPI_PATH = os.path.join(BASE, "nicegui_template/data/kpi_sistem_cache.json")

def load_daily():
    with open(DAILY_PATH) as f:
        return json.load(f)

def load_problems():
    try:
        with open(PROBLEM_PATH) as f:
            return json.load(f)
    except:
        return {}

def load_kpi():
    try:
        with open(KPI_PATH) as f:
            return json.load(f)
    except:
        return {}

def fmt_rp(n):
    return "Rp {:,.0f}".format(n).replace(",", ".")

def penjualan(date_str=None):
    data = load_daily()
    if not date_str:
        date_str = sorted(set(r["date"][:10] for r in data))[-1]
    
    day_data = [r for r in data if r["date"][:10] == date_str]
    total_rev = sum(r["revenue"] for r in day_data)
    total_sessions = sum(r["sessions"] for r in day_data)
    outlets = len(day_data)
    nonzero = [r for r in day_data if r["revenue"] > 0]
    
    lines = [
        "---",
        "",
        "Penjualan %s" % date_str,
        "",
        "Total: %s" % fmt_rp(total_rev),
        "Foto: %s" % "{:,}".format(total_sessions),
        "Outlet aktif: %d/%d" % (len(nonzero), outlets),
        "Rata-rata/outlet: %s" % fmt_rp(total_rev/outlets if outlets else 0),
        "",
        "Top 5 Outlet:",
    ]
    
    sorted_outlets = sorted(day_data, key=lambda x: x["revenue"], reverse=True)[:5]
    for i, r in enumerate(sorted_outlets, 1):
        lines.append("%d. %s: %s" % (i, r['outlet_name'], fmt_rp(r['revenue'])))
    
    return "\n".join(lines)

def problem_booth():
    cache = load_problems()
    records = cache.get("records", [])
    open_problems = [r for r in records if r.get("status") in ("Open", "Blm Selesai")]
    
    from collections import defaultdict
    by_area = defaultdict(list)
    for r in open_problems:
        area = r.get("area", "Lainnya") or "Lainnya"
        by_area[area].append(r)
    
    lines = [
        "---",
        "",
        "Problem Booth - Belum Selesai (%d)" % len(open_problems),
        "",
    ]
    
    for area in sorted(by_area.keys()):
        probs = by_area[area]
        lines.append("%s (%d)" % (area, len(probs)))
        for r in probs[:5]:
            outlet = r.get("outlet_name") or r.get("subject") or r.get("name", "Unknown")
            problem = r.get("type", "Unknown")
            lines.append("  - %s: %s" % (outlet, problem))
        if len(probs) > 5:
            lines.append("  ...dan %d lainnya" % (len(probs)-5))
        lines.append("")
    
    return "\n".join(lines)

def absen():
    kpi = load_kpi()
    if not kpi:
        return "Data absensi belum tersedia."
    
    staff = kpi.get("staff", [])
    today = datetime.now().strftime("%Y-%m-%d")
    
    lines = [
        "---",
        "",
        "Absensi Staff - %s" % today,
        "",
        "Total staff: %d" % len(staff),
        "",
    ]
    
    for s in staff[:10]:
        name = s.get("name", "Unknown")
        email = s.get("email", "")
        lines.append("- %s (%s)" % (name, email))
    
    return "\n".join(lines)

def trend(days=7):
    data = load_daily()
    from collections import defaultdict
    daily_rev = defaultdict(float)
    for r in data:
        daily_rev[r["date"][:10]] += r["revenue"]
    
    dates = sorted(daily_rev.keys())[-days:]
    lines = ["---", "", "Trend %d Hari Terakhir" % days, ""]
    for d in dates:
        rev = daily_rev[d]
        lines.append("%s: %s" % (d, fmt_rp(rev)))
    
    if len(dates) >= 2:
        prev = daily_rev[dates[-2]]
        curr = daily_rev[dates[-1]]
        if prev > 0:
            pct = ((curr - prev) / prev) * 100
            lines.append("")
            lines.append("vs kemarin: %+.1f%%" % pct)
    
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 difotoin_wa_bot.py <penjualan|problem_booth|absen|trend> [date/days]")
        sys.exit(1)
    
    intent = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    if intent == "penjualan":
        print(penjualan(arg))
    elif intent == "problem_booth":
        print(problem_booth())
    elif intent == "absen":
        print(absen())
    elif intent == "trend":
        print(trend(int(arg) if arg else 7))
    else:
        print("Intent tidak dikenal: %s" % intent)
        print("Tersedia: penjualan, problem_booth, absen, trend")

if __name__ == "__main__":
    main()
