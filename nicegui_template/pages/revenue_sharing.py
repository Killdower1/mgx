"""
💵 Revenue Sharing — breakdown partner, broker, difotoin per outlet.
"""
from pathlib import Path

from nicegui import ui
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import difotoin_api_adapter as api

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
SECTION_T = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"


def _fmt_currency(amount) -> str:
    try:
        return "Rp " + str(int(round(float(amount))))
    except (ValueError, TypeError):
        return "Rp 0"


def create_page(container: ui.column):
    """Build the Revenue Sharing page."""
    container.clear()

    state = {
        "df": None,
        "periods": [],
        "selected_period": None,
    }

    with container:
        ui.label("💵 Revenue Sharing").classes("text-2xl font-bold text-white mb-2")
        ui.label("Breakdown bagi hasil per outlet: Partner, Broker, dan Difotoin.").classes(
            "text-sm text-gray-400 mb-4")

        # ── Load data ──
        def load_data():
            txns = api.load_raw_transactions()
            if not txns:
                state["df"] = pd.DataFrame()
                state["periods"] = []
                return
            df = api.compute_revenue_sharing(txns)
            if df.empty:
                state["df"] = pd.DataFrame()
                state["periods"] = []
                return
            state["df"] = df
            if "periode" in df.columns:
                periods = sorted(df["periode"].dropna().unique().tolist(), reverse=True)
                state["periods"] = periods
                if periods:
                    state["selected_period"] = periods[0]

        load_data()

        # ── Controls ──
        with ui.row().classes("w-full items-center gap-4 mb-4"):
            ui.select(
                state["periods"],
                value=state["selected_period"] if state["periods"] else None,
                label="Filter Periode",
                on_change=lambda e: _render_period(e.value),
            ).props("dense outlined dark").classes("w-40")

        # ── Summary cards ──
        summary_row = ui.row().classes("w-full gap-4 mb-6")

        # ── Content area ──
        content_area = ui.column().classes("w-full")

        def _render_period(period):
            """Render table for selected period."""
            content_area.clear()
            df = state["df"]
            if df.empty:
                with content_area:
                    ui.label("Belum ada data. Lakukan sync terlebih dahulu dari halaman Admin.").classes(
                        "text-gray-400 italic")
                return

            if period:
                filtered = df[df["periode"] == period].copy()
            else:
                filtered = df.copy()

            if filtered.empty:
                with content_area:
                    ui.label("Tidak ada data untuk periode ini.").classes("text-gray-400 italic")
                return

            # Aggregate by outlet for this period
            outlet_agg = filtered.groupby("outlet_name", as_index=False).agg(
                total_revenue=("total_revenue", "sum"),
                partner_amount=("partner_amount", "sum"),
                broker_amount=("broker_amount", "sum"),
                difotoin_amount=("difotoin_amount", "sum"),
                transactions=("total_revenue", "count"),
                avg_partner_pct=("partner_share_pct", "mean"),
                avg_broker_pct=("broker_share_pct", "mean"),
            ).sort_values("total_revenue", ascending=False)

            # Update summary
            total_rev = float(filtered["total_revenue"].sum())
            total_partner = float(filtered["partner_amount"].sum())
            total_broker = float(filtered["broker_amount"].sum())
            total_difotoin = float(filtered["difotoin_amount"].sum())

            summary_row.clear()
            with summary_row:
                with ui.card().style(CARD):
                    ui.label("💰 Total Revenue").classes("text-xs text-gray-400")
                    ui.label(_fmt_currency(total_rev)).classes("text-lg font-bold text-white")
                with ui.card().style(CARD):
                    ui.label("🏪 Partner").classes("text-xs text-gray-400")
                    ui.label(_fmt_currency(total_partner)).classes("text-lg font-bold text-blue-400")
                with ui.card().style(CARD):
                    ui.label("🔗 Broker").classes("text-xs text-gray-400")
                    ui.label(_fmt_currency(total_broker)).classes("text-lg font-bold text-yellow-400")
                with ui.card().style(CARD):
                    ui.label("📸 Difotoin").classes("text-xs text-gray-400")
                    ui.label(_fmt_currency(total_difotoin)).classes("text-lg font-bold text-green-400")

            # Render table
            with content_area:
                display = outlet_agg.copy()
                display["Partner %"] = display["avg_partner_pct"].round(1).astype(str) + "%"
                display["Broker %"] = display["avg_broker_pct"].round(1).astype(str) + "%"
                display["Difotoin %"] = (100 - display["avg_partner_pct"] - display["avg_broker_pct"]).round(1).astype(str) + "%"

                for col in ["total_revenue", "partner_amount", "broker_amount", "difotoin_amount"]:
                    display[col] = display[col].apply(_fmt_currency)

                display = display.rename(columns={
                    "outlet_name": "Outlet",
                    "total_revenue": "Revenue",
                    "partner_amount": "Partner Rp",
                    "broker_amount": "Broker Rp",
                    "difotoin_amount": "Difotoin Rp",
                    "transactions": "Transaksi",
                })

                cols = [
                    {"name": "Outlet", "label": "Outlet", "field": "Outlet", "align": "left"},
                    {"name": "Transaksi", "label": "Tx", "field": "Transaksi", "align": "right"},
                    {"name": "Revenue", "label": "Revenue", "field": "Revenue", "align": "right"},
                    {"name": "Partner %", "label": "Partner %", "field": "Partner %", "align": "center"},
                    {"name": "Partner Rp", "label": "Partner Rp", "field": "Partner Rp", "align": "right"},
                    {"name": "Broker %", "label": "Broker %", "field": "Broker %", "align": "center"},
                    {"name": "Broker Rp", "label": "Broker Rp", "field": "Broker Rp", "align": "right"},
                    {"name": "Difotoin %", "label": "Difotoin %", "field": "Difotoin %", "align": "center"},
                    {"name": "Difotoin Rp", "label": "Difotoin Rp", "field": "Difotoin Rp", "align": "right"},
                ]

                ui.table(
                    rows=display.to_dict("records"),
                    columns=cols,
                    pagination={"rowsPerPage": 20, "rowsNumber": len(display)},
                ).classes("w-full").props("dark flat dense")

                # Transaction detail
                ui.label("📋 Detail Transaksi").style(SECTION_T).classes("mt-6 mb-2")
                detail_cols = [
                    {"name": "outlet_name", "label": "Outlet", "field": "outlet_name", "align": "left"},
                    {"name": "date", "label": "Tanggal", "field": "date", "align": "left"},
                    {"name": "total_revenue", "label": "Amount", "field": "total_revenue", "align": "right"},
                    {"name": "partner_share_pct", "label": "Partner %", "field": "partner_share_pct", "align": "center"},
                    {"name": "partner_amount", "label": "Partner Rp", "field": "partner_amount", "align": "right"},
                    {"name": "broker_share_pct", "label": "Broker %", "field": "broker_share_pct", "align": "center"},
                    {"name": "broker_amount", "label": "Broker Rp", "field": "broker_amount", "align": "right"},
                    {"name": "difotoin_amount", "label": "Difotoin Rp", "field": "difotoin_amount", "align": "right"},
                    {"name": "customer_name", "label": "Customer", "field": "customer_name", "align": "left"},
                ]

                detail_df = filtered.copy()
                detail_df["total_revenue"] = detail_df["total_revenue"].apply(_fmt_currency)
                detail_df["partner_amount"] = detail_df["partner_amount"].apply(_fmt_currency)
                detail_df["broker_amount"] = detail_df["broker_amount"].apply(_fmt_currency)
                detail_df["difotoin_amount"] = detail_df["difotoin_amount"].apply(_fmt_currency)
                detail_df["partner_share_pct"] = detail_df["partner_share_pct"].round(1).astype(str) + "%"
                detail_df["broker_share_pct"] = detail_df["broker_share_pct"].round(1).astype(str) + "%"

                ui.table(
                    rows=detail_df.to_dict("records"),
                    columns=detail_cols,
                    pagination={"rowsPerPage": 15, "rowsNumber": len(detail_df)},
                ).classes("w-full").props("dark flat dense")

        # Initial render
        if state["periods"]:
            _render_period(state["selected_period"])
        else:
            with content_area:
                ui.label("Belum ada data. Lakukan sync terlebih dahulu dari halaman Admin.").classes(
                    "text-gray-400 italic")
