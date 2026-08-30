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

# Staff email -> name mapping (for display)
STAFF_NAMES = {
    "almeydaroby@gmail.com": "Almeyda Roby Wijaya",
    "edgarsireg@gmail.com": "Wildan",
    "fadilalzurais04@gmail.com": "Fadil Al Zurais",
    "fadillahjkt32@gmail.com": "Fadillah",
    "farid.9april@gmail.com": "Farid Setyawan",
    "fengkymaksud@gmail.com": "Fengky Michael Hendrayadi Taneo",
    "galangsaputra136@gmail.com": "Galang Saputra",
    "gsimanjuntak49@gmail.com": "Gerry Octavian Simanjuntak",
    "hoseaimanuel17@gmail.com": "Hosea Immanuel Ignatius",
    "juwanparhan@gmail.com": "Juwan Parhan",
    "kahfidharma21@gmail.com": "Kahfi Dharma Nugraha",
    "mikaymikay412@gmail.com": "Mikayla",
    "pradivamahendra@gmail.com": "Pradiva Mahendra Winardi",
    "rifaldiferdiansyah0106@gmail.com": "Rivaldi Ferdiansyah",
    "febrianpratama376@gmail.com": "A Febrian",
}

# Shift type -> (start_hour, end_hour) mapping
# End hour > 24 means it crosses midnight (e.g. 17-25 = 17:00 to 01:00)
SHIFT_HOURS = {
    "Maintenance - Pagi": (8, 17),
    "Maintenance - Sore": (17, 25),
    "Pagi": (8, 17),
    "Controlling - Pagi (JKT)": (8, 17),
    "Controlling - Pagi (Bali)": (8, 17),
    "Controlling - Sore (JKT)": (17, 25),
    "Controlling - Sore (Bali)": (17, 25),
    "Workshop - Pagi": (8, 17),
    "Workshop - Pagi (Bali)": (8, 17),
    "Workshop - Sore": (17, 25),
    "Workshop - Sore (Bali)": (17, 25),
}
# Default shift for staff without assignment
DEFAULT_SHIFT = (8, 17)  # Pagi


def _is_on_shift(hour: int, shift_type: str = None) -> bool:
    start, end = SHIFT_HOURS.get(shift_type, DEFAULT_SHIFT)
    if end > 24:
        # Crosses midnight: e.g. 17-25 means 17:00 to 01:00
        return hour >= start or hour < end - 24
    return start <= hour < end


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

    # Fetch shift assignments for staff
    staff_shifts = {}
    try:
        sa_url = f"{url}/api/resource/Shift%20Assignment"
        sa_all = []
        sa_start = 0
        while True:
            sa_r = requests.get(sa_url, headers=headers,
                params={"limit_page_length": 200, "limit_start": sa_start,
                        "fields": json.dumps(["*"])}, timeout=30)
            if sa_r.status_code != 200:
                break
            sa_data = sa_r.json().get("data", [])
            if not sa_data:
                break
            sa_all.extend(sa_data)
            sa_start += 200
            if len(sa_data) < 200:
                break
        for s in sa_all:
            emp = (s.get("employee_name") or "").strip()
            shift = (s.get("shift_type") or "").strip()
            start = (s.get("start_date") or "")
            end = (s.get("end_date") or "") or "9999-12-31"
            if emp and shift and start:
                if emp not in staff_shifts:
                    staff_shifts[emp] = []
                staff_shifts[emp].append({"shift": shift, "start": str(start), "end": str(end)})
    except Exception as e:
        print(f"  Warning: could not fetch shifts: {e}")

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
    petugas_counter = Counter()
    monthly_raw = Counter()
    open_problems = []

    for r in all_data:
        statuses[safe(r.get("status"))] += 1
        tipeproblems[safe(r.get("tipeproblem"))] += 1
        branches[safe(r.get("branch"))] += 1
        pemiliks[safe(r.get("pemilik"))] += 1
        maintenances[safe(r.get("maintenance"))] += 1
        ptgs = safe(r.get("petugas"))
        if ptgs:
            petugas_counter[ptgs] += 1
        d = r.get("tanggal_foto", "")
        if d:
            monthly_raw[str(d)[:7]] += 1
        if safe(r.get("status")).lower() in ("open", "on the way", "reopen", ""):
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
                "creation": str(r.get("creation", ""))[:19],
                "visit": safe(r.get("visit")),
            })

    # Problems from last 60 days — all problems, no cap
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=60)
    recent_60d = []
    for r in all_data:
        created = r.get("creation", "")
        if created:
            try:
                created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if created_dt.tzinfo:
                    created_dt = created_dt.replace(tzinfo=None)
                if created_dt >= cutoff:
                    desc = str(r.get("description_problem", "") or "")
                    desc_clean = desc.replace("<p>", " ").replace("</p>", " ").replace("<br>", " ").strip()[:100]
                    recent_60d.append({
                        "name": r.get("name"),
                        "subject": safe(r.get("subject")) or safe(r.get("nama_full")) or safe(r.get("nama_tempat")),
                        "nama_tempat": safe(r.get("nama_tempat")),
                        "tipeproblem": safe(r.get("tipeproblem")),
                        "status": safe(r.get("status")),
                        "description": desc_clean,
                        "creation": str(created)[:19],
                        "maintenance": safe(r.get("maintenance")),
                    })
            except Exception:
                pass
    recent_60d.sort(key=lambda x: x.get("creation", ""), reverse=True)
    open_problems.sort(key=lambda x: str(x.get("creation", "")), reverse=True)

    summary = {
        "last_sync": now, "total": total,
        "statuses": dict(statuses.most_common()),
        "tipeproblems": dict(tipeproblems.most_common(15)),
        "branches": dict(branches.most_common(20)),
        "pemiliks": dict(pemiliks.most_common(10)),
        "maintenances": dict(maintenances.most_common(15)),
        "monthly": dict(sorted(monthly_raw.items())),
        "open_problems": open_problems,
        "recent_60d": recent_60d,
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
                "petugas": Counter(),
                "delays": {},
                "pemiliks": Counter(), "booth_count": 0, "booths": set(),
                "latest_problems": [],
                "outlets": Counter(), "outlet_tipes": {},
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
        ptgs = safe(r.get("petugas"))
        if ptgs:
            m["petugas"][ptgs] += 1
            # Track delay: visit_set_time -> pengambilan_tugas
            # Skip if staff requested pending (approved by supervisor)
            ap = str(r.get("approval_pending", "") or "").strip().lower()
            req_time = r.get("visit_set_time", "")
            ambil_time = r.get("pengambilan_tugas", "")
            if req_time and ambil_time and ap != "approved":
                try:
                    from datetime import datetime as dt
                    req_dt = dt.strptime(str(req_time)[:19], "%Y-%m-%d %H:%M:%S")
                    ambil_dt = dt.strptime(str(ambil_time)[:19], "%Y-%m-%d %H:%M:%S")
                    delay_min = (ambil_dt - req_dt).total_seconds() / 60
                    if 0 <= delay_min <= 1440:
                        # Check if staff was on shift
                        on_shift = False
                        pickup_hour = ambil_dt.hour
                        # Try to map petugas email -> employee name
                        emp_name = STAFF_NAMES.get(ptgs, "")
                        if emp_name:
                            emp_shifts = staff_shifts.get(emp_name, [])
                            if emp_shifts:
                                for s in emp_shifts:
                                    if s["start"] <= str(ambil_dt.date()) <= s["end"]:
                                        if _is_on_shift(pickup_hour, s["shift"]):
                                            on_shift = True
                                            break
                            else:
                                # Staff without assignment uses default shift
                                on_shift = _is_on_shift(pickup_hour)
                        else:
                            # No name mapping, assume default shift
                            on_shift = _is_on_shift(pickup_hour)
                        # Determine shift name for request time
                        shift_name_req = ""
                        req_hour = req_dt.hour
                        if emp_name:
                            emp_shifts = staff_shifts.get(emp_name, [])
                            for s in emp_shifts:
                                if s["start"] <= str(req_dt.date()) <= s["end"]:
                                    if _is_on_shift(req_hour, s["shift"]):
                                        shift_name_req = s["shift"]
                                        break
                            if not shift_name_req:
                                shift_name_req = "Pagi (Default)"
                        else:
                            shift_name_req = "Pagi (Default)"
                        # Determine shift name for pickup time
                        shift_name_ambil = ""
                        pickup_hour = ambil_dt.hour
                        if emp_name:
                            emp_shifts = staff_shifts.get(emp_name, [])
                            for s in emp_shifts:
                                if s["start"] <= str(ambil_dt.date()) <= s["end"]:
                                    if _is_on_shift(pickup_hour, s["shift"]):
                                        shift_name_ambil = s["shift"]
                                        break
                            if not shift_name_ambil:
                                shift_name_ambil = "Pagi (Default)"
                        else:
                            shift_name_ambil = "Pagi (Default)"
                        if ptgs not in m["delays"]:
                            m["delays"][ptgs] = {"total": 0, "sum_delay": 0, "max_delay": 0, "count": 0, "on_shift_count": 0, "on_shift_sum": 0, "on_shift_max": 0}
                        m["delays"][ptgs]["count"] += 1
                        m["delays"][ptgs]["sum_delay"] += delay_min
                        m["delays"][ptgs]["max_delay"] = max(m["delays"][ptgs]["max_delay"], delay_min)
                        if on_shift:
                            m["delays"][ptgs]["on_shift_count"] += 1
                            m["delays"][ptgs]["on_shift_sum"] += delay_min
                            m["delays"][ptgs]["on_shift_max"] = max(m["delays"][ptgs].get("on_shift_max", 0), delay_min)
                        # Store problem record for drilldown
                        if "problems" not in m["delays"][ptgs]:
                            m["delays"][ptgs]["problems"] = []
                        m["delays"][ptgs]["problems"].append({
                            "name": r.get("name", ""),
                            "subject": safe(r.get("subject")) or safe(r.get("nama_full")) or safe(r.get("nama_tempat")),
                            "tipeproblem": tipe,
                            "status": safe(r.get("status")),
                            "visit_set_time": str(req_time)[:19],
                            "pengambilan_tugas": str(ambil_time)[:19],
                            "ontheway_time": str(r.get("ontheway_time", ""))[:19],
                            "time_sampai_lokasi": str(r.get("time_sampai_lokasi", ""))[:19],
                            "delay_min": round(delay_min, 0),
                            "on_shift": on_shift,
                            "shift_name_req": shift_name_req,
                            "shift_name_ambil": shift_name_ambil,
                        })
                except Exception:
                    pass
        pem = safe(r.get("pemilik"))
        if pem:
            m["pemiliks"][pem] += 1
        m["booths"].add(safe(r.get("nama_tempat")) or safe(r.get("nama_full")))
        m["booth_count"] = len(m["booths"])
        outlet_name = r.get("subject") or r.get("nama_full") or r.get("nama_tempat") or "Unknown"
        m["outlets"][outlet_name] += 1
        if outlet_name not in m["outlet_tipes"]:
            m["outlet_tipes"][outlet_name] = Counter()
        m["outlet_tipes"][outlet_name][tipe if tipe else "Others"] += 1
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
        top_outlets = []
        for name, cnt in m["outlets"].most_common(10):
            top_tipes_dict = dict(m["outlet_tipes"].get(name, Counter()).most_common(3))
            top_outlets.append({"name": name, "total": cnt, "top_tipes": top_tipes_dict})

        months_out[month] = {
            "total": m["total"], "open": m["open"], "closed": m["closed"],
            "uncompleted": m["uncompleted"], "tipe": m["tipe"],
            "top_branches": dict(m["branches"].most_common(3)),
            "top_maintenances": dict(m["maintenances"].most_common(15)),
            "top_petugas": dict(m["petugas"].most_common(15)),
            "staff_delays": [
                {
                    "email": e,
                    "name": STAFF_NAMES.get(e, e),
                    "count": d["count"],
                    "avg_min": round(d["sum_delay"] / d["count"], 0),
                    "max_min": round(d["max_delay"], 0),
                    "on_shift_count": d.get("on_shift_count", 0),
                    "on_shift_avg_min": round(d.get("on_shift_sum", 0) / d.get("on_shift_count", 1), 0) if d.get("on_shift_count") else 0,
                    "on_shift_max_min": round(d.get("on_shift_max", 0), 0),
                    "problems": d.get("problems", []),
                }
                for e, d in sorted(
                    m.get("delays", {}).items(),
                    key=lambda x: x[1]["sum_delay"] / x[1]["count"],
                    reverse=True,
                )
            ],
            "top_pemiliks": dict(m["pemiliks"].most_common(2)),
            "booth_count": m["booth_count"],
            "latest": m["latest_problems"],
            "top_outlets": top_outlets,
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
