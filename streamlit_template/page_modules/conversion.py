"""Analisis Konversi page — extracted from app.py"""

import pandas as pd
import streamlit as st
import numpy as np

from components.ui_helpers import render_mobile_cards
from components.compat import df_show


def show_conversion_analysis(df, config, processor, viz):
    st.title("🔄 Analisis Konversi & Awareness")
    if df.empty:
        st.error("❌ Data tidak tersedia.")
        return
    base = df.copy(deep=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("📸➡️🖨️ Foto to Print", f"{base['conversion_rate'].mean():.1f}%")
    with c2:
        unlock_sum = pd.to_numeric(base.get('unlock_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        print_sum = pd.to_numeric(base.get('print_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        rate = (print_sum / unlock_sum * 100) if unlock_sum > 0 else 0
        st.metric("🔓➡️🖨️ Unlock to Print", f"{rate:.1f}%")
    with c3:
        foto_sum = pd.to_numeric(base.get('foto_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        print_sum = pd.to_numeric(base.get('print_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        over = (print_sum / foto_sum * 100) if foto_sum > 0 else 0
        st.metric("🎯 Overall Conversion", f"{over:.1f}%")
    st.subheader("🔄 Conversion Funnel")
    st.plotly_chart(viz.create_conversion_funnel(base), use_container_width=True)
    st.subheader("📊 Conversion Rate by Outlet")
    a, b = st.columns(2)
    with a:
        st.write("**🟢 High Conversion Outlets (>25%)**")
        hi = base[base['conversion_rate'] > 25].sort_values('conversion_rate', ascending=False)
        if not hi.empty:
            hi_display = hi[['outlet_name', 'conversion_rate', 'total_revenue']].copy()
            hi_display['conversion_rate'] = hi_display['conversion_rate'].apply(lambda x: f"{x:.1f}%")
            hi_display['total_revenue'] = hi_display['total_revenue'].apply(config.format_currency)
            render_mobile_cards(hi_display, "outlet_name", [("Conversion", "conversion_rate"), ("Omset", "total_revenue")], max_rows=12)
            st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
            df_show(hi_display, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No outlets with >25% conversion rate")
    with b:
        st.write("**🔴 Low Conversion Outlets (<15%)**")
        lo = base[base['conversion_rate'] < 15].sort_values('conversion_rate', ascending=True)
        if not lo.empty:
            lo_display = lo[['outlet_name', 'conversion_rate', 'total_revenue']].copy()
            lo_display['conversion_rate'] = lo_display['conversion_rate'].apply(lambda x: f"{x:.1f}%")
            lo_display['total_revenue'] = lo_display['total_revenue'].apply(config.format_currency)
            render_mobile_cards(lo_display, "outlet_name", [("Conversion", "conversion_rate"), ("Omset", "total_revenue")], max_rows=12)
            st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
            df_show(lo_display, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No outlets with <15% conversion rate")
    st.subheader("📢 Awareness Analysis")
    seg = base[(base['foto_qty'] > base['foto_qty'].median()) & (base['conversion_rate'] < base['conversion_rate'].median())]
    if not seg.empty:
        st.write("**⚠️ High Awareness, Low Conversion (Need Promotion)**")
        seg_display = seg[['outlet_name', 'foto_qty', 'conversion_rate', 'total_revenue']].copy()
        seg_display['conversion_rate'] = seg_display['conversion_rate'].apply(lambda x: f"{x:.1f}%")
        seg_display['total_revenue'] = seg_display['total_revenue'].apply(config.format_currency)
        render_mobile_cards(seg_display, "outlet_name", [("Foto", "foto_qty"), ("Conversion", "conversion_rate"), ("Omset", "total_revenue")], max_rows=12)
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(seg_display, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.subheader("📈 Conversion Trends")
    st.plotly_chart(viz.create_trend_chart(base, 'conversion_rate'), use_container_width=True)
