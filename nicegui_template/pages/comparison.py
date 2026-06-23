"""
📅 Perbandingan Periode — compare metrics between two periods.
"""
from nicegui import ui
import pandas as pd
import numpy as np

from services.dashboard_adapter import get_adapter

CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 20px;"
MV = "font-size: 1.3rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"
ST = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"


def create_page(container: ui.column):
    adapter = get_adapter()
    df = adapter.load_data()

    with container:
        ui.label("📅 Perbandingan Periode").classes("text-2xl font-bold text-white mb-4")

        if df.empty or "periode" not in df.columns:
            ui.label("❌ Data tidak tersedia.").classes("text-red-400")
            return

        base = df.copy()
        periods = sorted(base["periode"].dropna().astype(str).unique().tolist())

        with ui.row().classes("w-full gap-4 items-center mb-6"):
            cur_sel = ui.select(periods, value=periods[-1] if periods else None, label="Periode Saat Ini").props("dense outlined dark").classes("flex-1")
            prev_sel = ui.select(periods, value=periods[-2] if len(periods) > 1 else None, label="Periode Sebelumnya").props("dense outlined dark").classes("flex-1")

        content_col = ui.column().classes("w-full")

        def update():
            content_col.clear()
            cp = cur_sel.value
            pp = prev_sel.value
            if not cp or not pp or cp == pp:
                with content_col:
                    ui.label("Pilih dua periode berbeda untuk membandingkan.").classes("text-gray-400 italic")
                return

            cur = base[base["periode"] == cp]
            prev = base[base["periode"] == pp]

            cur_rev = float(cur["total_revenue"].sum()) if "total_revenue" in cur.columns else 0
            prev_rev = float(prev["total_revenue"].sum()) if "total_revenue" in prev.columns else 0
            rev_growth = ((cur_rev - prev_rev) / prev_rev * 100) if prev_rev else 0

            cur_photo = int(cur["foto_qty"].sum()) if "foto_qty" in cur.columns else 0
            prev_photo = int(prev["foto_qty"].sum()) if "foto_qty" in prev.columns else 0
            photo_growth = ((cur_photo - prev_photo) / prev_photo * 100) if prev_photo else 0

            cur_conv = float(cur["conversion_rate"].mean()) if "conversion_rate" in cur.columns else 0
            prev_conv = float(prev["conversion_rate"].mean()) if "conversion_rate" in prev.columns else 0
            conv_change = cur_conv - prev_conv

            with content_col:
                ui.label(f"📈 Growth Metrics: {cp} vs {pp}").classes("text-lg font-semibold text-white mb-4")

                with ui.row().classes("w-full gap-4 mb-6"):
                    metrics = [
                        ("💰 Revenue Growth", f"{rev_growth:+.1f}%", "#89b4fa"),
                        ("📸 Photo Growth", f"{photo_growth:+.1f}%", "#a6e3a1"),
                        ("📈 Conversion Change", f"{conv_change:+.1f}pp", "#f9e2af"),
                    ]
                    for lbl, val, color in metrics:
                        with ui.card().classes("flex-1").style(CARD):
                            ui.label(lbl).style(ML)
                            ui.label(val).style(MV)

                ui.separator().classes("mb-4")
                ui.label("📊 Revenue by Outlet — Perbandingan").style(ST)

                # Comparison bar chart
                merged = cur.merge(prev, on="outlet_name", how="outer", suffixes=("_cur", "_prev"))
                merged = merged.fillna(0)
                top = merged.nlargest(10, "total_revenue_cur") if "total_revenue_cur" in merged.columns else merged.head(10)

                labels = top["outlet_name"].tolist()
                cur_vals = [float(top[f"total_revenue_cur"].iloc[i]) if f"total_revenue_cur" in top.columns else 0 for i in range(len(top))]
                prev_vals = [float(top[f"total_revenue_prev"].iloc[i]) if f"total_revenue_prev" in top.columns else 0 for i in range(len(top))]

                ui.echart({
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": [cp, pp], "textStyle": {"color": "#cdd6f4"}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
                    "xAxis": {"type": "category", "data": labels,
                              "axisLabel": {"color": "#a6adc8", "fontSize": 9, "rotate": 30},
                              "axisLine": {"lineStyle": {"color": "#45475a"}}},
                    "yAxis": {"type": "value", "axisLabel": {"color": "#a6adc8"},
                              "splitLine": {"lineStyle": {"color": "#313244"}}},
                    "series": [
                        {"name": cp, "type": "bar", "data": cur_vals, "itemStyle": {"color": "#89b4fa"}, "barMaxWidth": 24},
                        {"name": pp, "type": "bar", "data": prev_vals, "itemStyle": {"color": "#45475a"}, "barMaxWidth": 24},
                    ],
                    "backgroundColor": "transparent", "textStyle": {"color": "#cdd6f4"},
                }).classes("w-full h-[350px]")

        cur_sel.on("change", update)
        prev_sel.on("change", update)
        update()
