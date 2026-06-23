"""
📤 Upload Data Bulanan (Overwrite by Period) — NiceGUI edition.
Port of Streamlit's upload page with full functional parity.
"""
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

from nicegui import ui
import pandas as pd
import numpy as np

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
SECTION_T = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"
METRIC_LBL = "font-size: 0.75rem; color: #a6adc8; text-transform: uppercase; letter-spacing: 0.5px;"

# ── DATA paths (mirror Streamlit's config) ──
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template" / "data"
DATA_CSV_PATH = DATA_DIR / "difotoin_data.csv"

# ═══════════════════════════════════════════════
#  LOGIC FUNCTIONS (ported from app.py — pure Python)
# ═══════════════════════════════════════════════

def _excel_engine(filename: str) -> str:
    return "openpyxl" if str(filename).lower().endswith(".xlsx") else "xlrd"

def _suggest_default_sheets(sheet_names):
    priority = ["data", "sheet1", "transaksi", "report", "database"]
    scored = sorted(sheet_names, key=lambda s: next((i for i, p in enumerate(priority) if p in s.lower()), 999))
    return scored[:1] if scored else sheet_names[:1]

def _read_selected_sheets(file_bytes, selected_sheets, engine):
    dfs = []
    for sheet in selected_sheets:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, engine=engine, dtype=str)
        if not df.empty:
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def _apply_column_mapping_auto(df):
    mapping = {}
    lower_cols = {c: c for c in df.columns}
    for keyword, target in [
        ("outlet", "outlet_name"), ("nama outlet", "outlet_name"), ("nama_outlet", "outlet_name"),
        ("harga", "harga"), ("nominal", "harga"), ("total", "harga"), ("amount", "harga"),
        ("tanggal", "tanggal"), ("date", "tanggal"), ("tgl", "tanggal"),
        ("area", "area"), ("cabang", "area"), ("branch", "area"),
        ("type", "type"), ("jenis", "type"), ("kategori", "type"),
    ]:
        for col in df.columns:
            if keyword in col.lower():
                mapping[target] = col
                break
    return {v: k for k, v in mapping.items()}

def _to_numeric_clean(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r"[^0-9,\-]", "", regex=True).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)

def _deduplicate_rows(df, subset=None):
    rows_before = len(df)
    if subset is None:
        subset = [c for c in ["outlet_name", "harga", "tanggal"] if c in df.columns]
    deduped = df.drop_duplicates(subset=subset, keep="first").copy() if subset else df.copy()
    rows_after = len(deduped)
    return deduped, {
        "rows_before": rows_before, "rows_after": rows_after,
        "dup_removed": rows_before - rows_after, "subset": subset,
        "sum_after": float(deduped.get("harga", pd.Series(dtype=float)).fillna(0).astype(float).sum()),
    }

def _aggregate_monthly(df, fallback_period=None):
    result = df.copy()
    if "periode" not in result.columns:
        if "tanggal" in result.columns:
            dt = pd.to_datetime(result["tanggal"], errors="coerce")
            result["periode"] = dt.dt.strftime("%Y-%m")
        else:
            result["periode"] = fallback_period or datetime.now().strftime("%Y-%m")
    result["total_revenue"] = _to_numeric_clean(result.get("harga", 0))
    result["foto_qty"] = 0
    result["unlock_qty"] = 0
    result["print_qty"] = 0
    if "type" in result.columns:
        t = result["type"].astype(str).str.strip().str.lower()
        result["foto_qty"] = (t.str.contains("foto", na=False)).astype(int)
        result["unlock_qty"] = (t.str.contains("unlock", na=False)).astype(int)
        result["print_qty"] = (t.str.contains("print|cetak", na=False, regex=True)).astype(int)
    result["conversion_rate"] = np.where(
        result["foto_qty"] > 0, (result["unlock_qty"] / result["foto_qty"] * 100), 0.0
    )
    if "harga" in result.columns:
        result.drop(columns=["harga"], inplace=True, errors="ignore")
    derive_audit = {
        "match_foto": int(result["foto_qty"].sum()),
        "match_unlock": int(result["unlock_qty"].sum()),
        "match_print": int(result["print_qty"].sum()),
    }
    return result, derive_audit

def _save_overwrite_periods(df, csv_path):
    df_save = df.copy()
    periods = df_save["periode"].dropna().unique().tolist() if "periode" in df_save.columns else []
    try:
        existing = pd.read_csv(csv_path, dtype=str)
    except (FileNotFoundError, Exception):
        existing = pd.DataFrame()
    before_total = float(
        existing.get("total_revenue", pd.Series(dtype=float)).fillna(0).astype(float).sum()
    ) if not existing.empty else 0.0
    if not existing.empty and periods:
        existing = existing[~existing["periode"].astype(str).str.strip().isin(periods)].copy()
    merged = pd.concat([existing, df_save], ignore_index=True)
    merged.to_csv(csv_path, index=False)
    after_total = float(merged.get("total_revenue", pd.Series(dtype=float)).fillna(0).astype(float).sum())
    remaining = sorted(merged["periode"].dropna().unique().tolist()) if "periode" in merged.columns else []
    return merged, {
        "periods_overwritten": periods,
        "before_total": before_total,
        "after_total": after_total,
        "remaining_periods": remaining,
    }

def _fmt_currency(amount) -> str:
    try:
        return f"Rp {int(round(float(amount))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"


# ═══════════════════════════════════════════════
#  VALIDATION
# ═══════════════════════════════════════════════

def _validate_upload_df(df, required_cols):
    errors = []
    for col in required_cols:
        if col not in df.columns:
            errors.append(f"Kolom '{col}' tidak ditemukan setelah mapping.")
        elif df[col].dropna().empty:
            errors.append(f"Kolom '{col}' kosong setelah mapping.")
    return (len(errors) == 0, errors)


# ═══════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════

def _render_table(df, max_rows=25):
    """Render ui.table from DataFrame."""
    if df.empty:
        ui.label("(kosong)").classes("text-gray-400 italic text-xs")
        return
    cols = [{"name": c, "label": c, "field": c, "align": "left"} for c in df.columns]
    ui.table(
        rows=df.head(max_rows).to_dict("records"),
        columns=cols,
        pagination={"rowsPerPage": 10, "rowsNumber": min(len(df), max_rows)},
    ).classes("w-full").props("dark flat dense")


# ═══════════════════════════════════════════════
#  PAGE
# ═══════════════════════════════════════════════

def create_page(container: ui.column):
    """Build the Upload Data page."""
    container.clear()

    # ── State ──
    state = {
        "file_bytes": None,
        "file_name": "",
        "engine": "openpyxl",
        "sheet_names": [],
        "selected_sheets": [],
        "raw_df": None,
        "cleaned_df": None,
        "processed_df": None,
        "dd_audit": {},
        "derive_audit": {},
    }

    with container:
        ui.label("📤 Upload Data Bulanan (Overwrite by Period)").classes("text-2xl font-bold text-white mb-2")
        ui.label("Upload per bulan. Saat menyimpan, semua data pada periode (YYYY-MM) yang sama di CSV akan dihapus, lalu diganti data dari file ini.").classes(
            "text-sm text-gray-400 mb-4")

        # ── Content area that rebuilds step by step ──
        content = ui.column().classes("w-full")

        def reset():
            state["file_bytes"] = None
            state["file_name"] = ""
            state["sheet_names"] = []
            state["selected_sheets"] = []
            state["raw_df"] = None
            state["cleaned_df"] = None
            state["processed_df"] = None
            state["dd_audit"] = {}
            state["derive_audit"] = {}
            content.clear()
            render_step1()

        # ══════════════════════════════════════════
        #  STEP 1: File Upload + Sheet Selection
        # ══════════════════════════════════════════

        def render_step1():
            content.clear()
            with content:
                ui.label("Langkah 1: Pilih File Excel").style(SECTION_T).classes("mb-2")

                upload = ui.upload(
                    label="Pilih file Excel (.xlsx / .xls)",
                    on_upload=lambda e: _on_file_uploaded(e),
                ).props("accept=.xlsx,.xls dark").classes("w-full mb-4")

                fallback_period_input = ui.input(
                    "🗓️ Fallback Period (YYYY-MM) bila kolom tanggal kosong",
                    value=datetime.now().strftime("%Y-%m"),
                ).props("dense outlined dark").classes("w-full mb-4")
                fallback_period_input.visible = False  # Show after upload

                state["fallback_period_input"] = fallback_period_input

        def _on_file_uploaded(e):
            content.clear()
            with content:
                ui.label("⏳ Memproses file...").classes("text-gray-400")

            # Read file
            state["file_bytes"] = e.content.read()
            state["file_name"] = e.name
            state["engine"] = _excel_engine(e.name)

            try:
                xls = pd.ExcelFile(io.BytesIO(state["file_bytes"]), engine=state["engine"])
                state["sheet_names"] = xls.sheet_names
            except Exception as ex:
                content.clear()
                with content:
                    ui.label(f"❌ Gagal membaca file: {ex}").classes("text-red-400")
                    ui.button("🔙 Kembali", on_click=reset).props("flat")
                return

            content.clear()
            with content:
                ui.label(f"📁 {e.name}").classes("text-sm text-gray-400 mb-2")

                # Sheet picker
                ui.label("📑 Pilih Sheet").style(SECTION_T).classes("mb-2")
                default_sheets = _suggest_default_sheets(state["sheet_names"])
                sheet_select = ui.select(
                    state["sheet_names"],
                    value=default_sheets,
                    multiple=True,
                    label="Gunakan sheet berikut:",
                ).props("dense outlined dark use-chips").classes("w-full mb-4")
                state["sheet_select"] = sheet_select

                # Fallback period
                fb = ui.input(
                    "🗓️ Fallback Period (YYYY-MM) bila kolom tanggal kosong",
                    value=datetime.now().strftime("%Y-%m"),
                ).props("dense outlined dark").classes("w-full mb-4")
                state["fallback_input"] = fb

                def on_sheets_confirmed():
                    sheets = sheet_select.value
                    if not sheets:
                        ui.notify("Pilih minimal satu sheet.", type="warning")
                        return
                    state["selected_sheets"] = sheets
                    state["fallback_period"] = fb.value.strip()
                    _process_file()

                ui.button("✅ Lanjut ke Mapping", on_click=on_sheets_confirmed, color="primary").classes("mt-2")

        # ══════════════════════════════════════════
        #  STEP 2: Process + Column Mapping
        # ══════════════════════════════════════════

        def _process_file():
            content.clear()
            with content:
                ui.label("⏳ Membaca data...").classes("text-gray-400")

            try:
                raw = _read_selected_sheets(
                    state["file_bytes"], state["selected_sheets"], state["engine"]
                )
            except Exception as ex:
                content.clear()
                with content:
                    ui.label(f"❌ Gagal membaca sheet: {ex}").classes("text-red-400")
                    ui.button("🔙 Kembali", on_click=reset).props("flat")
                return

            if raw.empty:
                content.clear()
                with content:
                    ui.label("❌ Sheet terpilih kosong.").classes("text-red-400")
                    ui.button("🔙 Kembali", on_click=reset).props("flat")
                return

            state["raw_df"] = raw
            col_list = list(raw.columns)
            auto_map = _apply_column_mapping_auto(raw)

            def _idx(name):
                if name in col_list:
                    return col_list.index(name) + 1
                return 0

            content.clear()
            with content:
                ui.label("🧭 Column Mapping").style(SECTION_T).classes("mb-2")
                ui.label("Petakan kolom dari file Excel ke field yang diperlukan.").classes(
                    "text-xs text-gray-400 mb-3")

                # Preview
                ui.label("Preview data (10 baris pertama):").classes("text-sm text-gray-300 mb-1")
                _render_table(raw.head(10))

                col_outlet = ui.select(
                    ["<None>"] + col_list,
                    value=auto_map.get("outlet_name", "<None>"),
                    label="Kolom Outlet → outlet_name *",
                ).props("dense outlined dark").classes("w-full mb-3")

                col_harga = ui.select(
                    ["<None>"] + col_list,
                    value=auto_map.get("harga", "<None>"),
                    label="Kolom Harga → harga *",
                ).props("dense outlined dark").classes("w-full mb-3")

                col_tanggal = ui.select(
                    ["<None>"] + col_list,
                    value=auto_map.get("tanggal", "<None>"),
                    label="Kolom Tanggal → tanggal (opsional)",
                ).props("dense outlined dark").classes("w-full mb-3")

                col_area = ui.select(
                    ["<None>"] + col_list,
                    value=auto_map.get("area", "<None>"),
                    label="Kolom Area → area (opsional)",
                ).props("dense outlined dark").classes("w-full mb-3")

                col_type = ui.select(
                    ["<None>"] + col_list,
                    value=auto_map.get("type", "<None>"),
                    label="Kolom Jenis/Type → type (opsional)",
                ).props("dense outlined dark").classes("w-full mb-3")

                # Scale
                ui.label("Harga Scale").style(SECTION_T).classes("mb-2")
                scale_select = ui.select(
                    ["x1 (normal)", "÷10", "÷100", "÷1000"],
                    value="x1 (normal)",
                    label="Pilih scale harga",
                ).props("dense outlined dark").classes("w-full mb-4")

                error_lbl = ui.label("").classes("text-sm")

                def on_mapping_confirm():
                    o = col_outlet.value
                    h = col_harga.value
                    if o == "<None>" or h == "<None>":
                        error_lbl.classes("text-red-400")
                        error_lbl.set_text("❌ Wajib pilih kolom Outlet dan Harga.")
                        return

                    mapping = {o: "outlet_name", h: "harga"}
                    if col_tanggal.value != "<None>":
                        mapping[col_tanggal.value] = "tanggal"
                    if col_area.value != "<None>":
                        mapping[col_area.value] = "area"
                    if col_type.value != "<None>":
                        mapping[col_type.value] = "type"

                    scale_val = {"x1 (normal)": 1.0, "÷10": 0.1, "÷100": 0.01, "÷1000": 0.001}[scale_select.value]

                    cleaned = raw.rename(columns=mapping).copy()
                    cleaned["harga"] = _to_numeric_clean(cleaned["harga"]) * scale_val

                    if "tanggal" in cleaned.columns:
                        cleaned["tanggal"] = pd.to_datetime(cleaned["tanggal"], errors="coerce")
                    if "outlet_name" in cleaned.columns:
                        cleaned["outlet_name"] = cleaned["outlet_name"].astype(str).str.strip()
                    if "area" not in cleaned.columns:
                        cleaned["area"] = ""

                    # Validate
                    is_valid, val_errors = _validate_upload_df(cleaned, ["outlet_name", "harga"])
                    if not is_valid:
                        error_lbl.classes("text-red-400")
                        error_lbl.set_text("❌ Validasi gagal. Perbaiki mapping.")
                        for err in val_errors:
                            ui.label(f"⚠️ {err}").classes("text-xs text-orange-400")
                        return

                    state["cleaned_df"] = cleaned
                    _review_data(cleaned, scale_select.value)

                ui.button("✅ Lanjut ke Review", on_click=on_mapping_confirm, color="primary").classes("mt-2")

        # ══════════════════════════════════════════
        #  STEP 3: Review + Save
        # ══════════════════════════════════════════

        def _review_data(cleaned, scale_label):
            content.clear()
            with content:
                ui.label("Review Data").style(SECTION_T).classes("mb-2")

                # Type distribution
                if "type" in cleaned.columns:
                    ui.label("Distribusi nilai kolom Type:").classes("text-sm text-gray-300 mb-1")
                    vc = cleaned["type"].astype(str).str.strip().str.lower().value_counts().head(15)
                    _render_table(vc.to_frame("count"))

                # Dedup
                deduped, dd_audit = _deduplicate_rows(cleaned)
                state["dd_audit"] = dd_audit

                ui.label("🧮 Ringkasan Excel RAW (setelah mapping, cleaning & dedup)").classes(
                    "text-md font-semibold text-white mt-4 mb-2")
                with ui.card().style(CARD).classes("w-full mb-4"):
                    ui.label(f"Rows sebelum dedup: {dd_audit['rows_before']:,}").classes("text-sm text-gray-300")
                    ui.label(f"Rows sesudah dedup: {dd_audit['rows_after']:,} (hapus {dd_audit['dup_removed']:,} duplikat)").classes(
                        "text-sm text-gray-300")
                    ui.label(f"Total Harga sesudah dedup: {_fmt_currency(dd_audit['sum_after'])}").classes(
                        "text-sm text-gray-300")
                    ui.label(f"Key dedup: {', '.join(dd_audit['subset']) or '(none)'}").classes("text-sm text-gray-300")

                # Aggregate
                processed, derive_audit = _aggregate_monthly(deduped, state.get("fallback_period"))
                state["processed_df"] = processed
                state["derive_audit"] = derive_audit

                ui.label("🧪 Derive Audit (dari kolom Type)").classes("text-md font-semibold text-white mt-4 mb-2")
                with ui.card().style(CARD).classes("w-full mb-4"):
                    ui.label(f"Match Foto: {derive_audit['match_foto']:,} rows").classes("text-sm text-gray-300")
                    ui.label(f"Match Unlock: {derive_audit['match_unlock']:,} rows").classes("text-sm text-gray-300")
                    ui.label(f"Match Print: {derive_audit['match_print']:,} rows").classes("text-sm text-gray-300")

                # Preview aggregated
                ui.label("🔎 Preview Hasil Agregasi").classes("text-md font-semibold text-white mt-4 mb-2")
                show_cols = [c for c in [
                    "periode", "outlet_name", "area", "total_revenue",
                    "foto_qty", "unlock_qty", "print_qty", "conversion_rate",
                ] if c in processed.columns]
                _render_table(processed[show_cols].head(25))

                # Audit
                total_raw = float(dd_audit["sum_after"])
                total_aggr = float(processed["total_revenue"].sum())

                ui.label("🧾 Audit — Perbandingan Total").classes("text-md font-semibold text-white mt-4 mb-2")
                with ui.card().style(CARD).classes("w-full mb-4"):
                    ui.label(f"Total Harga Excel RAW (DEDUP & SCALE): {_fmt_currency(total_raw)}").classes(
                        "text-sm text-gray-300")
                    ui.label(f"Total Revenue Agregasi file ini: {_fmt_currency(total_aggr)}").classes(
                        "text-sm text-gray-300")
                    ui.label(f"Selisih (Agregasi - Raw): {_fmt_currency(total_aggr - total_raw)}").classes(
                        "text-sm text-gray-300")

                status_lbl = ui.label("").classes("text-sm")

                def on_save():
                    try:
                        merged, ow = _save_overwrite_periods(processed, DATA_CSV_PATH)
                    except Exception as ex:
                        status_lbl.classes("text-red-400")
                        status_lbl.set_text(f"❌ Gagal menyimpan: {ex}")
                        return

                    per_up = ow["periods_overwritten"]
                    before_t = ow["before_total"]
                    after_t = ow["after_total"]

                    csv_subset = merged[merged["periode"].isin(per_up)]
                    csv_total_for_periods = float(csv_subset["total_revenue"].sum()) if not csv_subset.empty else 0

                    status_lbl.classes("text-green-400")
                    status_lbl.set_text(f"✅ Data berhasil disimpan! {len(per_up)} periode di-overwrite.")

                    # Show details
                    with ui.card().style(CARD).classes("w-full mt-4"):
                        ui.label("🧾 Audit — Overwrite by Period").classes("text-md font-semibold text-white mb-2")
                        ui.label(f"Periode di-overwrite: {', '.join(per_up)}").classes("text-sm text-gray-300")
                        ui.label(f"Total di CSV (sebelum): {_fmt_currency(before_t)}").classes("text-sm text-gray-300")
                        ui.label(f"Total di CSV (sesudah): {_fmt_currency(after_t)}").classes("text-sm text-gray-300")
                        ui.label(f"Periode tersedia: {', '.join(ow['remaining_periods'])}").classes(
                            "text-sm text-gray-300")
                        ui.label(f"Total di CSV (periode file ini): {_fmt_currency(csv_total_for_periods)}").classes(
                            "text-sm text-gray-300")
                        ui.label(f"Selisih (CSV - Agregasi): {_fmt_currency(csv_total_for_periods - total_aggr)}").classes(
                            "text-sm text-gray-300")

                    with ui.row().classes("gap-4 mt-4"):
                        ui.button("📤 Upload Lagi", on_click=reset, color="primary")
                        ui.button("🏠 Ke Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat")

                ui.button("💾 Save (Overwrite periode terpilih)", on_click=on_save, color="positive").classes("mt-4")

        # Start at step 1
        render_step1()
