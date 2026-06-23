"""
🤝 Kemitraan — partnership & financial analysis page.
Port of Streamlit's kemitraan page with full functional parity.
"""
from typing import Optional

from nicegui import ui
import pandas as pd
import numpy as np

import requests
import json
from pathlib import Path

CONFIG_PATH = Path('/var/www/difotoin-dashboard/streamlit_template/config/erpnext_config.json')

from services.kemitraan_adapter import (
    get_sharing_periods,
    load_sharing_outlets,
    build_kemitraan_financials,
    format_kemitraan_table,
    normalize_sharing_master,
    save_sharing_outlets,
    sync_sharing_to_mapping,
    get_dashboard_data,
    get_outlet_mapping,
    format_currency,
    get_config,
    get_kemitraan_services,
)

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
METRIC_VAL = "font-size: 1.2rem; font-weight: 700; color: #cdd6f4;"
METRIC_LBL = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px;"
SECTION_T = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"


def _fmt_num(n) -> str:
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def _render_table(df, max_rows=100):
    """Render ui.table from DataFrame."""
    if df.empty:
        ui.label("(kosong)").classes("text-gray-400 italic text-xs")
        return
    cols = [{"name": c, "label": c, "field": c, "align": "left"} for c in df.columns]
    ui.table(
        rows=df.head(max_rows).to_dict("records"),
        columns=cols,
        pagination={"rowsPerPage": 15, "rowsNumber": min(len(df), max_rows)},
    ).classes("w-full").props("dark flat dense")


# ═══════════════════════════════════════════════
#  PAGE
# ═══════════════════════════════════════════════

def create_page(container: ui.column):
    """Build the Kemitraan page."""
    container.clear()

    config = get_config()
    df = get_dashboard_data()
    mapping = get_outlet_mapping()
    sharing_periods = get_sharing_periods()
    tx_periods = sorted([str(p) for p in df.get("periode", pd.Series(dtype=str)).dropna().unique()]) if isinstance(df, pd.DataFrame) and not df.empty else []
    periods = sorted(set(sharing_periods + tx_periods))

    state = {
        "selected_period": periods[-1] if periods else None,
        "section": "satuan",  # 'satuan' or 'setting'
    }

    with container:
        ui.label("🤝 Kemitraan").classes("text-2xl font-bold text-white mb-2")
        ui.label("Analisis kemitraan outlet — revenue sharing, yield, dan BEP.").classes(
            "text-sm text-gray-400 mb-4")

        if not periods:
            ui.label("Belum ada data periode.").classes("text-gray-400 italic")
            return

        # ── Period selector ──
        period_sel = ui.select(
            periods, value=state["selected_period"], label="Periode",
        ).props("dense outlined dark").classes("w-full max-w-[300px] mb-4")

        # ── Tab: Kemitraan Satuan / Setting ──
        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="satuan").classes("w-full")

        with tabs:
            ui.tab("satuan", label="🤝 Kemitraan Satuan")
            ui.tab("setting", label="⚙️ Setting Kemitraan")

        # ── Content state ──
        kemitraan_cache = {}

        def compute_kemitraan(period):
            """Compute kemitraan financials for a period."""
            if period in kemitraan_cache:
                return kemitraan_cache[period]
            _, sharing_master = load_sharing_outlets(period)
            k = build_kemitraan_financials(df, sharing_master, mapping, period)
            kemitraan_cache[period] = k
            return k

        # ══════════════════════════════════════════
        #  TAB 1: KEMITRAAN SATUAN
        # ══════════════════════════════════════════

        with panels:
            with ui.tab_panel("satuan"):
                satuan_area = ui.column().classes("w-full")

                def render_satuan(period):
                    satuan_area.clear()
                    kemitraan = compute_kemitraan(period)
                    if kemitraan.empty:
                        with satuan_area:
                            ui.label("Belum ada data kemitraan untuk periode ini.").classes("text-gray-400 italic")
                        return

                    with satuan_area:
                        # ── Group by investor ──
                        people = kemitraan.copy()
                        people["investor_name"] = people["investor_name"].fillna("").astype(str).str.strip().replace("", "Belum diisi")

                        summary = people.groupby("investor_name", as_index=False).agg(
                            outlet_count=("outlet_name", "nunique"),
                            harga_beli=("harga_beli_kemitraan", "sum"),
                            revenue=("basis_bagi_hasil", "sum"),
                            pendapatan_mitra=("pendapatan_mitra", "sum"),
                            pendapatan_broker=("pendapatan_broker", "sum"),
                            pendapatan_difotoin=("pendapatan_difotoin", "sum"),
                            profit_difotoin=("profit_difotoin", "sum"),
                        )
                        summary["estimasi_bep_bulan"] = np.where(
                            (summary["harga_beli"] > 0) & (summary["pendapatan_mitra"] > 0),
                            summary["harga_beli"] / summary["pendapatan_mitra"],
                            np.nan,
                        )
                        summary["yield_bulanan"] = np.where(
                            summary["harga_beli"] > 0,
                            summary["pendapatan_mitra"] / summary["harga_beli"],
                            np.nan,
                        )
                        summary["yield_tahunan"] = summary["yield_bulanan"] * 12

                        # Summary table
                        ui.label("📊 Ringkasan Semua Kemitraan").style(SECTION_T).classes("mb-2")
                        sd = summary.sort_values("pendapatan_mitra", ascending=False).rename(columns={
                            "investor_name": "Kemitraan",
                            "outlet_count": "Jumlah Outlet",
                            "harga_beli": "Total Harga Beli",
                            "revenue": "Revenue/Basis",
                            "pendapatan_mitra": "Pendapatan Mitra",
                            "pendapatan_broker": "Pendapatan Broker",
                            "pendapatan_difotoin": "Pendapatan Difotoin",
                            "profit_difotoin": "Profit Difotoin",
                            "estimasi_bep_bulan": "BEP (bln)",
                            "yield_bulanan": "Yield Bulanan",
                            "yield_tahunan": "Yield Tahunan",
                        })
                        # Format currency columns
                        for col in ["Total Harga Beli", "Revenue/Basis", "Pendapatan Mitra",
                                    "Pendapatan Broker", "Pendapatan Difotoin", "Profit Difotoin"]:
                            if col in sd.columns:
                                sd[col] = sd[col].apply(lambda v: format_currency(v) if pd.notna(v) else "-")
                        for col in ["Yield Bulanan", "Yield Tahunan"]:
                            if col in sd.columns:
                                sd[col] = sd[col].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else "-")
                        if "BEP (bln)" in sd.columns:
                            sd["BEP (bln)"] = sd["BEP (bln)"].apply(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
                        _render_table(sd)

                        # Selectbox for detail
                        names = summary.sort_values("pendapatan_mitra", ascending=False)["investor_name"].tolist()

                        ui.separator().classes("my-4")
                        sel_name = ui.select(
                            names, value=names[0] if names else None,
                            label="Pilih kemitraan / pemilik",
                        ).props("dense outlined dark").classes("w-full max-w-[400px] mb-4")

                        detail_area = ui.column().classes("w-full")

                        def show_detail(name):
                            detail_area.clear()
                            if not name:
                                return
                            detail = people[people["investor_name"] == name].copy()
                            detail_cols = [
                                "outlet_id", "outlet_name", "area", "outlet_status_master",
                                "basis_bagi_hasil", "partner_share", "pendapatan_mitra",
                                "harga_beli_kemitraan", "estimasi_bep_bulan", "yield_bulanan", "yield_tahunan",
                            ]
                            avail = [c for c in detail_cols if c in detail.columns]
                            dd = detail[avail].sort_values("basis_bagi_hasil", ascending=False).rename(columns={
                                "outlet_id": "ID", "outlet_name": "Outlet", "area": "Area",
                                "outlet_status_master": "Status",
                                "basis_bagi_hasil": "Revenue/Basis",
                                "partner_share": "Partner Share",
                                "pendapatan_mitra": "Pendapatan Mitra",
                                "harga_beli_kemitraan": "Harga Beli",
                                "estimasi_bep_bulan": "BEP (bln)",
                                "yield_bulanan": "Yield Bulanan",
                                "yield_tahunan": "Yield Tahunan",
                            })
                            # Format
                            for col in ["Revenue/Basis", "Pendapatan Mitra", "Harga Beli"]:
                                if col in dd.columns:
                                    dd[col] = dd[col].apply(lambda v: format_currency(v) if pd.notna(v) else "-")
                            for col in ["Yield Bulanan", "Yield Tahunan"]:
                                if col in dd.columns:
                                    dd[col] = dd[col].apply(lambda v: f"{v*100:.1f}%" if pd.notna(v) else "-")
                            if "BEP (bln)" in dd.columns:
                                dd["BEP (bln)"] = dd["BEP (bln)"].apply(lambda v: f"{v:.1f}" if pd.notna(v) else "-")
                            if "Partner Share" in dd.columns:
                                dd["Partner Share"] = dd["Partner Share"].apply(lambda v: f"{v*100:.0f}%" if pd.notna(v) else "-")

                            with detail_area:
                                ui.label(f"📋 Detail Outlet — {name}").style(SECTION_T).classes("mb-2")
                                _render_table(dd)

                        sel_name.on("update:model-value", lambda e: show_detail(e.args) if hasattr(e, 'args') else None)
                        # Initial detail
                        if names:
                            show_detail(names[0])

                # Initial render
                period_sel.on("update:model-value", lambda e: render_satuan(e.args) if hasattr(e, 'args') else None)
                render_satuan(state["selected_period"])

            # ══════════════════════════════════════════
            #  TAB 2: SETTING KEMITRAAN
            # ══════════════════════════════════════════

            with ui.tab_panel("daftar"):
                with ui.column().classes("w-full p-2") as daftar_container:
                    _render_daftar_lead(daftar_container)

            with ui.tab_panel("setting"):
                setting_area = ui.column().classes("w-full")

                def render_setting():
                    setting_area.clear()
                    with setting_area:
                        ui.label("Upload Data Kemitraan").style(SECTION_T).classes("mb-2")
                        ui.label("Upload file outlet_update.xlsx untuk membuat/update master kemitraan.").classes(
                            "text-sm text-gray-400 mb-3")

                        # Upload
                        upload = ui.upload(
                            label="Pilih file outlet_update.xlsx",
                            on_upload=lambda e: _on_sharing_upload(e, setting_area, period_sel.value),
                        ).props("accept=.xlsx dark").classes("w-full mb-4")

                        ui.separator().classes("my-4")

                        # Master editor
                        ui.label("Master Kemitraan").style(SECTION_T).classes("mb-2")

                        if not sharing_periods:
                            ui.label("Upload file outlet_update.xlsx dulu untuk membuat master kemitraan.").classes(
                                "text-gray-400 italic")
                            return

                        edit_period_sel = ui.select(
                            sharing_periods,
                            value=sharing_periods[-1] if sharing_periods else None,
                            label="Periode master",
                        ).props("dense outlined dark").classes("w-full max-w-[300px] mb-4")

                        master_content = ui.column().classes("w-full")

                        def load_master(period):
                            master_content.clear()
                            if not period:
                                return
                            _, edit_df = load_sharing_outlets(period)
                            edit_df = normalize_sharing_master(edit_df)
                            if edit_df.empty:
                                with master_content:
                                    ui.label("Tidak ada data master untuk periode ini.").classes("text-gray-400 italic")
                                return

                            # Simplified editable table approach
                            # For now, show as readable table with a save button
                            with master_content:
                                ui.label(f"📋 Master — {len(edit_df)} outlet").classes("text-sm text-gray-300 mb-2")
                                cols = [{"name": c, "label": c, "field": c, "align": "left"} for c in edit_df.columns]
                                ui.table(
                                    rows=edit_df.to_dict("records"),
                                    columns=cols,
                                    pagination={"rowsPerPage": 15, "rowsNumber": len(edit_df)},
                                ).classes("w-full").props("dark flat dense")

                                status_lbl = ui.label("").classes("text-sm mt-2")

                                def on_save():
                                    try:
                                        cleaned = normalize_sharing_master(edit_df)
                                        save_sharing_outlets(period, cleaned)
                                        sync_sharing_to_mapping(cleaned, period)
                                        status_lbl.classes("text-green-400")
                                        status_lbl.set_text(f"✅ Master {period} tersimpan: {len(cleaned)} outlet.")
                                    except Exception as ex:
                                        status_lbl.classes("text-red-400")
                                        status_lbl.set_text(f"❌ Gagal menyimpan: {ex}")

                                ui.button("💾 Simpan Master", on_click=on_save, color="primary").classes("mt-2")

                        edit_period_sel.on("update:model-value", lambda e: load_master(e.args) if hasattr(e, 'args') else None)
                        load_master(edit_period_sel.value)

                render_setting()


# ═══════════════════════════════════════════════

# --- Daftar Lead (AG Grid + popup) ---

def _fetch_lk_from_erpnext():
    import requests, json
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        headers = {"Authorization": "token " + cfg["api_key"] + ":" + cfg["api_secret"]}
        base_url = cfg["url"]
        all_data = []
        limit_start = 0
        while True:
            r = requests.get(
                base_url + "/api/resource/Lead%20Kemitraan",
                headers=headers,
                params={"limit_page_length": 200, "limit_start": limit_start, "fields": '["*"]'},
                timeout=60,
            )
            if r.status_code != 200:
                break
            data = r.json().get("data", [])
            if not data:
                break
            all_data.extend(data)
            limit_start += 200
        if all_data:
            return pd.DataFrame(all_data)
        return pd.DataFrame()
    except Exception as ex:
        from nicegui import ui
        ui.notify("Gagal fetch ERPNext: " + str(ex), type="negative")
        return pd.DataFrame()


def _render_daftar_lead(container):
    df = _fetch_lk_from_erpnext()
    if df.empty:
        ui.label("Belum ada data Lead Kemitraan dari ERPNext.").classes("text-gray-400 italic mb-4")
        return

    total = len(df)
    ui.label(str(total) + " lead kemitraan").classes("text-sm text-gray-300 mb-3")

    css = (
        "<style>"
        ".ag-theme-balham-dark { "
        "--ag-background-color: #1e1e2e; --ag-header-background-color: #181825; "
        "--ag-odd-row-background-color: #1a1a2e; --ag-row-hover-color: #313244; "
        "--ag-border-color: #313244; --ag-font-size: 13px; "
        "--ag-header-height: 44px; --ag-row-height: 40px; "
        "--ag-selected-row-background-color: #2a2a4e; }"
        ".detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }"
        ".detail-table td { padding: 6px 10px; border: none; }"
        ".detail-table .lbl { font-weight: 600; color: #a6adc8; width: 150px; }"
        "</style>"
    )
    ui.add_head_html(css)

    def show_dialog(row):
        nama = str(row.get("nama_lengkap", "") or "").strip() or str(row.get("lead_name", "") or "").strip() or "-"
        flds = [
            ("ID", "name"), ("Nama", "nama_lengkap"),
            ("WhatsApp", "nomor_whatsapp"), ("Email", "email"),
            ("Kota Domisili", "kota_domisili"),
            ("Kota Penempatan", "kota_penempatan_mesin"),
            ("Pekerjaan", "pekerjaan_bisnis_saat_ini"),
            ("Sumber Info", "dari_mana_tahu_difotoin"),
            ("Status Lead", "status_lead"), ("Prioritas", "priority"),
            ("Sales PIC", "sales_pic"),
            ("Unit Diminati", "jumlah_unit_diminati"),
            ("Unit Final", "jumlah_unit_final"),
            ("Budget Investasi", "budget_investasi"),
            ("Investasi Dibahas", "harga_investasi_dibahas"),
            ("Skema Bayar", "skema_pembayaran"),
            ("Kesiapan DP", "kesiapan_dp"),
            ("Sudah Punya Lokasi", "sudah_punya_lokasi"),
            ("Jenis Lokasi", "jenis_lokasi"),
            ("Kapan Mulai", "kapan_ingin_mulai"),
            ("Hasil Follow Up", "hasil_follow_up_terakhir"),
            ("Last FO", "last_follow_up"), ("Next FO", "next_follow_up"),
            ("Next Step", "next_step"), ("Created", "creation"),
        ]
        with ui.dialog() as dialog, ui.card().style(
            "background: #1e1e2e; border: 1px solid #313244; border-radius: 12px; "
            "padding: 20px; min-width: 320px; max-width: 92vw; width: auto;"
        ).classes("responsive-dialog-card"):
            ui.label("Detail: " + nama).classes("text-lg font-bold text-white mb-4")
            parts = ["<table class='detail-table'>"]
            for i, (lbl, key) in enumerate(flds):
                val = str(row.get(key, "") or "")
                if not val.strip() or val in ("None", "nan"):
                    val = "-"
                bg = ";background:#1e1e2e" if i % 2 == 0 else ""
                parts.append("<tr style='" + bg + "'>")
                parts.append("<td class='lbl'>" + lbl + "</td>")
                parts.append("<td style='color:#cdd6f4'>" + val + "</td></tr>")
            parts.append("</table>")
            ui.html("".join(parts)).classes("w-full")
            ui.button("Tutup", on_click=dialog.close).props("flat").classes("mt-4")
        dialog.open()

    grid_rows = []
    for idx, raw in df.iterrows():
        nm = str(raw.get("nama_lengkap", "") or "").strip() or str(raw.get("lead_name", "") or "").strip() or "-"
        grid_rows.append({
            "Nama": nm,
            "WhatsApp": str(raw.get("nomor_whatsapp", "") or "").strip() or "-",
            "Kota": str(raw.get("kota_penempatan_mesin", "") or "").strip() or str(raw.get("kota_domisili", "") or "").strip() or "-",
            "Status": str(raw.get("status_lead", "") or "").strip() or "-",
            "Prio": str(raw.get("priority", "") or "").strip() or "-",
            "_idx": idx,
        })

    ui.label(str(total) + " record | klik Nama untuk detail").classes("text-xs text-gray-500 mb-2")

    grid = ui.aggrid({
        "columnDefs": [
            {"headerName": "Nama", "field": "Nama", "minWidth": 160, "flex": 2,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True, "pinned": "left",
             "cellStyle": {"color": "#89b4fa", "textDecoration": "underline", "cursor": "pointer", "fontWeight": "600"}},
            {"headerName": "WhatsApp", "field": "WhatsApp", "minWidth": 120, "flex": 1,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
            {"headerName": "Kota", "field": "Kota", "minWidth": 120, "flex": 1,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
            {"headerName": "Status", "field": "Status", "minWidth": 100, "flex": 1,
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
            {"headerName": "Prio", "field": "Prio", "width": 90, "pinned": "right",
             "sortable": True, "filter": "agTextColumnFilter", "floatingFilter": True},
        ],
        "rowData": grid_rows,
        "pagination": True,
        "paginationPageSize": 25,
        "paginationPageSizeSelector": [10, 25, 50, 100],
        "domLayout": "autoHeight",
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True, "floatingFilter": True},
        "animateRows": True,
        "rowHeight": 44,
        "headerHeight": 44,
        "enableCellTextSelection": True,
    }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: auto; min-height: 300px;")

    def on_cell_click(e):
        col = e.args.get("colId", "")
        if col == "Nama":
            idx = e.args.get("data", {}).get("_idx", -1)
            r = df.iloc[idx] if 0 <= idx < len(df) else None
            if r is not None:
                show_dialog(r)
            grid.run_grid_method("deselectAll")

    grid.on("cellClicked", on_cell_click)


#  SHARING UPLOAD HANDLER
# ═══════════════════════════════════════════════

def _on_sharing_upload(e, setting_area, period):
    """Handle sharing outlet file upload."""
    try:
        import io
        mod = get_kemitraan_services()
        parsed = mod.parse_sharing_outlet_excel(e)

        if parsed.empty:
            ui.notify("⚠️ File tidak mengandung data sharing yang valid.", type="warning")
            return

        # Infer period from filename
        period_name = mod.infer_period_from_filename(e.name)

        # Save
        mod.save_sharing_outlets(period_name, parsed)
        mod.sync_sharing_to_mapping(parsed, period_name)

        ui.notify(f"✅ Data sharing {period_name} tersimpan: {len(parsed)} outlet.", type="positive")

        # Refresh the page
        import asyncio
        asyncio.get_event_loop().call_later(1, ui.navigate.reload)

    except Exception as ex:
        ui.notify(f"❌ Gagal upload: {ex}", type="negative")
