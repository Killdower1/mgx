"""
Sync KPI Sistem data dari ERPNext -> cache JSON.
Staff list: HANYA dari QC owners + PB owners (Tim Controlling/Operasional).
Aggregate per bulan per staff.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "streamlit_template"))
from config import CONFIG_DIR

CONFIG_PATH = CONFIG_DIR / "erpnext_config.json"
CACHE_PATH = Path("/var/www/difotoin-dashboard/nicegui_template/data/kpi_sistem_cache.json")
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def erp_get(endpoint, params=None, timeout=60):
    import requests
    cfg = load_config()
    url = cfg["url"].rstrip("/") + endpoint
    auth = (cfg["api_key"], cfg["api_secret"])
    try:
        r = requests.get(url, auth=auth, params=params, timeout=timeout)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"ERR {endpoint}: {e}")
        return None

def fetch_all(doctype, fields, limit=20000):
    """Fetch all records with pagination."""
    all_data = []
    start = 0
    page = limit
    import json as _json
    while True:
        params = {
            "fields": _json.dumps(fields),
            "limit_start": start,
            "limit_page_length": page,
        }
        result = erp_get(f"/api/resource/{doctype.replace(' ', '%20')}", params)
        if not result or "data" not in result:
            break
        data = result["data"]
        if not data:
            break
        all_data.extend(data)
        if len(data) < page:
            break
        start += page
        print(f"  {doctype}: fetched {len(all_data)}...")
    return all_data

def month_key(dt_str):
    try:
        return str(dt_str)[:7]
    except:
        return None

def parse_dt(dt_str):
    try:
        return datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
    except:
        return None

def build_cache():
    print("=== KPI Sistem Sync Start ===")
    now = datetime.now()
    
    # STEP 1: Get controlling staff list from QC + PB owners
    print("Fetching QC owners...")
    qc_raw = fetch_all("Quality Control", ["owner"])
    qc_owners = set(r["owner"] for r in qc_raw if r.get("owner"))
    print(f"  QC owners: {len(qc_owners)}")
    
    print("Fetching PB owners...")
    pb_raw = fetch_all("Problem Booth", ["owner"])
    pb_owners = set(r["owner"] for r in pb_raw if r.get("owner"))
    print(f"  PB owners: {len(pb_owners)}")
    
    controlling_staff = qc_owners | pb_owners
    print(f"  Controlling staff (QC+PB): {len(controlling_staff)}")
    
    # STEP 2: Fetch full data for these staff only
    print("Fetching Employee Checkin (all)...")
    checkins_all = fetch_all("Employee Checkin", 
        ["name","owner","employee","employee_name","log_type","time","shift","shift_start","shift_end"])
    print(f"  Total checkins: {len(checkins_all)}")
    # Filter: only checkins by controlling staff owners (email match)
    checkins = [c for c in checkins_all 
                if c.get("owner") in controlling_staff]
    print(f"  Filtered (controlling only): {len(checkins)}")
    
    print("Fetching Quality Control (all)...")
    qc_all = fetch_all("Quality Control",
        ["name","owner","creation","modified","status_controlling"])
    qc = [q for q in qc_all if q.get("owner") in controlling_staff]
    print(f"  Filtered (controlling only): {len(qc)}")
    
    print("Fetching Problem Booth (all)...")
    pb_all = fetch_all("Problem Booth",
        ["name","owner","creation","tipeproblem","status","maintenance","modified_by"])
    pb = [p for p in pb_all if p.get("owner") in controlling_staff]
    print(f"  Filtered (controlling only): {len(pb)}")
    
    # STEP 3: Aggregate per staff per month
    # For checkins: group by owner (email) + month
    # Also build email -> display_name mapping
    email_to_name = {}
    checkin_by_staff_month = defaultdict(lambda: defaultdict(list))
    for c in checkins:
        email = c.get("owner", "Unknown")
        mk = month_key(c.get("time"))
        if mk:
            checkin_by_staff_month[email][mk].append(c)
            if email not in email_to_name and c.get("employee_name"):
                email_to_name[email] = c["employee_name"]
    
    # For QC: group by owner + month
    qc_by_staff_month = defaultdict(lambda: defaultdict(list))
    for q in qc:
        owner = q.get("owner", "Unknown")
        mk = month_key(q.get("creation"))
        if mk:
            qc_by_staff_month[owner][mk].append(q)
    
    # For PB: group by owner + month
    pb_by_staff_month = defaultdict(lambda: defaultdict(list))
    for p in pb:
        owner = p.get("owner", "Unknown")
        mk = month_key(p.get("creation"))
        if mk:
            pb_by_staff_month[owner][mk].append(p)
    
    # STEP 4: Calculate KPI per staff per month
    cache = {"last_sync": now.isoformat(), "staff": {}}
    
    for staff in sorted(controlling_staff):
        staff_data = {"months": {}, "display_name": email_to_name.get(staff, staff)}
        all_months = set(checkin_by_staff_month[staff].keys()) | set(qc_by_staff_month[staff].keys()) | set(pb_by_staff_month[staff].keys())
        
        for mk in sorted(all_months, reverse=True):
            c_records = checkin_by_staff_month[staff].get(mk, [])
            q_records = qc_by_staff_month[staff].get(mk, [])
            p_records = pb_by_staff_month[staff].get(mk, [])
            
            # KPI 1.1: Kehadiran
            # Build daily checkin map
            daily = defaultdict(list)
            for c in c_records:
                t = c.get("time")
                if t:
                    dt = parse_dt(t)
                    if dt:
                        daily[dt.strftime("%Y-%m-%d")].append(c)
            
            # Also count working days from QC and PB activity
            qc_dates = set()
            for q in q_records:
                t = q.get("creation")
                if t:
                    dt = parse_dt(t)
                    if dt:
                        qc_dates.add(dt.strftime("%Y-%m-%d"))
            
            pb_dates = set()
            for p in p_records:
                t = p.get("creation")
                if t:
                    dt = parse_dt(t)
                    if dt:
                        pb_dates.add(dt.strftime("%Y-%m-%d"))
            
            # Total working days = unique dates from checkin + QC + PB
            all_work_dates = set(daily.keys()) | qc_dates | pb_dates
            total_days = len(all_work_dates)
            
            late_count = 0
            late_details = []
            for date_str, logs in daily.items():
                in_logs = [l for l in logs if l.get("log_type") == "IN"]
                if in_logs:
                    first_in = min(in_logs, key=lambda x: x.get("time", ""))
                    shift_start = first_in.get("shift_start")
                    time_str = first_in.get("time", "")
                    if shift_start and time_str:
                        try:
                            checkin_dt = parse_dt(time_str)
                            shift_dt = parse_dt(str(shift_start))
                            if checkin_dt and shift_dt and checkin_dt > shift_dt:
                                late_count += 1
                                late_details.append({
                                    "date": date_str,
                                    "checkin": checkin_dt.strftime("%H:%M"),
                                    "shift_start": shift_dt.strftime("%H:%M"),
                                    "diff_min": int((checkin_dt - shift_dt).total_seconds() / 60),
                                })
                        except:
                            pass
            
            checkin_score = max(0, 100 - late_count * 33) if late_count < 3 else 0
            
            # KPI 2.2: QC
            total_qc = len(q_records)
            done_qc = sum(1 for r in q_records if r.get("status_controlling") == "Done")
            pending_qc = total_qc - done_qc
            qc_score = 100 if pending_qc == 0 else max(0, 100 - pending_qc * 10)
            
            # KPI 2.1: PB Created
            total_pb = len(p_records)
            by_tipe = dict(Counter(r.get("tipeproblem", "Unknown") for r in p_records).most_common(10))
            by_status = dict(Counter(r.get("status", "Unknown") for r in p_records))
            
            # KPI 3.1: Printer
            printer_pb = len([r for r in p_records if r.get("tipeproblem") == "Printer"])
            
            # Build raw checkin table: all working dates with activity
            raw_checkins = []
            all_dates = sorted(all_work_dates, reverse=True)
            for date_str in all_dates:
                logs = daily[date_str]
                in_logs = [l for l in logs if l.get("log_type") == "IN"]
                out_logs = [l for l in logs if l.get("log_type") == "OUT"]
                has_checkin = len(in_logs) > 0
                first_in = min(in_logs, key=lambda x: x.get("time", "")) if in_logs else None
                last_out = max(out_logs, key=lambda x: x.get("time", "")) if out_logs else None
                
                shift_start = first_in.get("shift_start") if first_in else None
                time_in = first_in.get("time", "") if first_in else ""
                is_late = False
                diff_min = 0
                if shift_start and time_in:
                    try:
                        checkin_dt = parse_dt(time_in)
                        shift_dt = parse_dt(str(shift_start))
                        if checkin_dt and shift_dt and checkin_dt > shift_dt:
                            is_late = True
                            diff_min = int((checkin_dt - shift_dt).total_seconds() / 60)
                    except:
                        pass
                
                # Get shift name from first IN log, or from QC/PB if no checkin
                shift_name = first_in.get("shift", "-") if first_in else "-"
                
                # Check QC/PB count for this date
                qc_count = sum(1 for q in q_records if str(q.get("creation", ""))[:10] == date_str)
                pb_count = sum(1 for p in p_records if str(p.get("creation", ""))[:10] == date_str)
                activity_note = ""
                if not has_checkin:
                    if qc_count and pb_count:
                        activity_note = f"QC:{qc_count}, PB:{pb_count}"
                    elif qc_count:
                        activity_note = f"QC:{qc_count}"
                    elif pb_count:
                        activity_note = f"PB:{pb_count}"
                
                raw_checkins.append({
                    "date": date_str,
                    "shift": shift_name,
                    "shift_start": parse_dt(str(shift_start)).strftime("%H:%M") if shift_start and parse_dt(str(shift_start)) else "-",
                    "checkin": parse_dt(time_in).strftime("%H:%M") if time_in and parse_dt(time_in) else "-",
                    "checkout": parse_dt(last_out.get("time", "")).strftime("%H:%M") if last_out and last_out.get("time") and parse_dt(last_out.get("time")) else "-",
                    "telat_menit": diff_min if is_late else "-",
                    "status": "TELAT" if is_late else ("OK" if has_checkin else ("QC/PB" if activity_note else "-")),
                    "activity": activity_note,
                })
            
            staff_data["months"][mk] = {
                "checkin": {
                    "total_days": total_days,
                    "late_count": late_count,
                    "late_details": late_details[:10],
                    "score": checkin_score,
                    "pass": late_count < 3,
                    "raw_records": raw_checkins,
                },
                "qc": {
                    "total": total_qc,
                    "done": done_qc,
                    "pending": pending_qc,
                    "score": qc_score,
                    "pass": pending_qc == 0,
                    "raw_records": [
                        {
                            "id": r.get("name", ""),
                            "date": str(r.get("creation", ""))[:10],
                            "status": r.get("status_controlling", ""),
                        }
                        for r in sorted(q_records, key=lambda x: x.get("creation", ""), reverse=True)
                    ],
                },
                "pb": {
                    "total": total_pb,
                    "by_tipe": by_tipe,
                    "by_status": by_status,
                    "score": 100,
                    "pass": True,
                    "raw_records": [
                        {
                            "id": r.get("name", ""),
                            "date": str(r.get("creation", ""))[:10],
                            "tipe": r.get("tipeproblem", ""),
                            "status": r.get("status", ""),
                            "maintenance": r.get("maintenance", ""),
                        }
                        for r in sorted(p_records, key=lambda x: x.get("creation", ""), reverse=True)
                    ],
                },
                "printer": {
                    "total_printer": printer_pb,
                    "pass": None,
                    "score": None,
                },
                "rekapan": {
                    "pass": None,
                    "score": None,
                }
            }
            
            # Overall score
            scores, weights = [], []
            if staff_data["months"][mk]["checkin"]["score"] is not None:
                scores.append(staff_data["months"][mk]["checkin"]["score"]); weights.append(20)
            if staff_data["months"][mk]["qc"]["score"] is not None:
                scores.append(staff_data["months"][mk]["qc"]["score"]); weights.append(25)
            if staff_data["months"][mk]["pb"]["score"] is not None:
                scores.append(staff_data["months"][mk]["pb"]["score"]); weights.append(20)
            staff_data["months"][mk]["overall"] = int(sum(s*w for s,w in zip(scores, weights)) / sum(weights)) if weights else 0
        
        if staff_data["months"]:
            cache["staff"][staff] = staff_data
    
    # Save
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, default=str, indent=2)
    
    print("=== Sync Complete ===")
    print(f"Controlling staff: {len(controlling_staff)}")
    print(f"Cache: {CACHE_PATH}")
    print(f"Size: {CACHE_PATH.stat().st_size / 1024:.1f} KB")

if __name__ == "__main__":
    build_cache()
