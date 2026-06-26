"""
💵 Revenue Sharing — ringkasan bulanan per outlet + sewa & minimum payment.
"""
from pathlib import Path
import pandas as pd

from nicegui import ui

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import difotoin_api_adapter as api

OUTLET_LIST_PATH = Path(__file__).resolve().parent.parent.parent / "streamlit_template" / "data" / "outlet_list.xlsx"

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"


def _load_outlets() -> dict:
    """Load outlet list with MONTHLY_RENT & MINIMUM_PAYMENT, keyed by name."""
    try:
        df = pd.read_excel(OUTLET_LIST_PATH)
        result = {}
        for _, r in df.iterrows():
            name = str(r.get("NAME", "")).strip()
            rent = r.get("MONTHLY_RENT")
            minpay = r.get("MINIMUM_PAYMENT")
            result[name] = {
                "monthly_rent": float(rent) if pd.notna(rent) else 0.0,
                "minimum_payment": float(minpay) if pd.notna(minpay) else None,
            }
        return result
    except Exception:
        return {}


def _fmt(amount) -> str:
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
    """Revenue sharing page with sewa & minimum payment."""
    container.clear()

    # ── Load data ──
    all_periods = api.get_rs_periods()
    if not all_periods:
        with container:
            ui.label("💵 Revenue Sharing").classes("text-2xl font-bold text-white mb-2")
            ui.label("Belum ada data. Lakukan sync dari halaman Admin.").classes("text-gray-400 italic")
        return

    outlets = _load_outlets()
    state = {
        "all_outlets": api.load_rs_outlet_summary(),
        "from_period": all_periods[-1],
        "to_period": all_periods[0],
    }

    with container:
        ui.label("💵 Revenue Sharing").classes("text-2xl font-bold text-white mb-2")
        ui.label("Ringkasan bagi hasil + sewa & minimum payment.").classes("text-sm text-gray-400 mb-4")

        # ── Range filter ──
        with ui.row().classes("w-full items-center gap-4 mb-4"):
            ui.select(
                all_periods, value=state["from_period"], label="Dari Bulan",
                on_change=lambda e: _update(),
            ).props("dense outlined dark").classes("w-36")
            ui.label("\u2192").classes("text-gray-500 text-sm")
            ui.select(
                all_periods, value=state["to_period"], label="Sampai Bulan",
                on_change=lambda e: _update(),
            ).props("dense outlined dark").classes("w-36")

        summary_row = ui.row().classes("w-full gap-4 mb-6")
        table_container = ui.column().classes("w-full")

        def _compute():
            data = state["all_outlets"]
            if not data:
                return [], [], 0, 0, 0, 0

            # Filter by period range
            periods_in = [p for p in all_periods if state["from_period"] <= p <= state["to_period"]]
            filtered = [r for r in data if r.get("periode") in periods_in]
            if not filtered:
                return [], [], 0, 0, 0, 0

            # Aggregate by outlet
            om = {}
            for r in filtered:
                name = r.get("outlet_name", "")
                if name not in om:
                    om[name] = {
                        "outlet_name": name,
                        "total_revenue": 0.0, "partner_amount": 0.0,
                        "broker_amount": 0.0, "difotoin_amount": 0.0,
                        "transactions": 0, "pcts": [], "bcts": [],
                    }
                o = om[name]
                o["total_revenue"] += float(r.get("total_revenue", 0))
                o["partner_amount"] += float(r.get("partner_amount", 0))
                o["broker_amount"] += float(r.get("broker_amount", 0))
                o["difotoin_amount"] += float(r.get("difotoin_amount", 0))
                o["transactions"] += int(r.get("transactions", 0))
                o["pcts"].append(float(r.get("avg_partner_pct", 0)))
                o["bcts"].append(float(r.get("avg_broker_pct", 0)))

            outlet_list = []
            for name, o in om.items():
                o["avg_partner_pct"] = sum(o["pcts"]) / len(o["pcts"]) if o["pcts"] else 0
                o["avg_broker_pct"] = sum(o["bcts"]) / len(o["bcts"]) if o["bcts"] else 0
                # Add outlet info
                info = outlets.get(name, {})
                o["monthly_rent"] = info.get("monthly_rent", 0.0)
                minpay = info.get("minimum_payment")
                o["minimum_payment"] = minpay if minpay is not None else 0.0
                # Effective payment: max(partner_amount, minimum_payment) if minpay exists
                if minpay is not None and minpay > 0:
                    o["effective_partner"] = max(o["partner_amount"], minpay)
                    o["minpay_applied"] = o["partner_amount"] < minpay
                else:
                    o["effective_partner"] = o["partner_amount"]
                    o["minpay_applied"] = False
                # Difotoin efektif: revenue - effective_partner - broker
                o["effective_difotoin"] = o["total_revenue"] - o["effective_partner"] - o["broker_amount"]
                outlet_list.append(o)

            outlet_list.sort(key=lambda x: x["total_revenue"], reverse=True)

            total_rev = sum(o["total_revenue"] for o in outlet_list)
            total_partner = sum(o["partner_amount"] for o in outlet_list)
            total_effective = sum(o["effective_partner"] for o in outlet_list)
            total_broker = sum(o["broker_amount"] for o in outlet_list)
            total_rent = sum(o["monthly_rent"] for o in outlet_list)

            return outlet_list, total_rev, total_partner, total_effective, total_broker, total_rent

        def _update():
            table_container.clear()
            summary_row.clear()

            result = _compute()
            if not result or not result[0]:
                with table_container:
                    ui.label("Tidak ada data untuk range tersebut.").classes("text-gray-400 italic")
                return

            outlet_list, total_rev, total_partner, total_effective, total_broker, total_rent = result

            # Summary cards
            with summary_row:
                with ui.card().style(CARD):
                    ui.label("💰 Revenue").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_rev)).classes("text-lg font-bold text-white")
                with ui.card().style(CARD):
                    ui.label("🏪 Partner (Efektif)").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_effective)).classes("text-lg font-bold text-blue-400")
                with ui.card().style(CARD):
                    ui.label("🔗 Broker").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_broker)).classes("text-lg font-bold text-yellow-400")
                with ui.card().style(CARD):
                    ui.label("📸 Difotoin Efektif").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_rev - total_effective - total_broker)).classes("text-lg font-bold text-green-400")
                with ui.card().style(CARD):
                    ui.label("🏠 Sewa").classes("text-xs text-gray-400")
                    ui.label(_fmt(total_rent)).classes("text-lg font-bold text-orange-400")

            # Table
            display = []
            for o in outlet_list:
                d_pct = max(0, 100 - o["avg_partner_pct"] - o["avg_broker_pct"])
                row = {
                    "outlet": o["outlet_name"],
                    "tx": o["transactions"],
                    "revenue": _fmt(o["total_revenue"]),
                    "p_pct": _pct(o["avg_partner_pct"]),
                    "p_rp": _fmt(o["partner_amount"]),
                    "minpay": _fmt(o["minimum_payment"]) if o["minimum_payment"] > 0 else "-",
                    "eff_p": _fmt(o["effective_partner"]),
                    "b_pct": _pct(o["avg_broker_pct"]),
                    "b_rp": _fmt(o["broker_amount"]),
                    "d_pct": _pct(d_pct),
                    "d_eff": _fmt(o["effective_difotoin"]),
                    "sewa": _fmt(o["monthly_rent"]) if o["monthly_rent"] > 0 else "-",
                }
                # Mark minpay-applied rows
                if o["minpay_applied"]:
                    row["_minpay"] = True
                display.append(row)

            cols = [
                {"name": "outlet", "label": "Outlet", "field": "outlet", "align": "left"},
                {"name": "tx", "label": "Tx", "field": "tx", "align": "right"},
                {"name": "revenue", "label": "Revenue", "field": "revenue", "align": "right"},
                {"name": "p_pct", "label": "P%", "field": "p_pct", "align": "center"},
                {"name": "minpay", "label": "MinPay", "field": "minpay", "align": "right"},
                {"name": "eff_p", "label": "Partner Rp*", "field": "eff_p", "align": "right"},
                {"name": "b_pct", "label": "B%", "field": "b_pct", "align": "center"},
                {"name": "b_rp", "label": "Broker Rp", "field": "b_rp", "align": "right"},
                {"name": "d_pct", "label": "D%", "field": "d_pct", "align": "center"},
                {"name": "d_eff", "label": "Difotoin Rp*", "field": "d_eff", "align": "right"},
                {"name": "sewa", "label": "Sewa", "field": "sewa", "align": "right"},
            ]

            with table_container:
                ui.table(
                    rows=display,
                    columns=cols,
                    pagination={"rowsPerPage": 25, "rowsNumber": len(display)},
                ).classes("w-full").props("dark flat dense")

                ui.label("* Partner Efektif = max(partner_amount, minimum_payment) jika ada minimum payment").classes(
                    "text-[10px] text-gray-600 mt-1")

        _update()
