"""
🔧 Problem Booth — operational dashboard & data viewer for booth problems.
Data from ERPNext (Problem Booth doctype). Read-only.
Two-tier data: summary.json (4KB) for dashboard, cache_light.json (6.8MB) for full data.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from nicegui import ui
import pandas as pd


# ── Paths ──
SUMMARY_PATH = Path("/var/www/difotoin-dashboard/problem_booth_summary.json")
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
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"

PROBLEM_ICONS = {
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


def _parse_date(val):
    if not val or str(val).strip() in ("", "None", "nan"):
        return None
    try:
        return pd.to_datetime(str(val))
    except Exception:
        return None


def _fmt_date(val):
    d = _parse_date(val)
    return d.strftime("%d/%m/%Y") if d is not None else "-"


def _days_since(val):
    d = _parse_date(val)
    return (datetime.now() - d).days if d is not None else None


# ═══════════════════════════════════════════════
#  DATA LOADERS
# ═══════════════════════════════════════════════

def load_summary() -> dict:
    """Load lightweight summary (4KB)."""
    if not SUMMARY_PATH.exists():
        return {}
    try:
        with open(SUMMARY_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def load_light_cache() -> pd.DataFrame:
    """Load lightweight cache (6.8MB) — called lazily only when needed."""
    if not LIGHT_CACHE_PATH.exists():
        return pd.DataFrame()
    try:
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
#  DASHBOARD TAB (using summary only — 4KB)
# ═══════════════════════════════════════════════

def _render_dashboard_tab(s: dict):
    """Dashboard operasional — lightweight, only uses summary."""
    if not s or not s.get("total"):
        ui.label("Belum ada data.").classes("text-gray-400 italic")
        return

    total = s["total"]
    statuses = s.get("statuses", {})
    open_count = sum(v for k, v in statuses.items() if k.lower() in ("open", "on the way", "reopen", ""))
    closed_count = statuses.get("Closed", 0)
    uncompleted_count = statuses.get("Uncompleted", 0)

    # Monthly stats
    monthly = s.get("monthly", {})
    this_month = datetime.now().strftime("%Y-%m")
    last_month = (datetime.now().replace(day=1) - timedelta(days=15)).strftime("%Y-%m")
    this_month_count = monthly.get(this_month, 0)
    last_month_count = monthly.get(last_month, 0)

    # KPI Row
    with ui.row().classes("w-full gap-4 mb-6"):
        _kpi_card("Total Problem", _fmt(total), f"{_fmt(closed_count)} closed", "#22c55e")
        _kpi_card("Bulan Ini", _fmt(this_month_count),
                  f"{_fmt(last_month_count)} bulan lalu" if last_month_count else "", "#89b4fa")
        _kpi_card("Open", _fmt(open_count), "belum selesai", "#ef4444")
        _kpi_card("Uncompleted", _fmt(uncompleted_count), "perlu follow-up", "#f59e0b")

    # Top Problem Types + Open List
    with ui.row().classes("w-full gap-4"):
        with ui.element("div").style(CARD).classes("flex-[3] min-w-[300px]"):
            ui.label("📊 Top Problem Types").classes(MV)
            tipeproblems = s.get("tipeproblems", {})
            max_val = max(tipeproblems.values()) if tipeproblems else 1
            for tipe, count in tipeproblems.items():
                pct = count / total * 100
                bar_w = max(count / max_val * 100, 5)
                icon = PROBLEM_ICONS.get(tipe, "🔧")
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
                    nama = rec.get("nama_tempat", "?")
                    tipe = rec.get("tipeproblem", "")
                    days = _days_since(rec.get("tanggal_foto"))
                    days_str = f" ({days}h)" if days is not None else ""
                    with ui.row().classes("w-full items-start gap-2 py-1 border-b border-gray-800 last:border-b-0"):
                        badge = "🟢" if rec.get("status") == "Open" else "🟡"
                        ui.label(f"{badge}").classes("text-sm mt-0.5")
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(f"{nama} — {tipe}{days_str}").classes("text-xs font-semibold text-white")
                            if rec.get("description"):
                                ui.label(rec["description"][:80]).classes("text-xs text-gray-400 truncate")
            else:
                ui.label("Tidak ada problem open.").classes("text-xs text-gray-500 italic")

    # Branch + Pemilik + Maintenance
    with ui.row().classes("w-full gap-4 mt-4"):
        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("🏙️ Per Branch").classes(MV)
            for branch, count in list(s.get("branches", {}).items())[:8]:
                bar_w = max(count / total * 100, 3)
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(branch if branch else "(no branch)").classes("text-xs text-gray-300 flex-1")
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
                    ui.element("div").style(
                        f"height: 12px; width: {bar_w:.0f}%; "
                        f"background: linear-gradient(90deg, #a6e3a1, #74c7ec); "
                        f"border-radius: 4px;"
                    ).classes("")

        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("🏢 Per Pemilik Booth").classes(MV)
            for pem, count in list(s.get("pemiliks", {}).items())[:5]:
                bar_w = max(count / total * 100, 3)
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(pem if pem else "(no data)").classes("text-xs text-gray-300 flex-1")
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
                    ui.element("div").style(
                        f"height: 12px; width: {bar_w:.0f}%; "
                        f"background: linear-gradient(90deg, #fab387, #f38ba8); "
                        f"border-radius: 4px;"
                    ).classes("")

        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("🔧 Per Maintenance PIC").classes(MV)
            for mtce, count in list(s.get("maintenances", {}).items())[:6]:
                bar_w = max(count / total * 100, 3)
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(mtce if mtce else "(unassigned)").classes("text-xs text-gray-300 flex-1")
                    ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
                    ui.element("div").style(
                        f"height: 12px; width: {bar_w:.0f}%; "
                        f"background: linear-gradient(90deg, #cba6f7, #f5c2e7); "
                        f"border-radius: 4px;"
                    ).classes("")


# ═══════════════════════════════════════════════
#  FULL DATA TAB (loads lightweight cache lazily)
# ═══════════════════════════════════════════════

def _render_full_data_tab(container):
    """Full data — loads only when tab is shown (lazy)."""
    with container:
        loading_label = ui.label("⏳ Loading data...").classes("text-gray-400 italic")

    def _load_data():
        loading_label.set_text("⏳ Memproses 16.464 record...")
        df = load_light_cache()
        loading_label.delete()
        if df.empty:
            with container:
                ui.label("Tidak ada data.").classes("text-gray-400 italic")
            return
        _build_full_data_grid(container, df)

    ui.timer(0.1, lambda: _load_data(), once=True)


def _build_full_data_grid(container, df):
    """Build AG Grid with all filters."""
    DISPLAY_FIELDS = {
        "name": "ID", "nama_tempat": "📍 Tempat", "nama_full": "📌 Nama Full",
        "branch": "🏙️ Branch", "tipeproblem": "🔧 Tipe Problem",
        "description_problem": "📝 Deskripsi", "status": "✅ Status",
        "maintenance": "🔧 Maintenance", "pemilik": "🏢 Pemilik",
        "visit": "🚗 Visit", "device_error": "⚠️ Device Error",
        "tanggal_foto": "📅 Tanggal", "creation": "🕐 Dibuat",
        "modified": "🔄 Modified",
    }
    avail = [k for k in DISPLAY_FIELDS if k in df.columns]

    with container:
        # Filters
        with ui.row().classes("w-full gap-4 items-center mb-4"):
            search_inp = ui.input("🔍 Cari booth, tipe, PIC, branch...").props("dense outlined dark").classes("flex-[3]")
            stat_opts = ["Semua"] + sorted(df["status"].dropna().unique().tolist())
            stat_sel = ui.select(stat_opts, value="Semua", label="Status").props("dense outlined dark").classes("flex-1")
            tipe_opts = ["Semua"] + sorted(df["tipeproblem"].dropna().unique().tolist())
            tipe_sel = ui.select(tipe_opts, value="Semua", label="Tipe").props("dense outlined dark").classes("flex-1")
            branch_opts = ["Semua"] + sorted(df["branch"].dropna().unique().tolist())
            branch_sel = ui.select(branch_opts, value="Semua", label="Branch").props("dense outlined dark").classes("flex-1")

        s = load_summary()
        ct = f"💾 {_fmt(len(df))} record"
        if s.get("last_sync"):
            try:
                sync_dt = datetime.fromisoformat(s["last_sync"])
                ct += f" — sync {sync_dt.strftime('%d/%m/%Y %H:%M')}"
            except Exception:
                ct += f" — sync {s['last_sync'][:16]}"
        ui.label(ct).classes("text-xs text-gray-500 mb-4")

        grid_container = ui.column().classes("w-full")

        def _build_grid(filtered_df=None):
            grid_container.clear()
            with grid_container:
                fdf = filtered_df if filtered_df is not None else df
                if fdf.empty:
                    ui.label("Tidak ada data yang cocok.").classes("text-gray-400 italic")
                    return

                rows = []
                for _, rec in fdf.iterrows():
                    r = {}
                    for f in avail:
                        v = rec.get(f)
                        if f == "visit":
                            r[DISPLAY_FIELDS[f]] = "✅ Ya" if v == 1 else "❌ Tidak"
                        elif f == "device_error":
                            r[DISPLAY_FIELDS[f]] = "⚠️ Ya" if v == 1 else "✅ Tidak"
                        elif f in ("tanggal_foto", "creation", "modified"):
                            r[DISPLAY_FIELDS[f]] = _fmt_date(v)
                        elif f == "description_problem":
                            r[DISPLAY_FIELDS[f]] = str(v or "")[:120]
                        else:
                            r[DISPLAY_FIELDS[f]] = str(v or "—").strip()[:80]
                    rows.append(r)

                col_defs = []
                for f in avail:
                    label = DISPLAY_FIELDS[f]
                    col = {
                        "headerName": label, "field": label,
                        "sortable": True, "filter": True,
                    }
                    if f == "nama_tempat":
                        col["pinned"] = "left"
                        col["minWidth"] = 140
                        col["cellStyle"] = {"color": "#89b4fa", "fontWeight": "600"}
                    elif f == "name":
                        col["width"] = 120
                        col["cellStyle"] = {"color": "#a6adc8"}
                    elif f == "tipeproblem":
                        col["width"] = 130
                    elif f == "status":
                        col["width"] = 100
                        col["cellStyle"] = {"fontWeight": "600"}
                    elif f == "branch":
                        col["width"] = 90
                    elif f in ("visit", "device_error"):
                        col["width"] = 85
                    elif f == "description_problem":
                        col["flex"] = 2
                        col["minWidth"] = 160
                    else:
                        col["minWidth"] = 90
                        col["flex"] = 1
                    col_defs.append(col)

                ui.aggrid({
                    "columnDefs": col_defs,
                    "rowData": rows,
                    "pagination": True,
                    "paginationPageSize": 25,
                    "paginationPageSizeSelector": [10, 25, 50, 100],
                    "domLayout": "autoHeight",
                    "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
                    "rowHeight": 34,
                    "headerHeight": 38,
                    "enableCellTextSelection": True,
                }, theme="balham-dark").classes("w-full").style("height: auto; min-height: 400px;")

                ui.label(f"Menampilkan {_fmt(len(rows))} record").classes("text-xs text-gray-500 mt-1")

        _build_grid()

        def _on_filter():
            fdf = df.copy()
            sq = search_inp.value.strip().lower()
            if stat_sel.value and stat_sel.value != "Semua" and "status" in fdf.columns:
                fdf = fdf[fdf["status"].astype(str).str.strip() == stat_sel.value]
            if tipe_sel.value and tipe_sel.value != "Semua" and "tipeproblem" in fdf.columns:
                fdf = fdf[fdf["tipeproblem"].astype(str).str.strip() == tipe_sel.value]
            if branch_sel.value and branch_sel.value != "Semua" and "branch" in fdf.columns:
                fdf = fdf[fdf["branch"].astype(str).str.strip() == branch_sel.value]
            if sq:
                like = fdf.astype(str).apply(lambda x: x.str.lower().str.contains(sq, na=False))
                fdf = fdf[like.any(axis=1)].copy()
            _build_grid(fdf)

        search_inp.on("input", _on_filter)
        stat_sel.on("change", _on_filter)
        tipe_sel.on("change", _on_filter)
        branch_sel.on("change", _on_filter)


# ═══════════════════════════════════════════════
#  DETAIL VIEW TAB
# ═══════════════════════════════════════════════

def _render_detail_tab(parent):
    """Search & view detail per record."""
    with parent:
        ui.label("🔍 Cari ID Problem Booth").classes(MV)
        ui.label("Ketik ID (misal PB-23065) untuk lihat detail lengkap.").classes("text-xs text-gray-400 mb-4")

        # Load names list from light cache
        df = load_light_cache()
        if df.empty or "name" not in df.columns:
            ui.label("Data tidak tersedia.").classes("text-gray-400 italic")
            return

        names = sorted(df["name"].dropna().unique().tolist())
        detail_container = ui.column().classes("w-full mt-4")

        with ui.row().classes("w-full gap-4 items-center"):
            name_sel = ui.select([" — Pilih ID —"] + names, value=" — Pilih ID —",
                                 label="Pilih ID").props("dense outlined dark use-chips").classes("min-w-[300px]")
            ui.button("🔍 Lihat Detail", on_click=lambda: _show_detail(name_sel.value)).props("dense flat")

        def _show_detail(name):
            detail_container.clear()
            if not name or name == " — Pilih ID —":
                return
            row = df[df["name"] == name]
            if row.empty:
                ui.label(f"ID '{name}' tidak ditemukan.").classes("text-gray-400 italic")
                return
            rec = row.iloc[0]

            with detail_container:
                with ui.element("div").style(CARD).classes("w-full"):
                    with ui.row().classes("w-full items-center gap-4 mb-4"):
                        ui.label(f"🔧 {name}").classes(MV)
                        st = str(rec.get("status", "") or "")
                        sc = STATUS_COLORS.get(st, "#cdd6f4")
                        ui.element("div").style(f"background: {sc}; padding: 2px 12px; border-radius: 8px;").classes("")
                        with ui.element("div").style(f"color: {sc}; font-weight: 600; font-size: 0.85rem;"):
                            ui.label(st)
                        if _ERP_URL:
                            ui.link("🔗 Buka di ERPNext", f"{_ERP_URL}/app/problem-booth/{name}",
                                    new_tab=True).classes("text-sm text-blue-400 ml-auto")

                    left_fields = [
                        ("nama_tempat", "📍 Nama Tempat"), ("nama_full", "📌 Nama Full"),
                        ("branch", "🏙️ Branch"), ("tipeproblem", "🔧 Tipe Problem"),
                        ("pemilik", "🏢 Pemilik Booth"), ("maintenance", "🔧 Maintenance PIC"),
                        ("visit", "🚗 Visit"), ("device_error", "⚠️ Device Error"),
                        ("status", "✅ Status"),
                    ]
                    right_fields = [
                        ("tanggal_foto", "📅 Tanggal Foto"),
                        ("creation", "🕐 Dibuat"), ("modified", "🔄 Terakhir diubah"),
                        ("pbsolving", "💡 Solving"),
                    ]

                    with ui.row().classes("w-full gap-6"):
                        with ui.column().classes("flex-1 gap-0"):
                            for f, lbl in left_fields:
                                v = rec.get(f)
                                if f == "visit":
                                    v = "✅ Ya" if v == 1 else "❌ Tidak"
                                elif f == "device_error":
                                    v = "⚠️ Ya" if v == 1 else "✅ Tidak"
                                else:
                                    v = str(v or "—").strip()[:200]
                                ui.label(f"{lbl}: {v}").classes("text-xs text-gray-300 py-1 border-b border-gray-800")

                        with ui.column().classes("flex-1 gap-0"):
                            for f, lbl in right_fields:
                                v = rec.get(f)
                                if f in ("tanggal_foto", "creation", "modified"):
                                    v = _fmt_date(v)
                                else:
                                    v = str(v or "—").strip()[:200]
                                ui.label(f"{lbl}: {v}").classes("text-xs text-gray-300 py-1 border-b border-gray-800")

                    # Full description
                    desc = str(rec.get("description_problem", "") or "")
                    if desc:
                        clean = desc.replace("<p>", "").replace("</p>", "\n").replace("<br>", "\n")
                        clean = clean.split("|")
                        clean = [c.strip() for c in clean if c.strip()]
                        ui.label("📝 Deskripsi:").classes("text-xs font-semibold text-white mt-4 mb-1")
                        for c in clean[:5]:
                            ui.label(c[:200]).classes("text-xs text-gray-300")


# ═══════════════════════════════════════════════
#  STATISTIK TAB
# ═══════════════════════════════════════════════

def _render_stat_tab(s: dict):
    """Monthly trend & status distribution from summary."""
    if not s:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return

    with ui.row().classes("w-full gap-4"):
        with ui.element("div").style(CARD).classes("flex-1 min-w-[300px]"):
            ui.label("📈 Problem per Bulan").classes(MV)
            monthly = s.get("monthly", {})
            max_m = max(monthly.values()) if monthly else 1
            for period, count in monthly.items():
                bar_w = max(count / max_m * 100, 5)
                with ui.row().classes("w-full items-center gap-2 py-0.5"):
                    ui.label(str(period)).classes("text-xs text-gray-300 flex-1")
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

def create_page(container: ui.column):
    """Build Problem Booth operational dashboard."""
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
            return

        # Tabs
        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="dash").classes("w-full")

        with tabs:
            ui.tab("dash", label="📊 Dashboard Operasional")
            ui.tab("list", label="📋 Full Data")
            ui.tab("detail", label="🔍 Detail Record")
            ui.tab("stats", label="📈 Statistik")

        with panels:
            with ui.tab_panel("dash"):
                _render_dashboard_tab(s)
            with ui.tab_panel("list"):
                # Full Data — loads lazily to avoid connection timeout
                list_container = ui.column().classes("w-full")
                _render_full_data_tab(list_container)
            with ui.tab_panel("detail"):
                _render_detail_tab(ui.column().classes("w-full"))
            with ui.tab_panel("stats"):
                _render_stat_tab(s)
