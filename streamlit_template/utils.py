
def format_number(num):
    """Format large numbers with K, M suffixes"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    else:
        return str(int(num))

def format_currency(amount):
    """Format currency in Indonesian Rupiah"""
    return f"Rp {amount:,.0f}"

def calculate_growth_metrics(current_df, previous_df):
    """Calculate growth metrics between two periods"""
    if current_df.empty or previous_df.empty:
        return {
            'revenue_growth': 0,
            'photo_growth': 0,
            'conversion_change': 0
        }
    
    current_revenue = current_df['total_revenue'].sum()
    previous_revenue = previous_df['total_revenue'].sum()
    
    current_photos = current_df['foto_qty'].sum()
    previous_photos = previous_df['foto_qty'].sum()
    
    current_conversion = current_df['paid_per_photo_rate'].mean()
    previous_conversion = previous_df['paid_per_photo_rate'].mean()
    
    revenue_growth = ((current_revenue - previous_revenue) / previous_revenue) * 100 if previous_revenue > 0 else 0
    photo_growth = ((current_photos - previous_photos) / previous_photos) * 100 if previous_photos > 0 else 0
    conversion_change = current_conversion - previous_conversion
    
    return {
        'revenue_growth': revenue_growth,
        'photo_growth': photo_growth,
        'conversion_change': conversion_change
    }

def validate_excel_file(df):
    """Validate uploaded Excel file format"""
    required_columns = ['outlet_name', 'harga']
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        return False, f"Missing required columns: {', '.join(missing_columns)}"
    
    if df.empty:
        return False, "File is empty"
    
    if df['outlet_name'].isnull().any():
        return False, "Outlet name cannot be empty"
    
    if df['harga'].isnull().any():
        return False, "Harga cannot be empty"
    
    return True, "File format is valid"

def generate_insights(df, config):
    """Generate key insights from data"""
    if df.empty:
        return ["No data available for analysis"]

    insights = []

    total_revenue = df['total_revenue'].sum()
    insights.append(f"💰 Total revenue: {config.format_currency(total_revenue)} across {len(df)} outlets")

    status_counts = df['outlet_status'].value_counts()
    keeper_pct = (status_counts.get('Keeper', 0) / len(df)) * 100
    insights.append(f"🏆 {keeper_pct:.1f}% outlets are in Keeper status")

    avg_conversion = df['paid_per_photo_rate'].mean()
    high_conversion = df[df['paid_per_photo_rate'] > avg_conversion * 1.2]
    if not high_conversion.empty:
        insights.append(f"📈 {len(high_conversion)} outlets have above-average conversion rates")

    if 'area' in df.columns:
        area_revenue = df.groupby('area')['total_revenue'].sum()
        if not area_revenue.empty:
            top_area = area_revenue.idxmax()
            insights.append(f"🗺️ {top_area} is the highest performing area")

    low_performers = df[df['outlet_status'] == 'Relocate']
    if not low_performers.empty:
        insights.append(f"⚠️ {len(low_performers)} outlets need attention (Relocate status)")

    return insights