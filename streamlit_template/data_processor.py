import pandas as pd
import numpy as np
from datetime import datetime
import os

class DataProcessor:
    def __init__(self):
        self.data_path = "data/"
        if not os.path.exists(self.data_path):
            os.makedirs(self.data_path)
    
    def load_data(self):
        """Load main dashboard data"""
        try:
            df = pd.read_csv(f"{self.data_path}difotoin_dashboard_data.csv")
            return df
        except FileNotFoundError:
            # Return sample data if no data exists
            return self.create_sample_data()
    
    def create_sample_data(self):
        """Create sample data for testing"""
        np.random.seed(42)
        
        outlets = [
            "Mall Taman Anggrek", "Mall Kelapa Gading", "Ancol Beach", "Monas", 
            "Kota Tua", "Mall Central Park", "PIK Avenue", "Gandaria City",
            "Plaza Indonesia", "Grand Indonesia", "Mall Pondok Indah", "Senayan City"
        ]
        
        areas = ["Jakarta", "Jakarta", "Jakarta", "Jakarta", "Jakarta", "Jakarta", 
                "Jakarta", "Jakarta", "Jakarta", "Jakarta", "Jakarta", "Jakarta"]
        
        kategoris = ["Mall", "Mall", "Wisata", "Wisata", "Wisata", "Mall", 
                    "Mall", "Mall", "Mall", "Mall", "Mall", "Mall"]
        
        data = []
        for i, outlet in enumerate(outlets):
            # Generate data for 3 periods
            for period in ["2024-01", "2024-02", "2024-03"]:
                foto_qty = np.random.randint(100, 500)
                unlock_qty = int(foto_qty * np.random.uniform(0.6, 0.9))
                print_qty = int(unlock_qty * np.random.uniform(0.2, 0.4))
                revenue = print_qty * np.random.randint(20000, 35000)
                
                conversion_rate = (print_qty / foto_qty) * 100 if foto_qty > 0 else 0
                unlock_to_print_rate = (print_qty / unlock_qty) * 100 if unlock_qty > 0 else 0
                
                # Determine status based on revenue
                if revenue >= 15000000:  # 15M
                    status = "Keeper"
                elif revenue >= 8000000:  # 8M
                    status = "Optimasi"
                else:
                    status = "Relocate"
                
                data.append({
                    'outlet_name': outlet,
                    'periode': period,
                    'area': areas[i],
                    'kategori_tempat': kategoris[i],
                    'sub_kategori_tempat': "Food Court" if kategoris[i] == "Mall" else "Pantai",
                    'tipe_tempat': "Indoor" if kategoris[i] == "Mall" else "Outdoor",
                    'foto_qty': foto_qty,
                    'unlock_qty': unlock_qty,
                    'print_qty': print_qty,
                    'total_revenue': revenue,
                    'conversion_rate': conversion_rate,
                    'unlock_to_print_rate': unlock_to_print_rate,
                    'outlet_status': status
                })
        
        df = pd.DataFrame(data)
        # Save sample data
        df.to_csv(f"{self.data_path}difotoin_dashboard_data.csv", index=False)
        return df
    
    def load_outlet_mapping(self):
        """Load outlet mapping data"""
        try:
            return pd.read_csv(f"{self.data_path}difotoin_outlet_mapping.csv")
        except FileNotFoundError:
            return pd.DataFrame()
    
    def calculate_metrics(self, df):
        """Calculate key metrics from dataframe"""
        if df.empty:
            return {
                'total_revenue': 0,
                'total_outlets': 0,
                'avg_conversion': 0,
                'total_photos': 0
            }
        
        return {
            'total_revenue': df['total_revenue'].sum(),
            'total_outlets': df['outlet_name'].nunique(),
            'avg_conversion': df['conversion_rate'].mean(),
            'total_photos': df['foto_qty'].sum()
        }
    
    def filter_data(self, df, area, kategori, tipe, periode=None):
        """Apply filters to dataframe"""
        filtered_df = df.copy()
        
        if area != "Semua":
            filtered_df = filtered_df[filtered_df['area'] == area]
        
        if kategori != "Semua":
            filtered_df = filtered_df[filtered_df['kategori_tempat'] == kategori]
        
        if tipe != "Semua":
            filtered_df = filtered_df[filtered_df['tipe_tempat'] == tipe]
        
        if periode:
            filtered_df = filtered_df[filtered_df['periode'] == periode]
        
        return filtered_df
    
    def get_top_performers(self, df, n=5):
        """Get top N performing outlets"""
        return df.nlargest(n, 'total_revenue')
    
    def aggregate_by_area(self, df):
        """Aggregate data by area"""
        if df.empty:
            return pd.DataFrame()
        
        return df.groupby('area').agg({
            'total_revenue': 'sum',
            'foto_qty': 'sum',
            'conversion_rate': 'mean',
            'outlet_name': 'nunique'
        }).rename(columns={'outlet_name': 'outlet_count'}).round(2)
    
    def aggregate_by_kategori(self, df):
        """Aggregate data by kategori"""
        if df.empty:
            return pd.DataFrame()
        
        return df.groupby('kategori_tempat').agg({
            'total_revenue': 'sum',
            'foto_qty': 'sum',
            'conversion_rate': 'mean',
            'outlet_name': 'nunique'
        }).rename(columns={'outlet_name': 'outlet_count'}).round(2)
    
    def process_uploaded_file(self, uploaded_file):
        """Process uploaded Excel file"""
        try:
            df = pd.read_excel(uploaded_file)
            
            # Basic data processing and validation
            required_columns = ['outlet_name', 'harga']
            
            for col in required_columns:
                if col not in df.columns:
                    return None
            
            # Process and calculate metrics
            processed_df = self.process_raw_data(df)
            return processed_df
            
        except Exception as e:
            print(f"Error processing file: {e}")
            return None
    
    def process_raw_data(self, df):
        """Process raw data into dashboard format"""
        # This is a simplified version - implement based on your data structure
        processed_data = []
        
        for outlet in df['outlet_name'].unique():
            outlet_data = df[df['outlet_name'] == outlet]
            
            # Calculate aggregated metrics per outlet
            total_revenue = outlet_data['harga'].sum()
            foto_qty = len(outlet_data) * 10  # Simplified calculation
            unlock_qty = int(foto_qty * 0.8)
            print_qty = len(outlet_data)
            
            conversion_rate = (print_qty / foto_qty) * 100 if foto_qty > 0 else 0
            unlock_to_print_rate = (print_qty / unlock_qty) * 100 if unlock_qty > 0 else 0
            
            # Determine status
            if total_revenue >= 15000000:
                status = "Keeper"
            elif total_revenue >= 8000000:
                status = "Optimasi"
            else:
                status = "Relocate"
            
            processed_data.append({
                'outlet_name': outlet,
                'periode': '2024-03',  # Default current period
                'area': outlet_data['area'].iloc[0] if 'area' in outlet_data.columns else 'Jakarta',
                'kategori_tempat': outlet_data['kategori_tempat'].iloc[0] if 'kategori_tempat' in outlet_data.columns else 'Mall',
                'sub_kategori_tempat': 'Food Court',
                'tipe_tempat': 'Indoor',
                'foto_qty': foto_qty,
                'unlock_qty': unlock_qty,
                'print_qty': print_qty,
                'total_revenue': total_revenue,
                'conversion_rate': conversion_rate,
                'unlock_to_print_rate': unlock_to_print_rate,
                'outlet_status': status
            })
        
        return pd.DataFrame(processed_data)