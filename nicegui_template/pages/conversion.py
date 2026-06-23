"""
🔄 Analisis Konversi & Awareness — conversion funnel analysis.
"""
from nicegui import ui
import pandas as pd
import numpy as np

from services.dashboard_adapter import get_adapter

CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"
ST = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"


def create_page(container: ui.column):
    adapter = get_adapter()
    df = adapter.load_data()

    with container:
        ui.label("🔄 Analisis Konversi & Awareness").classes("text-2xl font-bold text-white mb-4")

        if df.empty:
            ui.label("❌ Data tidak tersedia.").classes("text-red-400")
            return

        base = df.copy()
        for col in ["foto_qty", "unlock_qty", "print_qty"]:
            base[col] = pd.to_numeric(base.get(col, 0), errors="coerce").fillna(0)

        # KPI Cards
        foto_sum = base["foto_qty"].sum()
        unlock_sum = base["unlock_qty"].sum()
        print_sum = base["print_qty"].sum()
        avg_conv = base["conversion_rate"].mean() if "conversion_rate" in base.columns else 0
        unlock_print_rate = (print_sum / unlock_sum * 100) if unlock_sum > 0 else 0
        overall_conv = (print_sum / foto_sum * 100) if foto_sum > 0 else 0

        with ui.row().classes("w-full gap-4 mb-6"):
            for lbl, val in [
                ("📸➡️🖨️ Foto to Print", f"{avg_conv:.1f}%"),
                ("🔓➡️🖨️ Unlock to Print", f"{unlock_print_rate:.1f}%"),
                ("🎯 Overall Conversion", f"{overall_conv:.1f}%"),
            ]:
                with ui.card().classes("flex-1").style(CARD):
                    ui.label(lbl).style(ML)
                    ui.label(val).style(MV)

        ui.separator().classes("mb-4")

        # Conversion Funnel
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label("🔄 Conversion Funnel").style(ST)
            maxv = max(foto_sum, unlock_sum, print_sum) or 1
            ui.echart({
                "tooltip": {"trigger": "item", "formatter": "{b}: {c}"},
                "series": [{
                    "type": "funnel", "left": "10%", "top": 20, "bottom": 20, "width": "80%",
                    "min": 0, "max": maxv, "minSize": "0%", "maxSize": "100%",
                    "sort": "descending", "gap": 2,
                    "label": {"show": True, "position": "inside", "color": "#fff", "fontSize": 12,
                              "formatter": "{b}: {c}"},
                    "itemStyle": {"borderColor": "#1e1e2e", "borderWidth": 2},
                    "data": [
                        {"value": int(foto_sum), "name": "📸 Foto Taken", "itemStyle": {"color": "#89b4fa"}},
                        {"value": int(unlock_sum), "name": "🔓 Unlocked", "itemStyle": {"color": "#f9e2af"}},
                        {"value": int(print_sum), "name": "🖨️ Printed", "itemStyle": {"color": "#a6e3a1"}},
                    ],
                }],
                "backgroundColor": "transparent", "textStyle": {"color": "#cdd6f4"},
            }).classes("w-full h-[300px]")

        ui.separator().classes("mb-4")

        # High/Low Conversion by Outlet
        ui.label("📊 Conversion Rate by Outlet").classes("text-lg font-semibold text-white mb-3")
        with ui.row().classes("w-full gap-4 mb-6"):
            # High conversion
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🟢 High Conversion Outlets (>25%)").classes("text-sm font-semibold text-green-400 mb-2")
                hi = base[base["conversion_rate"] > 25].sort_values("conversion_rate", ascending=False)
                if not hi.empty:
                    hd = hi[["outlet_name", "conversion_rate", "total_revenue"]].copy()
                    hd["conversion_rate"] = hd["conversion_rate"].apply(lambda x: f"{x:.1f}%")
                    hd["total_revenue"] = hd["total_revenue"].apply(adapter.format_currency)
                    cols = [{"name": c, "label": c.replace("_", " ").title(), "field": c} for c in hd.columns]
                    ui.table(rows=hd.to_dict("records"), columns=cols, pagination={"rowsPerPage": 12}).classes("w-full").props("dark flat dense")
                else:
                    ui.label("No outlets with >25% conversion rate").classes("text-gray-400 italic text-xs")
            # Low conversion
            with ui.card().classes("flex-1").style(CARD):
                ui.label("🔴 Low Conversion Outlets (<15%)").classes("text-sm font-semibold text-red-400 mb-2")
                lo = base[base["conversion_rate"] < 15].sort_values("conversion_rate", ascending=True)
                if not lo.empty:
                    ld = lo[["outlet_name", "conversion_rate", "total_revenue"]].copy()
                    ld["conversion_rate"] = ld["conversion_rate"].apply(lambda x: f"{x:.1f}%")
                    ld["total_revenue"] = ld["total_revenue"].apply(adapter.format_currency)
                    cols = [{"name": c, "label": c.replace("_", " ").title(), "field": c} for c in ld.columns]
                    ui.table(rows=ld.to_dict("records"), columns=cols, pagination={"rowsPerPage": 12}).classes("w-full").props("dark flat dense")
                else:
                    ui.label("No outlets with <15% conversion rate").classes("text-gray-400 italic text-xs")

        ui.separator().classes("mb-4")

        # Awareness Analysis
        ui.label("📢 Awareness Analysis").classes("text-lg font-semibold text-white mb-3")
        med_foto = base["foto_qty"].median()
        med_conv = base["conversion_rate"].median()
        seg = base[(base["foto_qty"] > med_foto) & (base["conversion_rate"] < med_conv)]
        if not seg.empty:
            with ui.card().classes("w-full mb-6").style(CARD):
                ui.label("⚠️ High Awareness, Low Conversion (Need Promotion)").classes("text-sm font-semibold text-yellow-400 mb-2")
                sd = seg[["outlet_name", "foto_qty", "conversion_rate", "total_revenue"]].copy()
                sd["conversion_rate"] = sd["conversion_rate"].apply(lambda x: f"{x:.1f}%")
                sd["total_revenue"] = sd["total_revenue"].apply(adapter.format_currency)
                cols = [{"name": c, "label": c.replace("_", " ").title(), "field": c} for c in sd.columns]
                ui.table(rows=sd.to_dict("records"), columns=cols, pagination={"rowsPerPage": 15}).classes("w-full").props("dark flat dense")
        else:
            ui.label("No outlets in this segment.").classes("text-gray-400 italic")

        ui.separator().classes("mb-4")

        # Conversion Trends
        with ui.card().classes("w-full mb-6").style(CARD):
            ui.label("📈 Conversion Trends by Outlet").style(ST)
            top_conv = base.nlargest(10, "conversion_rate")
            ui.echart({
                "tooltip": {"trigger": "axis"},
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
                "xAxis": {"type": "category", "data": top_conv["outlet_name"].tolist(),
                          "axisLabel": {"color": "#a6adc8", "fontSize": 9, "rotate": 30},
                          "axisLine": {"lineStyle": {"color": "#45475a"}}},
                "yAxis": {"type": "value", "axisLabel": {"color": "#a6adc8", "formatter": "{value}%"},
                          "splitLine": {"lineStyle": {"color": "#313244"}}},
                "series": [{"type": "bar", "data": top_conv["conversion_rate"].tolist(),
                            "itemStyle": {"color": "#a6e3a1"}, "barMaxWidth": 30,
                            "label": {"show": True, "position": "top", "color": "#cdd6f4",
                                      "fontSize": 9, "formatter": "{@value}%"}}],
                "backgroundColor": "transparent", "textStyle": {"color": "#cdd6f4"},
            }).classes("w-full h-[300px]")
