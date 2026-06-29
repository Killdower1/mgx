"""
🎨 Creative Team Dashboard — 2 tabs:
  1. Leads (Partnership + Kemitraan)
  2. Outlet Optimasi (3 months)
"""
from datetime import datetime

from nicegui import ui
import pandas as pd

from services.erpnext_adapter import (
    load_lp_data,
    load_lk_data,
    get_cache_info,
)
from services.difotoin_api_adapter import load_dashboard_summary

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
METRIC_VAL = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
METRIC_LBL = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px;"
SECTION_T = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"


def _fmt_num(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def _fmt_rp(v) -> str:
    try:
        return f"Rp{v:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "-"


def _echart_opts():
    return {"backgroundColor": "transparent", "textStyle": {"color": "#cdd6f4"}}


# ═══════════════════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════════════════

def create_page(container: ui.column):
    """Build Creative Team page."""
    container.clear()

    with container:
        ui.label("🎨 Creative Team").classes("text-2xl font-bold text-white")
        ui.label("Monitoring leads & outlet optimasi untuk tim creative.").classes(
            "text-sm text-gray-400 mb-4")

        # ── Load all data ──
        df_lp = load_lp_data()
        df_lk = load_lk_data()
        df_dash = _load_optimasi_data()

        # ── Tabs ──
        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="leads").classes("w-full")

        with tabs:
            ui.tab("leads", label="📊 Leads")
            ui.tab("optimasi", label="🏪 Outlet Optimasi")

        with panels:
            with ui.tab_panel("leads"):
                _leads_container = ui.column().classes("w-full")
                _render_leads(_leads_container, df_lp, df_lk)

            with ui.tab_panel("optimasi"):
                _opt_container = ui.column().classes("w-full")
                _render_optimasi(_opt_container, df_dash)


# ═══════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════

def _load_optimasi_data() -> pd.DataFrame:
    """Load dashboard summary and filter for Optimasi outlets."""
    try:
        data = load_dashboard_summary()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty or "outlet_status" not in df.columns:
            return pd.DataFrame()

        # Filter only Optimasi
        df = df[df["outlet_status"] == "Optimasi"].copy()

        # Ensure numeric columns
        for col in ["total_revenue", "foto_qty", "unlock_qty", "print_qty"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Parse periode
        if "periode" in df.columns:
            df["periode_dt"] = pd.to_datetime(df["periode"], format="%Y-%m", errors="coerce")
            df = df.sort_values("periode_dt")

        return df
    except Exception:
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════
#  TAB 1: LEADS
# ═══════════════════════════════════════════════════════════

def _render_leads(container: ui.column, df_lp: pd.DataFrame, df_lk: pd.DataFrame):
    """Render the Leads tab."""
    with container:
        if df_lp.empty and df_lk.empty:
            ui.label("Belum ada data leads.").classes("text-gray-400 italic")
            # Cache info
            ci = get_cache_info()
            for src, label in [("lead_partnership", "Partnership"), ("lead_kemitraan", "Kemitraan")]:
                info = ci.get(src, {})
                if info.get("last_sync"):
                    ui.label(f"{label}: sync terakhir {info['last_sync'][:16]}").classes(
                        "text-xs text-gray-500")
            return

        # ── Compute KPI ──
        total_lp = len(df_lp)
        total_lk = len(df_lk)
        total_leads = total_lp + total_lk

        # Monthly breakdown
        def _monthly(series):
            try:
                return series.dropna().dt.to_period("M").value_counts().sort_index()
            except Exception:
                return pd.Series(dtype=int)

        lp_monthly = _monthly(df_lp.get("creation", pd.Series()))
        lk_monthly = _monthly(df_lk.get("creation", pd.Series()))

        # Current month
        now = datetime.now()
        current_month = f"{now.year}-{now.month:02d}"
        this_month_lp = int(lp_monthly.get(current_month, 0)) if current_month in lp_monthly.index else 0
        this_month_lk = int(lk_monthly.get(current_month, 0)) if current_month in lk_monthly.index else 0

        # ── KPI Cards ──
        with ui.row().classes("w-full gap-3 mb-6"):
            kpis = [
                ("📋 Total Leads", _fmt_num(total_leads), "#89b4fa"),
                ("🤝 Partnership", _fmt_num(total_lp), "#a6e3a1"),
                ("👥 Kemitraan", _fmt_num(total_lk), "#f9e2af"),
                ("📅 Bulan Ini", _fmt_num(this_month_lp + this_month_lk), "#cba6f7"),
            ]
            for lbl, val, color in kpis:
                with ui.card().classes("flex-1 min-w-[120px]").style(CARD):
                    ui.label(lbl).style(METRIC_LBL)
                    ui.label(val).style(METRIC_VAL)

        # ── Monthly Trend Chart ──
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label("📈 Tren Leads per Bulan").style(SECTION_T)
            _chart_monthly_trend(lp_monthly, lk_monthly)

        # ── Source Breakdown ──
        with ui.row().classes("w-full gap-4 mb-6"):
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📢 Sumber Info — Partnership").style(SECTION_T)
                _chart_source(df_lp, "source_lead", "Sumber")
            with ui.card().classes("flex-1").style(CARD):
                ui.label("📢 Tahu Difotoin Dari — Kemitraan").style(SECTION_T)
                _chart_source(df_lk, "dari_mana_tahu_difotoin", "Sumber Info")

        # ── Recent Leads Table ──
        with ui.expansion("📋 10 Leads Terbaru", icon="description").classes(
                "w-full mb-6").style("background: #1e1e2e; border-radius: 8px;"):
            _render_recent_leads(df_lp, df_lk)


def _chart_monthly_trend(lp_monthly: pd.Series, lk_monthly: pd.Series):
    """Stacked bar: Partnership + Kemitraan per month."""
    all_months = sorted(set(list(lp_monthly.index.astype(str)) + list(lk_monthly.index.astype(str))))
    if not all_months:
        ui.label("Belum ada data.").classes("text-gray-400 italic text-xs")
        return

    lp_vals = [int(lp_monthly.get(m, 0)) for m in all_months]
    lk_vals = [int(lk_monthly.get(m, 0)) for m in all_months]

    options = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": ["Partnership", "Kemitraan"], "textStyle": {"color": "#cdd6f4"}, "top": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": 40, "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": all_months,
            "axisLabel": {"color": "#a6adc8", "fontSize": 10, "rotate": 30},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [
            {"name": "Partnership", "type": "bar", "stack": "total",
             "data": lp_vals, "itemStyle": {"color": "#89b4fa"},
             "label": {"show": False}},
            {"name": "Kemitraan", "type": "bar", "stack": "total",
             "data": lk_vals, "itemStyle": {"color": "#f9e2af"},
             "label": {"show": False}},
        ],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[280px]")


def _chart_source(df: pd.DataFrame, col: str, label: str):
    """Top-N source bar chart."""
    if df.empty or col not in df.columns:
        ui.label("Belum ada data.").classes("text-gray-400 italic text-xs")
        return

    vals = df[col].dropna()
    if vals.empty:
        ui.label("Belum ada data.").classes("text-gray-400 italic text-xs")
        return

    counts = vals.value_counts().head(10)
    lbls = counts.index.tolist()
    data = counts.values.tolist()

    options = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": lbls,
            "axisLabel": {"color": "#a6adc8", "fontSize": 9, "rotate": 25},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [{
            "type": "bar",
            "data": data,
            "itemStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                                     "colorStops": [{"offset": 0, "color": "#89b4fa"},
                                                    {"offset": 1, "color": "#45475a"}]}},
            "barMaxWidth": 24,
            "label": {"show": True, "position": "top", "color": "#cdd6f4", "fontSize": 9},
        }],
        **_echart_opts(),
    }
    ui.echart(options).classes("w-full h-[220px]")


def _render_recent_leads(df_lp: pd.DataFrame, df_lk: pd.DataFrame):
    """Show 10 most recent leads from both sources combined."""
    rows = []

    if not df_lp.empty and "creation" in df_lp.columns:
        lp_recent = df_lp.sort_values("creation", ascending=False).head(10)
        for _, r in lp_recent.iterrows():
            rows.append({
                "type": "Partnership",
                "nama": str(r.get("nama_pic", "") or "").strip() or "-",
                "tempat": str(r.get("nama_tempat", "") or "").strip() or "-",
                "kota": str(r.get("kota_lokasi", "") or "").strip() or "-",
                "source": str(r.get("source_lead", "") or "").strip() or "-",
                "tgl": str(r.get("creation", "") or "")[:10],
            })

    if not df_lk.empty and "creation" in df_lk.columns:
        lk_recent = df_lk.sort_values("creation", ascending=False).head(10)
        for _, r in lk_recent.iterrows():
            nm = str(r.get("nama_lengkap", "") or "").strip() or str(r.get("lead_name", "") or "").strip() or "-"
            rows.append({
                "type": "Kemitraan",
                "nama": nm,
                "tempat": "-",
                "kota": str(r.get("kota_domisili", "") or "").strip() or "-",
                "source": str(r.get("dari_mana_tahu_difotoin", "") or str(r.get("source_lead", "") or "")).strip() or "-",
                "tgl": str(r.get("creation", "") or "")[:10],
            })

    # Sort by date descending, take top 10
    rows.sort(key=lambda x: x["tgl"], reverse=True)
    rows = rows[:10]

    if not rows:
        ui.label("Belum ada data.").classes("text-gray-400 italic text-xs")
        return

    columns = [
        {"name": "type", "label": "Tipe", "field": "type", "align": "left", "sortable": True},
        {"name": "nama", "label": "Nama", "field": "nama", "align": "left", "sortable": True},
        {"name": "tempat", "label": "Tempat", "field": "tempat", "align": "left", "sortable": True},
        {"name": "kota", "label": "Kota", "field": "kota", "align": "left", "sortable": True},
        {"name": "source", "label": "Sumber Info", "field": "source", "align": "left", "sortable": True},
        {"name": "tgl", "label": "Tanggal", "field": "tgl", "align": "left", "sortable": True},
    ]

    ui.table(
        rows=rows,
        columns=columns,
        pagination={"rowsPerPage": 10, "rowsNumber": len(rows)},
    ).classes("w-full").props("dark flat dense")


# ═══════════════════════════════════════════════════════════
#  TAB 2: OUTLET OPTIMASI
# ═══════════════════════════════════════════════════════════

def _render_optimasi(container: ui.column, df: pd.DataFrame):
    """Render the Outlet Optimasi tab."""
    with container:
        if df.empty:
            ui.label("Belum ada data outlet optimasi.").classes("text-gray-400 italic")
            ui.label("Pastikan dashboard_summary.json tersedia dan memiliki data outlet_status='Optimasi'.").classes(
                "text-xs text-gray-500")
            return

        # Determine last 3 months
        if "periode_dt" in df.columns:
            all_periods = sorted(df["periode"].unique())
            last_3 = all_periods[-3:] if len(all_periods) >= 3 else all_periods
        else:
            last_3 = []

        # Filter for last 3 months
        if last_3:
            df_filtered = df[df["periode"].isin(last_3)].copy()
        else:
            df_filtered = df.copy()

        if df_filtered.empty:
            ui.label("Tidak ada data untuk 3 bulan terakhir.").classes("text-gray-400 italic")
            return

        # ── KPI Cards ──
        total_outlet = df_filtered["outlet_name"].nunique()
        total_omset = float(df_filtered["total_revenue"].sum())
        avg_omset = total_omset / total_outlet if total_outlet > 0 else 0
        total_capture = int(df_filtered["foto_qty"].sum())
        len(last_3)

        with ui.row().classes("w-full gap-3 mb-6"):
            kpis = [
                ("🏪 Outlet Optimasi", _fmt_num(total_outlet), "#89b4fa"),
                ("💰 Total Omzet (3 bln)", _fmt_rp(total_omset), "#a6e3a1"),
                ("📊 Rata-rata/Outlet", _fmt_rp(avg_omset), "#f9e2af"),
                ("📷 Total Capture", _fmt_num(total_capture), "#cba6f7"),
                ("📅 Bulan", " / ".join(last_3), "#f38ba8"),
            ]
            for lbl, val, color in kpis:
                with ui.card().classes("flex-1 min-w-[100px]").style(CARD):
                    ui.label(lbl).style(METRIC_LBL)
                    ui.label(val).style(METRIC_VAL)

        # ── Revenue Trend per Outlet ──
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label(f"📈 Tren Omzet 3 Bulan — {total_outlet} Outlet Optimasi").style(SECTION_T)
            _chart_optimasi_trend(df_filtered, last_3)

        # ── Outlet Detail Table ──
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label("🏪 Daftar Outlet Optimasi — Omzet 3 Bulan").style(SECTION_T)
            _render_outlet_table(df_filtered, last_3)


def _chart_optimasi_trend(df: pd.DataFrame, periods: list):
    """Grouped bar chart: omzet per outlet per month (top 15 outlets)."""
    if df.empty or not periods:
        ui.label("Belum ada data.").classes("text-gray-400 italic text-xs")
        return

    # Get top 15 outlets by total revenue
    outlet_totals = df.groupby("outlet_name")["total_revenue"].sum().sort_values(ascending=False)
    top_outlets = outlet_totals.head(15).index.tolist()

    chart_df = df[df["outlet_name"].isin(top_outlets)].copy()

    if chart_df.empty:
        ui.label("Belum ada data.").classes("text-gray-400 italic text-xs")
        return

    colors = ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7"]

    # Build series: one bar group per outlet per period
    options = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": periods, "textStyle": {"color": "#cdd6f4"}, "top": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": 40, "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": top_outlets,
            "axisLabel": {"color": "#a6adc8", "fontSize": 9, "rotate": 35},
            "axisLine": {"lineStyle": {"color": "#45475a"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a6adc8", "formatter": "Rp{value}"},
            "splitLine": {"lineStyle": {"color": "#313244"}},
        },
        "series": [
            {
                "name": p,
                "type": "bar",
                "data": [
                    float(chart_df.loc[(chart_df["outlet_name"] == o) & (chart_df["periode"] == p), "total_revenue"].sum())
                    for o in top_outlets
                ],
                "itemStyle": {"color": colors[i % len(colors)]},
                "label": {"show": False},
            }
            for i, p in enumerate(periods)
        ],
        **_echart_opts(),
    }

    ui.echart(options).classes("w-full h-[320px]")


def _render_outlet_table(df: pd.DataFrame, periods: list):
    """AG Grid: outlet list with omzet per month + total."""
    if df.empty:
        ui.label("Belum ada data.").classes("text-gray-400 italic text-xs")
        return

    # Aggregate per outlet per period
    pivot = df.pivot_table(
        index="outlet_name",
        columns="periode",
        values="total_revenue",
        aggfunc="sum",
        fill_value=0,
    )

    # Reindex to include all periods
    for p in periods:
        if p not in pivot.columns:
            pivot[p] = 0
    pivot = pivot[periods]

    # Add total column
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False).reset_index()
    pivot.columns = ["outlet_name"] + periods + ["Total"]

    # Format currency
    def _rp(v):
        return _fmt_rp(float(v))

    grid_rows = []
    for _, r in pivot.iterrows():
        row = {"Outlet": str(r["outlet_name"]).strip()}
        for p in periods:
            row[p] = _rp(r[p])
        row["Total"] = _rp(r["Total"])
        grid_rows.append(row)

    # Add tot
    totals = {"Outlet": "🔥 TOTAL"}
    for p in periods:
        totals[p] = _rp(float(pivot[p].sum()))
    totals["Total"] = _rp(float(pivot["Total"].sum()))
    grid_rows.append(totals)

    # Column defs
    col_defs = [
        {"headerName": "Outlet", "field": "Outlet", "pinned": "left",
         "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True,
         "minWidth": 200, "flex": 2,
         "cellStyle": {"fontWeight": "600", "color": "#cdd6f4"}},
    ]
    for p in periods:
        col_defs.append({
            "headerName": p, "field": p,
            "sortable": True, "filter": "agNumberColumnFilter",
            "width": 130, "type": "rightAligned",
        })
    col_defs.append({
        "headerName": "💵 Total", "field": "Total",
        "sortable": True, "pinned": "right",
        "width": 150, "type": "rightAligned",
        "cellStyle": {"fontWeight": "700", "color": "#a6e3a1"},
    })

    ui.add_head_html("""<style>
.ag-theme-balham-dark {
    --ag-background-color: #1e1e2e; --ag-header-background-color: #181825;
    --ag-odd-row-background-color: #1a1a2e; --ag-row-hover-color: #313244;
    --ag-border-color: #313244; --ag-font-size: 13px;
    --ag-header-height: 44px; --ag-row-height: 40px;
}
</style>""")

    ui.aggrid({
        "columnDefs": col_defs,
        "rowData": grid_rows,
        "pagination": True,
        "paginationPageSize": 25,
        "paginationPageSizeSelector": [10, 25, 50, 100],
        "domLayout": "autoHeight",
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "animateRows": True,
        "rowHeight": 40,
        "headerHeight": 44,
        "enableCellTextSelection": True,
    }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 300px;")
