# app.py — Difotoin Dashboard (stabil: login persist, Styler.map, width='stretch')
import io
import os
import re
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from data_processor import DataProcessor
from visualizations import Visualizations
from utils import *
from config import Config

# ================= CONFIG =================
st.set_page_config(
    page_title="Difotoin Sales Dashboard",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Agar koneksi frontend gak gampang idle, dan warning deprecation lebih bersih
st.session_state.setdefault("_boot_ok", True)

INDONESIA_AREAS = [
    "Jakarta Pusat","Jakarta Utara","Jakarta Barat","Jakarta Selatan","Jakarta Timur","Jakarta",
    "Surabaya","Bandung","Medan","Bekasi","Tangerang","Depok","Semarang","Palembang","Makassar",
    "Batam","Bogor","Pekanbaru","Bandar Lampung","Malang","Padang","Denpasar","Samarinda","Tasikmalaya",
    "Balikpapan","Pontianak","Jambi","Cimahi","Sukabumi","Bengkulu","Mataram","Yogyakarta","Solo",
    "Purwokerto","Magelang","Tegal","Pekalongan","Kudus","Jepara","Demak","Kendal","Temanggung",
    "Wonosobo","Purworejo","Kebumen","Banjarnegara","Cilacap","Banyumas","Brebes","Pemalang",
    "Batang","Blora","Rembang","Pati","Grobogan","Sragen","Karanganyar","Wonogiri","Sukoharjo",
    "Klaten","Boyolali","Sleman","Bantul","Kulon Progo","Gunungkidul","Madiun","Ngawi","Bojonegoro",
    "Tuban","Lamongan","Gresik","Bangkalan","Sampang","Pamekasan","Sumenep","Kediri","Blitar",
    "Tulungagung","Trenggalek","Nganjuk","Jombang","Mojokerto","Pasuruan","Probolinggo","Situbondo",
    "Bondowoso","Banyuwangi","Jember","Lumajang","Malang","Batu","Bali","Denpasar","Badung",
    "Gianyar","Klungkung","Bangli","Karangasem","Buleleng","Jembrana","Tabanan"
]

DEFAULT_USERS = {
    "difotoin": {"password": "difotoin123", "role": "admin"},
    "analyst": {"password": "analyst", "role": "viewer"},
}

KATEGORI_TEMPAT = [
    "Mall", "Ruko", "Pasar", "Pinggir Jalan", "Kampus", "Perkantoran", "Rumah Sakit",
    "Tempat Wisata", "Stasiun/Terminal", "Bandara", "Hotel", "Apartemen", "Sekolah",
]

# ================== UTIL THEME ==================
def tag_badge(text, color="blue"):
    return f"""
    <span style="
        display:inline-block;padding:2px 8px;border-radius:12px;
        background:{color};color:white;font-size:11px;font-weight:600">{text}</span>
    """

def section_header(title, subtitle=""):
    sub = f"<div style='color:#888;font-size:12px'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"""
        <div style="margin:8px 0 4px 0">
            <div style="font-weight:700;font-size:18px">{title}</div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True
    )

# ================== SESSION & AUTH ==================
def init_session():
    st.session_state.setdefault("is_authed", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("role", "viewer")
    st.session_state.setdefault("outlet_map", pd.DataFrame())
    st.session_state.setdefault("config", {})

def login_form():
    with st.form("login_form", clear_on_submit=False):
        u = st.text_input("Username", value="", key="login_u")
        p = st.text_input("Password", value="", type="password", key="login_p")
        ok = st.form_submit_button("Login")
    if ok:
        ud = DEFAULT_USERS.get(u)
        if ud and p == ud["password"]:
            st.session_state["is_authed"] = True
            st.session_state["user"] = u
            st.session_state["role"] = ud["role"]
            st.success("✅ Login sukses")
            st.rerun()
        else:
            st.error("❌ Username/password salah")

def logout():
    st.session_state["is_authed"] = False
    st.session_state["user"] = None
    st.session_state["role"] = "viewer"

# ================== DATA LOADING ==================
@st.cache_data
def load_app_data():
    # (Why) Cache supaya cepat; heavy ops dipindah ke DataProcessor
    cfg = Config.load()
    dp = DataProcessor(cfg)
    raw_df = dp.load_all()
    processed = dp.process_all(raw_df)
    return cfg, dp, raw_df, processed

# ================== WIDGET HELPERS ==================
def metric_card(label, value, delta=None, help_text=None):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.metric(label, value, delta=delta, help=help_text)
    with c2:
        st.markdown("&nbsp;")

def money(n):
    try:
        return f"Rp {int(n):,}".replace(",", ".")
    except Exception:
        return "-"

def pct(x):
    try:
        return f"{x:.1%}"
    except Exception:
        return "-"

# ================== FILTER STATE ==================
def sidebar_filters(processed_df):
    st.sidebar.header("🔎 Filters")
    date_min = processed_df["tanggal"].min()
    date_max = processed_df["tanggal"].max()

    date_range = st.sidebar.date_input(
        "Periode",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
    )

    area = st.sidebar.multiselect("Area", options=sorted(processed_df["area"].dropna().unique().tolist()))
    outlet = st.sidebar.multiselect("Outlet", options=sorted(processed_df["outlet"].dropna().unique().tolist()))
    kategori = st.sidebar.multiselect("Kategori Tempat", options=KATEGORI_TEMPAT)

    return {
        "date_range": date_range,
        "areas": area,
        "outlets": outlet,
        "kategori": kategori,
    }

def apply_filters(df, f):
    m = (df["tanggal"].between(pd.to_datetime(f["date_range"][0]), pd.to_datetime(f["date_range"][1])))
    if f["areas"]:
        m &= df["area"].isin(f["areas"])
    if f["outlets"]:
        m &= df["outlet"].isin(f["outlets"])
    if f["kategori"]:
        m &= df["kategori_tempat"].isin(f["kategori"])
    return df[m].copy()

# ================== PAGES ==================
def show_overview(processed_df):
    st.title("📊 Difotoin — Sales Overview")

    # KPI ringkas
    total_omset = processed_df["omset"].sum()
    total_transaksi = processed_df["transaksi"].sum()
    avg_basket = (processed_df["omset"].sum() / max(processed_df["transaksi"].sum(), 1))

    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Total Omset", money(total_omset))
    with c2: metric_card("Total Transaksi", f"{int(total_transaksi):,}".replace(",", "."))
    with c3: metric_card("Avg Basket Size", money(avg_basket))

    # Omset harian
    section_header("Omset Harian", "Performa harian")
    daily = processed_df.groupby("tanggal", as_index=False)["omset"].sum()
    fig = px.line(daily, x="tanggal", y="omset", markers=True)
    st.plotly_chart(fig, use_container_width=True)

    # Top area
    section_header("Top Area", "Kontribusi per area")
    top_area = processed_df.groupby("area", as_index=False)["omset"].sum().sort_values("omset", ascending=False).head(15)
    fig2 = px.bar(top_area, x="area", y="omset")
    st.plotly_chart(fig2, use_container_width=True)

def show_transactions(processed_df):
    st.title("🧾 Transactions")
    show_cols = ["tanggal", "area", "outlet", "kategori_tempat", "omset", "transaksi", "produk"]
    if not set(show_cols).issubset(processed_df.columns):
        st.warning("Kolom tidak lengkap untuk tampilan transaksi.")
        return

    styled = processed_df[show_cols].sort_values("tanggal", ascending=False).head(200).style
    try:
        styled = styled.format({"omset": lambda x: money(x)})
    except Exception:
        pass
    st.dataframe(styled, width="stretch", hide_index=True)

def show_outlets(processed_df):
    st.title("🏪 Outlets")

    outlet_mapping = processed_df.groupby(["area", "outlet"], as_index=False).agg(
        transaksi=("transaksi", "sum"),
        omset=("omset", "sum"),
    )
    st.dataframe(outlet_mapping, width="stretch") if not outlet_mapping.empty else st.info("No outlet data available")

    s1, s2 = st.columns([2, 1])
    with s1:
        st.subheader("📍 Area Coverage")
        vc = processed_df["area"].value_counts()
        st.dataframe(vc.to_frame("count"), width="stretch")

    with s2:
        st.subheader("➕ Add New Outlet")
        with st.form("add_outlet_form"):
            area = st.selectbox("Area", options=sorted(processed_df["area"].dropna().unique().tolist()))
            outlet = st.text_input("Outlet Name")
            kategori = st.selectbox("Kategori Tempat", options=KATEGORI_TEMPAT)
            ok = st.form_submit_button("Add")
        if ok:
            st.success(f"✅ Outlet '{outlet}' ditambahkan (dummy).")

def show_upload():
    st.title("📥 Upload Data Excel")
    up = st.file_uploader("Upload Excel (multi-sheet)", type=["xlsx"])
    if not up:
        st.info("Pilih file Excel.")
        return

    # Contoh baca beberapa sheet
    selected_sheets = st.multiselect("Pilih sheets", options=[s.name for s in pd.ExcelFile(up).book.worksheets])
    if st.button("Process"):
        with st.spinner("Memproses data..."):
            try:
                full_df_raw = read_selected_sheets(up, selected_sheets)
                if full_df_raw.empty:
                    st.warning("File kosong / tidak valid.")
                    return
                cleaned = clean_raw(full_df_raw)
                tmp_for_dedup = cleaned.copy()
                deduped, dd_audit = deduplicate_rows(tmp_for_dedup)

                st.subheader("Preview")
                st.dataframe(cleaned.head(50), width="stretch")
                st.subheader("Hasil Dedup")
                st.dataframe(deduped.head(50), width="stretch")

                st.subheader("🧾 Audit — Perbandingan Total (Excel vs Agregasi)")
                total_raw = float(dd_audit['sum_after'])
                st.write(f"Total after: {money(total_raw)}")
            except Exception as e:
                st.error(f"Error: {e}")

# ================= ADMIN PANEL ===============
def show_admin_panel(config):
    import os
    from datetime import datetime as _dt
    st.title("⚙️ Admin Panel")

    st.subheader("🎯 Threshold Configuration")
    keeper_now = config.get_threshold("keeper_minimum")
    optim_now  = config.get_threshold("optimasi_minimum")

    c1, c2 = st.columns(2)
    with c1:
        new_keeper = st.number_input("Keeper Minimum (IDR)", min_value=0, value=int(keeper_now) if isinstance(keeper_now, (int, float)) else 0, step=1_000_000, format="%d")
    with c2:
        new_optim = st.number_input("Optimasi Minimum (IDR)", min_value=0, value=int(optim_now) if isinstance(optim_now, (int, float)) else 0, step=1_000_000, format="%d")

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("💾 Save Thresholds", type="primary"):
            try:
                config.set_threshold("keeper_minimum", new_keeper)
                config.set_threshold("optimasi_minimum", new_optim)
                ok = config.save_config()
                if ok:
                    try: load_app_data.clear()
                    except Exception: pass
                    st.success("✅ Thresholds updated & config saved.")
                    st.rerun()
                else:
                    st.error("❌ Failed to save thresholds.")
            except Exception as e:
                st.error(f"❌ Error saving thresholds: {e}")

    with colB:
        if st.button("🧹 Clear Cached Data", key="btn_clear_cache"):
            cleared_any = False
            # Clear per-function cache first
            try:
                load_app_data.clear()
                cleared_any = True
            except Exception:
                pass
            # Clear global caches (Streamlit >= 1.18)
            try:
                st.cache_data.clear()
                cleared_any = True
            except Exception:
                pass
            try:
                st.cache_resource.clear()
                cleared_any = True
            except Exception:
                pass
            if cleared_any:
                st.success("✅ Cache cleared.")
            else:
                st.warning("ℹ️ Tidak ada cache untuk dibersihkan atau versi Streamlit tidak mendukung.")

    st.subheader("📋 Current Configuration")
    try: st.json(config.config)
    except Exception: st.info("ℹ️ Tidak bisa menampilkan JSON config.")

    st.subheader("ℹ️ System Information")
    st.write(f"**Last Updated:** {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        st.write(f"**Keeper Threshold:** {config.format_currency(config.get_threshold('keeper_minimum'))}")
        st.write(f"**Optimasi Threshold:** {config.format_currency(config.get_threshold('optimasi_minimum'))}")
    except Exception:
        pass

    data_path = os.getcwd()
    st.caption(f"Working dir: `{data_path}`")

# ================== NAVIGATION ==================
def main():
    init_session()

    # Auth gate
    if not st.session_state["is_authed"]:
        st.title("🔐 Difotoin Dashboard — Login")
        login_form()
        return

    try:
        config, dp, raw_df, processed_df = load_app_data()
    except Exception as e:
        st.error(f"Gagal load data: {e}")
        return

    st.session_state["config"] = config

    pages = {
        "Overview": lambda: show_overview(processed_df),
        "Transactions": lambda: show_transactions(processed_df),
        "Outlets": lambda: show_outlets(processed_df),
        "Upload": show_upload,
        "Admin": lambda: show_admin_panel(config),
    }

    with st.sidebar:
        st.image("https://raw.githubusercontent.com/streamlit/brand/main/logos/mark/streamlit-mark-primary.png", width=64)
        st.markdown(f"**Hello, {st.session_state['user']}!**")
        choice = st.radio("Navigate", list(pages.keys()), index=0)
        if st.button("Logout"):
            logout()
            st.rerun()

    # Render page
    pages.get(choice, lambda: st.write("Page not found"))()

# ================ HELPER (mock) =================
def read_selected_sheets(file, sheets):
    # (Why) Mock reader contoh; sesuaikan dengan kebutuhan real
    try:
        dfs = []
        xls = pd.ExcelFile(file)
        for s in sheets or xls.sheet_names:
            dfs.append(pd.read_excel(file, sheet_name=s))
        out = pd.concat(dfs, ignore_index=True)
        if "tanggal" in out.columns:
            out["tanggal"] = pd.to_datetime(out["tanggal"], errors="coerce")
        return out
    except Exception:
        return pd.DataFrame()

def clean_raw(df):
    df = df.copy()
    possible_cols = ["area","outlet","kategori_tempat","omset","transaksi","tanggal","produk"]
    for c in possible_cols:
        if c not in df.columns:
            df[c] = np.nan
    df["omset"] = pd.to_numeric(df["omset"], errors="coerce").fillna(0.0)
    df["transaksi"] = pd.to_numeric(df["transaksi"], errors="coerce").fillna(0.0)
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")
    return df

def deduplicate_rows(df):
    # (Why) Audit sederhana untuk cek total berubah/tidak
    before = df["omset"].sum()
    deduped = df.drop_duplicates()
    after = deduped["omset"].sum()
    audit = {"sum_before": before, "sum_after": after}
    return deduped, audit

# ================== ENTRY ==================
if __name__ == "__main__":
    main()
