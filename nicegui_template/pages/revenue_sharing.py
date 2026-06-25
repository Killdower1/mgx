"""
💵 Revenue Sharing — ringkasan bulanan per outlet (range filter).
"""
from pathlib import Path

from nicegui import ui

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import difotoin_api_adapter as api

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"


def _fmt(amount) -> str:
    """Format with Indonesian thousand separator (dot)."""
    try:
        return "Rp " + f"{int(round(float(amount))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"


def _pct(val) -> str:
    try:
        return str(round(float(val), 1)) + "%"
    except (ValueError, TypeError):
        return "0%"


def create_page(container: ui.column):
    """Revenue sharing page: pure monthly summary with range filter."""
    container.clear()

    # ── Load periods from cache ──
    all_periods = api.get_rs_periods()  # sorted descending e.g. ["2025-07", "2025-06", ...]
    if not all_periods:
        with container:
            ui.label("💵 Revenue Sharing").classes("text-2xl font-bold text-white mb-2")
            ui.label("Belum ada data. Lakukan sync dari halaman Admin.").classes("text-gray-400 italic")
        return

    state = {
        "all_outlets": api.load_rs_outlet_summary(),  # list of dicts, ~16KB
        "from_period": all_periods[-1],  # oldest
        "to_period": all_periods[0],      # newest
    }

    # ── Build UI ──
    with container:
        ui.label("💵 Revenue Sharing").classes("text-2xl font-bold text-white mb-2")
        ui.label("Ringkasan bagi hasil per outlet — filter range bulan.").classes("text-sm text-gray-400 mb-4")

        # ── Range filter ──
        with ui.row().classes("w-full items-center gap-4 mb-4"):
            from_select = ui.select(
                all_periods,
                value=state["from_period"],
                label="Dari Bulan",
                on_change=lambda e: _update_range(),
            ).props("dense outlined dark").classes("w-36")

            ui.label("→").classes("text-gray-500 text-sm")

            to_select = ui.select(
                all_periods,
                value=state["to_period"],
                label="Sampai Bulan",
                on_change=lambda e: _update_range(),
            ).props("dense outlined dark").classes("w-36")

        # ── Summary row ──
        summary_row = ui.row().classes("w-full gap-4 mb-6")

        # ── Table ──
        table_container = ui.column().classes("w-full")

        def _update_range():
            state["from_period"] = from_select.value
            state["to_period"] = to_select.value
            _render()

        def _render():
            table_container.clear()
            summary_row.clear()

            data = state["all_outlets"]
            if not data:
                with table_container:
                    ui.label("Data kosong.").classes("text-gray-400 italic")
                return

            # Filter by period range
            periods_in_range = []
            for p in all_periods:
                if state["from_period"] <= p <= state["to_period"]:
                    periods_in_range.append(p)

            filtered = [r for r in data if r.get("periode") in periods_in_range]
            if not filtered:
                with table_container:
                    ui.label("Tidak ada data untuk range tersebut.").classes("text-gray-400 italic")
                return

            # Aggregate by outlet across all periods in range
            outlet_map = {}
            for r in filtered:
                name = r.get("outlet_name", "")
                if name not in outlet_map:
                    outlet_map[name] = {
                        "outlet_name": name,
                        "total_revenue": 0.0,
                        "partner_amount": 0.0,
                        "broker_amount": 0.0,
                        "difotoin_amount": 0.0,
                        "transactions": 0,
                        "avg_partner_pct": [],
                        "avg_broker_pct": [],
                    }
                o = outlet_map[name]
                o["total_revenue"] += float(r.get("total_revenue", 0))
                o["partner_amount"] += float(r.get("partner_amount", 0))
                o["broker_amount"] += float(r.get("broker_amount", 0))
                o["difotoin_amount"] += float(r.get("difotoin_amount", 0))
                o["transactions"] += int(r.get("transactions", 0))
                o["avg_partner_pct"].append(float(r.get("avg_partner_pct", 0)))
                o["avg_broker_pct"].append(float(r.get("avg_broker_pct", 0)))

            # Calculate averages
            outlet_list = []
            for name, o in outlet_map.items():
                o["avg_partner_pct"] = sum(o["avg_partner_pct"]) / len(o["avg_partner_pct"]) if o["avg_partner_pct"] else 0
                o["avg_broker_pct"] = sum(o["avg_broker_pct"]) / len(o["avg_broker_pct"]) if o["avg_broker_pct"] else 0
                outlet_list.append(o)

            # Sort by revenue descending
            outlet_list.sort(key=lambda x: x["total_revenue"], reverse=True)

            # ── Summary cards ──
            total_rev = sum(o["total_revenue"] for o in outlet_list)
            total_partner = sum(o["partner_amount"] for o in outlet_list)
            total_broker = sum(o["broker_amount"] for o in outlet_list)
            total_difotoin = sum(o["difotoin_amount"] for o in outlet_list)
            total_tx = sum(o["transactions"] for o in outlet_list)

            with summary_row:
                with ui.card().style(CARD):
                    ui.label("💰 Revenue").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_rev)).classes("text-lg font-bold text-white")
                    ui.label(str(total_tx) + " tx").classes("text-xs text-gray-500")
                with ui.card().style(CARD):
                    ui.label("🏪 Partner").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_partner)).classes("text-lg font-bold text-blue-400")
                with ui.card().style(CARD):
                    ui.label("🔗 Broker").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_broker)).classes("text-lg font-bold text-yellow-400")
                with ui.card().style(CARD):
                    ui.label("📸 Difotoin").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_difotoin)).classes("text-lg font-bold text-green-400")

            # ── Table ──
            display_rows = []
            for o in outlet_list:
                difo_pct = max(0, 100 - o["avg_partner_pct"] - o["avg_broker_pct"])
                display_rows.append({
                    "outlet": o["outlet_name"],
                    "tx": o["transactions"],
                    "revenue": _fmt(o["total_revenue"]),
                    "p_pct": _pct(o["avg_partner_pct"]),
                    "p_rp": _fmt(o["partner_amount"]),
                    "b_pct": _pct(o["avg_broker_pct"]),
                    "b_rp": _fmt(o["broker_amount"]),
                    "d_pct": _pct(difo_pct),
                    "d_rp": _fmt(o["difotoin_amount"]),
                })

            cols = [
                {"name": "outlet", "label": "Outlet", "field": "outlet", "align": "left"},
                {"name": "tx", "label": "Tx", "field": "tx", "align": "right"},
                {"name": "revenue", "label": "Revenue", "field": "revenue", "align": "right"},
                {"name": "p_pct", "label": "P%", "field": "p_pct", "align": "center"},
                {"name": "p_rp", "label": "Partner Rp", "field": "p_rp", "align": "right"},
                {"name": "b_pct", "label": "B%", "field": "b_pct", "align": "center"},
                {"name": "b_rp", "label": "Broker Rp", "field": "b_rp", "align": "right"},
                {"name": "d_pct", "label": "D%", "field": "d_pct", "align": "center"},
                {"name": "d_rp", "label": "Difotoin Rp", "field": "d_rp", "align": "right"},
            ]

            with table_container:
                ui.table(
                    rows=display_rows,
                    columns=cols,
                    pagination={"rowsPerPage": 25, "rowsNumber": len(display_rows)},
                ).classes("w-full").props("dark flat dense")

        # Initial render
        _render()
