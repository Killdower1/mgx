"""
🔧 Problem Booth — operational dashboard for booth problems.
Data from ERPNext. All data pre-computed: summary (4KB), monthly (42KB), light cache (7MB lazy).
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from nicegui import ui

from pages import kpi_sistem

# ── Paths ──
SUMMARY_PATH = Path("/var/www/difotoin-dashboard/problem_booth_summary.json")
MONTHLY_PATH = Path("/var/www/difotoin-dashboard/problem_booth_monthly.json")
LIGHT_CACHE_PATH = Path("/var/www/difotoin-dashboard/problem_booth_cache_light.json")
CONFIG_PATH = Path(
    "/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json"
)
RECENT_INDEX_PATH = Path("/var/www/difotoin-dashboard/problem_booth_recent_index.json")
CCC_8090_DB_PATH = Path(
    "/home/killdower/controller-command-center/screenshot monitoring/data.db"
)
CCC_OUTLET_MASTER_PATH = Path(
    "/home/killdower/controller-command-center/screenshot monitoring/master-data/outlet_master.json"
)

# ── ERPNext URL ──
_ERP_URL = ""
try:
    with open(CONFIG_PATH) as _f:
        _ERP_URL = json.load(_f).get("url", "").rstrip("/")
except Exception:
    pass

# ── Colors ──
STATUS_COLORS = {
    "Closed": "#22c55e",
    "Open": "#ef4444",
    "Uncompleted": "#f59e0b",
    "On The Way": "#3b82f6",
    "Reopen": "#ef4444",
}
TIPE_COLORS = [
    "#f43f5e",
    "#fb923c",
    "#fbbf24",
    "#a3e635",
    "#34d399",
    "#2dd4bf",
    "#22d3ee",
    "#60a5fa",
    "#818cf8",
    "#a78bfa",
    "#c084fc",
    "#e879f9",
]
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"

TIPE_ICONS = {
    "Overheat": "🔥",
    "Listrik Mati": "⚡",
    "Camera": "📷",
    "Printer": "🖨️",
    "Remote Connection Issue": "🌐",
    "Flash": "💡",
    "Booth": "🏠",
    "Bug": "🐛",
    "Ganti Kertas": "📄",
    "Print Manual": "🖨️",
    "PC": "💻",
    "Hardware Error": "🔧",
    "Button": "🔘",
    "Sticker": "🏷️",
    "Monitor": "🖥️",
    "Internet": "🌐",
    "Camera Setting": "📷",
    "Anydesk": "🌐",
    "Hardware": "🔧",
    "Others": "📌",
}


def _fmt(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def _strip_html(text: str) -> str:
    """Remove all HTML tags from text (Quill editor output, etc)."""
    import re

    if not text:
        return ""
    # <[^>]*>? juga menghapus tag yang terpotong/truncated (mis. <span class="ql-ui" tanpa >)
    clean = re.sub(r"<[^>]*>?", " ", str(text))
    # Normalize whitespace and entities
    clean = (
        clean.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    clean = " ".join(clean.split())
    return clean.strip()


def _month_name(m: str) -> str:
    """2026-07 → Jul 2026"""
    try:
        dt = datetime.strptime(m, "%Y-%m")
        months_en = [
            "",
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        return f"{months_en[dt.month]} {dt.year}"
    except Exception:
        return m


_MONTHS_ID = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Mei",
    "Jun",
    "Jul",
    "Agu",
    "Sep",
    "Okt",
    "Nov",
    "Des",
]


def _fmt_date(ts) -> str:
    """'2026-07-14 08:30:00' -> '14 Jul 2026' (graceful fallback: raw first 10 chars)."""
    try:
        d = str(ts)[:10]
        y, m, dd = d.split("-")
        return f"{int(dd)} {_MONTHS_ID[int(m)]} {y}"
    except Exception:
        return str(ts)[:10]


def _outlet_label(rec: dict) -> str:
    """Prefer outlet name (subject), fall back to other booth identifiers."""
    for key in ("subject", "nama_full", "nama_tempat", "name"):
        val = str(rec.get(key, "") or "").strip()
        if val:
            return val
    return "?"


# ═══════════════════════════════════════════════
#  DATA LOADERS
# ═══════════════════════════════════════════════


def load_summary() -> dict:
    if not SUMMARY_PATH.exists():
        return {}
    try:
        with open(SUMMARY_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def load_monthly() -> dict:
    if not MONTHLY_PATH.exists():
        return {}
    try:
        with open(MONTHLY_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def load_light_cache():
    """Load full cache (7MB) — lazy, only for detail tab."""
    if not LIGHT_CACHE_PATH.exists():
        import pandas as pd

        return pd.DataFrame()
    try:
        import pandas as pd

        with open(LIGHT_CACHE_PATH) as f:
            cache = json.load(f)
        records = cache.get("records", [])
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        if "tanggal_foto" in df.columns:
            df["_date"] = pd.to_datetime(df["tanggal_foto"], errors="coerce")
        return df
    except Exception:
        import pandas as pd

        return pd.DataFrame()


# ═══════════════════════════════════════════════
#  8090 → PB ERPNext MONITORING
# ═══════════════════════════════════════════════


def _norm_outlet_name(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def _load_outlet_master_maps():
    """Return alias->canonical map and canonical name set from 8090 outlet master JSON."""
    alias_to_canon = {}
    canonical_names = set()
    try:
        data = json.load(open(CCC_OUTLET_MASTER_PATH))
        for n in data.get("canonical_names", []) or []:
            if n:
                canonical_names.add(str(n))
                alias_to_canon[_norm_outlet_name(n)] = str(n)
        for m in data.get("mapping", []) or []:
            canon = (m.get("canonical_name") or "").strip()
            if not canon:
                continue
            canonical_names.add(canon)
            for key in ("monitor_name", "live_monitor_id"):
                val = (m.get(key) or "").strip()
                if val:
                    alias_to_canon[_norm_outlet_name(val)] = canon
    except Exception:
        pass
    return alias_to_canon, canonical_names


def _canon_outlet(name: str, alias_to_canon: dict) -> str:
    return alias_to_canon.get(_norm_outlet_name(name), str(name or "").strip())


def _parse_dt(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "")[:19])
    except Exception:
        try:
            return datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def _ms_to_dt(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000)
    except Exception:
        return None


def _fmt_dt(dt):
    if not dt:
        return "-"
    return dt.strftime("%d/%m %H:%M")


def _age_text(dt):
    if not dt:
        return "-"
    sec = max(0, int((datetime.now() - dt).total_seconds()))
    if sec < 3600:
        return f"{sec//60}m"
    if sec < 86400:
        return f"{sec//3600}j {(sec%3600)//60}m"
    return f"{sec//86400}h {((sec%86400)//3600)}j"


def _load_shift_staff_for_alerts(alert_rows):
    """Fetch ERPNext shift assignments/types once, then resolve active controlling staff per alert time/area."""
    result = {}
    if not alert_rows:
        return result
    dates = sorted(
        {(r.get("started_at") or datetime.now()).date().isoformat() for r in alert_rows}
    )
    try:
        import requests

        cfg = json.load(open(CONFIG_PATH))
        base = cfg.get("url", "").rstrip("/")
        headers = {"Authorization": "token " + cfg["api_key"] + ":" + cfg["api_secret"]}
        st = requests.get(
            base + "/api/resource/Shift Type",
            headers=headers,
            params={
                "fields": json.dumps(["name", "start_time", "end_time"]),
                "limit_page_length": 200,
            },
            timeout=20,
        )
        shift_types = (
            {x.get("name"): x for x in st.json().get("data", [])} if st.ok else {}
        )
        filters = [["status", "=", "Active"]]
        if dates:
            filters += [
                ["start_date", "<=", max(dates)],
                ["end_date", ">=", min(dates)],
            ]
        sa = requests.get(
            base + "/api/resource/Shift Assignment",
            headers=headers,
            params={
                "fields": json.dumps(
                    [
                        "employee",
                        "employee_name",
                        "shift_type",
                        "start_date",
                        "end_date",
                        "status",
                    ]
                ),
                "filters": json.dumps(filters),
                "limit_page_length": 500,
            },
            timeout=25,
        )
        assignments = sa.json().get("data", []) if sa.ok else []
    except Exception:
        return result

    def in_shift(dt, shift_name):
        info = shift_types.get(shift_name) or {}
        start = str(info.get("start_time") or "")[:8]
        end = str(info.get("end_time") or "")[:8]
        if not start or not end:
            return False
        sh, sm, *_ = [int(x) for x in start.split(":")]
        eh, em, *_ = [int(x) for x in end.split(":")]
        cur = dt.hour * 60 + dt.minute
        smin, emin = sh * 60 + sm, eh * 60 + em
        if smin <= emin:
            return smin <= cur <= emin
        return cur >= smin or cur <= emin

    def date_ok(dt, a):
        d = dt.date().isoformat()
        return (
            str(a.get("start_date") or "")[:10]
            <= d
            <= str(a.get("end_date") or a.get("start_date") or "")[:10]
        )

    for row in alert_rows:
        dt = row.get("started_at") or datetime.now()
        area = str(row.get("area") or "").lower()
        want_bali = "bali" in area
        staff = []
        for a in assignments:
            stype = str(a.get("shift_type") or "")
            low = stype.lower()
            if "controlling" not in low:
                continue
            if not date_ok(dt, a) or not in_shift(dt, stype):
                continue
            if want_bali and ("bali" not in low and "shift 3" not in low):
                continue
            if not want_bali and ("jkt" not in low and "shift 3" not in low):
                continue
            name = str(a.get("employee_name") or a.get("employee") or "").strip()
            if name and name not in staff:
                staff.append(name)
        result[row["_key"]] = ", ".join(staff[:4]) if staff else "-"
    return result


def _load_8090_pb_monitor(hours: int = 24, pb_window_hours: int = 24):
    """Build read-only funnel rows: 8090 machine error → ERPNext PB → visit status."""
    alias_to_canon, canonical_names = _load_outlet_master_maps()
    # 8090 alerts is an event log and repeats the same issue every few minutes.
    # For the dashboard, show ACTIVE/current problems only: current printer_status +
    # very fresh alert events (mainly no_update / API error), not the full 24h history.
    since_ms = int((datetime.now() - timedelta(minutes=15)).timestamp() * 1000)
    anomalies = {}

    def ensure(outlet_id, area=""):
        canon = _canon_outlet(outlet_id, alias_to_canon)
        key = _norm_outlet_name(canon or outlet_id)
        if key not in anomalies:
            anomalies[key] = {
                "_key": key,
                "outlet_id": outlet_id,
                "outlet": canon or outlet_id,
                "area": area or "-",
                "types": [],
                "messages": [],
                "started_at": None,
                "latest_at": None,
            }
        if area and anomalies[key].get("area") in ("", "-"):
            anomalies[key]["area"] = area
        return anomalies[key]

    try:
        con = sqlite3.connect(str(CCC_8090_DB_PATH))
        con.row_factory = sqlite3.Row
        # Aggregate recent alert noise per outlet/type; 8090 emits repeated alerts every few minutes.
        for r in con.execute(
            """
            SELECT a.outlet_id, COALESCE(m.area,'') area, a.type, MAX(a.message) message,
                   MIN(a.created_at) first_at, MAX(a.created_at) latest_at, COUNT(*) cnt
            FROM alerts a
            LEFT JOIN master_outlets m ON m.live_monitor_id = a.outlet_id OR m.outlet_name = a.outlet_id
            WHERE a.created_at >= ? AND a.type IN ('no_update','offline','error')
            GROUP BY a.outlet_id, a.type
            ORDER BY latest_at DESC
            """,
            (since_ms,),
        ):
            row = ensure(r["outlet_id"], r["area"])
            label = {
                "no_update": "No update",
                "offline": "Printer offline",
                "error": "Error 8090",
            }.get(r["type"], r["type"])
            if label not in row["types"]:
                row["types"].append(label)
            if r["message"]:
                row["messages"].append(str(r["message"]))
            first, latest = _ms_to_dt(r["first_at"]), _ms_to_dt(r["latest_at"])
            row["started_at"] = min(
                [x for x in [row["started_at"], first] if x], default=first
            )
            row["latest_at"] = max(
                [x for x in [row["latest_at"], latest] if x], default=latest
            )
        # Current printer_status conditions: queue and high ping may not always create alert rows.
        for r in con.execute("""
            SELECT p.*, COALESCE(m.area,'') area
            FROM printer_status p
            LEFT JOIN master_outlets m ON m.live_monitor_id = p.outlet_id OR m.outlet_name = p.outlet_id
            """):
            labels = []
            status = str(r["status"] or "").lower()
            if status in ("offline", "error"):
                labels.append(
                    "Printer offline" if status == "offline" else "Error printer"
                )
            if int(r["has_queue"] or 0) == 1:
                labels.append("Queue stuck")
            for field, label in (
                ("ping_ms", "Ping besar"),
                ("internet_ping_ms", "Internet ping besar"),
            ):
                try:
                    if int(r[field]) >= 3000:
                        labels.append(label)
                except Exception:
                    pass
            if not labels:
                continue
            row = ensure(r["outlet_id"], r["area"])
            for label in labels:
                if label not in row["types"]:
                    row["types"].append(label)
            ts = int(r["status_changed_at"] or r["queue_since"] or r["updated_at"] or 0)
            dt = _ms_to_dt(ts) if ts else None
            row["started_at"] = min(
                [x for x in [row["started_at"], dt] if x], default=dt
            )
            row["latest_at"] = max([x for x in [row["latest_at"], dt] if x], default=dt)
        con.close()
    except Exception as e:
        return {"error": str(e), "rows": [], "kpi": {}}

    rows = list(anomalies.values())
    shifts = _load_shift_staff_for_alerts(rows)

    # Load PB cache and index by canonical outlet.
    pb_by_outlet = {}
    try:
        cache = json.load(open(LIGHT_CACHE_PATH))
        for rec in cache.get("records", []) or []:
            outlet_raw = (
                rec.get("nama_full")
                or rec.get("subject")
                or rec.get("nama_tempat")
                or ""
            )
            canon = _canon_outlet(outlet_raw, alias_to_canon)
            key = _norm_outlet_name(canon or outlet_raw)
            if not key:
                continue
            pb_by_outlet.setdefault(key, []).append(rec)
        for vals in pb_by_outlet.values():
            vals.sort(key=lambda r: str(r.get("creation") or ""), reverse=True)
    except Exception:
        pass

    out_rows = []
    for row in rows:
        key = row["_key"]
        started = row.get("started_at") or row.get("latest_at") or datetime.now()
        pbs = pb_by_outlet.get(key, [])
        active = [
            p
            for p in pbs
            if str(p.get("status") or "").lower() not in ("closed", "cancelled")
        ]
        matched = active[:1]
        if not matched:
            lo, hi = started - timedelta(hours=1), started + timedelta(
                hours=pb_window_hours
            )
            for pbr in pbs[:30]:
                cr = _parse_dt(pbr.get("creation"))
                if cr and lo <= cr <= hi:
                    matched = [pbr]
                    break
        pb = matched[0] if matched else None
        visit = str((pb or {}).get("visit") or "")
        pb_status = str((pb or {}).get("status") or "")
        if not pb:
            funnel = "🔴 Belum ada PB ERPNext"
        elif pb_status.lower() == "closed":
            funnel = "🟢 PB Closed"
        elif visit.strip().lower() in ("visit", "repair", "workshop", "visit external"):
            funnel = "🟠 Butuh Visit"
        elif pb_status.lower() in ("on the way",):
            funnel = "🔵 On The Way"
        else:
            funnel = "🟡 Sudah ada PB"
        pb_link = "-"
        if pb and pb.get("name"):
            pb_link = f'<a href="{_ERP_URL}/app/problem-booth/{pb["name"]}" target="_blank" style="text-decoration:none;color:#cdd6f4;font-weight:600;">{pb["name"]}</a>'
        out_rows.append(
            {
                "Status": funnel,
                "Outlet": row["outlet"],
                "Area": row.get("area") or "-",
                "Error 8090": ", ".join(row["types"]),
                "Sejak": _fmt_dt(started),
                "Umur": _age_text(started),
                "Kontroller Jaga": shifts.get(key, "-"),
                "PB ERPNext": pb_link,
                "Status PB": pb_status or "-",
                "Visit": visit or "-",
                "_sort_ts": int(started.timestamp()) if started else 0,
            }
        )
    out_rows.sort(
        key=lambda r: (0 if r["Status"].startswith("🔴") else 1, -r.get("_sort_ts", 0))
    )
    kpi = {
        "errors": len(out_rows),
        "no_pb": sum(1 for r in out_rows if r["Status"].startswith("🔴")),
        "has_pb": sum(1 for r in out_rows if not r["Status"].startswith("🔴")),
        "visit": sum(
            1
            for r in out_rows
            if "Visit" in r["Status"]
            or str(r.get("Visit", "")).lower()
            in ("visit", "repair", "workshop", "visit external")
        ),
        "closed": sum(1 for r in out_rows if "Closed" in r["Status"]),
    }
    return {
        "rows": out_rows,
        "kpi": kpi,
        "error": None,
        "window_hours": hours,
        "pb_window_hours": pb_window_hours,
    }


def _monitor_cols():
    base = [
        ("Status", 190, 2),
        ("Outlet", 220, 3),
        ("Area", 100, 1),
        ("Error 8090", 230, 3),
        ("Sejak", 110, 1),
        ("Umur", 90, 1),
        ("Kontroller Jaga", 190, 2),
        ("PB ERPNext", 130, 1),
        ("Status PB", 120, 1),
        ("Visit", 130, 1),
    ]
    cols = []
    for name, minw, flex in base:
        c = {
            "headerName": name,
            "field": name,
            "minWidth": minw,
            "flex": flex,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
        }
        if name == "Outlet":
            c["pinned"] = "left"
        if name in ("Sejak", "Umur"):
            c["cellStyle"] = {"textAlign": "right"}
        cols.append(c)
    return cols


def _render_8090_pb_tab():
    data = _load_8090_pb_monitor(hours=24, pb_window_hours=24)
    if data.get("error"):
        ui.label(f"Gagal load monitor 8090: {data['error']}").classes("text-red-400")
        return
    k = data.get("kpi", {})
    ui.label("8090 → PB ERPNext").classes("text-xl font-bold text-white")
    ui.label(
        "Read-only: pantau mesin error 8090, kontroller shift, dan apakah sudah ada PB di ERPNext."
    ).classes("text-sm text-gray-400 mb-3")
    with ui.row().classes("w-full gap-4"):
        _kpi_card(
            "Mesin Error 8090",
            _fmt(k.get("errors", 0)),
            "aktif sekarang / alert fresh",
            "#ef4444",
        )
        _kpi_card(
            "Belum Ada PB",
            _fmt(k.get("no_pb", 0)),
            "butuh follow-up kontroller",
            "#f59e0b",
        )
        _kpi_card(
            "Sudah Ada PB", _fmt(k.get("has_pb", 0)), "terdeteksi di ERPNext", "#3b82f6"
        )
        _kpi_card(
            "Butuh Visit", _fmt(k.get("visit", 0)), "Visit/Repair/Workshop", "#fb923c"
        )
        _kpi_card("Closed", _fmt(k.get("closed", 0)), "sudah selesai", "#22c55e")
    rows = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in data.get("rows", [])
    ]
    with ui.element("div").style(CARD).classes("w-full mt-4"):
        ui.label("Pantauan Error → PB").classes(MV)
        if not rows:
            ui.label("Tidak ada error 8090 dalam 24 jam terakhir.").classes(
                "text-xs text-gray-500 italic"
            )
            return
        ui.aggrid(
            {
                "columnDefs": _monitor_cols(),
                "rowData": rows,
                "pagination": True,
                "paginationPageSize": 20,
                "paginationPageSizeSelector": [20, 50, 100],
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True},
                "animateRows": True,
                "rowHeight": 42,
                "headerHeight": 42,
                "enableCellTextSelection": True,
            },
            theme="balham",
            html_columns=[7],
        ).classes("w-full ag-theme-balham-dark").style("height:auto; min-height:240px;")


# ═══════════════════════════════════════════════
#  COMMAND CENTER NATIVE TAB (port 8090 flow)
# ═══════════════════════════════════════════════

CCC_SETTINGS_PATH = Path(
    "/home/killdower/controller-command-center/screenshot monitoring/settings.json"
)


def _cc_ms(value) -> int:
    if not value:
        return 0
    try:
        if isinstance(value, (int, float)):
            return int(value)
        raw = str(value).strip()
        if raw.isdigit():
            return int(raw)
        if raw.endswith("Z"):
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(raw.replace("T", " ")[:19])
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _cc_age(ms: int) -> str:
    if not ms or ms < 0:
        return "-"
    minute = int(ms // 60000)
    if minute < 1:
        return "<1m"
    if minute < 60:
        return f"{minute}m"
    hour = minute // 60
    rem_min = minute % 60
    if hour < 24:
        return f"{hour}j {rem_min}m"
    return f"{hour // 24}h {hour % 24}j"


def _cc_latest_client_version() -> str:
    try:
        data = json.load(open(CCC_8090_DB_PATH.parent / "client-version.json"))
        return str(data.get("version") or "").strip()
    except Exception:
        return ""


def _cc_version_lt(a: str, b: str) -> bool:
    def parts(v):
        out = []
        for x in str(v or "").split("."):
            try:
                out.append(int(x))
            except Exception:
                out.append(0)
        return out

    aa, bb = parts(a), parts(b)
    for i in range(max(len(aa), len(bb))):
        av = aa[i] if i < len(aa) else 0
        bv = bb[i] if i < len(bb) else 0
        if av < bv:
            return True
        if av > bv:
            return False
    return False


def _cc_read_threshold_minutes() -> int:
    try:
        data = json.load(open(CCC_SETTINGS_PATH))
        return max(1, int(data.get("delayedThresholdMinutes") or 15))
    except Exception:
        return 15


def _cc_classify(row: dict, opts: dict) -> dict:
    now = opts["now"]
    latest_version = opts.get("latest_version", "")
    screenshot_threshold_ms = opts["screenshot_threshold_ms"]
    printer_recent_ms = opts["printer_recent_ms"]
    printer_stale_ms = opts["printer_stale_ms"]
    modem_timeout_ms = opts["modem_timeout_ms"]
    issues, warnings, hygiene = [], [], []
    score = 100
    primary_age_ms = 0
    shot_ms = _cc_ms(row.get("screenshot_updated_at"))
    shot_age_ms = now - shot_ms if shot_ms else 0
    screenshot_recent = bool(shot_ms and shot_age_ms <= screenshot_threshold_ms)
    if not shot_ms:
        hygiene.append("Screenshot belum ada")
    elif shot_age_ms > screenshot_threshold_ms * 2:
        issues.append(f"Screenshot telat {_cc_age(shot_age_ms)}")
        score -= 30
        primary_age_ms = max(primary_age_ms, shot_age_ms)
    elif shot_age_ms > screenshot_threshold_ms:
        warnings.append(f"Screenshot mulai telat {_cc_age(shot_age_ms)}")
        score -= 12
        primary_age_ms = max(primary_age_ms, shot_age_ms)
    p = row.get("printer") or {}
    printer_updated_ms = _cc_ms(p.get("updated_at"))
    printer_age_ms = now - printer_updated_ms if printer_updated_ms else 0
    printer_recent = bool(printer_updated_ms and printer_age_ms <= printer_recent_ms)
    printer_very_stale = bool(printer_updated_ms and printer_age_ms > printer_stale_ms)
    printer_status = str(p.get("status") or "").lower()
    bad_printer = printer_status in (
        "offline",
        "paper_jam",
        "no_paper",
        "low_ink",
        "error",
        "cover_open",
    )
    if not p.get("outlet_id"):
        hygiene.append("Printer belum report")
    elif bad_printer and printer_recent:
        issues.append("Printer " + printer_status.replace("_", " "))
        score -= 28
        primary_age_ms = max(primary_age_ms, printer_age_ms or 1)
    elif bad_printer and not printer_recent:
        hygiene.append(
            f"Printer monitor stale {_cc_age(printer_age_ms)} ({printer_status.replace('_', ' ')})"
        )
    elif printer_very_stale and not screenshot_recent:
        hygiene.append(f"Printer monitor stale {_cc_age(printer_age_ms)}")
    elif printer_very_stale and screenshot_recent:
        hygiene.append(
            f"Printer monitor stale {_cc_age(printer_age_ms)} — screenshot tetap live"
        )
    has_queue = int(p.get("has_queue") or 0) == 1
    queue_since_ms = _cc_ms(p.get("queue_since"))
    queue_age_ms = now - queue_since_ms if has_queue and queue_since_ms else 0
    if has_queue and printer_recent and queue_age_ms > 10 * 60000:
        issues.append(
            f"Queue stuck {_cc_age(queue_age_ms)} ({p.get('queue_count') or 0} file)"
        )
        score -= 25
        primary_age_ms = max(primary_age_ms, queue_age_ms)
    elif has_queue and printer_recent:
        warnings.append(
            f"Queue aktif {_cc_age(queue_age_ms)} ({p.get('queue_count') or 0} file)"
        )
        score -= 12
        primary_age_ms = max(primary_age_ms, queue_age_ms)
    elif has_queue and not printer_recent:
        hygiene.append(f"Queue stale {_cc_age(queue_age_ms)} dari report lama")
    m = row.get("modem") or {}
    modem_updated_ms = _cc_ms(m.get("last_update"))
    modem_age_ms = now - modem_updated_ms if modem_updated_ms else 0
    modem_status = str(m.get("status") or "").lower()
    if (
        row.get("has_mapped_modem")
        and m.get("id")
        and modem_status == "offline"
        and modem_age_ms <= modem_timeout_ms
    ):
        issues.append(f"Modem offline {_cc_age(modem_age_ms)}")
        score -= 22
        primary_age_ms = max(primary_age_ms, modem_age_ms or 1)
    elif (
        row.get("has_mapped_modem") and m.get("id") and modem_age_ms > modem_timeout_ms
    ):
        hygiene.append(f"Modem monitor stale {_cc_age(modem_age_ms)}")
    elif row.get("has_mapped_modem") and not m.get("id"):
        hygiene.append("Modem mapped tapi belum report")
    client_version = str(p.get("client_version") or "").strip()
    if (
        latest_version
        and client_version
        and _cc_version_lt(client_version, latest_version)
    ):
        warnings.append(f"Client outdated v{client_version}")
        score -= 8
    score = max(0, min(100, score))
    level = "healthy"
    if issues or score < 60:
        level = "critical"
    elif warnings or score < 85:
        level = "warning"
    elif not shot_ms and not p.get("outlet_id") and not m.get("id"):
        level = "no_data"
        score = 60
    issue_text = " | ".join(issues + warnings).lower()
    root_cause, action = "Normal", "Monitor normal"
    if "queue" in issue_text:
        root_cause, action = (
            "DNP / hotfolder queue",
            "Cek printer, DNP Hot Folder, file nyangkut",
        )
    elif "printer" in issue_text:
        root_cause, action = (
            "Printer / client monitor",
            "Cek printer status dan app monitor di PC outlet",
        )
    elif "screenshot" in issue_text:
        root_cause, action = (
            "PC/app/internet outlet kemungkinan down",
            "Cek koneksi outlet, PC, dan app screenshot",
        )
    elif "modem" in issue_text:
        root_cause, action = (
            "Modem/ESP monitor",
            "Cek ESP/modem, restart modem jika perlu",
        )
    elif "outdated" in issue_text:
        root_cause, action = (
            "Client version outdated",
            "Biarkan auto-update / cek client jika stuck",
        )
    elif level == "no_data":
        root_cause, action = (
            "Belum ada data monitor",
            "Cek mapping master outlet dan instalasi client",
        )
    return {
        "outlet_id": row.get("outlet_id") or "-",
        "area": row.get("area") or "-",
        "score": score,
        "level": level,
        "issues": issues,
        "warnings": warnings,
        "hygiene": hygiene,
        "root_cause": root_cause,
        "action": action,
        "aging_ms": primary_age_ms,
        "aging": _cc_age(primary_age_ms),
        "screenshot_age": _cc_age(shot_age_ms) if shot_ms else "-",
        "printer_status": printer_status or "unknown",
        "printer_age": _cc_age(printer_age_ms) if printer_updated_ms else "-",
        "modem_status": modem_status or ("unknown" if m.get("id") else "-"),
        "modem_age": _cc_age(modem_age_ms) if modem_updated_ms else "-",
        "client_version": client_version or "-",
        "latest_version": latest_version or "-",
        "alert_count": int(row.get("alert_count") or 0),
    }


def _load_command_center_data(limit: int = 30) -> dict:
    try:
        now = int(datetime.now().timestamp() * 1000)
        screenshot_threshold_ms = _cc_read_threshold_minutes() * 60000
        latest_version = _cc_latest_client_version()
        since_24h = now - 24 * 60 * 60 * 1000
        con = sqlite3.connect(str(CCC_8090_DB_PATH))
        con.row_factory = sqlite3.Row
        masters = [
            dict(x)
            for x in con.execute(
                "SELECT * FROM master_outlets ORDER BY outlet_name ASC"
            )
        ]
        screenshots = [
            dict(x)
            for x in con.execute(
                """SELECT * FROM outlet_screenshots s WHERE NOT EXISTS (SELECT 1 FROM deleted_live_monitors dl WHERE dl.outlet_id = s.outlet_id)"""
            )
        ]
        printers = [dict(x) for x in con.execute("SELECT * FROM printer_status")]
        devices = [
            dict(x)
            for x in con.execute("SELECT * FROM devices WHERE COALESCE(hidden,0)=0")
        ]
        alert_rows = [
            dict(x)
            for x in con.execute(
                "SELECT outlet_id, COUNT(*) AS count, MAX(created_at) AS latest FROM alerts WHERE created_at > ? GROUP BY outlet_id",
                (since_24h,),
            )
        ]
        con.close()
        outlet_map = {}

        def ensure_outlet(outlet_id):
            key = str(outlet_id or "").strip()
            if not key:
                return None
            outlet_map.setdefault(
                key,
                {
                    "outlet_id": key,
                    "area": "",
                    "printer": {},
                    "modem": {},
                    "has_mapped_modem": False,
                },
            )
            return outlet_map[key]

        master_by_esp = {}
        for m in masters:
            row = ensure_outlet(m.get("outlet_name"))
            if not row:
                continue
            row["area"] = row.get("area") or m.get("area") or ""
            if m.get("esp_device_id"):
                row["has_mapped_modem"] = True
                master_by_esp[str(m.get("esp_device_id"))] = row["outlet_id"]
        for s in screenshots:
            row = ensure_outlet(s.get("outlet_id"))
            if row:
                row["area"] = row.get("area") or s.get("area") or ""
                row["screenshot_updated_at"] = s.get("updated_at")
        for p in printers:
            key = str(p.get("outlet_id") or "").strip()
            if key in outlet_map:
                outlet_map[key]["printer"] = p
        for d in devices:
            mapped = master_by_esp.get(str(d.get("id") or ""))
            if mapped and mapped in outlet_map:
                outlet_map[mapped]["modem"] = d
        for a in alert_rows:
            key = str(a.get("outlet_id") or "").strip()
            if key in outlet_map:
                outlet_map[key]["alert_count"] = a.get("count") or 0
        opts = {
            "now": now,
            "latest_version": latest_version,
            "screenshot_threshold_ms": screenshot_threshold_ms,
            "printer_recent_ms": 5 * 60000,
            "printer_stale_ms": max(30 * 60000, screenshot_threshold_ms * 2),
            "modem_timeout_ms": 5 * 60000,
        }
        classified = [_cc_classify(row, opts) for row in outlet_map.values()]
        order = {"critical": 0, "warning": 1, "no_data": 2, "healthy": 3}
        classified.sort(
            key=lambda r: (
                order.get(r["level"], 9),
                -r.get("aging_ms", 0),
                r.get("outlet_id", ""),
            )
        )
        summary = {
            "total": 0,
            "healthy": 0,
            "warning": 0,
            "critical": 0,
            "no_data": 0,
            "stale": 0,
            "sla_breached": 0,
            "with_alerts": 0,
        }
        for row in classified:
            summary["total"] += 1
            summary[row["level"]] = summary.get(row["level"], 0) + 1
            if row["level"] == "critical":
                summary["sla_breached"] += 1
            if row.get("alert_count", 0) > 0:
                summary["with_alerts"] += 1
            if row.get("hygiene"):
                summary["stale"] += 1
        areas = {}
        for row in classified:
            area = row.get("area") or "-"
            areas.setdefault(
                area,
                {
                    "area": area,
                    "total": 0,
                    "healthy": 0,
                    "warning": 0,
                    "critical": 0,
                    "no_data": 0,
                    "stale": 0,
                    "avg_score": 0,
                },
            )
            a = areas[area]
            a["total"] += 1
            a[row["level"]] = a.get(row["level"], 0) + 1
            a["avg_score"] += row["score"]
            if row.get("hygiene"):
                a["stale"] += 1
        area_rows = []
        for a in areas.values():
            a["avg_score"] = round(a["avg_score"] / max(1, a["total"]))
            area_rows.append(a)
        area_rows.sort(
            key=lambda a: (-a["critical"], -a["warning"], -a["stale"], a["area"])
        )
        top_problems = [
            r for r in classified if r["level"] in ("critical", "warning", "no_data")
        ][:limit]
        data_hygiene = sorted(
            [r for r in classified if r.get("hygiene")],
            key=lambda r: (-len(r.get("hygiene") or []), r.get("outlet_id", "")),
        )[:limit]
        brief_parts = [
            f"{summary['critical']} current critical, {summary['warning']} warning dari {summary['total']} outlet."
        ]
        if top_problems:
            brief_parts.append(
                f"Prioritas pertama: {top_problems[0]['outlet_id']} — {top_problems[0]['root_cause']} ({top_problems[0]['aging']})."
            )
        worst_area = next((a for a in area_rows if a["critical"] or a["warning"]), None)
        if worst_area:
            brief_parts.append(
                f"Area paling perlu perhatian: {worst_area['area']} ({worst_area['critical']} critical, {worst_area['warning']} warning)."
            )
        if summary["stale"]:
            brief_parts.append(
                f"{summary['stale']} outlet masuk data hygiene/stale, dipisah dari critical live."
            )
        return {
            "error": None,
            "generated_at": now,
            "latest_version": latest_version,
            "summary": summary,
            "brief": " ".join(brief_parts),
            "top_problems": top_problems,
            "data_hygiene": data_hygiene,
            "areas": area_rows,
            "outlets": classified,
        }
    except Exception as e:
        return {
            "error": str(e),
            "summary": {},
            "top_problems": [],
            "data_hygiene": [],
            "areas": [],
        }


def _cc_level_html(level: str, score=None) -> str:
    color = {
        "critical": "#ef4444",
        "warning": "#f0c94a",
        "healthy": "#22c55e",
        "no_data": "#a1a1aa",
    }.get(level, "#a1a1aa")
    label = {
        "critical": "🔴 Critical",
        "warning": "🟡 Warning",
        "healthy": "🟢 Healthy",
        "no_data": "⚫ No Data",
    }.get(level, level)
    suffix = (
        f"<div style='font-weight:900;font-size:16px;margin-top:3px'>{score}</div>"
        if score is not None
        else ""
    )
    return f"<span style='display:inline-flex;padding:3px 8px;border-radius:999px;background:{color}26;border:1px solid {color}80;color:{color};font-weight:800;white-space:nowrap'>{label}</span>{suffix}"


def _cc_problem_cols():
    base = [
        ("Outlet", 220, 2),
        ("Health", 140, 1),
        ("Problem", 260, 3),
        ("Aging", 120, 1),
        ("Root Cause", 210, 2),
        ("Action", 260, 3),
        ("History", 100, 1),
    ]
    cols = []
    for name, minw, flex in base:
        c = {
            "headerName": name,
            "field": name,
            "minWidth": minw,
            "flex": flex,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
            "wrapText": True,
            "autoHeight": True,
        }
        if name == "Outlet":
            c["pinned"] = "left"
        if name == "Aging":
            c["cellStyle"] = {"textAlign": "right"}
        cols.append(c)
    return cols


def _cc_hygiene_cols():
    return [
        {
            "headerName": "Outlet",
            "field": "Outlet",
            "pinned": "left",
            "minWidth": 220,
            "flex": 2,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
        },
        {
            "headerName": "Area",
            "field": "Area",
            "minWidth": 120,
            "flex": 1,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
        },
        {
            "headerName": "Issue",
            "field": "Issue",
            "minWidth": 260,
            "flex": 3,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
            "wrapText": True,
            "autoHeight": True,
        },
        {
            "headerName": "Context",
            "field": "Context",
            "minWidth": 260,
            "flex": 3,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
        },
    ]


def _cc_table(rows, cols, html_cols=()):
    ui.aggrid(
        {
            "columnDefs": cols,
            "rowData": rows,
            "pagination": True,
            "paginationPageSize": 20,
            "paginationPageSizeSelector": [20, 50, 100],
            "domLayout": "autoHeight",
            "defaultColDef": {
                "resizable": True,
                "cellStyle": {"fontSize": "11px", "lineHeight": "1.25"},
            },
            "animateRows": True,
            "rowHeight": 42,
            "headerHeight": 36,
            "enableCellTextSelection": True,
        },
        theme="balham",
        html_columns=list(html_cols),
    ).classes("w-full ag-theme-balham-dark text-xs").style(
        "height:auto; min-height:220px; --ag-font-size:11px; --ag-row-height:42px; --ag-header-height:36px;"
    )


def _render_command_center_tab():
    data = _load_command_center_data()
    if data.get("error"):
        ui.label(f"Gagal load Command Center: {data['error']}").classes("text-red-400")
        return
    s = data.get("summary", {})
    ui.label("🎯 Command Center").classes("text-xl font-bold text-white")
    ui.label(
        "Native port dari flow 8090: owner/control-tower fokus exception sekarang, data hygiene dipisah dari critical live."
    ).classes("text-sm text-gray-400 mb-3")
    with ui.element("div").style(
        "background:linear-gradient(135deg,rgba(58,112,208,.22),rgba(30,30,46,.96)); border:1px solid rgba(138,180,255,.35); border-radius:16px; padding:16px;"
    ).classes("w-full mb-4"):
        ui.label("Ops Brief").classes("text-sm font-bold text-white")
        ui.label(data.get("brief") or "-").classes("text-sm text-gray-300")
        updated = (
            datetime.fromtimestamp((data.get("generated_at") or 0) / 1000).strftime(
                "%d/%m/%Y %H:%M:%S"
            )
            if data.get("generated_at")
            else "-"
        )
        ui.label(
            f"Updated: {updated} · Latest client: {data.get('latest_version') or '-'}"
        ).classes("text-xs text-gray-500 mt-1")
    with ui.row().classes("w-full gap-3 mb-4"):
        _kpi_card(
            "Total Outlet", _fmt(s.get("total", 0)), "master + monitor", "#cdd6f4"
        )
        _kpi_card("Healthy", _fmt(s.get("healthy", 0)), "normal", "#22c55e")
        _kpi_card("Warning", _fmt(s.get("warning", 0)), "perlu pantau", "#f0c94a")
        _kpi_card(
            "Current Critical", _fmt(s.get("critical", 0)), "action now", "#ef4444"
        )
        _kpi_card("No Data", _fmt(s.get("no_data", 0)), "belum report", "#a1a1aa")
        _kpi_card("Data Hygiene", _fmt(s.get("stale", 0)), "stale/mapping", "#94a3b8")
        _kpi_card(
            "SLA Breach", _fmt(s.get("sla_breached", 0)), "critical count", "#fb7185"
        )
        _kpi_card("Alerts 24h", _fmt(s.get("with_alerts", 0)), "ada alert", "#89b4fa")
    problem_rows = []
    for r in data.get("top_problems", []):
        issue_bits = [
            f"<div style='color:#ffd3d3'>{x}</div>" for x in r.get("issues", [])
        ] + [f"<div style='color:#fde68a'>{x}</div>" for x in r.get("warnings", [])]
        if not issue_bits:
            issue_bits = [
                f"<div style='color:#d4d4d8'>{x}</div>" for x in r.get("hygiene", [])
            ]
        hist = "http://gempor.my.id:8090/outlet-history?outlet_id=" + str(
            r.get("outlet_id", "")
        ).replace(" ", "%20")
        problem_rows.append(
            {
                "Outlet": f"<b>{r.get('outlet_id','-')}</b><div style='color:#9b9ba1'>{r.get('area','-')}</div>",
                "Health": _cc_level_html(r.get("level"), r.get("score")),
                "Problem": "".join(issue_bits)
                or "<span style='color:#9b9ba1'>-</span>",
                "Aging": f"<b>{r.get('aging','-')}</b><div style='color:#9b9ba1'>Shot: {r.get('screenshot_age','-')} · Printer: {r.get('printer_age','-')}</div>",
                "Root Cause": f"{r.get('root_cause','-')}<div style='color:#9b9ba1'>Printer: {r.get('printer_status','-')} · Modem: {r.get('modem_status','-')}</div>",
                "Action": r.get("action", "-"),
                "History": f"<a href='{hist}' target='_blank' style='text-decoration:none;color:#89b4fa;font-weight:700'>History</a>",
            }
        )
    with ui.element("div").style(CARD).classes("w-full mb-4"):
        ui.label("Top Current Problems").classes(MV)
        ui.label(
            "Hanya live/current issue; stale lama dipisah ke Data Hygiene."
        ).classes("text-xs text-gray-500 mb-2")
        if problem_rows:
            _cc_table(problem_rows, _cc_problem_cols(), html_cols=(0, 1, 2, 3, 4, 6))
        else:
            ui.label("Tidak ada current problem aktif.").classes(
                "text-xs text-gray-500 italic"
            )
    with ui.row().classes("w-full gap-4"):
        with ui.element("div").style(CARD).classes("flex-[2] min-w-[360px]"):
            ui.label("Data Hygiene / Stale").classes(MV)
            hygiene_rows = [
                {
                    "Outlet": r.get("outlet_id", "-"),
                    "Area": r.get("area", "-"),
                    "Issue": "<br>".join(r.get("hygiene", []) or ["-"]),
                    "Context": f"Shot {r.get('screenshot_age','-')} · Printer {r.get('printer_age','-')} · Modem {r.get('modem_age','-')} · Alerts {r.get('alert_count',0)}",
                }
                for r in data.get("data_hygiene", [])
            ]
            if hygiene_rows:
                _cc_table(hygiene_rows, _cc_hygiene_cols(), html_cols=(2,))
            else:
                ui.label("Tidak ada data hygiene issue.").classes(
                    "text-xs text-gray-500 italic"
                )
        with ui.element("div").style(CARD).classes("flex-1 min-w-[280px]"):
            ui.label("Area Health").classes(MV)
            for a in data.get("areas", [])[:18]:
                with ui.row().classes(
                    "w-full items-center justify-between gap-2 py-1 border-b border-gray-800"
                ):
                    with ui.column().classes("gap-0"):
                        ui.label(a.get("area") or "-").classes(
                            "text-sm font-semibold text-white"
                        )
                        ui.label(
                            f"🔴 {a.get('critical',0)} · 🟡 {a.get('warning',0)} · 🟢 {a.get('healthy',0)} · stale {a.get('stale',0)}"
                        ).classes("text-xs text-gray-500")
                    ui.label(str(a.get("avg_score", 0))).classes(
                        "text-lg font-bold text-white"
                    )


# ═══════════════════════════════════════════════
#  KPI CARD
# ═══════════════════════════════════════════════


def _kpi_card(label: str, value: str, sub: str = "", color: str = "#cdd6f4"):
    with ui.element("div").style(CARD).classes("flex-1 min-w-[160px]"):
        ui.label(label).classes(ML)
        ui.label(value).style(f"font-size: 1.8rem; font-weight: 700; color: {color};")
        if sub:
            ui.label(sub).classes("text-xs text-gray-500 mt-1")


# ═══════════════════════════════════════════════
#  TAB 1: DASHBOARD OPERASIONAL (summary.json — 4KB)
# ═══════════════════════════════════════════════


def _render_dashboard_tab(s: dict):
    if not s or not s.get("total"):
        ui.label("Belum ada data.").classes("text-gray-400 italic")
        return

    total = s["total"]
    statuses = s.get("statuses", {})
    open_count = sum(
        v
        for k, v in statuses.items()
        if k.lower() in ("open", "on the way", "reopen", "")
    )
    closed_count = statuses.get("Closed", 0)

    monthly = s.get("monthly", {})
    this_month = datetime.now().strftime("%Y-%m")
    last_month = (datetime.now().replace(day=1) - timedelta(days=15)).strftime("%Y-%m")
    this_month_count = monthly.get(this_month, 0)
    last_month_count = monthly.get(last_month, 0)

    with ui.row().classes("w-full gap-4 mb-6"):
        _kpi_card(
            "Total Problem", _fmt(total), f"{_fmt(closed_count)} closed", "#22c55e"
        )
        _kpi_card(
            "Bulan Ini",
            _fmt(this_month_count),
            f"{_fmt(last_month_count)} bulan lalu" if last_month_count else "",
            "#89b4fa",
        )
        _kpi_card("Open", _fmt(open_count), "belum selesai", "#ef4444")

    with ui.row().classes("w-full gap-4"):
        with ui.element("div").style(CARD).classes("flex-[3] min-w-[300px]"):
            ui.label("📊 Top Problem Types").classes(MV)
            tipeproblems = s.get("tipeproblems", {})
            max_val = max(tipeproblems.values()) if tipeproblems else 1
            for tipe, count in tipeproblems.items():
                pct = count / total * 100
                bar_w = max(count / max_val * 100, 5)
                icon = TIPE_ICONS.get(tipe, "🔧")
                with ui.row().classes("w-full items-center gap-2 py-1"):
                    ui.label(f"{icon}").classes("text-sm w-6")
                    ui.label(tipe).classes("text-xs text-gray-300 flex-1")
                    ui.label(_fmt(count)).classes(
                        "text-xs font-bold text-white w-14 text-right"
                    )
                    ui.element("div").style(
                        f"height: 16px; width: {bar_w:.0f}%; "
                        f"background: linear-gradient(90deg, #89b4fa, #b4befe); "
                        f"border-radius: 4px; min-width: 4px;"
                    ).classes("")
                    ui.label(f"{pct:.0f}%").classes("text-xs text-gray-500 w-10")

    open_problems = s.get("open_problems", [])
    open_list = [
        r for r in open_problems if str(r.get("status", "")).lower() != "uncompleted"
    ]
    onreview_list = [
        r for r in open_list if str(r.get("visit", "")).strip().lower() == "on review"
    ]
    open_list = [
        r for r in open_list if str(r.get("visit", "")).strip().lower() != "on review"
    ]

    def _pb_rows(rec):
        return {
            "Outlet": _outlet_label(rec),
            "Problem": f'<a href="{_ERP_URL}/app/problem-booth/{rec["name"]}" target="_blank" style="text-decoration:none;color:#cdd6f4;font-weight:600;">{rec["name"]} · {rec.get("tipeproblem", "")}</a>',
            "Tgl": _fmt_date(rec.get("creation", "")),
        }

    _pb_cols = [
        {
            "headerName": "Outlet",
            "field": "Outlet",
            "pinned": "left",
            "minWidth": 200,
            "flex": 3,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
        },
        {
            "headerName": "Problem",
            "field": "Problem",
            "minWidth": 180,
            "flex": 2,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
        },
        {
            "headerName": "Tgl",
            "field": "Tgl",
            "minWidth": 110,
            "flex": 1,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": True,
            "cellStyle": {"textAlign": "right"},
            ":comparator": "(a,b)=>{const M={Jan:'01',Feb:'02',Mar:'03',Apr:'04',Mei:'05',Jun:'06',Jul:'07',Agu:'08',Sep:'09',Okt:'10',Nov:'11',Des:'12'};const p=v=>{if(!v)return 0;const x=String(v).split(' ');return x.length===3?Number(x[2]+M[x[1]]+x[0].padStart(2,'0')):0};return p(a)-p(b)}",
        },
    ]

    def _pb_table(rows):
        ui.aggrid(
            {
                "columnDefs": _pb_cols,
                "rowData": rows,
                "pagination": True,
                "paginationPageSize": 20,
                "paginationPageSizeSelector": [20, 50, 100],
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True},
                "animateRows": True,
                "rowHeight": 40,
                "headerHeight": 40,
                "enableCellTextSelection": True,
            },
            theme="balham",
            html_columns=[1],
        ).classes("w-full ag-theme-balham-dark").style(
            "height: auto; min-height: 200px;"
        )

    with ui.row().classes("w-full gap-4 mt-4"):
        with ui.element("div").style(CARD).classes("w-full"):
            ui.label("Problem Booth Open").classes(MV)
            if open_list:
                _pb_table([_pb_rows(r) for r in open_list])
            else:
                ui.label("Tidak ada problem open.").classes(
                    "text-xs text-gray-500 italic"
                )

    with ui.row().classes("w-full gap-4 mt-4"):
        with ui.element("div").style(CARD).classes("w-full"):
            ui.label("Problem Booth On Review").classes(MV)
            if onreview_list:
                _pb_table([_pb_rows(r) for r in onreview_list])
            else:
                ui.label("Tidak ada problem on review.").classes(
                    "text-xs text-gray-500 italic"
                )

    with ui.row().classes("w-full gap-4 mt-4"):
        for title, key, grad in [
            ("🏙️ Per Branch", "branches", "linear-gradient(90deg, #a6e3a1, #74c7ec)"),
            ("🏢 Per Pemilik", "pemiliks", "linear-gradient(90deg, #fab387, #f38ba8)"),
            (
                "🔧 Per Maintenance PIC",
                "maintenances",
                "linear-gradient(90deg, #cba6f7, #f5c2e7)",
            ),
        ]:
            data = s.get(key, {})
            with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
                ui.label(title).classes(MV)
                for name, count in list(data.items())[:7]:
                    bar_w = max(count / total * 100, 3)
                    with ui.row().classes("w-full items-center gap-2 py-0.5"):
                        ui.label(name if name else "(empty)").classes(
                            "text-xs text-gray-300 flex-1"
                        )
                        ui.label(_fmt(count)).classes(
                            "text-xs font-bold text-white w-14 text-right"
                        )
                        ui.element("div").style(
                            f"height: 12px; width: {bar_w:.0f}%; "
                            f"background: {grad}; border-radius: 4px;"
                        ).classes("")


# ═══════════════════════════════════════════════
#  TAB 2: FULL DATA — PER BULAN (monthly.json — 42KB)
# ═══════════════════════════════════════════════


def _render_monthly_tab(m: dict):
    if not m or "months" not in m:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return

    months_data = m.get("months", {})
    m.get("meta", {}).get("top_tipes", [])
    sorted_months = sorted(months_data.keys(), reverse=True)
    selected_staff = {"email": None}
    selected_problem = {"name": None}
    current_month = {"key": None}

    # Month labels
    _month_labels = [_month_name(mk) for mk in sorted_months]

    # Handler for month change
    def _on_month_change():
        val = month_sel.value
        for mk in sorted_months:
            if _month_name(mk) == val:
                _build_month_detail(mk)
                break

    # Month selector — MUST be first (before containers, controls DOM order)
    month_sel = (
        ui.select(
            _month_labels,
            value=_month_labels[0] if _month_labels else None,
            label="Pilih bulan...",
            on_change=_on_month_change,
        )
        .props("outlined dark")
        .classes("w-56 mb-4")
    )

    # Container for month detail view
    detail_container = ui.column().classes("w-full")
    # Container for table

    def show_staff_problems(rec):
        selected_staff["email"] = rec["email"]
        selected_problem["name"] = None
        detail_container.clear()
        with detail_container:
            # Back button
            with ui.row().classes("w-full items-center gap-2 mb-4"):
                ui.button(
                    "← Kembali ke ringkasan",
                    on_click=lambda: _rebuild_month(current_month["key"]),
                ).props("flat dense").classes("text-xs")
            # Header
            ui.label(
                f"⏰ Detail Problem — {rec.get('name', rec.get('email', '?'))}"
            ).style(MV)
            problems = rec.get("problems", [])
            ui.label(
                f"{len(problems)} problem dengan rata-rata delay {rec.get('avg_min', 0):.0f} menit"
            ).classes("text-xs text-gray-400 mb-4")
            # Problem list
            for prob in problems:
                delay = prob.get("delay_min", 0)
                color = (
                    "#ef4444" if delay > 180 else "#f59e0b" if delay > 60 else "#22c55e"
                )
                with ui.row().classes(
                    "w-full items-center gap-2 py-2 border-b border-gray-800 hover:bg-gray-800/30 cursor-pointer"
                ).on("click", lambda p=prob: show_problem_detail(p, rec)):
                    ui.label(prob.get("name", "?")).classes(
                        "text-xs font-bold text-gray-300 w-28"
                    )
                    ui.label(prob.get("subject", "?")).classes(
                        "text-xs text-white flex-1"
                    )
                    ui.label(prob.get("tipeproblem", "")).classes(
                        "text-xs text-gray-400"
                    )
                    ui.label(f"{delay:.0f} menit").style(
                        f"color: {color}; font-size: 0.75rem; font-weight: 600;"
                    )
                    sc = STATUS_COLORS.get(prob.get("status", ""), "#cdd6f4")
                    ui.element("div").style(
                        f"background: {sc}; padding: 1px 8px; border-radius: 6px;"
                    )
                    with ui.element("div").style(
                        f"color: {sc}; font-size: 0.75rem; font-weight: 600;"
                    ):
                        ui.label(prob.get("status", ""))

    def show_problem_detail(prob, staff_rec):
        selected_problem["name"] = prob["name"]
        detail_container.clear()
        erp_link = f"{_ERP_URL}/app/problem-booth/{prob['name']}"
        with detail_container:
            with ui.row().classes("w-full items-center gap-2 mb-4"):
                ui.button(
                    "← Kembali", on_click=lambda: show_staff_problems(staff_rec)
                ).props("flat dense").classes("text-xs")
            with ui.element("div").style(CARD).classes("w-full mb-4"):
                ui.label(f"📋 {prob.get('name', '?')}").style(MV)
                delay = prob.get("delay_min", 0)
                color = (
                    "#ef4444" if delay > 180 else "#f59e0b" if delay > 60 else "#22c55e"
                )
                with ui.row().classes("w-full gap-4"):
                    with ui.column().classes("flex-1"):
                        _detail_row("Outlet", prob.get("subject", "?"))
                        _detail_row("Tipe Problem", prob.get("tipeproblem", ""))
                        _detail_row("Status", prob.get("status", ""))
                        _detail_row("Request Visit", prob.get("visit_set_time", ""))
                        _detail_row("Shift Request", prob.get("shift_name_req", ""))
                    with ui.column().classes("flex-1"):
                        _detail_row("Ambil Tugas", prob.get("pengambilan_tugas", ""))
                        _detail_row("Shift Ambil", prob.get("shift_name_ambil", ""))
                        _detail_row("On The Way", prob.get("ontheway_time", ""))
                        _detail_row("Sampai Lokasi", prob.get("time_sampai_lokasi", ""))
                        _detail_row("Delay", f"{delay:.0f} menit", color)
                ui.separator().classes("my-3")
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label("🔗 ").classes("text-sm")
                    with ui.element("a").props(
                        f'href="{erp_link}" target="_blank"'
                    ).classes("text-blue-400 hover:text-blue-300 underline text-sm"):
                        ui.label("Buka di ERPNext →")

    def _detail_row(label, value, color=None):
        with ui.row().classes("w-full items-center gap-2"):
            ui.label(label).classes("text-xs text-gray-500 w-28")
            val = ui.label(value).classes("text-xs text-white font-semibold")
            if color:
                val.style(f"color: {color}")

    def _rebuild_month(mk):
        detail_container.clear()
        _build_month_detail(mk)

    # Build month detail
    def _build_month_detail(month_key):
        detail_container.clear()
        current_month["key"] = month_key
        if not month_key or month_key not in months_data:
            with detail_container:
                ui.label("Pilih bulan untuk melihat detail.").classes(
                    "text-gray-500 italic"
                )
            return

        data = months_data[month_key]
        s = load_summary()

        with detail_container:
            # KPI CARDS
            with ui.row().classes("w-full gap-3 mb-4"):
                _kpi_card(
                    "\U0001f4ca Total Problem",
                    _fmt(data["total"]),
                    f"{data['booth_count']} booth terdampak",
                    "#89b4fa",
                )
                _kpi_card(
                    "\U0001f7e0 Open", _fmt(data["open"]), "belum selesai", "#ef4444"
                )
                _kpi_card("\u2705 Closed", _fmt(data["closed"]), "", "#22c55e")

            # 2-COLUMN GRID: Types + Branches
            with ui.element("div").classes("w-full mb-4").style(
                "display: grid; gap: 16px; grid-template-columns: repeat(2, 1fr);"
            ):
                # Problem Types
                with ui.element("div").style(CARD):
                    ui.label("\U0001f527 Problem Types").style(MV)
                    tipe_data = data.get("tipe", {})
                    sorted_tipes = sorted(
                        tipe_data.items(), key=lambda x: x[1], reverse=True
                    )
                    for tipe, count in sorted_tipes[:10]:
                        pct = count / data["total"] * 100 if data["total"] else 0
                        icon = TIPE_ICONS.get(tipe, "\U0001f527")
                        with ui.row().classes("w-full items-center gap-2 py-0.5"):
                            ui.label(f"{icon}").classes("text-sm w-6")
                            ui.label(tipe).classes("text-xs text-gray-300 flex-1")
                            ui.label(_fmt(count)).classes(
                                "text-xs font-bold text-white w-12 text-right"
                            )
                            ui.label(f"{pct:.0f}%").classes(
                                "text-xs text-gray-500 w-10"
                            )

            # PROBLEMS LAST 24 HOURS — from summary.recent_24h
            recent_24h = s.get("recent_24h", [])
            if recent_24h:
                with ui.element("div").style(CARD).classes("w-full mb-4"):
                    ui.label(
                        f"🔥 Problem 24 Jam Terakhir — {len(recent_24h)} problem"
                    ).style(MV)
                    for rec in recent_24h:
                        nama = _outlet_label(rec)
                        tipe = rec.get("tipeproblem", "")
                        st = rec.get("status", "")
                        sc = STATUS_COLORS.get(st, "#cdd6f4")
                        created = rec.get("creation", "")[:16]
                        with ui.row().classes(
                            "w-full items-center gap-2 py-1 border-b border-gray-800 last:border-b-0"
                        ):
                            ui.label(f"{TIPE_ICONS.get(tipe, '🔧')}").classes("text-sm")
                            ui.label(f"{nama}").classes(
                                "text-xs font-semibold text-white flex-1"
                            )
                            ui.label(tipe).classes("text-xs text-gray-400")
                            ui.label(created).classes("text-xs text-gray-500")
                            ui.element("div").style(
                                f"background: {sc}; padding: 1px 8px; border-radius: 6px;"
                            )
                            with ui.element("div").style(
                                f"color: {sc}; font-size: 0.75rem; font-weight: 600;"
                            ):
                                ui.label(st)

            # TOP PROBLEMATIC OUTLETS
            top_outlets = data.get("top_outlets", [])
            if top_outlets:
                with ui.element("div").style(CARD).classes("w-full mb-4"):
                    ui.label("\U0001f534 Top Outlet Paling Bermasalah").style(MV)
                    ui.label("Outlet dengan problem terbanyak di bulan ini.").classes(
                        "text-xs text-gray-400 mb-3"
                    )
                    with ui.row().classes(
                        "w-full items-center gap-2 py-1 border-b border-gray-700 mb-1"
                    ):
                        ui.label("#").classes("text-xs text-gray-500 w-6")
                        ui.label("Outlet").classes("text-xs text-gray-500 flex-1")
                        ui.label("Total").classes(
                            "text-xs text-gray-500 w-14 text-right"
                        )
                        ui.label("Top Problem Types").classes("text-xs text-gray-500")
                    for rank, rec in enumerate(top_outlets[:10], 1):
                        total = rec["total"]
                        top_tipes = rec.get("top_tipes", {})
                        tipe_str = ", ".join(
                            f"{tipe} ({c})" for tipe, c in list(top_tipes.items())[:3]
                        )
                        with ui.row().classes(
                            "w-full items-center gap-2 py-1 border-b border-gray-800 last:border-b-0"
                        ):
                            ui.label(f"{rank}.").classes(
                                "text-xs font-bold text-gray-400 w-6"
                            )
                            ui.label(rec["name"]).classes(
                                "text-xs font-semibold text-white flex-1"
                            )
                            ui.label(_fmt(total)).classes(
                                "text-xs font-bold text-white w-12 text-right"
                            )
                            ui.label(tipe_str).classes("text-xs text-gray-300")

            # PETUGAS PALING AKTIF
            pics = data.get("top_petugas", {})
            if pics:
                sorted_pics = sorted(pics.items(), key=lambda x: x[1], reverse=True)
                with ui.element("div").style(CARD).classes("w-full mb-4"):
                    ui.label("🔧 Petugas Paling Aktif").style(MV)
                    ui.label(
                        "Teknisi dengan penanganan problem terbanyak di bulan ini."
                    ).classes("text-xs text-gray-400 mb-3")
                    with ui.row().classes(
                        "w-full items-center gap-2 py-1 border-b border-gray-700 mb-1"
                    ):
                        ui.label("#").classes("text-xs text-gray-500 w-6")
                        ui.label("Petugas").classes("text-xs text-gray-500 flex-1")
                        ui.label("Total").classes(
                            "text-xs text-gray-500 w-24 text-right"
                        )
                    for rank, (name, count) in enumerate(sorted_pics, 1):
                        pct = count / data["total"] * 100 if data["total"] else 0
                        with ui.row().classes(
                            "w-full items-center gap-2 py-1 border-b border-gray-800 last:border-b-0"
                        ):
                            ui.label(f"{rank}.").classes(
                                "text-xs font-bold text-gray-400 w-6"
                            )
                            ui.label(name).classes(
                                "text-xs font-semibold text-white flex-1"
                            )
                            ui.label(_fmt(count)).classes(
                                "text-xs font-bold text-white w-12 text-right"
                            )
                            ui.label(f"{pct:.0f}%").classes(
                                "text-xs text-gray-500 w-10"
                            )

            # STAFF DELAYS
            staff_delays = data.get("staff_delays", [])
            if staff_delays:
                with ui.element("div").style(CARD).classes("w-full mb-4"):
                    ui.label("⏰ Staf Suka Pending").style(MV)
                    ui.label(
                        "Rata-rata delay dari Request Visit ke Pengambilan Tugas."
                    ).classes("text-xs text-gray-400 mb-3")
                    with ui.row().classes(
                        "w-full items-center gap-2 py-1 border-b border-gray-700 mb-1"
                    ):
                        ui.label("#").classes("text-xs text-gray-500 w-6")
                        ui.label("Staf").classes("text-xs text-gray-500 flex-1")
                        ui.label("Problem").classes(
                            "text-xs text-gray-500 w-16 text-right"
                        )
                        ui.label("Rata2").classes(
                            "text-xs text-gray-500 w-16 text-right"
                        )
                        ui.label("Max").classes("text-xs text-gray-500 w-16 text-right")
                    for rank, rec in enumerate(staff_delays[:15], 1):
                        avg = rec.get("avg_min", 0)
                        max_d = rec.get("max_min", 0)
                        color = (
                            "#ef4444"
                            if avg > 180
                            else "#f59e0b" if avg > 60 else "#22c55e"
                        )
                        staff_name = rec.get("name") or rec.get("email", "?")
                        with ui.row().classes(
                            "w-full items-center gap-2 py-1 border-b border-gray-800 last:border-b-0"
                        ):
                            ui.label(f"{rank}.").classes(
                                "text-xs font-bold text-gray-400 w-6"
                            )
                            ui.link(staff_name, "#").props("no-caps").classes(
                                "text-xs font-semibold text-blue-400 flex-1"
                            ).on("click", lambda e, r=rec: show_staff_problems(r))
                            ui.label(str(rec.get("count", 0))).classes(
                                "text-xs text-gray-400 w-16 text-right"
                            )
                            ui.label(f"{avg:.0f} menit").style(
                                f"color: {color}; font-size: 0.75rem; font-weight: 600; width: 70px; text-align: right;"
                            )
                            ui.label(f"{max_d:.0f} menit").classes(
                                "text-xs text-gray-500 w-16 text-right"
                            )

    # Show first month by default
    first_month = sorted_months[0] if sorted_months else None
    if first_month:
        _build_month_detail(first_month)


#  TAB 3: DETAIL RECORD
# ═══════════════════════════════════════════════


def _render_detail_tab(parent):
    with parent:
        ui.label("🔍 Cari ID Problem Booth").classes(MV)
        ui.label("Ketik ID (misal PB-23065) untuk lihat detail lengkap.").classes(
            "text-xs text-gray-400 mb-4"
        )

        search_input = (
            ui.input("🔍 Cari ID (PB-xxxxx)")
            .props("dense outlined dark")
            .classes("w-80")
        )
        detail_container = ui.column().classes("w-full mt-4")

        def _search():
            q = search_input.value.strip().upper()
            if not q:
                return
            detail_container.clear()
            with detail_container:
                ui.label("⏳ Loading...").classes("text-gray-400 italic")
                ui.timer(0.1, lambda: _load_detail(q), once=True)

        def _load_detail(q):
            detail_container.clear()
            df = load_light_cache()
            if df.empty or "name" not in df.columns:
                with detail_container:
                    ui.label("Data tidak tersedia.").classes("text-gray-400 italic")
                return

            # Try exact match or partial
            match = df[df["name"].str.upper().str.contains(q, na=False)]
            if len(match) == 0:
                with detail_container:
                    ui.label(f"ID '{q}' tidak ditemukan.").classes(
                        "text-gray-400 italic"
                    )
                return

            with detail_container:
                for _, rec in match.head(5).iterrows():
                    name = rec.get("name", "?")
                    outlet = _outlet_label(rec.to_dict())
                    with ui.element("div").style(CARD).classes("w-full mb-4"):
                        with ui.row().classes("w-full items-center gap-4 mb-4"):
                            ui.label(f"🔧 {outlet}").classes(MV)
                            st = str(rec.get("status", "") or "")
                            sc = STATUS_COLORS.get(st, "#cdd6f4")
                            ui.element("div").style(
                                f"background: {sc}; padding: 2px 12px; border-radius: 8px;"
                            ).classes("")
                            with ui.element("div").style(
                                f"color: {sc}; font-weight: 600; font-size: 0.85rem;"
                            ):
                                ui.label(st)
                            if _ERP_URL:
                                ui.link(
                                    "🔗 Buka di ERPNext",
                                    f"{_ERP_URL}/app/problem-booth/{name}",
                                    new_tab=True,
                                ).classes("text-sm text-blue-400 ml-auto")

                        fields = [
                            ("subject", "📍 Nama Outlet"),
                            ("nama_tempat", "🔢 Kode Mesin"),
                            ("branch", "🏙️ Branch"),
                            ("tipeproblem", "🔧 Tipe"),
                            ("maintenance", "🔧 PIC"),
                            ("pemilik", "🏢 Pemilik"),
                            ("visit", "🚗 Visit"),
                            ("device_error", "⚠️ Device Error"),
                            ("tanggal_foto", "📅 Tanggal"),
                            ("pbsolving", "💡 Solusi"),
                        ]
                        for f, lbl in fields:
                            v = rec.get(f)
                            if f == "visit":
                                v = "✅ Ya" if v == 1 else "❌ Tidak"
                            elif f == "device_error":
                                v = "⚠️ Ya" if v == 1 else "✅ Tidak"
                            else:
                                v = _strip_html(str(v or "—"))[:200]
                            ui.label(f"{lbl}: {v}").classes(
                                "text-xs text-gray-300 py-1 border-b border-gray-800"
                            )

                        desc = str(rec.get("description_problem", "") or "")
                        if desc:
                            clean = _strip_html(desc)
                            if clean:
                                ui.label("📝 Deskripsi:").classes(
                                    "text-xs font-semibold text-white mt-2 mb-1"
                                )
                                ui.label(clean[:300]).classes("text-xs text-gray-300")

        search_input.on("keydown.enter", _search)
        ui.button("🔍 Cari", on_click=_search).props("dense flat").classes("mt-2")


# ═══════════════════════════════════════════════
#  TAB 4: STATISTIK
# ═══════════════════════════════════════════════


def _render_stat_tab(s: dict):
    if not s:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return

    with ui.row().classes("w-full gap-4"):
        with ui.element("div").style(CARD).classes("flex-1 min-w-[300px]"):
            ui.label("📈 Problem per Bulan").classes(MV)
            monthly = s.get("monthly", {})
            max_m = max(monthly.values()) if monthly else 1
            for period, count in list(monthly.items())[-24:]:
                bar_w = max(count / max_m * 100, 5)
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(_month_name(period)).classes(
                        "text-xs text-gray-300 flex-1"
                    )
                    ui.label(_fmt(count)).classes(
                        "text-xs font-bold text-white w-14 text-right"
                    )
                    ui.element("div").style(
                        f"height: 16px; width: {bar_w:.0f}%; "
                        f"background: linear-gradient(90deg, #94e2d5, #89dceb); "
                        f"border-radius: 4px;"
                    ).classes("")

        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("✅ Status Distribution").classes(MV)
            statuses = s.get("statuses", {})
            total = s.get("total", 1)
            for st, count in statuses.items():
                sc = STATUS_COLORS.get(st, "#cdd6f4")
                pct = count / total * 100
                bar_w = max(pct, 3)
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(st).classes("text-xs flex-1").style(f"color: {sc}")
                    ui.label(_fmt(count)).classes(
                        "text-xs font-bold text-white w-14 text-right"
                    )
                    ui.element("div").style(
                        f"height: 14px; width: {bar_w:.0f}%; "
                        f"background: {sc}; border-radius: 4px;"
                    ).classes("")
                    ui.label(f"{pct:.1f}%").classes("text-xs text-gray-500 w-12")


# ═══════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════

SYNC_SCRIPT = "/var/www/difotoin-dashboard/scripts/sync_problem_booth.py"
SYNC_KPI_SCRIPT = "/var/www/difotoin-dashboard/scripts/sync_kpi_sistem.py"
SYNC_VENV = "/var/www/difotoin-dashboard/nicegui_template/.venv/bin/python3"


def _sync_and_reload(container, tabs, panels):
    """Run sync script, then rebuild page."""
    ui.notify(
        "⏳ Sync data dari ERPNext... (2-3 menit)", type="info", close_button=False
    )

    import subprocess
    import threading

    def _run_sync():
        try:
            # Sync Problem Booth
            result = subprocess.run(
                [SYNC_VENV, SYNC_SCRIPT],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                ui.notify("✅ Problem Booth sync OK", type="positive")
            else:
                ui.notify(f"⚠️ PB sync: {result.stderr[-100:]}", type="warning")

            # Sync KPI Sistem
            ui.notify("⏳ Sync KPI Sistem...", type="info", close_button=False)
            result2 = subprocess.run(
                [SYNC_VENV, SYNC_KPI_SCRIPT],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result2.returncode == 0:
                ui.notify("✅ KPI Sistem sync OK", type="positive")
            else:
                ui.notify(f"⚠️ KPI sync: {result2.stderr[-100:]}", type="warning")

        except subprocess.TimeoutExpired:
            ui.notify("❌ Sync timeout", type="negative")
        except Exception as e:
            ui.notify(f"❌ Error: {e}", type="negative")
        # Rebuild page
        container.clear()
        create_page(container)

    threading.Thread(target=_run_sync, daemon=True).start()


def create_page(container: ui.column):
    container.clear()
    s = load_summary()
    total = s.get("total", 0)

    with container:
        ui.label("🔧 Problem Booth").classes("text-2xl font-bold text-white")
        ui.label(
            "Dashboard operasional monitoring problem booth & maintenance — untuk Dino / Head."
        ).classes("text-sm text-gray-400 mb-4")

        if total == 0:
            ui.label("Belum ada data. Sync data dari ERPNext terlebih dahulu.").classes(
                "text-gray-400 italic"
            )
            if s.get("last_sync"):
                ui.label(f"Terakhir sync: {s['last_sync'][:16]}").classes(
                    "text-xs text-gray-500"
                )
            with ui.row().classes("mt-4"):
                ui.button(
                    "📥 Sync dari ERPNext",
                    on_click=lambda: _sync_and_reload(container, None, None),
                ).props("dense flat text-white bg-green-700")
            return

        # Header row: sync info + fetch button
        sync_str = "-"
        if s.get("last_sync"):
            try:
                sync_dt = datetime.fromisoformat(s["last_sync"])
                sync_str = sync_dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                sync_str = s["last_sync"][:16]
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label(f"💾 {_fmt(total)} problem | sync: {sync_str}").classes(
                "text-xs text-gray-500"
            )
            ui.button(
                "📥 Sync dari ERPNext",
                on_click=lambda: _sync_and_reload(container, None, None),
            ).props("dense flat text-white bg-green-700")

        # AG Grid dark theme CSS
        ui.add_head_html(
            "<style>.ag-theme-balham-dark{"
            "--ag-background-color:#1e1e2e;--ag-header-background-color:#181825;"
            "--ag-odd-row-background-color:#1a1a2e;--ag-row-hover-color:#313244;"
            "--ag-border-color:#313244;--ag-font-size:13px;"
            "--ag-header-height:42px;--ag-row-height:38px;"
            "--ag-selected-row-background-color:#2a2a4e;}</style>"
        )

        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="dash").classes("w-full")
        with tabs:
            ui.tab("dash", label="📊 Dashboard")
            ui.tab("monthly", label="📋 Data Per Bulan")
            ui.tab("detail", label="🔍 Cari ID")
            ui.tab("stats", label="📈 Statistik")
            ui.tab("monitor8090", label="🚨 8090 → PB")
            ui.tab("command_center", label="🎯 Command Center")
            ui.tab("kpi", label="📊 KPI Sistem")

        with panels:
            with ui.tab_panel("dash"):
                _render_dashboard_tab(s)
            with ui.tab_panel("monthly"):
                _render_monthly_tab(load_monthly())
            with ui.tab_panel("detail"):
                _render_detail_tab(ui.column().classes("w-full"))
            with ui.tab_panel("stats"):
                _render_stat_tab(s)
            with ui.tab_panel("monitor8090"):
                _render_8090_pb_tab()
            with ui.tab_panel("command_center"):
                _render_command_center_tab()
            with ui.tab_panel("kpi"):
                kpi_sistem.create_page(ui.column().classes("w-full"))

        # ── Auto-sync: trigger background sync setelah halaman selesai render ──
        ui.timer(3.0, lambda: _sync_and_reload(container, None, None), once=True)
