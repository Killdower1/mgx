"""Perbandingan Periode page — extracted from app.py"""

import pandas as pd
import streamlit as st


def calculate_growth_metrics(cur, prev):
    """Calculate growth metrics between two periods."""
    gm = {}
    cur_rev = float(cur['total_revenue'].sum())
    prev_rev = float(prev['total_revenue'].sum())
    gm['revenue_growth'] = ((cur_rev - prev_rev) / prev_rev * 100) if prev_rev else 0

    cur_photo = int(cur['foto_qty'].sum())
    prev_photo = int(prev['foto_qty'].sum())
    gm['photo_growth'] = ((cur_photo - prev_photo) / prev_photo * 100) if prev_photo else 0

    cur_conv = float(cur['conversion_rate'].mean())
    prev_conv = float(prev['conversion_rate'].mean())
    gm['conversion_change'] = cur_conv - prev_conv
    return gm


def show_period_comparison(df, config, processor, viz, current_period, compare_period):
    st.title("📅 Perbandingan Periode")
    if df.empty:
        st.error("❌ Data tidak tersedia.")
        return
    base = df.copy(deep=True)
    if current_period and compare_period:
        cur = base[base['periode'] == current_period]
        prev = base[base['periode'] == compare_period]
        gm = calculate_growth_metrics(cur, prev)
        st.subheader("📈 Growth Metrics")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Revenue Growth", f"{gm.get('revenue_growth', 0):+.1f}%", delta=f"{gm.get('revenue_growth', 0):+.1f}%")
        with c2:
            st.metric("Photo Growth", f"{gm.get('photo_growth', 0):+.1f}%", delta=f"{gm.get('photo_growth', 0):+.1f}%")
        with c3:
            st.metric("Conversion Change", f"{gm.get('conversion_change', 0):+.1f}pp", delta=f"{gm.get('conversion_change', 0):+.1f}pp")
        st.subheader("📈 Trend Analysis")
        st.plotly_chart(viz.create_trend_chart(base, 'total_revenue'), use_container_width=True)
    else:
        st.info("Pilih kedua periode di sidebar untuk membandingkan.")
