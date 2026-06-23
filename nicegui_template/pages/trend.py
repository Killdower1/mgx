"""
📈 Trend Analysis — trend analysis v1/v2, AI insights.
Port of Streamlit's page_modules/trend.py to NiceGUI.
"""
import sys
from pathlib import Path
from typing import List, Optional, Dict

from nicegui import ui
import pandas as pd
import numpy as np
import plotly.express as px

# Config type — imported from streamlit_template (added to sys.path by dashboard_adapter)
from config import Config

# Import build_ai_trend_insights from streamlit_template — inline copy (pure Python, no streamlit deps)
def build_ai_trend_insights(base: pd.DataFrame, periods: List[str], config: Config) -> Dict[str, object]:
    """Generate local AI-style analysis from the selected trend data."""
    if base.empty or not periods:
        return {
            "summary": ["Data pada range periode ini belum cukup untuk dianalisis."],
            "findings": [], "actions": ["Coba perluas range periode atau cek filter sidebar."],
            "decisions": [], "risks": [], "experiments": [],
            "priority_outlets": pd.DataFrame(),
        }

    latest_period = periods[-1]
    previous_period = periods[-2] if len(periods) > 1 else None
    latest_df = base[base["periode"].astype(str) == latest_period].copy()
    previous_df = base[base["periode"].astype(str) == previous_period].copy() if previous_period else pd.DataFrame()

    def sum_col(frame, col):
        return float(pd.to_numeric(frame.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

    def pct_change(now, prev):
        return ((now - prev) / prev * 100) if prev > 0 else None

    def fmt_pct(value):
        return "-" if value is None or pd.isna(value) else f"{value:+.1f}%"

    monthly = base.groupby("periode", as_index=False).agg(
        total_revenue=("total_revenue", "sum"), foto_qty=("foto_qty", "sum"),
        print_qty=("print_qty", "sum"), outlet_count=("outlet_name", "nunique"),
    )
    monthly["conversion_rate"] = np.where(monthly["foto_qty"] > 0, monthly["print_qty"] / monthly["foto_qty"] * 100, 0)
    monthly["periode"] = pd.Categorical(monthly["periode"].astype(str), categories=periods, ordered=True)
    monthly = monthly.sort_values("periode")
    monthly["revenue_change"] = monthly["total_revenue"].diff()
    monthly["conversion_change"] = monthly["conversion_rate"].diff()

    latest_revenue = sum_col(latest_df, "total_revenue")
    previous_revenue = sum_col(previous_df, "total_revenue")
    revenue_delta = pct_change(latest_revenue, previous_revenue)
    avg_monthly = float(monthly["total_revenue"].mean()) if not monthly.empty else 0.0
    best_month = monthly.sort_values("total_revenue", ascending=False).head(1)
    weakest_month = monthly.sort_values("total_revenue", ascending=True).head(1)

    all_outlets = set(base["outlet_name"].dropna().astype(str).str.strip())
    latest_outlets = set(latest_df["outlet_name"].dropna().astype(str).str.strip())
    inactive_count = len(all_outlets - latest_outlets)

    area_summary = pd.DataFrame()
    if "area" in base.columns:
        area_summary = base.groupby("area", as_index=False).agg(total_revenue=("total_revenue", "sum"), outlet_count=("outlet_name", "nunique"))
        area_summary["revenue_per_outlet"] = area_summary["total_revenue"] / area_summary["outlet_count"].replace(0, np.nan)
        area_summary = area_summary.sort_values("total_revenue", ascending=False)

    category_summary = pd.DataFrame()
    if "kategori_tempat" in base.columns:
        category_summary = base.groupby("kategori_tempat", as_index=False).agg(total_revenue=("total_revenue", "sum"), outlet_count=("outlet_name", "nunique")).sort_values("total_revenue", ascending=False)

    top_area = area_summary.head(1).iloc[0] if not area_summary.empty else None
    low_area = area_summary[area_summary["total_revenue"] > 0].tail(1).iloc[0] if not area_summary.empty and (area_summary["total_revenue"] > 0).any() else None
    top_category = category_summary.head(1).iloc[0] if not category_summary.empty else None

    outlet_period = base.groupby(["outlet_name", "periode"], as_index=False).agg(total_revenue=("total_revenue", "sum"), foto_qty=("foto_qty", "sum"), print_qty=("print_qty", "sum"))
    outlet_pivot = outlet_period.pivot_table(index="outlet_name", columns="periode", values="total_revenue", aggfunc="sum", fill_value=0)
    movers = pd.DataFrame()
    if latest_period in outlet_pivot.columns:
        movers = pd.DataFrame({"outlet_name": outlet_pivot.index, "latest_revenue": outlet_pivot[latest_period].values})
        if previous_period and previous_period in outlet_pivot.columns:
            movers["previous_revenue"] = outlet_pivot[previous_period].values
        else:
            movers["previous_revenue"] = 0.0
        movers["growth_value"] = movers["latest_revenue"] - movers["previous_revenue"]
        movers = movers.sort_values("growth_value", ascending=False)

    outlet_summary = base.groupby("outlet_name", as_index=False).agg(
        total_revenue=("total_revenue", "sum"), avg_revenue=("total_revenue", "mean"),
        foto_qty=("foto_qty", "sum"), print_qty=("print_qty", "sum"),
        active_months=("periode", "nunique"),
    )
    outlet_summary["conversion_rate"] = np.where(outlet_summary["foto_qty"] > 0, outlet_summary["print_qty"] / outlet_summary["foto_qty"] * 100, 0)
    outlet_summary["revenue_per_active_month"] = outlet_summary["total_revenue"] / outlet_summary["active_months"].replace(0, np.nan)
    outlet_summary["status_ai"] = "Monitor"
    outlet_summary.loc[(outlet_summary["total_revenue"] > 0) & (outlet_summary["conversion_rate"] < 12), "status_ai"] = "Traffic ada, conversion rendah"
    outlet_summary.loc[(outlet_summary["revenue_per_active_month"] >= outlet_summary["revenue_per_active_month"].quantile(0.80)), "status_ai"] = "Scale / benchmark"
    outlet_summary.loc[outlet_summary["active_months"] <= max(1, len(periods) // 4), "status_ai"] = "Seasonal / belum stabil"
    priority_outlets = outlet_summary.sort_values(["total_revenue", "conversion_rate", "active_months"], ascending=[False, True, False]).head(12).copy()

    summary = [
        f"Range analisis: {periods[0]} sampai {periods[-1]} dengan {len(periods)} periode data.",
        f"Omzet periode terakhir {latest_period} adalah {config.format_currency(latest_revenue)}, dibanding periode sebelumnya: {fmt_pct(revenue_delta)}.",
        f"Rata-rata omzet bulanan pada range ini sekitar {config.format_currency(avg_monthly)}.",
    ]
    if not best_month.empty and not weakest_month.empty:
        summary.append(f"Bulan terkuat adalah {str(best_month.iloc[0]['periode'])} ({config.format_currency(float(best_month.iloc[0]['total_revenue']))}) dan bulan terlemah adalah {str(weakest_month.iloc[0]['periode'])} ({config.format_currency(float(weakest_month.iloc[0]['total_revenue']))}).")

    findings = []
    if top_area is not None:
        findings.append(f"Area terbesar adalah {top_area['area']} dengan kontribusi omzet {config.format_currency(float(top_area['total_revenue']))} dari {int(top_area['outlet_count'])} outlet.")
    if low_area is not None and top_area is not None and low_area['area'] != top_area['area']:
        findings.append(f"Area yang perlu dicek lebih lanjut: {low_area['area']} karena omzetnya paling rendah.")
    if top_category is not None:
        findings.append(f"Kategori paling kuat saat ini adalah {top_category['kategori_tempat']} dengan omzet {config.format_currency(float(top_category['total_revenue']))}.")
    if inactive_count > 0:
        findings.append(f"{inactive_count} outlet tidak aktif pada periode terakhir.")
    if not movers.empty:
        top_up = movers.head(1).iloc[0]
        top_down = movers.tail(1).iloc[0]
        findings.append(f"Outlet dengan kenaikan nominal terbesar: {top_up['outlet_name']} ({config.format_currency(float(top_up['growth_value']))}).")
        if float(top_down['growth_value']) < 0:
            findings.append(f"Outlet dengan penurunan terdalam: {top_down['outlet_name']} ({config.format_currency(float(top_down['growth_value']))}).")

    actions = []
    if revenue_delta is not None and revenue_delta < -10:
        actions.append("Prioritaskan audit outlet yang turun pada periode terakhir.")
    elif revenue_delta is not None and revenue_delta > 10:
        actions.append("Duplikasi pola dari outlet/area yang naik: cek promo, placement, timing.")
    else:
        actions.append("Fokuskan eksperimen pada outlet dengan conversion rendah tetapi traffic foto tinggi.")
    if inactive_count > 0:
        actions.append("Buat label operasional untuk outlet tidak aktif.")
    if top_area is not None:
        actions.append(f"Gunakan area {top_area['area']} sebagai benchmark.")
    actions.append("Untuk keputusan ekspansi, pakai metrik omzet per outlet dan conversion.")

    decisions, risks, experiments = [], [], []
    recent_months = monthly.tail(min(3, len(monthly)))
    recent_revenue_slope = float(recent_months["revenue_change"].fillna(0).sum()) if not recent_months.empty else 0.0
    recent_conv_slope = float(recent_months["conversion_change"].fillna(0).sum()) if not recent_months.empty else 0.0

    if revenue_delta is not None and revenue_delta > 15 and recent_revenue_slope > 0:
        decisions.append("Mode offense: ada momentum naik.")
    elif revenue_delta is not None and revenue_delta < -15:
        decisions.append("Mode defense: tahan ekspansi, audit outlet turun.")
    else:
        decisions.append("Mode selective growth.")

    if inactive_count > max(5, len(all_outlets) * 0.25):
        risks.append("Banyak outlet tidak aktif.")
    if recent_conv_slope < -2:
        risks.append("Conversion melemah.")
    if top_area is not None and len(area_summary) > 1:
        top_share = float(top_area["total_revenue"]) / float(area_summary["total_revenue"].sum()) if float(area_summary["total_revenue"].sum()) > 0 else 0
        if top_share > 0.45:
            risks.append("Omzet terlalu terkonsentrasi di satu area.")
    if not risks:
        risks.append("Tidak ada risiko ekstrem dari range ini.")

    experiments.append("Pilih 5 outlet omzet tinggi tetapi conversion di bawah median, test script upsell selama 2 minggu.")
    experiments.append("Bandingkan outlet indoor vs outdoor untuk placement terbaik.")
    experiments.append("Pisahkan target KPI outlet event/seasonal dari outlet permanen.")

    return {"summary": summary, "findings": findings, "actions": actions, "decisions": decisions,
            "risks": risks, "experiments": experiments, "priority_outlets": priority_outlets}

from services.dashboard_adapter import get_adapter

# ── Styling constants ──
CARD = 'background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);'
METRIC_VAL = 'font-size: 1.2rem; font-weight: 700; color: #cdd6f4;'
METRIC_LBL = 'font-size: 0.75rem; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px;'
SECTION_T = 'font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;'
DELTA_UP = 'font-size: 0.85rem; color: #a6e3a1; font-weight: 500;'
DELTA_DOWN = 'font-size: 0.85rem; color: #f38ba8; font-weight: 500;'
DELTA_FLAT = 'font-size: 0.85rem; color: #a6adc8; font-weight: 500;'


# ── Helpers ──

def _sort_periods_str(periods: List[str]) -> List[str]:
    """Sort period strings like '2024-01' chronologically."""
    s = pd.Series(periods, dtype=object)
    dt = pd.to_datetime(s, format="%Y-%m", errors="coerce")
    helper = pd.DataFrame({"p": s, "dt": dt}).sort_values(by=["dt", "p"], na_position="last")
    return helper["p"].astype(str).tolist()


def _sum_col(frame: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(frame.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())


def _conversion(frame: pd.DataFrame) -> float:
    foto = _sum_col(frame, "foto_qty")
    printed = _sum_col(frame, "print_qty")
    return (printed / foto * 100) if foto > 0 else 0.0


def _fmt_delta(val) -> str:
    if val is None or pd.isna(val):
        return "–"
    return f"{val:+.1f}%" if isinstance(val, float) else str(val)


def _render_table(df, max_rows=100):
    """Render ui.table from DataFrame."""
    if df.empty:
        ui.label("(kosong)").classes("text-gray-400 italic text-xs")
        return
    cols = [{"name": c, "label": c, "field": c, "align": "left"} for c in df.columns]
    ui.table(
        rows=df.head(max_rows).to_dict("records"),
        columns=cols,
        pagination={"rowsPerPage": 15, "rowsNumber": min(len(df), max_rows)},
    ).classes("w-full").props("dark flat dense")


def _render_kpi_card(label: str, value: str, delta: Optional[str] = None, delta_dir: str = "up"):
    """Render a KPI metric card."""
    with ui.card().classes("flex-1 min-w-[150px]").style(CARD):
        ui.label(label).style(METRIC_LBL)
        ui.label(value).style(METRIC_VAL)
        if delta:
            style = DELTA_UP if delta_dir == "up" else DELTA_DOWN if delta_dir == "down" else DELTA_FLAT
            ui.label(delta).style(style)


# ── Page ──

def create_page(container: ui.column):
    """Build the Trend Analysis page."""
    adapter = get_adapter()
    df = adapter.load_data()

    container.clear()
    with container:
        ui.label('📈 Analisis Trend Penjualan').classes('text-2xl font-bold text-white mb-4')

        if df.empty:
            ui.label('❌ Data tidak tersedia.').classes('text-red-400')
            return

        # ── Prepare base data ──
        base = df.copy(deep=True)
        for col in ["total_revenue", "foto_qty", "unlock_qty", "print_qty", "conversion_rate"]:
            if col in base.columns:
                base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0.0)
        base["periode"] = base["periode"].astype(str)

        # ── Periods ──
        raw_periods = base["periode"].dropna().unique().tolist() if "periode" in base.columns else []
        periods = _sort_periods_str(raw_periods) if raw_periods else []
        if not periods:
            ui.label('❌ Data periode tidak tersedia.').classes('text-red-400')
            return

        # ── Period range selector ──
        default_start_idx = max(0, len(periods) - 12)

        with ui.row().classes("w-full gap-4 items-center mb-4"):
            start_sel = ui.select(
                periods, value=periods[default_start_idx], label="Periode Mulai"
            ).props("dense outlined dark").classes("flex-1")
            end_sel = ui.select(
                periods, value=periods[-1], label="Periode Akhir"
            ).props("dense outlined dark").classes("flex-1")
            info_label = ui.label("").classes("text-sm text-gray-400 flex-1")

        # ── Content area (refreshed on period change) ──
        content = ui.column().classes("w-full")

        def update_content():
            """Rebuild all charts and tables based on selected period range."""
            content.clear()
            sp = start_sel.value
            ep = end_sel.value
            if not sp or not ep:
                with content:
                    ui.label("Pilih periode mulai dan akhir.").classes("text-gray-400 italic")
                return

            start_idx = periods.index(sp)
            end_idx = periods.index(ep)
            if start_idx > end_idx:
                with content:
                    ui.label("⚠️ Periode mulai tidak boleh lebih baru dari periode akhir.").classes("text-yellow-400")
                return

            selected_periods = periods[start_idx:end_idx + 1]
            filtered = base[base["periode"].isin(selected_periods)].copy()
            local_periods = selected_periods

            latest_period = local_periods[-1] if local_periods else None
            previous_period = local_periods[-2] if len(local_periods) > 1 else None
            latest_df = filtered[filtered["periode"] == latest_period].copy() if latest_period else filtered.copy()
            previous_df = filtered[filtered["periode"] == previous_period].copy() if previous_period else pd.DataFrame()

            # Compute KPIs
            revenue_now = _sum_col(latest_df, "total_revenue")
            revenue_prev = _sum_col(previous_df, "total_revenue")
            revenue_delta = ((revenue_now - revenue_prev) / revenue_prev * 100) if revenue_prev > 0 else None
            conv_now = _conversion(latest_df)
            conv_prev = _conversion(previous_df)
            conv_delta = conv_now - conv_prev if previous_period else None
            outlet_count = latest_df["outlet_name"].nunique() if "outlet_name" in latest_df.columns else 0

            info_label.set_text(f"Analisis memakai {len(local_periods)} periode: {sp} sampai {ep}.")

            # Build monthly aggregation
            monthly = (
                filtered.groupby("periode", as_index=False)
                .agg(
                    total_revenue=("total_revenue", "sum"),
                    foto_qty=("foto_qty", "sum"),
                    unlock_qty=("unlock_qty", "sum"),
                    print_qty=("print_qty", "sum"),
                    outlet_count=("outlet_name", "nunique"),
                )
            )
            monthly["conversion_rate"] = np.where(monthly["foto_qty"] > 0, monthly["print_qty"] / monthly["foto_qty"] * 100, 0)
            monthly["periode"] = pd.Categorical(monthly["periode"], categories=local_periods, ordered=True)
            monthly = monthly.sort_values("periode")

            # Build AI insights
            ai_insights = build_ai_trend_insights(filtered.copy(), local_periods, adapter.config)

            with content:
                # ── KPI Cards ──
                with ui.row().classes("w-full gap-4 mb-6"):
                    _render_kpi_card("Periode Terbaru", latest_period or "–")

                    delta_str = _fmt_delta(revenue_delta)
                    delta_dir = "up" if (revenue_delta is not None and revenue_delta > 0) else "down" if (revenue_delta is not None and revenue_delta < 0) else "flat"
                    _render_kpi_card("Omzet", adapter.format_currency(revenue_now),
                                     delta=delta_str if revenue_delta is not None else None,
                                     delta_dir=delta_dir)

                    _render_kpi_card("Outlet Aktif", f"{outlet_count:,}")

                    conv_str = f"{conv_now:.1f}%"
                    conv_delta_str = f"{conv_delta:+.1f}pp" if conv_delta is not None else None
                    conv_dir = "up" if (conv_delta is not None and conv_delta > 0) else "down" if (conv_delta is not None and conv_delta < 0) else "flat"
                    _render_kpi_card("Conversion", conv_str,
                                     delta=conv_delta_str if conv_delta is not None else None,
                                     delta_dir=conv_dir)

                ui.separator().classes("mb-4")

                # ── Tabs ──
                tabs = ui.tabs().classes("w-full")
                panels = ui.tab_panels(tabs, value="overview").classes("w-full")
                with tabs:
                    ui.tab("overview", label="📊 Overview")
                    ui.tab("segments", label="🏘️ Area & Category")
                    ui.tab("outlets", label="🏪 Outlet Movers")
                    ui.tab("heatmap", label="🔥 Heatmap")
                    ui.tab("ai", label="🤖 AI Insight")

                with panels:
                    # ════════════════════════════
                    # TAB 1: Overview
                    # ════════════════════════════
                    with ui.tab_panel("overview"):
                        # Line charts row
                        with ui.row().classes("w-full gap-4"):
                            with ui.card().classes("flex-1").style(CARD):
                                fig_rev = px.line(
                                    monthly, x="periode", y="total_revenue",
                                    markers=True, title="Monthly Revenue Trend"
                                )
                                fig_rev.update_traces(
                                    line_color="#89b4fa",
                                    hovertemplate="%{x}<br>Revenue: Rp %{y:,.0f}<extra></extra>"
                                )
                                fig_rev.update_layout(
                                    height=400,
                                    yaxis_title="Revenue",
                                    xaxis_title="Periode",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font_color="#cdd6f4",
                                    xaxis={"gridcolor": "#313244"},
                                    yaxis={"gridcolor": "#313244"},
                                )
                                ui.plotly(fig_rev).classes("w-full h-[400px]")

                            with ui.card().classes("flex-1").style(CARD):
                                fig_conv = px.line(
                                    monthly, x="periode", y="conversion_rate",
                                    markers=True, title="Conversion Trend"
                                )
                                fig_conv.update_traces(
                                    line_color="#a6e3a1",
                                    hovertemplate="%{x}<br>Conversion: %{y:.1f}%<extra></extra>"
                                )
                                fig_conv.update_layout(
                                    height=400,
                                    yaxis_title="Conversion %",
                                    xaxis_title="Periode",
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    font_color="#cdd6f4",
                                    xaxis={"gridcolor": "#313244"},
                                    yaxis={"gridcolor": "#313244"},
                                )
                                ui.plotly(fig_conv).classes("w-full h-[400px]")

                        # Monthly summary table
                        ui.label("📋 Monthly Summary").classes("text-lg font-semibold text-white mt-6 mb-3")
                        monthly_display = monthly.copy()
                        monthly_display["total_revenue"] = monthly_display["total_revenue"].apply(adapter.format_currency)
                        monthly_display["conversion_rate"] = monthly_display["conversion_rate"].apply(lambda x: f"{x:.1f}%")
                        monthly_display = monthly_display.rename(columns={
                            "periode": "Periode", "total_revenue": "Omzet",
                            "foto_qty": "Foto", "unlock_qty": "Unlock",
                            "print_qty": "Print", "outlet_count": "Outlet",
                            "conversion_rate": "Conversion",
                        })
                        _render_table(monthly_display)

                    # ════════════════════════════
                    # TAB 2: Area & Category
                    # ════════════════════════════
                    with ui.tab_panel("segments"):
                        # Charts row
                        with ui.row().classes("w-full gap-4"):
                            with ui.card().classes("flex-1").style(CARD):
                                ui.plotly(adapter.viz.create_area_analysis_chart(filtered)).classes("w-full h-[400px]")
                            with ui.card().classes("flex-1").style(CARD):
                                ui.plotly(adapter.viz.create_indoor_outdoor_comparison(filtered)).classes("w-full h-[400px]")

                        # Summary tables row
                        with ui.row().classes("w-full gap-4 mt-4"):
                            with ui.column().classes("flex-1"):
                                ui.label("📋 Summary by Area").style(SECTION_T)
                                area_summary = adapter.processor.aggregate_by_area(filtered.copy()).reset_index()
                                if not area_summary.empty:
                                    area_summary["revenue_per_outlet"] = area_summary["total_revenue"] / area_summary["outlet_count"].replace(0, np.nan)
                                    area_summary["total_revenue"] = area_summary["total_revenue"].apply(adapter.format_currency)
                                    area_summary["revenue_per_outlet"] = area_summary["revenue_per_outlet"].fillna(0).apply(adapter.format_currency)
                                _render_table(area_summary)

                            with ui.column().classes("flex-1"):
                                ui.label("📋 Summary by Category").style(SECTION_T)
                                kategori_summary = adapter.processor.aggregate_by_kategori(filtered.copy()).reset_index()
                                if not kategori_summary.empty:
                                    kategori_summary["revenue_per_outlet"] = kategori_summary["total_revenue"] / kategori_summary["outlet_count"].replace(0, np.nan)
                                    kategori_summary["total_revenue"] = kategori_summary["total_revenue"].apply(adapter.format_currency)
                                    kategori_summary["revenue_per_outlet"] = kategori_summary["revenue_per_outlet"].fillna(0).apply(adapter.format_currency)
                                _render_table(kategori_summary)

                        # Category analysis chart
                        with ui.card().classes("w-full mt-4").style(CARD):
                            ui.plotly(adapter.viz.create_kategori_analysis(filtered)).classes("w-full h-[400px]")

                    # ════════════════════════════
                    # TAB 3: Outlet Movers
                    # ════════════════════════════
                    with ui.tab_panel("outlets"):
                        if latest_period and not latest_df.empty and previous_period:
                            # Profit section
                            profit_source = latest_df.groupby("outlet_name", as_index=False).agg(
                                total_revenue=("total_revenue", "sum"),
                                foto_qty=("foto_qty", "sum"),
                                unlock_qty=("unlock_qty", "sum"),
                                print_qty=("print_qty", "sum"),
                            )
                            mapping_profit = (
                                adapter.processor.load_outlet_mapping()
                                if hasattr(adapter.processor, "load_outlet_mapping")
                                else pd.DataFrame()
                            )

                            # Import needed helpers from streamlit_template
                            try:
                                from app import apply_sharing_to_mapping, add_profit_columns
                                mapping_profit = apply_sharing_to_mapping(mapping_profit, latest_period)
                                profit_cols = [
                                    "outlet_name", "area", "partner_share", "broker_share",
                                    "sharing_bagi_hasil", "monthly_rent", "minimum_payment",
                                ]
                                if not mapping_profit.empty and "outlet_name" in mapping_profit.columns:
                                    profit_source = profit_source.merge(
                                        mapping_profit[[c for c in profit_cols if c in mapping_profit.columns]],
                                        on="outlet_name",
                                        how="left",
                                    )
                                profit_source = add_profit_columns(profit_source)
                                top_profit = profit_source.sort_values("estimasi_profit_difotoin", ascending=False).head(10).copy()
                                if not top_profit.empty:
                                    ui.label(f"🏆 Outlet Paling Menguntungkan — {latest_period}").style(SECTION_T)
                                    show_profit = top_profit[[
                                        c for c in [
                                            "outlet_name", "area", "basis_bagi_hasil", "sharing_bagi_hasil",
                                            "pendapatan_operator", "monthly_rent", "estimasi_profit_difotoin",
                                            "foto_qty", "unlock_qty", "print_qty",
                                        ] if c in top_profit.columns
                                    ]].copy()
                                    for col in ["basis_bagi_hasil", "pendapatan_operator", "monthly_rent", "estimasi_profit_difotoin"]:
                                        if col in show_profit.columns:
                                            show_profit[col] = show_profit[col].apply(
                                                lambda x: adapter.format_currency(float(x)) if pd.notna(x) and float(x) > 0 else "-"
                                            )
                                    if "sharing_bagi_hasil" in show_profit.columns:
                                        show_profit["sharing_bagi_hasil"] = show_profit["sharing_bagi_hasil"].apply(
                                            lambda x: "-" if pd.isna(x) else f"{float(x)*100:.1f}%"
                                        )
                                    show_profit = show_profit.rename(columns={
                                        "outlet_name": "Outlet", "area": "Area",
                                        "basis_bagi_hasil": "Basis Bagi Hasil",
                                        "sharing_bagi_hasil": "Share Difotoin",
                                        "pendapatan_operator": "Bagi Hasil Difotoin",
                                        "monthly_rent": "Monthly Rent",
                                        "estimasi_profit_difotoin": "Estimasi Profit",
                                        "foto_qty": "Foto", "unlock_qty": "Unlock", "print_qty": "Print",
                                    })
                                    _render_table(show_profit)
                                    ui.separator().classes("my-4")
                            except ImportError:
                                # Profit section optional
                                pass

                            # Outlet movers
                            outlet_period = (
                                filtered.groupby(["outlet_name", "periode"], as_index=False)
                                .agg(total_revenue=("total_revenue", "sum"), foto_qty=("foto_qty", "sum"), print_qty=("print_qty", "sum"))
                            )
                            outlet_pivot = outlet_period.pivot_table(
                                index="outlet_name", columns="periode",
                                values="total_revenue", aggfunc="sum", fill_value=0
                            )

                            if latest_period in outlet_pivot.columns:
                                movers = pd.DataFrame({"outlet_name": outlet_pivot.index, "latest_revenue": outlet_pivot[latest_period].values})
                                if previous_period and previous_period in outlet_pivot.columns:
                                    movers["previous_revenue"] = outlet_pivot[previous_period].values
                                    movers["growth_value"] = movers["latest_revenue"] - movers["previous_revenue"]
                                    movers["growth_pct"] = np.where(
                                        movers["previous_revenue"] > 0,
                                        movers["growth_value"] / movers["previous_revenue"] * 100,
                                        np.nan,
                                    )
                                else:
                                    movers["previous_revenue"] = 0.0
                                    movers["growth_value"] = movers["latest_revenue"]
                                    movers["growth_pct"] = np.nan

                                top_latest = movers.sort_values("latest_revenue", ascending=False).head(15).copy()
                                top_up = movers.sort_values("growth_value", ascending=False).head(10).copy()
                                top_down = movers.sort_values("growth_value", ascending=True).head(10).copy()

                                for tbl in [top_latest, top_up, top_down]:
                                    tbl["latest_revenue"] = tbl["latest_revenue"].apply(adapter.format_currency)
                                    tbl["previous_revenue"] = tbl["previous_revenue"].apply(adapter.format_currency)
                                    tbl["growth_value"] = tbl["growth_value"].apply(adapter.format_currency)
                                    tbl["growth_pct"] = tbl["growth_pct"].apply(lambda x: "-" if pd.isna(x) else f"{x:+.1f}%")

                                col_labels = {
                                    "outlet_name": "Outlet",
                                    "latest_revenue": "Omzet Terbaru",
                                    "previous_revenue": "Omzet Sebelumnya",
                                    "growth_value": "Growth (Rp)",
                                    "growth_pct": "Growth (%)",
                                }
                                for tbl in [top_latest, top_up, top_down]:
                                    tbl.rename(columns=col_labels, inplace=True)

                                with ui.row().classes("w-full gap-4"):
                                    with ui.column().classes("flex-1"):
                                        ui.label(f"🏪 Top Outlet — {latest_period}").style(SECTION_T)
                                        _render_table(top_latest)
                                    with ui.column().classes("flex-1"):
                                        ui.label("🚀 Biggest Growth").style(SECTION_T)
                                        _render_table(top_up)

                                ui.label("⚠️ Needs Attention").style(SECTION_T)
                                _render_table(top_down)
                            else:
                                ui.label("Data outlet per periode belum cukup untuk menghitung movers.").classes("text-gray-400 italic")
                        else:
                            ui.label("Perlu dua periode berbeda untuk analisis Outlet Movers.").classes("text-gray-400 italic")

                    # ════════════════════════════
                    # TAB 4: Heatmap
                    # ════════════════════════════
                    with ui.tab_panel("heatmap"):
                        with ui.card().classes("w-full").style(CARD):
                            ui.plotly(adapter.viz.create_heatmap(filtered)).classes("w-full h-[450px]")
                        ui.label("🔥 Heatmap membantu melihat kombinasi area dan kategori yang paling kuat atau perlu diperbaiki.").classes(
                            "text-xs text-gray-400 mt-2 italic"
                        )

                    # ════════════════════════════
                    # TAB 5: AI Insight
                    # ════════════════════════════
                    with ui.tab_panel("ai"):
                        ui.label("🧠 AI Insight").classes("text-lg font-semibold text-white mb-2")
                        ui.label(
                            "Analisis otomatis dari data dan filter periode yang sedang dipilih. "
                            "Fokusnya membantu keputusan founder, bukan hanya membaca chart."
                        ).classes("text-xs text-gray-400 mb-4 italic")

                        # Decision Brief
                        decisions = ai_insights.get("decisions", [])
                        if decisions:
                            ui.label("⚡ Decision Brief").style(SECTION_T)
                            for item in decisions:
                                with ui.card().classes("w-full mb-2 p-3").style("background-color: rgba(166, 227, 161, 0.1); border-left: 4px solid #a6e3a1;"):
                                    ui.label(item).classes("text-sm text-white")

                        # Executive Summary
                        ui.label("📄 Executive Summary").style(SECTION_T)
                        summary = ai_insights.get("summary", [])
                        if summary:
                            for item in summary:
                                ui.label(f"• {item}").classes("text-sm text-gray-300 mb-1")
                        else:
                            ui.label("Data pada range periode ini belum cukup untuk dianalisis.").classes("text-gray-400 italic")

                        # Findings
                        ui.label("🔍 Temuan Penting").style(SECTION_T)
                        findings = ai_insights.get("findings", [])
                        if findings:
                            for item in findings:
                                ui.label(f"• {item}").classes("text-sm text-gray-300 mb-1")
                        else:
                            ui.label("Belum ada temuan kuat dari range periode ini.").classes("text-gray-400 italic")

                        # Actions + Risks side by side
                        with ui.row().classes("w-full gap-4"):
                            with ui.column().classes("flex-1"):
                                ui.label("✅ Rekomendasi Aksi").style(SECTION_T)
                                actions = ai_insights.get("actions", [])
                                if actions:
                                    for idx, item in enumerate(actions, start=1):
                                        with ui.card().classes("w-full mb-1 p-2").style("background-color: rgba(137, 180, 250, 0.08); border-left: 3px solid #89b4fa;"):
                                            ui.label(f"{idx}. {item}").classes("text-sm text-gray-300")
                                else:
                                    ui.label("—").classes("text-gray-400 italic")

                            with ui.column().classes("flex-1"):
                                ui.label("⚠️ Risiko yang Perlu Dijaga").style(SECTION_T)
                                risks = ai_insights.get("risks", [])
                                if risks:
                                    for item in risks:
                                        with ui.card().classes("w-full mb-1 p-2").style("background-color: rgba(243, 139, 168, 0.08); border-left: 3px solid #f38ba8;"):
                                            ui.label(f"• {item}").classes("text-sm text-gray-300")
                                else:
                                    ui.label("—").classes("text-gray-400 italic")

                        # Experiments
                        ui.label("🧪 Eksperimen yang Bisa Dicoba").style(SECTION_T)
                        experiments = ai_insights.get("experiments", [])
                        if experiments:
                            for idx, item in enumerate(experiments, start=1):
                                with ui.card().classes("w-full mb-1 p-2").style("background-color: rgba(249, 226, 175, 0.08); border-left: 3px solid #f9e2af;"):
                                    ui.label(f"{idx}. {item}").classes("text-sm text-gray-300")
                        else:
                            ui.label("—").classes("text-gray-400 italic")

                        # Priority Outlets
                        priority_outlets = ai_insights.get("priority_outlets", pd.DataFrame())
                        if isinstance(priority_outlets, pd.DataFrame) and not priority_outlets.empty:
                            ui.label("🏆 Outlet Prioritas untuk Dibahas").style(SECTION_T)
                            priority_display = priority_outlets.copy()
                            for col in ["total_revenue", "avg_revenue", "revenue_per_active_month"]:
                                if col in priority_display.columns:
                                    priority_display[col] = priority_display[col].fillna(0).apply(adapter.format_currency)
                            if "conversion_rate" in priority_display.columns:
                                priority_display["conversion_rate"] = priority_display["conversion_rate"].apply(lambda x: f"{x:.1f}%")
                            priority_display = priority_display.rename(columns={
                                "outlet_name": "Outlet", "total_revenue": "Total Omzet",
                                "avg_revenue": "Avg Omzet", "foto_qty": "Foto",
                                "print_qty": "Print", "active_months": "Bulan Aktif",
                                "conversion_rate": "Conversion",
                                "revenue_per_active_month": "Omzet / Bulan Aktif",
                                "status_ai": "AI Label",
                            })
                            _render_table(priority_display, max_rows=12)

        # ── Wire up selector changes ──
        start_sel.on_value_change(lambda e: update_content())
        end_sel.on_value_change(lambda e: update_content())

        # Initial render
        update_content()
