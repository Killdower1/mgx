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
from pages.crud_outlet import show_outlet_crud, show_outlet_crud_v2
from pages.dashboard import show_main_dashboard
from pages.trend import show_trend_analysis, show_trend_analysis_v2, build_ai_trend_insights, render_ai_insights
from pages.ai_decision import show_ai_decision_center

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




# ================= OMSET TREND TABLE (12 bulan + Rata-rata + server-side sorting) =================
def _sort_periods_str(periods: List[str]) -> List[str]:
    s = pd.Series(periods, dtype=object)
    dt = pd.to_datetime(s, format="%Y-%m", errors="coerce")
    helper = pd.DataFrame({"p": s, "dt": dt}).sort_values(by=["dt","p"], na_position="last")
    return helper["p"].astype(str).tolist()

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


# show_ai_decision_center moved to pages/ai_decision.py


# show_trend_analysis_v2 moved to pages/trend.py
# show_trend_analysis moved to pages/trend.py

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
