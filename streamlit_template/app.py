"""app.py — Difotoin Dashboard: Streamlit dashboard for Difotoin outlet analysis.
Now slimmed to main router module (Task 15 refactor)."""

import json
import os
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Union

import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components

from data_processor import DataProcessor, normalize_outlet_name
from visualizations import Visualizations
from config import Config, DATA_CSV_PATH, OUTLET_MAPPING_PATH, MASTER_DATA_PATH
from components.compat import cache_data, rerun, text_col, number_col, table_height, df_show, DEFAULT_TABLE_MAX_HEIGHT, HAS_COLUMN_CONFIG
from components.ui_helpers import s_caption, _clean_master_values, kemitraan_table_show

from services.auth import check_login
from page_modules.login import show_login_page, show_logout_button
from page_modules.upload import show_upload_data
from page_modules.admin import show_admin_panel
from page_modules.crud_outlet import show_outlet_crud, show_outlet_crud_v2
from page_modules.dashboard import show_main_dashboard
from page_modules.trend import show_trend_analysis, show_trend_analysis_v2, render_ai_insights
from page_modules.ai_decision import show_ai_decision_center
from page_modules.conversion import show_conversion_analysis
from page_modules.ranking import show_outlet_ranking
from page_modules.comparison import show_period_comparison
from page_modules.kemitraan import show_kemitraan_page
from page_modules.lead_partnership import show_lead_partnership_page
from page_modules.lead_kemitraan import show_lead_kemitraan_page
from page_modules.lead_permanen import show_lead_permanen_page

# ================= SCROLL GUARDS =================


def cache_clear(func):
    try: func.clear(); return
    except Exception: pass
    for name in ("cache_data", "experimental_memo", "legacy_caching", "caching"):
        mod = getattr(st, name, None)
        if mod:
            clear = getattr(mod, "clear" if name in ("cache_data", "experimental_memo") else "clear_cache", None)
            if callable(clear):
                try: clear(); return
                except Exception: pass


# ================= UPLOAD HELPERS =================

def excel_engine_from_filename(filename: str) -> str:
    return "openpyxl" if str(filename).lower().endswith(".xlsx") else "xlrd"

def suggest_default_sheets(sheet_names):
    priority = ["data", "sheet1", "transaksi", "report", "database"]
    scored = sorted(sheet_names, key=lambda s: next((i for i, p in enumerate(priority) if p in s.lower()), 999))
    return scored[:1] if scored else sheet_names[:1]

def read_selected_sheets(file_bytes, selected_sheets, engine):
    import io
    dfs = []
    for sheet in selected_sheets:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, engine=engine, dtype=str)
        if not df.empty:
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def apply_column_mapping_auto(df):
    mapping = {}
    lower_cols = {c: c for c in df.columns}
    for keyword, target in [("outlet", "outlet_name"), ("nama outlet", "outlet_name"), ("nama_outlet", "outlet_name"), ("harga", "harga"), ("nominal", "harga"), ("total", "harga"), ("amount", "harga"), ("tanggal", "tanggal"), ("date", "tanggal"), ("tgl", "tanggal"), ("area", "area"), ("cabang", "area"), ("branch", "area"), ("type", "type"), ("jenis", "type"), ("kategori", "type")]:
        for col in df.columns:
            if keyword in col.lower():
                mapping[target] = col
                break
    return {v: k for k, v in mapping.items()}

def to_numeric_clean(series):
    return pd.to_numeric(series.astype(str).str.replace(r"[^0-9,\-]", "", regex=True).str.replace(",", ".", regex=False), errors="coerce").fillna(0)

def deduplicate_rows(df, subset=None):
    rows_before = len(df)
    if subset is None:
        subset = [c for c in ["outlet_name", "harga", "tanggal"] if c in df.columns]
    deduped = df.drop_duplicates(subset=subset, keep="first").copy() if subset else df.copy()
    rows_after = len(deduped)
    return deduped, {"rows_before": rows_before, "rows_after": rows_after, "dup_removed": rows_before - rows_after, "subset": subset, "sum_after": float(deduped.get("harga", pd.Series(dtype=float)).fillna(0).astype(float).sum())}

def aggregate_monthly(df, config, fallback_period=None):
    from datetime import datetime
    result = df.copy()
    if "periode" not in result.columns:
        if "tanggal" in result.columns:
            dt = pd.to_datetime(result["tanggal"], errors="coerce")
            result["periode"] = dt.dt.strftime("%Y-%m")
        else:
            result["periode"] = fallback_period or datetime.now().strftime("%Y-%m")
    result["total_revenue"] = to_numeric_clean(result.get("harga", 0))
    result["foto_qty"] = 0
    result["unlock_qty"] = 0
    result["print_qty"] = 0
    if "type" in result.columns:
        t = result["type"].astype(str).str.strip().str.lower()
        result["foto_qty"] = (t.str.contains("foto", na=False)).astype(int)
        result["unlock_qty"] = (t.str.contains("unlock", na=False)).astype(int)
        result["print_qty"] = (t.str.contains("print|cetak", na=False, regex=True)).astype(int)
    result["conversion_rate"] = np.where(result["foto_qty"] > 0, (result["unlock_qty"] / result["foto_qty"] * 100), 0.0)
    if "harga" in result.columns:
        result.drop(columns=["harga"], inplace=True, errors="ignore")
    return result, {}

def save_overwrite_periods(df, csv_path):
    df_save = df.copy()
    periods = df_save["periode"].dropna().unique().tolist() if "periode" in df_save.columns else []
    try:
        existing = pd.read_csv(csv_path, dtype=str)
    except (FileNotFoundError, Exception):
        existing = pd.DataFrame()
    before_total = float(existing.get("total_revenue", pd.Series(dtype=float)).fillna(0).astype(float).sum()) if not existing.empty else 0.0
    if not existing.empty and periods:
        existing = existing[~existing["periode"].astype(str).str.strip().isin(periods)].copy()
    merged = pd.concat([existing, df_save], ignore_index=True)
    merged.to_csv(csv_path, index=False)
    after_total = float(merged.get("total_revenue", pd.Series(dtype=float)).fillna(0).astype(float).sum())
    remaining = sorted(merged["periode"].dropna().unique().tolist()) if "periode" in merged.columns else []
    return merged, {"periods_overwritten": periods, "before_total": before_total, "after_total": after_total, "remaining_periods": remaining}

# ================= PAGE CONFIG =================

st.set_page_config(page_title="Difotoin Dashboard", page_icon="📸", layout="wide", initial_sidebar_state="collapsed")

# ================= MASTER DATA =================

INDONESIA_AREAS = ["Jakarta Pusat","Jakarta Utara","Jakarta Barat","Jakarta Selatan","Jakarta Timur","Jakarta","Surabaya","Bandung","Medan","Bekasi","Tangerang","Depok","Semarang","Palembang","Makassar","Batam","Bogor","Pekanbaru","Bandar Lampung","Malang","Padang","Denpasar","Samarinda","Tasikmalaya","Balikpapan","Pontianak","Jambi","Cimahi","Sukabumi","Bengkulu","Mataram","Yogyakarta","Solo","Purwokerto","Magelang","Tegal","Pekalongan","Kudus","Jepara","Demak","Kendal","Temanggung","Wonosobo","Purworejo","Kebumen","Banjarnegara","Cilacap","Banyumas","Brebes","Pemalang","Batang","Blora","Rembang","Pati","Grobogan","Sragen","Karanganyar","Wonogiri","Sukoharjo","Klaten","Boyolali","Sleman","Bantul","Kulon Progo","Gunungkidul","Madiun","Ngawi","Bojonegoro","Tuban","Lamongan","Gresik","Bangkalan","Sampang","Pamekasan","Sumenep","Kediri","Blitar","Tulungagung","Trenggalek","Nganjuk","Jombang","Mojokerto","Pasuruan","Probolinggo","Situbondo","Bondowoso","Banyuwangi","Jember","Lumajang","Malang","Batu","Bali","Denpasar","Badung","Gianyar","Klungkung","Bangli","Karangasem","Buleleng","Jembrana","Tabanan"]
KATEGORI_TEMPAT = ["Mall","Wisata","Restoran","Hotel","Komunitas","Sekolah","Universitas","Rumah Sakit","Perkantoran","Apartemen","Cafe","Gym","Salon","Spa","Bioskop","Taman","Museum","Galeri","Event Space","Co-working Space","Transportasi","Lainnya"]
SUB_KATEGORI_TEMPAT = ["Food Court","Shopping Center","Department Store","Supermarket","Boutique","Electronics Store","Bookstore","Pantai","Gunung","Danau","Taman Nasional","Taman/Wisata Alam","Candi","Kebun Binatang","Waterpark","Fine Dining","Fast Food","Street Food","Bakery","Coffee Shop","Bar","Lounge","Budget Hotel","Luxury Hotel","Resort","Resort/Hotel","Homestay","Guest House","Hostel","Community Space","Creative Space","Airport","Tidak Terkategorisasi","Lainnya"]
TIPE_TEMPAT = ["Indoor", "Outdoor", "Semi-Outdoor"]
DEFAULT_MASTER_DATA = {"areas": INDONESIA_AREAS.copy(), "kategori_tempat": KATEGORI_TEMPAT.copy(), "sub_kategori_tempat": SUB_KATEGORI_TEMPAT.copy(), "tipe_tempat": TIPE_TEMPAT.copy()}

def load_master_data() -> Dict[str, List[str]]:
    try:
        with open(MASTER_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict): return {k: v.copy() for k, v in DEFAULT_MASTER_DATA.items()}
    except (FileNotFoundError, Exception): return {k: v.copy() for k, v in DEFAULT_MASTER_DATA.items()}
    result = {}
    for key, defaults in DEFAULT_MASTER_DATA.items():
        values = data.get(key)
        result[key] = _clean_master_values(values if isinstance(values, list) else defaults)
        if not result[key]: result[key] = defaults.copy()
    return result

def save_master_data(data: Dict[str, List[str]]) -> None:
    MASTER_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"areas": _clean_master_values(data.get("areas", [])), "kategori_tempat": _clean_master_values(data.get("kategori_tempat", [])), "sub_kategori_tempat": _clean_master_values(data.get("sub_kategori_tempat", [])), "tipe_tempat": _clean_master_values(data.get("tipe_tempat", []))}
    with open(MASTER_DATA_PATH, "w", encoding="utf-8") as f: json.dump(payload, f, indent=2)

def apply_master_data():
    global INDONESIA_AREAS, KATEGORI_TEMPAT, SUB_KATEGORI_TEMPAT, TIPE_TEMPAT
    data = load_master_data()
    INDONESIA_AREAS = data["areas"]
    KATEGORI_TEMPAT = data["kategori_tempat"]
    SUB_KATEGORI_TEMPAT = data["sub_kategori_tempat"]
    TIPE_TEMPAT = data.get("tipe_tempat", ["Indoor", "Outdoor", "Semi-Outdoor"])

apply_master_data()

# ================= CSS STYLES =================

st.markdown("""<style>
:root{--bg:#09090b;--card:#18181b;--card-soft:#1f1f23;--border:#27272a;--text:#fafafa;--muted:#a1a1aa;--accent:#fafafa;--accent-bg:#27272a;--blue:#3b82f6;--green:#22c55e;--yellow:#f59e0b;--red:#ef4446;--radius:.5rem}
.main-header{font-size:2rem;font-weight:600;color:var(--text)!important;text-align:center;letter-spacing:-.025em;margin-bottom:1.5rem}
.status-keeper{color:var(--green)!important;font-weight:600}
.status-optimasi{color:var(--yellow)!important;font-weight:600}
.status-relocate{color:var(--red)!important;font-weight:600}
.status-inactive{color:var(--muted)!important}
.insight-box{background:var(--card);border-left:3px solid var(--blue);padding:1rem 1.1rem;margin:1rem 0;border-radius:var(--radius);color:var(--text)!important;font-size:.9rem}
.filter-buttons .stCheckbox>label{background:var(--card-soft)!important;padding:.5rem .75rem;border-radius:var(--radius);border:1px solid var(--border);color:var(--text)!important;font-weight:500;font-size:.82rem}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:.85rem 1rem}
.stMetric [data-testid="metric-value"]{font-size:1.35rem!important;color:var(--text)!important;font-weight:600!important}
.stMetric [data-testid="metric-label"]{color:var(--muted)!important;font-size:.8rem!important;font-weight:400!important}
.stApp{color:var(--text)!important;background:var(--bg)!important}
[data-testid="stAppViewContainer"]>.main{background:var(--bg)}
.stSidebar{background:#0c0c0f!important;border-right:1px solid var(--border)}
.stSidebar *{color:var(--text)!important}
.stSidebar .stSelectbox label,.stSidebar .stTextInput label{color:var(--muted)!important;font-weight:500!important;font-size:.82rem!important}
.stSelectbox label,.stTextInput label{color:var(--muted)!important;font-weight:500!important;font-size:.82rem!important}
[data-baseweb="select"]>div,.stTextInput input{background:var(--card)!important;border-color:var(--border)!important;color:var(--text)!important;border-radius:var(--radius)!important;font-size:.85rem!important}
[data-baseweb="select"]>div:hover{border-color:#3f3f46!important}
.stDataFrame{width:100%!important;max-width:100%!important;border-radius:var(--radius)!important}
.stDataFrame canvas{max-width:none!important}
.stTabs [data-baseweb="tab-list"]{gap:.25rem;overflow-x:auto}
.stTabs [data-baseweb="tab-list"] button{color:var(--muted)!important;background:transparent!important;border:none!important;border-radius:var(--radius)!important;padding:.35rem .75rem!important;font-size:.85rem!important;font-weight:500!important}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"]{color:var(--text)!important;background:var(--card-soft)!important}
.stButton button,.stDownloadButton button{color:var(--text)!important;background:var(--accent-bg)!important;border:1px solid var(--border)!important;border-radius:var(--radius)!important;font-weight:500!important;min-height:2.3rem;font-size:.85rem!important;transition:all .15s}
.stButton button:hover,.stDownloadButton button:hover{background:#3f3f46!important;border-color:#52525b!important}
.stButton button:active,.stDownloadButton button:active{transform:translateY(1px)}
.performer-card{padding:.75rem 1rem;margin:.4rem 0;border-radius:var(--radius);background:var(--card);border:1px solid var(--border);font-size:.88rem}
.pagination-wrap{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:.15rem .4rem;margin:.3rem 0}
.pagination-wrap .stButton button{background:transparent!important;color:var(--text)!important;border:1px solid var(--border)!important;min-height:1.9rem!important;font-size:.8rem!important;border-radius:calc(var(--radius) - 2px)!important;font-weight:500!important;padding:0 .45rem!important}
.pagination-wrap .stButton button:disabled{opacity:.25!important}
.pagination-wrap .stButton button:not(:disabled):hover{background:var(--accent-bg)!important;border-color:var(--border)!important}
[data-testid="stStatusWidget"],[data-testid="stConnectionStatus"]{display:none!important;visibility:hidden!important}
.stPlotlyChart{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:.5rem}
.stAlert{border-radius:var(--radius);border:1px solid var(--border)}iframe{max-width:100%!important}
.stDataFrame tbody tr{transition:background-color .12s}
.stDataFrame tbody tr:hover{background-color:rgba(255,255,255,.03)!important}
.stDataFrame thead tr th{background:var(--card)!important;border-bottom:1px solid var(--border)!important;color:var(--muted)!important;font-weight:500!important;font-size:.78rem!important;text-transform:uppercase;letter-spacing:.05em;padding:.6rem .8rem!important}
.stDataFrame tbody tr td{padding:.5rem .8rem!important;font-size:.85rem!important;border-bottom:1px solid rgba(39,39,42,.5)!important}
.stDataFrame tbody tr:last-child td{border-bottom:none!important}

@media(max-width:760px){
[data-testid="block-container"]{padding:1rem .75rem 5rem!important}
.main-header{font-size:1.4rem!important;text-align:left;margin:.2rem 0 1rem}
h1{font-size:1.35rem!important}h2{font-size:1.15rem!important}h3{font-size:1rem!important}
[data-testid="stMetric"]{padding:.7rem .8rem}
.stMetric [data-testid="metric-value"]{font-size:1.05rem!important}
.stButton button,.stDownloadButton button{width:100%;min-height:2.5rem}
.stPlotlyChart{padding:.3rem}
.mobile-table-muted{display:block!important;width:100%!important;max-width:100%!important;max-height:75vh;overflow:auto!important;-webkit-overflow-scrolling:touch}

}



/* Modern sidebar styling */
.stSidebar{background:#0c0c0f!important;border-right:1px solid var(--border);padding:1rem .5rem}
.stSidebar .stSelectbox label{font-size:.8rem!important;font-weight:500!important;color:var(--muted)!important}
.stSidebar .stSelectbox>div{background:var(--card)!important;border-color:var(--border)!important;border-radius:var(--radius)!important}
.stSidebar .stButton button{width:100%}
.stSidebar hr{margin:.75rem 0;border-color:var(--border)}
.stSidebar .sidebar-title{font-size:1.1rem;font-weight:600;margin-bottom:.5rem;display:block}

</style>""", unsafe_allow_html=True)


# ================= DATA LOADING =================

@cache_data
def load_app_data():
    return DataProcessor().load_data()

# ================= SIDEBAR HELPERS =================

def safe_unique_str(df: pd.DataFrame, col: str) -> List[str]:
    if col not in df.columns: return []
    return sorted(df[col].dropna().astype(str).unique().tolist())

# ================= MAIN ROUTER =================

def main():
    if not check_login():
        show_login_page(); return

    config = Config()
    processor = DataProcessor()
    viz = Visualizations(config)

    df = load_app_data()
    if isinstance(df, pd.DataFrame):
        df = df.copy(deep=True)
    if not df.empty and "area" in df.columns:
        df["area"] = df["area"].astype(str).replace({"nan": ""})

    # ===== SIDEBAR =====
    st.sidebar.markdown('<span class="sidebar-title">📸 Difotoin</span>', unsafe_allow_html=True)
    st.sidebar.markdown("---")
    show_logout_button()
    st.sidebar.markdown("### 📋 Halaman")

    page = st.sidebar.selectbox("", [
        "\U0001f3e0 Dashboard Utama", "\U0001f4ca Analisis Trend", "AI Decision",
        "\U0001f504 Analisis Konversi", "\U0001f3c6 Ranking Outlet", "\U0001f91d Kemitraan",
        "\U0001f4cb Lead Partnership", "\U0001f91d Lead Kemitraan",
        "\U0001f4cb Lead Permanen",
        "\U0001f4c5 Perbandingan Periode", "\U0001f5c3\ufe0f CRUD Data Outlet",
        "\u2699\ufe0f Admin Panel", "\U0001f4e4 Upload Data",
    ], label_visibility="collapsed")

    # Period selector
    current_period, compare_period = None, None
    if page in ("🏠 Dashboard Utama", "📅 Perbandingan Periode"):
        if not df.empty and "periode" in df.columns:
            periods = sorted([str(p) for p in df["periode"].dropna().unique()])
            if periods:
                st.sidebar.markdown("### 📅 Periode")
                current_period = st.sidebar.selectbox("", periods, index=len(periods)-1, key="period_sidebar", label_visibility="collapsed")
                cmp = st.sidebar.selectbox("", ["-"] + [p for p in periods if p != current_period], key="compare_sidebar", label_visibility="collapsed")
                compare_period = None if cmp == "-" else cmp

    # Filters
    st.sidebar.markdown("### 🔍 Filter")
    if not df.empty:
        areas = ["Semua"] + safe_unique_str(df, "area")
        selected_area = st.sidebar.selectbox("Area", areas, key="filter_area_sidebar")
        kategoris = ["Semua"] + safe_unique_str(df, "kategori_tempat")
        selected_kategori = st.sidebar.selectbox("Kategori", kategoris, key="filter_kategori_sidebar")
        tipes = ["Semua"] + safe_unique_str(df, "tipe_tempat")
        selected_tipe = st.sidebar.selectbox("Tipe", tipes, key="filter_tipe_sidebar")
    else:
        selected_area = selected_kategori = selected_tipe = "Semua"

    # Apply filters
    if not df.empty:
        df_for_filter = df.copy(deep=True)
        filtered_full_df = processor.filter_data(df_for_filter.copy(deep=True), selected_area, selected_kategori, selected_tipe, None) if hasattr(processor, "filter_data") else df_for_filter.copy(deep=True)
        filtered_df = processor.filter_data(df_for_filter, selected_area, selected_kategori, selected_tipe, current_period) if hasattr(processor, "filter_data") else df_for_filter
    else:
        filtered_df = filtered_full_df = df

    # ===== TOP BAR (branding) =====
    st.markdown('<div style="display:flex;align-items:center;gap:.75rem;padding:.5rem 0">'
                '<span style="font-size:1.5rem">📸</span>'
                '<span style="font-size:1.25rem;font-weight:600;color:var(--text)">difotoin.id</span>'
                '<span style="color:var(--muted);font-size:.85rem;margin-left:.25rem">— Dashboard</span>'
                '</div>', unsafe_allow_html=True)
    st.markdown("---")

    # ===== PAGE ROUTER =====
    if page == "🏠 Dashboard Utama":
        show_main_dashboard(filtered_df, config, processor, viz, current_period, compare_period, full_df=filtered_full_df)
    elif page == "📊 Analisis Trend":
        show_trend_analysis_v2(filtered_df, config, processor, viz)
    elif page == "AI Decision":
        show_ai_decision_center(filtered_full_df, config)
    elif page == "🔄 Analisis Konversi":
        show_conversion_analysis(filtered_df, config, processor, viz)
    elif page == "🏆 Ranking Outlet":
        show_outlet_ranking(filtered_df, config, processor)
    elif page == "🤝 Kemitraan":
        show_kemitraan_page(filtered_full_df, config, processor)
    elif page == "\U0001f4cb Lead Partnership":
        show_lead_partnership_page()
    elif page == "\U0001f91d Lead Kemitraan":
        show_lead_kemitraan_page()
    elif page == "\U0001f4cb Lead Permanen":
        show_lead_permanen_page()
    elif page == "📅 Perbandingan Periode":
        show_period_comparison(filtered_df, config, processor, viz, current_period, compare_period)
    elif page == "🗃️ CRUD Data Outlet":
        show_outlet_crud_v2(df, config, processor)
    elif page == "⚙️ Admin Panel":
        show_admin_panel(config)
    elif page == "📤 Upload Data":
        show_upload_data(config)

if __name__ == "__main__":
    main()
