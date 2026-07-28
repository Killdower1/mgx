"""
🤝 Lead Kemitraan (Franchise) — analytics dashboard & data viewer.
Read-only — data comes from ERPNext cache.
"""
from datetime import datetime

from nicegui import ui
import pandas as pd
import requests
import json
from pathlib import Path

from services.erpnext_adapter import (
    load_lk_data,
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
        limit_start = 0
        while True:
            r = requests.get(
                f"{url}/api/resource/Lead%20Kemitraan",
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



def _build_monthly_summary_kemitraan(df: pd.DataFrame) -> pd.DataFrame:
    """Per-month summary from Lead Kemitraan snapshot."""
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    id_col = "name" if "name" in work.columns else None
    if id_col is None:
        work = work.reset_index(drop=False).rename(columns={work.index.name or "index": "name"})
        id_col = "name"

    def _month_sets(cols):
        out = {}
        for col in cols:
            if col not in work.columns:
                continue
            ts = pd.to_datetime(work[col], errors="coerce")
            for idx2, val in ts.dropna().items():
                month = str(val.to_period("M"))
                out.setdefault(month, set()).add(str(work.at[idx2, id_col]))
        return out

    created = _month_sets(["creation"])
    updated = _month_sets(["modified", "last_follow_up", "next_follow_up", "status_updated_at"])

    months = sorted(set(created.keys()) | set(updated.keys()))
    rows = []
    for month in months:
        rows.append({
            "Month": month,
            "Lead Masuk": len(created.get(month, set())),
            "Lead Update": len(updated.get(month, set())),
        })
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary["_period"] = pd.PeriodIndex(summary["Month"], freq="M")
        summary = summary.sort_values("_period").drop(columns=["_period"]).reset_index(drop=True)
    return summary


def _render_kemitraan_monthly_inline():
    """Render monthly achievements inline in tab panel."""
    df = load_lk_data()
    ci = get_cache_info().get("lead_kemitraan", {})

    _user_email = get_current_email()
    _user_name = get_current_name()
    _role = get_current_role()
    if _role not in ("admin", "manager") and not df.empty:
        df = filter_by_staff(df, _user_email, _user_name)

    if df.empty:
        ui.label("Belum ada data Lead Kemitraan dari ERPNext.").classes("text-gray-400 italic")
        if ci.get("last_sync"):
            ui.label("Terakhir sync: " + str(ci["last_sync"])[:16]).classes("text-xs text-gray-500")
        return

    monthly = _build_monthly_summary_kemitraan(df)
    if monthly.empty:
        ui.label("Belum ada data bulanan yang bisa ditampilkan.").classes("text-gray-400 italic")
        return

    latest = monthly.iloc[-1]
    with ui.card().classes("w-full mb-6").style(CARD):
        ui.label("\U0001f4c8 Ringkasan Bulanan").style(SECTION_T)
        ui.label("Periode terbaru: " + str(latest["Month"])).classes("text-xs text-gray-400 mb-3")
        with ui.row().classes("w-full gap-3 mb-4"):
            for lbl, val in [
                ("\U0001f4e5 Lead Masuk", _fmt_num(latest["Lead Masuk"])),
                ("\U0001f6e0\ufe0f Lead Update", _fmt_num(latest["Lead Update"])),
            ]:
                with ui.card().classes("flex-1 min-w-[120px]").style(CARD):
                    ui.label(lbl).style(METRIC_LBL)
                    ui.label(val).style(METRIC_VAL)

    # Lead detail tables
    latest_month = str(latest["Month"])

    def _month_ids(col):
        if col not in df.columns:
            return set()
        ts2 = pd.to_datetime(df[col], errors="coerce")
        ids = set()
        for idx2, val in ts2.dropna().items():
            if str(val.to_period("M")) == latest_month:
                ids.add(str(df.at[idx2, "name"]))
        return ids

    created_set = _month_ids("creation")
    updated_set = (_month_ids("modified") | _month_ids("last_follow_up") |
                   _month_ids("next_follow_up") | _month_ids("status_updated_at"))

    def _find_date(row, cols):
        for col in cols:
            if col in row and pd.notna(row[col]) and str(row[col]).strip():
                dt = pd.to_datetime(row[col], errors="coerce")
                if pd.notna(dt):
                    return str(dt)[:16]
        return "-"

    metrics = [
        ("Lead Masuk", "\U0001f4e5", created_set, ["creation"]),
        ("Lead Update", "\U0001f6e0\ufe0f", updated_set,
         ["modified", "last_follow_up", "next_follow_up", "status_updated_at"]),
    ]

    for label, icon, ids_set, date_cols in metrics:
        count = len(ids_set)
        if count == 0:
            continue
        leads_df = df[df["name"].isin(ids_set)] if ids_set else pd.DataFrame()
        ui.label(icon + " " + label + ": " + str(count) + " lead").classes("text-sm font-semibold text-gray-300 mt-3 mb-1")
        if leads_df.empty:
            ui.label("Tidak ada data.").classes("text-gray-400 italic")
        else:
            trows = []
            for _, r in leads_df.iterrows():
                trows.append({
                    "Nama": r.get("nama_lengkap", r.get("lead_name", "-")) or "-",
                    "Kota": r.get("kota_domisili", "-") or "-",
                    "Status": r.get("status_lead", "-") or "-",
                    "Tgl": _find_date(r, date_cols),
                    "Sales": r.get("sales_pic", "-") or "-",
                })
            trows.sort(key=lambda x: x["Tgl"], reverse=True)
            ui.table(
                rows=trows,
                columns=[
                    {"name": "Nama", "label": "Nama", "field": "Nama", "align": "left"},
                    {"name": "Kota", "label": "Kota", "field": "Kota", "align": "left"},
                    {"name": "Status", "label": "Status", "field": "Status", "align": "center"},
                    {"name": "Tgl", "label": "Tanggal", "field": "Tgl", "align": "center"},
                    {"name": "Sales", "label": "Sales PIC", "field": "Sales", "align": "left"},
                ],
                row_key="Nama",
            ).props("dense dark flat bordered").classes("w-full")

    # Graph
    if len(monthly) > 1:
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label("\U0001f4ca Grafik Tren Bulanan").style(SECTION_T)
            # Custom monthly trend from summary
            months = monthly["Month"].tolist()
            masuk_vals = monthly["Lead Masuk"].tolist()
            update_vals = monthly["Lead Update"].tolist()
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["Lead Masuk", "Lead Update"], "textStyle": {"color": "#cdd6f4"}},
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
                "xAxis": {"type": "category", "data": months,
                          "axisLabel": {"color": "#a6adc8", "fontSize": 10},
                          "axisLine": {"lineStyle": {"color": "#45475a"}}},
                "yAxis": {"type": "value",
                          "axisLabel": {"color": "#a6adc8"},
                          "splitLine": {"lineStyle": {"color": "#313244"}}},
                "series": [
                    {"name": "Lead Masuk", "type": "line", "data": masuk_vals,
                     "smooth": True, "symbol": "circle", "symbolSize": 6,
                     "lineStyle": {"color": "#89b4fa", "width": 2},
                     "itemStyle": {"color": "#89b4fa"}},
                    {"name": "Lead Update", "type": "line", "data": update_vals,
                     "smooth": True, "symbol": "diamond", "symbolSize": 6,
                     "lineStyle": {"color": "#a6e3a1", "width": 2},
                     "itemStyle": {"color": "#a6e3a1"}},
                ],
            }).classes("w-full h-[250px]")


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

        # Staff filtering: non-admin/manager only see their assigned leads
        _user_email = get_current_email()
        _user_name = get_current_name()
        _role = get_current_role()
        if _role not in ("admin", "manager") and not df.empty:
            filtered = filter_by_staff(df, _user_email, _user_name)
            if filtered.empty:
                ui.label("Tidak ada lead yang di-assign ke Anda.").classes("text-xs text-yellow-400 mb-2")
            else:
                ui.label(f"Menampilkan {len(filtered)} lead yang di-assign ke {_user_name or _user_email}").classes(
                    "text-xs text-yellow-400 mb-2")
            df = filtered

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
            ui.button("🔄 Refresh", on_click=lambda: (container.clear(), create_page(container))).props(
                "dense flat text-white").classes("self-end")
            ui.button("📥 Fetch ERPNext", on_click=lambda: _fetch_and_rebuild(container)).props(
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
            ui.tab("daftar", label="Daftar Lead")
            ui.tab("bulanan", label="📈 Bulanan")
            ui.tab("master", label="📋 Master Data")
        with tab_panels:
            with ui.tab_panel("dashboard"):
                _dash_container = ui.column().classes("w-full")
            with ui.tab_panel("daftar"):
                _daftar_container = ui.column().classes("w-full")
            with ui.tab_panel("bulanan"):
                _render_kemitraan_monthly_inline()
            with ui.tab_panel("master"):
                _master_container = ui.column().classes("w-full")

        def rebuild_tabs(filtered_df):
            _dash_container.clear()
            _render_dashboard(_dash_container, filtered_df)
            _daftar_container.clear()
            _render_master_data(_daftar_container, filtered_df)
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
    fdf.get("jumlah_unit_final", "").dropna().values
    len(fdf[fdf.get("sudah_punya_lokasi", "").astype(str).str.strip() == "Sudah"])
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
    """Daftar Lead — AG Grid + popup detail, seperti Lead Partnership."""
    if df.empty:
        with container:
            ui.label("Belum ada data.").classes("text-gray-400 italic")
        return

    # Sanitize data to avoid surrogate encoding issues
    def _cln(v):
        if isinstance(v, str):
            return v.encode("utf-8", errors="replace").decode("utf-8")
        return v

    df = df.map(_cln) if hasattr(df, "map") else df.applymap(_cln)
    total = len(df)

    with container:
        ui.label(str(total) + " lead kemitraan").classes("text-sm text-gray-300 mb-3")

        css = (
            "<style>"
            ".ag-theme-balham-dark { "
            "--ag-background-color: #1e1e2e; --ag-header-background-color: #181825; "
            "--ag-odd-row-background-color: #1a1a2e; --ag-row-hover-color: #313244; "
            "--ag-border-color: #313244; --ag-font-size: 13px; "
            "--ag-header-height: 44px; --ag-row-height: 40px; "
            "--ag-selected-row-background-color: #2a2a4e; }"
            ".detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }"
            ".detail-table td { padding: 6px 10px; border: none; }"
            ".detail-table .lbl { font-weight: 600; color: #a6adc8; width: 150px; }"
            "@media (max-width: 768px) {"
            "  .ag-theme-balham-dark { --ag-row-height: 52px !important; --ag-font-size: 12px !important; }"
            "  .ag-cell { line-height: 44px !important; }"
            "}"
            "</style>"
        )
        ui.add_head_html(css)

        def show_dialog(row):
            nama = _cln(str(row.get("nama_lengkap", "") or "").strip()) or _cln(str(row.get("lead_name", "") or "").strip()) or "-"
            flds = [
                ("ID", "name"), ("Nama", "nama_lengkap"),
                ("WhatsApp", "nomor_whatsapp"), ("Email", "email"),
                ("Kota Domisili", "kota_domisili"),
                ("Kota Penempatan", "kota_penempatan_mesin"),
                ("Pekerjaan", "pekerjaan_bisnis_saat_ini"),
                ("Sumber Info", "dari_mana_tahu_difotoin"),
                ("Status Lead", "status_lead"), ("Prioritas", "priority"),
                ("Unit Diminati", "jumlah_unit_diminati"),
                ("Unit Final", "jumlah_unit_final"),
                ("Budget Investasi", "budget_investasi"),
                ("Investasi Dibahas", "harga_investasi_dibahas"),
                ("Skema Bayar", "skema_pembayaran"),
                ("Kesiapan DP", "kesiapan_dp"),
                ("Sudah Lokasi", "sudah_punya_lokasi"),
                ("Jenis Lokasi", "jenis_lokasi"),
                ("Kapan Mulai", "kapan_ingin_mulai"),
                ("Last FO", "last_follow_up"),
                ("Next FO", "next_follow_up"),
                ("Next Step", "next_step"),
                ("Created", "creation"),
            ]
            with ui.dialog() as dialog, ui.card().style(
                "background: #1e1e2e; border: 1px solid #313244; border-radius: 12px; "
                "padding: 20px; min-width: 320px; max-width: 92vw; width: auto;"
            ).classes("responsive-dialog-card"):
                ui.label("Detail: " + nama).classes("text-lg font-bold text-white mb-4")
                parts = ["<table class='detail-table'>"]
                for i, (lbl, key) in enumerate(flds):
                    val = _cln(str(row.get(key, "") or ""))
                    if not val.strip() or val in ("None", "nan"):
                        val = "-"
                    bg = ";background:#1e1e2e" if i % 2 == 0 else ""
                    parts.append("<tr style='" + bg + "'>")
                    parts.append("<td class='lbl'>" + lbl + "</td>")
                    parts.append("<td style='color:#cdd6f4'>" + val + "</td></tr>")
                parts.append("</table>")
                ui.html("".join(parts)).classes("w-full")
                with ui.row().classes("mt-4 gap-2 items-center"):
                    if _ERP_URL:
                        _rid = str(row.get("name", "") or "")
                        if _rid:
                            ui.link("\U0001f517 Buka di ERPNext",
                                    f"{_ERP_URL}/app/lead-kemitraan/{_rid}",
                                    new_tab=True).classes("text-sm text-blue-400 hover:text-blue-300")
                    ui.button("Tutup", on_click=dialog.close).props("flat")
            dialog.open()

        # Build AG Grid rows
        grid_rows = []
        for idx, raw in df.iterrows():
            nm = _cln(str(raw.get("nama_lengkap", "") or "").strip()) or _cln(str(raw.get("lead_name", "") or "").strip()) or "-"
            def _fmt_date_lk(val):
                    if not val or str(val).strip() in ("", "None", "nan"):
                        return "-"
                    try:
                        return pd.to_datetime(str(val)).strftime("%d/%m/%Y")
                    except:
                        return str(val)[:10]

            grid_rows.append({
                "Nama": nm,
                "WhatsApp": _cln(str(raw.get("nomor_whatsapp", "") or "").strip()) or "-",
                "Kota": _cln(str(raw.get("kota_penempatan_mesin", "") or "").strip()) or _cln(str(raw.get("kota_domisili", "") or "").strip()) or "-",
                "Status": _cln(str(raw.get("status_lead", "") or "").strip()) or "-",
                "Prio": _cln(str(raw.get("priority", "") or "").strip()) or "-",
                "Last FO": _fmt_date_lk(raw.get("last_follow_up", "")),
                "Next FO": _fmt_date_lk(raw.get("next_follow_up", "")),
                "_idx": idx,
            })

        ui.label(str(total) + " record | klik Nama (biru) untuk detail").classes("text-xs text-gray-500 mb-2")

        grid = ui.aggrid({
            "columnDefs": [
                {"headerName": "Nama", "field": "Nama", "minWidth": 160, "flex": 2,
                 "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True, "pinned": "left",
                 "cellStyle": {"color": "#89b4fa", "textDecoration": "underline", "cursor": "pointer", "fontWeight": "600"}},
                {"headerName": "WhatsApp", "field": "WhatsApp", "minWidth": 120, "flex": 1,
                 "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
                {"headerName": "Kota", "field": "Kota", "minWidth": 120, "flex": 1,
                 "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
                {"headerName": "Status", "field": "Status", "minWidth": 100, "flex": 1,
                 "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
                {"headerName": "Prio", "field": "Prio", "width": 80, "pinned": "right",
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

        def on_cell_click(e):
            col = e.args.get("colId", "")
            if col == "Nama":
                idx = e.args.get("data", {}).get("_idx", -1)
                r = df.iloc[idx] if 0 <= idx < len(df) else None
                if r is not None:
                    show_dialog(r)
                grid.run_grid_method("deselectAll")

        grid.on("cellClicked", on_cell_click)
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
