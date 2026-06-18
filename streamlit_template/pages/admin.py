import os
import re
import json
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from config import Config, DATA_CSV_PATH
from services.auth import _normalize_email, _hash_password, load_users, save_users

SHARING_MASTER_COLUMNS = [
    "outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master",
    "investor_name", "partner_share", "broker_share", "sharing_bagi_hasil",
    "monthly_rent", "minimum_payment", "harga_beli_kemitraan", "created_at",
]


def show_user_access_panel():
    from app import df_show, rerun
    st.subheader("User Access")
    users = load_users()

    if users:
        display = pd.DataFrame([{
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "created_at": u.get("created_at", ""),
        } for u in users])
        df_show(display, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada akun lokal. Login masih bisa memakai akun fallback dari launcher/env var.")

    tab_add, tab_reset, tab_delete = st.tabs(["Add Account", "Reset Password", "Delete Account"])

    with tab_add:
        with st.form("user_add_form"):
            name = st.text_input("Nama")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Create Account")
            if submitted:
                email_norm = _normalize_email(email)
                if not name.strip() or not email_norm or not password:
                    st.error("Nama, email, dan password wajib diisi.")
                elif password != confirm:
                    st.error("Password dan confirmation tidak sama.")
                elif any(_normalize_email(u.get("email")) == email_norm for u in users):
                    st.error("Email sudah terdaftar.")
                else:
                    salt, password_hash = _hash_password(password)
                    users.append({
                        "name": name.strip(),
                        "email": email_norm,
                        "salt": salt,
                        "password_hash": password_hash,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    save_users(users)
                    st.success("Akun berhasil dibuat.")
                    rerun()

    with tab_reset:
        if users:
            email_to_reset = st.selectbox("Pilih akun", [u.get("email", "") for u in users], key="user_reset_email")
            with st.form("user_reset_form"):
                new_password = st.text_input("Password baru", type="password")
                confirm_password = st.text_input("Confirm Password baru", type="password")
                if st.form_submit_button("Update Password"):
                    if not new_password:
                        st.error("Password baru wajib diisi.")
                    elif new_password != confirm_password:
                        st.error("Password dan confirmation tidak sama.")
                    else:
                        salt, password_hash = _hash_password(new_password)
                        for user in users:
                            if user.get("email") == email_to_reset:
                                user["salt"] = salt
                                user["password_hash"] = password_hash
                                user["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_users(users)
                        st.success("Password berhasil diupdate.")
                        rerun()
        else:
            st.info("Belum ada akun untuk di-reset.")

    with tab_delete:
        if users:
            emails = [u.get("email", "") for u in users]
            emails_to_delete = st.multiselect("Pilih akun yang mau dihapus", emails)
            if emails_to_delete:
                st.warning(f"{len(emails_to_delete)} akun akan dihapus.")
                if st.button("Confirm Delete Account", key="user_delete_btn"):
                    users = [u for u in users if u.get("email", "") not in emails_to_delete]
                    save_users(users)
                    st.success("Akun berhasil dihapus.")
                    rerun()
        else:
            st.info("Belum ada akun untuk dihapus.")



def show_monthly_database_panel(config: Config):
    from app import df_show, cache_clear, load_app_data, rerun
    st.subheader("Database Bulanan")
    if not os.path.exists(DATA_CSV_PATH):
        st.info("File data dashboard belum ada.")
        return

    try:
        db = pd.read_csv(DATA_CSV_PATH)
    except Exception as e:
        st.error(f"Gagal membaca data dashboard: {e}")
        return

    if db.empty or "periode" not in db.columns:
        st.info("Data dashboard kosong atau tidak punya kolom periode.")
        return

    db["periode"] = db["periode"].astype(str)
    if "total_revenue" in db.columns:
        db["total_revenue"] = pd.to_numeric(db["total_revenue"], errors="coerce").fillna(0.0)
    else:
        db["total_revenue"] = 0.0

    period_summary = (
        db.groupby("periode", as_index=False)
        .agg(
            rows=("periode", "size"),
            outlet_count=("outlet_name", "nunique") if "outlet_name" in db.columns else ("periode", "size"),
            total_revenue=("total_revenue", "sum"),
        )
    )
    period_summary["sort_key"] = pd.to_datetime(period_summary["periode"], format="%Y-%m", errors="coerce")
    period_summary = period_summary.sort_values(["sort_key", "periode"], na_position="first").drop(columns=["sort_key"])

    display_summary = period_summary.copy()
    display_summary["total_revenue"] = display_summary["total_revenue"].apply(config.format_currency)
    df_show(
        display_summary.rename(columns={
            "periode": "Periode",
            "rows": "Rows",
            "outlet_count": "Outlet",
            "total_revenue": "Omzet",
        }),
        use_container_width=True,
        hide_index=True,
    )

    periods = period_summary["periode"].astype(str).tolist()
    selected_periods = st.multiselect("Pilih periode yang mau dihapus", periods, key="delete_db_periods")

    if not selected_periods:
        st.caption("Pilih satu atau beberapa periode untuk preview dan delete.")
        return

    selected_df = db[db["periode"].isin(selected_periods)].copy()
    selected_total = float(selected_df["total_revenue"].sum())
    st.warning(
        "Periode terpilih: {} | Rows: {:,} | Omzet: {}".format(
            ", ".join(selected_periods),
            len(selected_df),
            config.format_currency(selected_total),
        )
    )

    preview_cols = [c for c in ["periode", "outlet_name", "area", "kategori_tempat", "tipe_tempat", "total_revenue"] if c in selected_df.columns]
    if preview_cols:
        preview = selected_df[preview_cols].head(50).copy()
        if "total_revenue" in preview.columns:
            preview["total_revenue"] = preview["total_revenue"].apply(config.format_currency)
        df_show(preview, use_container_width=True, hide_index=True)

    confirm_text = st.text_input("Ketik DELETE untuk konfirmasi hapus", key="delete_db_confirm")
    if st.button("Delete Selected Periods", key="delete_db_period_btn", type="primary"):
        if confirm_text != "DELETE":
            st.error("Konfirmasi belum benar. Ketik DELETE untuk menghapus.")
            return

        backup_path = DATA_CSV_PATH.with_name(
            "difotoin_dashboard_data.backup_before_delete_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
        )
        try:
            db.to_csv(backup_path, index=False)
            remaining = db[~db["periode"].isin(selected_periods)].copy()
            remaining.to_csv(DATA_CSV_PATH, index=False)
            try: cache_clear(load_app_data)
            except Exception: pass
            st.success(
                "Berhasil hapus periode {}. Backup tersimpan di {}.".format(
                    ", ".join(selected_periods),
                    backup_path.name,
                )
            )
            rerun()
        except Exception as e:
            st.error(f"Gagal menghapus periode: {e}")



def show_admin_panel(config):
    from app import df_show, cache_clear, load_app_data, rerun
    import os
    from datetime import datetime as _dt
    st.title("⚙️ Admin Panel")

    show_user_access_panel()
    st.markdown("---")

    show_monthly_database_panel(config)
    st.markdown("---")

    st.subheader("🎯 Threshold Configuration")
    keeper_now = config.get_threshold("keeper_minimum")
    optim_now  = config.get_threshold("optimasi_minimum")

    c1, c2 = st.columns(2)
    with c1:
        new_keeper = st.number_input("Keeper Minimum (IDR)", min_value=0, value=int(keeper_now) if isinstance(keeper_now, (int, float)) else 0, step=1_000_000, format="%d")
    with c2:
        new_optim = st.number_input("Optimasi Minimum (IDR)", min_value=0, value=int(optim_now) if isinstance(optim_now, (int, float)) else 0, step=1_000_000, format="%d")

    colA, colB = st.columns([1,1])
    with colA:
        if st.button("💾 Save Thresholds", key="btn_save_threshold"):
            try:
                config.set_threshold("keeper_minimum", int(new_keeper))
                config.set_threshold("optimasi_minimum", int(new_optim))
                ok = config.save_config()
                if ok:
                    try: cache_clear(load_app_data)
                    except Exception: pass
                    st.success("✅ Thresholds updated & config saved.")
                    rerun()
                else:
                    st.error("❌ Failed to save thresholds.")
            except Exception as e:
                st.error(f"❌ Error saving thresholds: {e}")

    with colB:
        if st.button("🧹 Clear Cached Data", key="btn_clear_cache"):
            try:
                cache_clear(load_app_data)
                st.success("✅ Cache cleared.")
            except Exception as e:
                st.warning(f"ℹ️ Cache clear note: {e}")

    st.subheader("📋 Current Configuration")
    try: st.json(config.config)
    except Exception: st.info("ℹ️ Tidak bisa menampilkan JSON config.")

    st.subheader("ℹ️ System Information")
    st.write(f"**Last Updated:** {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        st.write(f"**Keeper Threshold:** {config.format_currency(config.get_threshold('keeper_minimum'))}")
        st.write(f"**Optimasi Threshold:** {config.format_currency(config.get_threshold('optimasi_minimum'))}")
    except Exception:
        pass

    data_path = DATA_CSV_PATH
    with st.expander("📄 Data File Info (opsional)"):
        if os.path.exists(data_path):
            try:
                df_info = pd.read_csv(data_path, nrows=5)
                st.write(f"Path: `{data_path}`")
                try:
                    rows = sum(1 for _ in open(data_path, 'r', encoding='utf-8', errors='ignore')) - 1
                    st.write(f"Rows (approx): ~{rows:,}")
                except Exception:
                    pass
                df_show(df_info, use_container_width=True)
            except Exception as e:
                st.warning(f"Tidak bisa membaca CSV: {e}")
        else:
            st.info("File data belum ada.")

    if st.button("🔄 Reload Page", key="btn_reload_page"):
        rerun()

# ================= UPLOAD =================
