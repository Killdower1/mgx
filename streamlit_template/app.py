# path: app.py — Difotoin Dashboard (Trend 12 bulan + kolom Rata-rata) — Server-Compat (Streamlit/Python lama) — Mutation-safe
# NOTE: Patched to force openpyxl for .xlsx and xlrd only for .xls

import io
import os
import re
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Tuple, Dict, Optional

from data_processor import DataProcessor
from visualizations import Visualizations
from utils import *
from config import Config

# ============== COMPAT LAYER (Streamlit lama / Python 3.6) ==============
HAS_CACHE_DATA = hasattr(st, "cache_data")
HAS_COLUMN_CONFIG = hasattr(st, "column_config")
HAS_CAPTION = hasattr(st, "caption")

def cache_data(func=None, **kwargs):
    deco = st.cache_data if HAS_CACHE_DATA else st.cache
    return deco(func) if func else deco(**kwargs)

def rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def text_col(title, width="medium"):
    if HAS_COLUMN_CONFIG:
        try:
            return st.column_config.TextColumn(title, width=width)
        except Exception:
            return None
    return None

def df_show(df_obj, use_container_width=True, hide_index=True, column_config=None):
    try:
        if column_config is not None and HAS_COLUMN_CONFIG:
            st.dataframe(df_obj, use_container_width=use_container_width, hide_index=hide_index, column_config=column_config)
        else:
            st.dataframe(df_obj, use_container_width=use_container_width, hide_index=hide_index)
    except TypeError:
        st.dataframe(df_obj)
    except Exception:
        try:
            st.table(df_obj)
        except Exception:
            st.write(df_obj)

def s_caption(text: str):
    try:
        if HAS_CAPTION:
            st.caption(text)
        else:
            st.markdown(f"<small>{text}</small>", unsafe_allow_html=True)
    except Exception:
        st.markdown(f"<small>{text}</small>", unsafe_allow_html=True)

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
    page_title="Difotoin Sales Dashboard",
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
    "Galeri","Event Space","Co-working Space","Lainnya"
]
SUB_KATEGORI_TEMPAT = [
    "Food Court","Department Store","Supermarket","Boutique","Electronics Store","Bookstore",
    "Pantai","Gunung","Danau","Taman Nasional","Candi","Kebun Binatang","Waterpark",
    "Fine Dining","Fast Food","Street Food","Bakery","Coffee Shop","Bar","Lounge",
    "Budget Hotel","Luxury Hotel","Resort","Homestay","Guest House","Hostel",
    "Tidak Terkategorisasi","Lainnya"
]

VALID_EMAIL = "octadimas@gmail.com"
VALID_PASSWORD = "dowerdower1"
DATA_CSV_PATH = "data/difotoin_dashboard_data.csv"

# ================= STYLES =================
st.markdown("""
<style>
    .main-header{font-size:2.2rem;font-weight:700;color:#fff!important;text-align:center;margin-bottom:1.5rem;}
    .status-keeper{color:#10b981!important;font-weight:bold;}
    .status-optimasi{color:#f59e0b!important;font-weight:bold;}
    .status-relocate{color:#ef4444!important;font-weight:bold;}
    .insight-box{background:#000;border-left:4px solid #3b82f6;padding:1rem;margin:1rem 0;border-radius:.25rem;color:#fff!important;}
    .outlet-table{padding:0;margin-bottom:2rem;}
    .filter-buttons{margin-bottom:1rem;}
    .filter-buttons .stCheckbox>label{background:#f8fafc!important;padding:.5rem 1rem;border-radius:.5rem;border:1px solid #e5e7eb;color:#1f2937!important;font-weight:500;}
    .filter-buttons .stCheckbox>label:hover{background:#f1f5f9!important;}
    .stMetric>label{font-size:.8rem!important;color:#6b7280!important;}
    .stMetric [data-testid="metric-value"]{font-size:1.4rem!important;color:#fff!important;}
    .stApp{color:#fff!important;background:#1a1a1a!important;}
    .stSidebar{background:#000000!important;}
    .stSidebar *{color:#fff!important;}
    .stMarkdown,.stMarkdown *,.stText,.stText *,h1,h2,h3,h4,h5,h6,p,span,div,label{color:#fff!important;}
    .stSelectbox label,.stTextInput label,.stNumberInput label,.stTextArea label{color:#fff!important;}
    .stDataFrame,.stDataFrame *{color:#1f2937!important;}
    .stTabs [data-baseweb="tab-list"] button{color:#fff!important;}
    .stButton button{color:#1f2937!important;background:#3b82f6!important;border:none!important;}
    .performer-card{padding:.5rem;margin:.25rem 0;border-radius:.25rem;background:#2a2a2a;border:1px solid #404040;}
</style>
""", unsafe_allow_html=True)

# ================= AUTH =================
def _init_auth_state():
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_email", None)

def show_login_page():
    st.markdown('<h1 class="main-header">📸 Difotoin Dashboard</h1>', unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="Enter your email", key="login_email")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_pass")
        submitted = st.form_submit_button("🔐 Login")
        if submitted:
            if email == VALID_EMAIL and password == VALID_PASSWORD:
                st.session_state["logged_in"] = True
                st.session_state["user_email"] = email
                st.success("✅ Login successful! Redirecting…")
                rerun()
            else:
                st.error("❌ Invalid email or password. Please try again.")
    st.markdown("---")
    st.info("💡 **Demo Credentials:**\n- Email: octadimas@gmail.com\n- Password: dowerdower1")

def show_logout_button():
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", key="btn_logout"):
        st.session_state["logged_in"] = False
        st.session_state["user_email"] = None
        rerun()
    if st.session_state.get("user_email"):
        st.sidebar.markdown(f"👤 **Logged in as:**\n{st.session_state['user_email']}")

def check_login():
    _init_auth_state()
    return bool(st.session_state.get("logged_in"))

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
    s = series.astype(str).str.strip()
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    s = s.str.replace(r"[^\d\-,\.]", "", regex=True)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

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
    col1, col2, col3, col4 = st.columns(4)
    with col1: show_keeper = st.checkbox("🟢 Keeper", value=True, key="filter_keeper")
    with col2: show_optimasi = st.checkbox("🟡 Optimasi", value=True, key="filter_optimasi")
    with col3: show_relocate = st.checkbox("🔴 Relocate", value=True, key="filter_relocate")
    with col4: show_all = st.checkbox("Show All", value=False, key="filter_all")
    st.markdown('</div>', unsafe_allow_html=True)

    current_df = df[df['periode'] == current_period] if current_period else df
    if not show_all:
        keep = []
        if show_keeper: keep.append("Keeper")
        if show_optimasi: keep.append("Optimasi")
        if show_relocate: keep.append("Relocate")
        if keep: current_df = current_df[current_df['outlet_status'].isin(keep)]

    compare_map = {}
    if compare_period:
        src = full_df if full_df is not None else df
        cmp_df = src[src["periode"] == compare_period].copy()
        if not cmp_df.empty:
            cmp_df["_key"] = cmp_df["outlet_name"].map(_norm_name)
            compare_map = cmp_df.set_index("_key").to_dict(orient="index")

    rows = []
    for _, r in current_df.iterrows():
        name = r["outlet_name"]; key = _norm_name(name)
        omset = float(r["total_revenue"]); foto = int(r["foto_qty"]); unlock = int(r["unlock_qty"]); conv = float(r["conversion_rate"])
        rec = {
            "Outlet": name, "Area": r.get("area",""),
            "_omset_sort": int(omset), "_foto_sort": int(foto), "_unlock_sort": int(unlock), "_conversion_sort": float(conv),
            "Omset": format_number_with_dots(omset), "Omset Compare": "New Outlet",
            "Foto": format_number_with_dots(foto), "Foto Compare": "New Outlet",
            "Unlock": format_number_with_dots(unlock), "Unlock Compare": "New Outlet",
            "Conversion": f"{conv:.1f}%", "Conversion Compare": "New Outlet",
            "Status": r["outlet_status"],
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
        return ''
    styled = display_df.style.applymap(style_status, subset=["Status"])

    def color_by_delta(series, delta_series):
        d = delta_series.reindex(series.index).fillna(0)
        return ['color:#10b981;font-weight:600' if x>0 else ('color:#ef4444;font-weight:600' if x<0 else '') for x in d]

    if compare_period:
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_omset_delta']), axis=0, subset=['Omset Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_foto_delta']), axis=0, subset=['Foto Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_unlock_delta']), axis=0, subset=['Unlock Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_conv_delta']), axis=0, subset=['Conversion Compare'])

    column_config = None
    if HAS_COLUMN_CONFIG:
        column_config = {
            "Outlet": text_col("Outlet", width="medium"),
            "Area": text_col("Area", width="small"),
            "Omset": text_col("Omset", width="medium"),
            "Omset Compare": text_col("Omset Compare", width="medium"),
            "Foto": text_col("Foto", width="small"),
            "Foto Compare": text_col("Foto Compare", width="small"),
            "Unlock": text_col("Unlock", width="small"),
            "Unlock Compare": text_col("Unlock Compare", width="small"),
            "Conversion": text_col("Conversion", width="small"),
            "Conversion Compare": text_col("Conversion Compare", width="small"),
            "Status": text_col("Status", width="small"),
        }

    df_show(styled, use_container_width=True, hide_index=True, column_config=column_config)
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
    if df_filtered.empty or "outlet_name" not in df_filtered.columns or "periode" not in df_full.columns:
        st.info("Data tidak cukup untuk menampilkan tren omset."); return

    visible_outlets = df_filtered["outlet_name"].dropna().astype(str).unique().tolist()
    trend_df = df_full[df_full["outlet_name"].astype(str).isin(visible_outlets)].copy()
    if trend_df.empty:
        st.info("Tidak ada data tren untuk outlet terpilih."); return

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

    styled = (
        display_df_sorted.style
        .apply(_growth_colors, axis=1, subset=value_cols)
        .format(fmt_map)
    )

    column_config = None
    if HAS_COLUMN_CONFIG:
        column_config = {
            "Outlet": text_col("Outlet", width="medium"),
            "Rata-rata": text_col("Rata-rata", width="medium"),
        }

    df_show(styled, use_container_width=True, hide_index=True, column_config=column_config)
    s_caption("Nilai kosong ditampilkan sebagai 0. Rata-rata dihitung dari 12 bulan tampil (termasuk current), hanya omset > 0 yang dihitung. Hijau=naik vs bulan lalu; Merah=turun.")

    # ===== DOWNLOAD EXCEL (ANGKA MURNI) =====
    st.markdown("### 📥 Download Data")
    _export_trend_excel(display_df_sorted, value_cols)

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

    st.sidebar.title("📸 Difotoin Dashboard")
    st.sidebar.markdown("---")
    show_logout_button()

    page = st.sidebar.selectbox(
        "Pilih Halaman",
        ["🏠 Dashboard Utama","📊 Analisis Trend","🔄 Analisis Konversi",
         "🏆 Ranking Outlet","📅 Perbandingan Periode","🗃️ CRUD Data Outlet","⚙️ Admin Panel","📤 Upload Data"]
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
        filtered_df = processor.filter_data(df_for_filter, selected_area, selected_kategori, selected_tipe, current_period) if hasattr(processor, "filter_data") else df_for_filter
    else:
        filtered_df = df

    if page == "🏠 Dashboard Utama":
        show_main_dashboard(filtered_df, config, processor, viz, current_period, compare_period, full_df=df)
    elif page == "📊 Analisis Trend":
        show_trend_analysis(filtered_df, config, processor, viz)
    elif page == "🔄 Analisis Konversi":
        show_conversion_analysis(filtered_df, config, processor, viz)
    elif page == "🏆 Ranking Outlet":
        show_outlet_ranking(filtered_df, config, processor)
    elif page == "📅 Perbandingan Periode":
        show_period_comparison(filtered_df, config, processor, viz, current_period, compare_period)
    elif page == "🗃️ CRUD Data Outlet":
        show_outlet_crud(df, config, processor)
    elif page == "⚙️ Admin Panel":
        show_admin_panel(config)
    elif page == "📤 Upload Data":
        show_upload_data(config)

def show_main_dashboard(df, config, processor, viz, current_period, compare_period, full_df):
    st.markdown('<h1 class="main-header">📸 Difotoin Sales Dashboard</h1>', unsafe_allow_html=True)
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
                        outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
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
                            outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
                            st.success("✅ Outlet updated successfully!"); rerun()
            else:
                st.info("No outlets available to edit")
        with s4:
            st.subheader("🗑️ Delete Outlet")
            if not outlet_mapping.empty:
                outlet_to_delete = st.selectbox("Select Outlet to Delete", outlet_mapping['outlet_name'].tolist())
                if outlet_to_delete and st.button("🗑️ Confirm Delete"):
                    outlet_mapping = outlet_mapping[outlet_mapping['outlet_name']!=outlet_to_delete]
                    outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
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
        df_show(hi[['outlet_name','conversion_rate','total_revenue']], use_container_width=True) if not hi.empty else st.info("No outlets with >25% conversion rate")
    with b:
        st.write("**🔴 Low Conversion Outlets (<15%)**")
        lo = base[base['conversion_rate']<15].sort_values('conversion_rate', ascending=True)
        df_show(lo[['outlet_name','conversion_rate','total_revenue']], use_container_width=True) if not lo.empty else st.info("No outlets with <15% conversion rate")
    st.subheader("📢 Awareness Analysis")
    seg = base[(base['foto_qty']>base['foto_qty'].median()) & (base['conversion_rate']<base['conversion_rate'].median())]
    if not seg.empty:
        st.write("**⚠️ High Awareness, Low Conversion (Need Promotion)**")
        df_show(seg[['outlet_name','foto_qty','conversion_rate','total_revenue']], use_container_width=True)
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
    df_show(disp, use_container_width=True)
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

# =============== ADMIN PANEL ===============
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

    colA, colB = st.columns([1,1])
    with colA:
        if st.button("💾 Save Thresholds", key="btn_save_threshold"):
            try:
                config.set_threshold("keeper_minimum", int(new_keeper))
                config.set_threshold("optimasi_minimum", int(new_optim))
                ok = config.save_config()
                if ok:
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("✅ Thresholds updated & config saved.")
                    rerun()
                else:
                    st.error("❌ Failed to save thresholds.")
            except Exception as e:
                st.error(f"❌ Error saving thresholds: {e}")

    with colB:
        if st.button("🧹 Clear Cached Data", key="btn_clear_cache"):
            try:
                cache_clear(load_app_data)
                st.success("✅ Cache cleared.")
            except Exception as e:
                st.warning(f"ℹ️ Cache clear note: {e}")

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

    data_path = "data/difotoin_dashboard_data.csv"
    with st.expander("📄 Data File Info (opsional)"):
        if os.path.exists(data_path):
            try:
                df_info = pd.read_csv(data_path, nrows=5)
                st.write(f"Path: `{data_path}`")
                try:
                    rows = sum(1 for _ in open(data_path, 'r', encoding='utf-8', errors='ignore')) - 1
                    st.write(f"Rows (approx): ~{rows:,}")
                except Exception:
                    pass
                df_show(df_info, use_container_width=True)
            except Exception as e:
                st.warning(f"Tidak bisa membaca CSV: {e}")
        else:
            st.info("File data belum ada.")

    if st.button("🔄 Reload Page", key="btn_reload_page"):
        rerun()

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

def show_upload_data(config: Config):
    st.title("📤 Upload Data Bulanan (Overwrite by Period)")
    st.info("📋 Upload **per bulan**. Saat menyimpan, **semua data** pada periode (YYYY-MM) yang sama di CSV akan **dihapus**, lalu diganti data dari file ini.")

    uploaded_file = st.file_uploader("Choose Excel file", type=['xlsx','xls'])
    fallback_period = st.sidebar.text_input("🗓️ Fallback Period (YYYY-MM) bila kolom tanggal kosong", value=datetime.now().strftime("%Y-%m"))

    if uploaded_file is not None:
        try:
            engine = excel_engine_from_filename(uploaded_file.name)
            file_bytes = uploaded_file.getvalue()
            buf = io.BytesIO(file_bytes)

            # -- Sheet picker
            xls = pd.ExcelFile(buf, engine=engine)
            st.subheader("📑 Pilih Sheet")
            default_sheets = suggest_default_sheets(xls.sheet_names)
            selected_sheets = st.multiselect("Gunakan sheet berikut:", xls.sheet_names, default=default_sheets)
            if not selected_sheets:
                st.warning("Pilih minimal satu sheet."); return

            # -- Preview
            try:
                s_caption("Preview 10 baris pertama dari sheet pertama terpilih")
                prev = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_sheets[0], nrows=10, engine=engine)
                df_show(prev, use_container_width=True)
            except ImportError as ie:
                st.error(f"❌ Dependensi pembaca Excel belum terpasang untuk '{engine}'. Install paket yang sesuai (e.g. `pip install openpyxl`). Detail: {ie}")
                return
            except Exception:
                pass

            # -- Read all selected sheets with explicit engine
            full_df_raw = read_selected_sheets(file_bytes, selected_sheets, engine)
            if full_df_raw.empty:
                st.error("❌ Sheet terpilih kosong."); return

            # Mapping manual
            st.subheader("🧭 Column Mapping")
            auto_map = apply_column_mapping_auto(full_df_raw)
            col_list = list(full_df_raw.columns)

            def _idx(colname):
                return (col_list.index(colname)+1) if (colname in col_list) else 0

            col_outlet  = st.selectbox("Kolom Outlet → outlet_name", ["<None>"]+col_list, index=_idx(auto_map.get("outlet_name","")))
            col_harga   = st.selectbox("Kolom Harga → harga", ["<None>"]+col_list, index=_idx(auto_map.get("harga","")))
            col_tanggal = st.selectbox("Kolom Tanggal → tanggal (opsional)", ["<None>"]+col_list, index=_idx(auto_map.get("tanggal","")))
            col_area    = st.selectbox("Kolom Area → area (opsional)", ["<None>"]+col_list, index=_idx(auto_map.get("area","")))
            col_type    = st.selectbox("Kolom Jenis/Type (Foto/Unlock/Print) → type", ["<None>"]+col_list, index=_idx(auto_map.get("type","")))

            if col_outlet == "<None>" or col_harga == "<None>":
                st.error("❌ Wajib pilih kolom Outlet dan Harga."); return

            mapping = {col_outlet: "outlet_name", col_harga: "harga"}
            if col_tanggal != "<None>": mapping[col_tanggal] = "tanggal"
            if col_area    != "<None>": mapping[col_area]    = "area"
            if col_type    != "<None>": mapping[col_type]    = "type"

            cleaned = full_df_raw.rename(columns=mapping).copy()

            # Scale harga
            st.subheader("💵 Harga Scale (kalau total 10×)")
            scale_option = st.radio("Pilih scale harga:", ["x1 (normal)","÷10","÷100","÷1000"], index=0)
            scale_value = {"x1 (normal)":1.0,"÷10":0.1,"÷100":0.01,"÷1000":0.001}[scale_option]
            cleaned["harga"] = to_numeric_clean(cleaned["harga"]) * scale_value

            if "tanggal" in cleaned.columns:
                cleaned["tanggal"] = pd.to_datetime(cleaned["tanggal"], errors="coerce")
            if "outlet_name" in cleaned.columns:
                cleaned["outlet_name"] = cleaned["outlet_name"].astype(str).str.strip()
            if "area" not in cleaned.columns:
                cleaned["area"] = ""

            # DIAG: Distribusi type
            if "type" in cleaned.columns:
                s_caption("Distribusi nilai kolom Type (untuk derive Foto/Unlock/Print):")
                vc = cleaned["type"].astype(str).str.strip().str.lower().value_counts().head(15)
                df_show(vc.to_frame("count"), use_container_width=True)

            # Dedup
            tmp_for_dedup = cleaned.copy()
            deduped, dd_audit = deduplicate_rows(tmp_for_dedup)

            st.subheader("🧮 Ringkasan Excel RAW (setelah mapping, cleaning & dedup)")
            st.write("- Rows sebelum dedup: **{:,}**".format(dd_audit['rows_before']))
            st.write("- Rows sesudah dedup: **{:,}**  (hapus **{:,}** duplikat)".format(dd_audit['rows_after'], dd_audit['dup_removed']))
            st.write("- Total Harga sesudah dedup: **{}**".format(Config().format_currency(dd_audit['sum_after'])))
            st.write("- Key dedup: **{}**".format(', '.join(dd_audit['subset']) or '(none)'))

            # Agregasi
            processed_df, derive_audit = aggregate_monthly(deduped, config, fallback_period=fallback_period)

            st.subheader("🧪 Derive Audit (dari kolom Type)")
            st.write("- Match Foto  : **{:,}** rows".format(derive_audit.get('match_foto',0)))
            st.write("- Match Unlock: **{:,}** rows".format(derive_audit.get('match_unlock',0)))
            st.write("- Match Print : **{:,}** rows".format(derive_audit.get('match_print',0)))

            st.subheader("🔎 Preview Hasil Agregasi")
            show_cols = ["periode","outlet_name","area","total_revenue","foto_qty","unlock_qty","print_qty","conversion_rate"]
            df_show(processed_df[show_cols].head(25), use_container_width=True)

            st.subheader("🧾 Audit — Perbandingan Total (Excel vs Agregasi)")
            total_raw = float(dd_audit['sum_after'])
            total_aggr = float(processed_df["total_revenue"].sum())
            st.write("- Total Harga **Excel RAW (DEDUP & SCALE)**: **{}**".format(Config().format_currency(total_raw)))
            st.write("- Total Revenue **Agregasi file ini**: **{}**".format(Config().format_currency(total_aggr)))
            st.write("- Selisih (Agregasi - Raw): **{}**".format(Config().format_currency(total_aggr - total_raw)))

            if st.button("🚀 Save (Overwrite periode terpilih)"):
                with st.spinner("Menyimpan (overwrite by period)..."):
                    merged, ow = save_overwrite_periods(processed_df, DATA_CSV_PATH)
                    per_uploaded = ow["periods_overwritten"]
                    before_total = ow["before_total"]; after_total = ow["after_total"]
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("✅ Data berhasil di-overwrite berdasarkan periode!")
                    st.subheader("🧾 Audit — Overwrite by Period")
                    st.write("- Periode di-overwrite: **{}**".format(', '.join(per_uploaded)))
                    st.write("- Total di CSV (sebelum overwrite): **{}**".format(Config().format_currency(before_total)))
                    st.write("- Total di CSV (sesudah overwrite): **{}**".format(Config().format_currency(after_total)))
                    st.info("Periode tersedia sekarang: **{}**".format(', '.join(ow['remaining_periods'])))
                    csv_subset = merged[merged["periode"].isin(per_uploaded)]
                    csv_total_for_periods = float(csv_subset["total_revenue"].sum())
                    st.write("- Total di CSV (periode file ini): **{}**".format(Config().format_currency(csv_total_for_periods)))
                    st.write("- Selisih (CSV - Agregasi file ini): **{}**".format(Config().format_currency(csv_total_for_periods - total_aggr)))
                    rerun()

        except ImportError as ie:
            st.error(f"❌ Dependency untuk membaca Excel belum terpasang. Install sesuai engine: {ie}")
        except Exception as e:
            st.error(f"❌ Error reading/processing file: {e}")

# ================= BOOT =================
if __name__ == "__main__":
    main()
