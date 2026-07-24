"""
📊 KPI Sistem — Scorecard Tim Controlling (cache-only, FAST).
Data: kpi_sistem_cache.json (di-sync via scripts/sync_kpi_sistem.py).
"""
import json
from datetime import datetime
from pathlib import Path

from nicegui import ui

CACHE_PATH = Path("/var/www/difotoin-dashboard/nicegui_template/data/kpi_sistem_cache.json")
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.1rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"
STATUS_COLORS = {"Closed": "#22c55e", "Open": "#ef4444", "Uncompleted": "#f59e0b", "Done": "#22c55e", "": "#6b7280"}


def _fmt(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def _month_name(m: str) -> str:
    try:
        dt = datetime.strptime(m, "%Y-%m")
        months_en = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{months_en[dt.month]} {dt.year}"
    except Exception:
        return m


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def get_staff_list(cache: dict) -> list:
    return sorted(cache.get("staff", {}).keys())


def get_months_for_staff(cache: dict, staff: str) -> list:
    data = cache.get("staff", {}).get(staff, {})
    return sorted(data.get("months", {}).keys(), reverse=True)


def get_month_data(cache: dict, staff: str, month: str) -> dict:
    return cache.get("staff", {}).get(staff, {}).get("months", {}).get(month, {})


def get_staff_display_name(cache: dict, staff_email: str) -> str:
    """Get human-readable name for staff (from display_name or email prefix)."""
    data = cache.get("staff", {}).get(staff_email, {})
    if data.get("display_name"):
        return data["display_name"]
    return staff_email.split("@")[0]




# ═══════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════

def _kpi_card(label: str, value: str, sub: str = "", color: str = "#cdd6f4", status: str = ""):
    with ui.element("div").style(CARD).classes("flex-1 min-w-[180px]"):
        ui.label(label).classes(ML)
        with ui.row().classes("items-center gap-2"):
            ui.label(value).style(f"font-size: 1.6rem; font-weight: 700; color: {color};")
            if status:
                badge_color = "#22c55e" if status == "PASS" else "#ef4444" if status == "FAIL" else "#f59e0b"
                ui.element("div").style(f"background: {badge_color}; padding: 2px 10px; border-radius: 6px;")
                with ui.element("div").style("color: #fff; font-weight: 600; font-size: 0.75rem;"):
                    ui.label(status)
        if sub:
            ui.label(sub).classes("text-xs text-gray-500 mt-1")


def _score_ring(score: int, label: str):
    color = "#22c55e" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
    with ui.element("div").classes("flex flex-col items-center gap-1"):
        with ui.element("div").style(
            f"width: 70px; height: 70px; border-radius: 50%; border: 4px solid {color}; "
            f"display: flex; align-items: center; justify-content: center;"
        ):
            ui.label(f"{score}").style(f"font-size: 1.3rem; font-weight: 700; color: {color};")
        ui.label(label).classes("text-xs text-gray-400 text-center")


def _aggrid_dark():
    ui.add_head_html("""<style>
    .ag-theme-balham-dark{
        --ag-background-color:#1e1e2e;--ag-header-background-color:#181825;
        --ag-odd-row-background-color:#1a1a2e;--ag-row-hover-color:#313244;
        --ag-border-color:#313244;--ag-font-size:13px;
        --ag-header-height:42px;--ag-row-height:38px;
        --ag-selected-row-background-color:#2a2a4e;
    }
    .ag-cell-value[data-status="TELAT"]{color:#ef4444;font-weight:700;}
    .ag-cell-value[data-status="OK"]{color:#22c55e;font-weight:600;}
    .ag-cell-value[data-status="Done"]{color:#22c55e;font-weight:600;}
    .ag-cell-value[data-status="Open"]{color:#ef4444;font-weight:600;}
    .ag-cell-value[data-status="Closed"]{color:#22c55e;font-weight:600;}
    .ag-cell-value[data-status="Uncompleted"]{color:#f59e0b;font-weight:600;}
    </style>""")


# ═══════════════════════════════════════════════
#  TAB RENDERERS
# ═══════════════════════════════════════════════

def _render_overview(data: dict):
    if not data:
        ui.label("Tidak ada data untuk periode ini.").classes("text-gray-400 italic")
        return
    
    overall = data.get("overall", 0)
    ck = data.get("checkin", {})
    qc = data.get("qc", {})
    pb = data.get("pb", {})
    pr = data.get("printer", {})
    rk = data.get("rekapan", {})
    
    with ui.row().classes("w-full gap-4 mb-6"):
        _kpi_card("Overall", f"{overall}%", "", 
                  "#22c55e" if overall >= 80 else "#f59e0b" if overall >= 60 else "#ef4444",
                  "PASS" if overall >= 80 else "NEED IMPROVE")
        _kpi_card("Kehadiran", f"{ck.get('late_count', 0)}x telat", 
                  f"{ck.get('total_days', 0)} hari kerja",
                  "#22c55e" if ck.get('pass') else "#ef4444",
                  "PASS" if ck.get('pass') else "FAIL")
        _kpi_card("QC Verify", f"{qc.get('done', 0)}/{qc.get('total', 0)}", 
                  f"{qc.get('pending', 0)} pending" if qc.get('pending') else "All Done",
                  "#22c55e" if qc.get('pass') else "#ef4444",
                  "PASS" if qc.get('pass') else "FAIL")
        _kpi_card("PB Created", _fmt(pb.get('total', 0)), 
                  f"{len(pb.get('by_tipe', {}))} tipe", "#89b4fa", "OK")
    
    with ui.row().classes("w-full gap-6 justify-center mb-6"):
        _score_ring(ck.get("score", 0), "Kehadiran")
        _score_ring(qc.get("score", 0), "QC Verify")
        _score_ring(pb.get("score", 0), "PB Created")
        if pr.get("score") is not None:
            _score_ring(pr["score"], "Printer")
        if rk.get("score") is not None:
            _score_ring(rk["score"], "Rekapan")


def _render_checkin(data: dict):
    ui.label("⏰ KPI 1.1 — Kehadiran Tepat Waktu").classes(MV)
    ui.label("Target: < 3x telat/bulan").classes("text-xs text-gray-500 mb-3")
    
    ck = data.get("checkin", {})
    with ui.row().classes("w-full gap-4 mb-4"):
        _kpi_card("Hari Kerja", _fmt(ck.get('total_days', 0)), "Checkin + QC + PB")
        _kpi_card("Telat", _fmt(ck.get('late_count', 0)), "target: < 3x",
                  "#22c55e" if ck.get('pass') else "#ef4444")
        _kpi_card("Score", f"{ck.get('score', 0)}", "", 
                  "#22c55e" if ck.get('score', 0) >= 80 else "#f59e0b" if ck.get('score', 0) >= 60 else "#ef4444")
    
    # ALL checkin records table
    raw = ck.get("raw_records", [])
    if raw:
        with ui.element("div").style(CARD).classes("w-full mb-4"):
            ui.label("📋 Detail Kehadiran Harian:").classes("text-sm font-semibold text-white mb-2")
            cols = [
                {"headerName": "Tanggal", "field": "date", "width": 110, "pinned": "left"},
                {"headerName": "Shift Start", "field": "shift_start", "width": 100},
                {"headerName": "Masuk", "field": "checkin", "width": 80},
                {"headerName": "Pulang", "field": "checkout", "width": 80},
                {"headerName": "Status", "field": "status", "width": 80,
                 "cellClassRules": {"text-red-500": "x == 'TELAT'", "text-green-500": "x == 'OK'"}},
                {"headerName": "Telat (menit)", "field": "telat_menit", "width": 120,
                 "cellStyle": {"color": "#ef4444", "fontWeight": "600"}},
            ]
            ui.aggrid({
                "columnDefs": cols, "rowData": raw,
                "pagination": True, "paginationPageSize": 15,
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
            }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 200px;")
    
    # Summary of late days
    details = ck.get("late_details", [])
    if details:
        with ui.element("div").style(CARD).classes("w-full"):
            ui.label("⚠️ Ringkasan Keterlambatan:").classes("text-sm font-semibold text-white mb-2")
            cols = [
                {"headerName": "Tanggal", "field": "date", "width": 120},
                {"headerName": "Check-in", "field": "checkin", "width": 100},
                {"headerName": "Shift Start", "field": "shift_start", "width": 110},
                {"headerName": "Telat (menit)", "field": "diff_min", "width": 130,
                 "cellStyle": {"color": "#ef4444", "fontWeight": "600"}},
            ]
            ui.aggrid({
                "columnDefs": cols, "rowData": details,
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True, "sortable": True},
            }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 120px;")
    elif raw:
        ui.label("✅ Tidak ada keterlambatan di periode ini!").classes("text-sm text-green-400 mt-2")


def _render_qc(data: dict):
    ui.label("✅ KPI 2.2 — Verifikasi QC").classes(MV)
    ui.label("Target: 0x QC belum Done").classes("text-xs text-gray-500 mb-3")
    
    qc = data.get("qc", {})
    with ui.row().classes("w-full gap-4 mb-4"):
        _kpi_card("Total QC", _fmt(qc.get('total', 0)), "")
        _kpi_card("Done", _fmt(qc.get('done', 0)), "", "#22c55e")
        _kpi_card("Pending", _fmt(qc.get('pending', 0)), "target: 0",
                  "#22c55e" if qc.get('pass') else "#ef4444")
        _kpi_card("Score", f"{qc.get('score', 0)}", "",
                  "#22c55e" if qc.get('score', 0) >= 80 else "#f59e0b" if qc.get('score', 0) >= 60 else "#ef4444")
    
    # Raw QC records table
    raw = qc.get("raw_records", [])
    if raw:
        with ui.element("div").style(CARD).classes("w-full"):
            ui.label("📋 Daftar QC Records:").classes("text-sm font-semibold text-white mb-2")
            cols = [
                {"headerName": "ID", "field": "id", "width": 180, "pinned": "left"},
                {"headerName": "Tanggal", "field": "date", "width": 110},
                {"headerName": "Status", "field": "status", "width": 120,
                 "cellClassRules": {"text-green-500": "x == 'Done'", "text-amber-500": "x != 'Done'"}},
            ]
            ui.aggrid({
                "columnDefs": cols, "rowData": raw,
                "pagination": True, "paginationPageSize": 15,
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
            }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 200px;")
    
    if qc.get('pending', 0) > 0:
        ui.label(f"⚠️ {qc['pending']} QC belum diverifikasi.").classes("text-sm text-amber-400 mt-2")
    else:
        ui.label("✅ Semua QC sudah diverifikasi!").classes("text-sm text-green-400 mt-2")


def _render_pb(data: dict):
    ui.label("🔧 KPI 2.1 — Problem Booth Dibuat").classes(MV)
    ui.label("Target: Audit manual ≤2% error").classes("text-xs text-gray-500 mb-3")
    
    pb = data.get("pb", {})
    with ui.row().classes("w-full gap-4 mb-4"):
        _kpi_card("Total PB", _fmt(pb.get('total', 0)), "")
        _kpi_card("Score", f"{pb.get('score', 0)}", "Manual audit needed", "#89b4fa")
    
    with ui.row().classes("w-full gap-4 mb-4"):
        with ui.element("div").style(CARD).classes("flex-1 min-w-[250px]"):
            ui.label("📊 Per Tipe").classes("text-sm font-semibold text-white mb-2")
            for tipe, count in pb.get("by_tipe", {}).items():
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(tipe).classes("text-xs text-gray-300 flex-1")
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
        with ui.element("div").style(CARD).classes("flex-1 min-w-[250px]"):
            ui.label("📊 Per Status").classes("text-sm font-semibold text-white mb-2")
            for st, count in pb.get("by_status", {}).items():
                sc = STATUS_COLORS.get(st, "#cdd6f4")
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(st or "(empty)").classes("text-xs flex-1").style(f"color: {sc}")
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
    
    # Raw PB records table
    raw = pb.get("raw_records", [])
    if raw:
        with ui.element("div").style(CARD).classes("w-full"):
            ui.label("📋 Daftar Problem Booth Records:").classes("text-sm font-semibold text-white mb-2")
            cols = [
                {"headerName": "ID", "field": "id", "width": 180, "pinned": "left"},
                {"headerName": "Tanggal", "field": "date", "width": 110},
                {"headerName": "Tipe", "field": "tipe", "width": 130},
                {"headerName": "Status", "field": "status", "width": 100,
                 "cellClassRules": {"text-green-500": "x == 'Closed' || x == 'Done'", "text-red-500": "x == 'Open'", "text-amber-500": "x == 'Uncompleted'"}},
                {"headerName": "Maintenance", "field": "maintenance", "width": 150},
            ]
            ui.aggrid({
                "columnDefs": cols, "rowData": raw,
                "pagination": True, "paginationPageSize": 15,
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
            }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 200px;")
    
    ui.label("ℹ️ Untuk akurasi tipe, perlu audit manual sampling.").classes("text-xs text-gray-500 mt-4 italic")


def _render_printer(data: dict):
    ui.label("🖨️ KPI 3.1 — Response Printer").classes(MV)
    ui.label("Target: ≤1x >10 menit | Butuh email monitoring").classes("text-xs text-gray-500 mb-3")
    pr = data.get("printer", {})
    _kpi_card("Printer PB", _fmt(pr.get('total_printer', 0)), "Problem Booth tipe Printer")
    ui.label("💡 Integrasikan email monitoring printer untuk tracking otomatis.").classes("text-xs text-gray-500 mt-2")


def _render_rekapan():
    ui.label("📋 KPI 4.1 — Rekapan Akhir Shift").classes(MV)
    ui.label("Target: 0x bolos | Sumber: Discord (manual)").classes("text-xs text-gray-500 mb-3")
    ui.label("✏️ Input manual tersedia di sini (coming soon).").classes("text-sm text-amber-400 mt-2")


def _render_leaderboard(cache: dict, month: str):
    ui.label("🏆 Leaderboard Staff Controlling").classes("text-xl font-bold text-white mb-4")
    
    rows = []
    for staff, data in cache.get("staff", {}).items():
        mdata = data.get("months", {}).get(month, {})
        if not mdata:
            continue
        rows.append({
            "staff": get_staff_display_name(cache, staff),
            "overall": mdata.get("overall", 0),
            "checkin_score": mdata.get("checkin", {}).get("score", 0),
            "late": mdata.get("checkin", {}).get("late_count", 0),
            "qc_score": mdata.get("qc", {}).get("score", 0),
            "qc_pending": mdata.get("qc", {}).get("pending", 0),
            "pb_total": mdata.get("pb", {}).get("total", 0),
        })
    
    rows.sort(key=lambda x: x["overall"], reverse=True)
    
    cols = [
        {"headerName": "#", "field": "rank", "width": 50, "valueGetter": "node.rowIndex + 1"},
        {"headerName": "Staff", "field": "staff", "width": 150, "pinned": "left"},
        {"headerName": "Overall", "field": "overall", "width": 90,
         "cellStyle": {"fontWeight": "700", "color": "#89b4fa"}},
        {"headerName": "Kehadiran", "field": "checkin_score", "width": 100},
        {"headerName": "Telat", "field": "late", "width": 80, "cellStyle": {"color": "#ef4444"}},
        {"headerName": "QC Score", "field": "qc_score", "width": 100},
        {"headerName": "QC Pending", "field": "qc_pending", "width": 110, "cellStyle": {"color": "#f59e0b"}},
        {"headerName": "PB Total", "field": "pb_total", "width": 100},
    ]
    
    ui.aggrid({
        "columnDefs": cols, "rowData": rows,
        "pagination": True, "paginationPageSize": 15,
        "domLayout": "autoHeight",
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "animateRows": True,
    }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 300px;")


# ═══════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════

def create_page(container: ui.column):
    container.clear()
    cache = load_cache()
    
    with container:
        ui.label("📊 KPI Sistem — Tim Operasional (Controlling)").classes("text-2xl font-bold text-white")
        ui.label("Scorecard KPI staff operasional berdasarkan data ERPNext.").classes("text-sm text-gray-400 mb-4")
        
        if not cache or not cache.get("staff"):
            ui.label("Belum ada data. Sync terlebih dahulu.").classes("text-gray-400 italic")
            ui.label("Run: python scripts/sync_kpi_sistem.py").classes("text-xs text-gray-500")
            return
        
        sync_str = "-"
        if cache.get("last_sync"):
            try:
                sync_dt = datetime.fromisoformat(cache["last_sync"])
                sync_str = sync_dt.strftime("%d/%m/%Y %H:%M")
            except:
                sync_str = cache["last_sync"][:16]
        
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label(f"🔄 Last sync: {sync_str} | {len(cache.get('staff', {}))} staff").classes("text-xs text-gray-500")
        
        _aggrid_dark()
        
        # State
        state = {"staff": None, "month": None}
        
        staff_list = get_staff_list(cache)
        # Build display options: "Display Name (email)" -> email mapping
        staff_options = {f"{get_staff_display_name(cache, s)} ({s})": s for s in staff_list}
        all_months = set()
        for s in staff_list:
            all_months.update(get_months_for_staff(cache, s))
        sorted_months = sorted(all_months, reverse=True)
        
        if not sorted_months:
            ui.label("Tidak ada data periode.").classes("text-gray-400 italic")
            return
        
        default_month = sorted_months[0]
        
        # Controls
        with ui.row().classes("w-full gap-4 items-end mb-4"):
            ui.select(
                ["Semua Staff"] + list(staff_options.keys()),
                value="Semua Staff",
                label="👤 Staff",
                on_change=lambda e: _update_staff(staff_options.get(e.value, e.value)),
            ).props("dense outlined dark").classes("w-72")
            
            month_options = [f"{_month_name(m)} ({m})" for m in sorted_months]
            ui.select(
                month_options, value=month_options[0], label="📅 Periode",
                on_change=lambda e: _update_month(e.value),
            ).props("dense outlined dark").classes("w-48")
        
        content = ui.column().classes("w-full")
        
        def _update_staff(val):
            state["staff"] = None if val == "Semua Staff" else val
            _refresh()
        
        def _update_month(val):
            try:
                state["month"] = val.split("(")[1].split(")")[0]
            except:
                state["month"] = sorted_months[0]
            _refresh()
        
        def _refresh():
            content.clear()
            month = state["month"] or default_month
            staff = state["staff"]
            
            with content:
                if staff:
                    # Single staff view with tabs
                    data = get_month_data(cache, staff, month)
                    
                    tabs = ui.tabs().classes("w-full")
                    panels = ui.tab_panels(tabs, value="overview").classes("w-full")
                    with tabs:
                        ui.tab("overview", label="📊 Overview")
                        ui.tab("checkin", label="⏰ Kehadiran")
                        ui.tab("qc", label="✅ QC Verify")
                        ui.tab("pb", label="🔧 Problem Booth")
                        ui.tab("printer", label="🖨️ Printer")
                        ui.tab("rekapan", label="📋 Rekapan")
                    
                    with panels:
                        with ui.tab_panel("overview"):
                            _render_overview(data)
                        with ui.tab_panel("checkin"):
                            _render_checkin(data)
                        with ui.tab_panel("qc"):
                            _render_qc(data)
                        with ui.tab_panel("pb"):
                            _render_pb(data)
                        with ui.tab_panel("printer"):
                            _render_printer(data)
                        with ui.tab_panel("rekapan"):
                            _render_rekapan()
                else:
                    # All staff — show leaderboard
                    _render_leaderboard(cache, month)
        
        state["month"] = default_month
        _refresh()
