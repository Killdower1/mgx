"""
🔐 Login page — authenticates users via auth_service.
Stores user info + role in app.storage.user for session persistence.
"""
from nicegui import ui, app
from services import auth_service


CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 32px; box-shadow: 0 16px 48px rgba(0,0,0,0.35); max-width: 420px; margin: 0 auto;"


def create_page(container: ui.column):
    """Build the Login page."""
    container.clear()

    with container:
        with ui.column().classes("w-full items-center justify-center min-h-[80vh]"):
            ui.label("📸").classes("text-5xl mb-2")
            ui.label("Difotoin Dashboard").classes("text-2xl font-bold text-white")
            ui.label("Monitoring Outlet & Kemitraan").classes("text-sm text-gray-400 mb-6")

            with ui.card().style(CARD).classes("w-full"):
                email_in = ui.input(
                    "Email", placeholder="Masukkan email anda"
                ).props("dense outlined dark").classes("w-full mb-4")
                pass_in = ui.input(
                    "Password", password_toggle_button=True,
                    placeholder="Masukkan password",
                ).props("dense outlined dark").classes("w-full mb-4").on(
                    "keydown.enter", lambda: do_login()
                )

                status_lbl = ui.label("").classes("text-sm text-center")
                error_lbl = ui.label("").classes("text-sm text-center")

                def do_login():
                    email = email_in.value.strip()
                    password = pass_in.value
                    if not email or not password:
                        error_lbl.classes("text-red-400")
                        error_lbl.set_text("Email dan password wajib diisi.")
                        return

                    user = auth_service.authenticate_user(email, password)
                    if user:
                        role = user.get("role", "viewer")
                        app.storage.user.update({
                            "logged_in": True,
                            "email": user.get("email", email),
                            "name": user.get("name", ""),
                            "role": role,
                            "_password": password,  # simpan buat Cek Status
                        })
                        status_lbl.classes("text-green-400")
                        status_lbl.set_text("✅ Login berhasil! Mengarahkan...")
                        error_lbl.set_text("")
                        if role == "guest":
                            ui.navigate.to("/pending")
                        else:
                            ui.navigate.to("/")
                    else:
                        error_lbl.classes("text-red-400")
                        error_lbl.set_text("❌ Email atau password salah.")
                        status_lbl.set_text("")

                ui.button("🔐 Masuk", on_click=do_login, color="primary"
                          ).props("rounded").classes("w-full h-11 text-base font-bold mt-2")

                ui.label("Gunakan akun ERPNext (email & password) atau akun yang terdaftar di Admin Panel.").classes(
                    "text-xs text-gray-500 text-center mt-4")
                ui.label("Kredensial dari environment variable tetap bisa dipakai.").classes(
                    "text-xs text-gray-500 text-center")


def show_logout_button():
    """Show logout button + user info in sidebar."""
    if app.storage.user.get("logged_in"):
        name = app.storage.user.get("name") or app.storage.user.get("email", "")
        role = app.storage.user.get("role", "")
        display = f"{name} ({role})" if role else name
        ui.label(f"👤 {display}").classes("text-xs text-gray-400 px-3 mb-1")
        ui.button("🚪 Logout", icon="logout", on_click=do_logout).props(
            "flat dense text-white").classes("w-full")
        ui.label("v1.0 — NiceGUI").classes("text-[10px] text-gray-600 mt-auto")


def do_logout():
    """Clear auth session."""
    app.storage.user.clear()
    ui.navigate.to("/login")


def is_authenticated() -> bool:
    """Check if user is logged in."""
    return bool(app.storage.user.get("logged_in"))


def get_current_role() -> str:
    """Get current user's role. Returns 'viewer' as fallback."""
    return app.storage.user.get("role", "viewer")


def get_current_email() -> str:
    """Get current user's email. Returns empty string if not logged in."""
    return app.storage.user.get("email", "")


def get_current_name() -> str:
    """Get current user's display name. Returns empty string if not logged in."""
    return app.storage.user.get("name", "")
