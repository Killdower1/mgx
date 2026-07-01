"""
Sync Problem Booth data from ERPNext.
Fetches all records, then regenerates:
- problem_booth_cache_light.json (7MB)
- problem_booth_summary.json (4KB)
- problem_booth_monthly.json (42KB)
"""
import json
import sys
import os
from collections import Counter
from datetime import datetime

import requests

# ── Config ──
CONFIG_PATH = "/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json"
LIGHT_CACHE = "/var/www/difotoin-dashboard/problem_booth_cache_light.json"
SUMMARY_PATH = "/var/www/difotoin-dashboard/problem_booth_summary.json"
MONTHLY_PATH = "/var/www/difotoin-dashboard/problem_booth_monthly.json"

# Working fields for Problem Booth
WORKING_FIELDS = ["name", "nama_tempat", "nama_full", "branch", "tipeproblem",
                  "description_problem", "status", "maintenance", "pbsolving",
                  "pemilik", "visit", "device_error", "tanggal_foto",
                  "creation", "modified", "password_krisbow_2", "owner", "modified_by"]


def main():
    # Load ERPNext config
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    url = cfg["url"]
    headers = {"Authorization": f"token {cfg['api_key']}:{cfg['api_secret']}"}

    print(f"🔧 Fetching Problem Booth from {url}...")

    # Fetch all records with pagination
    all_data = []
    limit_start = 0
    while True:
        try:
            with requests.get(f"{url}/api/resource/Problem%20Booth", headers=headers,
                params={"limit_page_length": 200, "limit_start": limit_start,
                        "fields": json.dumps(WORKING_FIELDS)},
                stream=True, timeout=120) as r:
                if r.status_code != 200:
                    print(f"  Error at {limit_start}: {r.status_code}")
                    break
                data = r.json().get("data", [])
                if not data:
                    break
                all_data.extend(data)
                limit_start += 200
                if limit_start % 2000 == 0:
                    print(f"  {limit_start} records...")
                if len(data) < 200:
                    break
        except Exception as e:
            print(f"  Error at {limit_start}: {e}")
            break

    total = len(all_data)
    print(f"✅ Fetched {total} records")

    if total == 0:
        print("❌ No data fetched, aborting.")
        sys.exit(1)

    now = datetime.now().isoformat()

    # ── 1. Lightweight cache (7MB) ──
    light_records = []
    for r in all_data:
        lr = {f: r.get(f) for f in WORKING_FIELDS if f in r}
        desc = str(r.get("description_problem", ""))
        desc_clean = desc.replace("<p>", " ").replace("</p>", " ").replace("<br>", " ").replace("<div", " ").replace("</div>", " ")
        lr["description_problem"] = desc_clean[:150] if desc_clean else ""
        light_records.append(lr)

    light_cache = {"last_sync": now, "total_records": total, "records": light_records}
    with open(LIGHT_CACHE, "w") as f:
        json.dump(light_cache, f)
    light_size = os.path.getsize(LIGHT_CACHE) / 1024
    print(f"  ✅ Light cache: {light_size:.0f}KB")

    # ── 2. Summary (4KB) ──
    def safe(v):
        return str(v).strip() if v is not None else ""

    statuses = Counter()
    tipeproblems = Counter()
    branches = Counter()
    pemiliks = Counter()
    maintenances = Counter()
    monthly_raw = Counter()
    open_problems = []

    for r in all_data:
        statuses[safe(r.get("status"))] += 1
        tipeproblems[safe(r.get("tipeproblem"))] += 1
        branches[safe(r.get("branch"))] += 1
        pemiliks[safe(r.get("pemilik"))] += 1
        maintenances[safe(r.get("maintenance"))] += 1
        d = r.get("tanggal_foto", "")
        if d:
            monthly_raw[str(d)[:7]] += 1

        # Collect open problems
        if safe(r.get("status")).lower() in ("open", "on the way", "reopen", ""):
            if len(open_problems) < 20:
                desc = str(r.get("description_problem", ""))
                desc_clean = desc.replace("<p>", "").replace("</p>", " ").strip()[:100]
                open_problems.append({
                    "name": r.get("name"),
                    "nama_tempat": safe(r.get("nama_tempat")),
                    "tipeproblem": safe(r.get("tipeproblem")),
                    "status": safe(r.get("status")),
                    "description": desc_clean,
                    "maintenance": safe(r.get("maintenance")),
                    "tanggal_foto": str(r.get("tanggal_foto", ""))[:10],
                })

    summary = {
        "last_sync": now, "total": total,
        "statuses": dict(statuses.most_common()),
        "tipeproblems": dict(tipeproblems.most_common(15)),
        "branches": dict(branches.most_common(20)),
        "pemiliks": dict(pemiliks.most_common(10)),
        "maintenances": dict(maintenances.most_common(15)),
        "monthly": dict(sorted(monthly_raw.items())),
        "open_problems": open_problems,
    }
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f)
    print(f"  ✅ Summary: {os.path.getsize(SUMMARY_PATH)/1024:.0f}KB")

    # ── 3. Monthly (42KB) ──
    TOP_TIPES = ['Overheat', 'Listrik Mati', 'Camera', 'Printer',
                 'Remote Connection Issue', 'Flash', 'Others', 'Booth',
                 'Bug', 'Ganti Kertas', 'Print Manual', 'PC']

    monthly = {}
    for r in all_data:
        d = r.get("tanggal_foto", "")
        if not d:
            continue
        month = str(d)[:7]
        if month not in monthly:
            monthly[month] = {
                "total": 0, "open": 0, "closed": 0, "uncompleted": 0,
                "tipe": {t: 0 for t in TOP_TIPES},
                "branches": Counter(), "maintenances": Counter(),
                "pemiliks": Counter(), "booth_count": 0, "booths": set(),
                "latest_problems": [],
            }
        m = monthly[month]
        m["total"] += 1
        st = safe(r.get("status"))
        if st.lower() in ("open", "on the way", "reopen", ""):
            m["open"] += 1
        elif st == "Closed":
            m["closed"] += 1
        elif st == "Uncompleted":
            m["uncompleted"] += 1
        tipe = safe(r.get("tipeproblem"))
        if tipe in TOP_TIPES:
            m["tipe"][tipe] += 1
        elif tipe:
            m["tipe"]["Others"] += 1
        branch = safe(r.get("branch"))
        if branch:
            m["branches"][branch] += 1
        mtce = safe(r.get("maintenance"))
        if mtce:
            m["maintenances"][mtce] += 1
        pem = safe(r.get("pemilik"))
        if pem:
            m["pemiliks"][pem] += 1
        m["booths"].add(safe(r.get("nama_tempat")) or safe(r.get("nama_full")))
        m["booth_count"] = len(m["booths"])
        if len(m["latest_problems"]) < 3:
            m["latest_problems"].append({
                "name": r.get("name"),
                "nama_tempat": safe(r.get("nama_tempat")),
                "tipeproblem": tipe,
                "status": st or "Unknown",
            })

    months_out = {}
    for month, m in sorted(monthly.items()):
        months_out[month] = {
            "total": m["total"], "open": m["open"], "closed": m["closed"],
            "uncompleted": m["uncompleted"], "tipe": m["tipe"],
            "top_branches": dict(m["branches"].most_common(3)),
            "top_maintenances": dict(m["maintenances"].most_common(3)),
            "top_pemiliks": dict(m["pemiliks"].most_common(2)),
            "booth_count": m["booth_count"],
            "latest": m["latest_problems"],
        }

    monthly_out = {
        "meta": {
            "total_records": total,
            "total_months": len(monthly),
            "month_range": [sorted(monthly.keys())[0], sorted(monthly.keys())[-1]],
            "top_tipes": TOP_TIPES,
        },
        "months": months_out,
    }
    with open(MONTHLY_PATH, "w") as f:
        json.dump(monthly_out, f)
    print(f"  ✅ Monthly: {os.path.getsize(MONTHLY_PATH)/1024:.0f}KB ({len(monthly)} months)")

    print(f"\n✅ Sync complete! {total} records, {now[:16]}")


if __name__ == "__main__":
    main()
