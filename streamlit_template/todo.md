# Difotoin Dashboard Development Plan

## Overview
Create an interactive Streamlit dashboard for Difotoin photo machine sales analysis with the following features:

## Files to Create (Max 8 files):
1. **app.py** - Main Streamlit application with multi-page structure
2. **data_processor.py** - Data loading, cleaning, and transformation functions
3. **visualizations.py** - Chart and visualization components using Plotly
4. **utils.py** - Helper functions for calculations and metrics
5. **config.py** - Configuration management and admin settings
6. **requirements.txt** - Updated dependencies
7. **README.md** - Documentation and usage instructions
8. **styles.css** - Custom CSS for enhanced UI

## Key Features Implementation:
- **Main Dashboard**: Overview metrics, top performers, key insights
- **Trend Analysis**: Area-based sales trends, category performance, indoor vs outdoor
- **Conversion Analysis**: Photo → Unlock → Print funnel analysis
- **Outlet Ranking**: Keeper/Optimasi/Relocate categorization with admin controls
- **Period Comparison**: Monthly/Quarterly/Yearly analysis with growth rates
- **Data Upload**: Monthly Excel file processing capability
- **Admin Panel**: Configurable thresholds and settings

## Data Structure:
- Primary data: 148 records, 16 columns from difotoin_dashboard_data.csv
- Outlet mapping: 39 outlets with area/category classifications
- Revenue calculation: Sum of 'harga' column per outlet
- Conversion metrics: Print_Qty/Foto_Qty, Print_Qty/Unlock_Qty

## Technical Stack:
- Streamlit for web framework
- Plotly for interactive visualizations
- Pandas for data manipulation
- NumPy for calculations
- Streamlit-aggrid for data tables