"""
💵 Revenue Sharing — AG Grid, range filter, sewa & minimum payment.

Sumber kebenaran (audit 6 Agu 2026):
- Rp aktual (revenue, partner, broker) dari transaksi (rs_outlet cache, streaming rebuild).
- % share (P/B/D) = kontrak dari master outlet API difotoin.id (/api/outlets),
  fallback ke master sharing (sharing_outlets/<periode terakhir>), fallback rata-rata transaksi.
- Sewa = monthly_rent dari API outlets; MinPay = minimum_payment dari master sharing.
- ⚠️ ditampilkan kalau: minpay diterapkan, API ≠ master sharing, atau kontrak ≠ rata-rata transaksi.
"""
from pathlib import Path
import json
import math

from nicegui import ui

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import difotoin_api_adapter as api

SHARING_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template" / "data" / "sharing_outlets"
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"


def _norm(s: str) -> str:
    """Normalize outlet name for cross-source joining."""
    s = str(s or "").strip().lower()
    for c in "()-._/":
        s = s.replace(c, " ")
    return " ".join(s.split())


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _fmt(amount) -> str:
    try:
        return "Rp " + f"{int(round(float(amount))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"


def _load_api_master() -> dict:
    """norm(outlet) -> outlet record dari API (/api/outlets)."""
    out = {}
    try:
        for o in api.load_outlet_master():
            for key in (o.get("display_name"), o.get("name")):
                if key:
                    out.setdefault(_norm(key), o)
    except Exception:
        pass
    return out


def _load_sharing_master() -> dict:
    """norm(outlet) -> record master sharing (periode terbaru yang di-upload)."""
    try:
        periods = sorted(p.stem for p in SHARING_DIR.glob("*.json"))
        if not periods:
            return {}
        with open(SHARING_DIR / f"{periods[-1]}.json", encoding="utf-8") as f:
            rows = json.load(f)
        return {_norm(r.get("outlet_name", "")): r for r in rows if r.get("outlet_name")}
    except Exception:
        return {}


def create_page(container: ui.column):
    container.clear()

    all_periods = api.get_rs_periods()
    if not all_periods:
        with container:
            ui.label("Belum ada data.").classes("text-gray-400 italic")
        return

    api_master = _load_api_master()
    so_master = _load_sharing_master()

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
            if not name:
                continue
            if name not in om:
                om[name] = {"outlet_name": name, "total_revenue": 0.0, "partner_amount": 0.0,
                            "broker_amount": 0.0, "difotoin_amount": 0.0, "transactions": 0,
                            "pcts": [], "bcts": []}
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
            nm = _norm(name)
            a = api_master.get(nm)
            s = so_master.get(nm)

            # ── Kontrak share: API (%) → master sharing (fraksi ×100) → rata-rata transaksi ──
            api_p = _num(a.get("partner_share")) if a else None
            api_b = _num(a.get("broker_share")) if a else None
            so_p_raw = _num(s.get("partner_share")) if s else None
            so_b_raw = _num(s.get("broker_share")) if s else None
            so_p = so_p_raw * 100 if so_p_raw is not None else None
            so_b = so_b_raw * 100 if so_b_raw is not None else None

            tx_avg_p = sum(o["pcts"]) / len(o["pcts"]) if o["pcts"] else 0.0
            tx_avg_b = sum(o["bcts"]) / len(o["bcts"]) if o["bcts"] else 0.0

            p_share = api_p if api_p is not None else so_p
            b_share = api_b if api_b is not None else so_b
            p_disp = p_share if p_share is not None else tx_avg_p
            b_disp = b_share if b_share is not None else tx_avg_b
            d_disp = max(0.0, 100.0 - p_disp - b_disp)

            # ── Sewa: API monthly_rent → master sharing ──
            rent = _num(a.get("monthly_rent")) if a else None
            if rent is None:
                rent = _num(s.get("monthly_rent")) if s else None
            rent = rent or 0.0

            # ── MinPay: master sharing → API partner_minimal_share ──
            minpay = _num(s.get("minimum_payment")) if s else None
            if minpay is None and a:
                minpay = _num(a.get("partner_minimal_share"))
            minpay = minpay or 0.0

            # ── Flag / catatan ──
            notes = []
            if minpay > 0 and o["partner_amount"] < minpay:
                notes.append("minpay")
            if api_p is not None and so_p is not None and abs(api_p - so_p) > 0.5:
                notes.append(f"API {api_p:.0f}%≠master {so_p:.0f}%")
            elif p_share is not None and tx_avg_p > 0 and abs(p_share - tx_avg_p) > 2.0:
                notes.append(f"kontrak {p_share:.0f}%≠tx {tx_avg_p:.1f}%")

            eff_p = o["partner_amount"]
            minpay_applied = minpay > 0 and o["partner_amount"] < minpay
            if minpay_applied:
                eff_p = minpay
            eff_difo = o["total_revenue"] - eff_p - o["broker_amount"]

            o["avg_partner_pct"] = p_disp
            o["avg_broker_pct"] = b_disp
            o["difotoin_pct"] = d_disp
            o["monthly_rent"] = rent
            o["minimum_payment"] = minpay
            o["effective_partner"] = eff_p
            o["minpay_applied"] = minpay_applied
            o["effective_difotoin"] = eff_difo
            o["investor"] = (s or {}).get("investor_name", "") if s else ""
            o["note"] = "⚠️ " + ", ".join(notes) if notes else ""
            result.append(o)

        # Hanya outlet dengan revenue > 0 (buang sisa event/outlet mati)
        result = [o for o in result if o["total_revenue"] > 0]
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
            row_data.append({
                "outlet": o["outlet_name"],
                "investor": o.get("investor", ""),
                "tx": o["transactions"],
                "revenue": _fmt(o["total_revenue"]),
                "p_pct": f"{o['avg_partner_pct']:.1f}%",
                "minpay": _fmt(o["minimum_payment"]) if o["minimum_payment"] > 0 else "-",
                "eff_p": _fmt(o["effective_partner"]),
                "note": o["note"],
                "b_pct": f"{o['avg_broker_pct']:.1f}%",
                "b_rp": _fmt(o["broker_amount"]),
                "d_pct": f"{o['difotoin_pct']:.1f}%",
                "d_eff": _fmt(o["effective_difotoin"]),
                "sewa": _fmt(o["monthly_rent"]) if o["monthly_rent"] > 0 else "-",
            })

        ag_opts = {
            "columnDefs": [
                {"field": "outlet", "headerName": "Outlet", "pinned": "left", "minWidth": 120},
                {"field": "investor", "headerName": "Investor", "minWidth": 90},
                {"field": "tx", "headerName": "Tx", "minWidth": 50},
                {"field": "revenue", "headerName": "Revenue", "minWidth": 100},
                {"field": "p_pct", "headerName": "P%", "minWidth": 55},
                {"field": "minpay", "headerName": "MinPay", "minWidth": 85},
                {"field": "eff_p", "headerName": "Partner Rp*", "minWidth": 110},
                {"field": "note", "headerName": "⚠️", "width": 130, "maxWidth": 160, "resizable": True},
                {"field": "b_pct", "headerName": "B%", "minWidth": 55},
                {"field": "b_rp", "headerName": "Broker Rp", "minWidth": 110},
                {"field": "d_pct", "headerName": "D%", "minWidth": 55},
                {"field": "d_eff", "headerName": "Difotoin Rp*", "minWidth": 110},
                {"field": "sewa", "headerName": "Sewa", "minWidth": 85},
            ],
            "rowData": row_data,
            "defaultColDef": {
                "sortable": True,
                "filter": True,
                "resizable": True,
                "cellStyle": {"backgroundColor": "#1e1e2e", "color": "#cdd6f4", "border": "none"},
                "headerClass": "text-gray-400",
            },
            "autoSizeStrategy": {
                "type": "fitCellContents",
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
            ui.label(
                "* Partner Efektif = max(partner_amount, minimum_payment). "
                "P%/B%/D% = share kontrak (master API outlets / sharing). "
                "⚠️ = minpay diterapkan atau kontrak beda dengan transaksi. "
                "Rp aktual dari transaksi."
            ).classes("text-[10px] text-gray-600 mt-1")

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
