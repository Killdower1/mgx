"""
🔧 Problem Booth — operational dashboard & data viewer for booth problems.
Data from ERPNext (Problem Booth doctype). Read-only.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from nicegui import ui
import pandas as pd


# ── Paths ──
CACHE_PATH = Path("/var/www/difotoin-dashboard/problem_booth_cache.json")
CONFIG_PATH = Path("/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json")

# ── ERPNext URL for detail links ──
_ERP_URL = ""
try:
    with open(CONFIG_PATH) as _f:
        _ERP_URL = json.load(_f).get("url", "").rstrip("/")
except Exception:
    pass

# ── Colors & Styles ──
STATUS_COLORS = {
    "Closed": "#22c55e", "Open": "#ef4444", "Uncompleted": "#f59e0b",
    "On The Way": "#3b82f6", "Reopen": "#ef4444",
}
PRIO_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#6b7280"}
VISIT_COLORS = {0: "#6b7280", 1: "#22c55e"}
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"

# ── Problem type groupings for summary ──
PROBLEM_CATEGORIES = {
    "Overheat": "🔥 Overheat",
    "Listrik Mati": "⚡ Listrik",
    "Camera": "📷 Camera",
    "Camera Setting": "📷 Camera",
    "Printer": "🖨️ Printer",
    "Remote Connection Issue": "🌐 Remote",
    "Anydesk": "🌐 Remote",
    "Flash": "💡 Flash",
    "Booth": "🏠 Booth",
    "Bug": "🐛 Bug/System",
    "Ganti Kertas": "📄 Kertas",
    "Print Manual": "🖨️ Printer",
    "PC": "💻 PC",
    "Hardware Error": "🔧 Hardware",
    "Hardware": "🔧 Hardware",
    "Button": "🔘 Button",
    "Sticker": "🏷️ Sticker",
    "Monitor": "🖥️ Monitor",
    "Internet": "🌐 Internet",
    "Others": "📌 Lainnya",
}


def _fmt(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def _parse_date(val):
    """Parse ISO date string, return date object or None."""
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
#  DATA LOADER
# ═══════════════════════════════════════════════

def load_data() -> pd.DataFrame:
    """Load problem booth data from cache."""
    if not CACHE_PATH.exists():
        return pd.DataFrame()
    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        records = cache.get("records", [])
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)

        # Parse dates
        if "tanggal_foto" in df.columns:
            df["_date"] = pd.to_datetime(df["tanggal_foto"], errors="coerce")
        if "creation" in df.columns:
            df["_created"] = pd.to_datetime(df["creation"], errors="coerce")

        return df
    except Exception:
        return pd.DataFrame()


def get_cache_info() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
        return {
            "total_records": cache.get("total_records", 0),
            "last_sync": cache.get("last_sync", ""),
        }
    except Exception:
        return {}


# ═══════════════════════════════════════════════
#  PAGE COMPONENTS
# ═══════════════════════════════════════════════

def _kpi_card(label: str, value: str, sub: str = "", color: str = "#cdd6f4"):
    with ui.element("div").style(CARD).classes("flex-1 min-w-[160px]"):
        ui.label(label).classes(ML)
        ui.label(value).style(f"font-size: 1.8rem; font-weight: 700; color: {color};")
        if sub:
            ui.label(sub).classes("text-xs text-gray-500 mt-1")


def _render_dashboard_tab(df: pd.DataFrame):
    """Analytics dashboard — for Dino to monitor."""
    if df.empty:
        ui.label("Belum ada data Problem Booth.").classes("text-gray-400 italic")
        return

    total = len(df)
    total_closed = len(df[df["status"].astype(str).str.strip() == "Closed"]) if "status" in df.columns else 0
    open_recs = df[df["status"].astype(str).str.strip().isin(["Open", "On The Way", "Reopen", ""])] if "status" in df.columns else pd.DataFrame()
    uncompleted = df[df["status"].astype(str).str.strip() == "Uncompleted"] if "status" in df.columns else pd.DataFrame()

    # Problems this month
    if "_date" in df.columns:
        this_month = df[df["_date"] >= datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)]
        last_month = df[(df["_date"] >= (datetime.now().replace(day=1) - timedelta(days=60))) &
                        (df["_date"] < datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0))]
    else:
        this_month = df
        last_month = df

    # KPI Row
    with ui.row().classes("w-full gap-4 mb-6"):
        _kpi_card("Total Problem", _fmt(total), f"{_fmt(total_closed)} closed", "#22c55e")
        _kpi_card("Bulan Ini", _fmt(len(this_month)), f"{_fmt(len(last_month))} bulan lalu" if len(last_month) > 0 else "", "#89b4fa")
        _kpi_card("Open", _fmt(len(open_recs)), "belum selesai", "#ef4444")
        _kpi_card("Uncompleted", _fmt(len(uncompleted)), "perlu follow-up", "#f59e0b")

    # Top Tipe Problem + Open List (side by side)
    with ui.row().classes("w-full gap-4"):
        # Left: Top Problem Types
        with ui.element("div").style(CARD).classes("flex-[3] min-w-[300px]"):
            ui.label("📊 Top Problem Types").classes(MV)
            if "tipeproblem" in df.columns:
                top = df["tipeproblem"].value_counts().head(10)
                max_val = top.max() if len(top) > 0 else 1
                for tipe, count in top.items():
                    pct = count / total * 100
                    bar_w = max(count / max_val * 100, 5)
                    icon = "🔧"
                    for kw, emoji in PROBLEM_CATEGORIES.items():
                        if tipe == kw or tipe in kw:
                            icon = emoji.split()[0]
                            break
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

        # Right: Open Problems
        with ui.element("div").style(CARD).classes("flex-[2] min-w-[250px]"):
            ui.label("🟢 Open / Uncompleted").classes(MV)
            olist = open_recs if not open_recs.empty else uncompleted if not uncompleted.empty else df[df["status"].astype(str).str.strip() == "Uncompleted"]
            if not olist.empty:
                for _, rec in olist.sort_values("tanggal_foto", ascending=False).head(12).iterrows():
                    nama = str(rec.get("nama_tempat", rec.get("nama_full", "?")) or "?")
                    tipe = str(rec.get("tipeproblem", "") or "")
                    desc = str(rec.get("description_problem", "") or "")
                    days = _days_since(rec.get("tanggal_foto"))
                    days_str = f" ({days}h)" if days is not None else ""
                    with ui.row().classes("w-full items-start gap-2 py-1 border-b border-gray-800 last:border-b-0"):
                        badge = "🟢" if str(rec.get("status", "")).strip() == "Open" else "🟡"
                        ui.label(f"{badge}").classes("text-sm mt-0.5")
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(f"{nama} — {tipe}{days_str}").classes("text-xs font-semibold text-white")
                            if desc:
                                # Strip HTML for display
                                clean = desc.replace("<p>", " ").replace("</p>", " ").replace("<br>", " ")
                                clean = clean.split(".")[0][:100]
                                ui.label(clean).classes("text-xs text-gray-400 truncate")
            else:
                ui.label("Tidak ada problem open.").classes("text-xs text-gray-500 italic")

    # Branch Breakdown
    with ui.row().classes("w-full gap-4 mt-4"):
        # Branch
        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("🏙️ Per Branch").classes(MV)
            if "branch" in df.columns:
                for branch, count in df["branch"].value_counts().head(8).items():
                    bar_w = max(count / len(df) * 100, 3)
                    with ui.row().classes("w-full items-center gap-2 py-0.5"):
                        ui.label(branch if branch else "(no branch)").classes("text-xs text-gray-300 flex-1")
                        ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
                        ui.element("div").style(
                            f"height: 12px; width: {bar_w:.0f}%; "
                            f"background: linear-gradient(90deg, #a6e3a1, #74c7ec); "
                            f"border-radius: 4px;"
                        ).classes("")
        # Pemilik
        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("🏢 Per Pemilik Booth").classes(MV)
            if "pemilik" in df.columns:
                for pem, count in df["pemilik"].value_counts().head(5).items():
                    bar_w = max(count / len(df) * 100, 3)
                    with ui.row().classes("w-full items-center gap-2 py-0.5"):
                        ui.label(pem if pem else "(no data)").classes("text-xs text-gray-300 flex-1")
                        ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
                        ui.element("div").style(
                            f"height: 12px; width: {bar_w:.0f}%; "
                            f"background: linear-gradient(90deg, #fab387, #f38ba8); "
                            f"border-radius: 4px;"
                        ).classes("")
        # Maintenance PIC
        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("🔧 Per Maintenance PIC").classes(MV)
            if "maintenance" in df.columns:
                mtop = df["maintenance"].value_counts().head(6)
                for mtce, count in mtop.items():
                    bar_w = max(count / len(df) * 100, 3)
                    with ui.row().classes("w-full items-center gap-2 py-0.5"):
                        ui.label(mtce if mtce else "(unassigned)").classes("text-xs text-gray-300 flex-1")
                        ui.label(_fmt(count)).classes("text-xs font-bold text-white w-14 text-right")
                        ui.element("div").style(
                            f"height: 12px; width: {bar_w:.0f}%; "
                            f"background: linear-gradient(90deg, #cba6f7, #f5c2e7); "
                            f"border-radius: 4px;"
                        ).classes("")


def _render_full_data_tab(df: pd.DataFrame):
    """Full data table with all fields — AG Grid with search & filter."""
    if df.empty:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return

    # Available columns for display
    DISPLAY_FIELDS = {
        "name": "ID",
        "nama_tempat": "📍 Nama Tempat",
        "nama_full": "📌 Nama Full",
        "branch": "🏙️ Branch",
        "tipeproblem": "🔧 Tipe Problem",
        "description_problem": "📝 Deskripsi",
        "status": "✅ Status",
        "maintenance": "🔧 Maintenance",
        "pbsolving": "💡 Solusi",
        "pemilik": "🏢 Pemilik",
        "visit": "🚗 Visit",
        "device_error": "⚠️ Device Error",
        "tanggal_foto": "📅 Tanggal",
        "creation": "🕐 Created",
        "modified": "🔄 Modified",
        "password_krisbow_2": "🔑 Password",
        "owner": "👤 Owner",
        "modified_by": "✏️ Modified By",
    }

    avail = [k for k in DISPLAY_FIELDS if k in df.columns]

    # Filter search + status selector
    with ui.row().classes("w-full gap-4 items-center mb-4"):
        search_inp = ui.input("🔍 Cari booth, tipe, PIC, branch...").props("dense outlined dark").classes("flex-[3]")
        status_opts = ["Semua Status"] + sorted(df["status"].dropna().unique().tolist()) if "status" in df.columns else ["Semua Status"]
        status_sel = ui.select(status_opts, value="Semua Status", label="Status").props("dense outlined dark").classes("flex-1")
        tipe_opts = ["Semua Tipe"] + sorted(df["tipeproblem"].dropna().unique().tolist()) if "tipeproblem" in df.columns else ["Semua Tipe"]
        tipe_sel = ui.select(tipe_opts, value="Semua Tipe", label="Tipe Problem").props("dense outlined dark").classes("flex-1")
        branch_opts = ["Semua Branch"] + sorted(df["branch"].dropna().unique().tolist()) if "branch" in df.columns else ["Semua Branch"]
        branch_sel = ui.select(branch_opts, value="Semua Branch", label="Branch").props("dense outlined dark").classes("flex-1")

    # Cache info
    ci = get_cache_info()
    ct = f"💾 Total data: {_fmt(len(df))} record"
    if ci.get("last_sync"):
        try:
            sync_dt = datetime.fromisoformat(ci["last_sync"])
            ct += f" — sync terakhir {sync_dt.strftime('%d/%m/%Y %H:%M')}"
        except Exception:
            ct += f" — sync {ci['last_sync'][:16]}"
    ui.label(ct).classes("text-xs text-gray-500 mb-4")

    # Build grid data
    grid_container = ui.column().classes("w-full")

    def _build_grid(filtered_data=None):
        grid_container.clear()
        with grid_container:
            if filtered_data is None or len(filtered_data) == 0:
                fdf = df.copy()
            else:
                fdf = filtered_data.copy()

            if fdf.empty:
                ui.label("Tidak ada data yang cocok.").classes("text-gray-400 italic")
                return

            # Create AG Grid rows
            rows = []
            for _, rec in fdf.iterrows():
                r = {}
                for f in avail:
                    v = rec.get(f)
                    if f == "visit":
                        r[avail.index(f)] = "✅ Ya" if v == 1 else "❌ Tidak"
                    elif f == "device_error":
                        r[avail.index(f)] = "⚠️ Ya" if v == 1 else "✅ Tidak"
                    elif f in ("tanggal_foto", "creation", "modified"):
                        r[avail.index(f)] = _fmt_date(v)
                    elif f == "description_problem":
                        v = str(v or "")[:150].replace("<p>", "").replace("</p>", " | ").replace("<br>", " ").replace("<div", "").replace("</div>", "")
                        r[avail.index(f)] = v
                    else:
                        r[avail.index(f)] = str(v or "—").strip()[:100]
                rows.append(r)

            col_defs = []
            for i, f in enumerate(avail):
                col = {
                    "headerName": DISPLAY_FIELDS[f],
                    "field": str(i),
                    "sortable": True,
                    "filter": "agTextColumnFilter" if f not in ("visit", "device_error") else "agSetColumnFilter",
                }
                if f == "nama_tempat":
                    col["pinned"] = "left"
                    col["minWidth"] = 140
                    col["cellStyle"] = {"color": "#89b4fa", "fontWeight": "600"}
                elif f == "name":
                    col["width"] = 130
                    col["cellStyle"] = {"color": "#a6adc8"}
                elif f == "tipeproblem":
                    col["width"] = 140
                elif f == "status":
                    col["width"] = 110
                    col["cellStyle"] = {"fontWeight": "600"}
                elif f == "branch":
                    col["width"] = 100
                elif f == "maintenance":
                    col["width"] = 130
                elif f == "tanggal_foto":
                    col["width"] = 110
                elif f == "creation":
                    col["width"] = 110
                elif f in ("visit", "device_error"):
                    col["width"] = 90
                elif f == "description_problem":
                    col["flex"] = 2
                    col["minWidth"] = 180
                else:
                    col["minWidth"] = 100
                    col["flex"] = 1

                if f == "status":
                    cell_s = []
                    for st, sc in STATUS_COLORS.items():
                        cell_s.append(f"\"{st}\": \"{sc}\"")
                    col["cellStyle"] = f"function(params) {{ var m = {{{','.join(cell_s)}}}; return {{'color': m[params.value] || '#cdd6f4', 'fontWeight': '600'}}; }}"

                col_defs.append(col)

            ui.aggrid({
                "columnDefs": col_defs,
                "rowData": rows,
                "pagination": True,
                "paginationPageSize": 25,
                "paginationPageSizeSelector": [10, 25, 50, 100, 200],
                "domLayout": "autoHeight",
                "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
                "animateRows": True,
                "rowHeight": 36,
                "headerHeight": 40,
                "enableCellTextSelection": True,
                "enableRangeSelection": True,
            }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 400px;")

            ui.label(f"Menampilkan {_fmt(len(rows))} dari {_fmt(len(df))} record").classes(
                "text-xs text-gray-500 mt-1")

    # Initial build
    _build_grid()

    # Filter on change
    def _on_filter():
        fdf = df.copy()
        sq = search_inp.value.strip().lower()
        fs = status_sel.value
        ft = tipe_sel.value
        fb = branch_sel.value

        if fs and fs != "Semua Status" and "status" in fdf.columns:
            fdf = fdf[fdf["status"].astype(str).str.strip() == fs]
        if ft and ft != "Semua Tipe" and "tipeproblem" in fdf.columns:
            fdf = fdf[fdf["tipeproblem"].astype(str).str.strip() == ft]
        if fb and fb != "Semua Branch" and "branch" in fdf.columns:
            fdf = fdf[fdf["branch"].astype(str).str.strip() == fb]
        if sq:
            like = fdf.astype(str).apply(lambda x: x.str.lower().str.contains(sq, na=False))
            fdf = fdf[like.any(axis=1)].copy()
        _build_grid(fdf)

    search_inp.on("input", _on_filter)
    status_sel.on("change", lambda: _on_filter())
    tipe_sel.on("change", lambda: _on_filter())
    branch_sel.on("change", lambda: _on_filter())


def _render_detail_view(df: pd.DataFrame):
    """Search & view detail per record."""
    if df.empty:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return

    if "name" not in df.columns:
        ui.label("Field 'name' tidak tersedia.").classes("text-gray-400 italic")
        return

    names = ["— Pilih ID —"] + sorted(df["name"].dropna().unique().tolist())
    detail_container = ui.column().classes("w-full mt-4")

    with ui.row().classes("w-full gap-4 items-center"):
        name_sel = ui.select(names, value="— Pilih ID —", label="Pilih ID Problem").props(
            "dense outlined dark use-chips").classes("min-w-[300px]")
        ui.button("🔍 Lihat Detail", on_click=lambda: _show_detail(name_sel.value)).props(
            "dense flat").classes("self-end")

    def _show_detail(name):
        detail_container.clear()
        if not name or name == "— Pilih ID —":
            return
        row = df[df["name"] == name]
        if row.empty:
            ui.label(f"ID '{name}' tidak ditemukan.").classes("text-gray-400 italic")
            return
        rec = row.iloc[0]

        with detail_container:
            with ui.element("div").style(CARD).classes("w-full"):
                # Header
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

                # Two-column detail
                left_fields = [
                    ("nama_tempat", "📍 Nama Tempat"),
                    ("nama_full", "📌 Nama Full"),
                    ("branch", "🏙️ Branch"),
                    ("tipeproblem", "🔧 Tipe Problem"),
                    ("pemilik", "🏢 Pemilik Booth"),
                    ("maintenance", "🔧 Maintenance PIC"),
                    ("visit", "🚗 Visit"),
                    ("device_error", "⚠️ Device Error"),
                    ("status", "✅ Status"),
                ]
                right_fields = [
                    ("tanggal_foto", "📅 Tanggal Foto"),
                    ("creation", "🕐 Dibuat"),
                    ("modified", "🔄 Terakhir diubah"),
                    ("owner", "👤 Dibuat oleh"),
                    ("modified_by", "✏️ Diubah oleh"),
                    ("password_krisbow_2", "🔑 Password"),
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

                # Description (full width)
                desc = str(rec.get("description_problem", "") or "")
                if desc:
                    clean = desc.replace("<p>", "").replace("</p>", " | ").replace("<br>", "\n").replace("<div", "").replace("</div>", "")
                    clean = clean.replace('class="ql-editor read-mode"', "").replace(">", "").split("|")
                    clean = [c.strip() for c in clean if c.strip()]
                    if clean:
                        ui.label("📝 Deskripsi:").classes("text-xs font-semibold text-white mt-4 mb-1")
                        for c in clean:
                            ui.label(c).classes("text-xs text-gray-300")


def _render_stat_tab(df: pd.DataFrame):
    """Additional stats tab for deeper analysis."""
    if df.empty:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return

    with ui.row().classes("w-full gap-4"):
        # Monthly trend
        with ui.element("div").style(CARD).classes("flex-1 min-w-[300px]"):
            ui.label("📈 Problem per Bulan (Top 12)").classes(MV)
            if "_date" in df.columns:
                df_m = df.copy()
                df_m["_month"] = df_m["_date"].dt.to_period("M")
                monthly = df_m["_month"].value_counts().sort_index().tail(12)
                max_m = monthly.max() if len(monthly) > 0 else 1
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

        # Status distribution
        with ui.element("div").style(CARD).classes("flex-1 min-w-[200px]"):
            ui.label("✅ Status Distribution").classes(MV)
            if "status" in df.columns:
                for st, count in df["status"].value_counts().items():
                    sc = STATUS_COLORS.get(st, "#cdd6f4")
                    pct = count / len(df) * 100
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
    """Build the Problem Booth operational dashboard."""
    container.clear()
    df = load_data()
    ci = get_cache_info()

    with container:
        ui.label("🔧 Problem Booth").classes("text-2xl font-bold text-white")
        ui.label("Dashboard operasional monitoring problem booth & maintenance — pantau oleh Head (Dino).").classes(
            "text-sm text-gray-400 mb-4")

        if df.empty:
            ui.label("Belum ada data Problem Booth. Sync data dari ERPNext terlebih dahulu.").classes("text-gray-400 italic")
            if ci.get("last_sync"):
                ui.label(f"Terakhir sync: {ci['last_sync'][:16]}").classes("text-xs text-gray-500")
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
                _render_dashboard_tab(df)
            with ui.tab_panel("list"):
                _render_full_data_tab(df)
            with ui.tab_panel("detail"):
                _render_detail_view(df)
            with ui.tab_panel("stats"):
                _render_stat_tab(df)
