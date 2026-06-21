"""📋 Lead Partnership — analytics dashboard & data viewer for partnership leads (machine placement).
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
    fetch_lead_partnerships,
    get_lp_cache_info,
    LEAD_PARTNERSHIP_DISPLAY_NAMES,
)
from components.compat import rerun


# ── Color palette ──
STATUS_COLORS = {
    "New": "#6366f1", "Contact": "#06b6d4", "Need Info": "#f59e0b",
    "Qualified": "#22c55e", "Negotiation": "#f97316", "Approved": "#14b8a6",
    "Live": "#22c55e", "Lost": "#ef4444",
}
PRIORITY_COLORS = {"High": "#ef4444", "Medium": "#f59e0b", "Low": "#6b7280"}
CAT_COLORS = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel1


# ═══════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════

def show_lead_partnership_page():
    st.title("📋 Lead Partnership")
    st.caption(
        "Dashboard & data calon partner penempatan mesin dari ERPNext — "
        "analisis untuk pengambilan keputusan."
    )

    # ── Config ──
    cfg = load_erpnext_config()
    connected = False
    if not cfg.get("url") or not cfg.get("api_key"):
        _render_config_form(cfg); return
    else:
        ok, msg = check_connection("Lead%20Partnership")
        connected = ok
        if not ok:
            st.warning(f"⚠️ {msg}")
            with st.expander("🔧 Konfigurasi ERPNext"):
                _render_config_form(cfg)

    # ── Fetch ──
    df = fetch_lead_partnerships(limit=5000) if connected else pd.DataFrame()
    if df.empty:
        st.info("Belum ada data Lead Partnership dari ERPNext.")
        if not connected:
            st.caption("Pastikan konfigurasi ERPNext benar dan koneksi tersambung.")
        return

    # ── Global filters ──
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1.5, 1.5, 1])
    with col_f1:
        search_q = st.text_input("🔍 Cari (nama, tempat, PIC, kota)", key="lp_search_g")
    with col_f2:
        sopts = ["Semua Status"] + sorted(df["status_lead"].dropna().unique())
        filter_status = st.selectbox("Status", sopts, key="lp_filter_status_g")
    with col_f3:
        jopts = ["Semua Jenis"] + sorted(df["jenis_partnership"].dropna().unique())
        filter_jenis = st.selectbox("Jenis Partnership", jopts, key="lp_filter_jenis_g")
    with col_f4:
        refresh = st.button("🔄 Refresh", type="secondary", use_container_width=True)

    ci = get_lp_cache_info()
    if ci:
        st.caption(f"💾 Data lokal: {ci.get('count',0)} record — terakhir sync {ci.get('last_sync','-')[:16]}")

    # ── Apply filters ──
    fdf = df.copy()
    if filter_status and filter_status != "Semua Status":
        fdf = fdf[fdf["status_lead"].astype(str).str.strip() == filter_status]
    if filter_jenis and filter_jenis != "Semua Jenis":
        fdf = fdf[fdf["jenis_partnership"].astype(str).str.strip() == filter_jenis]
    if search_q.strip():
        q = search_q.strip().lower()
        mask = (
            fdf.get("nama_pic", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("nama_tempat", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("nama_perusahaan__lembaga__venue_jika_ada", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("kota_lokasi", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("sales_pic", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | fdf.get("name", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        )
        fdf = fdf[mask].copy()

    tab_dash, tab_list = st.tabs(["📊 Dashboard Lead Partnership", "📋 Daftar Lead"])
    with tab_dash:
        _render_dashboard(fdf)
    with tab_list:
        _render_lead_table(fdf)


# ═══════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════

def _render_dashboard(df: pd.DataFrame):
    total = len(df)
    qualified = len(df[df.get("status_lead","").astype(str).str.strip() == "Qualified"])
    high_prio = len(df[df.get("priority","").astype(str).str.strip() == "High"])
    live = len(df[df.get("status_lead","").astype(str).str.strip() == "Live"])
    total_sewa = df.get("harga_sewa", pd.Series(dtype=float)).fillna(0).astype(float).sum()
    unique_kota = df.get("kota_lokasi", pd.Series(dtype=str)).dropna().nunique()

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1: st.metric("📋 Total", total)
    with m2: st.metric("✅ Qualified", qualified)
    with m3: st.metric("🔴 High Prio", high_prio)
    with m4: st.metric("💚 Live", live)
    with m5: st.metric("💰 Total Sewa", f"Rp{total_sewa:,.0f}" if total_sewa > 0 else "-")
    with m6: st.metric("📍 Kota", unique_kota)
    st.markdown("---")

    # Row 1: Funnel + Trend
    c1, c2 = st.columns([1.2, 1])
    with c1: _chart_funnel(df)
    with c2: _chart_trend(df)
    st.markdown("---")

    # Row 2: Status, Priority, Jenis Partnership
    c1, c2, c3 = st.columns(3)
    with c1: _chart_status(df)
    with c2: _chart_priority(df)
    with c3: _chart_jenis(df)
    st.markdown("---")

    # Row 3: Kota, Source, Skema
    c1, c2, c3 = st.columns(3)
    with c1: _chart_kota(df)
    with c2: _chart_source(df)
    with c3: _chart_skema(df)
    st.markdown("---")

    # Row 4: Jenis Lokasi, Tipe Lokasi, Sales PIC
    c1, c2, c3 = st.columns(3)
    with c1: _chart_jenis_lokasi(df)
    with c2: _chart_tipe_lokasi(df)
    with c3: _chart_sales_pic(df)
    st.markdown("---")

    # Row 5: Revenue & Sewa Summary
    _chart_revenue_summary(df)
    st.markdown("---")

    # Row 6: Kelayakan
    c1, c2, c3 = st.columns(3)
    with c1: _chart_kelayakan_space(df)
    with c2: _chart_kelayakan_listrik(df)
    with c3: _chart_kelayakan_operasional(df)
    st.markdown("---")

    # Row 7: Raw data
    with st.expander("📋 Lihat Semua Data", expanded=False):
        _render_compact_table(df)


# ═══════════════════════════════════════════════
#  CHART FUNCTIONS
# ═══════════════════════════════════════════════

def _chart_funnel(df):
    st.subheader("🔄 Funnel Konversi")
    sc = df.get("status_lead", pd.Series(dtype=str))
    if sc.empty: st.info("−"); return
    order = ["New", "Contact", "Need Info", "Qualified", "Negotiation", "Approved", "Live", "Lost"]
    d = {s: (sc.astype(str).str.strip() == s).sum() for s in order if (sc.astype(str).str.strip() == s).sum() > 0}
    if not d: st.info("−"); return
    fd = pd.DataFrame(list(d.items()), columns=["stage","count"])
    fig = px.funnel(fd, x="count", y="stage", color="stage",
                    color_discrete_map=STATUS_COLORS, text="count", template="plotly_dark")
    fig.update_traces(textposition="inside", textfont=dict(size=14))
    fig.update_layout(height=400, margin=dict(t=10,b=10,l=10,r=10), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def _chart_trend(df):
    st.subheader("📈 Tren per Bulan")
    c = df.get("creation", pd.Series(dtype=str))
    if c.dropna().empty: st.info("−"); return
    ts = pd.to_datetime(c, errors="coerce").dropna()
    if ts.empty: st.info("−"); return
    m = ts.dt.to_period("M").value_counts().sort_index()
    m.index = m.index.astype(str)
    fig = px.line(x=m.index, y=m.values, markers=True, template="plotly_dark")
    fig.update_traces(line=dict(color="#3b82f6", width=3), marker=dict(size=8))
    fig.update_layout(height=350, margin=dict(t=10,b=40,l=10,r=10), xaxis_title="Bulan", yaxis_title="Lead")
    st.plotly_chart(fig, use_container_width=True)


def _chart_status(df):
    st.subheader("📊 Status")
    sc = df.get("status_lead", pd.Series(dtype=str)).dropna()
    if sc.empty: st.info("−"); return
    co = sc.value_counts().reset_index(); co.columns = ["s","c"]
    fig = px.bar(co, x="s", y="c", color="s", color_discrete_map=STATUS_COLORS,
                 text="c", template="plotly_dark")
    fig.update_traces(textposition="outside"); fig.update_layout(height=300, showlegend=False, margin=dict(t=10,b=40,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_priority(df):
    st.subheader("🎯 Prioritas")
    pc = df.get("priority", pd.Series(dtype=str)).dropna()
    if pc.empty: st.info("−"); return
    co = pc.value_counts().reset_index(); co.columns = ["p","c"]
    fig = px.pie(co, names="p", values="c", color="p", color_discrete_map=PRIORITY_COLORS,
                 template="plotly_dark", hole=0.4)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_jenis(df):
    st.subheader("🏷️ Jenis Partnership")
    jc = df.get("jenis_partnership", pd.Series(dtype=str)).dropna()
    if jc.empty: st.info("−"); return
    co = jc.value_counts().reset_index(); co.columns = ["j","c"]
    fig = px.bar(co, x="j", y="c", color="j", text="c", template="plotly_dark",
                 color_discrete_sequence=CAT_COLORS)
    fig.update_traces(textposition="outside"); fig.update_layout(height=300, showlegend=False, margin=dict(t=10,b=40,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_kota(df):
    st.subheader("🏙️ Kota")
    kc = df.get("kota_lokasi", pd.Series(dtype=str)).dropna()
    if kc.empty: st.info("−"); return
    co = kc.value_counts().head(10).reset_index(); co.columns = ["kota","c"]
    fig = px.bar(co, x="c", y="kota", orientation="h", color="c",
                 color_continuous_scale="blues", text="c", template="plotly_dark")
    fig.update_traces(textposition="outside"); fig.update_layout(height=300, showlegend=False,
                      margin=dict(t=10,b=10,l=10,r=40), xaxis_title="Lead", yaxis_title=None, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)


def _chart_source(df):
    st.subheader("📢 Sumber Lead")
    sc = df.get("source_lead", pd.Series(dtype=str)).dropna()
    if sc.empty: st.info("−"); return
    co = sc.value_counts().reset_index(); co.columns = ["s","c"]
    fig = px.pie(co, names="s", values="c", template="plotly_dark", hole=0.4,
                 color_discrete_sequence=CAT_COLORS)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_skema(df):
    st.subheader("🤝 Skema Kerjasama")
    sc = df.get("skema_kerja_sama_yang_terbuka", pd.Series(dtype=str)).dropna()
    if sc.empty: st.info("−"); return
    co = sc.value_counts().reset_index(); co.columns = ["skema","c"]
    fig = px.bar(co, x="skema", y="c", color="skema", text="c", template="plotly_dark",
                 color_discrete_sequence=CAT_COLORS)
    fig.update_traces(textposition="outside"); fig.update_layout(height=300, showlegend=False, margin=dict(t=10,b=40,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_jenis_lokasi(df):
    st.subheader("🏗️ Jenis Lokasi")
    jc = df.get("jenis_lokasi", pd.Series(dtype=str)).dropna()
    if jc.empty: st.info("−"); return
    co = jc.value_counts().reset_index(); co.columns = ["jl","c"]
    fig = px.pie(co, names="jl", values="c", template="plotly_dark", hole=0.4,
                 color_discrete_sequence=CAT_COLORS)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_tipe_lokasi(df):
    st.subheader("🔄 Tipe Lokasi")
    tc = df.get("tipe_lokasi", pd.Series(dtype=str)).dropna()
    if tc.empty: st.info("−"); return
    co = tc.value_counts().reset_index(); co.columns = ["tl","c"]
    colors = {"Indoor": "#3b82f6", "Outdoor": "#f59e0b", "Semi-Outdoor": "#8b5cf6"}
    fig = px.bar(co, x="tl", y="c", color="tl", color_discrete_map=colors,
                 text="c", template="plotly_dark")
    fig.update_traces(textposition="outside"); fig.update_layout(height=300, showlegend=False, margin=dict(t=10,b=40,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_sales_pic(df):
    st.subheader("👨‍💼 Sales PIC")
    sp = df.get("sales_pic_full", pd.Series(dtype=str))
    if sp.dropna().empty: sp = df.get("sales_pic", pd.Series(dtype=str))
    if sp.dropna().empty: st.info("−"); return
    co = sp.value_counts().reset_index(); co.columns = ["sales","c"]
    co = co.sort_values("c", ascending=True)
    fig = px.bar(co, x="c", y="sales", orientation="h", color="c",
                 color_continuous_scale="blues", text="c", template="plotly_dark")
    fig.update_traces(textposition="outside")
    fig.update_layout(height=max(250, len(co)*40), showlegend=False, margin=dict(t=10,b=10,l=10,r=40),
                      xaxis_title="Lead", yaxis_title=None, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)


def _chart_revenue_summary(df):
    st.subheader("💰 Ringkasan Revenue & Sewa")

    # Harga Sewa
    sewa = df.get("harga_sewa", pd.Series(dtype=float)).fillna(0).astype(float)
    revenue = df.get("potensi_revenue", pd.Series(dtype=float)).fillna(0).astype(float)
    rr = df.get("revenue_share", pd.Series(dtype=str))

    c1, c2, c3 = st.columns(3)
    with c1:
        if sewa.sum() > 0:
            st.metric("💰 Rata-rata Sewa", f"Rp{sewa[sewa>0].mean():,.0f}")
            st.metric("🔺 Sewa Tertinggi", f"Rp{sewa.max():,.0f}")
            st.metric("📊 Total Sewa", f"Rp{sewa.sum():,.0f}")
        else:
            st.info("Data sewa belum tersedia.")
    with c2:
        if revenue.sum() > 0:
            st.metric("📈 Rata-rata Potensi Revenue", f"Rp{revenue[revenue>0].mean():,.0f}")
            st.metric("🔺 Revenue Tertinggi", f"Rp{revenue.max():,.0f}")
            st.metric("📊 Total Potensi Revenue", f"Rp{revenue.sum():,.0f}")
        else:
            st.info("Data potensi revenue belum tersedia.")
    with c3:
        if rr.dropna().empty:
            st.info("Data revenue share belum tersedia.")
        else:
            st.write("**Revenue Share**")
            rco = rr.value_counts().reset_index(); rco.columns = ["rs","c"]
            fig = px.pie(rco, names="rs", values="c", template="plotly_dark", hole=0.4,
                         color_discrete_sequence=CAT_COLORS)
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(height=280, margin=dict(t=10,b=10,l=10,r=10))
            st.plotly_chart(fig, use_container_width=True)


def _chart_kelayakan_space(df):
    st.subheader("📐 Kelayakan Space")
    co = df.get("kelayakan_space", pd.Series(dtype=str)).dropna()
    if co.empty: st.info("−"); return
    colors = {"Layak": "#22c55e", "Tidak Layak": "#ef4444", "Perlu Review": "#f59e0b"}
    cc = co.value_counts().reset_index(); cc.columns = ["k","c"]
    fig = px.pie(cc, names="k", values="c", color="k", color_discrete_map=colors,
                 template="plotly_dark", hole=0.4)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_kelayakan_listrik(df):
    st.subheader("⚡ Kelayakan Listrik")
    co = df.get("kelayakan_listrik", pd.Series(dtype=str)).dropna()
    if co.empty: st.info("−"); return
    colors = {"Layak": "#22c55e", "Tidak Layak": "#ef4444", "Perlu Review": "#f59e0b"}
    cc = co.value_counts().reset_index(); cc.columns = ["k","c"]
    fig = px.pie(cc, names="k", values="c", color="k", color_discrete_map=colors,
                 template="plotly_dark", hole=0.4)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


def _chart_kelayakan_operasional(df):
    st.subheader("🔧 Kelayakan Operasional")
    co = df.get("kelayakan_operasional", pd.Series(dtype=str)).dropna()
    if co.empty: st.info("−"); return
    colors = {"Layak": "#22c55e", "Tidak Layak": "#ef4444", "Perlu Review": "#f59e0b"}
    cc = co.value_counts().reset_index(); cc.columns = ["k","c"]
    fig = px.pie(cc, names="k", values="c", color="k", color_discrete_map=colors,
                 template="plotly_dark", hole=0.4)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    fig.update_layout(height=300, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════
#  CONFIG FORM
# ═══════════════════════════════════════════════

def _render_config_form(cfg: dict):
    st.subheader("🔧 Konfigurasi ERPNext")
    with st.form("lp_config_form"):
        url = st.text_input("URL", value=cfg.get("url",""), key="lp_cfg_url")
        key = st.text_input("API Key", value=cfg.get("api_key",""), type="password", key="lp_cfg_key")
        sec = st.text_input("API Secret", value=cfg.get("api_secret",""), type="password", key="lp_cfg_sec")
        if st.form_submit_button("💾 Simpan", type="primary"):
            if not url.strip() or not key.strip(): st.error("URL & API Key wajib.")
            else:
                save_erpnext_config({"url":url.strip().rstrip("/"),"api_key":key.strip(),"api_secret":sec.strip()})
                ok, msg = check_connection("Lead%20Partnership")
                st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
                if ok: rerun()


# ═══════════════════════════════════════════════
#  LEAD TABLE (read-only)
# ═══════════════════════════════════════════════

def _render_lead_table(df: pd.DataFrame):
    st.write(f"**{len(df)}** lead partnership ditemukan.")
    if df.empty: st.info("Tidak ada data."); return

    display = df.copy()
    cm = dict(LEAD_PARTNERSHIP_DISPLAY_NAMES)
    avail = [c for c in cm if c in display.columns]
    preferred = ["name","nama_pic","nama_perusahaan__lembaga__venue_jika_ada","nama_tempat",
                  "jenis_partnership","kota_lokasi","status_lead","priority","source_lead","sales_pic"]
    ordered = [c for c in preferred if c in avail]
    remaining = [c for c in avail if c not in ordered]
    display = display[ordered + remaining].rename(columns=cm)

    # Format currency
    for col_key, label in [("harga_sewa","Harga Sewa"), ("potensi_revenue","Potensi Revenue")]:
        lbl = cm.get(col_key, label)
        if lbl in display.columns:
            display[lbl] = display[lbl].apply(
                lambda x: f"Rp{x:,.0f}" if pd.notna(x) and isinstance(x,(int,float)) and x>0 else "-")

    st.dataframe(display, use_container_width=True, hide_index=True, height=450)

    # Detail expander
    names = df["name"].tolist() if "name" in df.columns else []
    if names:
        with st.expander("🔍 Lihat Detail Lead"):
            sel = st.selectbox("Pilih Lead", names, format_func=lambda x: _get_label(df, x), key="lp_detail_sel")
            if sel:
                row = df[df["name"] == sel]
                if not row.empty:
                    _show_detail(row.iloc[0])


def _get_label(df, name):
    row = df[df["name"] == name]
    if row.empty: return name
    r = row.iloc[0]
    return " — ".join(str(r.get(c,"")) for c in ("nama_pic","nama_tempat","kota_lokasi") if str(r.get(c,"")).strip())


def _show_detail(r):
    cm = dict(LEAD_PARTNERSHIP_DISPLAY_NAMES)
    fields = [
        ("nama_pic","👤"),("nama_perusahaan__lembaga__venue_jika_ada","🏢"),("nama_tempat","📍"),
        ("jenis_partnership","🏷️"),("kota_lokasi","🏙️"),("jenis_lokasi","🏗️"),("tipe_lokasi","🔄"),
        ("skema_kerja_sama_yang_terbuka","🤝"),("status_lead","✅"),("source_lead","📢"),
        ("sales_pic","👨‍💼"),("sales_pic_full","👨‍💼"),("jabatan_pic","📋"),("nomor_whatsapp_pic","📞"),
        ("email_pic","📧"),("area_penempatan","📍"),("alamat__link_google_maps","🗺️"),
        ("estimasi_pengunjung_per_hari","👥"),("space_tersedia","📐"),("listrik_tersedia","⚡"),
        ("kelayakan_space","✅"),("kelayakan_listrik","✅"),("kelayakan_operasional","✅"),
        ("pic_responsif","📞"),("potensi_revenue","💰"),("priority","🎯"),
        ("harga_sewa","💵"),("revenue_share","📊"),("minimum_payment","📉"),("minimum_kontrak","📅"),
        ("skema_final","📋"),("last_follow_up","📆"),("next_follow_up","📆"),("hasil_follow_up","📝"),
        ("decision","📋"),("lost_reason","❌"),("creation","📅"),("modified","🔄"),
    ]
    c1, c2 = st.columns(2)
    for i, (f, e) in enumerate(fields):
        v = r.get(f)
        if v is None or (isinstance(v, float) and pd.isna(v)): continue
        lbl = cm.get(f, f)
        txt = f"Rp{v:,.0f}" if isinstance(v,(int,float)) and f in ("harga_sewa","potensi_revenue","minimum_payment") else str(v)
        with (c1 if i%2==0 else c2):
            st.markdown(f"**{e} {lbl}:** {txt}")


def _render_compact_table(df: pd.DataFrame):
    if df.empty: st.info("Tidak ada data."); return
    display = df.copy()
    cm = dict(LEAD_PARTNERSHIP_DISPLAY_NAMES)
    avail = [c for c in cm if c in display.columns]
    preferred = ["name","nama_pic","nama_tempat","jenis_partnership","kota_lokasi","status_lead","priority"]
    ordered = [c for c in preferred if c in avail]
    remaining = [c for c in avail if c not in ordered]
    st.dataframe(display[ordered + remaining].rename(columns=cm), use_container_width=True, hide_index=True, height=350)
