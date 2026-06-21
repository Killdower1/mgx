"""🤝 Lead Kemitraan — analytics dashboard & data viewer for franchise leads from ERPNext.
Read-only — data comes from ERPNext, no edit/create here."""
from typing import Optional

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from services.erpnext import (
    load_erpnext_config,
    save_erpnext_config,
    check_connection,
    fetch_lead_kemitraan,
    get_lk_cache_info,
    LEAD_KEMITRAAN_DISPLAY_NAMES,
)
from components.compat import rerun


# ── Color palette (dark theme friendly) ──
STATUS_COLORS = {
    "New": "#6366f1", "Contact": "#06b6d4", "Meeting": "#f59e0b",
    "Qualified": "#22c55e", "Negotiation": "#f97316", "Approved": "#14b8a6",
    "Live": "#22c55e", "Lost": "#ef4444", "DP Paid": "#8b5cf6",
}
PRIORITY_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#6b7280"}
CATEGORICAL_COLORS = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel1


def show_lead_kemitraan_page():
    st.title("🤝 Lead Kemitraan (Franchise)")
    st.caption(
        "Dashboard & data calon mitra franchise dari ERPNext — "
        "analisis untuk pengambilan keputusan."
    )

    # ── Config check ──
    cfg = load_erpnext_config()
    connected = False

    if not cfg.get("url") or not cfg.get("api_key"):
        _render_config_form(cfg)
        return
    else:
        connected_ok, connected_msg = check_connection("Lead%20Kemitraan")
        connected = connected_ok
        if not connected_ok:
            st.warning(f"⚠️ {connected_msg}")
            with st.expander("🔧 Konfigurasi ERPNext"):
                _render_config_form(cfg)

    # ── Fetch ──
    if connected:
        df = fetch_lead_kemitraan(limit=5000)
    else:
        df = pd.DataFrame()

    if df.empty:
        st.info("Belum ada data Lead Kemitraan dari ERPNext.")
        if not connected:
            st.caption("Pastikan konfigurasi ERPNext benar dan koneksi tersambung.")
        return

    # ── Global filters (apply to both tabs) ──
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1.5, 1.5, 1])
    with col_f1:
        search_q = st.text_input("🔍 Cari (nama, wa, email, kota)", key="lk_search_g")
    with col_f2:
        status_opts = ["Semua Status"] + sorted(df["status_lead"].dropna().unique())
        filter_status = st.selectbox("Status", status_opts, key="lk_filter_status_g")
    with col_f3:
        prio_opts = ["Semua Prioritas"] + sorted(df["priority"].dropna().unique())
        filter_prio = st.selectbox("Prioritas", prio_opts, key="lk_filter_prio_g")
    with col_f4:
        refresh = st.button("🔄 Refresh", type="secondary", use_container_width=True)

    cache_info = get_lk_cache_info()
    if cache_info:
        st.caption(
            f"💾 Data lokal: {cache_info.get('count', 0)} record — "
            f"terakhir sync {cache_info.get('last_sync', '-')[:16]}"
        )

    # ── Apply filters ──
    fdf = df.copy()
    if filter_status and filter_status != "Semua Status":
        fdf = fdf[fdf["status_lead"].astype(str).str.strip() == filter_status]
    if filter_prio and filter_prio != "Semua Prioritas":
        fdf = fdf[fdf["priority"].astype(str).str.strip() == filter_prio]
    if search_q.strip():
        q = search_q.strip().lower()
        mask = (
            fdf.get("nama_lengkap", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("nomor_whatsapp", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("email", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("kota_domisili", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("kota_penempatan_mesin", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("name", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        )
        fdf = fdf[mask].copy()

    # ── Tabs: Dashboard first, then List ──
    tab_dash, tab_list = st.tabs(["📊 Dashboard Lead Kemitraan", "📋 Daftar Lead"])

    with tab_dash:
        _render_dashboard(fdf, df)
    with tab_list:
        _render_lead_table(fdf)


# ═══════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════

def _render_dashboard(fdf: pd.DataFrame, full_df: pd.DataFrame):
    """Full analytics dashboard — all available data dimensions."""

    # ── KPI Cards ──
    total = len(fdf)
    qualified = len(fdf[fdf.get("status_lead", "").astype(str).str.strip() == "Qualified"])
    high_prio = len(fdf[fdf.get("priority", "").astype(str).str.strip() == "High"])
    total_investasi = fdf.get("harga_investasi_dibahas", pd.Series(dtype=float)).fillna(0).astype(float).sum()
    kota_col = fdf.get("kota_penempatan_mesin", fdf.get("kota_domisili", pd.Series(dtype=str)))
    unique_kota = kota_col.dropna().astype(str).nunique() if not kota_col.empty else 0
    total_unit = fdf.get("jumlah_unit_final", pd.Series(dtype=str)).dropna().values
    sudah_lokasi = len(fdf[fdf.get("sudah_punya_lokasi", "").astype(str).str.strip() == "Sudah"])
    sales_pics = fdf.get("sales_pic", pd.Series(dtype=str)).dropna().nunique()

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1: st.metric("📋 Total Lead", total)
    with m2: st.metric("✅ Qualified", qualified)
    with m3: st.metric("🔴 Prioritas Tinggi", high_prio)
    with m4: st.metric("💰 Total Investasi", f"Rp{total_investasi:,.0f}" if total_investasi > 0 else "-")
    with m5: st.metric("📍 Kota", unique_kota)
    with m6: st.metric("👨‍💼 Sales PIC", sales_pics)

    st.markdown("---")

    # ── ROW 1: Funnel + Trend ── (full width)
    c1, c2 = st.columns([1.2, 1])
    with c1: _chart_conversion_funnel(fdf)
    with c2: _chart_monthly_trend(fdf)

    st.markdown("---")

    # ── ROW 2: 3 kolom — Status, Priority, Source ──
    col1, col2, col3 = st.columns(3)
    with col1: _chart_status_distribution(fdf)
    with col2: _chart_priority_distribution(fdf)
    with col3: _chart_source_distribution(fdf)

    st.markdown("---")

    # ── ROW 3: 3 kolom — Kota, Pekerjaan, Tahu Difotoin ──
    col1, col2, col3 = st.columns(3)
    with col1: _chart_city_distribution(fdf)
    with col2: _chart_pekerjaan_distribution(fdf)
    with col3: _chart_tahu_difotoin_distribution(fdf)

    st.markdown("---")

    # ── ROW 4: 3 kolom — Status Lokasi, Jenis Lokasi, Potensi ──
    col1, col2, col3 = st.columns(3)
    with col1: _chart_status_lokasi_distribution(fdf)
    with col2: _chart_jenis_lokasi_distribution(fdf)
    with col3: _chart_potensi_lokasi_distribution(fdf)

    st.markdown("---")

    # ── ROW 5: 3 kolom — Sudah Punya Lokasi, Unit Diminati, Kapan Mulai ──
    col1, col2, col3 = st.columns(3)
    with col1: _chart_sudah_lokasi_distribution(fdf)
    with col2: _chart_unit_diminati_distribution(fdf)
    with col3: _chart_kapan_mulai_distribution(fdf)

    st.markdown("---")

    # ── ROW 6: 3 kolom — Disposition, Target BEP, Next Step ──
    col1, col2, col3 = st.columns(3)
    with col1: _chart_disposition_distribution(fdf)
    with col2: _chart_target_bep_distribution(fdf)
    with col3: _chart_next_step_distribution(fdf)

    st.markdown("---")

    # ── ROW 7: 2 kolom — Budget & Investasi detail ──
    _chart_budget_summary(fdf)

    st.markdown("---")

    # ── ROW 8: Sales PIC performance ──
    _chart_sales_pic_performance(fdf)

    st.markdown("---")

    # ── ROW 9: Raw data table at bottom ──
    with st.expander("📋 Lihat Semua Data Lead Kemitraan", expanded=False):
        _render_compact_table(fdf)


# ── Individual chart functions ──

def _chart_status_distribution(df: pd.DataFrame):
    st.subheader("📊 Sebaran Status Lead")
    status_col = df.get("status_lead", pd.Series(dtype=str))
    if status_col.empty:
        st.info("Belum ada data status.")
        return
    counts = status_col.value_counts().reset_index()
    counts.columns = ["status", "count"]
    counts["color"] = counts["status"].map(STATUS_COLORS).fillna("#6b7280")
    fig = px.bar(
        counts, x="status", y="count", color="status",
        color_discrete_map=STATUS_COLORS,
        text="count", template="plotly_dark",
    )
    fig.update_traces(textposition="outside", hovertemplate="%{x}: %{y} lead")
    fig.update_layout(
        height=320, margin=dict(t=10, b=40, l=10, r=10),
        xaxis_title=None, yaxis_title="Jumlah Lead",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_priority_distribution(df: pd.DataFrame):
    st.subheader("🎯 Prioritas Lead")
    prio_col = df.get("priority", pd.Series(dtype=str))
    if prio_col.empty:
        st.info("Belum ada data prioritas.")
        return
    counts = prio_col.value_counts().reset_index()
    counts.columns = ["priority", "count"]
    fig = px.pie(
        counts, names="priority", values="count",
        color="priority", color_discrete_map=PRIORITY_COLORS,
        template="plotly_dark", hole=0.4,
    )
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_source_distribution(df: pd.DataFrame):
    st.subheader("📢 Sumber Lead")
    src_col = df.get("source_lead", pd.Series(dtype=str))
    if src_col.empty or src_col.dropna().empty:
        st.info("Belum ada data sumber.")
        return
    counts = src_col.value_counts().reset_index()
    counts.columns = ["source", "count"]
    n = min(len(counts), 8)
    top = counts.head(n)
    others = pd.DataFrame([{"source": "Lainnya", "count": counts["count"][n:].sum()}]) if len(counts) > n else pd.DataFrame()
    chart_df = pd.concat([top, others], ignore_index=True) if not others.empty else top
    fig = px.bar(
        chart_df, x="source", y="count", color="source",
        text="count", template="plotly_dark",
        color_discrete_sequence=CATEGORICAL_COLORS,
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=320, margin=dict(t=10, b=40, l=10, r=10),
        xaxis_title=None, yaxis_title="Lead", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_city_distribution(df: pd.DataFrame):
    st.subheader("🏙️ Kota Penempatan")
    kota_col = df.get("kota_penempatan_mesin", pd.Series(dtype=str))
    if kota_col.empty or kota_col.dropna().empty:
        kota_col = df.get("kota_domisili", pd.Series(dtype=str))
    if kota_col.empty or kota_col.dropna().empty:
        st.info("Belum ada data kota.")
        return
    counts = kota_col.value_counts().reset_index()
    counts.columns = ["kota", "count"]
    top = counts.head(10)
    fig = px.bar(
        top, x="count", y="kota", orientation="h",
        color="count", color_continuous_scale="blues",
        text="count", template="plotly_dark",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=320, margin=dict(t=10, b=10, l=10, r=40),
        xaxis_title="Jumlah Lead", yaxis_title=None,
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_monthly_trend(df: pd.DataFrame):
    st.subheader("📈 Tren Lead per Bulan")
    creation = df.get("creation", pd.Series(dtype=str))
    if creation.empty or creation.dropna().empty:
        st.info("Belum ada data tanggal.")
        return
    ts = pd.to_datetime(creation, errors="coerce").dropna()
    if ts.empty:
        st.info("Data tanggal tidak valid.")
        return
    monthly = ts.dt.to_period("M").value_counts().sort_index()
    monthly.index = monthly.index.astype(str)
    fig = px.line(
        x=monthly.index, y=monthly.values,
        markers=True, template="plotly_dark",
    )
    fig.update_traces(
        line=dict(color="#3b82f6", width=3),
        marker=dict(size=8, color="#3b82f6"),
        hovertemplate="%{x}: %{y} lead",
    )
    fig.update_layout(
        height=350, margin=dict(t=10, b=40, l=10, r=10),
        xaxis_title="Bulan", yaxis_title="Lead Baru",
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_conversion_funnel(df: pd.DataFrame):
    st.subheader("🔄 Funnel Konversi")
    status_col = df.get("status_lead", pd.Series(dtype=str))
    if status_col.empty:
        st.info("Belum ada data status.")
        return
    # Funnel stages in order
    funnel_order = ["New", "Contact", "Meeting", "Qualified",
                    "Negotiation", "Approved", "Live", "DP Paid"]
    counts = {}
    for s in funnel_order:
        cnt = (status_col.astype(str).str.strip() == s).sum()
        if cnt > 0:
            counts[s] = cnt
    # Also add Lost
    lost = (status_col.astype(str).str.strip() == "Lost").sum()
    if lost > 0:
        counts["Lost"] = lost
    if not counts:
        st.info("Data funnel tidak tersedia.")
        return
    funnel_df = pd.DataFrame(list(counts.items()), columns=["stage", "count"])
    fig = px.funnel(
        funnel_df, x="count", y="stage",
        color="stage", color_discrete_map=STATUS_COLORS,
        template="plotly_dark", text="count",
    )
    fig.update_traces(textposition="inside", textfont=dict(size=14))
    fig.update_layout(
        height=400, margin=dict(t=10, b=10, l=10, r=10),
        yaxis_title=None, xaxis_title="Lead",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_budget_summary(df: pd.DataFrame):
    st.subheader("💰 Ringkasan Investasi")
    investasi = df.get("harga_investasi_dibahas", pd.Series(dtype=float))
    budget_str = df.get("budget_investasi", pd.Series(dtype=str))

    col1, col2 = st.columns(2)

    with col1:
        numeric_inv = investasi.fillna(0).astype(float)
        if numeric_inv.sum() > 0:
            avg_inv = numeric_inv[numeric_inv > 0].mean()
            max_inv = numeric_inv.max()
            st.metric("💰 Rata-rata Nilai Investasi", f"Rp{avg_inv:,.0f}")
            st.metric("🔺 Investasi Tertinggi", f"Rp{max_inv:,.0f}")
            st.metric("📊 Total Nilai Investasi", f"Rp{numeric_inv.sum():,.0f}")
        else:
            st.info("Data investasi numerik belum tersedia.")

    with col2:
        if not budget_str.dropna().empty:
            st.write("**Sebaran Budget Investasi**")
            budget_counts = budget_str.value_counts().reset_index()
            budget_counts.columns = ["range", "count"]
            fig = px.pie(
                budget_counts, names="range", values="count",
                template="plotly_dark", hole=0.4,
                color_discrete_sequence=CATEGORICAL_COLORS,
            )
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Data budget investasi belum tersedia.")

    # ── Kesiapan DP & Skema Bayar ──
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        dp_col = df.get("kesiapan_dp", pd.Series(dtype=str))
        if not dp_col.dropna().empty:
            st.write("**Kesiapan DP**")
            dp_counts = dp_col.value_counts().reset_index()
            dp_counts.columns = ["kesiapan", "count"]
            fig = px.bar(
                dp_counts, x="kesiapan", y="count", color="kesiapan",
                text="count", template="plotly_dark",
                color_discrete_sequence=CATEGORICAL_COLORS,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(height=260, showlegend=False, margin=dict(t=10, b=30, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        skema_col = df.get("skema_pembayaran", pd.Series(dtype=str))
        if not skema_col.dropna().empty:
            st.write("**Skema Pembayaran**")
            skema_counts = skema_col.value_counts().reset_index()
            skema_counts.columns = ["skema", "count"]
            fig = px.bar(
                skema_counts, x="skema", y="count", color="skema",
                text="count", template="plotly_dark",
                color_discrete_sequence=CATEGORICAL_COLORS,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(height=260, showlegend=False, margin=dict(t=10, b=30, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)


# ── NEW CHARTS ──

def _chart_pekerjaan_distribution(df: pd.DataFrame):
    """Pekerjaan / Bisnis calon mitra."""
    st.subheader("💼 Pekerjaan / Bisnis")
    col = df.get("pekerjaan_bisnis_saat_ini", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["pekerjaan", "count"]
    fig = px.pie(counts, names="pekerjaan", values="count",
                 template="plotly_dark", hole=0.4,
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_tahu_difotoin_distribution(df: pd.DataFrame):
    """Dari mana tahu Difotoin."""
    st.subheader("📢 Tahu Difotoin Dari")
    col = df.get("dari_mana_tahu_difotoin", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["sumber", "count"]
    fig = px.bar(counts, x="sumber", y="count", color="sumber",
                 text="count", template="plotly_dark",
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_status_lokasi_distribution(df: pd.DataFrame):
    """Status lokasi."""
    st.subheader("📍 Status Lokasi")
    col = df.get("status_lokasi", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["status", "count"]
    fig = px.bar(counts, x="status", y="count", color="status",
                 text="count", template="plotly_dark",
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_jenis_lokasi_distribution(df: pd.DataFrame):
    """Jenis lokasi (Mall, Cafe, etc)."""
    st.subheader("🏗️ Jenis Lokasi")
    col = df.get("jenis_lokasi", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["jenis", "count"]
    fig = px.pie(counts, names="jenis", values="count",
                 template="plotly_dark", hole=0.4,
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_potensi_lokasi_distribution(df: pd.DataFrame):
    """Potensi lokasi."""
    st.subheader("📈 Potensi Lokasi")
    col = df.get("potensi_lokasi", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["potensi", "count"]
    order = ["High", "Medium", "Low"]
    counts["sort"] = counts["potensi"].apply(lambda x: order.index(x) if x in order else 99)
    counts = counts.sort_values("sort")
    colors = {"High": "#22c55e", "Medium": "#f59e0b", "Low": "#ef4444"}
    fig = px.bar(counts, x="potensi", y="count", color="potensi",
                 color_discrete_map=colors, text="count",
                 template="plotly_dark", category_orders={"potensi": order})
    fig.update_traces(textposition="outside")
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_sudah_lokasi_distribution(df: pd.DataFrame):
    """Sudah punya lokasi."""
    st.subheader("🏠 Sudah Punya Lokasi")
    col = df.get("sudah_punya_lokasi", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["jawaban", "count"]
    fig = px.pie(counts, names="jawaban", values="count",
                 template="plotly_dark", hole=0.4,
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_unit_diminati_distribution(df: pd.DataFrame):
    """Jumlah unit diminati."""
    st.subheader("🔢 Unit Diminati")
    col = df.get("jumlah_unit_diminati", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["unit", "count"]
    fig = px.bar(counts, x="unit", y="count", color="unit",
                 text="count", template="plotly_dark",
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_kapan_mulai_distribution(df: pd.DataFrame):
    """Kapan ingin mulai."""
    st.subheader("📅 Kapan Mulai")
    col = df.get("kapan_ingin_mulai", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["waktu", "count"]
    fig = px.pie(counts, names="waktu", values="count",
                 template="plotly_dark", hole=0.4,
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_disposition_distribution(df: pd.DataFrame):
    """Disposition."""
    st.subheader("📋 Disposisi")
    col = df.get("disposition", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["dispo", "count"]
    colors = {"Active": "#22c55e", "Passive": "#f59e0b", "Warm": "#3b82f6", "Cold": "#6b7280", "Closed": "#ef4444"}
    fig = px.bar(counts, x="dispo", y="count", color="dispo",
                 color_discrete_map=colors, text="count",
                 template="plotly_dark")
    fig.update_traces(textposition="outside")
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_target_bep_distribution(df: pd.DataFrame):
    """Target BEP."""
    st.subheader("📊 Target BEP")
    col = df.get("target_bep", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["bep", "count"]
    fig = px.bar(counts, x="bep", y="count", color="bep",
                 text="count", template="plotly_dark",
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_next_step_distribution(df: pd.DataFrame):
    """Next step."""
    st.subheader("➡️ Next Step")
    col = df.get("next_step", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("−")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["step", "count"]
    fig = px.bar(counts, x="step", y="count", color="step",
                 text="count", template="plotly_dark",
                 color_discrete_sequence=CATEGORICAL_COLORS)
    fig.update_traces(textposition="outside")
    fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=40, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_sales_pic_performance(df: pd.DataFrame):
    """Sales PIC performance."""
    st.subheader("👨‍💼 Performa Sales PIC")
    col = df.get("sales_pic", pd.Series(dtype=str))
    if col.dropna().empty:
        st.info("Belum ada data sales PIC.")
        return
    counts = col.value_counts().reset_index()
    counts.columns = ["sales", "count"]
    counts = counts.sort_values("count", ascending=True)
    fig = px.bar(counts, x="count", y="sales", orientation="h",
                 color="count", color_continuous_scale="blues",
                 text="count", template="plotly_dark")
    fig.update_traces(textposition="outside")
    fig.update_layout(height=max(250, len(counts) * 40), showlegend=False,
                      margin=dict(t=10, b=10, l=10, r=40),
                      xaxis_title="Jumlah Lead", yaxis_title=None,
                      coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    # Detail per sales
    with st.expander("📋 Detail per Sales PIC", expanded=False):
        detail = df.groupby("sales_pic").agg(
            Total=("name", "count"),
            Qualified=("status_lead", lambda s: (s.astype(str).str.strip() == "Qualified").sum()),
            HighPrio=("priority", lambda s: (s.astype(str).str.strip() == "High").sum()),
            Negosiasi=("status_lead", lambda s: (s.astype(str).str.strip() == "Negotiation").sum()),
            Investasi=("harga_investasi_dibahas", "sum"),
        ).reset_index()
        detail.columns = ["Sales PIC", "Total", "Qualified", "High Prio", "Negosiasi", "Total Investasi"]
        detail["Total Investasi"] = detail["Total Investasi"].apply(
            lambda x: f"Rp{x:,.0f}" if x > 0 else "-")
        st.dataframe(detail, use_container_width=True, hide_index=True)


def _render_compact_table(df: pd.DataFrame):
    """Compact data table with all fields."""
    if df.empty:
        st.info("Tidak ada data.")
        return
    display = df.copy()
    col_map = dict(LEAD_KEMITRAAN_DISPLAY_NAMES)
    avail_cols = [c for c in col_map if c in display.columns]
    ordered = ["name", "nama_lengkap", "nomor_whatsapp", "email",
               "kota_domisili", "kota_penempatan_mesin", "status_lead",
               "priority", "source_lead", "sales_pic"]
    ordered = [c for c in ordered if c in avail_cols]
    remaining = [c for c in avail_cols if c not in ordered]
    display = display[ordered + remaining].rename(columns=col_map)
    st.dataframe(display, use_container_width=True, hide_index=True, height=350)


# ═══════════════════════════════════════════════
#  CONFIG FORM
# ═══════════════════════════════════════════════

def _render_config_form(cfg: dict):
    st.subheader("🔧 Konfigurasi ERPNext")
    with st.form("lk_config_form"):
        url = st.text_input("URL ERPNext", value=cfg.get("url", ""),
                            placeholder="https://erp.midory.id", key="lk_config_url")
        api_key = st.text_input("API Key", value=cfg.get("api_key", ""),
                                type="password", key="lk_config_key")
        api_secret = st.text_input("API Secret", value=cfg.get("api_secret", ""),
                                   type="password", key="lk_config_secret")
        submitted = st.form_submit_button("💾 Simpan & Uji Koneksi", type="primary")
        if submitted:
            if not url.strip() or not api_key.strip():
                st.error("URL dan API Key wajib diisi.")
            else:
                save_erpnext_config({
                    "url": url.strip().rstrip("/"),
                    "api_key": api_key.strip(),
                    "api_secret": api_secret.strip(),
                })
                ok, msg = check_connection("Lead%20Kemitraan")
                st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
                if ok:
                    rerun()


# ═══════════════════════════════════════════════
#  LEAD TABLE (read-only)
# ═══════════════════════════════════════════════

def _render_lead_table(df: pd.DataFrame):
    st.write(f"**{len(df)}** lead kemitraan ditemukan.")

    if df.empty:
        st.info("Tidak ada lead yang cocok dengan filter.")
        return

    display = df.copy()
    col_map = dict(LEAD_KEMITRAAN_DISPLAY_NAMES)
    avail_cols = [c for c in col_map if c in display.columns]

    preferred_order = [
        "name", "nama_lengkap", "nomor_whatsapp", "email",
        "kota_domisili", "pekerjaan_bisnis_saat_ini",
        "kota_penempatan_mesin", "jumlah_unit_diminati",
        "budget_investasi", "harga_investasi_dibahas",
        "status_lead", "priority", "disposition",
        "source_lead", "sales_pic",
    ]
    ordered = [c for c in preferred_order if c in avail_cols]
    remaining = [c for c in avail_cols if c not in ordered]
    final_cols = ordered + remaining

    display = display[final_cols].rename(columns=col_map)

    # Format currency
    investasi_col = col_map.get("harga_investasi_dibahas", "Nilai Investasi")
    if investasi_col in display.columns:
        display[investasi_col] = display[investasi_col].apply(
            lambda x: f"Rp{x:,.0f}" if pd.notna(x) and isinstance(x, (int, float)) and x > 0 else "-"
        )

    st.dataframe(display, use_container_width=True, hide_index=True, height=450)

    # ── Quick detail expander (no edit) ──
    lead_names = df["name"].tolist() if "name" in df.columns else []
    if lead_names:
        with st.expander("🔍 Lihat Detail Lead"):
            selected = st.selectbox(
                "Pilih Lead", lead_names,
                format_func=lambda x: _get_lead_label(df, x),
                key="lk_select_detail",
            )
            if selected:
                row = df[df["name"] == selected]
                if not row.empty:
                    r = row.iloc[0]
                    _show_detail_card(r)


def _get_lead_label(df: pd.DataFrame, name: str) -> str:
    row = df[df["name"] == name]
    if row.empty:
        return name
    r = row.iloc[0]
    parts = [str(r.get("nama_lengkap", "")), str(r.get("kota_domisili", ""))]
    return " — ".join(p for p in parts if p.strip())


def _show_detail_card(r: pd.Series):
    """Display lead details in a clean card layout (read-only)."""
    col_map = dict(LEAD_KEMITRAAN_DISPLAY_NAMES)
    detail_fields = [
        ("nama_lengkap", "👤"), ("nomor_whatsapp", "📞"), ("email", "📧"),
        ("kota_domisili", "🏙️"), ("pekerjaan_bisnis_saat_ini", "💼"),
        ("kota_penempatan_mesin", "📍"), ("sudah_punya_lokasi", "🏠"),
        ("tempat_instalasi", "🏢"), ("jumlah_unit_diminati", "🔢"),
        ("kapan_ingin_mulai", "📅"), ("dari_mana_tahu_difotoin", "📢"),
        ("source_lead", "📢"), ("priority", "🎯"), ("status_lead", "✅"),
        ("disposition", "📋"), ("budget_investasi", "💰"),
        ("jumlah_unit_final", "🎯"), ("harga_investasi_dibahas", "💵"),
        ("skema_pembayaran", "💳"), ("kesiapan_dp", "💪"),
        ("target_bep", "📊"), ("status_lokasi", "📍"),
        ("jenis_lokasi", "🏗️"), ("potensi_lokasi", "📈"),
        ("next_follow_up", "📆"), ("hasil_follow_up_terakhir", "📝"),
        ("next_step", "➡️"), ("sales_pic", "👨‍💼"),
        ("creation", "📅"), ("modified", "🔄"),
    ]
    c1, c2 = st.columns(2)
    for i, (field, emoji) in enumerate(detail_fields):
        val = r.get(field)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        label = col_map.get(field, field)
        text = f"Rp{val:,.0f}" if isinstance(val, (int, float)) and field in ("harga_investasi_dibahas",) else str(val)
        with (c1 if i % 2 == 0 else c2):
            st.markdown(f"**{emoji} {label}:** {text}")
