"""
🤖 AI Decision Center — trend analysis and AI-powered insights.
"""
import sys
from pathlib import Path

from nicegui import ui
import pandas as pd
import numpy as np

# Add streamlit_template to path for reusing insight engine
ST_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
if str(ST_DIR) not in sys.path:
    sys.path.insert(0, str(ST_DIR))

from services.dashboard_adapter import get_adapter

CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px;"


def _sort_periods_str(periods):
    """Sort period strings like '2024-01' chronologically."""
    s = pd.Series(periods, dtype=object)
    dt = pd.to_datetime(s, format="%Y-%m", errors="coerce")
    helper = pd.DataFrame({"p": s, "dt": dt}).sort_values(by=["dt", "p"], na_position="last")
    return helper["p"].astype(str).tolist()


def create_page(container: ui.column):
    adapter = get_adapter()
    df = adapter.load_data()

    with container:
        ui.label("🤖 AI Decision").classes("text-2xl font-bold text-white")
        ui.label("Ruang bantu keputusan founder: membaca data, memberi sinyal risiko, dan menyusun prioritas aksi.").classes(
            "text-sm text-gray-400 mb-4")

        if df.empty or "periode" not in df.columns:
            ui.label("❌ Data tidak tersedia untuk AI Decision.").classes("text-red-400")
            return

        base = df.copy()
        for col in ["total_revenue", "foto_qty", "unlock_qty", "print_qty", "paid_per_photo_rate"]:
            base[col] = pd.to_numeric(base.get(col, 0), errors="coerce").fillna(0.0)
        base["periode"] = base["periode"].astype(str)

        periods = _sort_periods_str(base["periode"].dropna().unique().tolist())
        if not periods:
            ui.label("Data periode tidak tersedia.").classes("text-red-400")
            return

        default_start = max(0, len(periods) - 12)

        with ui.row().classes("w-full gap-4 items-center mb-6"):
            start_sel = ui.select(periods, value=periods[default_start], label="Periode Mulai").props("dense outlined dark").classes("flex-1")
            end_sel = ui.select(periods, value=periods[-1], label="Periode Akhir").props("dense outlined dark").classes("flex-1")
            info_lbl = ui.label().classes("text-sm text-gray-400 flex-1")

        content = ui.column().classes("w-full")

        def update():
            content.clear()
            sp = start_sel.value
            ep = end_sel.value
            start_idx = periods.index(sp)
            end_idx = periods.index(ep)

            if start_idx > end_idx:
                with content:
                    ui.label("❌ Periode mulai tidak boleh lebih baru dari periode akhir.").classes("text-red-400")
                return

            selected = periods[start_idx:end_idx + 1]
            filtered = base[base["periode"].isin(selected)].copy()
            info_lbl.set_text(f"🤖 AI membaca {len(selected)} periode: {sp} sampai {ep}.")

            # Replicate build_ai_trend_insights logic inline
            latest_period = selected[-1]
            previous_period = selected[-2] if len(selected) > 1 else None
            latest_df = filtered[filtered["periode"] == latest_period].copy()
            previous_df = filtered[filtered["periode"] == previous_period].copy() if previous_period else pd.DataFrame()

            def sum_col(frame, col):
                return float(pd.to_numeric(frame.get(col, 0), errors="coerce").fillna(0).sum())

            def pct_change(now, prev):
                return ((now - prev) / prev * 100) if prev > 0 else None

            def fmt_pct(v):
                return "-" if v is None else f"{v:+.1f}%"

            monthly = filtered.groupby("periode", as_index=False).agg(
                total_revenue=("total_revenue", "sum"),
                foto_qty=("foto_qty", "sum"),
                print_qty=("print_qty", "sum"),
            )
            monthly["paid_per_photo_rate"] = np.where(monthly["foto_qty"] > 0, monthly["print_qty"] / monthly["foto_qty"] * 100, 0)

            latest_rev = sum_col(latest_df, "total_revenue")
            prev_rev = sum_col(previous_df, "total_revenue")
            rev_delta = pct_change(latest_rev, prev_rev)
            avg_monthly = float(monthly["total_revenue"].mean()) if not monthly.empty else 0

            with content:
                # Summary
                with ui.card().classes("w-full mb-4").style(CARD):
                    ui.label("📋 Ringkasan").classes("text-sm font-semibold text-blue-400 mb-2")
                    ui.label(f"Range analisis: {selected[0]} sampai {selected[-1]} dengan {len(selected)} periode data.").classes("text-sm text-gray-300")
                    ui.label(f"Omzet periode terakhir {latest_period} adalah {adapter.format_currency(latest_rev)}, dibanding periode sebelumnya: {fmt_pct(rev_delta)}.").classes("text-sm text-gray-300")
                    ui.label(f"Rata-rata omzet bulanan pada range ini sekitar {adapter.format_currency(avg_monthly)}.").classes("text-sm text-gray-300")

                    if not monthly.empty:
                        best = monthly.sort_values("total_revenue", ascending=False).head(1).iloc[0]
                        worst = monthly.sort_values("total_revenue", ascending=True).head(1).iloc[0]
                        ui.label(f"Bulan terkuat: {best['periode']} ({adapter.format_currency(float(best['total_revenue']))}).").classes("text-sm text-green-400")
                        ui.label(f"Bulan terlemah: {worst['periode']} ({adapter.format_currency(float(worst['total_revenue']))}).").classes("text-sm text-red-400")

                # Findings
                with ui.card().classes("w-full mb-4").style(CARD):
                    ui.label("🔍 Temuan").classes("text-sm font-semibold text-yellow-400 mb-2")
                    area_summary = filtered.groupby("area", as_index=False).agg(
                        total_revenue=("total_revenue", "sum"),
                        outlet_count=("outlet_name", "nunique"),
                    ).sort_values("total_revenue", ascending=False) if "area" in filtered.columns else pd.DataFrame()

                    if not area_summary.empty:
                        top_area = area_summary.head(1).iloc[0]
                        ui.label(f"Area terbesar: {top_area['area']} — {adapter.format_currency(float(top_area['total_revenue']))} dari {int(top_area['outlet_count'])} outlet.").classes("text-sm text-gray-300")

                    inactive = len(set(filtered["outlet_name"].dropna().astype(str).str.strip()) - set(latest_df["outlet_name"].dropna().astype(str).str.strip())) if "outlet_name" in filtered.columns else 0
                    if inactive > 0:
                        ui.label(f"{inactive} outlet tidak aktif di periode terakhir.").classes("text-sm text-yellow-400")

                # Actions
                with ui.card().classes("w-full mb-4").style(CARD):
                    ui.label("🎯 Aksi Prioritas").classes("text-sm font-semibold text-green-400 mb-2")
                    actions = []
                    if rev_delta is not None and rev_delta < -10:
                        actions.append("Prioritaskan audit outlet yang turun pada periode terakhir, terutama penyebab traffic, conversion, dan stok/operasional.")
                    elif rev_delta is not None and rev_delta > 10:
                        actions.append("Duplikasi pola dari outlet/area yang naik: cek promo, placement, timing event, dan operator yang bertugas.")
                    else:
                        actions.append("Fokuskan eksperimen pada outlet dengan conversion rendah tetapi traffic foto tinggi.")
                    for a in actions:
                        ui.label(f"• {a}").classes("text-sm text-gray-300")

                # Priority Outlets
                if "outlet_name" in filtered.columns:
                    outlet_summary = filtered.groupby("outlet_name", as_index=False).agg(
                        total_revenue=("total_revenue", "sum"),
                        foto_qty=("foto_qty", "sum"),
                        print_qty=("print_qty", "sum"),
                        active_months=("periode", "nunique"),
                    )
                    outlet_summary["paid_per_photo_rate"] = np.where(outlet_summary["foto_qty"] > 0,
                                                                   outlet_summary["print_qty"] / outlet_summary["foto_qty"] * 100, 0)
                    priority = outlet_summary.sort_values(["total_revenue", "paid_per_photo_rate"], ascending=[False, True]).head(12)

                    ui.label("🏆 Prioritas Outlet untuk Ditindaklanjuti").classes("text-sm font-semibold text-white mb-2")
                    cols = [{"name": c, "label": c.replace("_", " ").title(), "field": c} for c in priority.columns if c != "active_months"]
                    ui.table(
                        rows=priority.to_dict("records"),
                        columns=cols,
                        pagination={"rowsPerPage": 12},
                    ).classes("w-full").props("dark flat dense")

        start_sel.on("change", update)
        end_sel.on("change", update)
        update()
