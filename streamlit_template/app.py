# app.py — FULL

import io
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

# ================== PAGE CONFIG ==================
st.set_page_config(
    page_title="Difotoin Sales Dashboard",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================== CONSTANTS ==================
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

# ================== STYLES ==================
st.markdown("""
<style>
    .main-header{font-size:2.5rem;font-weight:bold;color:#fff!important;text-align:center;margin-bottom:2rem;}
    .status-keeper{color:#10b981!important;font-weight:bold;}
    .status-optimasi{color:#f59e0b!important;font-weight:bold;}
    .status-relocate{color:#ef4444!important;font-weight:bold;}
    .insight-box{background:#000;border-left:4px solid #3b82f6;padding:1rem;margin:1rem 0;border-radius:.25rem;color:#fff!important;}
    .outlet-table{padding:0;margin-bottom:2rem;}
    .filter-buttons{margin-bottom:1rem;}
    .filter-buttons .stCheckbox>label{background:#f8fafc!important;padding:.5rem 1rem;border-radius:.5rem;border:1px solid #e5e7eb;color:#1f2937!important;font-weight:500;}
    .filter-buttons .stCheckbox>label:hover{background:#f1f5f9!important;}
    .stMetric>label{font-size:.8rem!important;color:#6b7280!important;}
    .stMetric [data-testid="metric-value"]{font-size:1.5rem!important;color:#fff!important;}
    .stApp{color:#fff!important;background:#1a1a1a!important;}
    .stSidebar{background:#000000!important;} /* <- sidebar full black */
    .stSidebar *{color:#fff!important;}
    .stMarkdown,.stMarkdown *,.stText,.stText *,h1,h2,h3,h4,h5,h6,p,span,div,label{color:#fff!important;}
    .stSelectbox label,.stTextInput label,.stNumberInput label,.stTextArea label{color:#fff!important;}
    .stDataFrame,.stDataFrame *{color:#1f2937!important;}
    .stTabs [data-baseweb="tab-list"] button{color:#fff!important;}
    .stButton button{color:#1f2937!important;background:#3b82f6!important;border:none!important;}
    .stAlert{color:#1f2937!important;}
    .performer-card{padding:.5rem;margin:.25rem 0;border-radius:.25rem;background:#2a2a2a;border:1px solid #404040;}
    .performer-card strong{color:#fff!important;}
</style>
""", unsafe_allow_html=True)

# ================== AUTH ==================
def show_login_page():
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h1 class="login-header">📸 Difotoin Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subheader">Please login to access the dashboard</p>', unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        _, c, _ = st.columns([1,2,1])
        with c:
            submitted = st.form_submit_button("🔐 Login", use_container_width=True)
        if submitted:
            if email == VALID_EMAIL and password == VALID_PASSWORD:
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.success("✅ Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("❌ Invalid email or password. Please try again.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.info("💡 **Demo Credentials:**\n- Email: octadimas@gmail.com\n- Password: dowerdower1")

def show_logout_button():
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.rerun()
    st.sidebar.markdown(f"👤 **Logged in as:**\n{st.session_state.user_email}")

def check_login():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    return st.session_state.logged_in

# ================== DATA LOADING ==================
@st.cache_data
def load_app_data():
    processor = DataProcessor()
    return processor.load_data()

# ================== PERIOD SELECTOR (SIDEBAR) ==================
def create_sidebar_period_selector(df):
    if df.empty:
        return None, None
    st.sidebar.markdown("### 📅 Periode Selection")
    periods = sorted(df["periode"].unique())
    current = st.sidebar.selectbox("Current Period", periods, index=len(periods)-1 if periods else 0, key="period_current_sidebar")
    compare_opts = ["None"] + [p for p in periods if p != current]
    compare = st.sidebar.selectbox("Compare with", compare_opts, key="period_compare_sidebar")
    return current, (None if compare == "None" else compare)

# ================== HELPERS ==================
def format_number_with_dots(num):
    try:
        return f"{int(num):,}".replace(",", ".")
    except Exception:
        return str(num)

def format_comparison_value(current_val, compare_val, is_percentage=False):
    if compare_val == 0:
        return "0.0%" if not is_percentage else "0.0pp"
    if is_percentage:
        change = current_val - compare_val
        sign = "+" if change > 0 else ""
        return f"{sign}{change:.1f}pp" if change != 0 else "0.0pp"
    change_pct = ((current_val - compare_val) / compare_val) * 100
    sign = "+" if change_pct > 0 else ""
    return f"{sign}{change_pct:.1f}%" if change_pct != 0 else "0.0%"

def _norm_name(s: str) -> str:
    return str(s).strip().lower()

# ----- Upload mapping helpers -----
EXCEL_TO_APP_COLMAP = {
    "outlet": "outlet_name","nama outlet":"outlet_name","toko":"outlet_name",
    "harga":"harga","amount":"harga","price":"harga",
    "tanggal":"tanggal","date":"tanggal","waktu":"tanggal",
    "area":"area","kota":"area",
    "kategori":"kategori_tempat","kategori tempat":"kategori_tempat",
    "sub kategori":"sub_kategori_tempat","sub_kategori":"sub_kategori_tempat",
    "tipe":"tipe_tempat","tipe tempat":"tipe_tempat",
    "omset":"total_revenue","revenue":"total_revenue",
    "foto":"foto_qty","unlock":"unlock_qty","print":"print_qty","conversion":"conversion_rate",
}

def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    new_cols = [" ".join(str(c).strip().split()) for c in df.columns]
    df = df.copy()
    df.columns = new_cols
    return df

def apply_column_mapping(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    lower_map = {k.lower(): v for k, v in EXCEL_TO_APP_COLMAP.items()}
    used, ren = {}, {}
    for col in df.columns:
        k = col.lower()
        if k in lower_map:
            ren[col] = lower_map[k]
            used[col] = lower_map[k]
    df = df.rename(columns=ren)
    return df, used

def to_numeric_clean(series: pd.Series) -> pd.Series:
    """why: harga bisa '35.000', '35,000', '35000', None -> numerik"""
    s = series.astype(str).str.replace(r"[.\s]", "", regex=True)  # hapus titik & spasi
    s = s.str.replace(",", ".", regex=False)  # koma jadi titik untuk desimal
    s = pd.to_numeric(s, errors="coerce")
    return s

def sanitize_mapped_df(df: pd.DataFrame) -> pd.DataFrame:
    """why: cegah validasi 'harga empty' — NaN/None jadi 0, negatif dibulatkan 0."""
    df = df.copy()
    if "harga" in df.columns:
        # coerce ke numerik + isi NaN/None dengan 0
        df["harga"] = to_numeric_clean(df["harga"]).fillna(0)
        # harga negatif dianggap 0 (safety)
        df.loc[df["harga"] < 0, "harga"] = 0
    # kolom agregat lain kalau ada, rapikan tipe
    for col in ["total_revenue","foto_qty","unlock_qty","print_qty","conversion_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def df_to_excel_bytes(df: pd.DataFrame) -> io.BytesIO:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="Sheet1")
    bio.seek(0)
    return bio

# ================== OUTLET TABLE ==================
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
            "Outlet": name, "Area": r["area"],
            "_omset_sort": int(omset), "_foto_sort": int(foto), "_unlock_sort": int(unlock), "_conversion_sort": float(conv),
            "Omset": format_number_with_dots(omset), "Foto": format_number_with_dots(foto),
            "Unlock": format_number_with_dots(unlock), "Conversion": f"{conv:.1f}%", "Status": r["outlet_status"],
            "_omset_delta": np.nan, "_foto_delta": np.nan, "_unlock_delta": np.nan, "_conv_delta": np.nan
        }
        if compare_period and key in compare_map:
            p = compare_map[key]
            p_omset = float(p.get("total_revenue", 0) or 0); p_foto = int(p.get("foto_qty", 0) or 0)
            p_unlock = int(p.get("unlock_qty", 0) or 0); p_conv = float(p.get("conversion_rate", 0) or 0)
            rec["Omset Compare"] = format_comparison_value(omset, p_omset, False)
            rec["Foto Compare"] = format_comparison_value(foto, p_foto, False)
            rec["Unlock Compare"] = format_comparison_value(unlock, p_unlock, False)
            rec["Conversion Compare"] = format_comparison_value(conv, p_conv, True)
            rec["_omset_delta"] = 0 if p_omset == 0 else ((omset - p_omset) / p_omset) * 100
            rec["_foto_delta"]  = 0 if p_foto  == 0 else ((foto  - p_foto ) / p_foto ) * 100
            rec["_unlock_delta"]= 0 if p_unlock== 0 else ((unlock- p_unlock) / p_unlock) * 100
            rec["_conv_delta"]  = (conv - p_conv)
        else:
            if compare_period:
                rec["Omset Compare"] = "New Outlet"
                rec["Foto Compare"] = "New Outlet"
                rec["Unlock Compare"] = "New Outlet"
                rec["Conversion Compare"] = "New Outlet"
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

    column_config = {
        "Outlet": st.column_config.TextColumn("Outlet", width="medium", pinned=True),
        "Area": st.column_config.TextColumn("Area", width="small"),
        "Omset": st.column_config.TextColumn("Omset", width="medium"),
        "Foto": st.column_config.TextColumn("Foto", width="small"),
        "Unlock": st.column_config.TextColumn("Unlock", width="small"),
        "Conversion": st.column_config.TextColumn("Conversion", width="small"),
        "Status": st.column_config.TextColumn("Status", width="small"),
    }
    if compare_period:
        column_config.update({
            "Omset Compare": st.column_config.TextColumn("Omset Compare", width="medium"),
            "Foto Compare": st.column_config.TextColumn("Foto Compare", width="small"),
            "Unlock Compare": st.column_config.TextColumn("Unlock Compare", width="small"),
            "Conversion Compare": st.column_config.TextColumn("Conversion Compare", width="small"),
        })

    st.dataframe(styled, use_container_width=True, hide_index=True, column_config=column_config)
    st.markdown('</div>', unsafe_allow_html=True)

# ================== PAGES ==================
def main():
    if not check_login():
        show_login_page()
        return

    config = Config()
    processor = DataProcessor()
    viz = Visualizations(config)
    df = load_app_data()

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
        areas = ["Semua"] + sorted(df['area'].unique().tolist())
        selected_area = st.sidebar.selectbox("Area", areas)
        kategoris = ["Semua"] + sorted(df['kategori_tempat'].unique().tolist())
        selected_kategori = st.sidebar.selectbox("Kategori Tempat", kategoris)
        tipes = ["Semua"] + sorted(df['tipe_tempat'].unique().tolist())
        selected_tipe = st.sidebar.selectbox("Tipe Tempat", tipes)
        filtered_df = processor.filter_data(df, selected_area, selected_kategori, selected_tipe, current_period)
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
        show_upload_data(processor, config)

def show_main_dashboard(df, config, processor, viz, current_period, compare_period, full_df):
    st.markdown('<h1 class="main-header">📸 Difotoin Sales Dashboard</h1>', unsafe_allow_html=True)
    if df.empty:
        st.error("❌ Data tidak tersedia. Silakan upload data terlebih dahulu.")
        return
    metrics = processor.calculate_metrics(df)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("💰 Revenue", config.format_currency(metrics['total_revenue']))
    with c2: st.metric("🏪 Outlets", f"{metrics['total_outlets']}")
    with c3: st.metric("📈 Avg Conv Rate", f"{metrics['avg_conversion']:.1f}%")
    with c4: st.metric("📸 Photos", format_number(metrics['total_photos']))
    st.markdown("---")
    create_outlet_table(df, current_period, compare_period, full_df=full_df)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📊 Distribusi Status Outlet")
        st.plotly_chart(viz.create_status_distribution(df), use_container_width=True)
    with col2:
        st.subheader("🏆 Top 5 Performers")
        top = processor.get_top_performers(df, 5)
        for _, row in top.iterrows():
            status_class = f"status-{row['outlet_status'].lower()}"
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
        st.plotly_chart(viz.create_revenue_chart(df), use_container_width=True)
    with b:
        st.subheader("🔄 Conversion Funnel")
        st.plotly_chart(viz.create_conversion_funnel(df), use_container_width=True)

    st.markdown("---")
    st.subheader("💡 Key Insights")
    for insight in generate_insights(df, config):
        st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

def show_outlet_crud(df, config, processor):
    st.title("🗃️ CRUD Data Outlet & Master Data")
    outlet_mapping = processor.load_outlet_mapping()
    if outlet_mapping.empty:
        outlets = df['outlet_name'].unique()
        outlet_mapping = pd.DataFrame({
            'outlet_name': outlets,
            'area': df.groupby('outlet_name')['area'].first().values,
            'kategori_tempat': df.groupby('outlet_name')['kategori_tempat'].first().values,
            'sub_kategori_tempat': df.groupby('outlet_name')['sub_kategori_tempat'].first().values,
            'tipe_tempat': df.groupby('outlet_name')['tipe_tempat'].first().values
        })
    tab1, tab2, tab3 = st.tabs(["🏪 Outlet Management", "📋 Master Data Kategori", "🗺️ Master Data Area"])
    with tab1:
        s1, s2, s3, s4 = st.tabs(["📋 View All", "➕ Add New", "✏️ Edit", "🗑️ Delete"])
        with s1:
            st.subheader("📋 All Outlet Data")
            st.dataframe(outlet_mapping, use_container_width=True) if not outlet_mapping.empty else st.info("No outlet data available")
        with s2:
            st.subheader("➕ Add New Outlet")
            with st.form("add_outlet_form"):
                new_outlet_name = st.text_input("Outlet Name")
                new_area = st.selectbox("Area", INDONESIA_AREAS)
                new_kategori = st.selectbox("Kategori Tempat", KATEGORI_TEMPAT)
                new_sub_kategori = st.selectbox("Sub Kategori Tempat", SUB_KATEGORI_TEMPAT)
                new_tipe = st.selectbox("Tipe Tempat", ["Indoor","Outdoor","Semi-Outdoor"])
                if st.form_submit_button("Add Outlet") and new_outlet_name:
                    if new_outlet_name in outlet_mapping['outlet_name'].values:
                        st.error("❌ Outlet already exists!")
                    else:
                        new_row = pd.DataFrame({'outlet_name':[new_outlet_name],'area':[new_area],
                                                'kategori_tempat':[new_kategori],'sub_kategori_tempat':[new_sub_kategori],
                                                'tipe_tempat':[new_tipe]})
                        outlet_mapping = pd.concat([outlet_mapping, new_row], ignore_index=True)
                        outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
                        st.success("✅ Outlet added successfully!"); st.rerun()
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
                        edit_tipe = st.selectbox("Tipe Tempat", ["Indoor","Outdoor","Semi-Outdoor"], index=["Indoor","Outdoor","Semi-Outdoor"].index(row['tipe_tempat']))
                        if st.form_submit_button("Update Outlet"):
                            outlet_mapping.loc[outlet_mapping['outlet_name']==outlet_to_edit, ['area','kategori_tempat','sub_kategori_tempat','tipe_tempat']] = [edit_area, edit_kat, edit_sub, edit_tipe]
                            outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
                            st.success("✅ Outlet updated successfully!"); st.rerun()
            else:
                st.info("No outlets available to edit")
        with s4:
            st.subheader("🗑️ Delete Outlet")
            if not outlet_mapping.empty:
                outlet_to_delete = st.selectbox("Select Outlet to Delete", outlet_mapping['outlet_name'].tolist())
                if outlet_to_delete and st.button("🗑️ Confirm Delete", type="secondary"):
                    outlet_mapping = outlet_mapping[outlet_mapping['outlet_name']!=outlet_to_delete]
                    outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
                    st.success("✅ Outlet deleted successfully!"); st.rerun()
            else:
                st.info("No outlets available to delete")
    with tab2:
        st.subheader("📋 Master Data Kategori & Sub Kategori")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Kategori Tempat**")
            st.dataframe(pd.DataFrame({'Kategori': KATEGORI_TEMPAT}), use_container_width=True, hide_index=True)
            with st.form("add_kategori_form"):
                nk = st.text_input("Nama Kategori Baru")
                if st.form_submit_button("Tambah Kategori"):
                    if nk and nk not in KATEGORI_TEMPAT:
                        KATEGORI_TEMPAT.append(nk); st.success(f"✅ Kategori '{nk}' berhasil ditambahkan!"); st.rerun()
                    else: st.error("❌ Kategori sudah ada atau kosong!")
        with c2:
            st.markdown("**Sub Kategori Tempat**")
            st.dataframe(pd.DataFrame({'Sub Kategori': SUB_KATEGORI_TEMPAT}), use_container_width=True, hide_index=True)
            with st.form("add_sub_kategori_form"):
                ns = st.text_input("Nama Sub Kategori Baru")
                if st.form_submit_button("Tambah Sub Kategori"):
                    if ns and ns not in SUB_KATEGORI_TEMPAT:
                        SUB_KATEGORI_TEMPAT.append(ns); st.success(f"✅ Sub Kategori '{ns}' berhasil ditambahkan!"); st.rerun()
                    else: st.error("❌ Sub Kategori sudah ada atau kosong!")
    with tab3:
        st.subheader("🗺️ Master Data Area (Kota & Kabupaten Indonesia)")
        a1, a2 = st.columns([2,1])
        with a1:
            st.markdown("**Daftar Area Indonesia**")
            st.dataframe(pd.DataFrame({'Area': INDONESIA_AREAS}), use_container_width=True, hide_index=True, height=400)
        with a2:
            with st.form("add_area_form"):
                na = st.text_input("Nama Kota/Kabupaten Baru")
                if st.form_submit_button("Tambah Area"):
                    if na and na not in INDONESIA_AREAS:
                        INDONESIA_AREAS.append(na); INDONESIA_AREAS.sort(); st.success(f"✅ Area '{na}' berhasil ditambahkan!"); st.rerun()
                    else: st.error("❌ Area sudah ada atau kosong!")
            st.info(f"📊 Total Area: {len(INDONESIA_AREAS)} kota/kabupaten")

def show_trend_analysis(df, config, processor, viz):
    st.title("📊 Analisis Trend Penjualan")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    st.subheader("🗺️ Analisis per Area"); st.plotly_chart(viz.create_area_analysis_chart(df), use_container_width=True)
    st.subheader("🏢 Analisis per Kategori Tempat"); st.plotly_chart(viz.create_kategori_analysis(df), use_container_width=True)
    st.subheader("🏠 Indoor vs Outdoor Analysis"); st.plotly_chart(viz.create_indoor_outdoor_comparison(df), use_container_width=True)
    st.subheader("🔥 Performance Heatmap"); st.plotly_chart(viz.create_heatmap(df), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1: st.subheader("📋 Summary by Area"); st.dataframe(processor.aggregate_by_area(df), use_container_width=True)
    with c2: st.subheader("📋 Summary by Category"); st.dataframe(processor.aggregate_by_kategori(df), use_container_width=True)

def show_conversion_analysis(df, config, processor, viz):
    st.title("🔄 Analisis Konversi & Awareness")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("📸➡️🖨️ Foto to Print", f"{df['conversion_rate'].mean():.1f}%")
    with c2: st.metric("🔓➡️🖨️ Unlock to Print", f"{df['unlock_to_print_rate'].mean():.1f}%")
    with c3: st.metric("🎯 Overall Conversion", f"{(df['print_qty'].sum()/df['foto_qty'].sum())*100:.1f}%")
    st.subheader("🔄 Conversion Funnel"); st.plotly_chart(viz.create_conversion_funnel(df), use_container_width=True)
    st.subheader("📊 Conversion Rate by Outlet")
    a,b = st.columns(2)
    with a:
        st.write("**🟢 High Conversion Outlets (>25%)**")
        hi = df[df['conversion_rate']>25].sort_values('conversion_rate', ascending=False)
        st.dataframe(hi[['outlet_name','conversion_rate','total_revenue']], use_container_width=True) if not hi.empty else st.info("No outlets with >25% conversion rate")
    with b:
        st.write("**🔴 Low Conversion Outlets (<15%)**")
        lo = df[df['conversion_rate']<15].sort_values('conversion_rate', ascending=True)
        st.dataframe(lo[['outlet_name','conversion_rate','total_revenue']], use_container_width=True) if not lo.empty else st.info("No outlets with <15% conversion rate")
    st.subheader("📢 Awareness Analysis")
    seg = df[(df['foto_qty']>df['foto_qty'].median()) & (df['conversion_rate']<df['conversion_rate'].median())]
    if not seg.empty:
        st.write("**⚠️ High Awareness, Low Conversion (Need Promotion)**")
        st.dataframe(seg[['outlet_name','foto_qty','conversion_rate','total_revenue']], use_container_width=True)
    st.subheader("📈 Conversion Trends"); st.plotly_chart(viz.create_trend_chart(df, 'conversion_rate'), use_container_width=True)

def show_outlet_ranking(df, config, processor):
    st.title("🏆 Ranking Outlet")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    cnt = df['outlet_status'].value_counts()
    a,b,c = st.columns(3)
    with a: st.metric("🟢 Keeper", cnt.get('Keeper',0))
    with b: st.metric("🟡 Optimasi", cnt.get('Optimasi',0))
    with c: st.metric("🔴 Relocate", cnt.get('Relocate',0))
    st.subheader("📊 Complete Outlet Ranking")
    ranked = df.sort_values('total_revenue', ascending=False).reset_index(drop=True)
    ranked['rank'] = range(1,len(ranked)+1)
    disp = ranked[['rank','outlet_name','area','kategori_tempat','total_revenue','conversion_rate','outlet_status']].copy()
    disp['total_revenue'] = disp['total_revenue'].apply(lambda x: config.format_currency(x))
    disp['conversion_rate'] = disp['conversion_rate'].apply(lambda x: f"{x:.1f}%")
    st.dataframe(disp, use_container_width=True)
    st.subheader("📋 Analysis by Status")
    t1,t2,t3 = st.tabs(["🟢 Keeper","🟡 Optimasi","🔴 Relocate"])
    with t1:
        k = df[df['outlet_status']=="Keeper"]
        st.dataframe(k[['outlet_name','area','total_revenue','conversion_rate']], use_container_width=True) if not k.empty else st.info("No outlets in Keeper status")
    with t2:
        o = df[df['outlet_status']=="Optimasi"]
        st.dataframe(o[['outlet_name','area','total_revenue','conversion_rate']], use_container_width=True) if not o.empty else st.info("No outlets in Optimasi status")
    with t3:
        r = df[df['outlet_status']=="Relocate"]
        st.dataframe(r[['outlet_name','area','total_revenue','conversion_rate']], use_container_width=True) if not r.empty else st.info("No outlets in Relocate status")

def show_period_comparison(df, config, processor, viz, current_period, compare_period):
    st.title("📅 Perbandingan Periode")
    if df.empty: st.error("❌ Data tidak tersedia."); return
    if current_period and compare_period:
        cur = df[df['periode']==current_period]; prev = df[df['periode']==compare_period]
        gm = calculate_growth_metrics(cur, prev)
        st.subheader("📈 Growth Metrics")
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Revenue Growth", f"{gm.get('revenue_growth',0):+.1f}%", delta=f"{gm.get('revenue_growth',0):+.1f}%")
        with c2: st.metric("Photo Growth", f"{gm.get('photo_growth',0):+.1f}%", delta=f"{gm.get('photo_growth',0):+.1f}%")
        with c3: st.metric("Conversion Change", f"{gm.get('conversion_change',0):+.1f}pp", delta=f"{gm.get('conversion_change',0):+.1f}pp")
        st.subheader("📊 Side-by-Side Comparison")
        a,b = st.columns(2)
        with a:
            m = processor.calculate_metrics(cur)
            st.write(f"**{current_period}**"); st.write(f"Revenue: {config.format_currency(m['total_revenue'])}"); st.write(f"Outlets: {m['total_outlets']}"); st.write(f"Avg Conversion: {m['avg_conversion']:.1f}%")
        with b:
            m = processor.calculate_metrics(prev)
            st.write(f"**{compare_period}**"); st.write(f"Revenue: {config.format_currency(m['total_revenue'])}"); st.write(f"Outlets: {m['total_outlets']}"); st.write(f"Avg Conversion: {m['avg_conversion']:.1f}%")
        st.subheader("📈 Trend Analysis"); st.plotly_chart(viz.create_trend_chart(df, 'total_revenue'), use_container_width=True)
    else:
        st.info("Pilih kedua periode di sidebar untuk membandingkan.")

# ================== UPLOAD (FIX: harga 0 valid) ==================
def show_upload_data(processor, config):
    st.title("📤 Upload Data Bulanan")
    st.info("📋 Upload file Excel bulanan untuk memperbarui dashboard")

    uploaded_file = st.file_uploader(
        "Choose Excel file",
        type=['xlsx','xls'],
        help="Header bebas: Outlet, Harga, Tanggal, Area, dst. Sistem otomatis memetakan & membersihkan."
    )

    if uploaded_file is not None:
        try:
            # Preview raw
            preview_df = pd.read_excel(uploaded_file, nrows=5)
            st.subheader("👀 Preview Data (Raw)")
            st.dataframe(preview_df, use_container_width=True)

            # Full → normalize → map → sanitize
            uploaded_file.seek(0)
            full_df = pd.read_excel(uploaded_file)
            full_df = normalize_headers(full_df)
            mapped_df, used_mapping = apply_column_mapping(full_df)
            mapped_df = sanitize_mapped_df(mapped_df)  # <- core fix: harga NaN/None jadi 0

            # Mapping info
            st.subheader("🧭 Column Mapping")
            if used_mapping:
                st.success("Kolom dimapping otomatis:\n" + "\n".join([f"- **{k}** → **{v}**" for k,v in used_mapping.items()]))
            else:
                st.warning("Tidak ada kolom yang perlu di-rename.")

            st.subheader("🔎 Preview Setelah Mapping & Sanitizing")
            st.dataframe(mapped_df.head(10), use_container_width=True)

            # Validate with sanitized df
            is_valid, message = validate_excel_file(mapped_df)
            if is_valid:
                st.success(f"✅ {message}")
                if st.button("🚀 Process and Update Dashboard"):
                    with st.spinner("Processing data..."):
                        excel_bytes = df_to_excel_bytes(mapped_df)  # kirim hasil bersih
                        processed_df = processor.process_uploaded_file(excel_bytes)
                        if processed_df is not None:
                            processed_df.to_csv("data/difotoin_dashboard_data.csv", index=False)
                            st.success("✅ Data berhasil diproses dan dashboard diperbarui!")
                            st.subheader("📊 Summary")
                            st.write(f"Total outlets: {len(processed_df)}")
                            st.write(f"Total revenue: {config.format_currency(processed_df['total_revenue'].sum())}")
                        else:
                            st.error("❌ Gagal memproses data")
            else:
                st.error(f"❌ {message}")
                st.caption("Harga 0 itu valid. Sistem sudah mengubah sel kosong/None menjadi 0.")
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

    st.subheader("📋 Format Data Guide")
    st.write("""
    **Header Excel yang didukung (otomatis dipetakan & dibersihkan):**
    - Outlet → `outlet_name`
    - Harga / Price / Amount → `harga` (kosong/None otomatis jadi **0**)
    - Tanggal / Date → `tanggal`
    - Area / Kota → `area`
    - Kategori / Kategori Tempat → `kategori_tempat`
    - Sub Kategori → `sub_kategori_tempat`
    - Tipe → `tipe_tempat`
    """)

# ================== BOOT ==================
if __name__ == "__main__":
    main()
