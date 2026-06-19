"""📊 Lead Permanen — Dashboard untuk monitoring lead dari ERPNext.

2 tab:
  - Ringkasan Global: total lead, distribusi status, kota, kategori, sumber info.
  - Pantauan Team Lead: performa per staff, filter, expandable detail.
"""

from typing import Optional, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.erpnext import (
    load_erpnext_config,
    save_erpnext_config,
    check_connection,
    fetch_leads,
    fetch_lead_owners,
    aggregate_lead_data,
    aggregate_team_performance,
    FIELD_DISPLAY_NAMES,
    LEAD_FIELDS,
)
from components.compat import rerun, HAS_COLUMN_CONFIG

# ── Dark-theme colour palette ──
BG_COLOR = "#111827"
PANEL_COLOR = "#182235"
PANEL_SOFT = "#202c43"
TEXT_COLOR = "#f8fafc"
MUTED_COLOR = "#94a3b8"
ACCENT_BLUE = "#38bdf8"
ACCENT_GREEN = "#22c55e"
ACCENT_YELLOW = "#f59e0b"
ACCENT_RED = "#ef4444"
ACCENT_PURPLE = "#a78bfa"
ACCENT_PINK = "#f472b6"
CHART_COLORS = [
    "#38bdf8", "#22c55e", "#f59e0b", "#ef4444",
    "#a78bfa", "#f472b6", "#fb923c", "#4ade80",
    "#facc15", "#2dd4bf", "#818cf8", "#e879f9",
]

CHART_LAYOUT = dict(
    paper_bgcolor=BG_COLOR,
    plot_bgcolor=BG_COLOR,
    font=dict(color=TEXT_COLOR, size=12),
    margin=dict(l=40, r=20, t=40, b=40),
    hovermode="closest",
    legend=dict(font=dict(color=TEXT_COLOR), orientation="h", y=-0.2),
)


def _render_config_form(cfg: dict):
    """Form konfigurasi ERPNext (URL, API Key, Secret) inline."""
    st.subheader("🔧 Konfigurasi ERPNext")
    st.caption("Masukkan kredensial ERPNext untuk mengambil data Lead.")

    url = st.text_input("URL ERPNext", value=cfg.get("url", ""), placeholder="https://erp.midory.id")
    api_key = st.text_input("API Key", value=cfg.get("api_key", ""), type="password" if cfg.get("api_key") else "default")
    api_secret = st.text_input("API Secret", value=cfg.get("api_secret", ""), type="password" if cfg.get("api_secret") else "default")

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        test_clicked = st.button("🧪 Test Koneksi", use_container_width=True)
    with col2:
        save_clicked = st.button("💾 Simpan", type="primary", use_container_width=True)
    with col3:
        st.caption("")

    if test_clicked:
        cfg_test = {"url": url.strip(), "api_key": api_key.strip(), "api_secret": api_secret.strip()}
        ok, msg = check_connection(doctype="Lead")
        if ok:
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ {msg}")

    if save_clicked:
        save_erpnext_config({"url": url.strip(), "api_key": api_key.strip(), "api_secret": api_secret.strip()})
        st.success("✅ Konfigurasi ERPNext tersimpan!")
        rerun()


def _metric_card(label: str, value, delta: Optional[str] = None):
    """Styled metric card."""
    st.markdown(
        f"""
        <div style="background:linear-gradient(180deg,#1f2937,#151e2f);
                    border:1px solid #334155;border-radius:.75rem;
                    padding:.9rem 1rem;text-align:center;
                    box-shadow:0 8px 24px rgba(0,0,0,.18)">
            <div style="font-size:.8rem;color:#94a3b8;margin-bottom:.25rem">{label}</div>
            <div style="font-size:1.5rem;font-weight:800;color:#f8fafc">{value}</div>
            {f'<div style="font-size:.75rem;color:#22c55e">{delta}</div>' if delta else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _tab_ringkasan_global():
    """Tab 1: Ringkasan Global — agregat statistik + chart."""
    st.markdown("### 🌍 Ringkasan Global Lead")

    with st.spinner("Mengambil data lead dari ERPNext..."):
        df = fetch_leads(limit=5000)

    if df.empty:
        st.warning("⚠️ Tidak ada data lead dari ERPNext.")
        st.info("Pastikan Lead DocType di ERPNext sudah terisi data.")
        return

    # ── Aggregate ──
    agg = aggregate_lead_data(df)
    fmt_num = lambda n: f"{n:,}"

    # ── Metric cards ──
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card("Total Lead (All Time)", fmt_num(agg["total_all"]))
    with c2:
        _metric_card("Hari Ini", fmt_num(agg["total_today"]))
    with c3:
        _metric_card("Minggu Ini", fmt_num(agg["total_this_week"]))
    with c4:
        _metric_card("Bulan Ini", fmt_num(agg["total_this_month"]))

    st.markdown("---")

    # ── 2-column chart layout ──
    col_left, col_right = st.columns(2)

    # --- Kiri: Pie Status + Bar Kota ---
    with col_left:
        # Pie: Status Distribution
        if agg["status_distribution"]:
            status_df = pd.DataFrame(
                list(agg["status_distribution"].items()),
                columns=["Status", "Jumlah"],
            ).sort_values("Jumlah", ascending=False)

            fig = px.pie(
                status_df,
                names="Status",
                values="Jumlah",
                title="📊 Distribusi Status Lead",
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(**CHART_LAYOUT, height=360)
            st.plotly_chart(fig, use_container_width=True)

        # Bar: Top 10 Kota
        if agg["city_top10"]:
            city_df = pd.DataFrame(
                agg["city_top10"], columns=["Kota", "Jumlah"]
            )
            fig = px.bar(
                city_df,
                x="Jumlah",
                y="Kota",
                title="🏙️ Top 10 Kota",
                orientation="h",
                text_auto=True,
                color_discrete_sequence=[ACCENT_BLUE],
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                **CHART_LAYOUT,
                height=360,
                yaxis=dict(autorange="reversed"),
                xaxis=dict(title="Jumlah Lead"),
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- Kanan: Pie Source + Bar Kategori ---
    with col_right:
        # Pie: Source Distribution
        if agg["source_distribution"]:
            src_df = pd.DataFrame(
                list(agg["source_distribution"].items()),
                columns=["Sumber Info", "Jumlah"],
            ).sort_values("Jumlah", ascending=False)

            fig = px.pie(
                src_df,
                names="Sumber Info",
                values="Jumlah",
                title="📢 Sumber Info (Tahu Difotoin Dari)",
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(**CHART_LAYOUT, height=360)
            st.plotly_chart(fig, use_container_width=True)

        # Bar: Kategori Tempat
        if agg["kategori_tempat"]:
            kat_df = pd.DataFrame(
                list(agg["kategori_tempat"].items()),
                columns=["Kategori Tempat", "Jumlah"],
            ).sort_values("Jumlah", ascending=False)

            fig = px.bar(
                kat_df,
                x="Jumlah",
                y="Kategori Tempat",
                title="🏪 Kategori Tempat",
                orientation="h",
                text_auto=True,
                color_discrete_sequence=[ACCENT_GREEN],
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                **CHART_LAYOUT,
                height=360,
                yaxis=dict(autorange="reversed"),
                xaxis=dict(title="Jumlah Lead"),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Recent leads table ──
    st.markdown("---")
    with st.expander("📋 Data Lead Terbaru", expanded=False):
        display_cols = [
            c for c in [
                "lead_name", "company_name", "city", "status",
                "custom_kategori_tempat", "source", "lead_owner", "creation",
            ] if c in df.columns
        ]
        if display_cols:
            recent = df[display_cols].copy()
            # Rename to display names
            renamed = {}
            for c in display_cols:
                renamed[c] = FIELD_DISPLAY_NAMES.get(c, c)
            recent = recent.rename(columns=renamed)

            # Format date
            if "Tgl Dibuat" in recent.columns:
                recent["Tgl Dibuat"] = pd.to_datetime(recent["Tgl Dibuat"], errors="coerce").dt.strftime("%d/%m/%Y")

            st.dataframe(
                recent.sort_values("Tgl Dibuat" if "Tgl Dibuat" in recent.columns else recent.columns[0], ascending=False)
                .head(100),
                use_container_width=True,
                hide_index=True,
            )


def _tab_pantauan_team():
    """Tab 2: Pantauan Team Lead — performa per staff + filter + detail."""
    st.markdown("### 👥 Pantauan Team Lead")

    with st.spinner("Mengambil data lead dari ERPNext..."):
        df = fetch_leads(limit=5000)

    if df.empty:
        st.warning("⚠️ Tidak ada data lead dari ERPNext.")
        return

    if "lead_owner" not in df.columns or df["lead_owner"].isna().all():
        st.info("ℹ️ Belum ada data lead_owner (Sales PIC) di Lead ERPNext.")
        return

    # ── Staff list ──
    owners = sorted(df["lead_owner"].dropna().unique().tolist())

    # ── Filter multiselect ──
    selected_owners = st.multiselect(
        "👤 Filter Staff",
        options=owners,
        default=owners,
        key="lead_team_filter",
    )

    if not selected_owners:
        st.info("Pilih minimal 1 staff untuk melihat data.")
        return

    # Filter dataframe
    filtered = df[df["lead_owner"].isin(selected_owners)].copy()

    # ── Aggregate performance ──
    perf = aggregate_team_performance(filtered)

    if perf.empty:
        st.info("Tidak ada data performa untuk staff terpilih.")
        return

    # ── Bar chart perbandingan ──
    perf_melted = perf.melt(
        id_vars=["lead_owner"],
        value_vars=["Open", "Contacted", "Converted", "Lost", "Total"],
        var_name="Kategori",
        value_name="Jumlah",
    )

    fig = px.bar(
        perf_melted,
        x="lead_owner",
        y="Jumlah",
        color="Kategori",
        title="📊 Perbandingan Kinerja Staff",
        barmode="group",
        text_auto=True,
        color_discrete_map={
            "Open": ACCENT_BLUE,
            "Contacted": ACCENT_YELLOW,
            "Converted": ACCENT_GREEN,
            "Lost": ACCENT_RED,
            "Total": ACCENT_PURPLE,
        },
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **CHART_LAYOUT,
        height=400,
        xaxis=dict(title="Staff"),
        yaxis=dict(title="Jumlah Lead"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Table agregat ──
    st.markdown("#### 📋 Ringkasan Performa Staff")

    perf_display = perf.rename(
        columns={
            "lead_owner": "Staff",
            "Open": "Open",
            "Contacted": "Contacted",
            "Converted": "Converted",
            "Lost": "Lost",
            "Total": "Total Lead",
        }
    )
    # Add conversion rate
    perf_display["Conv. Rate"] = perf_display.apply(
        lambda r: f"{r['Converted'] / r['Total Lead'] * 100:.1f}%" if r['Total Lead'] > 0 else "0%",
        axis=1,
    )
    st.dataframe(perf_display, use_container_width=True, hide_index=True)

    # ── Expandable detail per staff ──
    st.markdown("#### 🔍 Detail Lead per Staff")
    display_detail_cols = [
        c for c in [
            "lead_name", "company_name", "city", "status",
            "custom_kategori_tempat", "custom_tipe_tempat",
            "source", "creation",
        ] if c in filtered.columns
    ]

    for owner in selected_owners:
        owner_df = filtered[filtered["lead_owner"] == owner]
        if owner_df.empty:
            continue

        with st.expander(f"👤 {owner} — {len(owner_df)} lead"):
            if display_detail_cols:
                detail = owner_df[display_detail_cols].copy()
                renamed = {}
                for c in display_detail_cols:
                    renamed[c] = FIELD_DISPLAY_NAMES.get(c, c)
                detail = detail.rename(columns=renamed)

                if "Tgl Dibuat" in detail.columns:
                    detail["Tgl Dibuat"] = pd.to_datetime(
                        detail["Tgl Dibuat"], errors="coerce"
                    ).dt.strftime("%d/%m/%Y")

                st.dataframe(
                    detail.sort_values(
                        "Tgl Dibuat" if "Tgl Dibuat" in detail.columns else detail.columns[0],
                        ascending=False,
                    ),
                    use_container_width=True,
                    hide_index=True,
                )


# ================= MAIN PAGE =================

def show_lead_permanen_page():
    """Main entry point — renders the Lead Permanen page with 2 tabs."""
    st.title("📋 Lead Permanen")
    st.caption("Monitoring dan analisis data Lead dari ERPNext — realtime via API.")

    # ── Config check ──
    cfg = load_erpnext_config()

    if not cfg.get("url") or not cfg.get("api_key"):
        st.warning("⚠️ Konfigurasi ERPNext belum diisi.")
        _render_config_form(cfg)
        return
    else:
        connected_ok, connected_msg = check_connection(doctype="Lead")
        if not connected_ok:
            st.warning(f"⚠️ {connected_msg}")
            with st.expander("🔧 Konfigurasi ERPNext"):
                _render_config_form(cfg)
            # Still show UI with potentially stale data
        else:
            st.success(f"✅ {connected_msg}")

    # ── Tab ──
    tab1, tab2 = st.tabs(["🌍 Ringkasan Global", "👥 Pantauan Team Lead"])

    with tab1:
        _tab_ringkasan_global()

    with tab2:
        _tab_pantauan_team()
