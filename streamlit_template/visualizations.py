import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

class Visualizations:
    def __init__(self, config):
        self.config = config
        self.colors = {
            'keeper': '#10b981',
            'optimasi': '#f59e0b', 
            'relocate': '#ef4444',
            'primary': '#3b82f6',
            'secondary': '#6b7280'
        }
    
    def create_status_distribution(self, df):
        """Create status distribution pie chart"""
        if df.empty:
            return go.Figure()
        
        status_counts = df['outlet_status'].value_counts()
        
        colors = [self.colors['keeper'], self.colors['optimasi'], self.colors['relocate']]
        
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Distribusi Status Outlet",
            color_discrete_sequence=colors
        )
        
        fig.update_layout(
            showlegend=True,
            height=400,
            font=dict(size=12)
        )
        
        return fig
    
    def create_revenue_chart(self, df):
        """Create revenue bar chart"""
        if df.empty:
            return go.Figure()
        
        # Top 10 outlets by revenue
        top_outlets = df.nlargest(10, 'total_revenue')
        
        # Color by status
        colors = []
        for status in top_outlets['outlet_status']:
            if status == 'Keeper':
                colors.append(self.colors['keeper'])
            elif status == 'Optimasi':
                colors.append(self.colors['optimasi'])
            else:
                colors.append(self.colors['relocate'])
        
        fig = go.Figure(data=[
            go.Bar(
                x=top_outlets['outlet_name'],
                y=top_outlets['total_revenue'],
                marker_color=colors,
                text=top_outlets['total_revenue'].apply(lambda x: f"Rp {x/1000000:.1f}M"),
                textposition='outside'
            )
        ])
        
        fig.update_layout(
            title="Top 10 Revenue by Outlet",
            xaxis_title="Outlet",
            yaxis_title="Revenue (IDR)",
            height=500,
            xaxis_tickangle=-45
        )
        
        return fig
    
    def create_conversion_funnel(self, df):
        """Create conversion funnel chart"""
        if df.empty:
            return go.Figure()
        
        total_foto = df['foto_qty'].sum()
        total_unlock = df['unlock_qty'].sum()
        total_print = df['print_qty'].sum()
        
        fig = go.Figure(go.Funnel(
            y = ["Foto Taken", "Unlocked", "Printed"],
            x = [total_foto, total_unlock, total_print],
            textinfo = "value+percent initial"
        ))
        
        fig.update_layout(
            title="Conversion Funnel",
            height=400
        )
        
        return fig
    
    def create_area_analysis_chart(self, df):
        """Create area analysis chart"""
        if df.empty:
            return go.Figure()
        
        area_data = df.groupby('area').agg({
            'total_revenue': 'sum',
            'outlet_name': 'nunique'
        }).reset_index()
        
        fig = px.bar(
            area_data,
            x='area',
            y='total_revenue',
            title="Revenue by Area",
            color='total_revenue',
            color_continuous_scale='Blues'
        )
        
        fig.update_layout(height=400)
        return fig
    
    def create_kategori_analysis(self, df):
        """Create category analysis chart"""
        if df.empty:
            return go.Figure()
        
        kategori_data = df.groupby('kategori_tempat').agg({
            'total_revenue': 'sum',
            'conversion_rate': 'mean'
        }).reset_index()
        
        fig = px.scatter(
            kategori_data,
            x='total_revenue',
            y='conversion_rate',
            size='total_revenue',
            color='kategori_tempat',
            title="Revenue vs Conversion Rate by Category",
            hover_name='kategori_tempat'
        )
        
        fig.update_layout(height=400)
        return fig
    
    def create_indoor_outdoor_comparison(self, df):
        """Create indoor vs outdoor comparison"""
        if df.empty:
            return go.Figure()
        
        tipe_data = df.groupby('tipe_tempat').agg({
            'total_revenue': 'sum',
            'conversion_rate': 'mean',
            'outlet_name': 'nunique'
        }).reset_index()
        
        fig = px.bar(
            tipe_data,
            x='tipe_tempat',
            y='total_revenue',
            title="Revenue by Location Type",
            color='tipe_tempat',
            color_discrete_sequence=['#3b82f6', '#10b981', '#f59e0b']
        )
        
        fig.update_layout(height=400)
        return fig
    
    def create_heatmap(self, df):
        """Create performance heatmap"""
        if df.empty:
            return go.Figure()
        
        # Create pivot table for heatmap
        pivot_data = df.pivot_table(
            values='total_revenue',
            index='area',
            columns='kategori_tempat',
            aggfunc='sum',
            fill_value=0
        )
        
        fig = px.imshow(
            pivot_data,
            title="Revenue Heatmap: Area vs Category",
            color_continuous_scale='Blues',
            aspect="auto"
        )
        
        fig.update_layout(height=400)
        return fig
    
    def create_trend_chart(self, df, metric):
        """Create trend chart for specified metric"""
        if df.empty:
            return go.Figure()
        
        trend_data = df.groupby('periode')[metric].sum().reset_index()
        
        fig = px.line(
            trend_data,
            x='periode',
            y=metric,
            title=f"{metric.title()} Trend Over Time",
            markers=True
        )
        
        fig.update_layout(height=400)
        return fig