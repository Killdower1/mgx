# path: pages/ai_decision.py — AI Decision page
import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict
from config import Config
from page_modules.trend import build_ai_trend_insights, render_ai_insights


def show_ai_decision_center(df: pd.DataFrame, config: Config):
    st.title("AI Decision")
    st.caption("Ruang bantu keputusan founder: membaca data, memberi sinyal risiko, dan menyusun prioritas aksi.")

    if df.empty or "periode" not in df.columns:
        st.error("Data tidak tersedia untuk AI Decision.")
        return

    base = df.copy(deep=True)
    for col in ["total_revenue", "foto_qty", "unlock_qty", "print_qty", "conversion_rate"]:
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0.0)
    base["periode"] = base["periode"].astype(str)

    from services.aggregation import _sort_periods_str

    periods = _sort_periods_str(base["periode"].dropna().astype(str).unique().tolist())
    if not periods:
        st.error("Data periode tidak tersedia.")
        return

    default_start_idx = max(0, len(periods) - 12)
    r1, r2, r3 = st.columns([1, 1, 2])
    with r1:
        start_period = st.selectbox("Periode Mulai", periods, index=default_start_idx, key="ai_decision_start")
    with r2:
        end_period = st.selectbox("Periode Akhir", periods, index=len(periods) - 1, key="ai_decision_end")

    start_idx = periods.index(start_period)
    end_idx = periods.index(end_period)
    if start_idx > end_idx:
        st.error("Periode mulai tidak boleh lebih baru dari periode akhir.")
        return

    selected_periods = periods[start_idx:end_idx + 1]
    base = base[base["periode"].isin(selected_periods)].copy()
    with r3:
        st.info("AI membaca {} periode: {} sampai {}.".format(len(selected_periods), start_period, end_period))

    insights = build_ai_trend_insights(base, selected_periods, config)
    render_ai_insights(insights, config)
