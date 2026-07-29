"""
🔧 Problem Booth — operational dashboard for booth problems.
Data from ERPNext. All data pre-computed: summary (4KB), monthly (42KB), light cache (7MB lazy).
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from nicegui import ui

from pages import kpi_sistem

# ── Paths ──
SUMMARY_PATH = Path("/var/www/difotoin-dashboard/problem_booth_summary.json")
MONTHLY_PATH = Path("/var/www/difotoin-dashboard/problem_booth_monthly.json")
LIGHT_CACHE_PATH = Path("/var/www/difotoin-dashboard/problem_booth_cache_light.json")
CONFIG_PATH = Path("/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json")

# ── ERPNext URL ──
_ERP_URL = ""
try:
    with open(CONFIG_PATH) as _f:
        _ERP_URL = json.load(_f).get("url", "").rstrip("/")
except Exception:
    pass

# ── Colors ──
STATUS_COLORS = {
    "Closed": "#22c55e", "Open": "#ef4444", "Uncompleted": "#f59e0b",
    "On The Way": "#3b82f6", "Reopen": "#ef4444",
}
TIPE_COLORS = [
    "#f43f5e", "#fb923c", "#fbbf24", "#a3e635", "#34d399",
    "#2dd4bf", "#22d3ee", "#60a5fa", "#818cf8", "#a78bfa",
    "#c084fc", "#e879f9",
]
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"

TIPE_ICONS = {
    "Overheat": "🔥", "Listrik Mati": "⚡", "Camera": "📷", "Printer": "🖨️",
    "Remote Connection Issue": "🌐", "Flash": "💡", "Booth": "🏠", "Bug": "🐛",
    "Ganti Kertas": "📄", "Print Manual": "🖨️", "PC": "💻", "Hardware Error": "🔧",
    "Button": "🔘", "Sticker": "🏷️", "Monitor": "🖥️", "Internet": "🌐",
    "Camera Setting": "📷", "Anydesk": "🌐", "Hardware": "🔧", "Others": "📌",
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
    # Remove all HTML tags
    clean = re.sub(r"<[^>]+>", " ", str(text))
    # Normalize whitespace and entities
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    clean = " ".join(clean.split())
    return clean.strip()


def _month_name(m: str) -> str:
    """2026-07 → Jul 2026"""
    try:
        dt = datetime.strptime(m, "%Y-%m")
        months_en = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{months_en[dt.month]} {dt.year}"
    except Exception:
        return m


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
    open_count = sum(v for k, v in statuses.items() if k.lower() in ("open", "on the way", "reopen", ""))
    closed_count = statuses.get("Closed", 0)
    uncompleted_count = statuses.get("Uncompleted", 0)

    monthly = s.get("monthly", {})
    this_month = datetime.now().strftime("%Y-%m")
    last_month = (datetime.now().replace(day=1) - timedelta(days=15)).strftime("%Y-%m")
    this_month_count = monthly.get(this_month, 0)
    last_month_count = monthly.get(last_month, 0)

    with ui.row().classes("w-full gap-4 mb-6"):
        _kpi_card("Total Problem", _fmt(total), f"{_fmt(closed_count)} closed", "#22c55e")
        _kpi_card("Bulan Ini", _fmt(this_month_count),
                  f"{_fmt(last_month_count)} bulan lalu" if last_month_count else "", "#89b4fa")
        _kpi_card("Open", _fmt(open_count), "belum selesai", "#ef4444")
        _kpi_card("Uncompleted", _fmt(uncompleted_count), "perlu follow-up", "#f59e0b")

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
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
                    ui.element("div").style(
                        f"height: 16px; width: {bar_w:.0f}%; "
                        f"background: linear-gradient(90deg, #89b4fa, #b4befe); "
                        f"border-radius: 4px; min-width: 4px;"
                    ).classes("")
                    ui.label(f"{pct:.0f}%").classes("text-xs text-gray-500 w-10")

        with ui.element("div").style(CARD).classes("flex-[2] min-w-[250px]"):
            ui.label("🟢 Open / Uncompleted").classes(MV)
            open_problems = s.get("open_problems", [])
            if open_problems:
                for rec in open_problems:
                    nama = _outlet_label(rec)
                    tipe = rec.get("tipeproblem", "")
                    badge = "🟢" if rec.get("status") == "Open" else "🟡"
                    with ui.row().classes("w-full items-start gap-2 py-1 border-b border-gray-800 last:border-b-0"):
                        ui.label(f"{badge}").classes("text-sm mt-0.5")
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(f"{nama} — {tipe}").classes("text-xs font-semibold text-white")
                            if rec.get("description"):
                                ui.label(_strip_html(rec["description"])[:80]).classes("text-xs text-gray-400 truncate")
            else:
                ui.label("Tidak ada problem open.").classes("text-xs text-gray-500 italic")

    with ui.row().classes("w-full gap-4 mt-4"):
        for title, key, grad in [
            ("🏙️ Per Branch", "branches", "linear-gradient(90deg, #a6e3a1, #74c7ec)"),
            ("🏢 Per Pemilik", "pemiliks", "linear-gradient(90deg, #fab387, #f38ba8)"),
            ("🔧 Per Maintenance PIC", "maintenances", "linear-gradient(90deg, #cba6f7, #f5c2e7)"),
        ]:
            data = s.get(key, {})
            with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
                ui.label(title).classes(MV)
                for name, count in list(data.items())[:7]:
                    bar_w = max(count / total * 100, 3)
                    with ui.row().classes("w-full items-center gap-2 py-0.5"):
                        ui.label(name if name else "(empty)").classes("text-xs text-gray-300 flex-1")
                        ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
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
    top_tipes = m.get("meta", {}).get("top_tipes", [])
    sorted_months = sorted(months_data.keys(), reverse=True)

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
    month_sel = ui.select(_month_labels,
                          value=_month_labels[0] if _month_labels else None,
                          label="Pilih bulan...",
                          on_change=_on_month_change).props(
        "outlined dark").classes("w-56 mb-4")

    # Container for month detail view
    detail_container = ui.column().classes("w-full")
    # Container for table
    table_container = ui.column().classes("w-full")

    # Build month detail
    def _build_month_detail(month_key):
        detail_container.clear()
        if not month_key or month_key not in months_data:
            with detail_container:
                ui.label("Pilih bulan untuk melihat detail.").classes("text-gray-500 italic")
            return

        data = months_data[month_key]

        with detail_container:
            # KPI CARDS
            with ui.row().classes("w-full gap-3 mb-4"):
                _kpi_card("\U0001f4ca Total Problem", _fmt(data["total"]), f"{data['booth_count']} booth terdampak", "#89b4fa")
                _kpi_card("\U0001f7e0 Open", _fmt(data["open"]), "belum selesai", "#ef4444")
                _kpi_card("\u2705 Closed", _fmt(data["closed"]), "", "#22c55e")
                _kpi_card("\U0001f7e1 Uncompleted", _fmt(data["uncompleted"]), "perlu follow-up", "#f59e0b")

            # 2-COLUMN GRID: Types + Branches
            with ui.element("div").classes("w-full mb-4").style(
                "display: grid; gap: 16px; grid-template-columns: repeat(2, 1fr);"
            ):
                # Problem Types
                with ui.element("div").style(CARD):
                    ui.label("\U0001f527 Problem Types").style(MV)
                    tipe_data = data.get("tipe", {})
                    sorted_tipes = sorted(tipe_data.items(), key=lambda x: x[1], reverse=True)
                    max_tipe = max((v for _, v in sorted_tipes), default=1)
                    for tipe, count in sorted_tipes[:10]:
                        pct = count / data["total"] * 100 if data["total"] else 0
                        bar_w = max(count / max_tipe * 100, 3)
                        icon = TIPE_ICONS.get(tipe, "\U0001f527")
                        with ui.row().classes("w-full items-center gap-2 py-0.5"):
                            ui.label(f"{icon}").classes("text-sm w-6")
                            ui.label(tipe).classes("text-xs text-gray-300 flex-1")
                            ui.label(_fmt(count)).classes("text-xs font-bold text-white w-12 text-right")
                            ui.element("div").style(
                                f"height: 14px; width: {bar_w:.0f}%; "
                                f"background: linear-gradient(90deg, #89b4fa, #b4befe); "
                                f"border-radius: 4px; min-width: 3px;"
                            )
                            ui.label(f"{pct:.0f}%").classes("text-xs text-gray-500 w-10")

                # Branch Distribution
                with ui.element("div").style(CARD):
                    ui.label("\U0001f3d9\ufe0f Branch Distribution").style(MV)
                    branches = data.get("top_branches", {})
                    sorted_b = sorted(branches.items(), key=lambda x: x[1], reverse=True)
                    max_b = max((v for _, v in sorted_b), default=1)
                    for name, count in sorted_b:
                        bar_w = max(count / max_b * 100, 3)
                        with ui.row().classes("w-full items-center gap-2 py-0.5"):
                            ui.label(name if name else "(empty)").classes("text-xs text-gray-300 flex-1")
                            ui.label(_fmt(count)).classes("text-xs font-bold text-white w-12 text-right")
                            ui.element("div").style(
                                f"height: 12px; width: {bar_w:.0f}%; "
                                f"background: linear-gradient(90deg, #a6e3a1, #74c7ec); "
                                f"border-radius: 4px;"
                            )

            # Row 2: PIC + Pemilik
            with ui.element("div").classes("w-full").style(
                "display: grid; gap: 16px; grid-template-columns: repeat(2, 1fr);"
            ):
                # PIC
                with ui.element("div").style(CARD):
                    ui.label("\U0001f527 Maintenance PIC").style(MV)
                    pics = data.get("top_maintenances", {})
                    sorted_p = sorted(pics.items(), key=lambda x: x[1], reverse=True)
                    max_p = max((v for _, v in sorted_p), default=1)
                    for name, count in sorted_p:
                        bar_w = max(count / max_p * 100, 3)
                        with ui.row().classes("w-full items-center gap-2 py-0.5"):
                            ui.label(name if name else "(empty)").classes("text-xs text-gray-300 flex-1")
                            ui.label(_fmt(count)).classes("text-xs font-bold text-white w-12 text-right")
                            ui.element("div").style(
                                f"height: 12px; width: {bar_w:.0f}%; "
                                f"background: linear-gradient(90deg, #cba6f7, #f5c2e7); "
                                f"border-radius: 4px;"
                            )

                # Pemilik
                with ui.element("div").style(CARD):
                    ui.label("\U0001f3e2 Pemilik").style(MV)
                    pemiliks = data.get("top_pemiliks", {})
                    sorted_pm = sorted(pemiliks.items(), key=lambda x: x[1], reverse=True)
                    max_pm = max((v for _, v in sorted_pm), default=1)
                    for name, count in sorted_pm:
                        bar_w = max(count / max_pm * 100, 3)
                        with ui.row().classes("w-full items-center gap-2 py-0.5"):
                            ui.label(name if name else "(empty)").classes("text-xs text-gray-300 flex-1")
                            ui.label(_fmt(count)).classes("text-xs font-bold text-white w-12 text-right")
                            ui.element("div").style(
                                f"height: 12px; width: {bar_w:.0f}%; "
                                f"background: linear-gradient(90deg, #fab387, #f38ba8); "
                                f"border-radius: 4px;"
                            )

            # LATEST PROBLEMS
            latest = data.get("latest", [])
            if latest:
                with ui.element("div").style(CARD).classes("w-full mb-4"):
                    ui.label("\U0001f195 Latest Problems").style(MV)
                    for rec in latest[:5]:
                        nama = _outlet_label(rec)
                        tipe = rec.get("tipeproblem", "")
                        st = rec.get("status", "")
                        sc = STATUS_COLORS.get(st, "#cdd6f4")
                        with ui.row().classes("w-full items-center gap-2 py-1 border-b border-gray-800 last:border-b-0"):
                            ui.label(TIPE_ICONS.get(tipe, '🔧')).classes("text-sm")
                            ui.label(f"{nama}").classes("text-xs font-semibold text-white flex-1")
                            ui.label(tipe).classes("text-xs text-gray-400")
                            ui.element("div").style(f"background: {sc}; padding: 1px 8px; border-radius: 6px;")
                            with ui.element("div").style(f"color: {sc}; font-size: 0.75rem; font-weight: 600;"):
                                ui.label(st)

            # TOP PROBLEMATIC OUTLETS
            top_outlets = data.get("top_outlets", [])
            if top_outlets:
                with ui.element("div").style(CARD).classes("w-full mb-4"):
                    ui.label("\U0001f534 Top Outlet Paling Bermasalah").style(MV)
                    ui.label("Outlet dengan problem terbanyak di bulan ini.").classes("text-xs text-gray-400 mb-3")
                    with ui.row().classes("w-full items-center gap-2 py-1 border-b border-gray-700 mb-1"):
                        ui.label("#").classes("text-xs text-gray-500 w-6")
                        ui.label("Outlet").classes("text-xs text-gray-500 flex-1")
                        ui.label("Total").classes("text-xs text-gray-500 w-14 text-right")
                        ui.label("Top Problem Types").classes("text-xs text-gray-500")
                    for rank, rec in enumerate(top_outlets[:10], 1):
                        total = rec["total"]
                        top_tipes = rec.get("top_tipes", {})
                        tipe_str = ", ".join(
                            f"{tipe} ({c})" for tipe, c in list(top_tipes.items())[:3]
                        )
                        with ui.row().classes("w-full items-center gap-2 py-1 border-b border-gray-800 last:border-b-0"):
                            ui.label(f"{rank}.").classes("text-xs font-bold text-gray-400 w-6")
                            ui.label(rec["name"]).classes("text-xs font-semibold text-white flex-1")
                            ui.label(_fmt(total)).classes("text-xs font-bold text-white w-12 text-right")
                            ui.label(tipe_str).classes("text-xs text-gray-300")

    # Show first month by default
    first_month = sorted_months[0] if sorted_months else None
    if first_month:
        _build_month_detail(first_month)


    # TABLE
    def _build_table():
        table_container.clear()
        with table_container:
            display = [(mk, data) for mk, data in months_data.items()]
            display.sort(reverse=True)

            col_defs = [
                {"headerName": "\U0001f4c5 Bulan", "field": "bulan", "width": 110,
                 "pinned": "left", "sortable": True,
                 "cellStyle": {"fontWeight": "600", "color": "#89b4fa"}},
                {"headerName": "\U0001f4ca Total", "field": "total", "width": 80,
                 "sortable": True, "cellStyle": {"fontWeight": "700"}},
                {"headerName": "\U0001f7e0 Open", "field": "open", "width": 75,
                 "sortable": True, "cellStyle": {"color": "#ef4444", "fontWeight": "600"}},
                {"headerName": "\u2705 Closed", "field": "closed", "width": 80,
                 "sortable": True, "cellStyle": {"color": "#22c55e"}},
                {"headerName": "\U0001f7e1 Uncomp", "field": "uncompleted", "width": 85,
                 "sortable": True, "cellStyle": {"color": "#f59e0b"}},
                {"headerName": "\U0001f3e0 Booth", "field": "booth_count", "width": 80,
                 "sortable": True},
                {"headerName": "\U0001f3d9\ufe0f Top Branch", "field": "top_branch", "width": 140,
                 "sortable": True},
                {"headerName": "\U0001f527 Top PIC", "field": "top_pic", "width": 140},
            ]

            # Add tipe columns (top 8)
            for tipe in top_tipes[:8]:
                icon = TIPE_ICONS.get(tipe, "\U0001f527")
                col_defs.append({
                    "headerName": f"{icon} {tipe}", "field": f"tipe_{tipe}",
                    "width": 80, "sortable": True,
                })

            rows = []
            for month_key, data in display:
                top_branch = ""
                top_pic = ""
                if data.get("top_branches"):
                    b, bc = list(data["top_branches"].items())[0]
                    top_branch = f"{b} ({bc})"
                if data.get("top_maintenances"):
                    p, pc = list(data["top_maintenances"].items())[0]
                    top_pic = f"{p} ({pc})"

                row = {
                    "bulan": _month_name(month_key),
                    "_month": month_key,
                    "total": data["total"],
                    "open": data["open"],
                    "closed": data["closed"],
                    "uncompleted": data["uncompleted"],
                    "booth_count": data["booth_count"],
                    "top_branch": top_branch,
                    "top_pic": top_pic,
                }
                for tipe in top_tipes[:8]:
                    row[f"tipe_{tipe}"] = data.get("tipe", {}).get(tipe, 0)
                rows.append(row)

            ui.aggrid({
                "columnDefs": col_defs,
                "rowData": rows,
                "pagination": True,
                "paginationPageSize": 20,
                "paginationPageSizeSelector": [10, 20, 34],
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
                "rowHeight": 38,
                "headerHeight": 42,
                "enableCellTextSelection": True,
                "animateRows": True,
            }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 300px;")

            ui.label(f"{len(display)} bulan").classes("text-xs text-gray-500 mt-1")

    _build_table()

#  TAB 3: DETAIL RECORD
# ═══════════════════════════════════════════════

def _render_detail_tab(parent):
    with parent:
        ui.label("🔍 Cari ID Problem Booth").classes(MV)
        ui.label("Ketik ID (misal PB-23065) untuk lihat detail lengkap.").classes("text-xs text-gray-400 mb-4")

        search_input = ui.input("🔍 Cari ID (PB-xxxxx)").props("dense outlined dark").classes("w-80")
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
                    ui.label(f"ID '{q}' tidak ditemukan.").classes("text-gray-400 italic")
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
                            ui.element("div").style(f"background: {sc}; padding: 2px 12px; border-radius: 8px;").classes("")
                            with ui.element("div").style(f"color: {sc}; font-weight: 600; font-size: 0.85rem;"):
                                ui.label(st)
                            if _ERP_URL:
                                ui.link("🔗 Buka di ERPNext", f"{_ERP_URL}/app/problem-booth/{name}",
                                        new_tab=True).classes("text-sm text-blue-400 ml-auto")

                        fields = [
                            ("subject", "📍 Nama Outlet"), ("nama_tempat", "🔢 Kode Mesin"),
                            ("branch", "🏙️ Branch"),
                            ("tipeproblem", "🔧 Tipe"), ("maintenance", "🔧 PIC"),
                            ("pemilik", "🏢 Pemilik"), ("visit", "🚗 Visit"),
                            ("device_error", "⚠️ Device Error"), ("tanggal_foto", "📅 Tanggal"), ("pbsolving", "💡 Solusi"),
                        ]
                        for f, lbl in fields:
                            v = rec.get(f)
                            if f == "visit":
                                v = "✅ Ya" if v == 1 else "❌ Tidak"
                            elif f == "device_error":
                                v = "⚠️ Ya" if v == 1 else "✅ Tidak"
                            else:
                                v = _strip_html(str(v or "—"))[:200]
                            ui.label(f"{lbl}: {v}").classes("text-xs text-gray-300 py-1 border-b border-gray-800")

                        desc = str(rec.get("description_problem", "") or "")
                        if desc:
                            clean = _strip_html(desc)
                            if clean:
                                ui.label("📝 Deskripsi:").classes("text-xs font-semibold text-white mt-2 mb-1")
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
                    ui.label(_month_name(period)).classes("text-xs text-gray-300 flex-1")
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
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
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
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
    ui.notify("⏳ Sync data dari ERPNext... (2-3 menit)", type="info", close_button=False)

    import subprocess
    import threading

    def _run_sync():
        try:
            # Sync Problem Booth
            result = subprocess.run(
                [SYNC_VENV, SYNC_SCRIPT],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                ui.notify("✅ Problem Booth sync OK", type="positive")
            else:
                ui.notify(f"⚠️ PB sync: {result.stderr[-100:]}", type="warning")
            
            # Sync KPI Sistem
            ui.notify("⏳ Sync KPI Sistem...", type="info", close_button=False)
            result2 = subprocess.run(
                [SYNC_VENV, SYNC_KPI_SCRIPT],
                capture_output=True, text=True, timeout=300,
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
        ui.label("Dashboard operasional monitoring problem booth & maintenance — untuk Dino / Head.").classes(
            "text-sm text-gray-400 mb-4")

        if total == 0:
            ui.label("Belum ada data. Sync data dari ERPNext terlebih dahulu.").classes("text-gray-400 italic")
            if s.get("last_sync"):
                ui.label(f"Terakhir sync: {s['last_sync'][:16]}").classes("text-xs text-gray-500")
            with ui.row().classes("mt-4"):
                ui.button("📥 Sync dari ERPNext", on_click=lambda: _sync_and_reload(container, None, None)).props(
                    "dense flat text-white bg-green-700")
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
            ui.label(f"💾 {_fmt(total)} problem | sync: {sync_str}").classes("text-xs text-gray-500")
            ui.button("📥 Sync dari ERPNext", on_click=lambda: _sync_and_reload(container, None, None)).props(
                "dense flat text-white bg-green-700")

        # AG Grid dark theme CSS
        ui.add_head_html("<style>.ag-theme-balham-dark{"
            "--ag-background-color:#1e1e2e;--ag-header-background-color:#181825;"
            "--ag-odd-row-background-color:#1a1a2e;--ag-row-hover-color:#313244;"
            "--ag-border-color:#313244;--ag-font-size:13px;"
            "--ag-header-height:42px;--ag-row-height:38px;"
            "--ag-selected-row-background-color:#2a2a4e;}</style>")

        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="dash").classes("w-full")
        with tabs:
            ui.tab("dash", label="📊 Dashboard")
            ui.tab("monthly", label="📋 Data Per Bulan")
            ui.tab("detail", label="🔍 Cari ID")
            ui.tab("stats", label="📈 Statistik")
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
            with ui.tab_panel("kpi"):
                kpi_sistem.create_page(ui.column().classes("w-full"))