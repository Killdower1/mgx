"""app.py — backup-dower: Streamlit dashboard for Difotoin outlet analysis.
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
from components.ui_helpers import render_mobile_cards, s_caption, _clean_master_values, kemitraan_table_show

from services.auth import check_login
from pages.login import show_login_page, show_logout_button
from pages.upload import show_upload_data
from pages.admin import show_admin_panel
from pages.crud_outlet import show_outlet_crud, show_outlet_crud_v2
from pages.dashboard import show_main_dashboard
from pages.trend import show_trend_analysis, show_trend_analysis_v2, render_ai_insights
from pages.ai_decision import show_ai_decision_center
from pages.conversion import show_conversion_analysis
from pages.ranking import show_outlet_ranking
from pages.comparison import show_period_comparison
from pages.kemitraan import show_kemitraan_page

# ================= SCROLL GUARDS =================

def install_scroll_guard():
    components.html("""<script>
(function(){try{const K="difotoin_scroll_y";const w=window.parent;const d=w.document;let t=false;
function y(){return w.scrollY||d.documentElement.scrollTop||d.body.scrollTop||0}
function s(){try{const v=y();if(v>=0)w.sessionStorage.setItem(K,String(v))}catch(e){}}
function r(){try{const v=parseInt(w.sessionStorage.getItem(K)||"0",10);if(!Number.isFinite(v)||v<80)return;const n=y();if(n<Math.max(40,v*0.25))w.scrollTo(0,v)}catch(e){}}
w.addEventListener("scroll",function(){if(t)return;t=true;w.setTimeout(function(){s();t=false},120)},{passive:true})
w.addEventListener("beforeunload",s);[50,150,350,800,1400].forEach(function(d){w.setTimeout(r,d)})}catch(e){}})();</script>""", height=0, width=0)

def install_table_unfreeze_guard():
    components.html("""<script>
(function(){try{const w=window.parent;const d=w.document;
const sel=['.stDataFrame [style*="position: sticky"]','.stDataFrame [style*="position:sticky"]','.stDataFrame [style*="position: fixed"]','.stDataFrame [style*="position:fixed"]','[data-testid="stDataFrame"] [style*="position: sticky"]','[data-testid="stDataFrame"] [style*="position:sticky"]','[data-testid="stDataFrame"] [style*="position: fixed"]','[data-testid="stDataFrame"] [style*="position:fixed"]','[role="grid"] [style*="position: sticky"]','[role="grid"] [style*="position:sticky"]','[role="grid"] [style*="position: fixed"]','[role="grid"] [style*="position:fixed"]'];
function u(){sel.forEach(function(s){d.querySelectorAll(s).forEach(function(el){el.style.setProperty('position','static','important');el.style.setProperty('left','auto','important');el.style.setProperty('right','auto','important');el.style.setProperty('transform','none','important');el.style.setProperty('z-index','auto','important')})})}
u();[100,350,800,1500,2500].forEach(function(d){w.setTimeout(u,d)});new MutationObserver(function(){w.requestAnimationFrame(u)}).observe(d.body,{childList:true,subtree:true,attributes:true,attributeFilter:['style','class']})}catch(e){}})();</script>""", height=0, width=0)

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

# ================= PAGE CONFIG =================

st.set_page_config(page_title="backup-dower", page_icon="📸", layout="wide", initial_sidebar_state="expanded")

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
:root{--df-bg:#111827;--df-panel:#182235;--df-panel-soft:#202c43;--df-border:#334155;--df-text:#f8fafc;--df-muted:#cbd5e1;--df-blue:#38bdf8;--df-green:#22c55e;--df-yellow:#f59e0b;--df-red:#ef4444}
.main-header{font-size:2.2rem;font-weight:800;color:var(--df-text)!important;text-align:center;margin-bottom:1.5rem}
.status-keeper{color:#10b981!important;font-weight:bold}
.status-optimasi{color:#f59e0b!important;font-weight:bold}
.status-relocate{color:#ef4444!important;font-weight:bold}
.insight-box{background:var(--df-panel);border-left:4px solid var(--df-blue);padding:1rem;margin:1rem 0;border-radius:.5rem;color:var(--df-text)!important}
.filter-buttons .stCheckbox>label{background:var(--df-panel-soft)!important;padding:.55rem .8rem;border-radius:.55rem;border:1px solid var(--df-border);color:var(--df-text)!important;font-weight:700}
[data-testid="stMetric"]{background:linear-gradient(180deg,#1f2937 0%,#151e2f 100%);border:1px solid var(--df-border);border-radius:.75rem;padding:.9rem 1rem;box-shadow:0 8px 24px rgba(0,0,0,.18)}
.stMetric [data-testid="metric-value"]{font-size:1.35rem!important;color:var(--df-text)!important;font-weight:800!important}
.stApp{color:var(--df-text)!important;background:var(--df-bg)!important}
[data-testid="stAppViewContainer"]>.main{background:radial-gradient(circle at top left,rgba(56,189,248,.10),transparent 26rem),var(--df-bg)}
.stSidebar{background:#0b1220!important;border-right:1px solid #1f2937}
.stSidebar *{color:var(--df-text)!important}
.stSelectbox label,.stTextInput label{color:var(--df-text)!important;font-weight:700!important}
[data-baseweb="select"]>div,.stTextInput input{background:#0f172a!important;border-color:var(--df-border)!important;color:var(--df-text)!important;border-radius:.65rem!important}
.stDataFrame{width:100%!important;max-width:100%!important;max-height:560px!important;overflow:auto!important;border-radius:.75rem!important}
.stDataFrame canvas{max-width:none!important}
.stTabs [data-baseweb="tab-list"]{gap:.35rem;overflow-x:auto}
.stTabs [data-baseweb="tab-list"] button{color:var(--df-text)!important;background:#172033;border:1px solid #26344e;border-radius:999px;padding:.25rem .8rem}
.stButton button,.stDownloadButton button{color:#06121f!important;background:var(--df-blue)!important;border:none!important;border-radius:.65rem!important;font-weight:800!important;min-height:2.7rem}
.performer-card{padding:.8rem;margin:.45rem 0;border-radius:.65rem;background:var(--df-panel);border:1px solid var(--df-border)}
.mobile-card-list{display:none}
.mobile-data-card{background:linear-gradient(180deg,#1f2937,#151e2f);border:1px solid var(--df-border);border-radius:.85rem;padding:.9rem;margin:.75rem 0;box-shadow:0 10px 24px rgba(0,0,0,.18)}
[data-testid="stStatusWidget"],[data-testid="stConnectionStatus"]{display:none!important;visibility:hidden!important}
@media(max-width:760px){
[data-testid="block-container"]{padding:1rem .85rem 5rem!important}
.main-header{font-size:1.45rem!important;text-align:left;margin:.2rem 0 1rem}
h1{font-size:1.45rem!important}h2{font-size:1.2rem!important}h3{font-size:1.02rem!important}
[data-testid="stMetric"]{padding:.78rem .85rem}
.stMetric [data-testid="metric-value"]{font-size:1.08rem!important}
.stButton button,.stDownloadButton button{width:100%;min-height:2.9rem}
.stPlotlyChart{background:var(--df-panel);border:1px solid var(--df-border);border-radius:.8rem;padding:.35rem}
.mobile-table-muted{display:block!important;width:100%!important;max-width:100%!important;max-height:68vh;overflow:auto!important;-webkit-overflow-scrolling:touch;overscroll-behavior:contain}
.mobile-table-muted [data-testid="stDataFrameResizable"]{min-width:760px!important}
.mobile-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.stAlert{border-radius:.75rem}iframe{max-width:100%!important}
}</style>""", unsafe_allow_html=True)

install_scroll_guard()
install_table_unfreeze_guard()

# ================= DATA LOADING =================

@cache_data
def load_app_data():
    return DataProcessor().load_data()

# ================= SIDEBAR HELPERS =================

def create_sidebar_period_selector(df):
    if df.empty or "periode" not in df.columns: return None, None
    periods = sorted([str(p) for p in df["periode"].dropna().unique()])
    st.sidebar.markdown("### 📅 Periode Selection")
    current = st.sidebar.selectbox("Current Period", periods, index=len(periods)-1 if periods else 0, key="period_current_sidebar")
    compare = st.sidebar.selectbox("Compare with", ["None"] + [p for p in periods if p != current], key="period_compare_sidebar")
    return current, (None if compare == "None" else compare)

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

    st.sidebar.title("📸 backup-dower")
    st.sidebar.markdown("---")
    show_logout_button()

    page = st.sidebar.selectbox("Pilih Halaman", [
        "🏠 Dashboard Utama", "📊 Analisis Trend", "AI Decision", "🔄 Analisis Konversi",
        "🏆 Ranking Outlet", "🤝 Kemitraan", "📅 Perbandingan Periode",
        "🗃️ CRUD Data Outlet", "⚙️ Admin Panel", "📤 Upload Data",
    ])

    current_period, compare_period = None, None
    if page in ("🏠 Dashboard Utama", "📅 Perbandingan Periode"):
        current_period, compare_period = create_sidebar_period_selector(df)
        st.sidebar.markdown("---")

    st.sidebar.markdown("### 🔍 Filter Data")
    if not df.empty:
        areas = ["Semua"] + safe_unique_str(df, "area")
        selected_area = st.sidebar.selectbox("Area", areas)
        kategoris = ["Semua"] + safe_unique_str(df, "kategori_tempat")
        selected_kategori = st.sidebar.selectbox("Kategori Tempat", kategoris)
        tipes = ["Semua"] + safe_unique_str(df, "tipe_tempat")
        selected_tipe = st.sidebar.selectbox("Tipe Tempat", tipes)
        df_for_filter = df.copy(deep=True)
        filtered_full_df = processor.filter_data(df_for_filter.copy(deep=True), selected_area, selected_kategori, selected_tipe, None) if hasattr(processor, "filter_data") else df_for_filter.copy(deep=True)
        filtered_df = processor.filter_data(df_for_filter, selected_area, selected_kategori, selected_tipe, current_period) if hasattr(processor, "filter_data") else df_for_filter
    else:
        filtered_df = filtered_full_df = df

    page_router = {
        "🏠 Dashboard Utama": lambda: show_main_dashboard(filtered_df, config, processor, viz, current_period, compare_period, full_df=filtered_full_df),
        "📊 Analisis Trend": lambda: show_trend_analysis_v2(filtered_df, config, processor, viz),
        "AI Decision": lambda: show_ai_decision_center(filtered_full_df, config),
        "🔄 Analisis Konversi": lambda: show_conversion_analysis(filtered_df, config, processor, viz),
        "🏆 Ranking Outlet": lambda: show_outlet_ranking(filtered_df, config, processor),
        "🤝 Kemitraan": lambda: show_kemitraan_page(filtered_full_df, config, processor),
        "📅 Perbandingan Periode": lambda: show_period_comparison(filtered_df, config, processor, viz, current_period, compare_period),
        "🗃️ CRUD Data Outlet": lambda: show_outlet_crud_v2(df, config, processor),
        "⚙️ Admin Panel": lambda: show_admin_panel(config),
        "📤 Upload Data": lambda: show_upload_data(config),
    }
    if page in page_router:
        page_router[page]()

if __name__ == "__main__":
    main()
