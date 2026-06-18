import hashlib
from typing import Optional, List, Dict

import numpy as np
import pandas as pd
import streamlit as st

from config import OUTLET_MAPPING_PATH
from components.compat import df_show, table_height, DEFAULT_TABLE_MAX_HEIGHT, HAS_COLUMN_CONFIG, rerun
from components.ui_helpers import _clean_master_values, bool_series
from services.auth import load_deleted_outlets, save_deleted_outlets


def render_master_data_editor(title: str, key: str, values: List[str]) -> None:
    from app import load_master_data, save_master_data, apply_master_data, cache_clear, load_app_data
    st.markdown(f"**{title}**")
    source = pd.DataFrame({
        "delete": False,
        "value": _clean_master_values(values),
    })
    editor_config = None
    if HAS_COLUMN_CONFIG:
        try:
            editor_config = {
                "delete": st.column_config.CheckboxColumn("Delete", width="small"),
                "value": st.column_config.TextColumn(title, width="medium"),
            }
        except Exception:
            editor_config = None

    with st.form(f"master_data_{key}_form"):
        new_value = st.text_input("Tambah baru", key=f"master_data_{key}_new")
        if hasattr(st, "data_editor"):
            edited = st.data_editor(
                source,
                use_container_width=True,
                hide_index=True,
                height=table_height(len(source), 220, DEFAULT_TABLE_MAX_HEIGHT),
                num_rows="fixed",
                column_config=editor_config,
                key=f"master_data_{key}_editor",
            )
        else:
            edited = source.copy()
            df_show(source.drop(columns=["delete"]), use_container_width=True, hide_index=True)
            st.warning("Versi Streamlit ini belum mendukung edit langsung di tabel.")
        submitted = st.form_submit_button(f"Save {title}", type="primary")

    if submitted:
        edited_df = pd.DataFrame(edited)
        if "delete" not in edited_df.columns:
            edited_df["delete"] = False
        if "value" not in edited_df.columns:
            edited_df["value"] = ""
        keep_mask = ~bool_series(edited_df["delete"])
        final_values = edited_df.loc[keep_mask, "value"].dropna().astype(str).str.strip().tolist()
        new_value = str(new_value or "").strip()
        if new_value:
            final_values.append(new_value)
        final_values = _clean_master_values(final_values)
        if not final_values:
            st.error(f"{title} minimal harus punya 1 data.")
            return

        master = load_master_data()
        master[key] = final_values
        save_master_data(master)
        apply_master_data()
        try:
            cache_clear(load_app_data)
        except Exception:
            pass
        st.success(f"{title} berhasil disimpan.")
        rerun()

# ---- pages lainnya (CRUD, Trend, Conversion, Ranking, Comparison, Admin, Upload) ----
def show_outlet_crud(df, config, processor):
    from app import INDONESIA_AREAS, KATEGORI_TEMPAT, SUB_KATEGORI_TEMPAT
    st.title("🗃️ CRUD Data Outlet & Master Data")
    outlet_mapping = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()
    if outlet_mapping.empty and not df.empty:
        base = df.copy(deep=True)
        outlets = base['outlet_name'].unique()
        outlet_mapping = pd.DataFrame({
            'outlet_name': outlets,
            'area': base.groupby('outlet_name')['area'].first().values if "area" in base.columns else "",
            'kategori_tempat': base.groupby('outlet_name')['kategori_tempat'].first().values if "kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            'sub_kategori_tempat': base.groupby('outlet_name')['sub_kategori_tempat'].first().values if "sub_kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            'tipe_tempat': base.groupby('outlet_name')['tipe_tempat'].first().values if "tipe_tempat" in base.columns else "Indoor"
        })
    tab1, tab2, tab3 = st.tabs(["🏪 Outlet Management", "📋 Master Data Kategori", "🗺️ Master Data Area"])
    with tab1:
        s1, s2, s3, s4 = st.tabs(["📋 View All", "➕ Add New", "✏️ Edit", "🗑️ Delete"])
        with s1:
            st.subheader("📋 All Outlet Data")
            df_show(outlet_mapping, use_container_width=True, hide_index=True) if not outlet_mapping.empty else st.info("No outlet data available")
        with s2:
            st.subheader("➕ Add New Outlet")
            with st.form("add_outlet_form"):
                new_outlet_name = st.text_input("Outlet Name")
                new_area = st.selectbox("Area", INDONESIA_AREAS)
                new_kategori = st.selectbox("Kategori Tempat", KATEGORI_TEMPAT)
                new_sub_kategori = st.selectbox("Sub Kategori Tempat", SUB_KATEGORI_TEMPAT)
                new_tipe = st.selectbox("Tipe Tempat", ["Indoor","Outdoor","Semi-Outdoor"])
                if st.form_submit_button("Add Outlet") and new_outlet_name:
                    if 'outlet_name' in outlet_mapping and new_outlet_name in outlet_mapping['outlet_name'].values:
                        st.error("❌ Outlet already exists!")
                    else:
                        new_row = pd.DataFrame({'outlet_name':[new_outlet_name],'area':[new_area],
                                                'kategori_tempat':[new_kategori],'sub_kategori_tempat':[new_sub_kategori],
                                                'tipe_tempat':[new_tipe]})
                        outlet_mapping = pd.concat([outlet_mapping, new_row], ignore_index=True)
                        outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                        st.success("✅ Outlet added successfully!"); rerun()
        with s3:
            st.subheader("✏️ Edit Outlet")
            if not outlet_mapping.empty:
                outlet_to_edit = st.selectbox("Select Outlet to Edit", outlet_mapping['outlet_name'].tolist())
                if outlet_to_edit:
                    row = outlet_mapping[outlet_mapping['outlet_name']==outlet_to_edit].iloc[0]
                    with st.form("edit_outlet_form"):
                        edit_area = st.selectbox("Area", INDONESIA_AREAS, index=INDONESIA_AREAS.index(row['area']) if row['area'] in INDONESIA_AREAS else 0)
                        edit_kat = st.selectbox("Kategori Tempat", KATEGORI_TEMPAT, index=KATEGORI_TEMPAT.index(row['kategori_tempat']) if row['kategori_tempat'] in KATEGORI_TEMPAT else 0)
                        edit_sub = st.selectbox("Sub Kategori Tempat", SUB_KATEGORI_TEMPAT, index=SUB_KATEGORI_TEMPAT.index(row['sub_kategori_tempat']) if row['sub_kategori_tempat'] in SUB_KATEGORI_TEMPAT else 0)
                        pilihan_tipe = ["Indoor","Outdoor","Semi-Outdoor"]
                        edit_tipe = st.selectbox("Tipe Tempat", pilihan_tipe, index=pilihan_tipe.index(row['tipe_tempat']) if row['tipe_tempat'] in pilihan_tipe else 0)
                        if st.form_submit_button("Update Outlet"):
                            outlet_mapping.loc[outlet_mapping['outlet_name']==outlet_to_edit, ['area','kategori_tempat','sub_kategori_tempat','tipe_tempat']] = [edit_area, edit_kat, edit_sub, edit_tipe]
                            outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                            st.success("✅ Outlet updated successfully!"); rerun()
            else:
                st.info("No outlets available to edit")
        with s4:
            st.subheader("🗑️ Delete Outlet")
            if not outlet_mapping.empty:
                outlet_to_delete = st.selectbox("Select Outlet to Delete", outlet_mapping['outlet_name'].tolist())
                if outlet_to_delete and st.button("🗑️ Confirm Delete"):
                    outlet_mapping = outlet_mapping[outlet_mapping['outlet_name']!=outlet_to_delete]
                    outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                    st.success("✅ Outlet deleted successfully!"); rerun()
            else:
                st.info("No outlets available to delete")
    with tab2:
        st.subheader("📋 Master Data Kategori & Sub Kategori")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Kategori Tempat**")
            df_show(pd.DataFrame({'Kategori': KATEGORI_TEMPAT}), use_container_width=True, hide_index=True)
            with st.form("add_kategori_form"):
                nk = st.text_input("Nama Kategori Baru")
                if st.form_submit_button("Tambah Kategori"):
                    if nk and nk not in KATEGORI_TEMPAT:
                        KATEGORI_TEMPAT.append(nk); st.success(f"✅ Kategori '{nk}' berhasil ditambahkan!"); rerun()
                    else: st.error("❌ Kategori sudah ada atau kosong!")
        with c2:
            st.markdown("**Sub Kategori Tempat**")
            df_show(pd.DataFrame({'Sub Kategori': SUB_KATEGORI_TEMPAT}), use_container_width=True, hide_index=True)
            with st.form("add_sub_kategori_form"):
                ns = st.text_input("Nama Sub Kategori Baru")
                if st.form_submit_button("Tambah Sub Kategori"):
                    if ns and ns not in SUB_KATEGORI_TEMPAT:
                        SUB_KATEGORI_TEMPAT.append(ns); st.success(f"✅ Sub Kategori '{ns}' berhasil ditambahkan!"); rerun()
                    else: st.error("❌ Sub Kategori sudah ada atau kosong!")
    with tab3:
        st.subheader("🗺️ Master Data Area (Kota & Kabupaten Indonesia)")
        a1, a2 = st.columns([2,1])
        with a1:
            st.markdown("**Daftar Area Indonesia**")
            df_show(pd.DataFrame({'Area': INDONESIA_AREAS}), use_container_width=True, hide_index=True)
        with a2:
            with st.form("add_area_form"):
                na = st.text_input("Nama Kota/Kabupaten Baru")
                if st.form_submit_button("Tambah Area"):
                    if na and na not in INDONESIA_AREAS:
                        INDONESIA_AREAS.append(na); INDONESIA_AREAS.sort(); st.success(f"✅ Area '{na}' berhasil ditambahkan!"); rerun()
                    else: st.error("❌ Area sudah ada atau kosong!")
            st.info("📊 Total Area: {}".format(len(INDONESIA_AREAS)))

def suggest_outlet_metadata(outlet_name: str, current_row: Optional[dict] = None) -> dict:
    from app import KATEGORI_TEMPAT, SUB_KATEGORI_TEMPAT
    name = str(outlet_name or "").strip()
    text = name.lower()
    row = current_row or {}

    def has_any(words):
        return any(word in text for word in words)

    area_rules = [
        ("Jakarta", ["jakarta", "pik", "ancol", "senayan", "sarinah", "tmii", "jgc", "monas", "mandiri", "jis", "central park", "neo soho", "ashta", "pantjoran", "kota intan", "lapangan banteng", "taman literasi"]),
        ("Bali", ["bali", "kuta", "sanur", "gwk", "ubud", "bedugul", "ngurah rai", "beachwalk", "discovery mall", "dewata", "denpasar"]),
        ("Yogyakarta", ["jogja", "yogya", "malioboro", "heha", "obelix", "tugu jogja", "sleman"]),
        ("Bogor", ["bogor", "puncak", "sentul", "daong", "kopi tubing", "nicole", "kembali ke alam"]),
        ("Bekasi", ["bekasi", "deltamas", "cikarang"]),
        ("Tangerang", ["tangerang", "alam sutera", "flavor bliss", "lippo village"]),
        ("Samarinda", ["samarinda", "citra niaga"]),
        ("Semarang", ["semarang", "ambarawa"]),
        ("Batam", ["batam", "batamu"]),
        ("Malang", ["malang"]),
        ("Bandung", ["bandung", "castello"]),
    ]

    area = str(row.get("area", "") or "").strip()
    area_reason = "pakai data existing"
    area_conf = 55
    if not area or area.lower() in ["none", "nan", "lainnya"]:
        for candidate, keywords in area_rules:
            if has_any(keywords):
                area = candidate
                area_reason = "nama outlet mengandung keyword lokasi"
                area_conf = 82
                break
    if not area:
        area = "Lainnya"
        area_reason = "lokasi belum kebaca dari nama"
        area_conf = 35

    kategori = "Lainnya"
    sub = "Lainnya"
    tipe = "Indoor"
    cat_conf = 45
    cat_reason = "fallback umum"

    if has_any(["mall", "aeon", "living world", "neo soho", "city plaza", "sarinah", "beachwalk", "discovery mall", "bali icon", "central park", "ashta"]):
        kategori, sub, tipe, cat_conf = "Mall", "Shopping Center", "Indoor", 86
        cat_reason = "terdeteksi shopping center/mall"
    elif has_any(["hotel", "resort", "sheraton", "aryaduta", "alana", "ayodya", "villa", "vacation hotel"]):
        kategori, sub, tipe, cat_conf = "Hotel", "Resort/Hotel", "Indoor", 84
        cat_reason = "terdeteksi hotel/resort"
    elif has_any(["kopi", "koffie", "coffee", "cafe", "kopitiam", "burger", "buerger", "resto", "restaurant", "pantjoran"]):
        kategori, sub, tipe, cat_conf = "Restoran", "Coffee Shop", "Indoor", 80
        cat_reason = "terdeteksi cafe/restoran"
    elif has_any(["pantai", "beach", "kuta", "sanur", "sea view", "waterfront"]):
        kategori, sub, tipe, cat_conf = "Wisata", "Pantai", "Outdoor", 82
        cat_reason = "terdeteksi destinasi pantai/outdoor"
    elif has_any(["museum", "galeri", "mandiri"]):
        kategori, sub, tipe, cat_conf = "Museum", "Lainnya", "Indoor", 78
        cat_reason = "terdeteksi museum/galeri"
    elif has_any(["taman", "tmii", "ancol", "gwk", "heha", "obelix", "zoo", "kebun raya", "waterfall", "sky", "benteng", "puncak", "wisata", "park"]):
        kategori, sub, tipe, cat_conf = "Wisata", "Taman/Wisata Alam", "Outdoor", 78
        cat_reason = "terdeteksi objek wisata/taman"
    elif has_any(["event", "festival", "run", "gathering", "wedding", "ideas", "nextdev", "kompasianival", "bduck", "suzuki", "kpk", "bfn"]):
        kategori, sub, tipe, cat_conf = "Event Space", "Lainnya", "Semi-Outdoor", 76
        cat_reason = "terdeteksi event/aktivasi"
    elif has_any(["universitas", "university", "unj", "ui "]):
        kategori, sub, tipe, cat_conf = "Universitas", "Lainnya", "Indoor", 76
        cat_reason = "terdeteksi kampus"
    elif has_any(["sekolah", "school", "sph", "pelita harapan"]):
        kategori, sub, tipe, cat_conf = "Sekolah", "Lainnya", "Indoor", 76
        cat_reason = "terdeteksi sekolah"
    elif has_any(["airport", "bandara", "arrival", "ngurah rai"]):
        kategori, sub, tipe, cat_conf = "Transportasi", "Airport", "Indoor", 68
        cat_reason = "terdeteksi transport hub"
    elif has_any(["space", "creative", "cowork", "co-work"]):
        kategori, sub, tipe, cat_conf = "Komunitas", "Creative Space", "Indoor", 70
        cat_reason = "terdeteksi community/creative space"

    if kategori not in KATEGORI_TEMPAT:
        kategori = "Lainnya"
    if sub not in SUB_KATEGORI_TEMPAT:
        sub = "Lainnya"
    if tipe not in ["Indoor", "Outdoor", "Semi-Outdoor"]:
        tipe = "Indoor"

    existing_area = str(row.get("area", "") or "").strip()
    existing_kat = str(row.get("kategori_tempat", "") or "").strip()
    existing_sub = str(row.get("sub_kategori_tempat", "") or "").strip()
    existing_tipe = str(row.get("tipe_tempat", "") or "").strip()
    needs_update = (
        not existing_area or existing_area.lower() in ["none", "nan", "lainnya"] or
        existing_kat in ["", "Tidak Terkategorisasi"] or
        existing_sub in ["", "Tidak Terkategorisasi"] or
        existing_tipe in ["", "Tidak Terkategorisasi"]
    )

    confidence = int(round((area_conf + cat_conf) / 2))
    return {
        "outlet_name": name,
        "suggested_area": area,
        "suggested_kategori_tempat": kategori,
        "suggested_sub_kategori_tempat": sub,
        "suggested_tipe_tempat": tipe,
        "confidence": confidence,
        "reason": "{}; {}".format(area_reason, cat_reason),
        "needs_update": needs_update,
    }

def show_outlet_crud_v2(df, config, processor):
    from app import safe_unique_str, INDONESIA_AREAS, KATEGORI_TEMPAT, SUB_KATEGORI_TEMPAT, load_app_data, cache_clear
    st.title("Outlet Management")

    required_cols = ["outlet_name", "area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]
    outlet_mapping = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()

    if outlet_mapping.empty and not df.empty:
        base = df.copy(deep=True)
        outlets = base["outlet_name"].dropna().astype(str).unique()
        outlet_mapping = pd.DataFrame({
            "outlet_name": outlets,
            "area": base.groupby("outlet_name")["area"].first().reindex(outlets).fillna("").values if "area" in base.columns else "",
            "kategori_tempat": base.groupby("outlet_name")["kategori_tempat"].first().reindex(outlets).fillna("Tidak Terkategorisasi").values if "kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            "sub_kategori_tempat": base.groupby("outlet_name")["sub_kategori_tempat"].first().reindex(outlets).fillna("Tidak Terkategorisasi").values if "sub_kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            "tipe_tempat": base.groupby("outlet_name")["tipe_tempat"].first().reindex(outlets).fillna("Indoor").values if "tipe_tempat" in base.columns else "Indoor",
        })

    for col in required_cols:
        if col not in outlet_mapping.columns:
            outlet_mapping[col] = ""
    outlet_mapping = outlet_mapping[required_cols].copy()
    for col in required_cols:
        outlet_mapping[col] = outlet_mapping[col].fillna("").astype(str)
    outlet_mapping["outlet_name"] = outlet_mapping["outlet_name"].str.strip()
    outlet_mapping = outlet_mapping[outlet_mapping["outlet_name"] != ""].drop_duplicates("outlet_name", keep="last")
    deleted_outlets = set(load_deleted_outlets())

    if not df.empty and "outlet_name" in df.columns:
        source_outlets = df.copy(deep=True)
        source_outlets["outlet_name"] = source_outlets["outlet_name"].fillna("").astype(str).str.strip()
        source_outlets = source_outlets[source_outlets["outlet_name"] != ""]
        missing_names = sorted(set(source_outlets["outlet_name"]) - set(outlet_mapping["outlet_name"]) - deleted_outlets)

        if missing_names:
            def first_non_empty(frame, col, default_value=""):
                if col not in frame.columns:
                    return default_value
                values = frame[col].dropna().astype(str).str.strip()
                values = values[values != ""]
                return values.iloc[0] if len(values) else default_value

            new_rows = []
            missing_source = source_outlets[source_outlets["outlet_name"].isin(missing_names)]
            for outlet_name, outlet_rows in missing_source.groupby("outlet_name", sort=False):
                new_rows.append({
                    "outlet_name": outlet_name,
                    "area": first_non_empty(outlet_rows, "area"),
                    "kategori_tempat": first_non_empty(outlet_rows, "kategori_tempat", "Tidak Terkategorisasi"),
                    "sub_kategori_tempat": first_non_empty(outlet_rows, "sub_kategori_tempat", "Tidak Terkategorisasi"),
                    "tipe_tempat": first_non_empty(outlet_rows, "tipe_tempat", "Indoor"),
                })

            if new_rows:
                outlet_mapping = pd.concat([outlet_mapping, pd.DataFrame(new_rows)], ignore_index=True)
                outlet_mapping = outlet_mapping[required_cols].drop_duplicates("outlet_name", keep="last")
                outlet_mapping = outlet_mapping.sort_values("outlet_name").reset_index(drop=True)
                outlet_mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
                try: cache_clear(load_app_data)
                except Exception: pass
                st.info("{} outlet dari database transaksi otomatis ditambahkan ke CRUD mapping.".format(len(new_rows)))

    crud_modes = ["Edit Outlet", "Add Outlet", "AI Suggest", "Master Data", "Delete"]
    try:
        crud_mode = st.radio("Mode CRUD Outlet", crud_modes, horizontal=True, key="crud_v2_mode")
    except TypeError:
        crud_mode = st.radio("Mode CRUD Outlet", crud_modes, key="crud_v2_mode")

    if crud_mode == "Edit Outlet":
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Outlet", f"{len(outlet_mapping):,}")
        with m2:
            st.metric("Area", f"{outlet_mapping['area'].replace('', np.nan).nunique():,}")
        with m3:
            st.metric("Tipe", f"{outlet_mapping['tipe_tempat'].replace('', np.nan).nunique():,}")

        f1, f2, f3, f4 = st.columns([2.2, 1.2, 1.2, 1.2])
        with f1:
            search = st.text_input("Search outlet", placeholder="Ketik nama outlet...", key="crud_v2_search")
        with f2:
            area_filter = st.selectbox("Area", ["Semua"] + safe_unique_str(outlet_mapping, "area"), key="crud_v2_area")
        with f3:
            kategori_filter = st.selectbox("Kategori", ["Semua"] + safe_unique_str(outlet_mapping, "kategori_tempat"), key="crud_v2_kategori")
        with f4:
            tipe_filter = st.selectbox("Tipe", ["Semua"] + safe_unique_str(outlet_mapping, "tipe_tempat"), key="crud_v2_tipe")

        visible = outlet_mapping.copy()
        if search:
            visible = visible[visible["outlet_name"].str.contains(search, case=False, na=False)]
        if area_filter != "Semua":
            visible = visible[visible["area"] == area_filter]
        if kategori_filter != "Semua":
            visible = visible[visible["kategori_tempat"] == kategori_filter]
        if tipe_filter != "Semua":
            visible = visible[visible["tipe_tempat"] == tipe_filter]

        st.caption("Edit area, kategori, sub kategori, dan tipe langsung di tabel. Outlet name dikunci agar identitas outlet tidak berubah tanpa sengaja.")

        if visible.empty:
            st.info("Tidak ada outlet yang cocok dengan filter.")
        else:
            editor_config = None
            if HAS_COLUMN_CONFIG:
                area_options = sorted(set(INDONESIA_AREAS) | set(safe_unique_str(outlet_mapping, "area")))
                kategori_options = sorted(set(KATEGORI_TEMPAT) | set(safe_unique_str(outlet_mapping, "kategori_tempat")))
                sub_options = sorted(set(SUB_KATEGORI_TEMPAT) | set(safe_unique_str(outlet_mapping, "sub_kategori_tempat")))
                tipe_options = sorted(set(["Indoor", "Outdoor", "Semi-Outdoor"]) | set(safe_unique_str(outlet_mapping, "tipe_tempat")))
                try:
                    editor_config = {
                        "_index": st.column_config.TextColumn("Outlet", width="large"),
                        "area": st.column_config.SelectboxColumn("Area", options=area_options, width="medium"),
                        "kategori_tempat": st.column_config.SelectboxColumn("Kategori", options=kategori_options, width="medium"),
                        "sub_kategori_tempat": st.column_config.SelectboxColumn("Sub Kategori", options=sub_options, width="medium"),
                        "tipe_tempat": st.column_config.SelectboxColumn("Tipe", options=tipe_options, width="small"),
                    }
                except Exception:
                    editor_config = None

            editor_key_seed = "|".join(visible["outlet_name"].astype(str).tolist())
            editor_key = "crud_v2_editor_" + hashlib.md5(editor_key_seed.encode("utf-8")).hexdigest()[:12]
            with st.form("crud_v2_edit_form"):
                if hasattr(st, "data_editor"):
                    editor_data = visible[required_cols].copy().set_index("outlet_name")
                    editor_data.index.name = "Outlet"
                    edited_visible = st.data_editor(
                        editor_data,
                        use_container_width=True,
                        hide_index=False,
                        height=table_height(len(editor_data), 300, DEFAULT_TABLE_MAX_HEIGHT),
                        num_rows="fixed",
                        column_config=editor_config,
                        key=editor_key,
                    )
                else:
                    edited_visible = visible.copy()
                    df_show(visible, use_container_width=True, hide_index=True, column_config=editor_config)
                    st.warning("Versi Streamlit ini belum mendukung edit langsung di tabel.")

                c_save, c_info = st.columns([1, 4])
                with c_save:
                    save_edit = st.form_submit_button("Save Changes", type="primary")
                with c_info:
                    st.caption(f"Menampilkan {len(visible):,} dari {len(outlet_mapping):,} outlet.")

            if save_edit:
                edited_visible = pd.DataFrame(edited_visible).reset_index()
                if "Outlet" in edited_visible.columns:
                    edited_visible = edited_visible.rename(columns={"Outlet": "outlet_name"})
                elif "index" in edited_visible.columns and "outlet_name" not in edited_visible.columns:
                    edited_visible = edited_visible.rename(columns={"index": "outlet_name"})
                edited_visible = edited_visible[required_cols].copy()
                edited_visible["outlet_name"] = edited_visible["outlet_name"].astype(str).str.strip()
                if edited_visible["outlet_name"].eq("").any():
                    st.error("Outlet name tidak boleh kosong.")
                elif edited_visible["outlet_name"].duplicated().any():
                    st.error("Ada outlet name duplikat di hasil edit.")
                else:
                    merged = outlet_mapping.set_index("outlet_name")
                    merged.update(edited_visible.set_index("outlet_name"))
                    merged = merged.reset_index()[required_cols].sort_values("outlet_name").reset_index(drop=True)
                    merged.to_csv(OUTLET_MAPPING_PATH, index=False)
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("Outlet mapping berhasil disimpan.")
                    rerun()

    if crud_mode == "Add Outlet":
        st.subheader("Add New Outlet")
        with st.form("crud_v2_add_form"):
            new_name = st.text_input("Outlet Name")
            c1, c2 = st.columns(2)
            with c1:
                new_area = st.selectbox("Area", INDONESIA_AREAS)
                new_sub = st.selectbox("Sub Kategori", SUB_KATEGORI_TEMPAT)
            with c2:
                new_kategori = st.selectbox("Kategori", KATEGORI_TEMPAT)
                new_tipe = st.selectbox("Tipe", ["Indoor", "Outdoor", "Semi-Outdoor"])
            if st.form_submit_button("Add Outlet"):
                new_name = new_name.strip()
                if not new_name:
                    st.error("Outlet name wajib diisi.")
                elif new_name in outlet_mapping["outlet_name"].values:
                    st.error("Outlet sudah ada.")
                else:
                    new_row = pd.DataFrame([{
                        "outlet_name": new_name,
                        "area": new_area,
                        "kategori_tempat": new_kategori,
                        "sub_kategori_tempat": new_sub,
                        "tipe_tempat": new_tipe,
                    }])
                    updated = pd.concat([outlet_mapping, new_row], ignore_index=True)
                    updated = updated[required_cols].sort_values("outlet_name").reset_index(drop=True)
                    updated.to_csv(OUTLET_MAPPING_PATH, index=False)
                    deleted_outlets = [x for x in load_deleted_outlets() if x != new_name]
                    save_deleted_outlets(deleted_outlets)
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("Outlet berhasil ditambahkan.")
                    rerun()

    if crud_mode == "AI Suggest":
        st.subheader("AI Suggest Outlet Mapping")
        st.caption("AI lokal membaca nama outlet untuk menebak area, kategori, sub kategori, dan tipe. Lo tetap bisa edit hasilnya sebelum apply.")

        ai_source = outlet_mapping.copy()
        ai_source["needs_ai"] = ai_source.apply(
            lambda r: suggest_outlet_metadata(r.get("outlet_name", ""), r.to_dict()).get("needs_update", False),
            axis=1,
        )
        only_needs = st.checkbox("Tampilkan yang belum lengkap saja", value=True, key="crud_ai_only_needs")
        min_conf = st.slider("Minimum confidence", min_value=0, max_value=100, value=55, step=5, key="crud_ai_min_conf")

        suggestions = []
        for _, row in ai_source.iterrows():
            suggestion = suggest_outlet_metadata(row.get("outlet_name", ""), row.to_dict())
            if only_needs and not suggestion["needs_update"]:
                continue
            if int(suggestion["confidence"]) < int(min_conf):
                continue
            suggestions.append({
                "apply": False,
                "outlet_name": suggestion["outlet_name"],
                "current_area": row.get("area", ""),
                "current_kategori": row.get("kategori_tempat", ""),
                "suggested_area": suggestion["suggested_area"],
                "suggested_kategori_tempat": suggestion["suggested_kategori_tempat"],
                "suggested_sub_kategori_tempat": suggestion["suggested_sub_kategori_tempat"],
                "suggested_tipe_tempat": suggestion["suggested_tipe_tempat"],
                "confidence": suggestion["confidence"],
                "reason": suggestion["reason"],
            })

        if not suggestions:
            st.info("Tidak ada outlet yang cocok dengan filter AI Suggest.")
        else:
            suggestion_df = pd.DataFrame(suggestions)
            st.info("{} rekomendasi ditemukan. Centang `apply`, edit hasil rekomendasi kalau perlu, lalu klik Apply.".format(len(suggestion_df)))

            ai_config = None
            if HAS_COLUMN_CONFIG:
                try:
                    ai_config = {
                        "apply": st.column_config.CheckboxColumn("Apply", width="small"),
                        "outlet_name": st.column_config.TextColumn("Outlet", width="large"),
                        "current_area": st.column_config.TextColumn("Area Saat Ini", width="medium"),
                        "current_kategori": st.column_config.TextColumn("Kategori Saat Ini", width="medium"),
                        "suggested_area": st.column_config.SelectboxColumn("Area AI", options=sorted(set(INDONESIA_AREAS) | set(safe_unique_str(outlet_mapping, "area")) | {"Lainnya"}), width="medium"),
                        "suggested_kategori_tempat": st.column_config.SelectboxColumn("Kategori AI", options=sorted(set(KATEGORI_TEMPAT) | {"Lainnya"}), width="medium"),
                        "suggested_sub_kategori_tempat": st.column_config.SelectboxColumn("Sub Kategori AI", options=sorted(set(SUB_KATEGORI_TEMPAT) | {"Lainnya"}), width="medium"),
                        "suggested_tipe_tempat": st.column_config.SelectboxColumn("Tipe AI", options=["Indoor", "Outdoor", "Semi-Outdoor"], width="small"),
                        "confidence": st.column_config.NumberColumn("Confidence", min_value=0, max_value=100, width="small"),
                        "reason": st.column_config.TextColumn("Reason", width="large"),
                    }
                except Exception:
                    ai_config = None

            if hasattr(st, "data_editor"):
                edited_suggestion = st.data_editor(
                    suggestion_df,
                    use_container_width=True,
                    hide_index=True,
                    height=table_height(len(suggestion_df), 300, DEFAULT_TABLE_MAX_HEIGHT),
                    num_rows="fixed",
                    disabled=["outlet_name", "current_area", "current_kategori", "confidence", "reason"],
                    column_config=ai_config,
                    key="crud_ai_suggest_editor",
                )
            else:
                edited_suggestion = suggestion_df.copy()
                df_show(suggestion_df, use_container_width=True, hide_index=True)
                st.warning("Versi Streamlit ini belum mendukung edit langsung di tabel AI Suggest.")

            selected_ai = pd.DataFrame(edited_suggestion)
            selected_ai = selected_ai[selected_ai["apply"] == True].copy()
            if not selected_ai.empty:
                st.warning("{} outlet akan diupdate dari rekomendasi AI.".format(len(selected_ai)))
                confirm_ai = st.text_input("Ketik APPLY untuk menyimpan rekomendasi AI", key="crud_ai_confirm")
                if st.button("Apply AI Suggestions", type="primary", key="crud_ai_apply"):
                    if confirm_ai != "APPLY":
                        st.error("Konfirmasi belum benar. Ketik APPLY untuk menyimpan.")
                        return
                    updated = outlet_mapping.set_index("outlet_name")
                    for _, row in selected_ai.iterrows():
                        name = str(row["outlet_name"])
                        if name in updated.index:
                            updated.loc[name, "area"] = str(row["suggested_area"])
                            updated.loc[name, "kategori_tempat"] = str(row["suggested_kategori_tempat"])
                            updated.loc[name, "sub_kategori_tempat"] = str(row["suggested_sub_kategori_tempat"])
                            updated.loc[name, "tipe_tempat"] = str(row["suggested_tipe_tempat"])
                    updated = updated.reset_index()[required_cols].sort_values("outlet_name").reset_index(drop=True)
                    updated.to_csv(OUTLET_MAPPING_PATH, index=False)
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("Rekomendasi AI berhasil disimpan. Cek lagi di tab Edit Outlet kalau mau koreksi manual.")
                    rerun()

    if crud_mode == "Master Data":
        st.subheader("Master Data")
        st.caption("Edit nilai langsung di tabel, centang Delete untuk hapus, atau isi Tambah baru. Perubahan master data dipakai sebagai opsi di Add/Edit/AI Suggest.")
        c1, c2, c3 = st.columns(3)
        with c1:
            render_master_data_editor("Area", "areas", INDONESIA_AREAS)
        with c2:
            render_master_data_editor("Kategori", "kategori_tempat", KATEGORI_TEMPAT)
        with c3:
            render_master_data_editor("Sub Kategori", "sub_kategori_tempat", SUB_KATEGORI_TEMPAT)

    if crud_mode == "Delete":
        st.subheader("Delete Outlet")
        st.caption("Centang outlet yang mau dihapus dari mapping CRUD. Data transaksi historis tidak ikut dihapus.")

        delete_source = outlet_mapping.copy().sort_values("outlet_name").reset_index(drop=True)
        saved_delete = set(st.session_state.get("crud_v2_delete_selected", []))
        delete_source.insert(0, "delete", delete_source["outlet_name"].astype(str).isin(saved_delete))
        delete_cols = ["delete", "outlet_name", "area", "kategori_tempat", "tipe_tempat"]
        delete_source = delete_source[[c for c in delete_cols if c in delete_source.columns]]

        if hasattr(st, "data_editor"):
            delete_config = None
            if HAS_COLUMN_CONFIG:
                try:
                    delete_config = {
                        "delete": st.column_config.CheckboxColumn("Delete", width="small"),
                        "outlet_name": st.column_config.TextColumn("Outlet", width="large"),
                        "area": st.column_config.TextColumn("Area", width="medium"),
                        "kategori_tempat": st.column_config.TextColumn("Kategori", width="medium"),
                        "tipe_tempat": st.column_config.TextColumn("Tipe", width="small"),
                    }
                except Exception:
                    delete_config = None
            edited_delete = st.data_editor(
                delete_source,
                use_container_width=True,
                hide_index=True,
                height=table_height(len(delete_source), 300, DEFAULT_TABLE_MAX_HEIGHT),
                num_rows="fixed",
                disabled=[c for c in delete_source.columns if c != "delete"],
                column_config=delete_config,
                key="crud_v2_delete_editor",
            )
            edited_delete_df = pd.DataFrame(edited_delete)
            delete_flags = edited_delete_df["delete"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
            outlets_to_delete = edited_delete_df.loc[delete_flags, "outlet_name"].dropna().astype(str).tolist()
        else:
            df_show(delete_source.drop(columns=["delete"]), use_container_width=True, hide_index=True)
            st.warning("Versi Streamlit ini belum mendukung checklist tabel. Pakai pilihan manual di bawah.")
            outlets_to_delete = st.multiselect(
                "Pilih outlet",
                outlet_mapping["outlet_name"].tolist(),
                default=st.session_state.get("crud_v2_delete_selected", []),
            )

        c_set, c_clear = st.columns([1.2, 4])
        with c_set:
            if st.button("Lock Selection", key="crud_v2_delete_set"):
                st.session_state["crud_v2_delete_selected"] = outlets_to_delete
                st.success("{} outlet dipilih untuk delete.".format(len(outlets_to_delete)))
        with c_clear:
            if st.button("Clear Selection", key="crud_v2_delete_clear"):
                st.session_state["crud_v2_delete_selected"] = []
                rerun()

        selected_for_delete = st.session_state.get("crud_v2_delete_selected", outlets_to_delete)
        if outlets_to_delete and outlets_to_delete != selected_for_delete:
            selected_for_delete = outlets_to_delete

        if selected_for_delete:
            st.warning(f"{len(selected_for_delete)} outlet akan dihapus dari mapping CRUD.")
            df_show(
                outlet_mapping[outlet_mapping["outlet_name"].isin(selected_for_delete)][["outlet_name", "area", "kategori_tempat", "tipe_tempat"]],
                use_container_width=True,
                hide_index=True,
            )
            confirm_delete = st.text_input("Ketik DELETE untuk konfirmasi hapus", key="crud_v2_delete_confirm")
            if st.button("Confirm Delete", key="crud_v2_delete", type="primary"):
                if confirm_delete != "DELETE":
                    st.error("Konfirmasi belum benar. Ketik DELETE untuk menghapus.")
                    return
                updated = outlet_mapping[~outlet_mapping["outlet_name"].isin(selected_for_delete)].copy()
                updated.to_csv(OUTLET_MAPPING_PATH, index=False)
                deleted_now = set(load_deleted_outlets())
                deleted_now.update(str(x).strip() for x in selected_for_delete if str(x).strip())
                save_deleted_outlets(list(deleted_now))
                try: cache_clear(load_app_data)
                except Exception: pass
                st.session_state["crud_v2_delete_selected"] = []
                st.success("Outlet berhasil dihapus dari mapping CRUD.")
                rerun()

