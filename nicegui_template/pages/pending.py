"""
⏳ Pending Confirmation — guest users waiting for CEO approval.
"""
from nicegui import ui, app
from services import auth_service

CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 32px; box-shadow: 0 16px 48px rgba(0,0,0,0.35); max-width: 480px; margin: 0 auto;"


def create_page(container: ui.column):
    """Build the pending confirmation page."""
    container.clear()

    with container:
        with ui.column().classes("w-full items-center justify-center min-h-[80vh]"):
            ui.label("⏳").classes("text-6xl mb-4")
            ui.label("Selamat telah berhasil login!").classes("text-xl font-bold text-white mb-2")
            ui.label(
                "Tunggu pak CEO konfirmasi kehadiran anda."
            ).classes("text-base text-gray-300 text-center mb-6 px-4")

            with ui.card().style(CARD).classes("w-full"):
                email = app.storage.user.get("email", "")
                ui.label(f"👤 {email}").classes("text-sm text-gray-400 mb-4")

                status_lbl = ui.label("").classes("text-sm text-center mb-2")

                def cek_status():
                    """Re-authenticate with stored credentials to check role update."""
                    saved_email = app.storage.user.get("email")
                    saved_password = app.storage.user.get("_password")
                    if not saved_email or not saved_password:
                        status_lbl.classes("text-red-400")
                        status_lbl.set_text("Sesi habis, silakan login ulang.")
                        return

                    user = auth_service.authenticate_user(saved_email, saved_password)
                    if user:
                        new_role = user.get("role", "guest")
                        if new_role != "guest":
                            # Role udah diubah! Update session & redirect
                            app.storage.user.update({
                                "logged_in": True,
                                "email": user.get("email", saved_email),
                                "name": user.get("name", ""),
                                "role": new_role,
                                "_password": saved_password,
                            })
                            status_lbl.classes("text-green-400")
                            status_lbl.set_text(f"✅ Role berubah jadi {new_role}! Mengarahkan...")
                            ui.navigate.to("/")
                            return
                        else:
                            status_lbl.classes("text-yellow-400")
                            status_lbl.set_text("⏳ Role masih guest. Silakan tunggu konfirmasi Pak CEO.")
                    else:
                        status_lbl.classes("text-red-400")
                        status_lbl.set_text("Gagal verifikasi ulang. Silakan login ulang.")

                with ui.row().classes("w-full gap-3"):
                    ui.button(
                        "🔄 Cek Status Sekarang",
                        on_click=cek_status,
                        color="primary",
                    ).props("rounded").classes("flex-1 h-11 text-base font-bold")

                    ui.button(
                        "🚪 Logout",
                        on_click=lambda: (
                            app.storage.user.clear(),
                            ui.navigate.to("/login"),
                        ),
                    ).props("rounded flat").classes("h-11")

            ui.label(
                "Setelah Pak CEO mengubah role anda, klik \"Cek Status Sekarang\" "
                "untuk mengakses dashboard."
            ).classes("text-xs text-gray-500 text-center mt-6 px-4")
            ui.label(
                "Atau logout & login kembali setelah dikonfirmasi."
            ).classes("text-xs text-gray-500 text-center")
