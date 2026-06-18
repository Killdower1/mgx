# path: app.py — backup-dower (Trend 12 bulan + kolom Rata-rata) — Server-Compat (Streamlit/Python lama) — Mutation-safe
# NOTE: Patched to force openpyxl for .xlsx and xlrd only for .xls

import io
import json
import os
import re
import base64
import hashlib
import hmac
import secrets
import time
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Tuple, Dict, Optional

from data_processor import DataProcessor, normalize_outlet_name
from visualizations import Visualizations
from utils import *
from config import Config, DATA_CSV_PATH, OUTLET_MAPPING_PATH, USERS_PATH, AUTH_SESSIONS_PATH, DELETED_OUTLETS_PATH, MASTER_DATA_PATH
from components.compat import cache_data, rerun, text_col, number_col, table_height, df_show, DEFAULT_TABLE_MAX_HEIGHT, HAS_COLUMN_CONFIG, HAS_CAPTION
from components.ui_helpers import render_mobile_cards, s_caption, bool_series, _clean_master_values, kemitraan_table_show

from services.auth import check_login, load_users, save_users, load_deleted_outlets, save_deleted_outlets
from pages.login import show_login_page, show_logout_button
from pages.upload import show_upload_data
from pages.admin import show_admin_panel

# ============== COMPAT LAYER (Streamlit lama / Python 3.6) ==============
# NOTE: moved to components/compat.py — kept re-exports for backward compat during transition

def install_scroll_guard():
    components.html(
        """
        <script>
        (function () {
          try {
            const KEY = "difotoin_scroll_y";
            const w = window.parent;
            const d = w.document;
            let ticking = false;

            function currentY() {
              return w.scrollY || d.documentElement.scrollTop || d.body.scrollTop || 0;
            }

            function save() {
              try {
                const y = currentY();
                if (y >= 0) w.sessionStorage.setItem(KEY, String(y));
              } catch (e) {}
            }

            function restore() {
              try {
                const saved = parseInt(w.sessionStorage.getItem(KEY) || "0", 10);
                if (!Number.isFinite(saved) || saved < 80) return;
                const now = currentY();
                if (now < Math.max(40, saved * 0.25)) {
                  w.scrollTo(0, saved);
                }
              } catch (e) {}
            }

            w.addEventListener("scroll", function () {
              if (ticking) return;
              ticking = true;
              w.setTimeout(function () {
                save();
                ticking = false;
              }, 120);
            }, { passive: true });

            w.addEventListener("beforeunload", save);
            [50, 150, 350, 800, 1400].forEach(function (delay) {
              w.setTimeout(restore, delay);
            });
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
        width=0,
    )

def install_table_unfreeze_guard():
    components.html(
        """
        <script>
        (function () {
          try {
            const w = window.parent;
            const d = w.document;
            const selectors = [
              '.stDataFrame [style*="position: sticky"]',
              '.stDataFrame [style*="position:sticky"]',
              '.stDataFrame [style*="position: fixed"]',
              '.stDataFrame [style*="position:fixed"]',
              '[data-testid="stDataFrame"] [style*="position: sticky"]',
              '[data-testid="stDataFrame"] [style*="position:sticky"]',
              '[data-testid="stDataFrame"] [style*="position: fixed"]',
              '[data-testid="stDataFrame"] [style*="position:fixed"]',
              '[role="grid"] [style*="position: sticky"]',
              '[role="grid"] [style*="position:sticky"]',
              '[role="grid"] [style*="position: fixed"]',
              '[role="grid"] [style*="position:fixed"]'
            ];

            function unfreezeTables() {
              selectors.forEach(function (selector) {
                d.querySelectorAll(selector).forEach(function (el) {
                  el.style.setProperty('position', 'static', 'important');
                  el.style.setProperty('left', 'auto', 'important');
                  el.style.setProperty('right', 'auto', 'important');
                  el.style.setProperty('transform', 'none', 'important');
                  el.style.setProperty('z-index', 'auto', 'important');
                });
              });
            }

            unfreezeTables();
            [100, 350, 800, 1500, 2500].forEach(function (delay) {
              w.setTimeout(unfreezeTables, delay);
            });
            new MutationObserver(function () {
              w.requestAnimationFrame(unfreezeTables);
            }).observe(d.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'] });
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
        width=0,
    )

def cache_clear(func):
    try:
        func.clear(); return
    except Exception:
        pass
    for name in ("cache_data", "experimental_memo", "legacy_caching", "caching"):
        mod = getattr(st, name, None)
        if mod:
            clear = getattr(mod, "clear" if name in ("cache_data", "experimental_memo") else "clear_cache", None)
            if callable(clear):
                try:
                    clear(); return
                except Exception:
                    pass

# ================= CONFIG =================
st.set_page_config(
    page_title="backup-dower",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
KATEGORI_TEMPAT = [
    "Mall","Wisata","Restoran","Hotel","Komunitas","Sekolah","Universitas","Rumah Sakit",
    "Perkantoran","Apartemen","Cafe","Gym","Salon","Spa","Bioskop","Taman","Museum",
    "Galeri","Event Space","Co-working Space","Transportasi","Lainnya"
]
SUB_KATEGORI_TEMPAT = [
    "Food Court","Shopping Center","Department Store","Supermarket","Boutique","Electronics Store","Bookstore",
    "Pantai","Gunung","Danau","Taman Nasional","Taman/Wisata Alam","Candi","Kebun Binatang","Waterpark",
    "Fine Dining","Fast Food","Street Food","Bakery","Coffee Shop","Bar","Lounge",
    "Budget Hotel","Luxury Hotel","Resort","Resort/Hotel","Homestay","Guest House","Hostel",
    "Community Space","Creative Space","Airport","Tidak Terkategorisasi","Lainnya"
]

TIPE_TEMPAT = ["Indoor", "Outdoor", "Semi-Outdoor"]

DEFAULT_MASTER_DATA = {
    "areas": INDONESIA_AREAS.copy(),
    "kategori_tempat": KATEGORI_TEMPAT.copy(),
    "sub_kategori_tempat": SUB_KATEGORI_TEMPAT.copy(),
    "tipe_tempat": TIPE_TEMPAT.copy(),
}

def load_master_data() -> Dict[str, List[str]]:
    try:
        with open(MASTER_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {k: v.copy() for k, v in DEFAULT_MASTER_DATA.items()}
    except FileNotFoundError:
        return {k: v.copy() for k, v in DEFAULT_MASTER_DATA.items()}
    except Exception:
        return {k: v.copy() for k, v in DEFAULT_MASTER_DATA.items()}

    result = {}
    for key, defaults in DEFAULT_MASTER_DATA.items():
        values = data.get(key)
        result[key] = _clean_master_values(values if isinstance(values, list) else defaults)
        if not result[key]:
            result[key] = defaults.copy()
    return result

def save_master_data(data: Dict[str, List[str]]) -> None:
    MASTER_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "areas": _clean_master_values(data.get("areas", [])),
        "kategori_tempat": _clean_master_values(data.get("kategori_tempat", [])),
        "sub_kategori_tempat": _clean_master_values(data.get("sub_kategori_tempat", [])),
        "tipe_tempat": _clean_master_values(data.get("tipe_tempat", [])),
    }
    with open(MASTER_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

def apply_master_data() -> None:
    global INDONESIA_AREAS, KATEGORI_TEMPAT, SUB_KATEGORI_TEMPAT, TIPE_TEMPAT
    data = load_master_data()
    INDONESIA_AREAS = data["areas"]
    KATEGORI_TEMPAT = data["kategori_tempat"]
    SUB_KATEGORI_TEMPAT = data["sub_kategori_tempat"]
    TIPE_TEMPAT = data.get("tipe_tempat", ["Indoor", "Outdoor", "Semi-Outdoor"])

apply_master_data()

def render_master_data_editor(title: str, key: str, values: List[str]) -> None:
    st.markdown(f"**{title}**")
    source = pd.DataFrame({
        "delete": False,
        "value": _clean_master_values(values),
    })
    editor_config = None
    if HAS_COLUMN_CONFIG:
        try:
            editor_config = {
                "delete": st.column_config.CheckboxColumn("Delete", width="small"),
                "value": st.column_config.TextColumn(title, width="medium"),
            }
        except Exception:
            editor_config = None

    with st.form(f"master_data_{key}_form"):
        new_value = st.text_input("Tambah baru", key=f"master_data_{key}_new")
        if hasattr(st, "data_editor"):
            edited = st.data_editor(
                source,
                use_container_width=True,
                hide_index=True,
                height=table_height(len(source), 220, DEFAULT_TABLE_MAX_HEIGHT),
                num_rows="fixed",
                column_config=editor_config,
                key=f"master_data_{key}_editor",
            )
        else:
            edited = source.copy()
            df_show(source.drop(columns=["delete"]), use_container_width=True, hide_index=True)
            st.warning("Versi Streamlit ini belum mendukung edit langsung di tabel.")
        submitted = st.form_submit_button(f"Save {title}", type="primary")

    if submitted:
        edited_df = pd.DataFrame(edited)
        if "delete" not in edited_df.columns:
            edited_df["delete"] = False
        if "value" not in edited_df.columns:
            edited_df["value"] = ""
        keep_mask = ~bool_series(edited_df["delete"])
        final_values = edited_df.loc[keep_mask, "value"].dropna().astype(str).str.strip().tolist()
        new_value = str(new_value or "").strip()
        if new_value:
            final_values.append(new_value)
        final_values = _clean_master_values(final_values)
        if not final_values:
            st.error(f"{title} minimal harus punya 1 data.")
            return

        master = load_master_data()
        master[key] = final_values
        save_master_data(master)
        apply_master_data()
        try:
            cache_clear(load_app_data)
        except Exception:
            pass
        st.success(f"{title} berhasil disimpan.")
        rerun()


# ================= STYLES =================
st.markdown("""
<style>
    :root{
        --df-bg:#111827;
        --df-panel:#182235;
        --df-panel-soft:#202c43;
        --df-border:#334155;
        --df-text:#f8fafc;
        --df-muted:#cbd5e1;
        --df-blue:#38bdf8;
        --df-green:#22c55e;
        --df-yellow:#f59e0b;
        --df-red:#ef4444;
    }
    .main-header{font-size:2.2rem;font-weight:800;color:var(--df-text)!important;text-align:center;margin-bottom:1.5rem;letter-spacing:0;}
    .status-keeper{color:#10b981!important;font-weight:bold;}
    .status-optimasi{color:#f59e0b!important;font-weight:bold;}
    .status-relocate{color:#ef4444!important;font-weight:bold;}
    .insight-box{background:var(--df-panel);border-left:4px solid var(--df-blue);padding:1rem;margin:1rem 0;border-radius:.5rem;color:var(--df-text)!important;}
    .outlet-table{padding:0;margin-bottom:2rem;}
    .filter-buttons{margin-bottom:1rem;}
    .filter-buttons .stCheckbox>label{background:var(--df-panel-soft)!important;padding:.55rem .8rem;border-radius:.55rem;border:1px solid var(--df-border);color:var(--df-text)!important;font-weight:700;}
    .filter-buttons .stCheckbox>label:hover{background:#26344e!important;}
    [data-testid="stMetric"]{background:linear-gradient(180deg,#1f2937 0%,#151e2f 100%);border:1px solid var(--df-border);border-radius:.75rem;padding:.9rem 1rem;box-shadow:0 8px 24px rgba(0,0,0,.18);}
    .stMetric>label{font-size:.78rem!important;color:var(--df-muted)!important;}
    .stMetric [data-testid="metric-value"]{font-size:1.35rem!important;color:var(--df-text)!important;font-weight:800!important;}
    .stMetric [data-testid="stMetricDelta"]{font-size:.82rem!important;}
    .stApp{color:var(--df-text)!important;background:var(--df-bg)!important;}
    [data-testid="stAppViewContainer"]>.main{background:radial-gradient(circle at top left,rgba(56,189,248,.10),transparent 26rem),var(--df-bg);}
    .stSidebar{background:#0b1220!important;border-right:1px solid #1f2937;}
    .stSidebar *{color:var(--df-text)!important;}
    .stMarkdown,.stMarkdown *,.stText,.stText *,h1,h2,h3,h4,h5,h6,p,span,div,label{color:var(--df-text)!important;}
    .stSelectbox label,.stTextInput label,.stNumberInput label,.stTextArea label,.stMultiSelect label,.stRadio label{color:var(--df-text)!important;font-weight:700!important;}
    [data-baseweb="select"]>div, .stTextInput input, .stNumberInput input, .stTextArea textarea{
        background:#0f172a!important;border-color:var(--df-border)!important;color:var(--df-text)!important;border-radius:.65rem!important;
    }
    .stDataFrame,.stDataFrame *{color:#1f2937!important;}
    .stDataFrame{
        width:100%!important;
        max-width:100%!important;
        max-height:560px!important;
        overflow:auto!important;
        border-radius:.75rem!important;
    }
    .stDataFrame [data-testid="stDataFrameResizable"],
    .stDataFrame [data-testid="stDataFrame"],
    .stDataFrame div[role="grid"],
    .stDataFrame .glideDataEditor{
        max-height:560px!important;
        overflow:auto!important;
    }
    .stDataFrame canvas{
        max-width:none!important;
    }
    .stDataFrame [role="gridcell"],
    .stDataFrame [role="columnheader"],
    .stDataFrame [role="rowheader"],
    .stDataFrame [style*="position: sticky"],
    .stDataFrame [style*="position:sticky"],
    .stDataFrame [style*="position: fixed"],
    .stDataFrame [style*="position:fixed"],
    [data-testid="stDataFrame"] [role="gridcell"],
    [data-testid="stDataFrame"] [role="columnheader"],
    [data-testid="stDataFrame"] [role="rowheader"],
    [data-testid="stDataFrame"] [style*="position: sticky"],
    [data-testid="stDataFrame"] [style*="position:sticky"],
    [data-testid="stDataFrame"] [style*="position: fixed"],
    [data-testid="stDataFrame"] [style*="position:fixed"],
    [role="grid"] [style*="position: sticky"],
    [role="grid"] [style*="position:sticky"],
    [role="grid"] [style*="position: fixed"],
    [role="grid"] [style*="position:fixed"]{
        position:static!important;
        left:auto!important;
        right:auto!important;
        transform:none!important;
        z-index:auto!important;
    }
    .stDataFrame [data-testid="stDataFrameResizable"]{
        overflow:auto!important;
    }
    .stTabs [data-baseweb="tab-list"]{gap:.35rem;overflow-x:auto;}
    .stTabs [data-baseweb="tab-list"] button{color:var(--df-text)!important;background:#172033;border:1px solid #26344e;border-radius:999px;padding:.25rem .8rem;}
    .stButton button, .stDownloadButton button, .stFormSubmitButton button{color:#06121f!important;background:var(--df-blue)!important;border:none!important;border-radius:.65rem!important;font-weight:800!important;min-height:2.7rem;}
    .performer-card{padding:.8rem;margin:.45rem 0;border-radius:.65rem;background:var(--df-panel);border:1px solid var(--df-border);}
    .mobile-card-list{display:none;}
    .mobile-data-card{background:linear-gradient(180deg,#1f2937,#151e2f);border:1px solid var(--df-border);border-radius:.85rem;padding:.9rem;margin:.75rem 0;box-shadow:0 10px 24px rgba(0,0,0,.18);}
    .mobile-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:.75rem;margin-bottom:.75rem;}
    .mobile-card-head strong{font-size:.96rem;line-height:1.25;}
    .mobile-status{display:inline-flex;align-items:center;border-radius:999px;padding:.22rem .55rem;font-size:.72rem;font-weight:800;white-space:nowrap;border:1px solid transparent;}
    .mobile-status.keeper{color:#dcfce7!important;background:rgba(34,197,94,.16);border-color:rgba(34,197,94,.35);}
    .mobile-status.optimasi{color:#fef3c7!important;background:rgba(245,158,11,.16);border-color:rgba(245,158,11,.35);}
    .mobile-status.relocate{color:#fee2e2!important;background:rgba(239,68,68,.16);border-color:rgba(239,68,68,.35);}
    .mobile-status.inactive,.mobile-status.neutral{color:#e2e8f0!important;background:rgba(148,163,184,.16);border-color:rgba(148,163,184,.28);}
    .mobile-card-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.6rem;}
    .mobile-card-grid div{background:#0f172a;border:1px solid #26344e;border-radius:.65rem;padding:.62rem;min-width:0;}
    .mobile-card-grid span{display:block;color:var(--df-muted)!important;font-size:.72rem;line-height:1.1;margin-bottom:.25rem;}
    .mobile-card-grid b{display:block;font-size:.88rem;line-height:1.2;word-break:break-word;}
    .mobile-card-note{color:var(--df-muted)!important;font-size:.78rem;margin:.75rem 0 0;}
    [data-testid="stStatusWidget"], [data-testid="stConnectionStatus"], .stStatusWidget{display:none!important;visibility:hidden!important;}
    @media (max-width: 760px){
        [data-testid="block-container"]{padding:1rem .85rem 5rem!important;}
        .main-header{font-size:1.45rem!important;line-height:1.18;text-align:left;margin:.2rem 0 1rem;}
        h1{font-size:1.45rem!important;line-height:1.18!important;}
        h2{font-size:1.2rem!important;}
        h3{font-size:1.02rem!important;}
        .stSidebar [data-testid="stSidebarContent"]{padding:1rem .85rem;}
        [data-testid="stMetric"]{padding:.78rem .85rem;border-radius:.75rem;}
        .stMetric [data-testid="metric-value"]{font-size:1.08rem!important;line-height:1.2!important;}
        .stButton button, .stDownloadButton button, .stFormSubmitButton button{width:100%;min-height:2.9rem;}
        .stTabs [data-baseweb="tab-list"]{display:flex;flex-wrap:nowrap;overflow-x:auto;padding-bottom:.45rem;}
        .stTabs [data-baseweb="tab-list"] button{min-width:max-content;font-size:.83rem;}
        .filter-buttons .stCheckbox>label{width:100%;justify-content:center;padding:.6rem .5rem;font-size:.82rem;}
        .stPlotlyChart{background:var(--df-panel);border:1px solid var(--df-border);border-radius:.8rem;padding:.35rem;overflow:hidden;}
        .stDataFrame{border-radius:.75rem;}
        .mobile-card-list{display:none!important;}
        .mobile-table-muted{
            display:block!important;
            width:100%!important;
            max-width:100%!important;
            max-height:68vh;
            overflow:auto!important;
            -webkit-overflow-scrolling:touch;
            overscroll-behavior:contain;
        }
        .mobile-table-muted [data-testid="stDataFrame"]{
            width:100%!important;
            max-width:100%!important;
            overflow:auto!important;
        }
        .mobile-table-muted [data-testid="stDataFrameResizable"]{
            min-width:760px!important;
        }
        .stDataFrame [role="gridcell"],
        .stDataFrame [role="columnheader"],
        .stDataFrame [role="rowheader"],
        .stDataFrame [style*="position: sticky"],
        .stDataFrame [style*="position:sticky"],
        .stDataFrame [style*="position: fixed"],
        .stDataFrame [style*="position:fixed"],
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"],
        [data-testid="stDataFrame"] [role="rowheader"],
        [data-testid="stDataFrame"] [style*="position: sticky"],
        [data-testid="stDataFrame"] [style*="position:sticky"],
        [data-testid="stDataFrame"] [style*="position: fixed"],
        [data-testid="stDataFrame"] [style*="position:fixed"],
        [role="grid"] [style*="position: sticky"],
        [role="grid"] [style*="position:sticky"],
        [role="grid"] [style*="position: fixed"],
        [role="grid"] [style*="position:fixed"]{
            position:static!important;
            left:auto!important;
            right:auto!important;
            transform:none!important;
            z-index:auto!important;
        }
        .mobile-table-muted [data-testid="stDataFrameResizable"]{
            min-width:920px!important;
        }
        .mobile-card-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
        .mobile-card-grid b{font-size:.82rem;}
        .stAlert{border-radius:.75rem;}
        iframe{max-width:100%!important;}
    }
    @media (max-width: 380px){
        .mobile-card-grid{grid-template-columns:1fr;}
    }
</style>
""", unsafe_allow_html=True)

install_scroll_guard()
install_table_unfreeze_guard()


# ================= LOAD =================
@cache_data
def load_app_data():
    processor = DataProcessor()
    return processor.load_data()

# ================= PERIOD (SIDEBAR) =================
def create_sidebar_period_selector(df):
    if df.empty or "periode" not in df.columns:
        return None, None
    periods = sorted([str(p) for p in df["periode"].dropna().unique()])
    st.sidebar.markdown("### 📅 Periode Selection")
    current = st.sidebar.selectbox("Current Period", periods, index=len(periods)-1 if periods else 0, key="period_current_sidebar")
    compare_opts = ["None"] + [p for p in periods if p != current]
    compare = st.sidebar.selectbox("Compare with", compare_opts, key="period_compare_sidebar")
    return current, (None if compare == "None" else compare)

# ================= HELPERS =================
def format_number_with_dots(num):
    try:
        return f"{int(round(float(num))):,}".replace(",", ".")
    except Exception:
        return str(num)

def format_decimal_with_comma(num, digits=1, suffix=""):
    try:
        return f"{float(num):.{int(digits)}f}".replace(".", ",") + suffix
    except Exception:
        return str(num)

def _norm_name(s: str) -> str:
    return str(s).strip().lower()

def safe_unique_str(df: pd.DataFrame, col: str) -> List[str]:
    if col not in df.columns:
        return []
    vals = df[col].dropna().astype(str).unique().tolist()
    return sorted(vals)

EXCEL_TO_APP_COLMAP = {
    "outlet":"outlet_name","nama outlet":"outlet_name","outlet name":"outlet_name","toko":"outlet_name",
    "harga":"harga","amount":"harga","price":"harga","nominal":"harga","omset":"harga",
    "tanggal":"tanggal","date":"tanggal","waktu":"tanggal","created at":"tanggal",
    "area":"area","kota":"area","city":"area",
    "type":"type","tipe":"type","jenis":"type","event":"type",
}

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [" ".join(str(c).strip().split()) for c in df.columns]
    return df

def apply_column_mapping_auto(df: pd.DataFrame) -> dict:
    lower_map = {k.lower(): v for k, v in EXCEL_TO_APP_COLMAP.items()}
    used = {}
    for col in df.columns:
        k = col.lower()
        if k in lower_map and lower_map[k] not in used:
            used[lower_map[k]] = col
    return used

def to_numeric_clean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0)

    s = series.astype(str).str.strip()
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    s = s.str.replace(r"\.0+$", "", regex=True)
    s = s.str.replace(r"[^\d\-,\.]", "", regex=True)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

SHARING_OUTLETS_DIR = Path(DATA_CSV_PATH).parent / "sharing_outlets"

def _share_num(value):
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return np.nan
        text = str(value).strip()
        if text == "":
            return np.nan
        n = float(re.sub(r"[^\d\.\-]", "", text))
        if n > 1:
            n = n / 100.0
        return max(0.0, min(1.0, n))
    except Exception:
        return np.nan

def _money_num(value):
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return np.nan
        text = str(value).strip()
        if text == "":
            return np.nan
        return float(re.sub(r"[^\d\.\-]", "", text) or 0)
    except Exception:
        return np.nan

def _pick_col(row, names):
    for name in names:
        if name in row and str(row.get(name, "")).strip() != "":
            return row.get(name)
    return ""

def infer_period_from_filename(filename: str) -> str:
    m = re.search(r"(\d{4})[-_](\d{2})(?:[-_]\d{2})?", str(filename or ""))
    return "{}-{}".format(m.group(1), m.group(2)) if m else ""

def list_sharing_periods() -> List[str]:
    try:
        if not SHARING_OUTLETS_DIR.exists():
            return []
        return sorted([p.stem for p in SHARING_OUTLETS_DIR.glob("*.json") if re.match(r"^\d{4}-\d{2}$", p.stem)])
    except Exception:
        return []

def load_sharing_outlets(period: Optional[str] = None) -> Tuple[Optional[str], pd.DataFrame]:
    periods = list_sharing_periods()
    if not periods:
        return None, pd.DataFrame()
    resolved = str(period or "").strip()
    if not re.match(r"^\d{4}-\d{2}$", resolved) or resolved not in periods:
        resolved = periods[-1]
    try:
        with open(SHARING_OUTLETS_DIR / f"{resolved}.json", "r", encoding="utf-8") as f:
            rows = json.load(f)
        df = pd.DataFrame(rows if isinstance(rows, list) else [])
        return resolved, df
    except Exception:
        return None, pd.DataFrame()

def load_sharing_outlets_exact(period: Optional[str]) -> Tuple[Optional[str], pd.DataFrame]:
    resolved = str(period or "").strip()
    if not re.match(r"^\d{4}-\d{2}$", resolved):
        return None, pd.DataFrame()
    path = SHARING_OUTLETS_DIR / f"{resolved}.json"
    if not path.exists():
        return None, pd.DataFrame()
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return resolved, pd.DataFrame(rows if isinstance(rows, list) else [])
    except Exception:
        return None, pd.DataFrame()

def save_sharing_outlets(period: str, df: pd.DataFrame) -> None:
    SHARING_OUTLETS_DIR.mkdir(parents=True, exist_ok=True)
    clean_df = normalize_sharing_master_df(df)
    if "harga_mesin" in clean_df.columns:
        clean_df = clean_df.drop(columns=["harga_mesin"])
    payload = clean_df.where(pd.notna(clean_df), None).to_dict(orient="records")
    with open(SHARING_OUTLETS_DIR / f"{period}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

def parse_sharing_outlet_excel(uploaded_file) -> pd.DataFrame:
    engine = excel_engine_from_filename(getattr(uploaded_file, "name", "xlsx"))
    raw = pd.read_excel(uploaded_file, engine=engine).fillna("")
    rows = []
    for _, row in raw.iterrows():
        name = str(_pick_col(row, ["NAME", "Name", "name", "Nama", "Outlet", "outlet_name"])).strip()
        if not name:
            continue
        partner_share = _share_num(_pick_col(row, ["PARTNER_SHARE", "Partner Share", "partner_share", "partnerShare"]))
        broker_share = _share_num(_pick_col(row, ["BROKER_SHARE", "Broker Share", "broker_share", "brokerShare"]))
        explicit_share = _share_num(_pick_col(row, ["SHARING_BAGI_HASIL", "Sharing Bagi Hasil", "sharing_bagi_hasil", "DIFOTOIN_SHARE", "Difotoin Share"]))
        sharing_bagi_hasil = explicit_share
        if pd.isna(sharing_bagi_hasil) and (pd.notna(partner_share) or pd.notna(broker_share)):
            sharing_bagi_hasil = max(0.0, min(1.0, 1.0 - (0.0 if pd.isna(partner_share) else partner_share) - (0.0 if pd.isna(broker_share) else broker_share)))
        harga_beli_kemitraan = _money_num(_pick_col(row, [
            "HARGA_BELI_KEMITRAAN", "Harga Beli Kemitraan", "harga_beli_kemitraan", "Harga Beli", "harga_beli",
            "INITIAL_COST", "Harga Mesin", "harga_mesin", "MACHINE_PRICE", "Machine Price", "machine_price",
        ]))
        rows.append({
            "outlet_id": str(_pick_col(row, ["ID", "Id", "id"])).strip(),
            "outlet_name": name,
            "area": str(_pick_col(row, ["BRANCH", "Branch", "branch", "Area", "area"])).strip(),
            "outlet_status_master": str(_pick_col(row, ["STATUS", "Status", "status"])).strip(),
            "outlet_type_master": str(_pick_col(row, ["TYPE", "Type", "type"])).strip(),
            "investor_name": str(_pick_col(row, ["OWNER", "Owner", "owner", "INVESTOR_NAME", "Investor Name", "investor_name", "NAMA_INVESTOR", "Nama Investor", "NAMA_KEMITRAAN", "Nama Kemitraan", "Nama Orang/Mitra", "Partner", "Partner Name"])).strip(),
            "partner_share": partner_share,
            "broker_share": broker_share,
            "sharing_bagi_hasil": sharing_bagi_hasil,
            "harga_beli_kemitraan": harga_beli_kemitraan,
            "monthly_rent": _money_num(_pick_col(row, ["MONTHLY_RENT", "Monthly Rent", "monthly_rent", "monthlyRent"])),
            "minimum_payment": _money_num(_pick_col(row, ["MINIMUM_PAYMENT", "Minimum Payment", "minimum_payment", "minimumPayment"])),
            "created_at": str(_pick_col(row, ["CREATED_AT", "Created At", "created_at", "createdAt"])).strip(),
        })
    return pd.DataFrame(rows)

def apply_sharing_to_mapping(mapping_df: pd.DataFrame, period: Optional[str] = None) -> pd.DataFrame:
    resolved, sharing = load_sharing_outlets(period)
    if mapping_df.empty or sharing.empty or "outlet_name" not in mapping_df.columns:
        return mapping_df
    out = mapping_df.copy()
    sharing = sharing.copy()
    if "harga_beli_kemitraan" not in sharing.columns:
        sharing["harga_beli_kemitraan"] = np.nan
    if "harga_mesin" in sharing.columns:
        sharing["harga_beli_kemitraan"] = sharing["harga_beli_kemitraan"].combine_first(sharing["harga_mesin"])
    sharing["_key"] = sharing["outlet_name"].map(normalize_outlet_name)
    sharing = sharing.drop_duplicates("_key", keep="last")
    out["_key"] = out["outlet_name"].map(normalize_outlet_name)
    merge_cols = [
        "outlet_id", "area", "outlet_status_master", "partner_share", "broker_share",
        "sharing_bagi_hasil", "monthly_rent", "minimum_payment", "investor_name",
        "harga_beli_kemitraan", "harga_mesin",
    ]
    sharing_owned_cols = {
        "partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent",
        "minimum_payment", "investor_name", "harga_beli_kemitraan", "harga_mesin",
    }
    merged = out.merge(sharing[["_key"] + [c for c in merge_cols if c in sharing.columns]], on="_key", how="left", suffixes=("", "_sharing"))
    for col in merge_cols:
        s_col = f"{col}_sharing"
        if s_col in merged.columns:
            vals = merged[s_col].replace("", np.nan)
            if col not in merged.columns:
                merged[col] = np.nan
            if col in sharing_owned_cols:
                merged[col] = vals
            else:
                merged[col] = vals.combine_first(merged[col])
            merged = merged.drop(columns=[s_col])
    for col in ["partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent", "minimum_payment", "harga_beli_kemitraan", "harga_mesin"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")
    if "harga_beli_kemitraan" in merged.columns:
        merged["harga_mesin"] = merged["harga_beli_kemitraan"]
    has_terms = (
        merged.get("partner_share", pd.Series(index=merged.index)).notna()
        | merged.get("broker_share", pd.Series(index=merged.index)).notna()
        | merged.get("minimum_payment", pd.Series(index=merged.index)).notna()
        | merged.get("monthly_rent", pd.Series(index=merged.index)).notna()
        | merged.get("harga_beli_kemitraan", pd.Series(index=merged.index)).notna()
        | merged.get("harga_mesin", pd.Series(index=merged.index)).notna()
    )
    if "ownership_status" not in merged.columns:
        merged["ownership_status"] = ""
    merged["ownership_status"] = np.where(has_terms, "kemitraan", "")
    return merged.drop(columns=["_key"], errors="ignore")

def sync_sharing_to_mapping(sharing_df: pd.DataFrame, period: Optional[str] = None) -> Tuple[int, int]:
    try:
        mapping = pd.read_csv(OUTLET_MAPPING_PATH)
    except Exception:
        mapping = pd.DataFrame(columns=["outlet_name"])
    if mapping.empty:
        mapping = pd.DataFrame(columns=["outlet_name"])
    if "outlet_name" not in mapping.columns:
        mapping["outlet_name"] = ""
    mapping["_key"] = mapping["outlet_name"].map(normalize_outlet_name)
    existing_keys = set(mapping["_key"].dropna().astype(str))
    additions = []
    for _, row in sharing_df.iterrows():
        key = normalize_outlet_name(row.get("outlet_name", ""))
        if key and key not in existing_keys:
            additions.append({"outlet_name": row.get("outlet_name", "")})
            existing_keys.add(key)
    if additions:
        mapping = pd.concat([mapping.drop(columns=["_key"], errors="ignore"), pd.DataFrame(additions)], ignore_index=True)
    else:
        mapping = mapping.drop(columns=["_key"], errors="ignore")
    mapping = apply_sharing_to_mapping(mapping, period)
    mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
    return len(mapping), len(additions)

def render_sharing_upload_panel(config: Config) -> None:
    periods = list_sharing_periods()
    latest_period = periods[-1] if periods else None
    latest_rows = 0
    if latest_period:
        _, latest_df = load_sharing_outlets(latest_period)
        latest_rows = len(latest_df)
    st.subheader("Upload Data Sharing Outlet")
    st.caption("Upload file outlet-list Excel per bulan. Contoh file bulanan: sftp://killdower@103.250.10.163/home/killdower/dower/outlet_update.xlsx. Data ini menimpa partner share, broker share, minimum payment, dan rent sesuai periode kontrak.")
    c1, c2 = st.columns([1, 2])
    with c1:
        period_input = st.text_input("Periode sharing (YYYY-MM)", value=datetime.now().strftime("%Y-%m"), key="sharing_period_input")
    with c2:
        sharing_file = st.file_uploader("File Excel sharing outlet", type=["xlsx", "xls"], key="sharing_upload_file")
    if sharing_file is not None:
        if not re.match(r"^\d{4}-\d{2}$", str(period_input or "")):
            inferred = infer_period_from_filename(sharing_file.name)
            if inferred:
                period_input = inferred
        if st.button("Upload & Terapkan Sharing", type="primary", key="sharing_upload_submit"):
            if not re.match(r"^\d{4}-\d{2}$", str(period_input or "")):
                st.error("Periode wajib format YYYY-MM.")
            else:
                sharing_df = parse_sharing_outlet_excel(sharing_file)
                if sharing_df.empty:
                    st.error("File tidak berisi outlet yang valid.")
                else:
                    save_sharing_outlets(period_input, sharing_df)
                    total, added = sync_sharing_to_mapping(sharing_df, period_input)
                    try:
                        cache_clear(load_app_data)
                    except Exception:
                        pass
                    st.success(f"{period_input}: {len(sharing_df)} outlet sharing tersimpan. Master outlet: {total} baris, tambah baru: {added}.")
                    rerun()
    st.info(f"Sharing terbaru: {latest_period or '-'} ({latest_rows} outlet). Periode tersimpan: {', '.join(periods) if periods else '-'}.")

SHARING_MASTER_COLUMNS = [
    "outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master",
    "investor_name", "partner_share", "broker_share", "sharing_bagi_hasil",
    "monthly_rent", "minimum_payment", "harga_beli_kemitraan", "created_at",
]

def normalize_sharing_master_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    rename_map = {
        "ID": "outlet_id", "Name": "outlet_name", "NAME": "outlet_name",
        "BRANCH": "area", "STATUS": "outlet_status_master", "TYPE": "outlet_type_master",
        "OWNER": "investor_name", "PARTNER_SHARE": "partner_share", "BROKER_SHARE": "broker_share",
        "MONTHLY_RENT": "monthly_rent", "MINIMUM_PAYMENT": "minimum_payment", "INITIAL_COST": "harga_beli_kemitraan",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})
    if "harga_beli_kemitraan" not in out.columns:
        out["harga_beli_kemitraan"] = np.nan
    if "harga_mesin" in out.columns:
        out["harga_beli_kemitraan"] = out["harga_beli_kemitraan"].combine_first(out["harga_mesin"])
    for col in SHARING_MASTER_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan if col not in ["outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master", "investor_name", "created_at"] else ""
    out = out[SHARING_MASTER_COLUMNS].copy()
    for col in ["outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master", "investor_name", "created_at"]:
        out[col] = out[col].fillna("").astype(str).str.strip()
    for col in ["partner_share", "broker_share", "sharing_bagi_hasil"]:
        out[col] = out[col].apply(_share_num)
    for col in ["monthly_rent", "minimum_payment", "harga_beli_kemitraan"]:
        out[col] = out[col].apply(_money_num)
    out["harga_mesin"] = out["harga_beli_kemitraan"]
    missing_share = out["sharing_bagi_hasil"].isna() & (out["partner_share"].notna() | out["broker_share"].notna())
    out.loc[missing_share, "sharing_bagi_hasil"] = (
        1 - out.loc[missing_share, "partner_share"].fillna(0) - out.loc[missing_share, "broker_share"].fillna(0)
    ).clip(lower=0, upper=1)
    out = out[out["outlet_name"].astype(str).str.strip() != ""].copy()
    out["_key"] = out["outlet_name"].map(normalize_outlet_name)
    out = out.drop_duplicates("_key", keep="last").drop(columns=["_key"])
    return out.reset_index(drop=True)

def build_kemitraan_financials(transactions_df: pd.DataFrame, sharing_df: pd.DataFrame, mapping_df: pd.DataFrame, period: Optional[str]) -> pd.DataFrame:
    master = normalize_sharing_master_df(sharing_df)
    if master.empty:
        return master

    master["_key"] = master["outlet_name"].map(normalize_outlet_name)

    if isinstance(mapping_df, pd.DataFrame) and not mapping_df.empty and "outlet_name" in mapping_df.columns:
        mapping_cols = ["outlet_name", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]
        mapping = mapping_df[[c for c in mapping_cols if c in mapping_df.columns]].copy()
        mapping["_key"] = mapping["outlet_name"].map(normalize_outlet_name)
        mapping = mapping.drop_duplicates("_key", keep="last").drop(columns=["outlet_name"], errors="ignore")
        master = master.merge(mapping, on="_key", how="left")

    if isinstance(transactions_df, pd.DataFrame) and not transactions_df.empty and "outlet_name" in transactions_df.columns:
        tx = transactions_df.copy()
        if period and "periode" in tx.columns:
            tx = tx[tx["periode"].astype(str) == str(period)].copy()
        tx["_key"] = tx["outlet_name"].map(normalize_outlet_name)
        if "total_revenue" not in tx.columns:
            tx["total_revenue"] = 0
        revenue = tx.groupby("_key", as_index=False).agg(total_revenue=("total_revenue", "sum"))
    else:
        revenue = pd.DataFrame(columns=["_key", "total_revenue"])

    master = master.merge(revenue, on="_key", how="left")
    master["total_revenue"] = pd.to_numeric(master.get("total_revenue", 0), errors="coerce").fillna(0.0)
    master["basis_bagi_hasil"] = np.where(master["total_revenue"] > 0, master["total_revenue"], master["minimum_payment"].fillna(0))
    master["partner_share"] = master["partner_share"].clip(lower=0, upper=1)
    master["broker_share"] = master["broker_share"].fillna(0).clip(lower=0, upper=1)
    master["sharing_bagi_hasil"] = master["sharing_bagi_hasil"].clip(lower=0, upper=1)
    master["pendapatan_mitra"] = np.where(
        master["partner_share"].notna(),
        master["basis_bagi_hasil"] * master["partner_share"],
        master["basis_bagi_hasil"] * (1 - master["sharing_bagi_hasil"].fillna(0) - master["broker_share"].fillna(0)),
    )
    master["pendapatan_broker"] = master["basis_bagi_hasil"] * master["broker_share"].fillna(0)
    master["pendapatan_difotoin"] = master["basis_bagi_hasil"] * master["sharing_bagi_hasil"].fillna(0)
    master["profit_difotoin"] = master["pendapatan_difotoin"].fillna(0) - master["monthly_rent"].fillna(0)
    master["estimasi_bep_bulan"] = np.where(
        (master["harga_beli_kemitraan"] > 0) & (master["pendapatan_mitra"] > 0),
        master["harga_beli_kemitraan"] / master["pendapatan_mitra"],
        np.nan,
    )
    master["yield_bulanan"] = np.where(
        master["harga_beli_kemitraan"] > 0,
        master["pendapatan_mitra"] / master["harga_beli_kemitraan"],
        np.nan,
    )
    master["yield_tahunan"] = master["yield_bulanan"] * 12
    return master.drop(columns=["_key"], errors="ignore")

def format_kemitraan_table(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    display = df.copy()
    money_cols = [
        "total_revenue", "basis_bagi_hasil", "revenue", "pendapatan_mitra", "pendapatan_broker",
        "pendapatan_difotoin", "profit_difotoin", "monthly_rent", "minimum_payment",
        "harga_beli_kemitraan", "harga_beli",
    ]
    pct_cols = ["partner_share", "broker_share", "sharing_bagi_hasil", "yield_bulanan", "yield_tahunan"]
    for col in money_cols:
        if col in display.columns:
            display[col] = display[col].apply(lambda x: config.format_currency(float(x)) if pd.notna(x) and float(x) > 0 else "-")
    for col in pct_cols:
        if col in display.columns:
            display[col] = display[col].apply(lambda x: "-" if pd.isna(x) else f"{float(x)*100:.1f}%")
    if "estimasi_bep_bulan" in display.columns:
        display["estimasi_bep_bulan"] = display["estimasi_bep_bulan"].apply(lambda x: "-" if pd.isna(x) else f"{float(x):.1f} bulan")
    return display

def add_profit_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["total_revenue", "minimum_payment", "partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["basis_bagi_hasil"] = np.where(out["total_revenue"].fillna(0) > 0, out["total_revenue"].fillna(0), out["minimum_payment"].fillna(0))
    missing_share = out["sharing_bagi_hasil"].isna() & (out["partner_share"].notna() | out["broker_share"].notna())
    out.loc[missing_share, "sharing_bagi_hasil"] = (1 - out.loc[missing_share, "partner_share"].fillna(0) - out.loc[missing_share, "broker_share"].fillna(0)).clip(lower=0, upper=1)
    out["pendapatan_operator"] = out["basis_bagi_hasil"].fillna(0) * out["sharing_bagi_hasil"].fillna(0)
    out["estimasi_profit_difotoin"] = out["pendapatan_operator"].fillna(0) - out["monthly_rent"].fillna(0)
    return out

# ================= EXPORT EXCEL (OMSET TREND) =================
from io import BytesIO


def _export_trend_excel(df_display_sorted, value_cols):
    export_df = df_display_sorted.copy()

    for col in ["Rata-rata"] + value_cols:
        if col in export_df.columns:
            # ambil angka murni
            export_df[col] = (
                export_df[col]
                .astype(str)
                .str.replace(r"[^0-9]", "", regex=True)
                .replace("", "0")
                .astype(int)
            )

            # FIX: kurangin 1 digit nol (10x -> normal)
            export_df[col] = (export_df[col] // 10).astype(int)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Tren Omset")
    buffer.seek(0)

    st.download_button(
        "⬇️ Download Excel (Angka Murni)",
        data=buffer,
        file_name="tren_omset_outlet_12_bulan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

# ======== Derive foto/unlock/print from 'type' with synonyms ========
FOTO_RE = re.compile(r"\b(foto|photo|photos|capture|shoot)\b", re.I)
UNLOCK_RE = re.compile(r"\b(unlock|qr|scan)\b", re.I)
PRINT_RE = re.compile(r"\b(print|printed|cetak|printout|print-out)\b", re.I)

def derive_counts_from_type(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    d = df.copy()
    t = d["type"].astype(str).str.strip().str.lower().fillna("") if "type" in d.columns else pd.Series([""]*len(d), index=d.index)
    d["_foto_qty"]   = t.str.contains(FOTO_RE).astype(int)
    d["_unlock_qty"] = t.str.contains(UNLOCK_RE).astype(int)
    d["_print_qty"]  = t.str.contains(PRINT_RE).astype(int)
    audit = {"match_foto": int(d["_foto_qty"].sum()), "match_unlock": int(d["_unlock_qty"].sum()), "match_print": int(d["_print_qty"].sum())}
    return d, audit

def compute_status(total_revenue: float, config: Config) -> str:
    keep = config.get_threshold('keeper_minimum'); opt = config.get_threshold('optimasi_minimum')
    if total_revenue >= keep: return "Keeper"
    if total_revenue >= opt:  return "Optimasi"
    return "Relocate"

# ======== Agregasi ========
def aggregate_monthly(mapped_df: pd.DataFrame, config: Config, fallback_period: Optional[str] = None) -> Tuple[pd.DataFrame, dict]:
    df = mapped_df.copy()
    if "tanggal" in df.columns and df["tanggal"].notna().any():
        df["periode"] = pd.to_datetime(df["tanggal"], errors="coerce").dt.strftime("%Y-%m")
    else:
        df["periode"] = fallback_period or datetime.now().strftime("%Y-%m")

    have_cols = all(c in df.columns for c in ["foto","unlock","print"])
    totals_zero = False
    if have_cols:
        df["_foto_qty"]   = pd.to_numeric(df["foto"], errors="coerce").fillna(0).astype(int)
        df["_unlock_qty"] = pd.to_numeric(df["unlock"], errors="coerce").fillna(0).astype(int)
        df["_print_qty"]  = pd.to_numeric(df["print"], errors="coerce").fillna(0).astype(int)
        totals_zero = (df["_foto_qty"].sum()==0) and (df["_unlock_qty"].sum()==0) and (df["_print_qty"].sum()==0)

    audit_derive = {"match_foto":0,"match_unlock":0,"match_print":0}
    if (not have_cols or totals_zero) and ("type" in df.columns):
        df, audit_derive = derive_counts_from_type(df)

    if "outlet_name" not in df.columns:
        raise ValueError("Kolom 'Outlet' tidak ditemukan (harap set mapping kolom Outlet di UI).")

    group_keys = ["periode","outlet_name"]
    if "area" in df.columns: group_keys.append("area")
    df["harga"] = pd.to_numeric(df["harga"], errors="coerce").fillna(0.0)

    agg = df.groupby(group_keys, dropna=False).agg(
        total_revenue=("harga","sum"),
        foto_qty=("_foto_qty","sum"),
        unlock_qty=("_unlock_qty","sum"),
        print_qty=("_print_qty","sum")
    ).reset_index()

    agg["conversion_rate"] = np.where(agg["foto_qty"]>0, agg["print_qty"]/agg["foto_qty"]*100, 0.0)
    agg["outlet_status"] = agg["total_revenue"].apply(lambda x: compute_status(float(x), config))
    for col in ["kategori_tempat","sub_kategori_tempat","tipe_tempat"]:
        if col not in agg.columns: agg[col] = "Tidak Terkategorisasi"
    agg["area"] = agg.get("area","").astype(str).replace({"nan": ""})

    cols = ["periode","outlet_name","area","kategori_tempat","sub_kategori_tempat","tipe_tempat",
            "total_revenue","foto_qty","unlock_qty","print_qty","conversion_rate","outlet_status"]
    for c in cols:
        if c not in agg.columns: agg[c] = np.nan

    return agg[cols], audit_derive

# ======== SAVE: OVERWRITE by PERIOD ========
def save_overwrite_periods(new_df: pd.DataFrame, path: str) -> Tuple[pd.DataFrame, dict]:
    periods = sorted(new_df["periode"].astype(str).unique().tolist())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        old = pd.read_csv(path)
        before_total = float(pd.to_numeric(old.get("total_revenue", 0), errors="coerce").fillna(0).sum())
        before_periods = sorted(old.get("periode", pd.Series(dtype=str)).astype(str).unique().tolist())
        remaining = old[~old["periode"].astype(str).isin(periods)].copy()
        merged = pd.concat([remaining, new_df], ignore_index=True)
    else:
        before_total = 0.0
        before_periods = []
        merged = new_df.copy()

    merged = merged.sort_values(["periode","outlet_name"]).reset_index(drop=True)
    merged.to_csv(path, index=False)
    after_total = float(pd.to_numeric(merged["total_revenue"], errors="coerce").fillna(0).sum())
    return merged, {"periods_overwritten": periods,"before_total": before_total,"after_total": after_total,
                    "before_periods": before_periods,"remaining_periods": sorted(merged["periode"].astype(str).unique().tolist())}

# ================= TABLE (compare) =================
def format_comparison_value(current_val, compare_val, is_percentage=False):
    if compare_val == 0:
        return "0.0%" if not is_percentage else "0.0pp"
    if is_percentage:
        change = float(current_val) - float(compare_val)
        sign = "+" if change > 0 else ""
        return f"{sign}{change:.1f}pp" if change != 0 else "0.0pp"
    change_pct = ((float(current_val) - float(compare_val)) / float(compare_val)) * 100
    sign = "+" if change_pct > 0 else ""
    return f"{sign}{change_pct:.1f}%" if change_pct != 0 else "0.0%"

def create_outlet_table(df, current_period, compare_period, full_df=None):
    st.markdown('<div class="outlet-table">', unsafe_allow_html=True)
    st.markdown("### 🏪 Outlet Performance Table")

    st.markdown('<div class="filter-buttons">', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: show_keeper = st.checkbox("🟢 Keeper", value=True, key="filter_keeper")
    with col2: show_optimasi = st.checkbox("🟡 Optimasi", value=True, key="filter_optimasi")
    with col3: show_relocate = st.checkbox("🔴 Relocate", value=True, key="filter_relocate")
    with col4: show_inactive = st.checkbox("Tidak Aktif", value=True, key="filter_inactive")
    with col5: show_all = st.checkbox("Show All", value=False, key="filter_all")
    st.markdown('</div>', unsafe_allow_html=True)

    src = full_df if isinstance(full_df, pd.DataFrame) and not full_df.empty else df
    if src.empty or "outlet_name" not in src.columns:
        st.info("No outlets match the selected filters")
        st.markdown('</div>', unsafe_allow_html=True); return

    source_df = src.copy(deep=True)
    source_df["outlet_name"] = source_df["outlet_name"].fillna("").astype(str).str.strip()
    source_df = source_df[source_df["outlet_name"] != ""]
    if source_df.empty:
        st.info("No outlets match the selected filters")
        st.markdown('</div>', unsafe_allow_html=True); return

    current_src = source_df[source_df["periode"].astype(str) == str(current_period)].copy() if current_period and "periode" in source_df.columns else df.copy(deep=True)
    if "outlet_name" in current_src.columns:
        current_src["outlet_name"] = current_src["outlet_name"].fillna("").astype(str).str.strip()
    current_map = {}
    if not current_src.empty and "outlet_name" in current_src.columns:
        current_src["_key"] = current_src["outlet_name"].map(_norm_name)
        current_map = current_src.drop_duplicates("_key", keep="last").set_index("_key").to_dict(orient="index")

    meta = source_df.drop_duplicates("outlet_name", keep="last").set_index("outlet_name").to_dict(orient="index")

    compare_map = {}
    if compare_period:
        cmp_df = src[src["periode"] == compare_period].copy()
        if not cmp_df.empty:
            cmp_df["_key"] = cmp_df["outlet_name"].map(_norm_name)
            compare_map = cmp_df.set_index("_key").to_dict(orient="index")

    rows = []
    for name in sorted(source_df["outlet_name"].dropna().astype(str).unique().tolist()):
        key = _norm_name(name)
        is_active = key in current_map
        r = current_map.get(key, meta.get(name, {}))
        omset = float(r.get("total_revenue", 0) or 0) if is_active else 0.0
        foto = int(r.get("foto_qty", 0) or 0) if is_active else 0
        unlock = int(r.get("unlock_qty", 0) or 0) if is_active else 0
        conv = float(r.get("conversion_rate", 0) or 0) if is_active else 0.0
        status = str(r.get("outlet_status", "")) if is_active else "Tidak Aktif"
        if not show_all:
            keep = []
            if show_keeper: keep.append("Keeper")
            if show_optimasi: keep.append("Optimasi")
            if show_relocate: keep.append("Relocate")
            if show_inactive: keep.append("Tidak Aktif")
            if status not in keep:
                continue
        rec = {
            "Outlet": name, "Area": r.get("area",""),
            "_omset_sort": int(omset), "_foto_sort": int(foto), "_unlock_sort": int(unlock), "_conversion_sort": float(conv),
            "Omset": float(omset), "Omset Compare": "New Outlet",
            "Foto": int(foto), "Foto Compare": "New Outlet",
            "Unlock": int(unlock), "Unlock Compare": "New Outlet",
            "Conversion": float(conv), "Conversion Compare": "New Outlet",
            "Status": status,
            "_omset_delta": np.nan, "_foto_delta": np.nan, "_unlock_delta": np.nan, "_conv_delta": np.nan
        }
        if compare_period and key in compare_map:
            p = compare_map[key]
            p_omset = float(p.get("total_revenue", 0) or 0)
            p_foto  = int(p.get("foto_qty", 0) or 0)
            p_unlock= int(p.get("unlock_qty", 0) or 0)
            p_conv  = float(p.get("conversion_rate", 0) or 0)
            rec["Omset Compare"]      = format_comparison_value(omset, p_omset, False)
            rec["Foto Compare"]       = format_comparison_value(foto, p_foto, False)
            rec["Unlock Compare"]     = format_comparison_value(unlock, p_unlock, False)
            rec["Conversion Compare"] = format_comparison_value(conv, p_conv, True)
            rec["_omset_delta"] = 0 if p_omset==0 else ((omset - p_omset)/p_omset)*100
            rec["_foto_delta"]  = 0 if p_foto ==0 else ((foto  - p_foto )/p_foto )*100
            rec["_unlock_delta"]= 0 if p_unlock==0 else ((unlock- p_unlock)/p_unlock)*100
            rec["_conv_delta"]  = (conv - p_conv)
        rows.append(rec)

    if not rows:
        st.info("No outlets match the selected filters")
        st.markdown('</div>', unsafe_allow_html=True); return

    table_df = pd.DataFrame(rows)
    visible = (["Outlet","Area","Omset","Omset Compare","Foto","Foto Compare","Unlock","Unlock Compare","Conversion","Conversion Compare","Status"]
               if compare_period else ["Outlet","Area","Omset","Foto","Unlock","Conversion","Status"])

    st.info("💡 **Sorting**: gunakan dropdown untuk mengurutkan")
    c1, c2 = st.columns([2,1])
    with c1: sort_col_name = st.selectbox("Sort by:", ["Omset","Foto","Unlock","Conversion"], key="sort_column")
    with c2: order = st.selectbox("Order:", ["Descending (High to Low)","Ascending (Low to High)"], key="sort_order")
    sort_key = {"Omset":"_omset_sort","Foto":"_foto_sort","Unlock":"_unlock_sort","Conversion":"_conversion_sort"}[sort_col_name]
    ascending = order == "Ascending (Low to High)"
    table_sorted = table_df.sort_values(sort_key, ascending=ascending).reset_index(drop=True)
    display_df = table_sorted[visible].copy()

    def style_status(val):
        if val == 'Keeper': return 'color:#10b981;font-weight:bold'
        if val == 'Optimasi': return 'color:#f59e0b;font-weight:bold'
        if val == 'Relocate': return 'color:#ef4444;font-weight:bold'
        if val == 'Tidak Aktif': return 'color:#94a3b8;font-weight:bold'
        return ''
    styled = display_df.style.map(style_status, subset=["Status"])

    def color_by_delta(series, delta_series):
        d = delta_series.reindex(series.index).fillna(0)
        return ['color:#10b981;font-weight:600' if x>0 else ('color:#ef4444;font-weight:600' if x<0 else '') for x in d]

    if compare_period:
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_omset_delta']), axis=0, subset=['Omset Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_foto_delta']), axis=0, subset=['Foto Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_unlock_delta']), axis=0, subset=['Unlock Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_conv_delta']), axis=0, subset=['Conversion Compare'])
    styled = styled.format({
        "Omset": format_number_with_dots,
        "Foto": format_number_with_dots,
        "Unlock": format_number_with_dots,
        "Conversion": lambda v: format_decimal_with_comma(v, 1, "%"),
    })

    column_config = None
    if HAS_COLUMN_CONFIG:
        column_config = {
            "Outlet": text_col("Outlet", width="medium"),
            "Area": text_col("Area", width="small"),
            "Omset Compare": text_col("Omset Compare", width="medium"),
            "Foto Compare": text_col("Foto Compare", width="small"),
            "Unlock Compare": text_col("Unlock Compare", width="small"),
            "Conversion Compare": text_col("Conversion Compare", width="small"),
            "Status": text_col("Status", width="small"),
        }

    mobile_df = display_df.copy()
    for col in ("Omset", "Foto", "Unlock"):
        if col in mobile_df.columns:
            mobile_df[col] = mobile_df[col].apply(format_number_with_dots)
    if "Conversion" in mobile_df.columns:
        mobile_df["Conversion"] = mobile_df["Conversion"].apply(lambda v: format_decimal_with_comma(v, 1, "%"))
    mobile_rows = [
        ("Area", "Area"),
        ("Omset", "Omset"),
        ("Foto", "Foto"),
        ("Unlock", "Unlock"),
        ("Conversion", "Conversion"),
    ]
    if compare_period:
        mobile_rows.extend([
            ("Omset vs compare", "Omset Compare"),
            ("Foto vs compare", "Foto Compare"),
            ("Unlock vs compare", "Unlock Compare"),
            ("Conversion vs compare", "Conversion Compare"),
        ])
    render_mobile_cards(mobile_df, "Outlet", mobile_rows, status_col="Status", max_rows=25)
    st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
    df_show(styled, use_container_width=True, hide_index=True, column_config=column_config)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ================= OMSET TREND TABLE (12 bulan + Rata-rata + server-side sorting) =================
def _sort_periods_str(periods: List[str]) -> List[str]:
    s = pd.Series(periods, dtype=object)
    dt = pd.to_datetime(s, format="%Y-%m", errors="coerce")
    helper = pd.DataFrame({"p": s, "dt": dt}).sort_values(by=["dt","p"], na_position="last")
    return helper["p"].astype(str).tolist()

def _list_last_n_periods(anchor_period: str, n: int) -> List[str]:
    try:
        y, m = map(int, anchor_period.split("-"))
    except Exception:
        dt = pd.to_datetime(anchor_period, errors="coerce")
        if pd.isna(dt): return []
        y, m = dt.year, dt.month
    out = []
    for k in range(n):
        total = y * 12 + (m - 1) - k
        yy = total // 12
        mm = (total % 12) + 1
        out.append(f"{yy:04d}-{mm:02d}")
    return out

def show_omset_trend_table(df_filtered: pd.DataFrame, df_full: pd.DataFrame, config: Config, current_period: Optional[str], months: int = 12):
    st.subheader("📆 Tren Omset Outlet (12 Bulan)")
    if df_full.empty or "outlet_name" not in df_full.columns or "periode" not in df_full.columns:
        st.info("Data tidak cukup untuk menampilkan tren omset."); return

    visible_outlets = df_full["outlet_name"].dropna().astype(str).str.strip().unique().tolist()
    trend_df = df_full[df_full["outlet_name"].astype(str).str.strip().isin(visible_outlets)].copy()
    if trend_df.empty:
        st.info("Tidak ada data tren untuk outlet terpilih."); return

    trend_df["outlet_name"] = trend_df["outlet_name"].astype(str).str.strip()
    trend_df["total_revenue"] = pd.to_numeric(trend_df.get("total_revenue", 0), errors="coerce").fillna(0.0)

    anchor = current_period if (current_period and isinstance(current_period, str)) else (
        _sort_periods_str([str(x) for x in trend_df["periode"].dropna().unique().tolist()])[-1]
        if trend_df["periode"].notna().any() else None
    )
    if not anchor:
        st.info("Periode kosong."); return

    periods_window = _list_last_n_periods(anchor, months)
    if not periods_window:
        st.info("Gagal menentukan window periode."); return

    active_period = current_period if current_period else anchor
    active_outlets = set(
        trend_df.loc[trend_df["periode"].astype(str) == str(active_period), "outlet_name"]
        .dropna().astype(str).str.strip().tolist()
    )

    pivot = (
        trend_df.pivot_table(
            index="outlet_name",
            columns="periode",
            values="total_revenue",
            aggfunc="sum",
        )
        .reindex(columns=periods_window)
        .sort_index()
    )

    value_cols = periods_window

    def _avg_real_row(row: pd.Series) -> float:
        vals = [float(v) for v in row.tolist() if (pd.notna(v) and float(v) > 0.0)]
        return float(np.mean(vals)) if len(vals) > 0 else 0.0

    avg_real = pivot.apply(_avg_real_row, axis=1)
    display_pivot = pivot.fillna(0.0)

    display_df = display_pivot.reset_index().rename(columns={"outlet_name": "Outlet"})
    display_df.insert(1, "Rata-rata", avg_real.values)

    st.info("🔽 Sorting Tren Omset")
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        sort_by = st.selectbox("Urutkan berdasarkan", ["Rata-rata", "Outlet"], index=0, key="trend_sort_by")
    with sc2:
        sort_order = st.selectbox("Urutan", ["Descending (High to Low)", "Ascending (Low to High)"], index=0, key="trend_sort_order")
    ascending = (sort_order == "Ascending (Low to High)")
    if sort_by == "Outlet":
        display_df_sorted = display_df.sort_values(by="Outlet", ascending=ascending, kind="mergesort")
    else:
        display_df_sorted = display_df.sort_values(by="Rata-rata", ascending=ascending, kind="mergesort")
    display_df_sorted["_aktif_current"] = display_df_sorted["Outlet"].astype(str).isin(active_outlets)

    def _growth_colors(row: pd.Series):
        vals = row[value_cols]
        cells = []
        last_index = len(vals) - 1
        for j in range(len(vals)):
            if j == last_index:
                cells.append("")
            else:
                cur = float(vals.iloc[j]) if pd.notna(vals.iloc[j]) else 0.0
                prv = float(vals.iloc[j+1]) if pd.notna(vals.iloc[j+1]) else 0.0
                if cur > prv:
                    cells.append("color:#10b981;font-weight:600")
                elif cur < prv:
                    cells.append("color:#ef4444;font-weight:600")
                else:
                    cells.append("")
        return cells

    def _fmt_currency(x, _cfg=config):
        try:
            v = 0.0 if (x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x)))) else float(x)
            return _cfg.format_currency(v)
        except Exception:
            return _cfg.format_currency(0.0)

    fmt_map = {col: _fmt_currency for col in value_cols}
    fmt_map["Rata-rata"] = _fmt_currency

    column_config = None
    if HAS_COLUMN_CONFIG:
        column_config = {
            "Outlet": text_col("Outlet", width="medium"),
        }

    active_df = display_df_sorted[display_df_sorted["_aktif_current"]].drop(columns=["_aktif_current"])
    inactive_df = display_df_sorted[~display_df_sorted["_aktif_current"]].drop(columns=["_aktif_current"])

    st.markdown("**Outlet Aktif**")
    if active_df.empty:
        st.info("Tidak ada outlet aktif di periode ini.")
    else:
        active_mobile = active_df.copy()
        for col, formatter in fmt_map.items():
            if col in active_mobile.columns:
                active_mobile[col] = active_mobile[col].apply(formatter)
        render_mobile_cards(
            active_mobile,
            "Outlet",
            [("Rata-rata", "Rata-rata")] + [(p, p) for p in value_cols[:4]],
            max_rows=20,
        )
        styled_active = active_df.style.apply(_growth_colors, axis=1, subset=value_cols).format(fmt_map)
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(styled_active, use_container_width=True, hide_index=True, column_config=column_config)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("**Outlet Tidak Aktif di Periode Ini**")
    if inactive_df.empty:
        st.info("Tidak ada outlet tidak aktif di periode ini.")
    else:
        inactive_mobile = inactive_df.copy()
        for col, formatter in fmt_map.items():
            if col in inactive_mobile.columns:
                inactive_mobile[col] = inactive_mobile[col].apply(formatter)
        render_mobile_cards(
            inactive_mobile,
            "Outlet",
            [("Rata-rata", "Rata-rata")] + [(p, p) for p in value_cols[:4]],
            max_rows=20,
        )
        styled_inactive = inactive_df.style.apply(_growth_colors, axis=1, subset=value_cols).format(fmt_map)
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(styled_inactive, use_container_width=True, hide_index=True, column_config=column_config)
        st.markdown('</div>', unsafe_allow_html=True)
    s_caption("Nilai kosong ditampilkan sebagai 0. Rata-rata dihitung dari 12 bulan tampil (termasuk current), hanya omset > 0 yang dihitung. Hijau=naik vs bulan lalu; Merah=turun.")

    # ===== DOWNLOAD EXCEL (ANGKA MURNI) =====
    st.markdown("### 📥 Download Data")
    _export_trend_excel(display_df_sorted.drop(columns=["_aktif_current"]), value_cols)

# ================= PAGES =================
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

    page = st.sidebar.selectbox(
        "Pilih Halaman",
        ["🏠 Dashboard Utama","📊 Analisis Trend","AI Decision","🔄 Analisis Konversi",
         "🏆 Ranking Outlet","🤝 Kemitraan","📅 Perbandingan Periode","🗃️ CRUD Data Outlet","⚙️ Admin Panel","📤 Upload Data"]
    )

    current_period, compare_period = (None, None)
    if page in ["🏠 Dashboard Utama","📅 Perbandingan Periode"]:
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
        filtered_df = df
        filtered_full_df = df

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
    elif page == "📅 Perbandingan Periode":
        show_period_comparison(filtered_df, config, processor, viz, current_period, compare_period)
    elif page == "🗃️ CRUD Data Outlet":
        show_outlet_crud_v2(df, config, processor)
    elif page == "⚙️ Admin Panel":
        show_admin_panel(config)
    elif page == "📤 Upload Data":
        show_upload_data(config)

def show_main_dashboard(df, config, processor, viz, current_period, compare_period, full_df):
    st.markdown('<h1 class="main-header">📸 backup-dower</h1>', unsafe_allow_html=True)
    if df.empty:
        st.error("❌ Data tidak tersedia. Silakan upload data terlebih dahulu."); return

    m_df = df.copy(deep=True)
    for col in ["total_revenue","foto_qty","unlock_qty","print_qty","conversion_rate"]:
        if col in m_df.columns:
            m_df[col] = pd.to_numeric(m_df[col], errors="coerce").fillna(0)

    metrics = processor.calculate_metrics(m_df) if hasattr(processor, "calculate_metrics") else {
        "total_revenue": m_df["total_revenue"].sum(),
        "total_outlets": m_df["outlet_name"].nunique(),
        "avg_conversion": (m_df["conversion_rate"].mean() if "conversion_rate" in m_df.columns else 0),
        "total_photos": (m_df["foto_qty"].sum() if "foto_qty" in m_df.columns else 0),
    }

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("💰 Revenue", config.format_currency(metrics['total_revenue']))
    with c2: st.metric("🏪 Outlets", f"{metrics['total_outlets']}")
    with c3: st.metric("📈 Avg Conv Rate", f"{metrics['avg_conversion']:.1f}%")
    with c4: st.metric("📸 Photos", format_number_with_dots(metrics['total_photos']))
    st.markdown("---")

    create_outlet_table(m_df, current_period, compare_period, full_df=full_df)

    if m_df.empty:
        st.info("Tidak ada transaksi aktif di periode terpilih untuk filter ini. Outlet historis tetap tampil sebagai Tidak Aktif.")
        st.markdown("---")
        show_omset_trend_table(df_filtered=m_df, df_full=full_df, config=config, current_period=current_period, months=12)
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📊 Distribusi Status Outlet")
        st.plotly_chart(viz.create_status_distribution(m_df), use_container_width=True)
    with col2:
        st.subheader("🏆 Top 5 Performers")
        top = processor.get_top_performers(m_df, 5) if hasattr(processor, "get_top_performers") else m_df.sort_values("total_revenue", ascending=False).head(5)
        for _, row in top.iterrows():
            status_class = f"status-{str(row['outlet_status']).lower()}"
            st.markdown(f"""
            <div class="performer-card">
                <strong>{row['outlet_name']}</strong><br>
                <span class="{status_class}">{row['outlet_status']}</span> | 
                <span>{config.format_currency(row['total_revenue'])}</span> | 
                <span>{row['conversion_rate']:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    a, b = st.columns([2, 1])
    with a:
        st.subheader("💹 Revenue by Outlet")
        st.plotly_chart(viz.create_revenue_chart(m_df), use_container_width=True)
    with b:
        st.subheader("🔄 Conversion Funnel")
        st.plotly_chart(viz.create_conversion_funnel(m_df), use_container_width=True)

    st.markdown("---")
    st.subheader("💡 Key Insights")
    for insight in generate_insights(m_df, config):
        st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

    st.markdown("---")
    show_omset_trend_table(df_filtered=m_df, df_full=full_df, config=config, current_period=current_period, months=12)

# ---- pages lainnya (CRUD, Trend, Conversion, Ranking, Comparison, Admin, Upload) ----
def show_outlet_crud(df, config, processor):
    st.title("🗃️ CRUD Data Outlet & Master Data")
    outlet_mapping = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()
    if outlet_mapping.empty and not df.empty:
        base = df.copy(deep=True)
        outlets = base['outlet_name'].unique()
        outlet_mapping = pd.DataFrame({
            'outlet_name': outlets,
            'area': base.groupby('outlet_name')['area'].first().values if "area" in base.columns else "",
            'kategori_tempat': base.groupby('outlet_name')['kategori_tempat'].first().values if "kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            'sub_kategori_tempat': base.groupby('outlet_name')['sub_kategori_tempat'].first().values if "sub_kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            'tipe_tempat': base.groupby('outlet_name')['tipe_tempat'].first().values if "tipe_tempat" in base.columns else "Indoor"
        })
    tab1, tab2, tab3 = st.tabs(["🏪 Outlet Management", "📋 Master Data Kategori", "🗺️ Master Data Area"])
    with tab1:
        s1, s2, s3, s4 = st.tabs(["📋 View All", "➕ Add New", "✏️ Edit", "🗑️ Delete"])
        with s1:
            st.subheader("📋 All Outlet Data")
            df_show(outlet_mapping, use_container_width=True, hide_index=True) if not outlet_mapping.empty else st.info("No outlet data available")
        with s2:
            st.subheader("➕ Add New Outlet")
            with st.form("add_outlet_form"):
                new_outlet_name = st.text_input("Outlet Name")
                new_area = st.selectbox("Area", INDONESIA_AREAS)
                new_kategori = st.selectbox("Kategori Tempat", KATEGORI_TEMPAT)
                new_sub_kategori = st.selectbox("Sub Kategori Tempat", SUB_KATEGORI_TEMPAT)
                new_tipe = st.selectbox("Tipe Tempat", ["Indoor","Outdoor","Semi-Outdoor"])
                if st.form_submit_button("Add Outlet") and new_outlet_name:
                    if 'outlet_name' in outlet_mapping and new_outlet_name in outlet_mapping['outlet_name'].values:
                        st.error("❌ Outlet already exists!")
                    else:
                        new_row = pd.DataFrame({'outlet_name':[new_outlet_name],'area':[new_area],
                                                'kategori_tempat':[new_kategori],'sub_kategori_tempat':[new_sub_kategori],
                                                'tipe_tempat':[new_tipe]})
                        outlet_mapping = pd.concat([outlet_mapping, new_row], ignore_index=True)
                        outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                        st.success("✅ Outlet added successfully!"); rerun()
        with s3:
            st.subheader("✏️ Edit Outlet")
            if not outlet_mapping.empty:
                outlet_to_edit = st.selectbox("Select Outlet to Edit", outlet_mapping['outlet_name'].tolist())
                if outlet_to_edit:
                    row = outlet_mapping[outlet_mapping['outlet_name']==outlet_to_edit].iloc[0]
                    with st.form("edit_outlet_form"):
                        edit_area = st.selectbox("Area", INDONESIA_AREAS, index=INDONESIA_AREAS.index(row['area']) if row['area'] in INDONESIA_AREAS else 0)
                        edit_kat = st.selectbox("Kategori Tempat", KATEGORI_TEMPAT, index=KATEGORI_TEMPAT.index(row['kategori_tempat']) if row['kategori_tempat'] in KATEGORI_TEMPAT else 0)
                        edit_sub = st.selectbox("Sub Kategori Tempat", SUB_KATEGORI_TEMPAT, index=SUB_KATEGORI_TEMPAT.index(row['sub_kategori_tempat']) if row['sub_kategori_tempat'] in SUB_KATEGORI_TEMPAT else 0)
                        pilihan_tipe = ["Indoor","Outdoor","Semi-Outdoor"]
                        edit_tipe = st.selectbox("Tipe Tempat", pilihan_tipe, index=pilihan_tipe.index(row['tipe_tempat']) if row['tipe_tempat'] in pilihan_tipe else 0)
                        if st.form_submit_button("Update Outlet"):
                            outlet_mapping.loc[outlet_mapping['outlet_name']==outlet_to_edit, ['area','kategori_tempat','sub_kategori_tempat','tipe_tempat']] = [edit_area, edit_kat, edit_sub, edit_tipe]
                            outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                            st.success("✅ Outlet updated successfully!"); rerun()
            else:
                st.info("No outlets available to edit")
        with s4:
            st.subheader("🗑️ Delete Outlet")
            if not outlet_mapping.empty:
                outlet_to_delete = st.selectbox("Select Outlet to Delete", outlet_mapping['outlet_name'].tolist())
                if outlet_to_delete and st.button("🗑️ Confirm Delete"):
                    outlet_mapping = outlet_mapping[outlet_mapping['outlet_name']!=outlet_to_delete]
                    outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                    st.success("✅ Outlet deleted successfully!"); rerun()
            else:
                st.info("No outlets available to delete")
    with tab2:
        st.subheader("📋 Master Data Kategori & Sub Kategori")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Kategori Tempat**")
            df_show(pd.DataFrame({'Kategori': KATEGORI_TEMPAT}), use_container_width=True, hide_index=True)
            with st.form("add_kategori_form"):
                nk = st.text_input("Nama Kategori Baru")
                if st.form_submit_button("Tambah Kategori"):
                    if nk and nk not in KATEGORI_TEMPAT:
                        KATEGORI_TEMPAT.append(nk); st.success(f"✅ Kategori '{nk}' berhasil ditambahkan!"); rerun()
                    else: st.error("❌ Kategori sudah ada atau kosong!")
        with c2:
            st.markdown("**Sub Kategori Tempat**")
            df_show(pd.DataFrame({'Sub Kategori': SUB_KATEGORI_TEMPAT}), use_container_width=True, hide_index=True)
            with st.form("add_sub_kategori_form"):
                ns = st.text_input("Nama Sub Kategori Baru")
                if st.form_submit_button("Tambah Sub Kategori"):
                    if ns and ns not in SUB_KATEGORI_TEMPAT:
                        SUB_KATEGORI_TEMPAT.append(ns); st.success(f"✅ Sub Kategori '{ns}' berhasil ditambahkan!"); rerun()
                    else: st.error("❌ Sub Kategori sudah ada atau kosong!")
    with tab3:
        st.subheader("🗺️ Master Data Area (Kota & Kabupaten Indonesia)")
        a1, a2 = st.columns([2,1])
        with a1:
            st.markdown("**Daftar Area Indonesia**")
            df_show(pd.DataFrame({'Area': INDONESIA_AREAS}), use_container_width=True, hide_index=True)
        with a2:
            with st.form("add_area_form"):
                na = st.text_input("Nama Kota/Kabupaten Baru")
                if st.form_submit_button("Tambah Area"):
                    if na and na not in INDONESIA_AREAS:
                        INDONESIA_AREAS.append(na); INDONESIA_AREAS.sort(); st.success(f"✅ Area '{na}' berhasil ditambahkan!"); rerun()
                    else: st.error("❌ Area sudah ada atau kosong!")
            st.info("📊 Total Area: {}".format(len(INDONESIA_AREAS)))

def suggest_outlet_metadata(outlet_name: str, current_row: Optional[dict] = None) -> dict:
    name = str(outlet_name or "").strip()
    text = name.lower()
    row = current_row or {}

    def has_any(words):
        return any(word in text for word in words)

    area_rules = [
        ("Jakarta", ["jakarta", "pik", "ancol", "senayan", "sarinah", "tmii", "jgc", "monas", "mandiri", "jis", "central park", "neo soho", "ashta", "pantjoran", "kota intan", "lapangan banteng", "taman literasi"]),
        ("Bali", ["bali", "kuta", "sanur", "gwk", "ubud", "bedugul", "ngurah rai", "beachwalk", "discovery mall", "dewata", "denpasar"]),
        ("Yogyakarta", ["jogja", "yogya", "malioboro", "heha", "obelix", "tugu jogja", "sleman"]),
        ("Bogor", ["bogor", "puncak", "sentul", "daong", "kopi tubing", "nicole", "kembali ke alam"]),
        ("Bekasi", ["bekasi", "deltamas", "cikarang"]),
        ("Tangerang", ["tangerang", "alam sutera", "flavor bliss", "lippo village"]),
        ("Samarinda", ["samarinda", "citra niaga"]),
        ("Semarang", ["semarang", "ambarawa"]),
        ("Batam", ["batam", "batamu"]),
        ("Malang", ["malang"]),
        ("Bandung", ["bandung", "castello"]),
    ]

    area = str(row.get("area", "") or "").strip()
    area_reason = "pakai data existing"
    area_conf = 55
    if not area or area.lower() in ["none", "nan", "lainnya"]:
        for candidate, keywords in area_rules:
            if has_any(keywords):
                area = candidate
                area_reason = "nama outlet mengandung keyword lokasi"
                area_conf = 82
                break
    if not area:
        area = "Lainnya"
        area_reason = "lokasi belum kebaca dari nama"
        area_conf = 35

    kategori = "Lainnya"
    sub = "Lainnya"
    tipe = "Indoor"
    cat_conf = 45
    cat_reason = "fallback umum"

    if has_any(["mall", "aeon", "living world", "neo soho", "city plaza", "sarinah", "beachwalk", "discovery mall", "bali icon", "central park", "ashta"]):
        kategori, sub, tipe, cat_conf = "Mall", "Shopping Center", "Indoor", 86
        cat_reason = "terdeteksi shopping center/mall"
    elif has_any(["hotel", "resort", "sheraton", "aryaduta", "alana", "ayodya", "villa", "vacation hotel"]):
        kategori, sub, tipe, cat_conf = "Hotel", "Resort/Hotel", "Indoor", 84
        cat_reason = "terdeteksi hotel/resort"
    elif has_any(["kopi", "koffie", "coffee", "cafe", "kopitiam", "burger", "buerger", "resto", "restaurant", "pantjoran"]):
        kategori, sub, tipe, cat_conf = "Restoran", "Coffee Shop", "Indoor", 80
        cat_reason = "terdeteksi cafe/restoran"
    elif has_any(["pantai", "beach", "kuta", "sanur", "sea view", "waterfront"]):
        kategori, sub, tipe, cat_conf = "Wisata", "Pantai", "Outdoor", 82
        cat_reason = "terdeteksi destinasi pantai/outdoor"
    elif has_any(["museum", "galeri", "mandiri"]):
        kategori, sub, tipe, cat_conf = "Museum", "Lainnya", "Indoor", 78
        cat_reason = "terdeteksi museum/galeri"
    elif has_any(["taman", "tmii", "ancol", "gwk", "heha", "obelix", "zoo", "kebun raya", "waterfall", "sky", "benteng", "puncak", "wisata", "park"]):
        kategori, sub, tipe, cat_conf = "Wisata", "Taman/Wisata Alam", "Outdoor", 78
        cat_reason = "terdeteksi objek wisata/taman"
    elif has_any(["event", "festival", "run", "gathering", "wedding", "ideas", "nextdev", "kompasianival", "bduck", "suzuki", "kpk", "bfn"]):
        kategori, sub, tipe, cat_conf = "Event Space", "Lainnya", "Semi-Outdoor", 76
        cat_reason = "terdeteksi event/aktivasi"
    elif has_any(["universitas", "university", "unj", "ui "]):
        kategori, sub, tipe, cat_conf = "Universitas", "Lainnya", "Indoor", 76
        cat_reason = "terdeteksi kampus"
    elif has_any(["sekolah", "school", "sph", "pelita harapan"]):
        kategori, sub, tipe, cat_conf = "Sekolah", "Lainnya", "Indoor", 76
        cat_reason = "terdeteksi sekolah"
    elif has_any(["airport", "bandara", "arrival", "ngurah rai"]):
        kategori, sub, tipe, cat_conf = "Transportasi", "Airport", "Indoor", 68
        cat_reason = "terdeteksi transport hub"
    elif has_any(["space", "creative", "cowork", "co-work"]):
        kategori, sub, tipe, cat_conf = "Komunitas", "Creative Space", "Indoor", 70
        cat_reason = "terdeteksi community/creative space"

    if kategori not in KATEGORI_TEMPAT:
        kategori = "Lainnya"
    if sub not in SUB_KATEGORI_TEMPAT:
        sub = "Lainnya"
    if tipe not in ["Indoor", "Outdoor", "Semi-Outdoor"]:
        tipe = "Indoor"

    existing_area = str(row.get("area", "") or "").strip()
    existing_kat = str(row.get("kategori_tempat", "") or "").strip()
    existing_sub = str(row.get("sub_kategori_tempat", "") or "").strip()
    existing_tipe = str(row.get("tipe_tempat", "") or "").strip()
    needs_update = (
        not existing_area or existing_area.lower() in ["none", "nan", "lainnya"] or
        existing_kat in ["", "Tidak Terkategorisasi"] or
        existing_sub in ["", "Tidak Terkategorisasi"] or
        existing_tipe in ["", "Tidak Terkategorisasi"]
    )

    confidence = int(round((area_conf + cat_conf) / 2))
    return {
        "outlet_name": name,
        "suggested_area": area,
        "suggested_kategori_tempat": kategori,
        "suggested_sub_kategori_tempat": sub,
        "suggested_tipe_tempat": tipe,
        "confidence": confidence,
        "reason": "{}; {}".format(area_reason, cat_reason),
        "needs_update": needs_update,
    }


def show_outlet_crud_v2(df, config, processor):
    st.title("Outlet Management")

    required_cols = ["outlet_name", "area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]
    outlet_mapping = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()

    if outlet_mapping.empty and not df.empty:
        base = df.copy(deep=True)
        outlets = base["outlet_name"].dropna().astype(str).unique()
        outlet_mapping = pd.DataFrame({
            "outlet_name": outlets,
            "area": base.groupby("outlet_name")["area"].first().reindex(outlets).fillna("").values if "area" in base.columns else "",
            "kategori_tempat": base.groupby("outlet_name")["kategori_tempat"].first().reindex(outlets).fillna("Tidak Terkategorisasi").values if "kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            "sub_kategori_tempat": base.groupby("outlet_name")["sub_kategori_tempat"].first().reindex(outlets).fillna("Tidak Terkategorisasi").values if "sub_kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            "tipe_tempat": base.groupby("outlet_name")["tipe_tempat"].first().reindex(outlets).fillna("Indoor").values if "tipe_tempat" in base.columns else "Indoor",
        })

    for col in required_cols:
        if col not in outlet_mapping.columns:
            outlet_mapping[col] = ""
    outlet_mapping = outlet_mapping[required_cols].copy()
    for col in required_cols:
        outlet_mapping[col] = outlet_mapping[col].fillna("").astype(str)
    outlet_mapping["outlet_name"] = outlet_mapping["outlet_name"].str.strip()
    outlet_mapping = outlet_mapping[outlet_mapping["outlet_name"] != ""].drop_duplicates("outlet_name", keep="last")
    deleted_outlets = set(load_deleted_outlets())

    if not df.empty and "outlet_name" in df.columns:
        source_outlets = df.copy(deep=True)
        source_outlets["outlet_name"] = source_outlets["outlet_name"].fillna("").astype(str).str.strip()
        source_outlets = source_outlets[source_outlets["outlet_name"] != ""]
        missing_names = sorted(set(source_outlets["outlet_name"]) - set(outlet_mapping["outlet_name"]) - deleted_outlets)

        if missing_names:
            def first_non_empty(frame, col, default_value=""):
                if col not in frame.columns:
                    return default_value
                values = frame[col].dropna().astype(str).str.strip()
                values = values[values != ""]
                return values.iloc[0] if len(values) else default_value

            new_rows = []
            missing_source = source_outlets[source_outlets["outlet_name"].isin(missing_names)]
            for outlet_name, outlet_rows in missing_source.groupby("outlet_name", sort=False):
                new_rows.append({
                    "outlet_name": outlet_name,
                    "area": first_non_empty(outlet_rows, "area"),
                    "kategori_tempat": first_non_empty(outlet_rows, "kategori_tempat", "Tidak Terkategorisasi"),
                    "sub_kategori_tempat": first_non_empty(outlet_rows, "sub_kategori_tempat", "Tidak Terkategorisasi"),
                    "tipe_tempat": first_non_empty(outlet_rows, "tipe_tempat", "Indoor"),
                })

            if new_rows:
                outlet_mapping = pd.concat([outlet_mapping, pd.DataFrame(new_rows)], ignore_index=True)
                outlet_mapping = outlet_mapping[required_cols].drop_duplicates("outlet_name", keep="last")
                outlet_mapping = outlet_mapping.sort_values("outlet_name").reset_index(drop=True)
                outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                try: cache_clear(load_app_data)
                except Exception: pass
                st.info("{} outlet dari database transaksi otomatis ditambahkan ke CRUD mapping.".format(len(new_rows)))

    crud_modes = ["Edit Outlet", "Add Outlet", "AI Suggest", "Master Data", "Delete"]
    try:
        crud_mode = st.radio("Mode CRUD Outlet", crud_modes, horizontal=True, key="crud_v2_mode")
    except TypeError:
        crud_mode = st.radio("Mode CRUD Outlet", crud_modes, key="crud_v2_mode")

    if crud_mode == "Edit Outlet":
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Outlet", f"{len(outlet_mapping):,}")
        with m2:
            st.metric("Area", f"{outlet_mapping['area'].replace('', np.nan).nunique():,}")
        with m3:
            st.metric("Tipe", f"{outlet_mapping['tipe_tempat'].replace('', np.nan).nunique():,}")

        f1, f2, f3, f4 = st.columns([2.2, 1.2, 1.2, 1.2])
        with f1:
            search = st.text_input("Search outlet", placeholder="Ketik nama outlet...", key="crud_v2_search")
        with f2:
            area_filter = st.selectbox("Area", ["Semua"] + safe_unique_str(outlet_mapping, "area"), key="crud_v2_area")
        with f3:
            kategori_filter = st.selectbox("Kategori", ["Semua"] + safe_unique_str(outlet_mapping, "kategori_tempat"), key="crud_v2_kategori")
        with f4:
            tipe_filter = st.selectbox("Tipe", ["Semua"] + safe_unique_str(outlet_mapping, "tipe_tempat"), key="crud_v2_tipe")

        visible = outlet_mapping.copy()
        if search:
            visible = visible[visible["outlet_name"].str.contains(search, case=False, na=False)]
        if area_filter != "Semua":
            visible = visible[visible["area"] == area_filter]
        if kategori_filter != "Semua":
            visible = visible[visible["kategori_tempat"] == kategori_filter]
        if tipe_filter != "Semua":
            visible = visible[visible["tipe_tempat"] == tipe_filter]

        st.caption("Edit area, kategori, sub kategori, dan tipe langsung di tabel. Outlet name dikunci agar identitas outlet tidak berubah tanpa sengaja.")

        if visible.empty:
            st.info("Tidak ada outlet yang cocok dengan filter.")
        else:
            editor_config = None
            if HAS_COLUMN_CONFIG:
                area_options = sorted(set(INDONESIA_AREAS) | set(safe_unique_str(outlet_mapping, "area")))
                kategori_options = sorted(set(KATEGORI_TEMPAT) | set(safe_unique_str(outlet_mapping, "kategori_tempat")))
                sub_options = sorted(set(SUB_KATEGORI_TEMPAT) | set(safe_unique_str(outlet_mapping, "sub_kategori_tempat")))
                tipe_options = sorted(set(["Indoor", "Outdoor", "Semi-Outdoor"]) | set(safe_unique_str(outlet_mapping, "tipe_tempat")))
                try:
                    editor_config = {
                        "_index": st.column_config.TextColumn("Outlet", width="large"),
                        "area": st.column_config.SelectboxColumn("Area", options=area_options, width="medium"),
                        "kategori_tempat": st.column_config.SelectboxColumn("Kategori", options=kategori_options, width="medium"),
                        "sub_kategori_tempat": st.column_config.SelectboxColumn("Sub Kategori", options=sub_options, width="medium"),
                        "tipe_tempat": st.column_config.SelectboxColumn("Tipe", options=tipe_options, width="small"),
                    }
                except Exception:
                    editor_config = None

            editor_key_seed = "|".join(visible["outlet_name"].astype(str).tolist())
            editor_key = "crud_v2_editor_" + hashlib.md5(editor_key_seed.encode("utf-8")).hexdigest()[:12]
            with st.form("crud_v2_edit_form"):
                if hasattr(st, "data_editor"):
                    editor_data = visible[required_cols].copy().set_index("outlet_name")
                    editor_data.index.name = "Outlet"
                    edited_visible = st.data_editor(
                        editor_data,
                        use_container_width=True,
                        hide_index=False,
                        height=table_height(len(editor_data), 300, DEFAULT_TABLE_MAX_HEIGHT),
                        num_rows="fixed",
                        column_config=editor_config,
                        key=editor_key,
                    )
                else:
                    edited_visible = visible.copy()
                    df_show(visible, use_container_width=True, hide_index=True, column_config=editor_config)
                    st.warning("Versi Streamlit ini belum mendukung edit langsung di tabel.")

                c_save, c_info = st.columns([1, 4])
                with c_save:
                    save_edit = st.form_submit_button("Save Changes", type="primary")
                with c_info:
                    st.caption(f"Menampilkan {len(visible):,} dari {len(outlet_mapping):,} outlet.")

            if save_edit:
                edited_visible = pd.DataFrame(edited_visible).reset_index()
                if "Outlet" in edited_visible.columns:
                    edited_visible = edited_visible.rename(columns={"Outlet": "outlet_name"})
                elif "index" in edited_visible.columns and "outlet_name" not in edited_visible.columns:
                    edited_visible = edited_visible.rename(columns={"index": "outlet_name"})
                edited_visible = edited_visible[required_cols].copy()
                edited_visible["outlet_name"] = edited_visible["outlet_name"].astype(str).str.strip()
                if edited_visible["outlet_name"].eq("").any():
                    st.error("Outlet name tidak boleh kosong.")
                elif edited_visible["outlet_name"].duplicated().any():
                    st.error("Ada outlet name duplikat di hasil edit.")
                else:
                    merged = outlet_mapping.set_index("outlet_name")
                    merged.update(edited_visible.set_index("outlet_name"))
                    merged = merged.reset_index()[required_cols].sort_values("outlet_name").reset_index(drop=True)
                    merged.to_csv(OUTLET_MAPPING_PATH, index=False)
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("Outlet mapping berhasil disimpan.")
                    rerun()

    if crud_mode == "Add Outlet":
        st.subheader("Add New Outlet")
        with st.form("crud_v2_add_form"):
            new_name = st.text_input("Outlet Name")
            c1, c2 = st.columns(2)
            with c1:
                new_area = st.selectbox("Area", INDONESIA_AREAS)
                new_sub = st.selectbox("Sub Kategori", SUB_KATEGORI_TEMPAT)
            with c2:
                new_kategori = st.selectbox("Kategori", KATEGORI_TEMPAT)
                new_tipe = st.selectbox("Tipe", ["Indoor", "Outdoor", "Semi-Outdoor"])
            if st.form_submit_button("Add Outlet"):
                new_name = new_name.strip()
                if not new_name:
                    st.error("Outlet name wajib diisi.")
                elif new_name in outlet_mapping["outlet_name"].values:
                    st.error("Outlet sudah ada.")
                else:
                    new_row = pd.DataFrame([{
                        "outlet_name": new_name,
                        "area": new_area,
                        "kategori_tempat": new_kategori,
                        "sub_kategori_tempat": new_sub,
                        "tipe_tempat": new_tipe,
                    }])
                    updated = pd.concat([outlet_mapping, new_row], ignore_index=True)
                    updated = updated[required_cols].sort_values("outlet_name").reset_index(drop=True)
                    updated.to_csv(OUTLET_MAPPING_PATH, index=False)
                    deleted_outlets = [x for x in load_deleted_outlets() if x != new_name]
                    save_deleted_outlets(deleted_outlets)
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("Outlet berhasil ditambahkan.")
                    rerun()

    if crud_mode == "AI Suggest":
        st.subheader("AI Suggest Outlet Mapping")
        st.caption("AI lokal membaca nama outlet untuk menebak area, kategori, sub kategori, dan tipe. Lo tetap bisa edit hasilnya sebelum apply.")

        ai_source = outlet_mapping.copy()
        ai_source["needs_ai"] = ai_source.apply(
            lambda r: suggest_outlet_metadata(r.get("outlet_name", ""), r.to_dict()).get("needs_update", False),
            axis=1,
        )
        only_needs = st.checkbox("Tampilkan yang belum lengkap saja", value=True, key="crud_ai_only_needs")
        min_conf = st.slider("Minimum confidence", min_value=0, max_value=100, value=55, step=5, key="crud_ai_min_conf")

        suggestions = []
        for _, row in ai_source.iterrows():
            suggestion = suggest_outlet_metadata(row.get("outlet_name", ""), row.to_dict())
            if only_needs and not suggestion["needs_update"]:
                continue
            if int(suggestion["confidence"]) < int(min_conf):
                continue
            suggestions.append({
                "apply": False,
                "outlet_name": suggestion["outlet_name"],
                "current_area": row.get("area", ""),
                "current_kategori": row.get("kategori_tempat", ""),
                "suggested_area": suggestion["suggested_area"],
                "suggested_kategori_tempat": suggestion["suggested_kategori_tempat"],
                "suggested_sub_kategori_tempat": suggestion["suggested_sub_kategori_tempat"],
                "suggested_tipe_tempat": suggestion["suggested_tipe_tempat"],
                "confidence": suggestion["confidence"],
                "reason": suggestion["reason"],
            })

        if not suggestions:
            st.info("Tidak ada outlet yang cocok dengan filter AI Suggest.")
        else:
            suggestion_df = pd.DataFrame(suggestions)
            st.info("{} rekomendasi ditemukan. Centang `apply`, edit hasil rekomendasi kalau perlu, lalu klik Apply.".format(len(suggestion_df)))

            ai_config = None
            if HAS_COLUMN_CONFIG:
                try:
                    ai_config = {
                        "apply": st.column_config.CheckboxColumn("Apply", width="small"),
                        "outlet_name": st.column_config.TextColumn("Outlet", width="large"),
                        "current_area": st.column_config.TextColumn("Area Saat Ini", width="medium"),
                        "current_kategori": st.column_config.TextColumn("Kategori Saat Ini", width="medium"),
                        "suggested_area": st.column_config.SelectboxColumn("Area AI", options=sorted(set(INDONESIA_AREAS) | set(safe_unique_str(outlet_mapping, "area")) | {"Lainnya"}), width="medium"),
                        "suggested_kategori_tempat": st.column_config.SelectboxColumn("Kategori AI", options=sorted(set(KATEGORI_TEMPAT) | {"Lainnya"}), width="medium"),
                        "suggested_sub_kategori_tempat": st.column_config.SelectboxColumn("Sub Kategori AI", options=sorted(set(SUB_KATEGORI_TEMPAT) | {"Lainnya"}), width="medium"),
                        "suggested_tipe_tempat": st.column_config.SelectboxColumn("Tipe AI", options=["Indoor", "Outdoor", "Semi-Outdoor"], width="small"),
                        "confidence": st.column_config.NumberColumn("Confidence", min_value=0, max_value=100, width="small"),
                        "reason": st.column_config.TextColumn("Reason", width="large"),
                    }
                except Exception:
                    ai_config = None

            if hasattr(st, "data_editor"):
                edited_suggestion = st.data_editor(
                    suggestion_df,
                    use_container_width=True,
                    hide_index=True,
                    height=table_height(len(suggestion_df), 300, DEFAULT_TABLE_MAX_HEIGHT),
                    num_rows="fixed",
                    disabled=["outlet_name", "current_area", "current_kategori", "confidence", "reason"],
                    column_config=ai_config,
                    key="crud_ai_suggest_editor",
                )
            else:
                edited_suggestion = suggestion_df.copy()
                df_show(suggestion_df, use_container_width=True, hide_index=True)
                st.warning("Versi Streamlit ini belum mendukung edit langsung di tabel AI Suggest.")

            selected_ai = pd.DataFrame(edited_suggestion)
            selected_ai = selected_ai[selected_ai["apply"] == True].copy()
            if not selected_ai.empty:
                st.warning("{} outlet akan diupdate dari rekomendasi AI.".format(len(selected_ai)))
                confirm_ai = st.text_input("Ketik APPLY untuk menyimpan rekomendasi AI", key="crud_ai_confirm")
                if st.button("Apply AI Suggestions", type="primary", key="crud_ai_apply"):
                    if confirm_ai != "APPLY":
                        st.error("Konfirmasi belum benar. Ketik APPLY untuk menyimpan.")
                        return
                    updated = outlet_mapping.set_index("outlet_name")
                    for _, row in selected_ai.iterrows():
                        name = str(row["outlet_name"])
                        if name in updated.index:
                            updated.loc[name, "area"] = str(row["suggested_area"])
                            updated.loc[name, "kategori_tempat"] = str(row["suggested_kategori_tempat"])
                            updated.loc[name, "sub_kategori_tempat"] = str(row["suggested_sub_kategori_tempat"])
                            updated.loc[name, "tipe_tempat"] = str(row["suggested_tipe_tempat"])
                    updated = updated.reset_index()[required_cols].sort_values("outlet_name").reset_index(drop=True)
                    updated.to_csv(OUTLET_MAPPING_PATH, index=False)
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("Rekomendasi AI berhasil disimpan. Cek lagi di tab Edit Outlet kalau mau koreksi manual.")
                    rerun()

    if crud_mode == "Master Data":
        st.subheader("Master Data")
        st.caption("Edit nilai langsung di tabel, centang Delete untuk hapus, atau isi Tambah baru. Perubahan master data dipakai sebagai opsi di Add/Edit/AI Suggest.")
        c1, c2, c3 = st.columns(3)
        with c1:
            render_master_data_editor("Area", "areas", INDONESIA_AREAS)
        with c2:
            render_master_data_editor("Kategori", "kategori_tempat", KATEGORI_TEMPAT)
        with c3:
            render_master_data_editor("Sub Kategori", "sub_kategori_tempat", SUB_KATEGORI_TEMPAT)

    if crud_mode == "Delete":
        st.subheader("Delete Outlet")
        st.caption("Centang outlet yang mau dihapus dari mapping CRUD. Data transaksi historis tidak ikut dihapus.")

        delete_source = outlet_mapping.copy().sort_values("outlet_name").reset_index(drop=True)
        saved_delete = set(st.session_state.get("crud_v2_delete_selected", []))
        delete_source.insert(0, "delete", delete_source["outlet_name"].astype(str).isin(saved_delete))
        delete_cols = ["delete", "outlet_name", "area", "kategori_tempat", "tipe_tempat"]
        delete_source = delete_source[[c for c in delete_cols if c in delete_source.columns]]

        if hasattr(st, "data_editor"):
            delete_config = None
            if HAS_COLUMN_CONFIG:
                try:
                    delete_config = {
                        "delete": st.column_config.CheckboxColumn("Delete", width="small"),
                        "outlet_name": st.column_config.TextColumn("Outlet", width="large"),
                        "area": st.column_config.TextColumn("Area", width="medium"),
                        "kategori_tempat": st.column_config.TextColumn("Kategori", width="medium"),
                        "tipe_tempat": st.column_config.TextColumn("Tipe", width="small"),
                    }
                except Exception:
                    delete_config = None
            edited_delete = st.data_editor(
                delete_source,
                use_container_width=True,
                hide_index=True,
                height=table_height(len(delete_source), 300, DEFAULT_TABLE_MAX_HEIGHT),
                num_rows="fixed",
                disabled=[c for c in delete_source.columns if c != "delete"],
                column_config=delete_config,
                key="crud_v2_delete_editor",
            )
            edited_delete_df = pd.DataFrame(edited_delete)
            delete_flags = edited_delete_df["delete"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
            outlets_to_delete = edited_delete_df.loc[delete_flags, "outlet_name"].dropna().astype(str).tolist()
        else:
            df_show(delete_source.drop(columns=["delete"]), use_container_width=True, hide_index=True)
            st.warning("Versi Streamlit ini belum mendukung checklist tabel. Pakai pilihan manual di bawah.")
            outlets_to_delete = st.multiselect(
                "Pilih outlet",
                outlet_mapping["outlet_name"].tolist(),
                default=st.session_state.get("crud_v2_delete_selected", []),
            )

        c_set, c_clear = st.columns([1.2, 4])
        with c_set:
            if st.button("Lock Selection", key="crud_v2_delete_set"):
                st.session_state["crud_v2_delete_selected"] = outlets_to_delete
                st.success("{} outlet dipilih untuk delete.".format(len(outlets_to_delete)))
        with c_clear:
            if st.button("Clear Selection", key="crud_v2_delete_clear"):
                st.session_state["crud_v2_delete_selected"] = []
                rerun()

        selected_for_delete = st.session_state.get("crud_v2_delete_selected", outlets_to_delete)
        if outlets_to_delete and outlets_to_delete != selected_for_delete:
            selected_for_delete = outlets_to_delete

        if selected_for_delete:
            st.warning(f"{len(selected_for_delete)} outlet akan dihapus dari mapping CRUD.")
            df_show(
                outlet_mapping[outlet_mapping["outlet_name"].isin(selected_for_delete)][["outlet_name", "area", "kategori_tempat", "tipe_tempat"]],
                use_container_width=True,
                hide_index=True,
            )
            confirm_delete = st.text_input("Ketik DELETE untuk konfirmasi hapus", key="crud_v2_delete_confirm")
            if st.button("Confirm Delete", key="crud_v2_delete", type="primary"):
                if confirm_delete != "DELETE":
                    st.error("Konfirmasi belum benar. Ketik DELETE untuk menghapus.")
                    return
                updated = outlet_mapping[~outlet_mapping["outlet_name"].isin(selected_for_delete)].copy()
                updated.to_csv(OUTLET_MAPPING_PATH, index=False)
                deleted_now = set(load_deleted_outlets())
                deleted_now.update(str(x).strip() for x in selected_for_delete if str(x).strip())
                save_deleted_outlets(list(deleted_now))
                try: cache_clear(load_app_data)
                except Exception: pass
                st.session_state["crud_v2_delete_selected"] = []
                st.success("Outlet berhasil dihapus dari mapping CRUD.")
                rerun()


def build_ai_trend_insights(base: pd.DataFrame, periods: List[str], config: Config) -> Dict[str, object]:
    """Generate local AI-style analysis from the selected trend data."""
    if base.empty or not periods:
        return {
            "summary": ["Data pada range periode ini belum cukup untuk dianalisis."],
            "findings": [],
            "actions": ["Coba perluas range periode atau cek filter sidebar."],
            "decisions": [],
            "risks": [],
            "experiments": [],
            "priority_outlets": pd.DataFrame(),
        }

    latest_period = periods[-1]
    previous_period = periods[-2] if len(periods) > 1 else None
    latest_df = base[base["periode"].astype(str) == latest_period].copy()
    previous_df = base[base["periode"].astype(str) == previous_period].copy() if previous_period else pd.DataFrame()

    def sum_col(frame, col):
        return float(pd.to_numeric(frame.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

    def pct_change(now, prev):
        return ((now - prev) / prev * 100) if prev > 0 else None

    def fmt_pct(value):
        return "-" if value is None or pd.isna(value) else f"{value:+.1f}%"

    monthly = (
        base.groupby("periode", as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            foto_qty=("foto_qty", "sum"),
            print_qty=("print_qty", "sum"),
            outlet_count=("outlet_name", "nunique"),
        )
    )
    monthly["conversion_rate"] = np.where(monthly["foto_qty"] > 0, monthly["print_qty"] / monthly["foto_qty"] * 100, 0)
    monthly["periode"] = pd.Categorical(monthly["periode"].astype(str), categories=periods, ordered=True)
    monthly = monthly.sort_values("periode")
    monthly["revenue_change"] = monthly["total_revenue"].diff()
    monthly["conversion_change"] = monthly["conversion_rate"].diff()

    latest_revenue = sum_col(latest_df, "total_revenue")
    previous_revenue = sum_col(previous_df, "total_revenue")
    revenue_delta = pct_change(latest_revenue, previous_revenue)
    avg_monthly = float(monthly["total_revenue"].mean()) if not monthly.empty else 0.0
    best_month = monthly.sort_values("total_revenue", ascending=False).head(1)
    weakest_month = monthly.sort_values("total_revenue", ascending=True).head(1)

    all_outlets = set(base["outlet_name"].dropna().astype(str).str.strip())
    latest_outlets = set(latest_df["outlet_name"].dropna().astype(str).str.strip())
    inactive_count = len(all_outlets - latest_outlets)

    area_summary = pd.DataFrame()
    if "area" in base.columns:
        area_summary = (
            base.groupby("area", as_index=False)
            .agg(total_revenue=("total_revenue", "sum"), outlet_count=("outlet_name", "nunique"))
        )
        area_summary["revenue_per_outlet"] = area_summary["total_revenue"] / area_summary["outlet_count"].replace(0, np.nan)
        area_summary = area_summary.sort_values("total_revenue", ascending=False)

    category_summary = pd.DataFrame()
    if "kategori_tempat" in base.columns:
        category_summary = (
            base.groupby("kategori_tempat", as_index=False)
            .agg(total_revenue=("total_revenue", "sum"), outlet_count=("outlet_name", "nunique"))
            .sort_values("total_revenue", ascending=False)
        )

    top_area = area_summary.head(1).iloc[0] if not area_summary.empty else None
    low_area = area_summary[area_summary["total_revenue"] > 0].tail(1).iloc[0] if not area_summary.empty and (area_summary["total_revenue"] > 0).any() else None
    top_category = category_summary.head(1).iloc[0] if not category_summary.empty else None

    outlet_period = (
        base.groupby(["outlet_name", "periode"], as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            foto_qty=("foto_qty", "sum"),
            print_qty=("print_qty", "sum"),
        )
    )
    outlet_pivot = outlet_period.pivot_table(index="outlet_name", columns="periode", values="total_revenue", aggfunc="sum", fill_value=0)
    movers = pd.DataFrame()
    if latest_period in outlet_pivot.columns:
        movers = pd.DataFrame({"outlet_name": outlet_pivot.index, "latest_revenue": outlet_pivot[latest_period].values})
        if previous_period and previous_period in outlet_pivot.columns:
            movers["previous_revenue"] = outlet_pivot[previous_period].values
        else:
            movers["previous_revenue"] = 0.0
        movers["growth_value"] = movers["latest_revenue"] - movers["previous_revenue"]
        movers = movers.sort_values("growth_value", ascending=False)

    outlet_summary = (
        base.groupby("outlet_name", as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            avg_revenue=("total_revenue", "mean"),
            foto_qty=("foto_qty", "sum"),
            print_qty=("print_qty", "sum"),
            active_months=("periode", "nunique"),
        )
    )
    outlet_summary["conversion_rate"] = np.where(outlet_summary["foto_qty"] > 0, outlet_summary["print_qty"] / outlet_summary["foto_qty"] * 100, 0)
    outlet_summary["revenue_per_active_month"] = outlet_summary["total_revenue"] / outlet_summary["active_months"].replace(0, np.nan)
    outlet_summary["status_ai"] = "Monitor"
    outlet_summary.loc[(outlet_summary["total_revenue"] > 0) & (outlet_summary["conversion_rate"] < 12), "status_ai"] = "Traffic ada, conversion rendah"
    outlet_summary.loc[(outlet_summary["revenue_per_active_month"] >= outlet_summary["revenue_per_active_month"].quantile(0.80)), "status_ai"] = "Scale / benchmark"
    outlet_summary.loc[outlet_summary["active_months"] <= max(1, len(periods) // 4), "status_ai"] = "Seasonal / belum stabil"
    priority_outlets = outlet_summary.sort_values(
        ["total_revenue", "conversion_rate", "active_months"],
        ascending=[False, True, False],
    ).head(12).copy()

    summary = [
        "Range analisis: {} sampai {} dengan {} periode data.".format(periods[0], periods[-1], len(periods)),
        "Omzet periode terakhir {} adalah {}, dibanding periode sebelumnya: {}.".format(
            latest_period,
            config.format_currency(latest_revenue),
            fmt_pct(revenue_delta),
        ),
        "Rata-rata omzet bulanan pada range ini sekitar {}.".format(config.format_currency(avg_monthly)),
    ]

    if not best_month.empty and not weakest_month.empty:
        summary.append(
            "Bulan terkuat adalah {} ({}) dan bulan terlemah adalah {} ({}).".format(
                str(best_month.iloc[0]["periode"]),
                config.format_currency(float(best_month.iloc[0]["total_revenue"])),
                str(weakest_month.iloc[0]["periode"]),
                config.format_currency(float(weakest_month.iloc[0]["total_revenue"])),
            )
        )

    findings = []
    if top_area is not None:
        findings.append("Area terbesar adalah {} dengan kontribusi omzet {} dari {} outlet.".format(
            top_area["area"], config.format_currency(float(top_area["total_revenue"])), int(top_area["outlet_count"])
        ))
    if low_area is not None and top_area is not None and low_area["area"] != top_area["area"]:
        findings.append("Area yang perlu dicek lebih lanjut: {} karena omzetnya paling rendah di antara area yang masih menghasilkan.".format(low_area["area"]))
    if top_category is not None:
        findings.append("Kategori paling kuat saat ini adalah {} dengan omzet {}.".format(
            top_category["kategori_tempat"], config.format_currency(float(top_category["total_revenue"]))
        ))
    if inactive_count > 0:
        findings.append("{} outlet tidak aktif pada periode terakhir di range ini. Ini perlu dipisahkan dari outlet aktif agar ranking lebih fair.".format(inactive_count))
    if not movers.empty:
        top_up = movers.head(1).iloc[0]
        top_down = movers.tail(1).iloc[0]
        findings.append("Outlet dengan kenaikan nominal terbesar: {} ({}) dibanding periode sebelumnya.".format(
            top_up["outlet_name"], config.format_currency(float(top_up["growth_value"]))
        ))
        if float(top_down["growth_value"]) < 0:
            findings.append("Outlet dengan penurunan terdalam: {} ({}) dibanding periode sebelumnya.".format(
                top_down["outlet_name"], config.format_currency(float(top_down["growth_value"]))
            ))

    actions = []
    if revenue_delta is not None and revenue_delta < -10:
        actions.append("Prioritaskan audit outlet yang turun pada periode terakhir, terutama penyebab traffic, conversion, dan stok/operasional.")
    elif revenue_delta is not None and revenue_delta > 10:
        actions.append("Duplikasi pola dari outlet/area yang naik: cek promo, placement, timing event, dan operator yang bertugas.")
    else:
        actions.append("Karena omzet relatif stabil, fokuskan eksperimen pada outlet dengan conversion rendah tetapi traffic foto tinggi.")
    if inactive_count > 0:
        actions.append("Buat label operasional untuk outlet tidak aktif: seasonal/event selesai, pending buka, atau perlu follow-up partner.")
    if top_area is not None:
        actions.append("Gunakan area {} sebagai benchmark untuk area lain, tapi bandingkan dengan range periode yang sama agar tidak bias outlet lama.".format(top_area["area"]))
    actions.append("Untuk keputusan ekspansi, pakai metrik omzet per outlet dan conversion, bukan total omzet saja.")

    decisions = []
    risks = []
    experiments = []
    recent_months = monthly.tail(min(3, len(monthly)))
    recent_revenue_slope = float(recent_months["revenue_change"].fillna(0).sum()) if not recent_months.empty else 0.0
    recent_conv_slope = float(recent_months["conversion_change"].fillna(0).sum()) if not recent_months.empty else 0.0

    if revenue_delta is not None and revenue_delta > 15 and recent_revenue_slope > 0:
        decisions.append("Mode keputusan: offense. Ada momentum naik, pilih 3-5 outlet/area terbaik untuk jadi benchmark SOP dan dorong scale.")
    elif revenue_delta is not None and revenue_delta < -15:
        decisions.append("Mode keputusan: defense. Tahan ekspansi yang belum urgent, audit outlet turun, dan cari penyebab drop bulan terakhir.")
    else:
        decisions.append("Mode keputusan: selective growth. Jangan pukul rata; pilih outlet dengan omzet stabil dan conversion sehat untuk ekspansi kecil.")

    if inactive_count > max(5, len(all_outlets) * 0.25):
        risks.append("Banyak outlet tidak aktif di periode terakhir. Ranking total bisa bias kalau outlet event/seasonal tidak dipisahkan.")
    if recent_conv_slope < -2:
        risks.append("Conversion beberapa bulan terakhir melemah. Ada risiko traffic bagus tidak berubah jadi print/revenue.")
    if top_area is not None and len(area_summary) > 1:
        top_share = float(top_area["total_revenue"]) / float(area_summary["total_revenue"].sum()) if float(area_summary["total_revenue"].sum()) > 0 else 0
        if top_share > 0.45:
            risks.append("Omzet terlalu terkonsentrasi di satu area. Kalau area utama turun, total bisnis ikut rentan.")
    if not risks:
        risks.append("Tidak ada risiko ekstrem dari range ini, tapi tetap cek outlet baru/event karena datanya belum stabil.")

    experiments.append("Pilih 5 outlet omzet tinggi tetapi conversion di bawah median, lalu test script upsell/operator selama 2 minggu.")
    experiments.append("Bandingkan outlet indoor vs outdoor pada range yang sama untuk menentukan placement dan jam operasional terbaik.")
    experiments.append("Untuk outlet event/seasonal, pisahkan target KPI dari outlet permanen agar keputusan tidak bias.")

    return {
        "summary": summary,
        "findings": findings,
        "actions": actions,
        "decisions": decisions,
        "risks": risks,
        "experiments": experiments,
        "priority_outlets": priority_outlets,
    }


def render_ai_insights(insights: Dict[str, object], config: Config):
    st.markdown("**Decision Brief**")
    for item in insights.get("decisions", []):
        st.success(item)

    st.markdown("**Executive Summary**")
    for item in insights.get("summary", []):
        st.markdown(f"- {item}")

    st.markdown("**Temuan Penting**")
    findings = insights.get("findings", [])
    if findings:
        for item in findings:
            st.markdown(f"- {item}")
    else:
        st.info("Belum ada temuan kuat dari range periode ini.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Rekomendasi Aksi**")
        for idx, item in enumerate(insights.get("actions", []), start=1):
            st.markdown(f"{idx}. {item}")
    with c2:
        st.markdown("**Risiko yang Perlu Dijaga**")
        for item in insights.get("risks", []):
            st.warning(item)

    st.markdown("**Eksperimen yang Bisa Dicoba**")
    for idx, item in enumerate(insights.get("experiments", []), start=1):
        st.markdown(f"{idx}. {item}")

    priority_outlets = insights.get("priority_outlets", pd.DataFrame())
    if isinstance(priority_outlets, pd.DataFrame) and not priority_outlets.empty:
        st.markdown("**Outlet Prioritas untuk Dibahas**")
        priority_display = priority_outlets.copy()
        for col in ["total_revenue", "avg_revenue", "revenue_per_active_month"]:
            if col in priority_display.columns:
                priority_display[col] = priority_display[col].fillna(0).apply(config.format_currency)
        if "conversion_rate" in priority_display.columns:
            priority_display["conversion_rate"] = priority_display["conversion_rate"].apply(lambda x: f"{x:.1f}%")
        priority_display = priority_display.rename(columns={
            "outlet_name": "Outlet",
            "total_revenue": "Total Omzet",
            "avg_revenue": "Avg Omzet",
            "foto_qty": "Foto",
            "print_qty": "Print",
            "active_months": "Bulan Aktif",
            "conversion_rate": "Conversion",
            "revenue_per_active_month": "Omzet / Bulan Aktif",
            "status_ai": "AI Label",
        })
        render_mobile_cards(
            priority_display,
            "Outlet",
            [
                ("Total Omzet", "Total Omzet"),
                ("Conversion", "Conversion"),
                ("Bulan Aktif", "Bulan Aktif"),
                ("Omzet / Bulan", "Omzet / Bulan Aktif"),
            ],
            status_col="AI Label",
            max_rows=12,
        )
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(priority_display, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)


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


def show_trend_analysis_v2(df, config, processor, viz):
    st.title("Analisis Trend Penjualan")
    if df.empty:
        st.error("Data tidak tersedia.")
        return

    base = df.copy(deep=True)
    for col in ["total_revenue", "foto_qty", "unlock_qty", "print_qty", "conversion_rate"]:
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0.0)
    base["periode"] = base["periode"].astype(str)

    periods = _sort_periods_str(base["periode"].dropna().astype(str).unique().tolist()) if "periode" in base.columns else []
    if not periods:
        st.error("Data periode tidak tersedia.")
        return

    default_start_idx = max(0, len(periods) - 12)
    default_end_idx = len(periods) - 1
    st.markdown("#### Range Periode Analisis")
    r1, r2, r3 = st.columns([1, 1, 2])
    with r1:
        start_period = st.selectbox("Periode Mulai", periods, index=default_start_idx, key="trend_period_start")
    with r2:
        end_period = st.selectbox("Periode Akhir", periods, index=default_end_idx, key="trend_period_end")

    start_idx = periods.index(start_period)
    end_idx = periods.index(end_period)
    if start_idx > end_idx:
        st.error("Periode mulai tidak boleh lebih baru dari periode akhir.")
        return

    selected_periods = periods[start_idx:end_idx + 1]
    base = base[base["periode"].isin(selected_periods)].copy()
    periods = selected_periods
    with r3:
        st.info("Analisis memakai {} periode: {} sampai {}.".format(len(periods), start_period, end_period))

    latest_period = periods[-1] if periods else None
    previous_period = periods[-2] if len(periods) > 1 else None
    latest_df = base[base["periode"] == latest_period].copy() if latest_period else base.copy()
    previous_df = base[base["periode"] == previous_period].copy() if previous_period else pd.DataFrame()
    ai_insights = build_ai_trend_insights(base.copy(), periods, config)

    def _sum(frame, col):
        return float(pd.to_numeric(frame.get(col, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

    def _conversion(frame):
        foto = _sum(frame, "foto_qty")
        printed = _sum(frame, "print_qty")
        return (printed / foto * 100) if foto > 0 else 0.0

    revenue_now = _sum(latest_df, "total_revenue")
    revenue_prev = _sum(previous_df, "total_revenue")
    revenue_delta = ((revenue_now - revenue_prev) / revenue_prev * 100) if revenue_prev > 0 else None
    conv_now = _conversion(latest_df)
    conv_prev = _conversion(previous_df)
    conv_delta = conv_now - conv_prev if previous_period else None

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Periode Terbaru", latest_period or "-")
    with k2:
        st.metric("Omzet", config.format_currency(revenue_now), delta=(f"{revenue_delta:+.1f}%" if revenue_delta is not None else None))
    with k3:
        st.metric("Outlet Aktif", f"{latest_df['outlet_name'].nunique():,}")
    with k4:
        st.metric("Conversion", f"{conv_now:.1f}%", delta=(f"{conv_delta:+.1f}pp" if conv_delta is not None else None))

    monthly = (
        base.groupby("periode", as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            foto_qty=("foto_qty", "sum"),
            unlock_qty=("unlock_qty", "sum"),
            print_qty=("print_qty", "sum"),
            outlet_count=("outlet_name", "nunique"),
        )
    )
    monthly["conversion_rate"] = np.where(monthly["foto_qty"] > 0, monthly["print_qty"] / monthly["foto_qty"] * 100, 0)
    monthly["periode"] = pd.Categorical(monthly["periode"], categories=periods, ordered=True)
    monthly = monthly.sort_values("periode")

    tab_overview, tab_segments, tab_outlets, tab_heatmap, tab_ai = st.tabs(["Overview", "Area & Category", "Outlet Movers", "Heatmap", "AI Insight"])

    with tab_overview:
        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.line(monthly, x="periode", y="total_revenue", markers=True, title="Monthly Revenue Trend")
            fig.update_traces(hovertemplate="%{x}<br>Revenue: Rp %{y:,.0f}<extra></extra>")
            fig.update_layout(height=420, yaxis_title="Revenue", xaxis_title="Periode")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig_conv = px.line(monthly, x="periode", y="conversion_rate", markers=True, title="Conversion Trend")
            fig_conv.update_traces(hovertemplate="%{x}<br>Conversion: %{y:.1f}%<extra></extra>")
            fig_conv.update_layout(height=420, yaxis_title="Conversion %", xaxis_title="Periode")
            st.plotly_chart(fig_conv, use_container_width=True)

        monthly_display = monthly.copy()
        monthly_display["total_revenue"] = monthly_display["total_revenue"].apply(config.format_currency)
        monthly_display["conversion_rate"] = monthly_display["conversion_rate"].apply(lambda x: f"{x:.1f}%")
        monthly_display = monthly_display.rename(columns={
            "periode": "Periode",
            "total_revenue": "Omzet",
            "foto_qty": "Foto",
            "unlock_qty": "Unlock",
            "print_qty": "Print",
            "outlet_count": "Outlet",
            "conversion_rate": "Conversion",
        })
        render_mobile_cards(
            monthly_display,
            "Periode",
            [("Omzet", "Omzet"), ("Outlet", "Outlet"), ("Foto", "Foto"), ("Print", "Print"), ("Conversion", "Conversion")],
            max_rows=12,
        )
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(monthly_display, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab_segments:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(viz.create_area_analysis_chart(base), use_container_width=True)
        with c2:
            st.plotly_chart(viz.create_indoor_outdoor_comparison(base), use_container_width=True)

        c3, c4 = st.columns(2)
        with c3:
            area_summary = processor.aggregate_by_area(base.copy()).reset_index()
            if not area_summary.empty:
                area_summary["revenue_per_outlet"] = area_summary["total_revenue"] / area_summary["outlet_count"].replace(0, np.nan)
                area_summary["total_revenue"] = area_summary["total_revenue"].apply(config.format_currency)
                area_summary["revenue_per_outlet"] = area_summary["revenue_per_outlet"].fillna(0).apply(config.format_currency)
            st.subheader("Summary by Area")
            df_show(area_summary, use_container_width=True, hide_index=True)
        with c4:
            kategori_summary = processor.aggregate_by_kategori(base.copy()).reset_index()
            if not kategori_summary.empty:
                kategori_summary["revenue_per_outlet"] = kategori_summary["total_revenue"] / kategori_summary["outlet_count"].replace(0, np.nan)
                kategori_summary["total_revenue"] = kategori_summary["total_revenue"].apply(config.format_currency)
                kategori_summary["revenue_per_outlet"] = kategori_summary["revenue_per_outlet"].fillna(0).apply(config.format_currency)
            st.subheader("Summary by Category")
            df_show(kategori_summary, use_container_width=True, hide_index=True)

        st.plotly_chart(viz.create_kategori_analysis(base), use_container_width=True)

    with tab_outlets:
        if latest_period and not latest_df.empty:
            profit_source = latest_df.groupby("outlet_name", as_index=False).agg(
                total_revenue=("total_revenue", "sum"),
                foto_qty=("foto_qty", "sum"),
                unlock_qty=("unlock_qty", "sum"),
                print_qty=("print_qty", "sum"),
            )
            mapping_profit = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()
            mapping_profit = apply_sharing_to_mapping(mapping_profit, latest_period)
            profit_cols = [
                "outlet_name", "area", "partner_share", "broker_share",
                "sharing_bagi_hasil", "monthly_rent", "minimum_payment",
            ]
            if not mapping_profit.empty and "outlet_name" in mapping_profit.columns:
                profit_source = profit_source.merge(
                    mapping_profit[[c for c in profit_cols if c in mapping_profit.columns]],
                    on="outlet_name",
                    how="left",
                )
            profit_source = add_profit_columns(profit_source)
            top_profit = profit_source.sort_values("estimasi_profit_difotoin", ascending=False).head(10).copy()
            if not top_profit.empty:
                st.subheader(f"Outlet Paling Menguntungkan untuk Difotoin - {latest_period}")
                show_profit = top_profit[[
                    c for c in [
                        "outlet_name", "area", "basis_bagi_hasil", "sharing_bagi_hasil",
                        "pendapatan_operator", "monthly_rent", "estimasi_profit_difotoin",
                        "foto_qty", "unlock_qty", "print_qty",
                    ] if c in top_profit.columns
                ]].copy()
                for col in ["basis_bagi_hasil", "pendapatan_operator", "monthly_rent", "estimasi_profit_difotoin"]:
                    if col in show_profit.columns:
                        show_profit[col] = show_profit[col].apply(lambda x: config.format_currency(float(x)) if pd.notna(x) and float(x) > 0 else "-")
                if "sharing_bagi_hasil" in show_profit.columns:
                    show_profit["sharing_bagi_hasil"] = show_profit["sharing_bagi_hasil"].apply(lambda x: "-" if pd.isna(x) else f"{float(x)*100:.1f}%")
                show_profit = show_profit.rename(columns={
                    "outlet_name": "Outlet",
                    "area": "Area",
                    "basis_bagi_hasil": "Basis Bagi Hasil",
                    "sharing_bagi_hasil": "Share Difotoin",
                    "pendapatan_operator": "Bagi Hasil Difotoin",
                    "monthly_rent": "Monthly Rent",
                    "estimasi_profit_difotoin": "Estimasi Profit",
                    "foto_qty": "Foto",
                    "unlock_qty": "Unlock",
                    "print_qty": "Print",
                })
                df_show(show_profit, use_container_width=True, hide_index=True, height=table_height(len(show_profit), 240, 420))

        outlet_period = (
            base.groupby(["outlet_name", "periode"], as_index=False)
            .agg(total_revenue=("total_revenue", "sum"), foto_qty=("foto_qty", "sum"), print_qty=("print_qty", "sum"))
        )
        outlet_pivot = outlet_period.pivot_table(index="outlet_name", columns="periode", values="total_revenue", aggfunc="sum", fill_value=0)
        if latest_period and latest_period in outlet_pivot.columns:
            movers = pd.DataFrame({"outlet_name": outlet_pivot.index, "latest_revenue": outlet_pivot[latest_period].values})
            if previous_period and previous_period in outlet_pivot.columns:
                movers["previous_revenue"] = outlet_pivot[previous_period].values
                movers["growth_value"] = movers["latest_revenue"] - movers["previous_revenue"]
                movers["growth_pct"] = np.where(movers["previous_revenue"] > 0, movers["growth_value"] / movers["previous_revenue"] * 100, np.nan)
            else:
                movers["previous_revenue"] = 0.0
                movers["growth_value"] = movers["latest_revenue"]
                movers["growth_pct"] = np.nan

            top_latest = movers.sort_values("latest_revenue", ascending=False).head(15).copy()
            top_up = movers.sort_values("growth_value", ascending=False).head(10).copy()
            top_down = movers.sort_values("growth_value", ascending=True).head(10).copy()

            for table in [top_latest, top_up, top_down]:
                table["latest_revenue"] = table["latest_revenue"].apply(config.format_currency)
                table["previous_revenue"] = table["previous_revenue"].apply(config.format_currency)
                table["growth_value"] = table["growth_value"].apply(config.format_currency)
                table["growth_pct"] = table["growth_pct"].apply(lambda x: "-" if pd.isna(x) else f"{x:+.1f}%")

            c1, c2 = st.columns(2)
            with c1:
                st.subheader(f"Top Outlet {latest_period}")
                render_mobile_cards(top_latest, "outlet_name", [("Omzet terbaru", "latest_revenue"), ("Omzet sebelumnya", "previous_revenue"), ("Growth", "growth_value"), ("Growth %", "growth_pct")], max_rows=10)
                st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
                df_show(top_latest, use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.subheader("Biggest Growth")
                render_mobile_cards(top_up, "outlet_name", [("Omzet terbaru", "latest_revenue"), ("Omzet sebelumnya", "previous_revenue"), ("Growth", "growth_value"), ("Growth %", "growth_pct")], max_rows=10)
                st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
                df_show(top_up, use_container_width=True, hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
            st.subheader("Needs Attention")
            render_mobile_cards(top_down, "outlet_name", [("Omzet terbaru", "latest_revenue"), ("Omzet sebelumnya", "previous_revenue"), ("Growth", "growth_value"), ("Growth %", "growth_pct")], max_rows=10)
            st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
            df_show(top_down, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Data outlet per periode belum cukup untuk menghitung movers.")

    with tab_heatmap:
        st.plotly_chart(viz.create_heatmap(base), use_container_width=True)
        st.caption("Heatmap membantu melihat kombinasi area dan kategori yang paling kuat atau perlu diperbaiki.")

    with tab_ai:
        st.subheader("AI Insight")
        st.caption("Analisis otomatis dari data dan filter periode yang sedang dipilih. Fokusnya membantu keputusan founder, bukan hanya membaca chart.")
        render_ai_insights(ai_insights, config)


def show_trend_analysis(df, config, processor, viz):
    st.title("📊 Analisis Trend Penjualan")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    st.subheader("🗺️ Analisis per Area"); st.plotly_chart(viz.create_area_analysis_chart(df), use_container_width=True)
    st.subheader("🏢 Analisis per Kategori Tempat"); st.plotly_chart(viz.create_kategori_analysis(df), use_container_width=True)
    st.subheader("🏠 Indoor vs Outdoor Analysis"); st.plotly_chart(viz.create_indoor_outdoor_comparison(df), use_container_width=True)
    st.subheader("🔥 Performance Heatmap"); st.plotly_chart(viz.create_heatmap(df), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1: st.subheader("📋 Summary by Area"); df_show(processor.aggregate_by_area(df.copy(deep=True)), use_container_width=True)
    with c2: st.subheader("📋 Summary by Category"); df_show(processor.aggregate_by_kategori(df.copy(deep=True)), use_container_width=True)

def show_conversion_analysis(df, config, processor, viz):
    st.title("🔄 Analisis Konversi & Awareness")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    base = df.copy(deep=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("📸➡️🖨️ Foto to Print", f"{base['conversion_rate'].mean():.1f}%")
    with c2:
        unlock_sum = pd.to_numeric(base.get('unlock_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        print_sum  = pd.to_numeric(base.get('print_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        rate = (print_sum/unlock_sum*100) if unlock_sum>0 else 0
        st.metric("🔓➡️🖨️ Unlock to Print", f"{rate:.1f}%")
    with c3:
        foto_sum = pd.to_numeric(base.get('foto_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        print_sum = pd.to_numeric(base.get('print_qty', pd.Series(dtype=int)), errors="coerce").fillna(0).sum()
        over = (print_sum/foto_sum*100) if foto_sum>0 else 0
        st.metric("🎯 Overall Conversion", f"{over:.1f}%")
    st.subheader("🔄 Conversion Funnel"); st.plotly_chart(viz.create_conversion_funnel(base), use_container_width=True)
    st.subheader("📊 Conversion Rate by Outlet")
    a,b = st.columns(2)
    with a:
        st.write("**🟢 High Conversion Outlets (>25%)**")
        hi = base[base['conversion_rate']>25].sort_values('conversion_rate', ascending=False)
        if not hi.empty:
            hi_display = hi[['outlet_name','conversion_rate','total_revenue']].copy()
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
        lo = base[base['conversion_rate']<15].sort_values('conversion_rate', ascending=True)
        if not lo.empty:
            lo_display = lo[['outlet_name','conversion_rate','total_revenue']].copy()
            lo_display['conversion_rate'] = lo_display['conversion_rate'].apply(lambda x: f"{x:.1f}%")
            lo_display['total_revenue'] = lo_display['total_revenue'].apply(config.format_currency)
            render_mobile_cards(lo_display, "outlet_name", [("Conversion", "conversion_rate"), ("Omset", "total_revenue")], max_rows=12)
            st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
            df_show(lo_display, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("No outlets with <15% conversion rate")
    st.subheader("📢 Awareness Analysis")
    seg = base[(base['foto_qty']>base['foto_qty'].median()) & (base['conversion_rate']<base['conversion_rate'].median())]
    if not seg.empty:
        st.write("**⚠️ High Awareness, Low Conversion (Need Promotion)**")
        seg_display = seg[['outlet_name','foto_qty','conversion_rate','total_revenue']].copy()
        seg_display['conversion_rate'] = seg_display['conversion_rate'].apply(lambda x: f"{x:.1f}%")
        seg_display['total_revenue'] = seg_display['total_revenue'].apply(config.format_currency)
        render_mobile_cards(seg_display, "outlet_name", [("Foto", "foto_qty"), ("Conversion", "conversion_rate"), ("Omset", "total_revenue")], max_rows=12)
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(seg_display, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.subheader("📈 Conversion Trends"); st.plotly_chart(viz.create_trend_chart(base, 'conversion_rate'), use_container_width=True)

def show_outlet_ranking(df, config, processor):
    st.title("🏆 Ranking Outlet")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    base = df.copy(deep=True)
    cnt = base['outlet_status'].value_counts()
    a,b,c = st.columns(3)
    with a: st.metric("🟢 Keeper", cnt.get('Keeper',0))
    with b: st.metric("🟡 Optimasi", cnt.get('Optimasi',0))
    with c: st.metric("🔴 Relocate", cnt.get('Relocate',0))
    st.subheader("📊 Complete Outlet Ranking")
    ranked = base.sort_values('total_revenue', ascending=False).reset_index(drop=True)
    ranked['rank'] = range(1,len(ranked)+1)
    disp = ranked[['rank','outlet_name','area','kategori_tempat','total_revenue','conversion_rate','outlet_status']].copy()
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
    t1,t2,t3 = st.tabs(["🟢 Keeper","🟡 Optimasi","🔴 Relocate"])
    with t1:
        k = base[base['outlet_status']=="Keeper"]
        df_show(k[['outlet_name','area','total_revenue','conversion_rate']], use_container_width=True) if not k.empty else st.info("No outlets in Keeper status")
    with t2:
        o = base[base['outlet_status']=="Optimasi"]
        df_show(o[['outlet_name','area','total_revenue','conversion_rate']], use_container_width=True) if not o.empty else st.info("No outlets in Optimasi status")
    with t3:
        r = base[base['outlet_status']=="Relocate"]
        df_show(r[['outlet_name','area','total_revenue','conversion_rate']], use_container_width=True) if not r.empty else st.info("No outlets in Relocate status")

def show_period_comparison(df, config, processor, viz, current_period, compare_period):
    st.title("📅 Perbandingan Periode")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    base = df.copy(deep=True)
    if current_period and compare_period:
        cur = base[base['periode']==current_period]; prev = base[base['periode']==compare_period]
        gm = calculate_growth_metrics(cur, prev)
        st.subheader("📈 Growth Metrics")
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Revenue Growth", f"{gm.get('revenue_growth',0):+.1f}%", delta=f"{gm.get('revenue_growth',0):+.1f}%")
        with c2: st.metric("Photo Growth", f"{gm.get('photo_growth',0):+.1f}%", delta=f"{gm.get('photo_growth',0):+.1f}%")
        with c3: st.metric("Conversion Change", f"{gm.get('conversion_change',0):+.1f}pp", delta=f"{gm.get('conversion_change',0):+.1f}pp")
        st.subheader("📈 Trend Analysis"); st.plotly_chart(viz.create_trend_chart(base, 'total_revenue'), use_container_width=True)
    else:
        st.info("Pilih kedua periode di sidebar untuk membandingkan.")


# ================= UPLOAD =================
def excel_engine_from_filename(filename: str) -> str:
    """
    Why: pastikan .xlsx → openpyxl, .xls → xlrd (pandas lama default ke xlrd untuk semuanya).
    """
    ext = os.path.splitext(str(filename).lower())[1]
    if ext == ".xlsx":
        return "openpyxl"
    if ext == ".xls":
        return "xlrd"
    raise ValueError(f"Format file '{ext}' tidak didukung. Gunakan .xlsx atau .xls.")

def suggest_default_sheets(sheet_names: List[str]) -> List[str]:
    picks = [s for s in sheet_names if any(k in s.lower() for k in ["data","transaksi","raw","detail"])]
    return picks or sheet_names[:1]

def read_selected_sheets(file_bytes: bytes, selected_sheets: List[str], engine: str) -> pd.DataFrame:
    """
    Why: gunakan engine eksplisit untuk menghindari error xlrd saat .xlsx.
    """
    buf = io.BytesIO(file_bytes)
    xls = pd.ExcelFile(buf, engine=engine)
    frames = []
    for name in selected_sheets:
        df = pd.read_excel(xls, sheet_name=name, engine=engine)
        if df is None or df.empty:
            continue
        frames.append(normalize_headers(df))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def deduplicate_rows(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    df = df.copy()
    subset = [c for c in ["outlet_name","tanggal","harga","type"] if c in df.columns] or [c for c in ["outlet_name","harga"] if c in df.columns]
    before_rows = len(df)
    before_sum  = df["harga"].sum() if "harga" in df.columns else 0.0
    df = df.drop_duplicates(subset=subset, keep="first")
    after_rows  = len(df)
    after_sum   = df["harga"].sum() if "harga" in df.columns else 0.0
    audit = {"subset": subset,"rows_before": before_rows,"rows_after": after_rows,
             "dup_removed": before_rows - after_rows,"sum_before": float(before_sum),
             "sum_after": float(after_sum),"sum_diff": float(after_sum - before_sum)}
    return df, audit

def show_kemitraan_page(df: pd.DataFrame, config: Config, processor: DataProcessor):
    st.title("🤝 Kemitraan")
    mapping = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()
    sharing_periods = list_sharing_periods()
    tx_periods = sorted([str(p) for p in df.get("periode", pd.Series(dtype=str)).dropna().unique()]) if isinstance(df, pd.DataFrame) and not df.empty else []
    periods = sorted(set(sharing_periods + tx_periods))
    selected_period = st.selectbox("Periode", periods, index=len(periods)-1 if periods else 0, key="kemitraan_period") if periods else None
    _, sharing_master = load_sharing_outlets_exact(selected_period)
    kemitraan = build_kemitraan_financials(df, sharing_master, mapping, selected_period)

    section = st.radio(
        "Menu Kemitraan",
        ["Ringkasan Dashboard", "Kemitraan All", "Kemitraan Satuan", "Setting Kemitraan"],
        horizontal=True,
        key="kemitraan_section",
    )

    if section == "Ringkasan Dashboard":
        if selected_period and isinstance(df, pd.DataFrame) and not df.empty and "periode" in df.columns:
            dashboard_tx = df[df["periode"].astype(str) == str(selected_period)].copy()
        else:
            dashboard_tx = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if dashboard_tx.empty or "outlet_name" not in dashboard_tx.columns:
            st.info("Belum ada transaksi dashboard untuk periode ini.")
            return
        if "total_revenue" not in dashboard_tx.columns:
            dashboard_tx["total_revenue"] = 0
        dashboard_tx["_key"] = dashboard_tx["outlet_name"].map(normalize_outlet_name)
        agg_map = {"total_revenue": ("total_revenue", "sum")}
        if "area" in dashboard_tx.columns:
            agg_map["area"] = ("area", "first")
        if "kategori_tempat" in dashboard_tx.columns:
            agg_map["kategori_tempat"] = ("kategori_tempat", "first")
        if "tipe_tempat" in dashboard_tx.columns:
            agg_map["tipe_tempat"] = ("tipe_tempat", "first")
        outlet_summary = dashboard_tx.groupby(["_key", "outlet_name"], as_index=False).agg(**agg_map)

        master_cols = [
            "outlet_name", "area", "outlet_status_master", "outlet_type_master",
            "harga_beli_kemitraan", "partner_share", "broker_share", "sharing_bagi_hasil",
            "monthly_rent", "minimum_payment",
        ]
        master = normalize_sharing_master_df(sharing_master)
        if not master.empty:
            master["_key"] = master["outlet_name"].map(normalize_outlet_name)
            master = master[[c for c in master_cols if c in master.columns] + ["_key"]].drop_duplicates("_key", keep="last")
            outlet_summary = outlet_summary.merge(master.drop(columns=["outlet_name"], errors="ignore"), on="_key", how="left", suffixes=("", "_master"))
            if "area_master" in outlet_summary.columns:
                outlet_summary["area"] = outlet_summary["area_master"].replace("", np.nan).combine_first(outlet_summary.get("area", pd.Series(index=outlet_summary.index)))
                outlet_summary = outlet_summary.drop(columns=["area_master"])

        outlet_summary["harga_beli_kemitraan"] = pd.to_numeric(outlet_summary.get("harga_beli_kemitraan", np.nan), errors="coerce")
        for col in ["partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent", "minimum_payment"]:
            if col not in outlet_summary.columns:
                outlet_summary[col] = np.nan
            outlet_summary[col] = pd.to_numeric(outlet_summary[col], errors="coerce")
        outlet_summary["basis_bagi_hasil"] = np.where(
            outlet_summary["total_revenue"] > 0,
            outlet_summary["total_revenue"],
            outlet_summary["minimum_payment"].fillna(0),
        )
        missing_share = outlet_summary["sharing_bagi_hasil"].isna() & (
            outlet_summary["partner_share"].notna() | outlet_summary["broker_share"].notna()
        )
        outlet_summary.loc[missing_share, "sharing_bagi_hasil"] = (
            1
            - outlet_summary.loc[missing_share, "partner_share"].fillna(0)
            - outlet_summary.loc[missing_share, "broker_share"].fillna(0)
        ).clip(lower=0, upper=1)
        outlet_summary["pendapatan_mitra"] = np.where(
            outlet_summary["partner_share"].notna(),
            outlet_summary["basis_bagi_hasil"] * outlet_summary["partner_share"].clip(lower=0, upper=1),
            outlet_summary["basis_bagi_hasil"]
            * (1 - outlet_summary["sharing_bagi_hasil"].fillna(0).clip(lower=0, upper=1) - outlet_summary["broker_share"].fillna(0).clip(lower=0, upper=1)),
        )
        outlet_summary["pendapatan_broker"] = outlet_summary["basis_bagi_hasil"] * outlet_summary["broker_share"].fillna(0).clip(lower=0, upper=1)
        outlet_summary["pendapatan_difotoin"] = outlet_summary["basis_bagi_hasil"] * outlet_summary["sharing_bagi_hasil"].fillna(0).clip(lower=0, upper=1)
        outlet_summary["persen_pendapatan_mitra"] = np.where(
            outlet_summary["basis_bagi_hasil"] > 0,
            outlet_summary["pendapatan_mitra"] / outlet_summary["basis_bagi_hasil"],
            np.nan,
        )
        outlet_summary["persen_pendapatan_broker"] = np.where(
            outlet_summary["basis_bagi_hasil"] > 0,
            outlet_summary["pendapatan_broker"] / outlet_summary["basis_bagi_hasil"],
            np.nan,
        )
        outlet_summary["persen_pendapatan_difotoin"] = np.where(
            outlet_summary["basis_bagi_hasil"] > 0,
            outlet_summary["pendapatan_difotoin"] / outlet_summary["basis_bagi_hasil"],
            np.nan,
        )
        outlet_summary["yield_bulanan"] = np.where(
            outlet_summary["harga_beli_kemitraan"] > 0,
            outlet_summary["total_revenue"] / outlet_summary["harga_beli_kemitraan"],
            np.nan,
        )
        outlet_summary["yield_tahunan"] = outlet_summary["yield_bulanan"] * 12

        total_revenue_tx = float(outlet_summary["total_revenue"].sum())
        total_outlet_kemitraan = int(kemitraan["outlet_name"].nunique()) if not kemitraan.empty and "outlet_name" in kemitraan.columns else 0
        total_pendapatan_mitra = float(kemitraan["pendapatan_mitra"].sum()) if not kemitraan.empty and "pendapatan_mitra" in kemitraan.columns else 0.0
        total_pendapatan_broker = float(kemitraan["pendapatan_broker"].sum()) if not kemitraan.empty and "pendapatan_broker" in kemitraan.columns else 0.0
        total_pendapatan_difotoin = float(kemitraan["pendapatan_difotoin"].sum()) if not kemitraan.empty and "pendapatan_difotoin" in kemitraan.columns else 0.0
        total_harga_beli = float(outlet_summary["harga_beli_kemitraan"].fillna(0).sum())
        total_yield_bulanan = total_revenue_tx / total_harga_beli if total_harga_beli > 0 else np.nan
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Outlet Kemitraan", total_outlet_kemitraan)
        c2.metric("Total Pendapatan", config.format_currency(total_revenue_tx))
        c3.metric("Pendapatan Mitra", config.format_currency(total_pendapatan_mitra))
        c4.metric("Pendapatan Broker", config.format_currency(total_pendapatan_broker))
        c5.metric("Pendapatan Difotoin", config.format_currency(total_pendapatan_difotoin))
        c6.metric("Yield Bulanan", "-" if pd.isna(total_yield_bulanan) else f"{total_yield_bulanan*100:.1f}%")

        st.subheader("Ringkasan Semua Outlet")
        outlet_summary = outlet_summary[
            outlet_summary["outlet_type_master"].fillna("").astype(str).str.strip().str.lower() == "franchise"
        ].copy()
        display_cols = [
            "outlet_name", "area", "outlet_type_master", "total_revenue",
            "monthly_rent", "minimum_payment",
            "pendapatan_mitra", "pendapatan_broker", "pendapatan_difotoin",
            "persen_pendapatan_mitra", "persen_pendapatan_broker", "persen_pendapatan_difotoin",
            "harga_beli_kemitraan", "yield_bulanan", "yield_tahunan",
        ]
        display = outlet_summary[[c for c in display_cols if c in outlet_summary.columns]].sort_values("total_revenue", ascending=False).copy()
        display_pct = display[
            [c for c in ["persen_pendapatan_mitra", "persen_pendapatan_broker", "persen_pendapatan_difotoin"] if c in display.columns]
        ].copy()
        display = format_kemitraan_table(display, config)
        pct_pairs = {
            "pendapatan_mitra": "persen_pendapatan_mitra",
            "pendapatan_broker": "persen_pendapatan_broker",
            "pendapatan_difotoin": "persen_pendapatan_difotoin",
        }
        for amount_col, pct_col in pct_pairs.items():
            if amount_col in display.columns and pct_col in display_pct.columns:
                display[amount_col] = [
                    f"{amount} ({float(pct) * 100:.1f}%)" if pd.notna(pct) else amount
                    for amount, pct in zip(display[amount_col], display_pct[pct_col])
                ]
        display = display.drop(columns=list(pct_pairs.values()), errors="ignore").rename(columns={
            "outlet_name": "Outlet",
            "area": "Area",
            "outlet_type_master": "Type Master",
            "total_revenue": "Pendapatan Transaksi",
            "monthly_rent": "Monthly Rent",
            "minimum_payment": "Minimum Payment",
            "pendapatan_mitra": "Pendapatan Mitra",
            "pendapatan_broker": "Pendapatan Broker",
            "pendapatan_difotoin": "Pendapatan Difotoin",
            "harga_beli_kemitraan": "Harga Beli Kemitraan",
            "yield_bulanan": "Yield Bulanan",
            "yield_tahunan": "Yield Tahunan",
        })
        kemitraan_table_show(display, use_container_width=True, hide_index=True, height=table_height(len(display), 300, DEFAULT_TABLE_MAX_HEIGHT))

    if section == "Kemitraan All":
        if kemitraan.empty:
            st.info("Belum ada data kemitraan untuk periode ini.")
            return
        query = st.text_input("Cari outlet / area / pemilik", key="kemitraan_all_search")
        view = kemitraan.copy()
        if query.strip():
            q = query.strip()
            mask = (
                view["outlet_name"].astype(str).str.contains(q, case=False, na=False)
                | view["area"].astype(str).str.contains(q, case=False, na=False)
                | view["investor_name"].astype(str).str.contains(q, case=False, na=False)
            )
            view = view[mask].copy()
        cols = [
            "outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master",
            "investor_name", "total_revenue", "minimum_payment", "basis_bagi_hasil",
            "partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent",
            "pendapatan_mitra", "pendapatan_broker", "pendapatan_difotoin", "profit_difotoin",
            "harga_beli_kemitraan", "estimasi_bep_bulan", "yield_bulanan", "yield_tahunan",
        ]
        display = format_kemitraan_table(view[[c for c in cols if c in view.columns]].sort_values("basis_bagi_hasil", ascending=False), config)
        display = display.rename(columns={
            "outlet_id": "ID",
            "outlet_name": "Outlet",
            "area": "Area",
            "outlet_status_master": "Status",
            "outlet_type_master": "Type",
            "investor_name": "Pemilik/Kemitraan",
            "total_revenue": "Revenue Transaksi",
            "minimum_payment": "Minimum Payment",
            "basis_bagi_hasil": "Revenue/Basis",
            "partner_share": "Partner Share",
            "broker_share": "Broker Share",
            "sharing_bagi_hasil": "Share Difotoin",
            "monthly_rent": "Monthly Rent",
            "pendapatan_mitra": "Pendapatan Mitra",
            "pendapatan_broker": "Pendapatan Broker",
            "pendapatan_difotoin": "Pendapatan Difotoin",
            "profit_difotoin": "Profit Difotoin",
            "harga_beli_kemitraan": "Harga Beli Kemitraan",
            "estimasi_bep_bulan": "BEP",
            "yield_bulanan": "Yield Bulanan",
            "yield_tahunan": "Yield Tahunan",
        })
        kemitraan_table_show(display, use_container_width=True, hide_index=True, height=table_height(len(display), 320, DEFAULT_TABLE_MAX_HEIGHT))

    if section == "Kemitraan Satuan":
        if kemitraan.empty:
            st.info("Belum ada data kemitraan untuk periode ini.")
            return
        people = kemitraan.copy()
        people["investor_name"] = people["investor_name"].fillna("").astype(str).str.strip().replace("", "Belum diisi")
        summary = people.groupby("investor_name", as_index=False).agg(
            outlet_count=("outlet_name", "nunique"),
            harga_beli=("harga_beli_kemitraan", "sum"),
            revenue=("basis_bagi_hasil", "sum"),
            pendapatan_mitra=("pendapatan_mitra", "sum"),
            pendapatan_broker=("pendapatan_broker", "sum"),
            pendapatan_difotoin=("pendapatan_difotoin", "sum"),
            profit_difotoin=("profit_difotoin", "sum"),
        )
        summary["estimasi_bep_bulan"] = np.where(
            (summary["harga_beli"] > 0) & (summary["pendapatan_mitra"] > 0),
            summary["harga_beli"] / summary["pendapatan_mitra"],
            np.nan,
        )
        summary["yield_bulanan"] = np.where(summary["harga_beli"] > 0, summary["pendapatan_mitra"] / summary["harga_beli"], np.nan)
        summary["yield_tahunan"] = summary["yield_bulanan"] * 12
        names = summary.sort_values("pendapatan_mitra", ascending=False)["investor_name"].tolist()

        st.subheader("Ringkasan Semua Kemitraan")
        summary_display = format_kemitraan_table(summary.sort_values("pendapatan_mitra", ascending=False), config).rename(columns={
            "investor_name": "Kemitraan",
            "outlet_count": "Jumlah Outlet",
            "harga_beli": "Total Harga Beli",
            "revenue": "Revenue/Basis",
            "pendapatan_mitra": "Pendapatan Mitra",
            "pendapatan_broker": "Pendapatan Broker",
            "pendapatan_difotoin": "Pendapatan Difotoin",
            "profit_difotoin": "Profit Difotoin",
            "estimasi_bep_bulan": "BEP",
            "yield_bulanan": "Yield Bulanan",
            "yield_tahunan": "Yield Tahunan",
        })
        kemitraan_table_show(
            summary_display,
            use_container_width=True,
            hide_index=True,
            height=table_height(len(summary_display), 260, DEFAULT_TABLE_MAX_HEIGHT),
        )

        selected_name = st.selectbox("Pilih kemitraan / pemilik", names, key="kemitraan_satuan_select") if names else None

        if selected_name:
            st.subheader("Detail Outlet Dimiliki")
            detail = people[people["investor_name"] == selected_name].copy()
            detail_cols = [
                "outlet_id", "outlet_name", "area", "outlet_status_master", "basis_bagi_hasil",
                "partner_share", "pendapatan_mitra", "harga_beli_kemitraan",
                "estimasi_bep_bulan", "yield_bulanan", "yield_tahunan",
            ]
            detail = format_kemitraan_table(detail[[c for c in detail_cols if c in detail.columns]].sort_values("basis_bagi_hasil", ascending=False), config)
            detail = detail.rename(columns={
                "outlet_id": "ID",
                "outlet_name": "Outlet",
                "area": "Area",
                "outlet_status_master": "Status",
                "basis_bagi_hasil": "Revenue/Basis",
                "partner_share": "Partner Share",
                "pendapatan_mitra": "Pendapatan Mitra",
                "harga_beli_kemitraan": "Harga Beli",
                "estimasi_bep_bulan": "BEP",
                "yield_bulanan": "Yield Bulanan",
                "yield_tahunan": "Yield Tahunan",
            })
            kemitraan_table_show(detail, use_container_width=True, hide_index=True, height=table_height(len(detail), 240, DEFAULT_TABLE_MAX_HEIGHT))

    if section == "Setting Kemitraan":
        st.subheader("Upload Data Kemitraan")
        render_sharing_upload_panel(config)
        st.divider()
        st.subheader("Master Kemitraan Editable")
        edit_period = st.selectbox(
            "Periode master",
            sharing_periods,
            index=len(sharing_periods)-1 if sharing_periods else 0,
            key="kemitraan_setting_period",
        ) if sharing_periods else None
        if not edit_period:
            st.info("Upload file outlet_update.xlsx dulu untuk membuat master kemitraan.")
            return
        _, edit_df = load_sharing_outlets_exact(edit_period)
        edit_df = normalize_sharing_master_df(edit_df)
        editor_config = None
        if HAS_COLUMN_CONFIG:
            try:
                editor_config = {
                    "outlet_id": st.column_config.TextColumn("ID", width="small"),
                    "outlet_name": st.column_config.TextColumn("Nama Outlet", width="large"),
                    "area": st.column_config.TextColumn("Branch/Area", width="medium"),
                    "outlet_status_master": st.column_config.SelectboxColumn("Status", options=["", "Active", "Inactive"], width="small"),
                    "outlet_type_master": st.column_config.TextColumn("Type", width="small"),
                    "investor_name": st.column_config.TextColumn("Nama Kemitraan/Pemilik", width="medium"),
                    "partner_share": st.column_config.NumberColumn("Partner Share", min_value=0, max_value=1, step=0.01, format="%.2f"),
                    "broker_share": st.column_config.NumberColumn("Broker Share", min_value=0, max_value=1, step=0.01, format="%.2f"),
                    "sharing_bagi_hasil": st.column_config.NumberColumn("Share Difotoin", min_value=0, max_value=1, step=0.01, format="%.2f"),
                    "monthly_rent": st.column_config.NumberColumn("Monthly Rent", min_value=0, step=100000, format="%.0f"),
                    "minimum_payment": st.column_config.NumberColumn("Minimum Payment", min_value=0, step=100000, format="%.0f"),
                    "harga_beli_kemitraan": st.column_config.NumberColumn("Harga Beli Kemitraan", min_value=0, step=1000000, format="%.0f"),
                    "created_at": st.column_config.TextColumn("Created At", width="medium"),
                }
            except Exception:
                editor_config = None
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        if hasattr(st, "data_editor"):
            edited = st.data_editor(
                edit_df,
                use_container_width=True,
                hide_index=True,
                height=table_height(len(edit_df), 340, DEFAULT_TABLE_MAX_HEIGHT),
                num_rows="dynamic",
                column_config=editor_config,
                key=f"kemitraan_master_editor_{edit_period}",
            )
        else:
            edited = edit_df
            df_show(edit_df, use_container_width=True, hide_index=True, height=table_height(len(edit_df), 340, DEFAULT_TABLE_MAX_HEIGHT))
        st.markdown('</div>', unsafe_allow_html=True)
        if st.button("Simpan Master Kemitraan", type="primary", key="kemitraan_save_master"):
            cleaned = normalize_sharing_master_df(pd.DataFrame(edited))
            save_sharing_outlets(edit_period, cleaned)
            sync_sharing_to_mapping(cleaned, edit_period)
            try:
                cache_clear(load_app_data)
            except Exception:
                pass
            st.success(f"Master kemitraan {edit_period} tersimpan: {len(cleaned)} outlet.")
            rerun()


# ================= BOOT =================
if __name__ == "__main__":
    main()
