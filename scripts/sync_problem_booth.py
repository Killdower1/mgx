"""
Sync Problem Booth — now fetches subject field via ["*"] wildcard.
Batch size reduced to 100 with stream=True to prevent timeout.
"""
import json
import sys
import os
from collections import Counter
from datetime import datetime

import requests

CONFIG_PATH = "/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json"
LIGHT_CACHE = "/var/www/difotoin-dashboard/problem_booth_cache_light.json"
SUMMARY_PATH = "/var/www/difotoin-dashboard/problem_booth_summary.json"
MONTHLY_PATH = "/var/www/difotoin-dashboard/problem_booth_monthly.json"


def main():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    url = cfg["url"]
    headers = {"Authorization": "token {}:{}".format(cfg["api_key"], cfg["api_secret"])}

    print("Fetching Problem Booth (wildcard)...")
    all_data = []
    limit_start = 0
    page = 0
    while True:
        page += 1
        try:
            with requests.get("{}/api/resource/Problem%20Booth".format(url),
                headers=headers,
                params={"limit_page_length": 100, "limit_start": limit_start,
                        "fields": '["*"]'},
                stream=True, timeout=120) as r:
                if r.status_code != 200:
                    print("Error at {}: {}".format(limit_start, r.status_code))
                    break
                data = r.json().get("data", [])
                if not data:
                    break
                all_data.extend(data)
                limit_start += 100
                if page % 10 == 0:
                    print("  {} records...".format(limit_start))
                if len(data) < 100:
                    break
        except Exception as e:
            print("Error at {}: {}".format(limit_start, e))
            break

    total = len(all_data)
    print("Fetched {} records".format(total))
    if total == 0:
        sys.exit(1)

    now = datetime.now().isoformat()

    # Save light cache with subject field
    light_records = []
    for r in all_data:
        lr = {}
        # Keep all fields but truncate description
        for k, v in r.items():
            if k == "description_problem":
                if v:
                    clean = str(v).replace("<p>", " ").replace("</p>", " ").replace("<br>", " ")
                    clean = clean.replace("<div", " ").replace("</div>", " ").replace('class="ql-editor read-mode"', "")
                    lr[k] = clean[:150]
                else:
                    lr[k] = ""
            else:
                lr[k] = v
        light_records.append(lr)

    light_cache = {"last_sync": now, "total_records": total, "records": light_records}
    with open(LIGHT_CACHE, "w") as f:
        json.dump(light_cache, f)
    print("Light cache: {}KB".format(os.path.getsize(LIGHT_CACHE) // 1024))

    # Build summary (unchanged logic)
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
        if safe(r.get("status")).lower() in ("open", "on the way", "reopen", ""):
            if len(open_problems) < 20:
                desc = str(r.get("description_problem", "") or "")
                desc_clean = desc.replace("<p>", "").replace("</p>", " ").strip()[:100]
                open_problems.append({
                    "name": r.get("name"),
                    "subject": safe(r.get("subject")) or safe(r.get("nama_full")) or safe(r.get("nama_tempat")),
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
    print("Summary: {}KB".format(os.path.getsize(SUMMARY_PATH) // 1024))

    # Build monthly (unchanged)
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
                "subject": safe(r.get("subject")) or safe(r.get("nama_full")) or safe(r.get("nama_tempat")),
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
            "total_records": total, "total_months": len(monthly),
            "month_range": [sorted(monthly.keys())[0], sorted(monthly.keys())[-1]],
            "top_tipes": TOP_TIPES,
        },
        "months": months_out,
    }
    with open(MONTHLY_PATH, "w") as f:
        json.dump(monthly_out, f)
    print("Monthly: {}KB".format(os.path.getsize(MONTHLY_PATH) // 1024))
    print("Done. Subject field now included in cache.")


if __name__ == "__main__":
    main()
