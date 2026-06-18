"""Ranking Outlet page — extracted from app.py"""

import pandas as pd
import streamlit as st

from components.ui_helpers import render_mobile_cards
from components.compat import df_show
from config import Config


def show_outlet_ranking(df, config, processor):
    st.title("🏆 Ranking Outlet")
    if df.empty:
        st.error("❌ Data tidak tersedia.")
        return
    base = df.copy(deep=True)
    cnt = base['outlet_status'].value_counts()
    a, b, c = st.columns(3)
    with a:
        st.metric("🟢 Keeper", cnt.get('Keeper', 0))
    with b:
        st.metric("🟡 Optimasi", cnt.get('Optimasi', 0))
    with c:
        st.metric("🔴 Relocate", cnt.get('Relocate', 0))
    st.subheader("📊 Complete Outlet Ranking")
    ranked = base.sort_values('total_revenue', ascending=False).reset_index(drop=True)
    ranked['rank'] = range(1, len(ranked) + 1)
    disp = ranked[['rank', 'outlet_name', 'area', 'kategori_tempat', 'total_revenue', 'conversion_rate', 'outlet_status']].copy()
    disp['total_revenue'] = disp['total_revenue'].apply(lambda x: Config().format_currency(x))
    disp['conversion_rate'] = disp['conversion_rate'].apply(lambda x: f"{x:.1f}%")
    render_mobile_cards(
        disp,
        "outlet_name",
        [("Rank", "rank"), ("Area", "area"), ("Kategori", "kategori_tempat"), ("Omset", "total_revenue"), ("Conversion", "conversion_rate")],
        status_col="outlet_status",
        max_rows=25,
    )
    st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
    df_show(disp, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.subheader("📋 Analysis by Status")
    t1, t2, t3 = st.tabs(["🟢 Keeper", "🟡 Optimasi", "🔴 Relocate"])
    with t1:
        k = base[base['outlet_status'] == "Keeper"]
        df_show(k[['outlet_name', 'area', 'total_revenue', 'conversion_rate']], use_container_width=True) if not k.empty else st.info("No outlets in Keeper status")
    with t2:
        o = base[base['outlet_status'] == "Optimasi"]
        df_show(o[['outlet_name', 'area', 'total_revenue', 'conversion_rate']], use_container_width=True) if not o.empty else st.info("No outlets in Optimasi status")
    with t3:
        r = base[base['outlet_status'] == "Relocate"]
        df_show(r[['outlet_name', 'area', 'total_revenue', 'conversion_rate']], use_container_width=True) if not r.empty else st.info("No outlets in Relocate status")
