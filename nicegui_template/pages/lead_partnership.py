"""
📋 Lead Partnership — analytics dashboard & data viewer for partnership leads (machine placement).
Read-only — data comes from ERPNext cache.
"""
from datetime import datetime

from nicegui import ui
import pandas as pd
import requests
import json
from pathlib import Path

from services.erpnext_adapter import (
    load_lp_data,
    get_cache_info,
    filter_by_staff,
)
from pages.login import get_current_email, get_current_name, get_current_role

# ── ERPNext URL for detail links ──
_ERP_URL = ""
try:
    with open("/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json") as _f:
        _ERP_URL = __import__("json").load(_f).get("url", "").rstrip("/")
except Exception:
    pass

# ── Constants for ERPNext fetch ──
CONFIG_PATH = Path("/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json")
LP_CACHE_PATH = Path("/var/www/difotoin-dashboard/streamlit_template/data/lead_partnership_cache.json")

# ── Colors ──
STATUS_COLORS = {
    "New": "#6366f1", "Contact": "#06b6d4", "Need Info": "#f59e0b",
    "Qualified": "#22c55e", "Negotiation": "#f97316", "Approved": "#14b8a6",
    "Live": "#22c55e", "Lost": "#ef4444",
}
PRIO_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#6b7280"}
KELAYAKAN_COLORS = {"Layak": "#22c55e", "Tidak Layak": "#ef4444", "Perlu Review": "#f59e0b"}
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"
ST = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"


def _fmt(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


# ═══════════════════════════════════════════════
#  ERPNext Fetch (like lead_kemitraan)
# ═══════════════════════════════════════════════

def _fetch_from_erpnext() -> pd.DataFrame:
    """Fetch fresh Lead Partnership data from ERPNext API and update cache."""
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        headers = {"Authorization": f"token {cfg['api_key']}:{cfg['api_secret']}"}
        url = cfg["url"]
        all_data = []
        limit_start = 0
        while True:
            r = requests.get(
                f"{url}/api/resource/Lead%20Partnership",
                headers=headers,
                params={"limit_page_length": 200, "limit_start": limit_start, "fields": json.dumps(["*"])},
                timeout=60,
            )
            if r.status_code != 200:
                break
            data = r.json().get("data", [])
            if not data:
                break
            all_data.extend(data)
            limit_start += 200
        cache = {"last_sync": datetime.now().isoformat(), "records": all_data}
        with open(LP_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        return pd.DataFrame(all_data)
    except Exception as e:
        ui.notify(f"Gagal fetch: {e}", type="negative")
        return pd.DataFrame()


def _fetch_and_rebuild(container):
    """Fetch from ERPNext, update cache, then rebuild entire page."""
    ui.notify("Mengambil data dari ERPNext...", type="info")
    df = _fetch_from_erpnext()
    if not df.empty:
        ui.notify(f"Berhasil: {len(df)} record!", type="positive")
    container.clear()
    create_page(container)


# ═══════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════

def create_page(container: ui.column):
    """Build the Lead Partnership page."""
    container.clear()

    with container:
        ui.label("📋 Lead Partnership").classes("text-2xl font-bold text-white")
        ui.label("Dashboard & data calon partner penempatan mesin dari ERPNext — analisis untuk pengambilan keputusan.").classes(
            "text-sm text-gray-400 mb-4")

        df = load_lp_data()
        ci = get_cache_info().get("lead_partnership", {})

        # ── Staff filtering: non-admin/manager only see their assigned leads ──
        _user_email = get_current_email()
        _user_name = get_current_name()
        _role = get_current_role()
        if _role not in ("admin", "manager") and not df.empty:
            filtered = filter_by_staff(df, _user_email, _user_name)
            if filtered.empty:
                ui.label("👤 Tidak ada lead yang di-assign ke Anda.").classes("text-xs text-yellow-400 mb-2")
            else:
                ui.label(f"👤 Menampilkan {len(filtered)} lead yang di-assign ke {_user_name or _user_email}").classes(
                    "text-xs text-yellow-400 mb-2")
            df = filtered

        if df.empty:
            ui.label("Belum ada data Lead Partnership dari ERPNext.").classes("text-gray-400 italic")
            if ci.get("last_sync"):
                ui.label(f"Terakhir sync: {ci['last_sync'][:16]}").classes("text-xs text-gray-500")
            with ui.row().classes("mt-4"):
                ui.button("📥 Fetch ERPNext", on_click=lambda: _fetch_and_rebuild(container)).props(
                    "dense flat text-white bg-green-700")
            return

        # ── Filters ──
        with ui.row().classes("w-full gap-4 items-center mb-4"):
            search_inp = ui.input("🔍 Cari (nama, tempat, PIC, kota)").props("dense outlined dark").classes("flex-[2]")
            sopts = ["Semua Status"] + sorted(df["status_lead"].dropna().unique().tolist())
            ssel = ui.select(sopts, value="Semua Status", label="Status").props("dense outlined dark").classes("flex-1")
            jopts = ["Semua Jenis"] + sorted(df["jenis_partnership"].dropna().unique().tolist())
            jsel = ui.select(jopts, value="Semua Jenis", label="Jenis Partnership").props("dense outlined dark").classes("flex-1")
            ui.button("🔄 Refresh", on_click=lambda: (container.clear(), create_page(container))).props(
                "dense flat text-white").classes("self-end")
            ui.button("📥 Fetch ERPNext", on_click=lambda: _fetch_and_rebuild(container)).props(
                "dense flat text-white bg-green-700").classes("self-end ml-2")

        # Cache info
        ct = f"💾 Data lokal: {len(df)} record"
        if ci.get("last_sync"):
            try:
                sync_dt = datetime.fromisoformat(ci["last_sync"])
                ct += f" — terakhir sync {sync_dt.strftime('%d/%m/%Y %H:%M')}"
            except Exception:
                ct += f" — terakhir sync {ci['last_sync'][:16]}"
        ui.label(ct).classes("text-xs text-gray-500 mb-4")

        # ── Filter function ──
        def get_filtered():
            fdf = df.copy()
            sq = search_inp.value.strip().lower()
            fs = ssel.value
            fj = jsel.value
            if fs and fs != "Semua Status":
                fdf = fdf[fdf["status_lead"].astype(str).str.strip() == fs]
            if fj and fj != "Semua Jenis":
                fdf = fdf[fdf["jenis_partnership"].astype(str).str.strip() == fj]
            if sq:
                mask = (
                    fdf.get("nama_pic", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("nama_tempat", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("nama_perusahaan__lembaga__venue_jika_ada", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("kota_lokasi", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("name", "").astype(str).str.lower().str.contains(sq, na=False)
                )
                fdf = fdf[mask].copy()
            return fdf

        # ── Tabs ──
        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="dash").classes("w-full")
        with tabs:
            ui.tab("dash", label="📊 Dashboard Lead Partnership")
            ui.tab("list", label="📋 Daftar Lead")
            ui.tab("master", label="📋 Master Data")

        with panels:
            with ui.tab_panel("dash"):
                _dash_container = ui.column().classes("w-full")
            with ui.tab_panel("list"):
                _list_container = ui.column().classes("w-full")
            with ui.tab_panel("master"):
                _master_container = ui.column().classes("w-full")

        def update_content():
            fdf = get_filtered()
            _dash_container.clear()
            _list_container.clear()
            _master_container.clear()
            with _dash_container:
                _render_dashboard(fdf)
            with _list_container:
                _render_lead_table(fdf)
            with _master_container:
                _render_master_data(fdf)

        for w in [search_inp, ssel, jsel]:
            w.on("change", update_content)

        update_content()


# ═══════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════

def _render_dashboard(df):
    total = len(df)
    qualified = len(df[df.get("status_lead", "").astype(str).str.strip() == "Qualified"])
    high_prio = len(df[df.get("priority", "").astype(str).str.strip() == "High"])
    live = len(df[df.get("status_lead", "").astype(str).str.strip() == "Live"])
    total_sewa = pd.to_numeric(df.get("harga_sewa", 0), errors="coerce").fillna(0).sum()
    unique_kota = df.get("kota_lokasi", "").dropna().nunique()
    sewa_fmt = f"Rp{total_sewa:,.0f}".replace(",", ".") if total_sewa > 0 else "-"

    # KPI
    with ui.row().classes("w-full gap-3 mb-6"):
        for lbl, val in [("📋 Total", _fmt(total)), ("✅ Qualified", _fmt(qualified)),
                         ("🔴 High Prio", _fmt(high_prio)), ("💚 Live", _fmt(live)),
                         ("💰 Total Sewa", sewa_fmt), ("📍 Kota", _fmt(unique_kota))]:
            with ui.card().classes("flex-1 min-w-[120px]").style(CARD):
                ui.label(lbl).style(ML)
                ui.label(val).style(MV)

    # Row 1: Status & QTY — tabel data dg filter status
    with ui.card().classes("w-full mb-6").style(CARD):
        ui.label("📊 Status & QTY").style(ST)
        _render_status_qty_table(df)

    # Row 2: Funnel + Trend
    with ui.row().classes("w-full gap-4 mb-6"):
        with ui.card().classes("flex-[1.2]").style(CARD):
            ui.label("🔄 Funnel Konversi").style(ST)
            _echart_funnel(df)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🏙️ Kota & Qty").style(ST)
            _render_kota_table(df)

    # Row 3: Status, Priority, Jenis Partnership
    with ui.row().classes("w-full gap-4 mb-6"):
        with ui.card().classes("flex-1").style(CARD):
            ui.label("📊 Status").style(ST)
            _echart_bar(df, "status_lead", STATUS_COLORS)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🎯 Prioritas").style(ST)
            _echart_pie(df, "priority", PRIO_COLORS)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🏷️ Jenis Partnership").style(ST)
            _echart_bar(df, "jenis_partnership", None)

    # Row 4: High Priority & Need Survey
    with ui.row().classes("w-full gap-4 mb-6"):
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🔴 High Priority").style(ST)
            _render_high_prio_table(df)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("📋 Butuh Survei (Need Info)").style(ST)
            _render_need_survey_table(df)

    # Row 5: Kota, Source, Skema
    with ui.row().classes("w-full gap-4 mb-6"):
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🏙️ Kota").style(ST)
            _echart_hbar(df, "kota_lokasi")
        with ui.card().classes("flex-1").style(CARD):
            ui.label("📢 Sumber Lead").style(ST)
            _echart_pie(df, "source_lead", None)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🤝 Skema Kerjasama").style(ST)
            _echart_bar(df, "skema_kerja_sama_yang_terbuka", None)

    # Row 4: Jenis Lokasi, Tipe Lokasi, Sales PIC
    with ui.row().classes("w-full gap-4 mb-6"):
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🏗️ Jenis Lokasi").style(ST)
            _echart_pie(df, "jenis_lokasi", None)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🔄 Tipe Lokasi").style(ST)
            _echart_bar_tipe(df)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("👨‍💼 Sales PIC").style(ST)
            _echart_sales_pic(df)

    # Row 5: Revenue & Sewa Summary
    with ui.card().classes("w-full mb-6").style(CARD):
        ui.label("💰 Ringkasan Revenue & Sewa").style(ST)
        _revenue_summary(df)

    # Row 6: Kelayakan
    with ui.row().classes("w-full gap-4 mb-6"):
        with ui.card().classes("flex-1").style(CARD):
            ui.label("📐 Kelayakan Space").style(ST)
            _echart_pie(df, "kelayakan_space", KELAYAKAN_COLORS)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("⚡ Kelayakan Listrik").style(ST)
            _echart_pie(df, "kelayakan_listrik", KELAYAKAN_COLORS)
        with ui.card().classes("flex-1").style(CARD):
            ui.label("🔧 Kelayakan Operasional").style(ST)
            _echart_pie(df, "kelayakan_operasional", KELAYAKAN_COLORS)

    # Row 7: Raw data
    with ui.expansion("📋 Lihat Semua Data", icon="description").classes("w-full mb-6"):
        _render_compact_table(df)


# ═══════════════════════════════════════════════
#  MASTER DATA (like lead_kemitraan)
# ═══════════════════════════════════════════════

def _render_master_data(df):
    """Show ALL data in a comprehensive table with search."""
    if df.empty:
        with ui.column():
            ui.label("Belum ada data.").classes("text-gray-400 italic")
        return

    skip_cols = {"_user_tags", "_comments", "_assign", "_liked_by", "_seen",
                 "idx", "docstatus", "disabled", "unsubscribed", "blog_subscriber", "naming_series"}
    cols = [c for c in df.columns if c not in skip_cols]
    display_df = df[cols].copy()

    # Format datetime columns
    for c in ["creation", "modified", "last_follow_up", "next_follow_up", "datetime_contact",
              "datetime_qualified", "datetime_negotiation", "datetime_approved", "datetime_live", "datetime_lost"]:
        if c in display_df.columns:
            display_df[c] = pd.to_datetime(display_df[c], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")

    # Format currency columns
    for c in ["harga_sewa", "minimum_payment"]:
        if c in display_df.columns:
            display_df[c] = display_df[c].apply(
                lambda x: f"Rp{x:,.0f}".replace(",", ".") if pd.notna(x) and isinstance(x, (int, float)) and x > 0 else x
            )

    with ui.column().classes("w-full"):  # noqa: E999
        srch = ui.input("🔍 Cari di semua kolom...").props("dense outlined dark").classes("w-full mb-3")
        info = ui.label(f"Total: {len(display_df)} record, {len(display_df.columns)} kolom").classes("text-xs text-gray-500 mb-2")
        tc = ui.column().classes("w-full")

        def rebuild():
            q = srch.value.strip().lower()
            fd = display_df.copy()
            if q:
                mask = fd.astype(str).apply(
                    lambda r: r.str.lower().str.contains(q, na=False).any(), axis=1
                )
                fd = fd[mask]
            info.text = f"Total: {len(fd)} record (dari {len(display_df)}) — {len(display_df.columns)} kolom"
            tc.clear()
            with tc:
                cd = [{"name": c, "label": c, "field": c, "align": "left", "sortable": True} for c in fd.columns]
                ui.table(
                    rows=fd.to_dict("records"),
                    columns=cd,
                    row_key="name",
                    pagination={"rowsPerPage": 25, "rowsNumber": len(fd)},
                ).props("dense dark flat bordered").classes("w-full")

        srch.on("update:model-value", rebuild)
        rebuild()


# ═══════════════════════════════════════════════
#  ECHARTS
# ═══════════════════════════════════════════════

def _dk():
    return {"backgroundColor": "transparent", "textStyle": {"color": "#cdd6f4"}}


def _render_status_qty_table(df):
    """Tabel data lead dengan filter status."""
    status_col = df.get("status_lead", "")
    if status_col.empty or status_col.dropna().empty:
        ui.label("-").classes("text-gray-400 italic text-xs")
        return

    status_options = ["Semua Status"] + sorted(status_col.dropna().unique().tolist())
    table_container = ui.column().classes("w-full")

    def rebuild_table(filter_status):
        table_container.clear()
        with table_container:
            filtered = df if filter_status == "Semua Status" else df[df["status_lead"].astype(str).str.strip() == filter_status]
            if filtered.empty:
                ui.label("Tidak ada data untuk status ini.").classes("text-gray-400 italic text-xs")
                return
            rows = []
            for _, r in filtered.iterrows():
                tempat = str(r.get("nama_tempat", "") or "").strip() or "-"
                kota = str(r.get("kota_lokasi", "") or "").strip() or "-"
                rows.append({"Tempat": tempat, "Kota": kota})
            columns = [{"name": "Tempat", "label": "📍 Nama Lokasi", "field": "Tempat", "align": "left"},
                       {"name": "Kota", "label": "🏙️ Kota Lokasi", "field": "Kota", "align": "left"}]
            ui.table(rows=rows, columns=columns, pagination={"rowsPerPage": 15}).classes("w-full").props("dark flat dense")
            ui.label(f"Total: {len(filtered)} record").classes("text-xs text-gray-400 mt-1")

    ui.select(status_options, value="Semua Status", label="Filter Status Lead",
                              on_value_change=rebuild_table
                              ).props("dense outlined dark").classes("w-full mb-3")

    rebuild_table("Semua Status")


def _render_high_prio_table(df):
    """Render high priority leads table."""
    high_df = df[df.get("priority", "").astype(str).str.strip() == "High"]
    if high_df.empty:
        ui.label("Tidak ada lead prioritas tinggi.").classes("text-gray-400 italic text-xs")
        return
    rows = []
    for _, r in high_df.iterrows():
        tempat = str(r.get("nama_tempat", "") or "").strip() or "-"
        kota = str(r.get("kota_lokasi", "") or "").strip() or "-"
        rows.append({"Tempat": tempat, "Kota": kota})
    columns = [{"name": "Tempat", "label": "📍 Tempat", "field": "Tempat", "align": "left"},
               {"name": "Kota", "label": "🏙️ Kota", "field": "Kota", "align": "left"}]
    ui.table(rows=rows, columns=columns).classes("w-full").props("dark flat dense")


def _render_need_survey_table(df):
    """Render Need Survey / Need Info leads table."""
    need_df = df[df.get("status_lead", "").astype(str).str.strip() == "Need Info"]
    if need_df.empty:
        ui.label("Tidak ada lead butuh survei.").classes("text-gray-400 italic text-xs")
        return
    rows = []
    for _, r in need_df.iterrows():
        tempat = str(r.get("nama_tempat", "") or "").strip() or "-"
        kota = str(r.get("kota_lokasi", "") or "").strip() or "-"
        status = str(r.get("status_lead", "") or "").strip() or "-"
        rows.append({"Tempat": tempat, "Kota": kota, "Status": status})
    columns = [{"name": "Tempat", "label": "📍 Tempat", "field": "Tempat", "align": "left"},
               {"name": "Kota", "label": "🏙️ Kota", "field": "Kota", "align": "left"},
               {"name": "Status", "label": "📋 Status", "field": "Status", "align": "left"}]
    ui.table(rows=rows, columns=columns).classes("w-full").props("dark flat dense")


def _render_kota_table(df):
    """Render city table with partnership counts."""
    kota = df.get("kota_lokasi", "").dropna()
    if kota.empty:
        ui.label("−").classes("text-gray-400 italic text-xs")
        return
    counts = kota.value_counts().reset_index()
    counts.columns = ["Kota", "Jumlah"]
    counts = counts.sort_values("Jumlah", ascending=False)
    
    # Format dengan nomor urut
    total = counts["Jumlah"].sum()
    columns = [
        {"name": "#", "label": "#", "field": "#", "align": "center"},
        {"name": "Kota", "label": "🏙️ Kota", "field": "Kota", "align": "left"},
        {"name": "Jumlah", "label": "📋 Qty", "field": "Jumlah", "align": "center"},
    ]
    rows = []
    for i, (_, row) in enumerate(counts.iterrows(), 1):
        rows.append({"#": i, "Kota": row["Kota"], "Jumlah": int(row["Jumlah"])})
    # Add total row
    rows.append({"#": "", "Kota": "**Total**", "Jumlah": int(total)})
    
    ui.table(
        rows=rows,
        columns=columns,
        pagination={"rowsPerPage": 20, "rowsNumber": len(rows)},
    ).classes("w-full").props("dark flat dense")


def _echart_funnel(df):
    order = ["New", "Contact", "Need Info", "Qualified", "Negotiation", "Approved", "Live"]
    counts = [int((df.get("status_lead", "").astype(str).str.strip() == s).sum()) for s in order]
    maxv = max(counts) if counts else 1
    items = [{"value": v, "name": s, "itemStyle": {"color": STATUS_COLORS.get(s, "#6b7280")}}
             for s, v in zip(order, counts) if v > 0]
    if not items:
        ui.label("−").classes("text-gray-400 italic text-xs")
        return
    ui.echart({
        "tooltip": {"trigger": "item", "formatter": "{b}: {c}"},
        "series": [{"type": "funnel", "left": "10%", "top": 20, "bottom": 20, "width": "80%",
                    "min": 0, "max": maxv, "minSize": "0%", "maxSize": "100%",
                    "sort": "descending", "gap": 2,
                    "label": {"show": True, "position": "inside", "color": "#fff", "fontSize": 11,
                              "formatter": "{b}: {c}"},
                    "itemStyle": {"borderColor": "#1e1e2e", "borderWidth": 2},
                    "data": items}],
        **_dk(),
    }).classes("w-full h-[280px]")


def _echart_bar(df, col, cmap):
    s = df.get(col, "").dropna()
    if s.empty:
        ui.label("−").classes("text-gray-400 italic text-xs")
        return
    c = s.value_counts()
    lbls = c.index.tolist()
    vals = c.values.tolist()
    colors = [cmap.get(k, "#6b7280") for k in lbls] if cmap else None
    data = [{"value": v, "itemStyle": {"color": colors[i]}} if colors else v for i, v in enumerate(vals)]
    ui.echart({
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "18%", "containLabel": True},
        "xAxis": {"type": "category", "data": lbls,
                  "axisLabel": {"color": "#a6adc8", "fontSize": 9, "rotate": 25},
                  "axisLine": {"lineStyle": {"color": "#45475a"}}},
        "yAxis": {"type": "value", "axisLabel": {"color": "#a6adc8"},
                  "splitLine": {"lineStyle": {"color": "#313244"}}},
        "series": [{"type": "bar", "data": data, "barMaxWidth": 28,
                    "label": {"show": True, "position": "top", "color": "#cdd6f4", "fontSize": 9}}],
        **_dk(),
    }).classes("w-full h-[250px]")


def _echart_pie(df, col, cmap):
    s = df.get(col, "").dropna()
    if s.empty:
        ui.label("−").classes("text-gray-400 italic text-xs")
        return
    c = s.value_counts()
    lbls = c.index.tolist()
    vals = c.values.tolist()
    colors = [cmap.get(k, "#6b7280") for k in lbls] if cmap else (["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7", "#94e2d5"] * 3)
    ui.echart({
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "color": colors,
        "series": [{"type": "pie", "radius": ["40%", "70%"], "center": ["50%", "50%"],
                    "data": [{"name": k, "value": v} for k, v in zip(lbls, vals)],
                    "label": {"color": "#cdd6f4", "fontSize": 10, "formatter": "{b}: {c}"},
                    "itemStyle": {"borderColor": "#1e1e2e", "borderWidth": 2}}],
        **_dk(),
    }).classes("w-full h-[250px]")


def _echart_hbar(df, col):
    s = df.get(col, "").dropna()
    if s.empty:
        ui.label("−").classes("text-gray-400 italic text-xs")
        return
    c = s.value_counts().head(10)
    lbls = c.index.tolist()[::-1]
    vals = c.values.tolist()[::-1]
    ui.echart({
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "10%", "bottom": "10%", "containLabel": True},
        "yAxis": {"type": "category", "data": lbls,
                  "axisLabel": {"color": "#a6adc8", "fontSize": 9},
                  "axisLine": {"lineStyle": {"color": "#45475a"}}},
        "xAxis": {"type": "value", "axisLabel": {"color": "#a6adc8"},
                  "splitLine": {"lineStyle": {"color": "#313244"}}},
        "series": [{"type": "bar", "data": vals, "barMaxWidth": 20,
                    "itemStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
                                            "colorStops": [{"offset": 0, "color": "#89b4fa"},
                                                           {"offset": 1, "color": "#45475a"}]}},
                    "label": {"show": True, "position": "right", "color": "#cdd6f4", "fontSize": 9}}],
        **_dk(),
    }).classes("w-full h-[250px]")


def _echart_bar_tipe(df):
    s = df.get("tipe_lokasi", "").dropna()
    if s.empty:
        ui.label("−").classes("text-gray-400 italic text-xs")
        return
    c = s.value_counts()
    cmap_tipe = {"Indoor": "#3b82f6", "Outdoor": "#f59e0b", "Semi-Outdoor": "#8b5cf6"}
    lbls = c.index.tolist()
    vals = c.values.tolist()
    colors = [cmap_tipe.get(k, "#6b7280") for k in lbls]
    data = [{"value": v, "itemStyle": {"color": colors[i]}} for i, v in enumerate(vals)]
    ui.echart({
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "18%", "containLabel": True},
        "xAxis": {"type": "category", "data": lbls,
                  "axisLabel": {"color": "#a6adc8"}, "axisLine": {"lineStyle": {"color": "#45475a"}}},
        "yAxis": {"type": "value", "axisLabel": {"color": "#a6adc8"},
                  "splitLine": {"lineStyle": {"color": "#313244"}}},
        "series": [{"type": "bar", "data": data, "barMaxWidth": 30,
                    "label": {"show": True, "position": "top", "color": "#cdd6f4", "fontSize": 10}}],
        **_dk(),
    }).classes("w-full h-[250px]")


def _echart_sales_pic(df):
    sp = df.get("sales_pic_full", "")
    if sp.dropna().empty:
        sp = df.get("sales_pic", "")
    if sp.dropna().empty:
        ui.label("−").classes("text-gray-400 italic text-xs")
        return
    c = sp.value_counts().sort_values(ascending=True)
    lbls = c.index.tolist()
    vals = c.values.tolist()
    ui.echart({
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "10%", "bottom": "10%", "containLabel": True},
        "yAxis": {"type": "category", "data": lbls,
                  "axisLabel": {"color": "#a6adc8", "fontSize": 9},
                  "axisLine": {"lineStyle": {"color": "#45475a"}}},
        "xAxis": {"type": "value", "axisLabel": {"color": "#a6adc8"},
                  "splitLine": {"lineStyle": {"color": "#313244"}}},
        "series": [{"type": "bar", "data": vals, "barMaxWidth": 18,
                    "itemStyle": {"color": "#cba6f7"},
                    "label": {"show": True, "position": "right", "color": "#cdd6f4", "fontSize": 9}}],
        **_dk(),
    }).classes("w-full h-[250px]")


def _revenue_summary(df):
    sewa = pd.to_numeric(df.get("harga_sewa", 0), errors="coerce").fillna(0)
    rev = pd.to_numeric(df.get("potensi_revenue", 0), errors="coerce").fillna(0)
    rr = df.get("revenue_share", "")

    with ui.row().classes("w-full gap-4"):
        with ui.column().classes("flex-1"):
            if sewa.sum() > 0:
                ui.label(f"💰 Rata-rata Sewa: Rp{sewa[sewa>0].mean():,.0f}".replace(",", ".")).classes("text-sm text-white")
                ui.label(f"🔺 Sewa Tertinggi: Rp{sewa.max():,.0f}".replace(",", ".")).classes("text-sm text-green-400")
                ui.label(f"📊 Total Sewa: Rp{sewa.sum():,.0f}".replace(",", ".")).classes("text-sm text-blue-400")
            else:
                ui.label("Data sewa belum tersedia.").classes("text-gray-400 italic text-xs")
        with ui.column().classes("flex-1"):
            if rev.sum() > 0:
                ui.label(f"📈 Rata-rata Rev: Rp{rev[rev>0].mean():,.0f}".replace(",", ".")).classes("text-sm text-white")
                ui.label(f"🔺 Rev Tertinggi: Rp{rev.max():,.0f}".replace(",", ".")).classes("text-sm text-green-400")
                ui.label(f"📊 Total Rev: Rp{rev.sum():,.0f}".replace(",", ".")).classes("text-sm text-blue-400")
            else:
                ui.label("Data potensi revenue belum tersedia.").classes("text-gray-400 italic text-xs")
        with ui.column().classes("flex-1"):
            if not rr.dropna().empty:
                ui.label("Revenue Share:").classes("text-sm text-white mb-2")
                _echart_pie(df, "revenue_share", None)
            else:
                ui.label("Data revenue share belum tersedia.").classes("text-gray-400 italic text-xs")


# ═══════════════════════════════════════════════
#  LEAD TABLE & DETAIL
# ═══════════════════════════════════════════════

def _render_lead_table(df):
    """AG Grid display (floating filter, pinned, sort, pagination) + Tempat sebagai link → klik = popup detail."""
    if df.empty:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return

    detail_data = []
    for _, row in df.iterrows():
        pic_val = str(row.get("sales_pic_full", "") or row.get("sales_pic", "") or "").strip() or "-"
        row_data = {k: row.get(k, "") for k in row.index}
        row_data["_pic"] = pic_val
        detail_data.append(row_data)

    total = len(detail_data)
    ui.label(f"📋 **{total}** lead partnership").classes("text-sm text-gray-300 mb-3")

    # Dark theme + link-style CSS
    ui.add_head_html("""<style>
.ag-theme-balham-dark { --ag-background-color: #1e1e2e; --ag-header-background-color: #181825;
    --ag-odd-row-background-color: #1a1a2e; --ag-row-hover-color: #313244;
    --ag-border-color: #313244; --ag-font-size: 13px;
    --ag-header-height: 44px; --ag-row-height: 40px;
    --ag-selected-row-background-color: #2a2a4e; }
.detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.detail-table td { padding: 6px 10px; border: none; }
.detail-table .lbl { font-weight: 600; color: #a6adc8; width: 150px; }

/* Mobile responsive */
@media (max-width: 768px) {
  .ag-theme-balham-dark { --ag-row-height: 52px !important; --ag-font-size: 12px !important; }
  .ag-cell { line-height: 44px !important; }
}
@media (max-width: 480px) {
  .nicegui-aggrid { font-size: 11px !important; }
}
</style>""")

    # ── Popup responsive for mobile ──
    ui.add_head_html("""<style>
@media (max-width: 768px) {
  .responsive-dialog-card .detail-table { font-size: 11px !important; }
  .responsive-dialog-card .detail-table td { padding: 3px 5px !important; }
  .responsive-dialog-card .detail-table .lbl { width: 85px !important; font-size: 11px !important; }
  .responsive-dialog-card .q-card { min-width: 280px !important; }
}
</style>""")

    def show_dialog(row):
        tempat = str(row.get("nama_tempat", "") or "").strip() or "-"
        fields = [
            ("ID", row.get("name","")), ("PIC", row.get("nama_pic","")),
            ("Perusahaan", row.get("nama_perusahaan__lembaga__venue_jika_ada","")),
            ("Jenis Partnership", row.get("jenis_partnership","")),
            ("Jenis Lokasi", row.get("jenis_lokasi","")), ("Tipe Lokasi", row.get("tipe_lokasi","")),
            ("Skema", row.get("skema_kerja_sama_yang_terbuka","")),
            ("Sumber", row.get("source_lead","")), ("WA PIC", row.get("nomor_whatsapp_pic","")),
            ("Email", row.get("email_pic","")), ("Area", row.get("area_penempatan","")),
            ("Jabatan", row.get("jabatan_pic","")),
            ("Pengunjung/hari", row.get("estimasi_pengunjung_per_hari","")),
            ("Space", row.get("space_tersedia","")), ("Listrik", row.get("listrik_tersedia","")),
            ("Kelayakan Space", row.get("kelayakan_space","")),
            ("Kelayakan Listrik", row.get("kelayakan_listrik","")),
            ("Kelayakan Operasional", row.get("kelayakan_operasional","")),
            ("Last FO", str(row.get("last_follow_up","") or "")[:10]),
            ("Next FO", str(row.get("next_follow_up","") or "")[:10]),
            ("Hasil FO", row.get("hasil_follow_up","")),
            ("Decision", row.get("decision","")), ("Created", str(row.get("creation","") or "")[:10]),
        ]
        with ui.dialog() as dialog, ui.card().style("background: #1e1e2e; border: 1px solid #313244; border-radius: 12px; padding: 20px; min-width: 320px; max-width: 92vw; width: auto;").classes("responsive-dialog-card"):
            ui.label(f"📋 {tempat}").classes("text-lg font-bold text-white mb-4")
            html = "<table class='detail-table'>"
            for i, (lbl, val) in enumerate(fields):
                v = str(val) if val and str(val).strip() and str(val) not in ("None", "nan", "") else "-"
                bg = ";background:#1e1e2e" if i % 2 == 0 else ""
                html += f"<tr style='{bg}'><td class='lbl'>{lbl}</td><td style='color:#cdd6f4'>{v}</td></tr>"
            html += "</table>"
            ui.html(html).classes("w-full")
            with ui.row().classes("mt-4 gap-2 items-center"):
                if _ERP_URL:
                    _rid = str(row.get("name", "") or "")
                    if _rid:
                        ui.link("\U0001f517 Buka di ERPNext",
                                f"{_ERP_URL}/app/lead-partnership/{_rid}",
                                new_tab=True).classes("text-sm text-blue-400 hover:text-blue-300")
                ui.button("Tutup", on_click=dialog.close).props("flat")
        dialog.open()

    ui.label(f"📊 {total} record — klik nama Tempat (biru) untuk detail").classes("text-xs text-gray-500 mb-2")

    # Build row data
    grid_rows = []
    for idx, r in enumerate(detail_data):
        def _fmt_date_lp(val):
                if not val or str(val).strip() in ("", "None", "nan"):
                    return "-"
                try:
                    import pandas as pd
                    return pd.to_datetime(str(val)).strftime("%d/%m/%Y")
                except:
                    return str(val)[:10]

        grid_rows.append({
            "Tempat": str(r.get("nama_tempat", "") or "").strip() or "-",
            "Kota": str(r.get("kota_lokasi", "") or "").strip() or "-",
            "Status": str(r.get("status_lead", "") or "").strip() or "-",
            "Prio": str(r.get("priority", "") or "").strip() or "-",
            "Last FO": _fmt_date_lp(r.get("last_follow_up", "")),
            "Next FO": _fmt_date_lp(r.get("next_follow_up", "")),
            "_idx": idx,
        })

    grid = ui.aggrid({
        "columnDefs": [
            {"headerName": "📍 Tempat", "field": "Tempat", "minWidth": 160, "flex": 2,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True, "pinned": "left",
             "cellStyle": {"color": "#89b4fa", "textDecoration": "underline", "cursor": "pointer", "fontWeight": "600"},
             "tooltipField": "Tempat"},
            {"headerName": "🏙️ Kota", "field": "Kota", "minWidth": 120, "flex": 1,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
            {"headerName": "✅ Status", "field": "Status", "minWidth": 100, "flex": 1,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
            {"headerName": "🎯 Prio", "field": "Prio", "width": 80, "pinned": "right",
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
            {"headerName": "Last FO", "field": "Last FO", "width": 110,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
            {"headerName": "Next FO", "field": "Next FO", "width": 110,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
        ],
        "rowData": grid_rows,
        "pagination": True,
        "paginationPageSize": 25,
        "paginationPageSizeSelector": [10, 25, 50, 100],
        "domLayout": "autoHeight",
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True, "floatingFilter": True},
        "animateRows": True,
        "rowHeight": 44,
        "headerHeight": 44,
        "enableCellTextSelection": True,
    }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 300px;")

    # Click handler — cuma Tempat aja yg trigger popup
    def on_cell_click(e):
        col = e.args.get("colId", "")
        if col == "Tempat":
            idx = e.args.get("data", {}).get("_idx", -1)
            if 0 <= idx < len(detail_data):
                show_dialog(detail_data[idx])
            grid.run_grid_method("deselectAll")

    grid.on("cellClicked", on_cell_click)

    # Fallback: detail via ID
    names = df["name"].tolist() if "name" in df.columns else []
    if names:
        with ui.expansion("🔍 Cari Detail via ID").classes("w-full mt-4").style("background: #1e1e2e; border-radius: 8px;"):
            ui.select(names, label="Pilih Lead ID", on_change=lambda e: _show_detail(df, e.value)).props("dense outlined dark").classes("w-full")

def _show_detail(df, name):
    if not name:
        return
    row = df[df["name"] == name]
    if row.empty:
        return
    r = row.iloc[0]
    fields = [
        ("nama_pic", "👤"), ("nama_perusahaan__lembaga__venue_jika_ada", "🏢"),
        ("nama_tempat", "📍"), ("jenis_partnership", "🏷️"), ("kota_lokasi", "🏙️"),
        ("jenis_lokasi", "🏗️"), ("tipe_lokasi", "🔄"),
        ("skema_kerja_sama_yang_terbuka", "🤝"), ("status_lead", "✅"),
        ("source_lead", "📢"), ("sales_pic", "👨‍💼"), ("jabatan_pic", "📋"),
        ("nomor_whatsapp_pic", "📞"), ("email_pic", "📧"), ("area_penempatan", "📍"),
        ("estimasi_pengunjung_per_hari", "👥"), ("space_tersedia", "📐"),
        ("listrik_tersedia", "⚡"), ("kelayakan_space", "✅"),
        ("kelayakan_listrik", "✅"), ("kelayakan_operasional", "✅"),
        ("pic_responsif", "📞"), ("potensi_revenue", "💰"), ("priority", "🎯"),
        ("harga_sewa", "💵"), ("revenue_share", "📊"), ("minimum_payment", "📉"),
        ("minimum_kontrak", "📅"), ("skema_final", "📋"),
        ("last_follow_up", "📆"), ("next_follow_up", "📆"), ("hasil_follow_up", "📝"),
        ("decision", "📋"), ("lost_reason", "❌"), ("creation", "📅"), ("modified", "🔄"),
    ]
    with ui.row().classes("w-full gap-4 mt-4"):
        with ui.column().classes("flex-1 gap-1"):
            for i, (f, e) in enumerate(fields):
                if i >= len(fields) // 2:
                    break
                v = r.get(f)
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                txt = str(v)
                if isinstance(v, (int, float)) and f in ("harga_sewa", "potensi_revenue", "minimum_payment"):
                    txt = f"Rp{v:,.0f}".replace(",", ".")
                ui.label(f"{e} {txt}").classes("text-xs text-gray-300 py-0.5")
        with ui.column().classes("flex-1 gap-1"):
            for i, (f, e) in enumerate(fields):
                if i < len(fields) // 2:
                    continue
                v = r.get(f)
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                txt = str(v)
                if isinstance(v, (int, float)) and f in ("harga_sewa", "potensi_revenue", "minimum_payment"):
                    txt = f"Rp{v:,.0f}".replace(",", ".")
                ui.label(f"{e} {txt}").classes("text-xs text-gray-300 py-0.5")


def _render_compact_table(df):
    if df.empty:
        ui.label("Tidak ada data.").classes("text-gray-400 italic")
        return
    display_cols = {
        "name": "ID", "nama_pic": "PIC", "nama_tempat": "Tempat",
        "jenis_partnership": "Jenis", "kota_lokasi": "Kota",
        "status_lead": "Status", "priority": "Prio",
    }
    avail = [k for k in display_cols if k in df.columns]
    display_df = df[avail].copy().rename(columns=display_cols)
    columns = [{"name": c, "label": c, "field": c} for c in display_df.columns]
    ui.table(
        rows=display_df.to_dict("records"),
        columns=columns,
        pagination={"rowsPerPage": 15},
    ).classes("w-full").props("dark flat dense")