"""
⚙️ Admin Panel — user management, role management, database, thresholds, ERPNext config.
"""
import os
from datetime import datetime
from pathlib import Path

from nicegui import ui
import pandas as pd

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
SECTION_T = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"
INPUT_STYLE = "font-size: 0.85rem;"

ST_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"

# ── All known routes ──
ALL_ROUTES = [
    ("📊 Dashboard", "/"),
    ("📈 Trend", "/trend"),
    ("🤖 AI Decision", "/ai-decision"),
    ("🔄 Konversi", "/conversion"),
    ("🏆 Ranking", "/ranking"),
    ("🤝 Kemitraan", "/kemitraan"),
    ("📋 Lead Partnership", "/lead-partnership"),
    ("👥 Lead Kemitraan", "/lead-kemitraan"),
    ("📅 Perbandingan", "/comparison"),
    ("🗃️ CRUD Outlet", "/crud"),
    ("💵 Revenue Sharing", "/revenue-sharing"),
    ("⚙️ Admin", "/admin"),
    ("📤 Upload", "/upload"),
]


def _render_table(df, max_rows=50):
    if df.empty:
        ui.label("(kosong)").classes("text-gray-400 italic text-xs")
        return
    cols = [{"name": c, "label": c, "field": c, "align": "left"} for c in df.columns]
    ui.table(
        rows=df.head(max_rows).to_dict("records"),
        columns=cols,
        pagination={"rowsPerPage": 10, "rowsNumber": min(len(df), max_rows)},
    ).classes("w-full").props("dark flat dense")


def _add_to_sys_path():
    import sys
    if str(ST_DIR) not in sys.path:
        sys.path.insert(0, str(ST_DIR))


def _import_streamlit_module(name, path_suffix):
    import importlib.util
    module_path = ST_DIR / path_suffix
    spec = importlib.util.spec_from_file_location(f"streamlit_{name}", str(module_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════
#  PAGE
# ═══════════════════════════════════════════════

def create_page(container: ui.column):
    """Build the Admin panel."""
    container.clear()
    _add_to_sys_path()
    from config import Config, DATA_CSV_PATH
    from services import auth_service

    config = Config()
    _auth_mod = _import_streamlit_module("auth", "services/auth.py")
    _erp_mod = _import_streamlit_module("erpnext", "services/erpnext.py")
    auth_mod = _auth_mod
    load_erpnext_config = _erp_mod.load_erpnext_config
    save_erpnext_config = _erp_mod.save_erpnext_config
    check_connection = _erp_mod.check_connection

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with container:
        ui.label("⚙️ Admin Panel").classes("text-2xl font-bold text-white mb-4")

        # Main tabs
        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="users").classes("w-full")
        with tabs:
            ui.tab("users", label="👥 Users")
            ui.tab("roles", label="🎭 Roles")
            ui.tab("database", label="🗄️ Database")
            ui.tab("config", label="⚙️ Config")

        with panels:
            with ui.tab_panel("users"):
                _build_users_tab(container, auth_mod, auth_service)

            with ui.tab_panel("roles"):
                _build_roles_tab(container, auth_service)

            with ui.tab_panel("database"):
                _build_database_tab(container, config, DATA_CSV_PATH)

            with ui.tab_panel("sync"):
                _build_sync_tab(container)


            with ui.tab_panel("config"):
                _build_config_tab(container, config, load_erpnext_config, save_erpnext_config, check_connection, now)

        ui.separator().classes("my-4")
        with ui.row().classes("gap-4 text-xs text-gray-500"):
            ui.label(f"🕐 {now}")
            try:
                ui.label(f"Keeper: {config.format_currency(config.get_threshold('keeper_minimum'))}")
                ui.label(f"Optimasi: {config.format_currency(config.get_threshold('optimasi_minimum'))}")
            except Exception:
                pass


# ── USERS TAB ──

def _build_users_tab(container, auth_mod, auth_service):
    ui.label("Manage dashboard user accounts & roles.").classes("text-sm text-gray-400 mb-2")

    _add_to_sys_path()
    users = auth_mod.load_users()
    all_roles = [r.get("name") for r in auth_service.load_roles()]

    if users:
        udf = pd.DataFrame([{
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "role": u.get("role", "viewer"),
            "created_at": u.get("created_at", ""),
        } for u in users])
        ui.label("Existing Users:").classes("text-sm text-gray-300 mb-1")
        _render_table(udf)
    else:
        ui.label("Belum ada akun lokal. Login memakai fallback env var admin.").classes("text-sm text-gray-400 italic")

    ui.separator().classes("my-3")

    utabs = ui.tabs().classes("w-full")
    upanels = ui.tab_panels(utabs, value="add").classes("w-full")
    with utabs:
        ui.tab("add", label="Tambah")
        ui.tab("edit", label="Edit Role")
        ui.tab("reset", label="Reset Password")
        ui.tab("delete", label="Hapus")

    with upanels:
        # ── Add ──
        with ui.tab_panel("add"):
            ui.label("Override role staff yang login via ERPNext — cukup masukkan emailnya.").classes("text-sm text-gray-400 mb-3")

            with ui.card().style(CARD).classes("w-full mb-4"):
                email_in = ui.input("Email ERPNext Staff", placeholder="contoh: novi@difotoin.id").props("dense outlined dark").classes("w-full mb-3")
                role_sel = ui.select(all_roles, value=all_roles[0] if all_roles else "viewer", label="Role Dashboard"
                                    ).props("dense outlined dark").classes("w-full mb-3")
                status = ui.label("").classes("text-sm")

                def add_override():
                    email = auth_mod._normalize_email(email_in.value)
                    if not email:
                        status.classes("text-red-400"); status.set_text("Email wajib diisi."); return
                    if auth_service.create_user("Auto (ERPNext)", email, "erpnext-auto", role_sel.value) is None:
                        status.classes("text-red-400"); status.set_text("Email sudah terdaftar."); return
                    status.classes("text-green-400")
                    status.set_text(f"✅ {email} override role '{role_sel.value}' berhasil. Staff login via ERPNext.")
                    email_in.value = ""

                ui.button("🖉️ Tambahkan Override Role", on_click=add_override, color="primary").classes("w-full")

            ui.label("Tips:").classes("text-xs text-gray-500 mt-1")
            ui.label("• Staff login pake email & password ERPNext — password di atas gak dipakai.").classes("text-xs text-gray-500")
            ui.label("• Kalo staff gak didaftarin di sini, dapet role otomatis dari mapping ERPNext.").classes("text-xs text-gray-500")
            ui.label("• Mau ubah role? Buka tab Edit Role.").classes("text-xs text-gray-500")
            ui.label("• Mau hapus? Buka tab Hapus.").classes("text-xs text-gray-500")
        with ui.tab_panel("edit"):
            users_list = auth_mod.load_users()
            if users_list:
                emails = [u.get("email", "") for u in users_list]
                edit_email = ui.select(emails, value=emails[0], label="Pilih akun").props("dense outlined dark").classes("w-full mb-3")
                edit_role = ui.select(all_roles, value=all_roles[0] if all_roles else "viewer", label="Role baru"
                                     ).props("dense outlined dark").classes("w-full mb-3")
                edit_status = ui.label("").classes("text-sm")

                def do_edit_role():
                    ok = auth_service.update_user(edit_email.value, {"role": edit_role.value})
                    edit_status.classes("text-green-400" if ok else "text-red-400")
                    edit_status.set_text(f"{'✅ Role diupdate.' if ok else '❌ Gagal.'}")

                ui.button("Update Role", on_click=do_edit_role, color="primary")
            else:
                ui.label("Belum ada akun.").classes("text-gray-400 italic")

        # ── Reset Password ──
        with ui.tab_panel("reset"):
            users_list = auth_mod.load_users()
            if users_list:
                emails = [u.get("email", "") for u in users_list]
                reset_email = ui.select(emails, value=emails[0], label="Pilih akun").props("dense outlined dark").classes("w-full mb-3")
                new_pw = ui.input("Password baru", password_toggle_button=True).props("dense outlined dark").classes("w-full mb-3")
                cf_pw = ui.input("Confirm Password baru", password_toggle_button=True).props("dense outlined dark").classes("w-full mb-3")
                rst_status = ui.label("").classes("text-sm")

                def reset_pass():
                    pw = new_pw.value
                    if not pw:
                        rst_status.classes("text-red-400"); rst_status.set_text("Password wajib diisi."); return
                    if pw != cf_pw.value:
                        rst_status.classes("text-red-400"); rst_status.set_text("Password tidak sama."); return
                    ok = auth_service.update_user(reset_email.value, {"password": pw})
                    rst_status.classes("text-green-400" if ok else "text-red-400")
                    rst_status.set_text(f"{'✅ Password diupdate.' if ok else '❌ Gagal.'}")

                ui.button("Update Password", on_click=reset_pass, color="primary")
            else:
                ui.label("Belum ada akun.").classes("text-gray-400 italic")

        # ── Delete ──
        with ui.tab_panel("delete"):
            users_list = auth_mod.load_users()
            if users_list:
                emails = [u.get("email", "") for u in users_list]
                del_sel = ui.select(emails, value=[], multiple=True, label="Pilih akun yang mau dihapus"
                                    ).props("dense outlined dark use-chips").classes("w-full mb-3")
                del_status = ui.label("").classes("text-sm")

                def delete_users():
                    to_del = del_sel.value
                    if not to_del:
                        del_status.classes("text-red-400"); del_status.set_text("Pilih minimal 1 akun."); return
                    cnt = auth_service.delete_users(to_del)
                    del_status.classes("text-green-400"); del_status.set_text(f"✅ {cnt} akun berhasil dihapus.")

                ui.button("Hapus Akun", on_click=delete_users, color="negative")
            else:
                ui.label("Belum ada akun.").classes("text-gray-400 italic")

    ui.separator().classes("my-3")
    ui.label("💡 User dari env var (DIFOTOIN_ADMIN_EMAIL/PASSWORD) otomatis punya role admin.").classes("text-xs text-gray-500 italic")


# ── ROLES TAB ──

def _build_roles_tab(container, auth_service):
    ui.label("Buat, edit, dan hapus role. Setiap role menentukan halaman yang bisa diakses.").classes("text-sm text-gray-400 mb-2")

    roles = auth_service.load_roles()

    if roles:
        rdf = pd.DataFrame([{
            "role": r.get("name", ""),
            "halaman": ", ".join(r.get("permissions", [])),
            "total_page": len(r.get("permissions", [])),
        } for r in roles])
        ui.label("Existing Roles:").classes("text-sm text-gray-300 mb-1")
        _render_table(rdf)
    else:
        ui.label("Belum ada role.").classes("text-gray-400 italic")

    ui.separator().classes("my-3")

    rtabs = ui.tabs().classes("w-full")
    rpanels = ui.tab_panels(rtabs, value="create").classes("w-full")
    with rtabs:
        ui.tab("create", label="Buat Role")
        ui.tab("edit", label="Edit Role")
        ui.tab("delete", label="Hapus Role")

    with rpanels:
        # ── Create ──
        with ui.tab_panel("create"):
            rname_in = ui.input("Nama Role", placeholder="contoh: supervisor").props("dense outlined dark").classes("w-full mb-3")
            ui.label("Pilih halaman yang boleh diakses:").classes("text-xs text-gray-400 mb-2")
            route_checks = {}
            with ui.grid(columns=3).classes("w-full gap-2 mb-4"):
                for label, route in ALL_ROUTES:
                    chk = ui.checkbox(label, value=False).props("dense dark")
                    route_checks[route] = chk
            rc_status = ui.label("").classes("text-sm")

            def create_role():
                name = rname_in.value.strip()
                if not name:
                    rc_status.classes("text-red-400"); rc_status.set_text("Nama role wajib diisi."); return
                selected = [r for r, chk in route_checks.items() if chk.value]
                if not selected:
                    rc_status.classes("text-red-400"); rc_status.set_text("Pilih minimal 1 halaman."); return
                if auth_service.create_role(name, selected) is None:
                    rc_status.classes("text-red-400"); rc_status.set_text("Role sudah ada."); return
                rc_status.classes("text-green-400"); rc_status.set_text(f"✅ Role '{name}' berhasil dibuat ({len(selected)} halaman).")
                rname_in.value = ""
                for chk in route_checks.values():
                    chk.value = False

            ui.button("Buat Role", on_click=create_role, color="primary")

        # ── Edit ──
        with ui.tab_panel("edit"):
            roles_list = auth_service.load_roles()
            if roles_list:
                role_names = [r.get("name") for r in roles_list]
                edit_rname = ui.select(role_names, value=role_names[0], label="Pilih role"
                                       ).props("dense outlined dark").classes("w-full mb-3")
                ui.label("Atur ulang akses halaman:").classes("text-xs text-gray-400 mb-2")
                edit_checks = {}
                with ui.grid(columns=3).classes("w-full gap-2 mb-4"):
                    for label, route in ALL_ROUTES:
                        chk = ui.checkbox(label, value=False).props("dense dark")
                        edit_checks[route] = chk
                re_status = ui.label("").classes("text-sm")

                def _load_role_perms():
                    perms = auth_service.get_role_permissions(edit_rname.value)
                    for route, chk in edit_checks.items():
                        chk.value = route in perms

                edit_rname.on("update:model-value", _load_role_perms)
                _load_role_perms()

                def save_role():
                    selected = [r for r, chk in edit_checks.items() if chk.value]
                    ok = auth_service.update_role(edit_rname.value, permissions=selected)
                    re_status.classes("text-green-400" if ok else "text-red-400")
                    re_status.set_text(f"{'✅ Role diupdate.' if ok else '❌ Gagal.'}")

                ui.button("Simpan Perubahan", on_click=save_role, color="primary")
            else:
                ui.label("Belum ada role.").classes("text-gray-400 italic")

        # ── Delete ──
        with ui.tab_panel("delete"):
            roles_list = auth_service.load_roles()
            admin_roles = [r.get("name") for r in roles_list if r.get("name") != "admin"]
            if admin_roles:
                del_rname = ui.select(admin_roles, value=admin_roles[0], label="Pilih role yang mau dihapus"
                                      ).props("dense outlined dark").classes("w-full mb-3")
                rd_status = ui.label("").classes("text-sm")

                def delete_role():
                    ok = auth_service.delete_role(del_rname.value)
                    rd_status.classes("text-green-400" if ok else "text-red-400")
                    rd_status.set_text(f"{'✅ Role dihapus.' if ok else '❌ Tidak bisa hapus admin role.'}")

                ui.button("Hapus Role", on_click=delete_role, color="negative")
            else:
                ui.label("Tidak ada role yang bisa dihapus (admin tidak bisa dihapus).").classes("text-gray-400 italic")

    ui.separator().classes("my-3")
    ui.label("💡 Role 'admin' punya akses ke SEMUA halaman dan tidak bisa dihapus.").classes("text-xs text-gray-500 italic")
    ui.label("💡 Setelah edit role, user perlu login ulang untuk melihat perubahan.").classes("text-xs text-gray-500 italic")
    ui.button("🔄 Refresh Page", on_click=lambda: create_page(container)).props("flat dense").classes("mt-2")


# ── DATABASE TAB ──

def _build_database_tab(container, config, DATA_CSV_PATH):


    if not os.path.exists(DATA_CSV_PATH):
        ui.label("File data dashboard belum ada.").classes("text-gray-400 italic")
        return
    try:
        db = pd.read_csv(DATA_CSV_PATH)
    except Exception as ex:
        ui.label(f"Gagal membaca data: {ex}").classes("text-red-400")
        return
    if db.empty or "periode" not in db.columns:
        ui.label("Data kosong.").classes("text-gray-400 italic")
        return
    db["periode"] = db["periode"].astype(str)
    if "total_revenue" in db.columns:
        db["total_revenue"] = pd.to_numeric(db["total_revenue"], errors="coerce").fillna(0.0)

    def _fmt_amt(v):
        return config.format_currency(v)

    outlet_col = "outlet_name" if "outlet_name" in db.columns else "periode"
    period_summary = (
        db.groupby("periode", as_index=False)
        .agg(rows=("periode", "size"),
             outlet_count=(outlet_col, "nunique"),
             total_revenue=("total_revenue", "sum"))
    )
    ps = period_summary.copy()
    ps["total_revenue"] = ps["total_revenue"].apply(_fmt_amt)
    ps_display = ps.rename(columns={
        "periode": "Periode", "rows": "Rows",
        "outlet_count": "Outlet", "total_revenue": "Omzet",
    })
    _render_table(ps_display)

    periods = period_summary["periode"].astype(str).tolist()
    sel_periods = ui.select(periods, value=[], multiple=True, label="Pilih periode yang mau dihapus"
                            ).props("dense outlined dark use-chips").classes("w-full mt-4 mb-3")
    db_status = ui.label("").classes("text-sm")

    def delete_periods():
        selected = sel_periods.value
        if not selected:
            db_status.classes("text-red-400"); db_status.set_text("Pilih minimal 1 periode."); return
        sel_df = db[db["periode"].isin(selected)]
        sel_total = float(sel_df["total_revenue"].sum())
        backup_path = DATA_CSV_PATH.with_name(
            f"difotoin_dashboard_data.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        try:
            db.to_csv(backup_path, index=False)
            remaining = db[~db["periode"].isin(selected)].copy()
            remaining.to_csv(DATA_CSV_PATH, index=False)
            db_status.classes("text-green-400")
            db_status.set_text(f"✅ Berhasil hapus {', '.join(selected)}. Omzet terhapus: {_fmt_amt(sel_total)}. Backup: {backup_path.name}")
        except Exception as ex:
            db_status.classes("text-red-400")
            db_status.set_text(f"❌ Gagal: {ex}")

    ui.button("Hapus Periode Terpilih", on_click=delete_periods, color="negative")



# ── SYNC TAB ──

def _build_sync_tab(container):
    """Sync from difotoin.id API."""
    import sys
    from pathlib import Path
    
    ST_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
    if str(ST_DIR) not in sys.path:
        sys.path.insert(0, str(ST_DIR))
    
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from services import difotoin_api_adapter as api_adapter
    from config import Config
    Config()
    
    ui.label("Sinkronisasi data dari difotoin.id API.").classes("text-sm text-gray-400 mb-4")
    
    status_area = ui.column().classes("w-full mb-4")
    
    last = api_adapter.get_last_sync()
    if last:
        ts = last.get("timestamp", "?")
        msg = last.get("message", "")
        ok = last.get("success", False)
        icon = "✅" if ok else "❌"
        with ui.card().style("background-color: #1e1e2e; border-radius: 12px; padding: 16px;").classes("w-full mb-4"):
            ui.label(icon + " Sync Terakhir: " + str(ts)[:19]).classes("text-sm text-gray-300")
            ui.label(msg).classes("text-sm " + ("text-green-400" if ok else "text-red-400"))
    
    def _do_sync():
        btn.props("loading disable")
        try:
            ok, msg = api_adapter.run_sync(months_back=12)
            status_area.clear()
            with status_area:
                ui.label(msg).classes("text-green-400 text-sm" if ok else "text-red-400 text-sm")
        except Exception as e:
            status_area.clear()
            with status_area:
                ui.label("Error: " + str(e)).classes("text-red-400 text-sm")
        finally:
            btn.props(remove="loading")
    
    with ui.row().classes("gap-4 items-center"):
        btn = ui.button("Sync Sekarang", on_click=_do_sync, color="primary").props("icon=cloud_download")
        ui.label("Mengambil data 12 bulan terakhir dari difotoin.id").classes("text-xs text-gray-500")
    
    ui.separator().classes("my-4")
    ui.label("Data transaksi akan di-aggregate per outlet + bulan, lalu disimpan ke CSV.").classes("text-xs text-gray-500")
    ui.label("Transaksi mentah di-cache untuk halaman Revenue Sharing.").classes("text-xs text-gray-500")


# ── CONFIG TAB ──

# ── CONFIG TAB ──

def _build_config_tab(container, config, load_erpnext_config, save_erpnext_config, check_connection, now):
    with ui.expansion("🎯 Threshold", icon="tune", value=True).classes("w-full mb-4"):
        keeper_now = config.get_threshold("keeper_minimum")
        optim_now = config.get_threshold("optimasi_minimum")
        with ui.row().classes("w-full gap-4"):
            keeper_inp = ui.input("Keeper Minimum (IDR)",
                                  value=str(int(keeper_now)) if isinstance(keeper_now, (int, float)) else "0"
                                  ).props("dense outlined dark type=number").classes("flex-1")
            optim_inp = ui.input("Optimasi Minimum (IDR)",
                                 value=str(int(optim_now)) if isinstance(optim_now, (int, float)) else "0"
                                 ).props("dense outlined dark type=number").classes("flex-1")
        thr_status = ui.label("").classes("text-sm mt-2")

        def save_thresholds():
            try:
                config.set_threshold("keeper_minimum", int(float(keeper_inp.value)))
                config.set_threshold("optimasi_minimum", int(float(optim_inp.value)))
                config.save_config()
                thr_status.classes("text-green-400"); thr_status.set_text("✅ Thresholds updated & config saved.")
            except Exception as ex:
                thr_status.classes("text-red-400"); thr_status.set_text(f"❌ Error: {ex}")

        def clear_cache():
            try:
                _add_to_sys_path()
                from app import cache_clear, load_app_data
                cache_clear(load_app_data)
                thr_status.classes("text-green-400"); thr_status.set_text("✅ Cache cleared.")
            except Exception as ex:
                thr_status.classes("text-orange-400"); thr_status.set_text(f"ℹ️ Cache clear: {ex}")

        with ui.row().classes("gap-4 mt-2"):
            ui.button("💾 Save Thresholds", on_click=save_thresholds, color="primary")
            ui.button("🧹 Clear Cache", on_click=clear_cache).props("flat")

    with ui.expansion("🔗 ERPNext Config", icon="link", value=False).classes("w-full mb-4"):
        erp_cfg = load_erpnext_config()
        erp_url = ui.input("URL ERPNext", value=erp_cfg.get("url", ""),
                           placeholder="https://erp.midory.id").props("dense outlined dark").classes("w-full mb-3")
        erp_key = ui.input("API Key", value=erp_cfg.get("api_key", ""),
                           password_toggle_button=True).props("dense outlined dark").classes("w-full mb-3")
        erp_secret = ui.input("API Secret", value=erp_cfg.get("api_secret", ""),
                              password_toggle_button=True).props("dense outlined dark").classes("w-full mb-3")
        erp_status = ui.label("").classes("text-sm")

        def test_erp():
            save_erpnext_config({"url": erp_url.value.strip(), "api_key": erp_key.value.strip(), "api_secret": erp_secret.value.strip()})
            ok, msg = check_connection(doctype="Lead")
            erp_status.classes("text-green-400" if ok else "text-red-400")
            erp_status.set_text(f"{'✅' if ok else '❌'} {msg}")

        def save_erp():
            save_erpnext_config({"url": erp_url.value.strip(), "api_key": erp_key.value.strip(), "api_secret": erp_secret.value.strip()})
            erp_status.classes("text-green-400"); erp_status.set_text("✅ Konfigurasi ERPNext tersimpan!")

        with ui.row().classes("gap-4"):
            ui.button("🧪 Test Koneksi", on_click=test_erp).props("flat")
            ui.button("💾 Simpan", on_click=save_erp, color="primary")

    with ui.expansion("ℹ️ System Info", icon="info", value=False).classes("w-full mb-4"):
        ui.label(f"Last Updated: {now}").classes("text-sm text-gray-300")
        try:
            ui.json(config.config)
        except Exception:
            ui.label("Tidak bisa menampilkan JSON config.").classes("text-gray-400 italic")
