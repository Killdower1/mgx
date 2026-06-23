"""
🤝 Lead Kemitraan (Franchise) — analytics dashboard & data viewer.
Read-only — data comes from ERPNext cache.
"""
from datetime import datetime
from typing import Optional

from nicegui import ui
import pandas as pd
import requests
import json
from pathlib import Path

from services.erpnext_adapter import (
    load_lk_data,
    get_cache_info,
    compute_dashboard_stats,
)

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
METRIC_VAL = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
METRIC_LBL = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px;"
SECTION_T = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"
STATUS_COLORS = {
    "New": "#6366f1", "Contact": "#06b6d4", "Meeting": "#f59e0b",
    "Qualified": "#22c55e", "Negotiation": "#f97316", "Approved": "#14b8a6",
    "Live": "#22c55e", "Lost": "#ef4444", "DP Paid": "#8b5cf6",
}
PRIO_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#6b7280"}


# ── Helpers ──

def _fmt_num(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


# ── Page ──

CONFIG_PATH = Path("/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json")
LK_CACHE_PATH = Path("/var/www/difotoin-dashboard/streamlit_template/data/lead_kemitraan_cache.json")

def _fetch_from_erpnext() -> pd.DataFrame:
    """Fetch fresh Lead Kemitraan data from ERPNext API and update cache."""
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        headers = {"Authorization": f"token {cfg['api_key']}:{cfg['api_secret']}"}
        url = cfg["url"]
        all_data = []
        offset = 0
        while True:
            r = requests.get(
                f"{url}/api/resource/Lead%20Kemitraan",
                headers=headers,
                params={"limit_page_length": 200, "offset": offset, "fields": json.dumps(["*"])},
                timeout=60,
            )
            if r.status_code != 200:
                break
            data = r.json().get("data", [])
            if not data:
                break
            all_data.extend(data)
            offset += 200
        cache = {"last_sync": datetime.now().isoformat(), "records": all_data}
        with open(LK_CACHE_PATH, "w", encoding="utf-8") as f:
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


def create_page(container: ui.column):
    """Build the Lead Kemitraan page."""
    container.clear()

    with container:
        ui.label("🤝 Lead Kemitraan (Franchise)").classes("text-2xl font-bold text-white")
        ui.label("Dashboard & data calon mitra franchise dari ERPNext — analisis untuk pengambilan keputusan.").classes(
            "text-sm text-gray-400 mb-4")

        # ── Load data ──
        df = load_lk_data()
        cache_info = get_cache_info().get("lead_kemitraan", {})

        if df.empty:
            ui.label("Belum ada data Lead Kemitraan dari ERPNext.").classes("text-gray-400 italic")
            if cache_info.get("last_sync"):
                ui.label(f"Terakhir sync: {cache_info['last_sync'][:16]}").classes("text-xs text-gray-500")
            return

        # ── Global Filters ──
        fdf = df.copy()
        search_q = ""
        filter_status = "Semua Status"
        filter_prio = "Semua Prioritas"

        with ui.row().classes("w-full gap-4 items-center mb-4"):
            search_input = ui.input("🔍 Cari (nama, wa, email, kota)").props("dense outlined dark").classes("flex-[2]")
            status_opts = ["Semua Status"] + sorted(df["status_lead"].dropna().unique().tolist())
            status_select = ui.select(status_opts, value="Semua Status", label="Status").props(
                "dense outlined dark").classes("flex-1")
            prio_opts = ["Semua Prioritas"] + sorted(df["priority"].dropna().unique().tolist())
            prio_select = ui.select(prio_opts, value="Semua Prioritas", label="Prioritas").props(
                "dense outlined dark").classes("flex-1")
            refresh_btn = ui.button("🔄 Refresh", on_click=lambda: (container.clear(), create_page(container))).props(
                "dense flat text-white").classes("self-end")
            fetch_btn = ui.button("📥 Fetch ERPNext", on_click=lambda: _fetch_and_rebuild(container)).props(
                "dense flat text-white bg-green-700").classes("self-end ml-2")

        cache_txt = f"💾 Data lokal: {len(df)} record"
        if cache_info.get("last_sync"):
            try:
                sync_dt = datetime.fromisoformat(cache_info["last_sync"])
                cache_txt += f" — terakhir sync {sync_dt.strftime('%d/%m/%Y %H:%M')}"
            except Exception:
                cache_txt += f" — terakhir sync {cache_info['last_sync'][:16]}"
        ui.label(cache_txt).classes("text-xs text-gray-500 mb-4")

        # ── Apply filters ──
        def apply_filters():
            nonlocal fdf, search_q, filter_status, filter_prio
            fdf = df.copy()
            sq = search_input.value.strip().lower()
            fs = status_select.value
            fp = prio_select.value

            if fs and fs != "Semua Status":
                fdf = fdf[fdf["status_lead"].astype(str).str.strip() == fs]
            if fp and fp != "Semua Prioritas":
                fdf = fdf[fdf["priority"].astype(str).str.strip() == fp]
            if sq:
                mask = (
                    fdf.get("nama_lengkap", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("nomor_whatsapp", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("email", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("kota_domisili", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("kota_penempatan_mesin", "").astype(str).str.lower().str.contains(sq, na=False)
                    | fdf.get("name", "").astype(str).str.lower().str.contains(sq, na=False)
                )
                fdf = fdf[mask].copy()

            # Rebuild content inside tabs
            rebuild_tabs(fdf)

        for widget in [search_input, status_select, prio_select]:
            widget.on("change", apply_filters)

        # ── Tabs ──
        tabs = ui.tabs().classes("w-full")
        tab_panels = ui.tab_panels(tabs, value="dashboard").classes("w-full")

        with tabs:
            ui.tab("dashboard", label="📊 Dashboard Lead Kemitraan")
            ui.tab("master", label="📋 Master Data")
        with tab_panels:
            with ui.tab_panel("dashboard"):
                _dash_container = ui.column().classes("w-full")
            with ui.tab_panel("master"):
                _master_container = ui.column().classes("w-full")

        def rebuild_tabs(filtered_df):
            _dash_container.clear()
            _render_dashboard(_dash_container, filtered_df)
            _master_container.clear()
            _render_master_data(_master_container, filtered_df)

        # Initial render
        rebuild_tabs(fdf)


# ═══════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════

def _render_dashboard(container: ui.column, df):
    """Full analytics dashboard."""
    fdf = df
    total = len(fdf)
    qualified = len(fdf[fdf.get("status_lead", "").astype(str).str.strip() == "Qualified"])
    high_prio = len(fdf[fdf.get("priority", "").astype(str).str.strip() == "High"])
    total_investasi = pd.to_numeric(fdf.get("harga_investasi_dibahas", 0), errors="coerce").fillna(0).astype(float).sum()
    kota_col = fdf.get("kota_penempatan_mesin", fdf.get("kota_domisili", ""))
    unique_kota = kota_col.dropna().astype(str).nunique() if not kota_col.empty else 0
    total_unit = fdf.get("jumlah_unit_final", "").dropna().values
    sudah_lokasi = len(fdf[fdf.get("sudah_punya_lokasi", "").astype(str).str.strip() == "Sudah"])
    sales_pics = fdf.get("sales_pic", "").dropna().nunique()
    total_investasi_fmt = f"Rp{total_investasi:,.0f}".replace(",", ".") if total_investasi > 0 else "-"

    with container:
        # ── KPI Cards ──
        with ui.row().classes("w-full gap-3 mb-6"):
            metrics = [
                ("📋 Total Lead", _fmt_num(total), "#89b4fa"),
                ("✅ Qualified", _fmt_num(qualified), "#a6e3a1"),
                ("🔴 Prioritas Tinggi", _fmt_num(high_prio), "#f38ba8"),
                ("💰 Total Investasi", total_investasi_fmt, "#f9e2af"),
                ("📍 Kota", _fmt_num(unique_kota), "#89b4fa"),
                ("👨‍💼 Sales PIC", _fmt_num(sales_pics), "#cba6f7"),
            ]
            for lbl, val, color in metrics:
                with ui.card().classes("flex-1 min-w-[120px]").style(CARD):
                    ui.label(lbl).style(METRIC_LBL)
                    ui.label(val).style(METRIC_VAL)

        ui.separator().classes("mb-4")

        # ── ROW 1: Funnel + Trend (2 col) ──
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-[1.2]").style(CARD):
                ui.label("🔴 Funnel Konversi").style(SECTION_T)
                _chart_funnel(fdf)
            with ui.card().classes("flex-[1]").style(CARD):
                ui.label("📈 Tren Lead per Bulan").style(SECTION_T)
                _chart_monthly_trend(fdf)

        ui.separator().classes("mb-4")

        # ── ROW 2: Status, Priority, Source (3 col) ──
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📊 Sebaran Status Lead").style(SECTION_T)
                _chart_distribution(fdf, "status_lead", STATUS_COLORS, "Status")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🎯 Prioritas Lead").style(SECTION_T)
                _chart_pie(fdf, "priority", PRIO_COLORS, "Prioritas")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📢 Sumber Lead").style(SECTION_T)
                _chart_bar_top(fdf, "source_lead", "Sumber")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("💻 Tipe Meeting").style(SECTION_T)
                _chart_pie(fdf, "tipe_meeting", None, "Tipe Meeting")

        ui.separator().classes("mb-4")

        # ── ROW 3: City, Pekerjaan, Tahu Difotoin (3 col) ──
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🏙️ Kota Penempatan").style(SECTION_T)
                _chart_hbar(fdf, "kota_penempatan_mesin", "kota_domisili", "Kota")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("💼 Pekerjaan / Bisnis").style(SECTION_T)
                _chart_bar_top(fdf, "pekerjaan_bisnis_saat_ini", "Pekerjaan")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📢 Tahu Difotoin Dari").style(SECTION_T)
                _chart_bar_top(fdf, "dari_mana_tahu_difotoin", "Sumber Info")

        ui.separator().classes("mb-4")

        # ── ROW 4: Status Lokasi, Jenis Lokasi, Potensi (3 col) ──
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📍 Status Lokasi").style(SECTION_T)
                _chart_pie(fdf, "status_lokasi", None, "Status Lokasi")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🏗️ Jenis Lokasi").style(SECTION_T)
                _chart_bar_top(fdf, "jenis_lokasi", "Jenis Lokasi")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📈 Potensi").style(SECTION_T)
                _chart_bar_top(fdf, "potensi_lokasi", "Potensi")

        ui.separator().classes("mb-4")

        # ── ROW 5: Sudah Lokasi, Unit Diminati, Kapan Mulai (3 col) ──
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🏠 Sudah Punya Lokasi").style(SECTION_T)
                _chart_pie(fdf, "sudah_punya_lokasi", None, "Status")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🔢 Unit Diminati").style(SECTION_T)
                _chart_bar_top(fdf, "jumlah_unit_diminati", "Unit")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📅 Kapan Mulai").style(SECTION_T)
                _chart_bar_top(fdf, "kapan_ingin_mulai", "Waktu")

        ui.separator().classes("mb-4")

        # ── ROW 6: Disposition, Target BEP, Next Step (3 col) ──
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📋 Disposisi").style(SECTION_T)
                _chart_bar_top(fdf, "disposition", "Disposisi")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📊 Target BEP").style(SECTION_T)
                _chart_bar_top(fdf, "target_bep", "BEP")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("➡️ Next Step").style(SECTION_T)
                _chart_bar_top(fdf, "next_step", "Next Step")

        ui.separator().classes("mb-4")

        # ── ROW 7: Budget Summary (full width) ──
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label("💰 Ringkasan Budget Investasi").style(SECTION_T)
            _chart_budget_summary(fdf)

        ui.separator().classes("mb-4")

        # ── ROW 8: Sales PIC Performance ──
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label("👨‍💼 Performa Sales PIC").style(SECTION_T)
            _chart_sales_pic(fdf)

        ui.separator().classes("mb-4")

        # ── ROW 9: Raw Data Table ──
        with ui.expansion("📋 Lihat Semua Data Lead Kemitraan", icon="description").classes("w-full mb-6"):
            _render_compact_table(fdf)


# ═══════════════════════════════════════════════
#  CHART HELPERS
# ═══════════════════════════════════════════════

def _echart_opts():
    """Base dark theme for echart."""
    return {
        "backgroundColor": "transparent",
        "textStyle": {"color": "#cdd6f4"},
    }


def _chart_funnel(df):
    """Conversion funnel chart."""
    statuses = ["New", "Contact", "Qualified", "Negotiation", "Approved", "Live"]
    counts = []
    for s in statuses:
        c = int((df.get("status_lead", "").astype(str).str.strip() == s).sum())
        counts.append(c)

    max_val = max(counts) if counts else 1
    options = {
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} lead"},
        "series": [{
            "type": "funnel",
            "left": "10%",
            "top": 20,
            "bottom": 20,
            "width": "80%",
            "min": 0,
            "max": max_val,
            "minSize": "0%",
            "maxSize": "100%",
            "sort": "descending",
            "gap": 2,
            "label": {"show": True, "position": "inside", "color": "#fff", "fontSize": 11,
                     "formatter": "{b}: {c}"},
            "itemStyle": {"borderColor": "#1e1e2e", "borderWidth": 2},
            "data": [
                {"value": v, "name": s,
                 "itemStyle": {"color": STATUS_COLORS.get(s, "#6b7280")}}
                for s, v in zip(statuses, counts) if v > 0
            ],
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[250px]")
    if not any(c > 0 for c in counts):
        ui.label("Belum ada data funnel.").classes("text-gray-400 italic text-xs")


def _chart_monthly_trend(df):
    """Monthly lead trend line chart."""
    date_col = "tanggal_masuk" if "tanggal_masuk" in df.columns and not df["tanggal_masuk"].dropna().empty else "creation"
    creation = df.get(date_col, "")
    if creation.empty or creation.dropna().empty:
        ui.label("Belum ada data tanggal.").classes("text-gray-400 italic text-xs")
        return

    monthly = (
        pd.to_datetime(creation, errors="coerce").dropna().dt.to_period("M").value_counts().sort_index()
    )
    if monthly.empty:
        ui.label("Belum ada data trend.").classes("text-gray-400 italic text-xs")
        return

    months = [str(k) for k in monthly.index]
    values = monthly.values.tolist()

    options = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": months,
            "axisLabel": {"color": "#a6adc8", "fontSize": 10},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [{
            "type": "line",
            "data": values,
            "smooth": True,
            "symbol": "circle",
            "symbolSize": 6,
            "lineStyle": {"color": "#89b4fa", "width": 2},
            "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                     "colorStops": [{"offset": 0, "color": "rgba(137,180,250,0.3)"},
                                                    {"offset": 1, "color": "rgba(137,180,250,0.01)"}]}},
            "itemStyle": {"color": "#89b4fa"},
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[250px]")


def _chart_distribution(df, col, color_map, label):
    """Categorical bar chart with color map."""
    col_data = df.get(col, "")
    if col_data.empty or col_data.dropna().empty:
        ui.label(f"Belum ada data {label}.").classes("text-gray-400 italic text-xs")
        return
    counts = col_data.value_counts()
    labels = counts.index.tolist()
    values = counts.values.tolist()
    colors = [color_map.get(s, "#6b7280") for s in labels]

    options = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": labels,
            "axisLabel": {"color": "#a6adc8", "fontSize": 9, "rotate": 30},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [{
            "type": "bar",
            "data": [{"value": v, "itemStyle": {"color": c}} for v, c in zip(values, colors)],
            "barMaxWidth": 30,
            "label": {"show": True, "position": "top", "color": "#cdd6f4", "fontSize": 10},
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[250px]")


def _chart_pie(df, col, color_map, label):
    """Pie/donut chart."""
    col_data = df.get(col, "")
    if col_data.empty or col_data.dropna().empty:
        ui.label(f"Belum ada data {label}.").classes("text-gray-400 italic text-xs")
        return
    counts = col_data.value_counts()
    labels = counts.index.tolist()
    values = counts.values.tolist()
    if color_map:
        colors = [color_map.get(s, "#6b7280") for s in labels]
    else:
        colors = ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7", "#94e2d5", "#fab387", "#b4befe"] * 3

    options = {
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "color": colors,
        "series": [{
            "type": "pie",
            "radius": ["40%", "70%"],
            "center": ["50%", "50%"],
            "data": [{"name": k, "value": v} for k, v in zip(labels, values)],
            "label": {"color": "#cdd6f4", "fontSize": 10, "formatter": "{b}: {c}"},
            "itemStyle": {"borderColor": "#1e1e2e", "borderWidth": 2},
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[250px]")


def _chart_bar_top(df, col, label):
    """Top-N horizontal bar chart."""
    col_data = df.get(col, "")
    if col_data.empty or col_data.dropna().empty:
        ui.label(f"Belum ada data {label}.").classes("text-gray-400 italic text-xs")
        return
    counts = col_data.value_counts().head(10)
    labels = counts.index.tolist()
    values = counts.values.tolist()

    options = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": labels,
            "axisLabel": {"color": "#a6adc8", "fontSize": 8, "rotate": 30},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [{
            "type": "bar",
            "data": values,
            "itemStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                     "colorStops": [{"offset": 0, "color": "#89b4fa"},
                                                    {"offset": 1, "color": "#45475a"}]}},
            "barMaxWidth": 24,
            "label": {"show": True, "position": "top", "color": "#cdd6f4", "fontSize": 9},
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[250px]")


def _chart_hbar(df, col, fallback_col, label):
    """Horizontal bar chart (top cities)."""
    col_data = df.get(col, "")
    if col_data.empty or col_data.dropna().empty:
        col_data = df.get(fallback_col, "")
    if col_data.empty or col_data.dropna().empty:
        ui.label(f"Belum ada data {label}.").classes("text-gray-400 italic text-xs")
        return
    counts = col_data.value_counts().head(10)
    labels = counts.index.tolist()
    values = counts.values.tolist()

    options = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "10%", "bottom": "10%", "containLabel": True},
        "yAxis": {
            "type": "category",
            "data": labels[::-1],
            "axisLabel": {"color": "#a6adc8", "fontSize": 9},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "xAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [{
            "type": "bar",
            "data": values[::-1],
            "itemStyle": {
                "color": {"type": "linear", "x": 0, "y": 0, "x2": 1, "y2": 0,
                          "colorStops": [{"offset": 0, "color": "#89b4fa"}, {"offset": 1, "color": "#45475a"}]}
            },
            "label": {"show": True, "position": "right", "color": "#cdd6f4", "fontSize": 9},
            "barMaxWidth": 20,
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[250px]")


def _chart_budget_summary(df):
    """Investment budget breakdown."""
    budget_col = df.get("budget_investasi", "")
    if budget_col.empty or budget_col.dropna().empty:
        ui.label("Belum ada data budget investasi.").classes("text-gray-400 italic text-xs")
        return

    # Show budget distribution
    _chart_bar_top(df, "budget_investasi", "Budget Investasi")

    # Show additional detail
    with ui.row().classes("w-full gap-4 mt-2"):
        skema = df.get("skema_pembayaran", "").dropna().unique().tolist()
        if skema:
            ui.label(f"Skema Bayar: {', '.join(skema[:5])}").classes("text-xs text-gray-400")
        kesiapan = df.get("kesiapan_dp", "").value_counts()
        if not kesiapan.empty:
            ui.label(f"Kesiapan DP: {kesiapan.index[0]} ({kesiapan.values[0]})").classes("text-xs text-gray-400")


def _chart_sales_pic(df):
    """Sales PIC performance — count per PIC."""
    pic_col = df.get("sales_pic", "")
    if pic_col.empty or pic_col.dropna().empty:
        ui.label("Belum ada data Sales PIC.").classes("text-gray-400 italic text-xs")
        return
    counts = pic_col.value_counts()
    labels = counts.index.tolist()
    values = counts.values.tolist()

    options = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": labels,
            "axisLabel": {"color": "#a6adc8", "fontSize": 9, "rotate": 30},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [{
            "type": "bar",
            "data": values,
            "itemStyle": {"color": "#cba6f7"},
            "barMaxWidth": 30,
            "label": {"show": True, "position": "top", "color": "#cdd6f4", "fontSize": 10},
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[250px]")


def _render_master_data(container: ui.column, df):
    """Show ALL data in a comprehensive table with search."""
    if df.empty:
        with container:
            ui.label("Belum ada data.").classes("text-gray-400 italic")
        return
    skip_cols = {"_user_tags","_comments","_assign","_liked_by","_seen",
                 "idx","docstatus","disabled","unsubscribed","blog_subscriber","naming_series"}
    cols = [c for c in df.columns if c not in skip_cols]
    display_df = df[cols].copy()
    for c in ["creation","modified","tanggal_masuk","last_follow_up",
              "status_updated_at","next_follow_up","jadwal_meeting"]:
        if c in display_df.columns:
            display_df[c] = pd.to_datetime(display_df[c],errors="coerce").dt.strftime("%d/%m/%Y %H:%M")
    with container:
        srch = ui.input("🔍 Cari di semua kolom...").props("dense outlined dark").classes("w-full mb-3")
        info = ui.label(f"Total: {len(display_df)} record, {len(display_df.columns)} kolom").classes("text-xs text-gray-500 mb-2")
        tc = ui.column().classes("w-full")
        def rebuild():
            q = srch.value.strip().lower()
            fd = display_df.copy()
            if q:
                fd = fd[fd.astype(str).apply(lambda r: r.str.lower().str.contains(q,na=False).any(),axis=1)]
            info.text = f"Total: {len(fd)} record (dari {len(display_df)}) — {len(display_df.columns)} kolom"
            tc.clear()
            with tc:
                cd = [{"name":c,"label":c,"field":c,"align":"left","sortable":True} for c in fd.columns]
                ui.table(rows=fd.to_dict("records"),columns=cd,row_key="name",
                    pagination={"rowsPerPage":25,"rowsNumber":len(fd)}
                ).props("dense dark flat bordered").classes("w-full")
        srch.on("update:model-value",rebuild)
        rebuild()


def _render_compact_table(df):
    """Compact data table with display names."""
    # Map display names
    display_cols = {
        "name": "ID", "nama_lengkap": "Nama", "nomor_whatsapp": "WA",
        "kota_domisili": "Domisili", "status_lead": "Status", "priority": "Prioritas",
        "source_lead": "Source", "sales_pic": "Sales PIC",
        "creation": "Dibuat", "budget_investasi": "Budget",
        "jumlah_unit_final": "Unit", "next_follow_up": "FO Berikut",
        "tanggal_masuk": "Tgl Masuk", "tipe_meeting": "Meeting",
        "last_follow_up": "FO Terakhir", "alamat": "Alamat",
    }
    avail_cols = [(k, v) for k, v in display_cols.items() if k in df.columns]

    display_df = df[[c for c, _ in avail_cols]].copy()
    display_df = display_df.rename(columns={k: v for k, v in avail_cols})

    # Format date
    if "Dibuat" in display_df.columns:
        display_df["Dibuat"] = pd.to_datetime(display_df["Dibuat"], errors="coerce").dt.strftime("%d/%m/%Y")

    columns = [{"name": c, "label": c, "field": c, "align": "left"} for c in display_df.columns]

    ui.table(
        rows=display_df.head(100).to_dict("records"),
        columns=columns,
        pagination={"rowsPerPage": 15, "rowsNumber": len(display_df)},
    ).classes("w-full").props("dark flat dense")
