import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# Import custom modules
from data_processor import DataProcessor
from visualizations import Visualizations
from utils import *
from config import Config

# Page configuration
st.set_page_config(
    page_title="Difotoin Sales Dashboard",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Indonesian cities and regencies list
INDONESIA_AREAS = [
    "Jakarta Pusat", "Jakarta Utara", "Jakarta Barat", "Jakarta Selatan", "Jakarta Timur", "Jakarta",
    "Surabaya", "Bandung", "Medan", "Bekasi", "Tangerang", "Depok", "Semarang", "Palembang", "Makassar",
    "Batam", "Bogor", "Pekanbaru", "Bandar Lampung", "Malang", "Padang", "Denpasar", "Samarinda", "Tasikmalaya",
    "Balikpapan", "Pontianak", "Jambi", "Cimahi", "Sukabumi", "Bengkulu", "Mataram", "Yogyakarta", "Solo",
    "Purwokerto", "Magelang", "Tegal", "Pekalongan", "Kudus", "Jepara", "Demak", "Kendal", "Temanggung",
    "Wonosobo", "Purworejo", "Kebumen", "Banjarnegara", "Cilacap", "Banyumas", "Brebes", "Pemalang",
    "Batang", "Blora", "Rembang", "Pati", "Grobogan", "Sragen", "Karanganyar", "Wonogiri", "Sukoharjo",
    "Klaten", "Boyolali", "Sleman", "Bantul", "Kulon Progo", "Gunungkidul", "Madiun", "Ngawi", "Bojonegoro",
    "Tuban", "Lamongan", "Gresik", "Bangkalan", "Sampang", "Pamekasan", "Sumenep", "Kediri", "Blitar",
    "Tulungagung", "Trenggalek", "Nganjuk", "Jombang", "Mojokerto", "Pasuruan", "Probolinggo", "Situbondo",
    "Bondowoso", "Banyuwangi", "Jember", "Lumajang", "Malang", "Batu", "Bali", "Denpasar", "Badung",
    "Gianyar", "Klungkung", "Bangli", "Karangasem", "Buleleng", "Jembrana", "Tabanan"
]

KATEGORI_TEMPAT = [
    "Mall", "Wisata", "Restoran", "Hotel", "Komunitas", "Sekolah", "Universitas", "Rumah Sakit", 
    "Perkantoran", "Apartemen", "Cafe", "Gym", "Salon", "Spa", "Bioskop", "Taman", "Museum",
    "Galeri", "Event Space", "Co-working Space", "Lainnya"
]

SUB_KATEGORI_TEMPAT = [
    "Food Court", "Department Store", "Supermarket", "Boutique", "Electronics Store", "Bookstore",
    "Pantai", "Gunung", "Danau", "Taman Nasional", "Candi", "Kebun Binatang", "Waterpark",
    "Fine Dining", "Fast Food", "Street Food", "Bakery", "Coffee Shop", "Bar", "Lounge",
    "Budget Hotel", "Luxury Hotel", "Resort", "Homestay", "Guest House", "Hostel",
    "Tidak Terkategorisasi", "Lainnya"
]

# Custom CSS
st.markdown("""
<style>
    /* Base styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f2937 !important;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Status colors */
    .status-keeper { color: #10b981 !important; font-weight: bold; }
    .status-optimasi { color: #f59e0b !important; font-weight: bold; }
    .status-relocate { color: #ef4444 !important; font-weight: bold; }
    
    /* Insight box */
    .insight-box {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
        color: #1f2937 !important;
    }
    
    /* Period selector */
    .period-selector {
        padding: 1rem 0;
        margin-bottom: 1rem;
    }
    .period-selector h3 {
        color: #1f2937 !important;
        margin-bottom: 0.5rem;
    }
    
    /* Outlet table */
    .outlet-table {
        padding: 0;
        margin-bottom: 2rem;
    }
    
    /* Filter buttons */
    .filter-buttons {
        margin-bottom: 1rem;
    }
    .filter-buttons .stCheckbox > label {
        background-color: #f8fafc !important;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e5e7eb;
        color: #1f2937 !important;
        font-weight: 500;
    }
    .filter-buttons .stCheckbox > label:hover {
        background-color: #f1f5f9 !important;
    }
    
    /* Metrics styling */
    .stMetric > label {
        font-size: 0.8rem !important;
        color: #6b7280 !important;
    }
    .stMetric [data-testid="metric-value"] {
        font-size: 1.5rem !important;
        color: #1f2937 !important;
    }
    
    /* Comprehensive text color fixes */
    .stApp {
        color: #1f2937 !important;
    }
    
    /* Sidebar fixes */
    .stSidebar {
        background-color: #f8fafc !important;
    }
    .stSidebar * {
        color: #1f2937 !important;
    }
    .stSidebar .stSelectbox label,
    .stSidebar .stMarkdown,
    .stSidebar h1,
    .stSidebar h2,
    .stSidebar h3,
    .stSidebar p,
    .stSidebar div {
        color: #1f2937 !important;
    }
    
    /* Main content text fixes */
    .stMarkdown,
    .stMarkdown *,
    .stText,
    .stText *,
    h1, h2, h3, h4, h5, h6,
    p, span, div, label {
        color: #1f2937 !important;
    }
    
    /* Form elements */
    .stSelectbox label,
    .stTextInput label,
    .stNumberInput label,
    .stTextArea label {
        color: #1f2937 !important;
    }
    
    /* Dataframe text */
    .stDataFrame,
    .stDataFrame * {
        color: #1f2937 !important;
    }
    
    /* Tab text */
    .stTabs [data-baseweb="tab-list"] button {
        color: #1f2937 !important;
    }
    
    /* Button text */
    .stButton button {
        color: #1f2937 !important;
    }
    
    /* Info/warning/error text */
    .stAlert {
        color: #1f2937 !important;
    }
    
    /* Top performers card */
    .performer-card {
        padding: 0.5rem;
        margin: 0.25rem 0;
        border-radius: 0.25rem;
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
    }
    .performer-card strong {
        color: #1f2937 !important;
    }
    .performer-card span:not([class*="status-"]) {
        color: #1f2937 !important;
    }
    
    /* Subheader text */
    .stSubheader {
        color: #1f2937 !important;
    }
    
    /* General text override */
    * {
        color: #1f2937 !important;
    }
    
    /* Exception for status colors */
    .status-keeper,
    .status-optimasi, 
    .status-relocate {
        color: inherit !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize components
@st.cache_data
def load_app_data():
    processor = DataProcessor()
    return processor.load_data()

def create_period_selector(df):
    """Create static period selector at top - only for specific pages"""
    if df.empty:
        return None, None
    
    st.markdown('<div class="period-selector">', unsafe_allow_html=True)
    st.markdown("### 📅 Periode Selection")
    
    available_periods = sorted(df['periode'].unique())
    
    col1, col2 = st.columns(2)
    
    with col1:
        current_period = st.selectbox(
            "Current Period", 
            available_periods, 
            index=len(available_periods)-1 if available_periods else 0,
            key="current_period_top"
        )
    
    with col2:
        previous_periods = ["None"] + [p for p in available_periods if p != current_period]
        compare_period = st.selectbox(
            "Compare with", 
            previous_periods,
            key="compare_period_top"
        )
        compare_period = None if compare_period == "None" else compare_period
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return current_period, compare_period

def format_comparison_value(current_val, compare_val, is_percentage=False):
    """Format comparison value with proper icons and colors"""
    if compare_val == 0:
        return "➡️ 0.0%"
    
    if is_percentage:
        # For percentage values (like conversion rate), calculate difference in percentage points
        change = current_val - compare_val
        if change > 0:
            return f"🔺 +{change:.1f}pp"
        elif change < 0:
            return f"🔻 {change:.1f}pp"
        else:
            return "➡️ 0.0pp"
    else:
        # For absolute values (revenue, foto, unlock), calculate percentage change
        change_pct = ((current_val - compare_val) / compare_val) * 100
        if change_pct > 0:
            return f"🔺 +{change_pct:.1f}%"
        elif change_pct < 0:
            return f"🔻 {change_pct:.1f}%"
        else:
            return "➡️ 0.0%"

def format_number_with_dots(num):
    """Format number with dot separators (Indonesian style)"""
    return f"{int(num):,}".replace(",", ".")

def create_outlet_table(df, current_period, compare_period):
    """Create outlet table with filters and comparisons"""
    st.markdown('<div class="outlet-table">', unsafe_allow_html=True)
    st.markdown("### 🏪 Outlet Performance Table")
    
    # Filter buttons
    st.markdown('<div class="filter-buttons">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        show_keeper = st.checkbox("🟢 Keeper", value=True, key="filter_keeper")
    with col2:
        show_optimasi = st.checkbox("🟡 Optimasi", value=True, key="filter_optimasi")
    with col3:
        show_relocate = st.checkbox("🔴 Relocate", value=True, key="filter_relocate")
    with col4:
        show_all = st.checkbox("Show All", value=False, key="filter_all")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Filter data based on current period
    current_df = df[df['periode'] == current_period] if current_period else df
    
    # Apply status filters
    if not show_all:
        status_filters = []
        if show_keeper:
            status_filters.append('Keeper')
        if show_optimasi:
            status_filters.append('Optimasi')
        if show_relocate:
            status_filters.append('Relocate')
        
        if status_filters:
            current_df = current_df[current_df['outlet_status'].isin(status_filters)]
    
    # Get compare data if available
    compare_df = None
    if compare_period:
        compare_df = df[df['periode'] == compare_period]
    
    # Create table data
    table_data = []
    
    for _, row in current_df.iterrows():
        outlet_name = row['outlet_name']
        
        # Base data structure - keep numeric values for sorting
        row_data = {
            'Outlet': outlet_name,
            'Area': row['area'],
            'Omset': int(row['total_revenue']),  # Keep as numeric for sorting
            'Foto': int(row['foto_qty']),        # Keep as numeric for sorting
            'Unlock': int(row['unlock_qty']),    # Keep as numeric for sorting
            'Conversion': float(row['conversion_rate']),  # Keep as numeric for sorting
            'Status': row['outlet_status']
        }
        
        # Add compare columns only if compare_period exists
        if compare_period and compare_df is not None:
            compare_match = compare_df[compare_df['outlet_name'] == outlet_name]
            if not compare_match.empty:
                compare_row = compare_match.iloc[0]
                
                # Revenue comparison
                row_data['Omset Compare'] = format_comparison_value(
                    row['total_revenue'], compare_row['total_revenue']
                )
                
                # Photo comparison
                row_data['Foto Compare'] = format_comparison_value(
                    row['foto_qty'], compare_row['foto_qty']
                )
                
                # Unlock comparison
                row_data['Unlock Compare'] = format_comparison_value(
                    row['unlock_qty'], compare_row['unlock_qty']
                )
                
                # Conversion comparison (percentage points)
                row_data['Conversion Compare'] = format_comparison_value(
                    row['conversion_rate'], compare_row['conversion_rate'], is_percentage=True
                )
            else:
                # No compare data available for this outlet
                row_data['Omset Compare'] = "➡️ New Outlet"
                row_data['Foto Compare'] = "➡️ New Outlet"
                row_data['Unlock Compare'] = "➡️ New Outlet"
                row_data['Conversion Compare'] = "➡️ New Outlet"
        
        table_data.append(row_data)
    
    # Display table
    if table_data:
        table_df = pd.DataFrame(table_data)
        
        # Reorder columns to have compare columns next to their respective data columns
        if compare_period:
            column_order = [
                'Outlet', 'Area', 
                'Omset', 'Omset Compare',
                'Foto', 'Foto Compare', 
                'Unlock', 'Unlock Compare',
                'Conversion', 'Conversion Compare',
                'Status'
            ]
        else:
            column_order = [
                'Outlet', 'Area', 'Omset', 'Foto', 'Unlock', 'Conversion', 'Status'
            ]
        
        # Reorder dataframe columns
        table_df = table_df[column_order]
        
        # Style the dataframe
        def style_status(val):
            if val == 'Keeper':
                return 'color: #10b981; font-weight: bold'
            elif val == 'Optimasi':
                return 'color: #f59e0b; font-weight: bold'
            elif val == 'Relocate':
                return 'color: #ef4444; font-weight: bold'
            return ''
        
        styled_df = table_df.style.applymap(style_status, subset=['Status'])
        
        # Column configuration with proper formatting that maintains sorting
        column_config = {
            "Outlet": st.column_config.TextColumn(
                "Outlet",
                width="medium",
                pinned=True
            ),
            "Omset": st.column_config.NumberColumn(
                "Omset",
                format="%d"
            ),
            "Foto": st.column_config.NumberColumn(
                "Foto", 
                format="%d"
            ),
            "Unlock": st.column_config.NumberColumn(
                "Unlock",
                format="%d"
            ),
            "Conversion": st.column_config.NumberColumn(
                "Conversion",
                format="%.1f%%"
            )
        }
        
        # Add compare column configs if they exist
        if compare_period:
            column_config.update({
                "Omset Compare": st.column_config.TextColumn("Omset Compare", width="small"),
                "Foto Compare": st.column_config.TextColumn("Foto Compare", width="small"),
                "Unlock Compare": st.column_config.TextColumn("Unlock Compare", width="small"),
                "Conversion Compare": st.column_config.TextColumn("Conversion Compare", width="small")
            })
        
        # Display with proper column configuration that maintains sorting
        st.dataframe(
            styled_df, 
            use_container_width=True, 
            hide_index=True,
            column_config=column_config
        )
        
        # Add note about number formatting
        st.info("💡 **Tip**: Angka dalam tabel menggunakan format standar untuk mempertahankan fungsi sorting. Klik header kolom untuk mengurutkan data.")
        
    else:
        st.info("No outlets match the selected filters")
    
    st.markdown('</div>', unsafe_allow_html=True)

def main():
    # Initialize configuration and data processor
    config = Config()
    processor = DataProcessor()
    viz = Visualizations(config)
    
    # Load data
    df = load_app_data()
    
    # Sidebar
    st.sidebar.title("📸 Difotoin Dashboard")
    st.sidebar.markdown("---")
    
    # Navigation
    page = st.sidebar.selectbox(
        "Pilih Halaman",
        ["🏠 Dashboard Utama", "📊 Analisis Trend", "🔄 Analisis Konversi", 
         "🏆 Ranking Outlet", "📅 Perbandingan Periode", "🗃️ CRUD Data Outlet", "⚙️ Admin Panel", "📤 Upload Data"]
    )
    
    # Period selector - only show on specific pages
    current_period, compare_period = None, None
    if page in ["🏠 Dashboard Utama", "📅 Perbandingan Periode"]:
        current_period, compare_period = create_period_selector(df)
    
    # Filters
    st.sidebar.markdown("### 🔍 Filter Data")
    
    if not df.empty:
        areas = ["Semua"] + sorted(df['area'].unique().tolist())
        selected_area = st.sidebar.selectbox("Area", areas)
        
        kategoris = ["Semua"] + sorted(df['kategori_tempat'].unique().tolist())
        selected_kategori = st.sidebar.selectbox("Kategori Tempat", kategoris)
        
        tipes = ["Semua"] + sorted(df['tipe_tempat'].unique().tolist())
        selected_tipe = st.sidebar.selectbox("Tipe Tempat", tipes)
        
        # Apply filters
        filtered_df = processor.filter_data(df, selected_area, selected_kategori, selected_tipe, current_period)
    else:
        filtered_df = df
    
    # Main content based on selected page
    if page == "🏠 Dashboard Utama":
        show_main_dashboard(filtered_df, config, processor, viz, current_period, compare_period)
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

def show_main_dashboard(df, config, processor, viz, current_period, compare_period):
    """Main dashboard page"""
    st.markdown('<h1 class="main-header">📸 Difotoin Sales Dashboard</h1>', unsafe_allow_html=True)
    
    if df.empty:
        st.error("❌ Data tidak tersedia. Silakan upload data terlebih dahulu.")
        return
    
    # Key metrics with smaller text
    metrics = processor.calculate_metrics(df)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 Revenue",
            config.format_currency(metrics['total_revenue']),
            delta=None
        )
    
    with col2:
        st.metric(
            "🏪 Outlets",
            f"{metrics['total_outlets']}",
            delta=None
        )
    
    with col3:
        st.metric(
            "📈 Avg Conv Rate",
            f"{metrics['avg_conversion']:.1f}%",
            delta=None
        )
    
    with col4:
        st.metric(
            "📸 Photos",
            format_number(metrics['total_photos']),
            delta=None
        )
    
    st.markdown("---")
    
    # Outlet table (new feature)
    create_outlet_table(df, current_period, compare_period)
    
    # Status distribution
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📊 Distribusi Status Outlet")
        fig_status = viz.create_status_distribution(df)
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        st.subheader("🏆 Top 5 Performers")
        top_performers = processor.get_top_performers(df, 5)
        for idx, row in top_performers.iterrows():
            status_class = f"status-{row['outlet_status'].lower()}"
            st.markdown(f"""
            <div class="performer-card">
                <strong>{row['outlet_name']}</strong><br>
                <span class="{status_class}">{row['outlet_status']}</span> | 
                <span>{config.format_currency(row['total_revenue'])}</span> | 
                <span>{row['conversion_rate']:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)
    
    # Charts
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("💹 Revenue by Outlet")
        fig_revenue = viz.create_revenue_chart(df)
        st.plotly_chart(fig_revenue, use_container_width=True)
    
    with col2:
        st.subheader("🔄 Conversion Funnel")
        fig_funnel = viz.create_conversion_funnel(df)
        st.plotly_chart(fig_funnel, use_container_width=True)
    
    # Insights
    st.markdown("---")
    st.subheader("💡 Key Insights")
    insights = generate_insights(df, config)
    
    for insight in insights:
        st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

def show_outlet_crud(df, config, processor):
    """CRUD page for outlet data management with master data management"""
    st.title("🗃️ CRUD Data Outlet & Master Data")
    st.markdown("Manage outlet data dan master data: kategori, sub kategori, area")
    
    # Load outlet mapping
    outlet_mapping = processor.load_outlet_mapping()
    
    if outlet_mapping.empty:
        # Create default mapping from existing data
        outlets = df['outlet_name'].unique()
        outlet_mapping = pd.DataFrame({
            'outlet_name': outlets,
            'area': df.groupby('outlet_name')['area'].first().values,
            'kategori_tempat': df.groupby('outlet_name')['kategori_tempat'].first().values,
            'sub_kategori_tempat': df.groupby('outlet_name')['sub_kategori_tempat'].first().values,
            'tipe_tempat': df.groupby('outlet_name')['tipe_tempat'].first().values
        })
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["🏪 Outlet Management", "📋 Master Data Kategori", "🗺️ Master Data Area"])
    
    with tab1:
        # Outlet CRUD Operations
        subtab1, subtab2, subtab3, subtab4 = st.tabs(["📋 View All", "➕ Add New", "✏️ Edit", "🗑️ Delete"])
        
        with subtab1:
            st.subheader("📋 All Outlet Data")
            if not outlet_mapping.empty:
                st.dataframe(outlet_mapping, use_container_width=True)
            else:
                st.info("No outlet data available")
        
        with subtab2:
            st.subheader("➕ Add New Outlet")
            
            with st.form("add_outlet_form"):
                new_outlet_name = st.text_input("Outlet Name")
                new_area = st.selectbox("Area", INDONESIA_AREAS)
                new_kategori = st.selectbox("Kategori Tempat", KATEGORI_TEMPAT)
                new_sub_kategori = st.selectbox("Sub Kategori Tempat", SUB_KATEGORI_TEMPAT)
                new_tipe = st.selectbox("Tipe Tempat", ["Indoor", "Outdoor", "Semi-Outdoor"])
                
                submitted = st.form_submit_button("Add Outlet")
                
                if submitted and new_outlet_name:
                    # Check if outlet already exists
                    if new_outlet_name in outlet_mapping['outlet_name'].values:
                        st.error("❌ Outlet already exists!")
                    else:
                        # Add new outlet
                        new_row = pd.DataFrame({
                            'outlet_name': [new_outlet_name],
                            'area': [new_area],
                            'kategori_tempat': [new_kategori],
                            'sub_kategori_tempat': [new_sub_kategori],
                            'tipe_tempat': [new_tipe]
                        })
                        outlet_mapping = pd.concat([outlet_mapping, new_row], ignore_index=True)
                        
                        # Save to file
                        outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
                        st.success("✅ Outlet added successfully!")
                        st.rerun()
        
        with subtab3:
            st.subheader("✏️ Edit Outlet")
            
            if not outlet_mapping.empty:
                outlet_to_edit = st.selectbox("Select Outlet to Edit", outlet_mapping['outlet_name'].tolist())
                
                if outlet_to_edit:
                    current_data = outlet_mapping[outlet_mapping['outlet_name'] == outlet_to_edit].iloc[0]
                    
                    with st.form("edit_outlet_form"):
                        edit_area = st.selectbox("Area", INDONESIA_AREAS, 
                                               index=INDONESIA_AREAS.index(current_data['area']) if current_data['area'] in INDONESIA_AREAS else 0)
                        edit_kategori = st.selectbox("Kategori Tempat", KATEGORI_TEMPAT,
                                                   index=KATEGORI_TEMPAT.index(current_data['kategori_tempat']) if current_data['kategori_tempat'] in KATEGORI_TEMPAT else 0)
                        edit_sub_kategori = st.selectbox("Sub Kategori Tempat", SUB_KATEGORI_TEMPAT,
                                                       index=SUB_KATEGORI_TEMPAT.index(current_data['sub_kategori_tempat']) if current_data['sub_kategori_tempat'] in SUB_KATEGORI_TEMPAT else 0)
                        edit_tipe = st.selectbox("Tipe Tempat", ["Indoor", "Outdoor", "Semi-Outdoor"],
                                               index=["Indoor", "Outdoor", "Semi-Outdoor"].index(current_data['tipe_tempat']))
                        
                        submitted = st.form_submit_button("Update Outlet")
                        
                        if submitted:
                            # Update outlet data
                            outlet_mapping.loc[outlet_mapping['outlet_name'] == outlet_to_edit, 'area'] = edit_area
                            outlet_mapping.loc[outlet_mapping['outlet_name'] == outlet_to_edit, 'kategori_tempat'] = edit_kategori
                            outlet_mapping.loc[outlet_mapping['outlet_name'] == outlet_to_edit, 'sub_kategori_tempat'] = edit_sub_kategori
                            outlet_mapping.loc[outlet_mapping['outlet_name'] == outlet_to_edit, 'tipe_tempat'] = edit_tipe
                            
                            # Save to file
                            outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
                            st.success("✅ Outlet updated successfully!")
                            st.rerun()
            else:
                st.info("No outlets available to edit")
        
        with subtab4:
            st.subheader("🗑️ Delete Outlet")
            
            if not outlet_mapping.empty:
                outlet_to_delete = st.selectbox("Select Outlet to Delete", outlet_mapping['outlet_name'].tolist())
                
                if outlet_to_delete:
                    st.warning(f"⚠️ Are you sure you want to delete '{outlet_to_delete}'?")
                    
                    if st.button("🗑️ Confirm Delete", type="secondary"):
                        # Remove outlet
                        outlet_mapping = outlet_mapping[outlet_mapping['outlet_name'] != outlet_to_delete]
                        
                        # Save to file
                        outlet_mapping.to_csv("data/difotoin_outlet_mapping.csv", index=False)
                        st.success("✅ Outlet deleted successfully!")
                        st.rerun()
            else:
                st.info("No outlets available to delete")
    
    with tab2:
        st.subheader("📋 Master Data Kategori & Sub Kategori")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Kategori Tempat**")
            kategori_df = pd.DataFrame({'Kategori': KATEGORI_TEMPAT})
            st.dataframe(kategori_df, use_container_width=True, hide_index=True)
            
            st.markdown("**Tambah Kategori Baru**")
            with st.form("add_kategori_form"):
                new_kategori = st.text_input("Nama Kategori Baru")
                if st.form_submit_button("Tambah Kategori"):
                    if new_kategori and new_kategori not in KATEGORI_TEMPAT:
                        KATEGORI_TEMPAT.append(new_kategori)
                        st.success(f"✅ Kategori '{new_kategori}' berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.error("❌ Kategori sudah ada atau kosong!")
        
        with col2:
            st.markdown("**Sub Kategori Tempat**")
            sub_kategori_df = pd.DataFrame({'Sub Kategori': SUB_KATEGORI_TEMPAT})
            st.dataframe(sub_kategori_df, use_container_width=True, hide_index=True)
            
            st.markdown("**Tambah Sub Kategori Baru**")
            with st.form("add_sub_kategori_form"):
                new_sub_kategori = st.text_input("Nama Sub Kategori Baru")
                if st.form_submit_button("Tambah Sub Kategori"):
                    if new_sub_kategori and new_sub_kategori not in SUB_KATEGORI_TEMPAT:
                        SUB_KATEGORI_TEMPAT.append(new_sub_kategori)
                        st.success(f"✅ Sub Kategori '{new_sub_kategori}' berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.error("❌ Sub Kategori sudah ada atau kosong!")
    
    with tab3:
        st.subheader("🗺️ Master Data Area (Kota & Kabupaten Indonesia)")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("**Daftar Area Indonesia**")
            area_df = pd.DataFrame({'Area': INDONESIA_AREAS})
            st.dataframe(area_df, use_container_width=True, hide_index=True, height=400)
        
        with col2:
            st.markdown("**Tambah Area Baru**")
            with st.form("add_area_form"):
                new_area = st.text_input("Nama Kota/Kabupaten Baru")
                if st.form_submit_button("Tambah Area"):
                    if new_area and new_area not in INDONESIA_AREAS:
                        INDONESIA_AREAS.append(new_area)
                        INDONESIA_AREAS.sort()  # Keep alphabetical order
                        st.success(f"✅ Area '{new_area}' berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.error("❌ Area sudah ada atau kosong!")
            
            st.markdown("**Info**")
            st.info(f"📊 Total Area: {len(INDONESIA_AREAS)} kota/kabupaten")

def show_trend_analysis(df, config, processor, viz):
    """Trend analysis page"""
    st.title("📊 Analisis Trend Penjualan")
    
    if df.empty:
        st.error("❌ Data tidak tersedia.")
        return
    
    # Area analysis
    st.subheader("🗺️ Analisis per Area")
    fig_area = viz.create_area_analysis_chart(df)
    st.plotly_chart(fig_area, use_container_width=True)
    
    # Category analysis
    st.subheader("🏢 Analisis per Kategori Tempat")
    fig_kategori = viz.create_kategori_analysis(df)
    st.plotly_chart(fig_kategori, use_container_width=True)
    
    # Indoor vs Outdoor
    st.subheader("🏠 Indoor vs Outdoor Analysis")
    fig_indoor_outdoor = viz.create_indoor_outdoor_comparison(df)
    st.plotly_chart(fig_indoor_outdoor, use_container_width=True)
    
    # Heatmap
    st.subheader("🔥 Performance Heatmap")
    fig_heatmap = viz.create_heatmap(df)
    st.plotly_chart(fig_heatmap, use_container_width=True)
    
    # Summary tables
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Summary by Area")
        area_summary = processor.aggregate_by_area(df)
        st.dataframe(area_summary, use_container_width=True)
    
    with col2:
        st.subheader("📋 Summary by Category")
        kategori_summary = processor.aggregate_by_kategori(df)
        st.dataframe(kategori_summary, use_container_width=True)

def show_conversion_analysis(df, config, processor, viz):
    """Conversion analysis page"""
    st.title("🔄 Analisis Konversi & Awareness")
    
    if df.empty:
        st.error("❌ Data tidak tersedia.")
        return
    
    # Conversion metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        avg_foto_to_print = df['conversion_rate'].mean()
        st.metric("📸➡️🖨️ Foto to Print", f"{avg_foto_to_print:.1f}%")
    
    with col2:
        avg_unlock_to_print = df['unlock_to_print_rate'].mean()
        st.metric("🔓➡️🖨️ Unlock to Print", f"{avg_unlock_to_print:.1f}%")
    
    with col3:
        total_conversion = (df['print_qty'].sum() / df['foto_qty'].sum()) * 100
        st.metric("🎯 Overall Conversion", f"{total_conversion:.1f}%")
    
    # Conversion funnel
    st.subheader("🔄 Conversion Funnel")
    fig_funnel = viz.create_conversion_funnel(df)
    st.plotly_chart(fig_funnel, use_container_width=True)
    
    # Conversion by outlet
    st.subheader("📊 Conversion Rate by Outlet")
    
    # High vs Low conversion outlets
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**🟢 High Conversion Outlets (>25%)**")
        high_conv = df[df['conversion_rate'] > 25].sort_values('conversion_rate', ascending=False)
        if not high_conv.empty:
            st.dataframe(high_conv[['outlet_name', 'conversion_rate', 'total_revenue']], use_container_width=True)
        else:
            st.info("No outlets with >25% conversion rate")
    
    with col2:
        st.write("**🔴 Low Conversion Outlets (<15%)**")
        low_conv = df[df['conversion_rate'] < 15].sort_values('conversion_rate', ascending=True)
        if not low_conv.empty:
            st.dataframe(low_conv[['outlet_name', 'conversion_rate', 'total_revenue']], use_container_width=True)
        else:
            st.info("No outlets with <15% conversion rate")
    
    # Awareness analysis
    st.subheader("📢 Awareness Analysis")
    
    # High awareness, low conversion (need promotion)
    high_foto_low_conv = df[(df['foto_qty'] > df['foto_qty'].median()) & 
                           (df['conversion_rate'] < df['conversion_rate'].median())]
    
    if not high_foto_low_conv.empty:
        st.write("**⚠️ High Awareness, Low Conversion (Need Promotion)**")
        st.dataframe(high_foto_low_conv[['outlet_name', 'foto_qty', 'conversion_rate', 'total_revenue']], 
                    use_container_width=True)
    
    # Conversion trend chart
    st.subheader("📈 Conversion Trends")
    fig_trend = viz.create_trend_chart(df, 'conversion_rate')
    st.plotly_chart(fig_trend, use_container_width=True)

def show_outlet_ranking(df, config, processor):
    """Outlet ranking page"""
    st.title("🏆 Ranking Outlet")
    
    if df.empty:
        st.error("❌ Data tidak tersedia.")
        return
    
    # Status summary
    status_counts = df['outlet_status'].value_counts()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🟢 Keeper", status_counts.get('Keeper', 0))
    with col2:
        st.metric("🟡 Optimasi", status_counts.get('Optimasi', 0))
    with col3:
        st.metric("🔴 Relocate", status_counts.get('Relocate', 0))
    
    # Ranking table
    st.subheader("📊 Complete Outlet Ranking")
    
    # Sort by revenue
    ranked_df = df.sort_values('total_revenue', ascending=False).reset_index(drop=True)
    ranked_df['rank'] = range(1, len(ranked_df) + 1)
    
    # Display table with formatting
    display_df = ranked_df[['rank', 'outlet_name', 'area', 'kategori_tempat', 
                           'total_revenue', 'conversion_rate', 'outlet_status']].copy()
    
    # Format revenue
    display_df['total_revenue'] = display_df['total_revenue'].apply(
        lambda x: config.format_currency(x)
    )
    display_df['conversion_rate'] = display_df['conversion_rate'].apply(
        lambda x: f"{x:.1f}%"
    )
    
    st.dataframe(display_df, use_container_width=True)
    
    # Status-wise analysis
    st.subheader("📋 Analysis by Status")
    
    tab1, tab2, tab3 = st.tabs(["🟢 Keeper", "🟡 Optimasi", "🔴 Relocate"])
    
    with tab1:
        keeper_df = df[df['outlet_status'] == 'Keeper']
        if not keeper_df.empty:
            st.write(f"**{len(keeper_df)} outlets in Keeper status**")
            st.dataframe(keeper_df[['outlet_name', 'area', 'total_revenue', 'conversion_rate']], 
                        use_container_width=True)
        else:
            st.info("No outlets in Keeper status")
    
    with tab2:
        optimasi_df = df[df['outlet_status'] == 'Optimasi']
        if not optimasi_df.empty:
            st.write(f"**{len(optimasi_df)} outlets in Optimasi status**")
            st.dataframe(optimasi_df[['outlet_name', 'area', 'total_revenue', 'conversion_rate']], 
                        use_container_width=True)
        else:
            st.info("No outlets in Optimasi status")
    
    with tab3:
        relocate_df = df[df['outlet_status'] == 'Relocate']
        if not relocate_df.empty:
            st.write(f"**{len(relocate_df)} outlets in Relocate status**")
            st.dataframe(relocate_df[['outlet_name', 'area', 'total_revenue', 'conversion_rate']], 
                        use_container_width=True)
            
            st.warning("⚠️ These outlets may need strategic review for relocation or optimization.")
        else:
            st.info("No outlets in Relocate status")

def show_period_comparison(df, config, processor, viz, current_period, compare_period):
    """Period comparison page"""
    st.title("📅 Perbandingan Periode")
    
    if df.empty:
        st.error("❌ Data tidak tersedia.")
        return
    
    if current_period and compare_period:
        current_df = df[df['periode'] == current_period]
        previous_df = df[df['periode'] == compare_period]
        
        # Calculate growth metrics
        growth_metrics = calculate_growth_metrics(current_df, previous_df)
        
        # Display growth metrics
        st.subheader("📈 Growth Metrics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            revenue_growth = growth_metrics.get('revenue_growth', 0)
            delta_color = "normal" if revenue_growth >= 0 else "inverse"
            st.metric(
                "Revenue Growth",
                f"{revenue_growth:+.1f}%",
                delta=f"{revenue_growth:+.1f}%"
            )
        
        with col2:
            photo_growth = growth_metrics.get('photo_growth', 0)
            st.metric(
                "Photo Growth",
                f"{photo_growth:+.1f}%",
                delta=f"{photo_growth:+.1f}%"
            )
        
        with col3:
            conversion_change = growth_metrics.get('conversion_change', 0)
            st.metric(
                "Conversion Change",
                f"{conversion_change:+.1f}pp",
                delta=f"{conversion_change:+.1f}pp"
            )
        
        # Side-by-side comparison
        st.subheader("📊 Side-by-Side Comparison")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**{current_period}**")
            current_metrics = processor.calculate_metrics(current_df)
            st.write(f"Revenue: {config.format_currency(current_metrics['total_revenue'])}")
            st.write(f"Outlets: {current_metrics['total_outlets']}")
            st.write(f"Avg Conversion: {current_metrics['avg_conversion']:.1f}%")
        
        with col2:
            st.write(f"**{compare_period}**")
            previous_metrics = processor.calculate_metrics(previous_df)
            st.write(f"Revenue: {config.format_currency(previous_metrics['total_revenue'])}")
            st.write(f"Outlets: {previous_metrics['total_outlets']}")
            st.write(f"Avg Conversion: {previous_metrics['avg_conversion']:.1f}%")
        
        # Trend charts
        st.subheader("📈 Trend Analysis")
        fig_trend = viz.create_trend_chart(df, 'total_revenue')
        st.plotly_chart(fig_trend, use_container_width=True)
    
    else:
        st.info("Select periods to compare using the period selector above")

def show_admin_panel(config):
    """Admin panel for configuration"""
    st.title("⚙️ Admin Panel")
    
    st.subheader("🎯 Threshold Configuration")
    
    # Current thresholds
    current_keeper = config.get_threshold('keeper_minimum')
    current_optimasi = config.get_threshold('optimasi_minimum')
    
    col1, col2 = st.columns(2)
    
    with col1:
        new_keeper = st.number_input(
            "Keeper Minimum (IDR)",
            min_value=0,
            value=current_keeper,
            step=1000000,
            format="%d"
        )
    
    with col2:
        new_optimasi = st.number_input(
            "Optimasi Minimum (IDR)",
            min_value=0,
            value=current_optimasi,
            step=1000000,
            format="%d"
        )
    
    if st.button("💾 Save Thresholds"):
        config.set_threshold('keeper_minimum', new_keeper)
        config.set_threshold('optimasi_minimum', new_optimasi)
        
        if config.save_config():
            st.success("✅ Thresholds updated successfully!")
            st.rerun()
        else:
            st.error("❌ Failed to save thresholds")
    
    # Display current configuration
    st.subheader("📋 Current Configuration")
    st.json(config.config)
    
    # System information
    st.subheader("ℹ️ System Information")
    st.write(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    st.write(f"**Keeper Threshold:** {config.format_currency(config.get_threshold('keeper_minimum'))}")
    st.write(f"**Optimasi Threshold:** {config.format_currency(config.get_threshold('optimasi_minimum'))}")

def show_upload_data(processor, config):
    """Data upload page"""
    st.title("📤 Upload Data Bulanan")
    
    st.info("📋 Upload file Excel bulanan untuk memperbarui dashboard")
    
    uploaded_file = st.file_uploader(
        "Choose Excel file",
        type=['xlsx', 'xls'],
        help="Upload file Excel dengan format yang sesuai"
    )
    
    if uploaded_file is not None:
        try:
            # Preview file
            st.subheader("👀 Preview Data")
            preview_df = pd.read_excel(uploaded_file, nrows=5)
            st.dataframe(preview_df)
            
            # Validate file
            full_df = pd.read_excel(uploaded_file)
            is_valid, message = validate_excel_file(full_df)
            
            if is_valid:
                st.success(f"✅ {message}")
                
                if st.button("🚀 Process and Update Dashboard"):
                    with st.spinner("Processing data..."):
                        processed_df = processor.process_uploaded_file(uploaded_file)
                        
                        if processed_df is not None:
                            # Save processed data
                            processed_df.to_csv("data/difotoin_dashboard_data.csv", index=False)
                            st.success("✅ Data berhasil diproses dan dashboard diperbarui!")
                            
                            # Show summary
                            st.subheader("📊 Summary")
                            st.write(f"Total outlets: {len(processed_df)}")
                            st.write(f"Total revenue: {config.format_currency(processed_df['total_revenue'].sum())}")
                            
                        else:
                            st.error("❌ Gagal memproses data")
            else:
                st.error(f"❌ {message}")
                
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")
    
    # Data format guide
    st.subheader("📋 Format Data Guide")
    st.write("""
    **Required columns:**
    - `outlet_name`: Nama outlet
    - `harga`: Revenue per transaksi
    
    **Optional columns:**
    - `tanggal`: Tanggal transaksi
    - `area`: Area/kota outlet
    - `kategori_tempat`: Kategori tempat (Mall, Wisata, etc.)
    """)

if __name__ == "__main__":
    main()