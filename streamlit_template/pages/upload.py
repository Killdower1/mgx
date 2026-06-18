import io
from datetime import datetime

import pandas as pd
import streamlit as st

from config import Config

def show_upload_data(config: Config):
    # Lazy imports to avoid circular dependency while app.py still hosts helpers
    from app import (
        excel_engine_from_filename,
        suggest_default_sheets,
        read_selected_sheets,
        apply_column_mapping_auto,
        to_numeric_clean,
        deduplicate_rows,
        aggregate_monthly,
        save_overwrite_periods,
        s_caption,
        df_show,
        DATA_CSV_PATH,
        cache_clear,
        load_app_data,
        rerun,
    )

    st.title("📤 Upload Data Bulanan (Overwrite by Period)")
    st.info("📋 Upload **per bulan**. Saat menyimpan, **semua data** pada periode (YYYY-MM) yang sama di CSV akan **dihapus**, lalu diganti data dari file ini.")

    uploaded_file = st.file_uploader("Choose Excel file", type=['xlsx','xls'])
    fallback_period = st.sidebar.text_input("🗓️ Fallback Period (YYYY-MM) bila kolom tanggal kosong", value=datetime.now().strftime("%Y-%m"))

    if uploaded_file is not None:
        try:
            engine = excel_engine_from_filename(uploaded_file.name)
            file_bytes = uploaded_file.getvalue()
            buf = io.BytesIO(file_bytes)

            # -- Sheet picker
            xls = pd.ExcelFile(buf, engine=engine)
            st.subheader("📑 Pilih Sheet")
            default_sheets = suggest_default_sheets(xls.sheet_names)
            selected_sheets = st.multiselect("Gunakan sheet berikut:", xls.sheet_names, default=default_sheets)
            if not selected_sheets:
                st.warning("Pilih minimal satu sheet."); return

            # -- Preview
            try:
                s_caption("Preview 10 baris pertama dari sheet pertama terpilih")
                prev = pd.read_excel(io.BytesIO(file_bytes), sheet_name=selected_sheets[0], nrows=10, engine=engine)
                df_show(prev, use_container_width=True)
            except ImportError as ie:
                st.error(f"❌ Dependensi pembaca Excel belum terpasang untuk '{engine}'. Install paket yang sesuai (e.g. `pip install openpyxl`). Detail: {ie}")
                return
            except Exception:
                pass

            # -- Read all selected sheets with explicit engine
            full_df_raw = read_selected_sheets(file_bytes, selected_sheets, engine)
            if full_df_raw.empty:
                st.error("❌ Sheet terpilih kosong."); return

            # Mapping manual
            st.subheader("🧭 Column Mapping")
            auto_map = apply_column_mapping_auto(full_df_raw)
            col_list = list(full_df_raw.columns)

            def _idx(colname):
                return (col_list.index(colname)+1) if (colname in col_list) else 0

            col_outlet  = st.selectbox("Kolom Outlet → outlet_name", ["<None>"]+col_list, index=_idx(auto_map.get("outlet_name","")))
            col_harga   = st.selectbox("Kolom Harga → harga", ["<None>"]+col_list, index=_idx(auto_map.get("harga","")))
            col_tanggal = st.selectbox("Kolom Tanggal → tanggal (opsional)", ["<None>"]+col_list, index=_idx(auto_map.get("tanggal","")))
            col_area    = st.selectbox("Kolom Area → area (opsional)", ["<None>"]+col_list, index=_idx(auto_map.get("area","")))
            col_type    = st.selectbox("Kolom Jenis/Type (Foto/Unlock/Print) → type", ["<None>"]+col_list, index=_idx(auto_map.get("type","")))

            if col_outlet == "<None>" or col_harga == "<None>":
                st.error("❌ Wajib pilih kolom Outlet dan Harga."); return

            mapping = {col_outlet: "outlet_name", col_harga: "harga"}
            if col_tanggal != "<None>": mapping[col_tanggal] = "tanggal"
            if col_area    != "<None>": mapping[col_area]    = "area"
            if col_type    != "<None>": mapping[col_type]    = "type"

            cleaned = full_df_raw.rename(columns=mapping).copy()

            # Scale harga
            st.subheader("Harga Scale")
            scale_option = st.radio("Pilih scale harga:", ["x1 (normal)","÷10","÷100","÷1000"], index=0)
            scale_value = {"x1 (normal)":1.0,"÷10":0.1,"÷100":0.01,"÷1000":0.001}[scale_option]
            cleaned["harga"] = to_numeric_clean(cleaned["harga"]) * scale_value

            if "tanggal" in cleaned.columns:
                cleaned["tanggal"] = pd.to_datetime(cleaned["tanggal"], errors="coerce")
            if "outlet_name" in cleaned.columns:
                cleaned["outlet_name"] = cleaned["outlet_name"].astype(str).str.strip()
            if "area" not in cleaned.columns:
                cleaned["area"] = ""

            # DIAG: Distribusi type
            if "type" in cleaned.columns:
                s_caption("Distribusi nilai kolom Type (untuk derive Foto/Unlock/Print):")
                vc = cleaned["type"].astype(str).str.strip().str.lower().value_counts().head(15)
                df_show(vc.to_frame("count"), use_container_width=True)

            # Dedup
            tmp_for_dedup = cleaned.copy()
            deduped, dd_audit = deduplicate_rows(tmp_for_dedup)

            st.subheader("🧮 Ringkasan Excel RAW (setelah mapping, cleaning & dedup)")
            st.write("- Rows sebelum dedup: **{:,}**".format(dd_audit['rows_before']))
            st.write("- Rows sesudah dedup: **{:,}**  (hapus **{:,}** duplikat)".format(dd_audit['rows_after'], dd_audit['dup_removed']))
            st.write("- Total Harga sesudah dedup: **{}**".format(Config().format_currency(dd_audit['sum_after'])))
            st.write("- Key dedup: **{}**".format(', '.join(dd_audit['subset']) or '(none)'))

            # Agregasi
            processed_df, derive_audit = aggregate_monthly(deduped, config, fallback_period=fallback_period)

            st.subheader("🧪 Derive Audit (dari kolom Type)")
            st.write("- Match Foto  : **{:,}** rows".format(derive_audit.get('match_foto',0)))
            st.write("- Match Unlock: **{:,}** rows".format(derive_audit.get('match_unlock',0)))
            st.write("- Match Print : **{:,}** rows".format(derive_audit.get('match_print',0)))

            st.subheader("🔎 Preview Hasil Agregasi")
            show_cols = ["periode","outlet_name","area","total_revenue","foto_qty","unlock_qty","print_qty","conversion_rate"]
            df_show(processed_df[show_cols].head(25), use_container_width=True)

            st.subheader("🧾 Audit — Perbandingan Total (Excel vs Agregasi)")
            total_raw = float(dd_audit['sum_after'])
            total_aggr = float(processed_df["total_revenue"].sum())
            st.write("- Total Harga **Excel RAW (DEDUP & SCALE)**: **{}**".format(Config().format_currency(total_raw)))
            st.write("- Total Revenue **Agregasi file ini**: **{}**".format(Config().format_currency(total_aggr)))
            st.write("- Selisih (Agregasi - Raw): **{}**".format(Config().format_currency(total_aggr - total_raw)))

            if st.button("🚀 Save (Overwrite periode terpilih)"):
                with st.spinner("Menyimpan (overwrite by period)..."):
                    merged, ow = save_overwrite_periods(processed_df, DATA_CSV_PATH)
                    per_uploaded = ow["periods_overwritten"]
                    before_total = ow["before_total"]; after_total = ow["after_total"]
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("✅ Data berhasil di-overwrite berdasarkan periode!")
                    st.subheader("🧾 Audit — Overwrite by Period")
                    st.write("- Periode di-overwrite: **{}**".format(', '.join(per_uploaded)))
                    st.write("- Total di CSV (sebelum overwrite): **{}**".format(Config().format_currency(before_total)))
                    st.write("- Total di CSV (sesudah overwrite): **{}**".format(Config().format_currency(after_total)))
                    st.info("Periode tersedia sekarang: **{}**".format(', '.join(ow['remaining_periods'])))
                    csv_subset = merged[merged["periode"].isin(per_uploaded)]
                    csv_total_for_periods = float(csv_subset["total_revenue"].sum())
                    st.write("- Total di CSV (periode file ini): **{}**".format(Config().format_currency(csv_total_for_periods)))
                    st.write("- Selisih (CSV - Agregasi file ini): **{}**".format(Config().format_currency(csv_total_for_periods - total_aggr)))
                    rerun()

        except ImportError as ie:
            st.error(f"❌ Dependency untuk membaca Excel belum terpasang. Install sesuai engine: {ie}")
        except Exception as e:
            st.error(f"❌ Error reading/processing file: {e}")
