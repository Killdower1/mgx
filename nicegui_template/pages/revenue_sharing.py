"""
💵 Revenue Sharing — AG Grid, range filter, sewa & minimum payment.
"""
from pathlib import Path
import pandas as pd

from nicegui import ui

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import difotoin_api_adapter as api

OUTLET_LIST_PATH = Path(__file__).resolve().parent.parent.parent / "streamlit_template" / "data" / "outlet_list.xlsx"
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"


def _load_outlets() -> dict:
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


def create_page(container: ui.column):
    container.clear()

    all_periods = api.get_rs_periods()
    if not all_periods:
        with container:
            ui.label("Belum ada data.").classes("text-gray-400 italic")
        return

    outlets = _load_outlets()

    state = {
        "all_outlets": api.load_rs_outlet_summary(),
        "from_period": all_periods[-1],
        "to_period": all_periods[0],
    }

    # ── Helper: compute filtered + aggregated data ──
    def _compute():
        data = state["all_outlets"]
        if not data:
            return []

        fp, tp = state["from_period"], state["to_period"]
        periods_in = [p for p in all_periods if fp <= p <= tp]
        filtered = [r for r in data if r.get("periode") in periods_in]
        if not filtered:
            return []

        om = {}
        for r in filtered:
            name = r.get("outlet_name", "")
            if name not in om:
                om[name] = {"outlet_name": name, "total_revenue": 0.0, "partner_amount": 0.0,
                            "broker_amount": 0.0, "difotoin_amount": 0.0, "transactions": 0, "pcts": [], "bcts": []}
            o = om[name]
            o["total_revenue"] += float(r.get("total_revenue", 0))
            o["partner_amount"] += float(r.get("partner_amount", 0))
            o["broker_amount"] += float(r.get("broker_amount", 0))
            o["difotoin_amount"] += float(r.get("difotoin_amount", 0))
            o["transactions"] += int(r.get("transactions", 0))
            o["pcts"].append(float(r.get("avg_partner_pct", 0)))
            o["bcts"].append(float(r.get("avg_broker_pct", 0)))

        result = []
        for name, o in om.items():
            o["avg_partner_pct"] = sum(o["pcts"]) / len(o["pcts"]) if o["pcts"] else 0
            o["avg_broker_pct"] = sum(o["bcts"]) / len(o["bcts"]) if o["bcts"] else 0
            info = outlets.get(name, {})
            o["monthly_rent"] = info.get("monthly_rent", 0.0)
            minpay = info.get("minimum_payment")
            o["minimum_payment"] = minpay if minpay is not None else 0.0
            if minpay is not None and minpay > 0 and o["partner_amount"] < minpay:
                o["effective_partner"] = minpay
                o["minpay_applied"] = True
            else:
                o["effective_partner"] = o["partner_amount"]
                o["minpay_applied"] = False
            o["effective_difotoin"] = o["total_revenue"] - o["effective_partner"] - o["broker_amount"]
            result.append(o)

        result.sort(key=lambda x: x["total_revenue"], reverse=True)
        return result

    def _render():
        table_container.clear()
        summary_row.clear()

        outlet_list = _compute()
        if not outlet_list:
            with table_container:
                ui.label("Tidak ada data.").classes("text-gray-400 italic")
            return

        total_rev = sum(o["total_revenue"] for o in outlet_list)
        total_eff = sum(o["effective_partner"] for o in outlet_list)
        total_broker = sum(o["broker_amount"] for o in outlet_list)
        total_rent = sum(o["monthly_rent"] for o in outlet_list)
        total_difo = total_rev - total_eff - total_broker

        # Summary cards
        with summary_row:
            def _card(label, value, color="text-white"):
                with ui.card().style(CARD):
                    ui.label(label).classes("text-xs text-gray-400")
                    ui.label(_fmt(value)).classes("text-lg font-bold " + color)
            _card("Revenue", total_rev)
            _card("Partner*", total_eff, "text-blue-400")
            _card("Broker", total_broker, "text-yellow-400")
            _card("Difotoin*", total_difo, "text-green-400")
            _card("Total Sewa", total_rent, "text-orange-400")

        # AG Grid
        row_data = []
        for o in outlet_list:
            d_pct = max(0, 100 - o["avg_partner_pct"] - o["avg_broker_pct"])
            note = "⚠️" if o["minpay_applied"] else ""
            row_data.append({
                "outlet": o["outlet_name"],
                "tx": o["transactions"],
                "revenue": _fmt(o["total_revenue"]),
                "p_pct": f"{o['avg_partner_pct']:.1f}%",
                "minpay": _fmt(o["minimum_payment"]) if o["minimum_payment"] > 0 else "-",
                "eff_p": _fmt(o["effective_partner"]),
                "note": note,
                "b_pct": f"{o['avg_broker_pct']:.1f}%",
                "b_rp": _fmt(o["broker_amount"]),
                "d_pct": f"{d_pct:.1f}%",
                "d_eff": _fmt(o["effective_difotoin"]),
                "sewa": _fmt(o["monthly_rent"]) if o["monthly_rent"] > 0 else "-",
            })

        ag_opts = {
            "columnDefs": [
                {"field": "outlet", "headerName": "Outlet", "width": 280, "pinned": "left"},
                {"field": "tx", "headerName": "Tx", "width": 70},
                {"field": "revenue", "headerName": "Revenue", "width": 130},
                {"field": "p_pct", "headerName": "P%", "width": 60},
                {"field": "minpay", "headerName": "MinPay", "width": 120},
                {"field": "eff_p", "headerName": "Partner Rp*", "width": 140},
                {"field": "note", "headerName": " ", "width": 50},
                {"field": "b_pct", "headerName": "B%", "width": 60},
                {"field": "b_rp", "headerName": "Broker Rp", "width": 130},
                {"field": "d_pct", "headerName": "D%", "width": 60},
                {"field": "d_eff", "headerName": "Difotoin Rp*", "width": 140},
                {"field": "sewa", "headerName": "Sewa", "width": 120},
            ],
            "rowData": row_data,
            "defaultColDef": {
                "sortable": True,
                "filter": True,
                "resizable": True,
                "cellStyle": {"backgroundColor": "#1e1e2e", "color": "#cdd6f4", "border": "none"},
                "headerClass": "text-gray-400",
            },
            "theme": "quartz",
            "domLayout": "autoHeight",
            "pagination": True,
            "paginationPageSize": 25,
            "rowHeight": 36,
            "headerHeight": 36,
        }

        with table_container:
            ui.aggrid(ag_opts).classes("w-full")
            ui.label("* Partner Efektif = max(partner_amount, minimum_payment) jika ada minimum payment").classes(
                "text-[10px] text-gray-600 mt-1")

    # ── UI ──
    with container:
        ui.label("💵 Revenue Sharing").classes("text-2xl font-bold text-white mb-2")
        ui.label("Ringkasan bagi hasil + sewa & minimum payment.").classes("text-sm text-gray-400 mb-4")

        # Range filter — update state then re-render
        def _on_from_change(e):
            state["from_period"] = e.value
            _render()

        def _on_to_change(e):
            state["to_period"] = e.value
            _render()

        with ui.row().classes("w-full items-center gap-4 mb-4"):
            ui.select(
                all_periods, value=state["from_period"], label="Dari Bulan",
                on_change=_on_from_change,
            ).props("dense outlined dark").classes("w-36")

            ui.label("\u2192").classes("text-gray-500 text-sm")

            ui.select(
                all_periods, value=state["to_period"], label="Sampai Bulan",
                on_change=_on_to_change,
            ).props("dense outlined dark").classes("w-36")

        summary_row = ui.row().classes("w-full gap-4 mb-6")
        table_container = ui.column().classes("w-full")

        _render()
