"""
Trend Analysis page — trend analysis v1/v2, AI insights, and build functions.
Extracted from app.py during refactor (Task 13).
"""
from typing import List, Dict, Optional
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from config import Config
from components.compat import cache_data, rerun, text_col, number_col, table_height, df_show, DEFAULT_TABLE_MAX_HEIGHT, HAS_COLUMN_CONFIG, HAS_CAPTION
from components.ui_helpers import render_mobile_cards, s_caption, bool_series, _clean_master_values, kemitraan_table_show


def build_ai_trend_insights(base: pd.DataFrame, periods: List[str], config: Config) -> Dict[str, object]:
    """Generate local AI-style analysis from the selected trend data."""
    if base.empty or not periods:
        return {
            "summary": ["Data pada range periode ini belum cukup untuk dianalisis."],
            "findings": [],
            "actions": ["Coba perluas range periode atau cek filter sidebar."],
            "decisions": [],
            "risks": [],
            "experiments": [],
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

    monthly = (
        base.groupby("periode", as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            foto_qty=("foto_qty", "sum"),
            print_qty=("print_qty", "sum"),
            outlet_count=("outlet_name", "nunique"),
        )
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
        area_summary = (
            base.groupby("area", as_index=False)
            .agg(total_revenue=("total_revenue", "sum"), outlet_count=("outlet_name", "nunique"))
        )
        area_summary["revenue_per_outlet"] = area_summary["total_revenue"] / area_summary["outlet_count"].replace(0, np.nan)
        area_summary = area_summary.sort_values("total_revenue", ascending=False)

    category_summary = pd.DataFrame()
    if "kategori_tempat" in base.columns:
        category_summary = (
            base.groupby("kategori_tempat", as_index=False)
            .agg(total_revenue=("total_revenue", "sum"), outlet_count=("outlet_name", "nunique"))
            .sort_values("total_revenue", ascending=False)
        )

    top_area = area_summary.head(1).iloc[0] if not area_summary.empty else None
    low_area = area_summary[area_summary["total_revenue"] > 0].tail(1).iloc[0] if not area_summary.empty and (area_summary["total_revenue"] > 0).any() else None
    top_category = category_summary.head(1).iloc[0] if not category_summary.empty else None

    outlet_period = (
        base.groupby(["outlet_name", "periode"], as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            foto_qty=("foto_qty", "sum"),
            print_qty=("print_qty", "sum"),
        )
    )
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

    outlet_summary = (
        base.groupby("outlet_name", as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            avg_revenue=("total_revenue", "mean"),
            foto_qty=("foto_qty", "sum"),
            print_qty=("print_qty", "sum"),
            active_months=("periode", "nunique"),
        )
    )
    outlet_summary["conversion_rate"] = np.where(outlet_summary["foto_qty"] > 0, outlet_summary["print_qty"] / outlet_summary["foto_qty"] * 100, 0)
    outlet_summary["revenue_per_active_month"] = outlet_summary["total_revenue"] / outlet_summary["active_months"].replace(0, np.nan)
    outlet_summary["status_ai"] = "Monitor"
    outlet_summary.loc[(outlet_summary["total_revenue"] > 0) & (outlet_summary["conversion_rate"] < 12), "status_ai"] = "Traffic ada, conversion rendah"
    outlet_summary.loc[(outlet_summary["revenue_per_active_month"] >= outlet_summary["revenue_per_active_month"].quantile(0.80)), "status_ai"] = "Scale / benchmark"
    outlet_summary.loc[outlet_summary["active_months"] <= max(1, len(periods) // 4), "status_ai"] = "Seasonal / belum stabil"
    priority_outlets = outlet_summary.sort_values(
        ["total_revenue", "conversion_rate", "active_months"],
        ascending=[False, True, False],
    ).head(12).copy()

    summary = [
        "Range analisis: {} sampai {} dengan {} periode data.".format(periods[0], periods[-1], len(periods)),
        "Omzet periode terakhir {} adalah {}, dibanding periode sebelumnya: {}.".format(
            latest_period,
            config.format_currency(latest_revenue),
            fmt_pct(revenue_delta),
        ),
        "Rata-rata omzet bulanan pada range ini sekitar {}.".format(config.format_currency(avg_monthly)),
    ]

    if not best_month.empty and not weakest_month.empty:
        summary.append(
            "Bulan terkuat adalah {} ({}) dan bulan terlemah adalah {} ({}).".format(
                str(best_month.iloc[0]["periode"]),
                config.format_currency(float(best_month.iloc[0]["total_revenue"])),
                str(weakest_month.iloc[0]["periode"]),
                config.format_currency(float(weakest_month.iloc[0]["total_revenue"])),
            )
        )

    findings = []
    if top_area is not None:
        findings.append("Area terbesar adalah {} dengan kontribusi omzet {} dari {} outlet.".format(
            top_area["area"], config.format_currency(float(top_area["total_revenue"])), int(top_area["outlet_count"])
        ))
    if low_area is not None and top_area is not None and low_area["area"] != top_area["area"]:
        findings.append("Area yang perlu dicek lebih lanjut: {} karena omzetnya paling rendah di antara area yang masih menghasilkan.".format(low_area["area"]))
    if top_category is not None:
        findings.append("Kategori paling kuat saat ini adalah {} dengan omzet {}.".format(
            top_category["kategori_tempat"], config.format_currency(float(top_category["total_revenue"]))
        ))
    if inactive_count > 0:
        findings.append("{} outlet tidak aktif pada periode terakhir di range ini. Ini perlu dipisahkan dari outlet aktif agar ranking lebih fair.".format(inactive_count))
    if not movers.empty:
        top_up = movers.head(1).iloc[0]
        top_down = movers.tail(1).iloc[0]
        findings.append("Outlet dengan kenaikan nominal terbesar: {} ({}) dibanding periode sebelumnya.".format(
            top_up["outlet_name"], config.format_currency(float(top_up["growth_value"]))
        ))
        if float(top_down["growth_value"]) < 0:
            findings.append("Outlet dengan penurunan terdalam: {} ({}) dibanding periode sebelumnya.".format(
                top_down["outlet_name"], config.format_currency(float(top_down["growth_value"]))
            ))

    actions = []
    if revenue_delta is not None and revenue_delta < -10:
        actions.append("Prioritaskan audit outlet yang turun pada periode terakhir, terutama penyebab traffic, conversion, dan stok/operasional.")
    elif revenue_delta is not None and revenue_delta > 10:
        actions.append("Duplikasi pola dari outlet/area yang naik: cek promo, placement, timing event, dan operator yang bertugas.")
    else:
        actions.append("Karena omzet relatif stabil, fokuskan eksperimen pada outlet dengan conversion rendah tetapi traffic foto tinggi.")
    if inactive_count > 0:
        actions.append("Buat label operasional untuk outlet tidak aktif: seasonal/event selesai, pending buka, atau perlu follow-up partner.")
    if top_area is not None:
        actions.append("Gunakan area {} sebagai benchmark untuk area lain, tapi bandingkan dengan range periode yang sama agar tidak bias outlet lama.".format(top_area["area"]))
    actions.append("Untuk keputusan ekspansi, pakai metrik omzet per outlet dan conversion, bukan total omzet saja.")

    decisions = []
    risks = []
    experiments = []
    recent_months = monthly.tail(min(3, len(monthly)))
    recent_revenue_slope = float(recent_months["revenue_change"].fillna(0).sum()) if not recent_months.empty else 0.0
    recent_conv_slope = float(recent_months["conversion_change"].fillna(0).sum()) if not recent_months.empty else 0.0

    if revenue_delta is not None and revenue_delta > 15 and recent_revenue_slope > 0:
        decisions.append("Mode keputusan: offense. Ada momentum naik, pilih 3-5 outlet/area terbaik untuk jadi benchmark SOP dan dorong scale.")
    elif revenue_delta is not None and revenue_delta < -15:
        decisions.append("Mode keputusan: defense. Tahan ekspansi yang belum urgent, audit outlet turun, dan cari penyebab drop bulan terakhir.")
    else:
        decisions.append("Mode keputusan: selective growth. Jangan pukul rata; pilih outlet dengan omzet stabil dan conversion sehat untuk ekspansi kecil.")

    if inactive_count > max(5, len(all_outlets) * 0.25):
        risks.append("Banyak outlet tidak aktif di periode terakhir. Ranking total bisa bias kalau outlet event/seasonal tidak dipisahkan.")
    if recent_conv_slope < -2:
        risks.append("Conversion beberapa bulan terakhir melemah. Ada risiko traffic bagus tidak berubah jadi print/revenue.")
    if top_area is not None and len(area_summary) > 1:
        top_share = float(top_area["total_revenue"]) / float(area_summary["total_revenue"].sum()) if float(area_summary["total_revenue"].sum()) > 0 else 0
        if top_share > 0.45:
            risks.append("Omzet terlalu terkonsentrasi di satu area. Kalau area utama turun, total bisnis ikut rentan.")
    if not risks:
        risks.append("Tidak ada risiko ekstrem dari range ini, tapi tetap cek outlet baru/event karena datanya belum stabil.")

    experiments.append("Pilih 5 outlet omzet tinggi tetapi conversion di bawah median, lalu test script upsell/operator selama 2 minggu.")
    experiments.append("Bandingkan outlet indoor vs outdoor pada range yang sama untuk menentukan placement dan jam operasional terbaik.")
    experiments.append("Untuk outlet event/seasonal, pisahkan target KPI dari outlet permanen agar keputusan tidak bias.")

    return {
        "summary": summary,
        "findings": findings,
        "actions": actions,
        "decisions": decisions,
        "risks": risks,
        "experiments": experiments,
        "priority_outlets": priority_outlets,
    }


def render_ai_insights(insights: Dict[str, object], config: Config):
    st.markdown("**Decision Brief**")
    for item in insights.get("decisions", []):
        st.success(item)

    st.markdown("**Executive Summary**")
    for item in insights.get("summary", []):
        st.markdown(f"- {item}")

    st.markdown("**Temuan Penting**")
    findings = insights.get("findings", [])
    if findings:
        for item in findings:
            st.markdown(f"- {item}")
    else:
        st.info("Belum ada temuan kuat dari range periode ini.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Rekomendasi Aksi**")
        for idx, item in enumerate(insights.get("actions", []), start=1):
            st.markdown(f"{idx}. {item}")
    with c2:
        st.markdown("**Risiko yang Perlu Dijaga**")
        for item in insights.get("risks", []):
            st.warning(item)

    st.markdown("**Eksperimen yang Bisa Dicoba**")
    for idx, item in enumerate(insights.get("experiments", []), start=1):
        st.markdown(f"{idx}. {item}")

    priority_outlets = insights.get("priority_outlets", pd.DataFrame())
    if isinstance(priority_outlets, pd.DataFrame) and not priority_outlets.empty:
        st.markdown("**Outlet Prioritas untuk Dibahas**")
        priority_display = priority_outlets.copy()
        for col in ["total_revenue", "avg_revenue", "revenue_per_active_month"]:
            if col in priority_display.columns:
                priority_display[col] = priority_display[col].fillna(0).apply(config.format_currency)
        if "conversion_rate" in priority_display.columns:
            priority_display["conversion_rate"] = priority_display["conversion_rate"].apply(lambda x: f"{x:.1f}%")
        priority_display = priority_display.rename(columns={
            "outlet_name": "Outlet",
            "total_revenue": "Total Omzet",
            "avg_revenue": "Avg Omzet",
            "foto_qty": "Foto",
            "print_qty": "Print",
            "active_months": "Bulan Aktif",
            "conversion_rate": "Conversion",
            "revenue_per_active_month": "Omzet / Bulan Aktif",
            "status_ai": "AI Label",
        })
        render_mobile_cards(
            priority_display,
            "Outlet",
            [
                ("Total Omzet", "Total Omzet"),
                ("Conversion", "Conversion"),
                ("Bulan Aktif", "Bulan Aktif"),
                ("Omzet / Bulan", "Omzet / Bulan Aktif"),
            ],
            status_col="AI Label",
            max_rows=12,
        )
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(priority_display, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)


def show_trend_analysis_v2(df, config, processor, viz):
    st.title("Analisis Trend Penjualan")
    if df.empty:
        st.error("Data tidak tersedia.")
        return

    base = df.copy(deep=True)
    for col in ["total_revenue", "foto_qty", "unlock_qty", "print_qty", "conversion_rate"]:
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0.0)
    base["periode"] = base["periode"].astype(str)

    from services.aggregation import _sort_periods_str
    periods = _sort_periods_str(base["periode"].dropna().astype(str).unique().tolist()) if "periode" in base.columns else []
    if not periods:
        st.error("Data periode tidak tersedia.")
        return

    default_start_idx = max(0, len(periods) - 12)
    default_end_idx = len(periods) - 1
    st.markdown("#### Range Periode Analisis")
    r1, r2, r3 = st.columns([1, 1, 2])
    with r1:
        start_period = st.selectbox("Periode Mulai", periods, index=default_start_idx, key="trend_period_start")
    with r2:
        end_period = st.selectbox("Periode Akhir", periods, index=default_end_idx, key="trend_period_end")

    start_idx = periods.index(start_period)
    end_idx = periods.index(end_period)
    if start_idx > end_idx:
        st.error("Periode mulai tidak boleh lebih baru dari periode akhir.")
        return

    selected_periods = periods[start_idx:end_idx + 1]
    base = base[base["periode"].isin(selected_periods)].copy()
    periods = selected_periods
    with r3:
        st.info("Analisis memakai {} periode: {} sampai {}.".format(len(periods), start_period, end_period))

    latest_period = periods[-1] if periods else None
    previous_period = periods[-2] if len(periods) > 1 else None
    latest_df = base[base["periode"] == latest_period].copy() if latest_period else base.copy()
    previous_df = base[base["periode"] == previous_period].copy() if previous_period else pd.DataFrame()
    ai_insights = build_ai_trend_insights(base.copy(), periods, config)

    def _sum(frame, col):
        return float(pd.to_numeric(frame.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

    def _conversion(frame):
        foto = _sum(frame, "foto_qty")
        printed = _sum(frame, "print_qty")
        return (printed / foto * 100) if foto > 0 else 0.0

    revenue_now = _sum(latest_df, "total_revenue")
    revenue_prev = _sum(previous_df, "total_revenue")
    revenue_delta = ((revenue_now - revenue_prev) / revenue_prev * 100) if revenue_prev > 0 else None
    conv_now = _conversion(latest_df)
    conv_prev = _conversion(previous_df)
    conv_delta = conv_now - conv_prev if previous_period else None

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Periode Terbaru", latest_period or "-")
    with k2:
        st.metric("Omzet", config.format_currency(revenue_now), delta=(f"{revenue_delta:+.1f}%" if revenue_delta is not None else None))
    with k3:
        st.metric("Outlet Aktif", f"{latest_df['outlet_name'].nunique():,}")
    with k4:
        st.metric("Conversion", f"{conv_now:.1f}%", delta=(f"{conv_delta:+.1f}pp" if conv_delta is not None else None))

    monthly = (
        base.groupby("periode", as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            foto_qty=("foto_qty", "sum"),
            unlock_qty=("unlock_qty", "sum"),
            print_qty=("print_qty", "sum"),
            outlet_count=("outlet_name", "nunique"),
        )
    )
    monthly["conversion_rate"] = np.where(monthly["foto_qty"] > 0, monthly["print_qty"] / monthly["foto_qty"] * 100, 0)
    monthly["periode"] = pd.Categorical(monthly["periode"], categories=periods, ordered=True)
    monthly = monthly.sort_values("periode")

    tab_overview, tab_segments, tab_outlets, tab_heatmap, tab_ai = st.tabs(["Overview", "Area & Category", "Outlet Movers", "Heatmap", "AI Insight"])

    with tab_overview:
        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.line(monthly, x="periode", y="total_revenue", markers=True, title="Monthly Revenue Trend")
            fig.update_traces(hovertemplate="%{x}<br>Revenue: Rp %{y:,.0f}<extra></extra>")
            fig.update_layout(height=420, yaxis_title="Revenue", xaxis_title="Periode")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig_conv = px.line(monthly, x="periode", y="conversion_rate", markers=True, title="Conversion Trend")
            fig_conv.update_traces(hovertemplate="%{x}<br>Conversion: %{y:.1f}%<extra></extra>")
            fig_conv.update_layout(height=420, yaxis_title="Conversion %", xaxis_title="Periode")
            st.plotly_chart(fig_conv, use_container_width=True)

        monthly_display = monthly.copy()
        monthly_display["total_revenue"] = monthly_display["total_revenue"].apply(config.format_currency)
        monthly_display["conversion_rate"] = monthly_display["conversion_rate"].apply(lambda x: f"{x:.1f}%")
        monthly_display = monthly_display.rename(columns={
            "periode": "Periode",
            "total_revenue": "Omzet",
            "foto_qty": "Foto",
            "unlock_qty": "Unlock",
            "print_qty": "Print",
            "outlet_count": "Outlet",
            "conversion_rate": "Conversion",
        })
        render_mobile_cards(
            monthly_display,
            "Periode",
            [("Omzet", "Omzet"), ("Outlet", "Outlet"), ("Foto", "Foto"), ("Print", "Print"), ("Conversion", "Conversion")],
            max_rows=12,
        )
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(monthly_display, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_segments:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(viz.create_area_analysis_chart(base), use_container_width=True)
        with c2:
            st.plotly_chart(viz.create_indoor_outdoor_comparison(base), use_container_width=True)

        c3, c4 = st.columns(2)
        with c3:
            area_summary = processor.aggregate_by_area(base.copy()).reset_index()
            if not area_summary.empty:
                area_summary["revenue_per_outlet"] = area_summary["total_revenue"] / area_summary["outlet_count"].replace(0, np.nan)
                area_summary["total_revenue"] = area_summary["total_revenue"].apply(config.format_currency)
                area_summary["revenue_per_outlet"] = area_summary["revenue_per_outlet"].fillna(0).apply(config.format_currency)
            st.subheader("Summary by Area")
            df_show(area_summary, use_container_width=True, hide_index=True)
        with c4:
            kategori_summary = processor.aggregate_by_kategori(base.copy()).reset_index()
            if not kategori_summary.empty:
                kategori_summary["revenue_per_outlet"] = kategori_summary["total_revenue"] / kategori_summary["outlet_count"].replace(0, np.nan)
                kategori_summary["total_revenue"] = kategori_summary["total_revenue"].apply(config.format_currency)
                kategori_summary["revenue_per_outlet"] = kategori_summary["revenue_per_outlet"].fillna(0).apply(config.format_currency)
            st.subheader("Summary by Category")
            df_show(kategori_summary, use_container_width=True, hide_index=True)

        st.plotly_chart(viz.create_kategori_analysis(base), use_container_width=True)

    with tab_outlets:
        if latest_period and not latest_df.empty:
            profit_source = latest_df.groupby("outlet_name", as_index=False).agg(
                total_revenue=("total_revenue", "sum"),
                foto_qty=("foto_qty", "sum"),
                unlock_qty=("unlock_qty", "sum"),
                print_qty=("print_qty", "sum"),
            )
            mapping_profit = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()
            from app import apply_sharing_to_mapping
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
            from app import add_profit_columns
            profit_source = add_profit_columns(profit_source)
            top_profit = profit_source.sort_values("estimasi_profit_difotoin", ascending=False).head(10).copy()
            if not top_profit.empty:
                st.subheader(f"Outlet Paling Menguntungkan untuk Difotoin - {latest_period}")
                show_profit = top_profit[[
                    c for c in [
                        "outlet_name", "area", "basis_bagi_hasil", "sharing_bagi_hasil",
                        "pendapatan_operator", "monthly_rent", "estimasi_profit_difotoin",
                        "foto_qty", "unlock_qty", "print_qty",
                    ] if c in top_profit.columns
                ]].copy()
                for col in ["basis_bagi_hasil", "pendapatan_operator", "monthly_rent", "estimasi_profit_difotoin"]:
                    if col in show_profit.columns:
                        show_profit[col] = show_profit[col].apply(lambda x: config.format_currency(float(x)) if pd.notna(x) and float(x) > 0 else "-")
                if "sharing_bagi_hasil" in show_profit.columns:
                    show_profit["sharing_bagi_hasil"] = show_profit["sharing_bagi_hasil"].apply(lambda x: "-" if pd.isna(x) else f"{float(x)*100:.1f}%")
                show_profit = show_profit.rename(columns={
                    "outlet_name": "Outlet",
                    "area": "Area",
                    "basis_bagi_hasil": "Basis Bagi Hasil",
                    "sharing_bagi_hasil": "Share Difotoin",
                    "pendapatan_operator": "Bagi Hasil Difotoin",
                    "monthly_rent": "Monthly Rent",
                    "estimasi_profit_difotoin": "Estimasi Profit",
                    "foto_qty": "Foto",
                    "unlock_qty": "Unlock",
                    "print_qty": "Print",
                })
                df_show(show_profit, use_container_width=True, hide_index=True, height=table_height(len(show_profit), 240, 420))

        outlet_period = (
            base.groupby(["outlet_name", "periode"], as_index=False)
            .agg(total_revenue=("total_revenue", "sum"), foto_qty=("foto_qty", "sum"), print_qty=("print_qty", "sum"))
        )
        outlet_pivot = outlet_period.pivot_table(index="outlet_name", columns="periode", values="total_revenue", aggfunc="sum", fill_value=0)
        if latest_period and latest_period in outlet_pivot.columns:
            movers = pd.DataFrame({"outlet_name": outlet_pivot.index, "latest_revenue": outlet_pivot[latest_period].values})
            if previous_period and previous_period in outlet_pivot.columns:
                movers["previous_revenue"] = outlet_pivot[previous_period].values
                movers["growth_value"] = movers["latest_revenue"] - movers["previous_revenue"]
                movers["growth_pct"] = np.where(movers["previous_revenue"] > 0, movers["growth_value"] / movers["previous_revenue"] * 100, np.nan)
            else:
                movers["previous_revenue"] = 0.0
                movers["growth_value"] = movers["latest_revenue"]
                movers["growth_pct"] = np.nan

            top_latest = movers.sort_values("latest_revenue", ascending=False).head(15).copy()
            top_up = movers.sort_values("growth_value", ascending=False).head(10).copy()
            top_down = movers.sort_values("growth_value", ascending=True).head(10).copy()

            for table in [top_latest, top_up, top_down]:
                table["latest_revenue"] = table["latest_revenue"].apply(config.format_currency)
                table["previous_revenue"] = table["previous_revenue"].apply(config.format_currency)
                table["growth_value"] = table["growth_value"].apply(config.format_currency)
                table["growth_pct"] = table["growth_pct"].apply(lambda x: "-" if pd.isna(x) else f"{x:+.1f}%")

            c1, c2 = st.columns(2)
            with c1:
                st.subheader(f"Top Outlet {latest_period}")
                render_mobile_cards(top_latest, "outlet_name", [("Omzet terbaru", "latest_revenue"), ("Omzet sebelumnya", "previous_revenue"), ("Growth", "growth_value"), ("Growth %", "growth_pct")], max_rows=10)
                st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
                df_show(top_latest, use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.subheader("Biggest Growth")
                render_mobile_cards(top_up, "outlet_name", [("Omzet terbaru", "latest_revenue"), ("Omzet sebelumnya", "previous_revenue"), ("Growth", "growth_value"), ("Growth %", "growth_pct")], max_rows=10)
                st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
                df_show(top_up, use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
            st.subheader("Needs Attention")
            render_mobile_cards(top_down, "outlet_name", [("Omzet terbaru", "latest_revenue"), ("Omzet sebelumnya", "previous_revenue"), ("Growth", "growth_value"), ("Growth %", "growth_pct")], max_rows=10)
            st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
            df_show(top_down, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Data outlet per periode belum cukup untuk menghitung movers.")

    with tab_heatmap:
        st.plotly_chart(viz.create_heatmap(base), use_container_width=True)
        st.caption("Heatmap membantu melihat kombinasi area dan kategori yang paling kuat atau perlu diperbaiki.")

    with tab_ai:
        st.subheader("AI Insight")
        st.caption("Analisis otomatis dari data dan filter periode yang sedang dipilih. Fokusnya membantu keputusan founder, bukan hanya membaca chart.")
        render_ai_insights(ai_insights, config)


def show_trend_analysis(df, config, processor, viz):
    st.title("📊 Analisis Trend Penjualan")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    st.subheader("🗺️ Analisis per Area"); st.plotly_chart(viz.create_area_analysis_chart(df), use_container_width=True)
    st.subheader("🏢 Analisis per Kategori Tempat"); st.plotly_chart(viz.create_kategori_analysis(df), use_container_width=True)
    st.subheader("🏠 Indoor vs Outdoor Analysis"); st.plotly_chart(viz.create_indoor_outdoor_comparison(df), use_container_width=True)
    st.subheader("🔥 Performance Heatmap"); st.plotly_chart(viz.create_heatmap(df), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1: st.subheader("📋 Summary by Area"); df_show(processor.aggregate_by_area(df.copy(deep=True)), use_container_width=True)
    with c2: st.subheader("📋 Summary by Category"); df_show(processor.aggregate_by_kategori(df.copy(deep=True)), use_container_width=True)
