"""📋 Lead Partnership — manage partnership leads from ERPNext."""

from typing import Optional

import pandas as pd
import streamlit as st

from services.erpnext import (
    load_erpnext_config,
    save_erpnext_config,
    check_connection,
    fetch_lead_partnerships,
    get_lead_partnership,
    create_lead_partnership,
    update_lead_partnership,
    get_jenis_options,
    get_skema_options,
    get_lokasi_options,
    get_status_options,
    get_status_kemitraan_options,
)
from components.compat import rerun, HAS_COLUMN_CONFIG


def show_lead_partnership_page():
    st.title("📋 Lead Partnership")
    st.caption("Manajemen data partnership lead dari ERPNext — lihat, cari, edit, dan tambah lead.")

    # ----------------- CONFIG CHECK -----------------
    cfg = load_erpnext_config()
    connected = False

    if not cfg.get("url") or not cfg.get("api_key"):
        _render_config_form(cfg)
        return
    else:
        connected_ok, connected_msg = check_connection()
        connected = connected_ok
        if not connected_ok:
            st.warning(f"⚠️ {connected_msg}")
            with st.expander("🔧 Konfigurasi ERPNext"):
                _render_config_form(cfg)
            # Still show cached/generic data if connection fails

    # ----------------- TOOLBAR -----------------
    cols = st.columns([3, 1, 1])
    with cols[0]:
        search_q = st.text_input("🔍 Cari lead (nama, tempat, PIC, kota)", key="lp_search")
    with cols[1]:
        filter_status = st.selectbox(
            "Filter Status",
            ["Semua"] + [s for s in get_status_options() if s],
            key="lp_filter_status",
        )
    with cols[2]:
        refresh = st.button("🔄 Refresh Data", type="secondary", use_container_width=True)

    # ----------------- FETCH -----------------
    if connected:
        df = fetch_lead_partnerships(limit=200)
    else:
        df = pd.DataFrame()

    if df.empty:
        st.info("Belum ada data Lead Partnership dari ERPNext.")
        if not connected:
            st.caption("Pastikan konfigurasi ERPNext benar dan koneksi tersambung.")
        return

    # ----------------- FILTER -----------------
    if filter_status and filter_status != "Semua":
        df = df[df.get("status", "").astype(str).str.strip() == filter_status].copy()

    if search_q.strip():
        q = search_q.strip().lower()
        mask = (
            df.get("lead_name", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("tempat", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("pic", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("kota", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
            | df.get("name", pd.Series(dtype=str)).astype(str).str.lower().str.contains(q, na=False)
        )
        df = df[mask].copy()

    # ----------------- TABS -----------------
    tab_list, tab_add = st.tabs(["📋 Daftar Lead", "➕ Tambah Lead Baru"])

    with tab_list:
        _render_lead_table(df)

    with tab_add:
        if connected:
            _render_create_form()
        else:
            st.info("Sambungkan ke ERPNext dulu untuk menambah lead baru.")


# ================= CONFIG FORM =================

def _render_config_form(cfg: dict):
    st.subheader("🔧 Konfigurasi ERPNext")
    st.caption("Masukkan kredensial ERPNext untuk mengakses Lead Partnership.")

    with st.form("erpnext_config_form"):
        url = st.text_input(
            "URL ERPNext",
            value=cfg.get("url", ""),
            placeholder="https://erp.midory.id",
            key="lp_config_url",
        )
        api_key = st.text_input(
            "API Key",
            value=cfg.get("api_key", ""),
            type="password",
            key="lp_config_key",
        )
        api_secret = st.text_input(
            "API Secret",
            value=cfg.get("api_secret", ""),
            type="password",
            key="lp_config_secret",
        )
        submitted = st.form_submit_button("💾 Simpan & Uji Koneksi", type="primary")
        if submitted:
            if not url.strip():
                st.error("URL ERPNext wajib diisi.")
            elif not api_key.strip():
                st.error("API Key wajib diisi.")
            else:
                save_erpnext_config({
                    "url": url.strip().rstrip("/"),
                    "api_key": api_key.strip(),
                    "api_secret": api_secret.strip(),
                })
                ok, msg = check_connection()
                if ok:
                    st.success(f"✅ {msg}")
                    rerun()
                else:
                    st.error(f"❌ {msg}")


# ================= LEAD TABLE =================

def _render_lead_table(df: pd.DataFrame):
    st.write(f"**{len(df)}** lead ditemukan.")

    display = df.copy()
    # Format columns for display
    col_map = {
        "name": "ID Lead",
        "lead_name": "Nama Lead",
        "jenis": "Jenis",
        "tempat": "Tempat",
        "pic": "PIC",
        "kota": "Kota",
        "lokasi": "Lokasi",
        "skema": "Skema",
        "status": "Status",
    }
    avail_cols = [c for c in col_map if c in display.columns]
    display = display[avail_cols].rename(columns=col_map)

    # Make status column more visual
    if "Status" in display.columns:
        display["Status"] = display["Status"].apply(_status_badge)

    # Use st.dataframe with config
    if HAS_COLUMN_CONFIG:
        col_config = {
            "ID Lead": st.column_config.TextColumn("ID Lead", width="small"),
            "Nama Lead": st.column_config.TextColumn("Nama Lead", width="medium"),
            "PIC": st.column_config.TextColumn("PIC", width="medium"),
        }
    else:
        col_config = None

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        height=400,
    )

    # ----------------- DETAIL / EDIT SELECTION -----------------
    lead_names = df["name"].tolist() if "name" in df.columns else []
    if lead_names:
        st.markdown("---")
        st.subheader("✏️ Edit Lead")
        selected = st.selectbox(
            "Pilih Lead untuk diedit",
            lead_names,
            format_func=lambda x: f"{x} — {_get_lead_label(df, x)}",
            key="lp_select_edit",
        )
        if selected:
            _render_edit_form(selected)


def _get_lead_label(df: pd.DataFrame, name: str) -> str:
    row = df[df["name"] == name]
    if row.empty:
        return name
    r = row.iloc[0]
    parts = [str(r.get("lead_name", "")), str(r.get("tempat", "")), str(r.get("kota", ""))]
    return " - ".join(p for p in parts if p.strip())


def _status_badge(status) -> str:
    status_str = str(status or "").strip()
    if not status_str:
        return "-"
    badges = {
        "Open": "🟢",
        "Contact": "🔵",
        "Negotiation": "🟡",
        "Won": "✅",
        "Lost": "🔴",
        "On Hold": "🟠",
        "Spam": "⚫",
    }
    emoji = badges.get(status_str, "⚪")
    return f"{emoji} {status_str}"


# ================= EDIT FORM =================

def _render_edit_form(record_name: str):
    detail = get_lead_partnership(record_name)
    if not detail:
        st.error(f"Tidak bisa mengambil detail lead {record_name}.")
        return

    with st.form(f"edit_lp_{record_name}"):
        st.markdown(f"**Mengedit:** {record_name}")
        cols = st.columns(2)

        with cols[0]:
            lead_name = st.text_input(
                "Nama Lead", value=detail.get("lead_name", ""),
                key=f"lp_edit_name_{record_name}",
            )
            jenis = st.selectbox(
                "Jenis", get_jenis_options(),
                index=_dropdown_idx(get_jenis_options(), detail.get("jenis", "")),
                key=f"lp_edit_jenis_{record_name}",
            )
            tempat = st.text_input(
                "Tempat", value=detail.get("tempat", ""),
                key=f"lp_edit_tempat_{record_name}",
            )
            pic = st.text_input(
                "PIC", value=detail.get("pic", ""),
                key=f"lp_edit_pic_{record_name}",
            )

        with cols[1]:
            kota = st.text_input(
                "Kota", value=detail.get("kota", ""),
                key=f"lp_edit_kota_{record_name}",
            )
            lokasi = st.selectbox(
                "Lokasi", get_lokasi_options(),
                index=_dropdown_idx(get_lokasi_options(), detail.get("lokasi", "")),
                key=f"lp_edit_lokasi_{record_name}",
            )
            skema = st.selectbox(
                "Skema", get_skema_options(),
                index=_dropdown_idx(get_skema_options(), detail.get("skema", "")),
                key=f"lp_edit_skema_{record_name}",
            )
            status = st.selectbox(
                "Status", get_status_options(),
                index=_dropdown_idx(get_status_options(), detail.get("status", "")),
                key=f"lp_edit_status_{record_name}",
            )

        submitted = st.form_submit_button("💾 Simpan Perubahan", type="primary")
        if submitted:
            payload = {
                "lead_name": lead_name.strip(),
                "jenis": jenis,
                "tempat": tempat.strip(),
                "pic": pic.strip(),
                "kota": kota.strip(),
                "lokasi": lokasi,
                "skema": skema,
                "status": status,
            }
            ok, msg = update_lead_partnership(record_name, payload)
            if ok:
                st.success(f"✅ {msg}")
                rerun()
            else:
                st.error(f"❌ {msg}")


# ================= CREATE FORM =================

def _render_create_form():
    with st.form("create_lead_partnership"):
        st.markdown("**Form Lead Baru**")
        cols = st.columns(2)

        with cols[0]:
            lead_name = st.text_input(
                "Nama Lead *", placeholder="Nama calon mitra",
                key="lp_create_name",
            )
            jenis = st.selectbox(
                "Jenis", get_jenis_options(),
                key="lp_create_jenis",
            )
            tempat = st.text_input(
                "Tempat", placeholder="Nama tempat / venue",
                key="lp_create_tempat",
            )
            pic = st.text_input(
                "PIC", placeholder="Nama kontak person",
                key="lp_create_pic",
            )

        with cols[1]:
            kota = st.text_input(
                "Kota", placeholder="Kota lokasi",
                key="lp_create_kota",
            )
            lokasi = st.selectbox(
                "Lokasi", get_lokasi_options(),
                key="lp_create_lokasi",
            )
            skema = st.selectbox(
                "Skema", get_skema_options(),
                key="lp_create_skema",
            )
            status = st.selectbox(
                "Status", get_status_options(),
                index=1,  # Default: "Open"
                key="lp_create_status",
            )

        submitted = st.form_submit_button("➕ Buat Lead Baru", type="primary")
        if submitted:
            if not lead_name.strip():
                st.error("Nama Lead wajib diisi.")
            else:
                payload = {
                    "lead_name": lead_name.strip(),
                    "jenis": jenis,
                    "tempat": tempat.strip(),
                    "pic": pic.strip(),
                    "kota": kota.strip(),
                    "lokasi": lokasi,
                    "skema": skema,
                    "status": status,
                }
                ok, msg = create_lead_partnership(payload)
                if ok:
                    st.success(f"✅ {msg}")
                    rerun()
                else:
                    st.error(f"❌ {msg}")


# ================= HELPERS =================

def _dropdown_idx(options: list, current: str) -> int:
    current = str(current or "").strip()
    for i, opt in enumerate(options):
        if str(opt or "").strip() == current:
            return i
    return 0  # fallback index (empty string)
