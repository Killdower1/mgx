"""
🏆 Ranking Outlet — outlet ranking sorted by revenue.
"""
from nicegui import ui
import pandas as pd

from services.dashboard_adapter import get_adapter

CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"
MV = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
ML = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase;"


def create_page(container: ui.column):
    adapter = get_adapter()
    df = adapter.load_data()

    with container:
        ui.label("🏆 Ranking Outlet").classes("text-2xl font-bold text-white mb-4")

        if df.empty:
            ui.label("❌ Data tidak tersedia.").classes("text-red-400")
            return

        base = df.copy()
        cnt = base["outlet_status"].value_counts()

        # KPI Cards
        with ui.row().classes("w-full gap-4 mb-6"):
            for lbl, key, color in [("🟢 Keeper", "Keeper", "#22c55e"), ("🟡 Optimasi", "Optimasi", "#f59e0b"), ("🔴 Relocate", "Relocate", "#ef4444")]:
                with ui.card().classes("flex-1").style(CARD):
                    ui.label(lbl).style(ML)
                    ui.label(str(cnt.get(key, 0))).style(MV)

        ui.separator().classes("mb-4")

        # Complete Ranking Table
        ui.label("📊 Complete Outlet Ranking").classes("text-lg font-semibold text-white mb-3")
        ranked = base.sort_values("total_revenue", ascending=False).reset_index(drop=True)
        ranked["rank"] = range(1, len(ranked) + 1)

        disp = ranked[["rank", "outlet_name", "area", "kategori_tempat", "total_revenue", "conversion_rate", "outlet_status"]].copy()
        disp["total_revenue"] = disp["total_revenue"].apply(adapter.format_currency)
        disp["conversion_rate"] = disp["conversion_rate"].apply(lambda x: f"{x:.1f}%")

        columns = [
            {"name": "rank", "label": "#", "field": "rank", "align": "center"},
            {"name": "outlet_name", "label": "Outlet", "field": "outlet_name"},
            {"name": "area", "label": "Area", "field": "area"},
            {"name": "kategori_tempat", "label": "Kategori", "field": "kategori_tempat"},
            {"name": "total_revenue", "label": "Omset", "field": "total_revenue", "align": "right"},
            {"name": "conversion_rate", "label": "Conversion", "field": "conversion_rate", "align": "right"},
            {"name": "outlet_status", "label": "Status", "field": "outlet_status", "align": "center"},
        ]
        ui.table(
            rows=disp.to_dict("records"),
            columns=columns,
            pagination={"rowsPerPage": 25, "rowsNumber": len(disp)},
        ).classes("w-full mb-6").props("dark flat dense")

        # Analysis by Status tabs
        ui.label("📋 Analysis by Status").classes("text-lg font-semibold text-white mb-3")

        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="keeper").classes("w-full")
        with tabs:
            ui.tab("keeper", label="🟢 Keeper")
            ui.tab("optimasi", label="🟡 Optimasi")
            ui.tab("relocate", label="🔴 Relocate")

        for status_name, tab_val, color in [("Keeper", "keeper", "#22c55e"), ("Optimasi", "optimasi", "#f59e0b"), ("Relocate", "relocate", "#ef4444")]:
            with panels:
                with ui.tab_panel(tab_val):
                    sdf = base[base["outlet_status"] == status_name]
                    if sdf.empty:
                        ui.label(f"No outlets in {status_name} status.").classes("text-gray-400 italic")
                    else:
                        sd = sdf[["outlet_name", "area", "total_revenue", "conversion_rate"]].copy()
                        sd["total_revenue"] = sd["total_revenue"].apply(adapter.format_currency)
                        sd["conversion_rate"] = sd["conversion_rate"].apply(lambda x: f"{x:.1f}%")
                        cols = [{"name": c, "label": c.replace("_", " ").title(), "field": c} for c in sd.columns]
                        ui.table(rows=sd.to_dict("records"), columns=cols, pagination={"rowsPerPage": 15}).classes("w-full").props("dark flat dense")
