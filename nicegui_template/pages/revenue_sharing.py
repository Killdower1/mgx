"""
💵 Revenue Sharing — breakdown partner, broker, difotoin per outlet.
Uses pre-computed lightweight cache (not 92MB raw transactions).
"""
from pathlib import Path

from nicegui import ui

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import difotoin_api_adapter as api

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"


def _fmt_currency(amount) -> str:
    try:
        return "Rp " + str(int(round(float(amount))))
    except (ValueError, TypeError):
        return "Rp 0"


def _pct(val) -> str:
    try:
        return str(round(float(val), 1)) + "%"
    except (ValueError, TypeError):
        return "0%"


def create_page(container: ui.column):
    """Build the Revenue Sharing page using lightweight cache."""
    container.clear()

    states = {
        "periods": [],
        "current_period": None,
        "outlet_data": [],
    }

    # ── Load periods from pre-computed cache ──
    periods = api.get_rs_periods()
    states["periods"] = periods
    states["current_period"] = periods[0] if periods else None

    with container:
        ui.label("💵 Revenue Sharing").classes("text-2xl font-bold text-white mb-2")
        ui.label("Breakdown bagi hasil per outlet: Partner, Broker, dan Difotoin.").classes(
            "text-sm text-gray-400 mb-4")

        # ── Controls ──
        with ui.row().classes("w-full items-center gap-4 mb-4"):
            ui.select(
                periods,
                value=states["current_period"],
                label="Filter Periode",
                on_change=lambda e: _render_period(e.value),
            ).props("dense outlined dark").classes("w-40")

        # ── Summary cards ──
        summary_row = ui.row().classes("w-full gap-4 mb-6")

        # ── Content area ──
        content_area = ui.column().classes("w-full")

        def _render_period(period):
            """Render summary + table + detail for selected period."""
            content_area.clear()
            if not period:
                with content_area:
                    ui.label("Pilih periode.").classes("text-gray-400 italic")
                return

            # Load filtered outlet summary (lightweight)
            all_outlets = api.load_rs_outlet_summary()
            if not all_outlets:
                with content_area:
                    ui.label("Belum ada data. Lakukan sync dari halaman Admin.").classes("text-gray-400 italic")
                return

            # Filter by period
            period_outlets = [r for r in all_outlets if r.get("periode") == period]
            if not period_outlets:
                with content_area:
                    ui.label("Tidak ada data untuk periode ini.").classes("text-gray-400 italic")
                return

            # Sort by total_revenue descending
            period_outlets.sort(key=lambda r: float(r.get("total_revenue", 0)), reverse=True)

            # ── Summary cards ──
            total_rev = sum(float(r.get("total_revenue", 0)) for r in period_outlets)
            total_partner = sum(float(r.get("partner_amount", 0)) for r in period_outlets)
            total_broker = sum(float(r.get("broker_amount", 0)) for r in period_outlets)
            total_difotoin = sum(float(r.get("difotoin_amount", 0)) for r in period_outlets)

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

            # ── Outlet summary table ──
            with content_area:
                display = []
                for r in period_outlets:
                    display.append({
                        "Outlet": r.get("outlet_name", ""),
                        "Tx": int(r.get("transactions", 0)),
                        "Revenue": _fmt_currency(r.get("total_revenue", 0)),
                        "Partner %": _pct(r.get("avg_partner_pct", 0)),
                        "Partner Rp": _fmt_currency(r.get("partner_amount", 0)),
                        "Broker %": _pct(r.get("avg_broker_pct", 0)),
                        "Broker Rp": _fmt_currency(r.get("broker_amount", 0)),
                        "Difotoin %": _pct(max(0, 100 - float(r.get("avg_partner_pct", 0)) - float(r.get("avg_broker_pct", 0)))),
                        "Difotoin Rp": _fmt_currency(r.get("difotoin_amount", 0)),
                    })

                cols = [
                    {"name": "Outlet", "label": "Outlet", "field": "Outlet", "align": "left"},
                    {"name": "Tx", "label": "Tx", "field": "Tx", "align": "right"},
                    {"name": "Revenue", "label": "Revenue", "field": "Revenue", "align": "right"},
                    {"name": "Partner %", "label": "P %", "field": "Partner %", "align": "center"},
                    {"name": "Partner Rp", "label": "P Rp", "field": "Partner Rp", "align": "right"},
                    {"name": "Broker %", "label": "B %", "field": "Broker %", "align": "center"},
                    {"name": "Broker Rp", "label": "B Rp", "field": "Broker Rp", "align": "right"},
                    {"name": "Difotoin %", "label": "D %", "field": "Difotoin %", "align": "center"},
                    {"name": "Difotoin Rp", "label": "D Rp", "field": "Difotoin Rp", "align": "right"},
                ]

                ui.table(
                    rows=display,
                    columns=cols,
                    pagination={"rowsPerPage": 20, "rowsNumber": len(display)},
                ).classes("w-full").props("dark flat dense")

                # ── Transaction Detail ──
                detail_data = api.load_rs_period_detail(period)
                if detail_data:
                    ui.label("📋 Detail Transaksi").classes(
                        "text-sm font-semibold text-white mt-6 mb-2")

                    detail_cols = [
                        {"name": "outlet_name", "label": "Outlet", "field": "outlet_name", "align": "left"},
                        {"name": "date", "label": "Tgl", "field": "date", "align": "left"},
                        {"name": "total_revenue", "label": "Amount", "field": "total_revenue", "align": "right"},
                        {"name": "partner_share_pct", "label": "P %", "field": "partner_share_pct", "align": "center"},
                        {"name": "partner_amount", "label": "P Rp", "field": "partner_amount", "align": "right"},
                        {"name": "broker_share_pct", "label": "B %", "field": "broker_share_pct", "align": "center"},
                        {"name": "broker_amount", "label": "B Rp", "field": "broker_amount", "align": "right"},
                        {"name": "difotoin_amount", "label": "D Rp", "field": "difotoin_amount", "align": "right"},
                    ]

                    detail_clean = []
                    for d in detail_data:
                        detail_clean.append({
                            "outlet_name": d.get("outlet_name", ""),
                            "date": str(d.get("date", ""))[:10],
                            "total_revenue": _fmt_currency(d.get("total_revenue", 0)),
                            "partner_share_pct": _pct(d.get("partner_share_pct", 0)),
                            "partner_amount": _fmt_currency(d.get("partner_amount", 0)),
                            "broker_share_pct": _pct(d.get("broker_share_pct", 0)),
                            "broker_amount": _fmt_currency(d.get("broker_amount", 0)),
                            "difotoin_amount": _fmt_currency(d.get("difotoin_amount", 0)),
                        })

                    ui.table(
                        rows=detail_clean,
                        columns=detail_cols,
                        pagination={"rowsPerPage": 15, "rowsNumber": len(detail_clean)},
                    ).classes("w-full").props("dark flat dense")

        # Initial render
        if not states["current_period"]:
            with content_area:
                ui.label("Belum ada data. Lakukan sync dari halaman Admin.").classes(
                    "text-gray-400 italic")
        else:
            _render_period(states["current_period"])
