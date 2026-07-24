#!/usr/bin/env python3
"""
Difotoin Health Check
Alerts if revenue is 0 for ALL outlets for >1 day
"""
import json
import os
import sys
from datetime import datetime

BASE = "/var/www/difotoin-dashboard"
DAILY_PATH = os.path.join(BASE, "streamlit_template/data/api_cache/daily_summary.json")
LOG_PATH = os.path.join(BASE, ".health_check_log")

def load_daily():
    with open(DAILY_PATH) as f:
        return json.load(f)

def fmt_rp(n):
    return "Rp {:,.0f}".format(n).replace(",", ".")

def check():
    data = load_daily()
    from collections import defaultdict
    daily_rev = defaultdict(float)
    daily_outlets = defaultdict(set)
    
    for r in data:
        d = r["date"][:10]
        daily_rev[d] += r["revenue"]
        daily_outlets[d].add(r["outlet_name"])
    
    dates = sorted(daily_rev.keys())
    if len(dates) < 2:
        print("Data kurang dari 2 hari. Skip.")
        return 0
    
    latest = dates[-1]
    prev = dates[-2]
    
    latest_rev = daily_rev[latest]
    prev_rev = daily_rev[prev]
    latest_outlets = len(daily_outlets[latest])
    
    alerts = []
    
    # Alert 1: Revenue 0 for all outlets
    if latest_rev == 0 and latest_outlets > 0:
        alerts.append("ALERT: Revenue 0 untuk semua %d outlet pada %s!" % (latest_outlets, latest))
    
    # Alert 2: Revenue drop >50%
    if prev_rev > 0:
        pct = ((latest_rev - prev_rev) / prev_rev) * 100
        if pct < -50:
            alerts.append("ALERT: Revenue drop %.1f%%! %s: %s -> %s: %s" % (
                pct, prev, fmt_rp(prev_rev), latest, fmt_rp(latest_rev)))
    
    # Log
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    "%s | %s | Rev=%s | Outlets=%d" % (now, latest, fmt_rp(latest_rev), latest_outlets)
    
    if alerts:
        for a in alerts:
            print(a)
        return 1
    else:
        print("OK: %s | Rev=%s | Outlets=%d" % (latest, fmt_rp(latest_rev), latest_outlets))
        return 0

if __name__ == "__main__":
    sys.exit(check())
