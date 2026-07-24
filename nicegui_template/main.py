"""
Difotoin Dashboard — NiceGUI Edition.
Full functional parity with Streamlit version.
"""
import sys
from pathlib import Path
from typing import Optional

from nicegui import ui
from starlette.responses import RedirectResponse

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.dashboard_adapter import get_adapter
from services import auth_service
from pages.dashboard import create_page, set_filters
from pages.lead_kemitraan import create_page as create_lk_page
from pages.lead_partnership import create_page as create_lp_page
from pages.ranking import create_page as create_ranking_page
from pages.conversion import create_page as create_conversion_page
from pages.comparison import create_page as create_comparison_page
from pages.trend import create_page as create_trend_page
from pages.ai_decision import create_page as create_ai_decision_page
from pages.upload import create_page as create_upload_page
from pages.kemitraan import create_page as create_kemitraan_page
from pages.admin import create_page as create_admin_page
from pages.crud import create_page as create_crud_page
from pages.master_data import create_page as create_master_data_page
from pages.login import create_page as create_login_page, show_logout_button, do_logout, is_authenticated, get_current_role
from pages.revenue_sharing import create_page as create_revenue_page
from pages.creative_team import create_page as create_creative_team_page
from pages.pending import create_page as create_pending_page
from pages.problem_booth import create_page as create_problem_booth_page


# ── Global state ──
_df = None
_full_df = None
_periods = []
_current_period = None
_compare_period = None
_areas = ["Semua"]
_kategoris = ["Semua"]
_tipes = ["Semua"]
_selected_area = "Semua"
_selected_kategori = "Semua"
_selected_tipe = "Semua"
_dashboard_container: Optional[ui.column] = None

# UI refs
_period_select = None
_compare_select = None
_area_select = None
_kategori_select = None
_tipe_select = None


def _refresh_data():
    """Reload data from CSV and update all sidebar options."""
    global _df, _full_df, _periods, _areas, _kategoris, _tipes
    global _current_period, _compare_period

    adapter = get_adapter()
    _df = adapter.load_data()
    _full_df = adapter.load_full_data()

    _periods = adapter.get_periods(_df)
    _current_period = _periods[-1] if _periods else None
    _compare_period = None

    _areas = ["Semua"] + adapter.get_unique_values(_df, "area")
    _kategoris = ["Semua"] + adapter.get_unique_values(_df, "kategori_tempat")
    _tipes = ["Semua"] + adapter.get_unique_values(_df, "tipe_tempat")

    # Update sidebar selectors
    if _period_select:
        _period_select.options = _periods
        _period_select.value = _current_period
    if _compare_select:
        _compare_select.options = ["-"] + [p for p in _periods if p != _current_period]
        _compare_select.value = "-"
    if _area_select:
        _area_select.options = _areas
        _area_select.value = "Semua"
    if _kategori_select:
        _kategori_select.options = _kategoris
        _kategori_select.value = "Semua"
    if _tipe_select:
        _tipe_select.options = _tipes
        _tipe_select.value = "Semua"

    _apply_filters()


def _apply_filters():
    """Apply current filters and rebuild dashboard."""
    global _current_period, _compare_period

    adapter = get_adapter()

    filtered_full = adapter.filter_data(
        _full_df, _selected_area, _selected_kategori, _selected_tipe, None
    ) if _full_df is not None and not _full_df.empty else _full_df

    filtered = adapter.filter_data(
        _df, _selected_area, _selected_kategori, _selected_tipe, _current_period
    ) if _df is not None and not _df.empty else _df

    set_filters(filtered, filtered_full, _current_period, _compare_period,
                _selected_area, _selected_kategori, _selected_tipe)


def _on_period_change(value):
    global _current_period
    _current_period = value
    if _compare_select:
        _compare_select.options = ["-"] + [p for p in _periods if p != value]
        _compare_select.value = "-"
    _on_compare_change("-")
    _apply_filters()


def _on_compare_change(value):
    global _compare_period
    _compare_period = None if value == "-" else value
    _apply_filters()


def _on_filter_change():
    global _selected_area, _selected_kategori, _selected_tipe
    _selected_area = _area_select.value if _area_select else "Semua"
    _selected_kategori = _kategori_select.value if _kategori_select else "Semua"
    _selected_tipe = _tipe_select.value if _tipe_select else "Semua"
    _apply_filters()


# ── Auth Guard ──

def _auth_guard():
    """Redirect to /login if not authenticated. Returns RedirectResponse for server-side redirect (no flash)."""
    if not is_authenticated():
        return RedirectResponse(url="/login")
    return None


def _check_page_access(route: str):
    """Check if current user has access to this route. Redirects if not."""
    if not is_authenticated():
        ui.navigate.to("/login")
        return False
    role = get_current_role()
    if not auth_service.has_permission(role, route):
        ui.navigate.to("/")
        return False
    return True


# ── Shared Navigation ──

ALL_NAV_ITEMS = [
    ("📊 Dashboard", "/"),
    ("📈 Analisis Trend", "/trend"),
    ("🤖 AI Decision", "/ai-decision"),
    ("🔄 Analisis Konversi", "/conversion"),
    ("🏆 Ranking Outlet", "/ranking"),
    ("🤝 Kemitraan", "/kemitraan"),
    ("📋 Lead Partnership", "/lead-partnership"),
    ("👥 Lead Kemitraan", "/lead-kemitraan"),
    ("📅 Perbandingan", "/comparison"),
    ("🗃️ CRUD Outlet", "/crud"),
    ("⚙️ Admin", "/admin"),
    ("[MD] Master Data", "/master-data"),
    ("💵 Revenue Sharing", "/revenue-sharing"),
    ("🎨 Creative Team", "/creative-team"),
    ("📤 Upload Data", "/upload"),
    ("🔧 Problem Booth", "/problem-booth"),
    ("📊 KPI Sistem", "/kpi-sistem"),
]

PAGE_STYLES = """<style>
    body { background-color: #11111b; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    .nicegui-content { max-width: 1500px; margin: 0 auto; padding: 0; }
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #11111b; }
    ::-webkit-scrollbar-thumb { background: #45475a; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #585b70; }
</style>"""


def _build_filters():
    """Build period/filter widgets for dashboard page — inside drawer."""
    global _area_select, _kategori_select, _tipe_select

    ui.separator().classes("my-4")
    ui.label("🔍 Filter").classes("text-xs text-gray-500 uppercase tracking-wide mb-2")

    _area_select = ui.select(
        _areas, value="Semua", label="Area",
        on_change=lambda e: _on_filter_change(),
    ).props("dense outlined dark").classes("w-full")

    _kategori_select = ui.select(
        _kategoris, value="Semua", label="Kategori",
        on_change=lambda e: _on_filter_change(),
    ).props("dense outlined dark").classes("w-full")

    _tipe_select = ui.select(
        _tipes, value="Semua", label="Tipe",
        on_change=lambda e: _on_filter_change(),
    ).props("dense outlined dark").classes("w-full")

    ui.separator().classes("my-4")
    ui.button("🔄 Refresh Data", icon="refresh", on_click=_refresh_data).props(
        "flat dense text-white").classes("w-full")


def build_nav(current_route: str, show_filters: bool = False, minimal: bool = False):
    """Responsive navigation: left drawer + top header bar with logout.

    Args:
        current_route: Active page path for highlighting.
        show_filters: Show period/filter widgets (dashboard only).
        minimal: Just logout, no menu (login page).
    """
    role = get_current_role()
    allowed = auth_service.get_allowed_routes(role)

    # Filter nav items by role permission
    visible_items = [(label, route) for label, route in ALL_NAV_ITEMS if route in allowed]

    drawer = ui.left_drawer().classes("bg-[#181825] border-r border-[#313244]").props("width=260")

    # Header bar
    with ui.header().classes("bg-[#181825] border-b border-[#313244] h-14"):
        with ui.row().classes("items-center h-full px-4 w-full gap-0"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()
                      ).props("flat color-white").classes("mr-2 lg:hidden")
            ui.label("📸 difotoin.id").classes("text-lg font-bold text-white flex-grow")
            # Show role badge
            if not minimal and role:
                ui.label(role.upper()).classes(
                    "text-[10px] bg-[#313244] text-gray-300 px-2 py-0.5 rounded mr-2 hidden sm:inline"
                )
            # Logout button
            ui.button(icon="logout", on_click=lambda: do_logout()
                      ).props("flat color-white dense").classes("ml-auto")

    # Drawer content
    with drawer:
        with ui.column().classes("p-4 gap-2 w-full"):
            if not minimal:
                ui.label("Menu").classes("text-xs text-gray-500 uppercase tracking-wide mb-2")

                for label_text, route in visible_items:
                    is_active = route == current_route
                    color = "#89b4fa" if is_active else "#a6adc8"
                    bg = "rgba(137,180,250,0.1)" if is_active else "transparent"
                    with ui.row().classes("items-center w-full px-3 py-2 rounded-lg cursor-pointer").style(
                        f"background-color: {bg};"
                    ).on("click", lambda r=route: ui.navigate.to(r)):
                        ui.label(label_text).classes("text-sm").style(f"color: {color};")

                if show_filters:
                    _build_filters()

            # Auth (always)
            ui.separator().classes("my-4")
            show_logout_button()
            ui.label("v1.0 — NiceGUI").classes("text-[10px] text-gray-600 mt-auto")

    return drawer


# ── Pages ──

@ui.page("/")
def index():
    """Main dashboard page."""
    redirect = _auth_guard()
    if redirect:
        return redirect
    global _dashboard_container

    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/", show_filters=True)

    with ui.column().classes("w-full p-6"):
        _dashboard_container = ui.column().classes("w-full")
        create_page(_dashboard_container)

    _refresh_data()


@ui.page("/lead-kemitraan")
def lead_kemitraan():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/lead-kemitraan")
    container = ui.column().classes("w-full p-6")
    create_lk_page(container)


@ui.page("/trend")
def trend():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/trend")
    create_trend_page(ui.column().classes("w-full p-6"))


@ui.page("/ai-decision")
def ai_decision():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/ai-decision")
    create_ai_decision_page(ui.column().classes("w-full p-6"))


@ui.page("/conversion")
def conversion():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/conversion")
    create_conversion_page(ui.column().classes("w-full p-6"))


@ui.page("/ranking")
def ranking():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/ranking")
    create_ranking_page(ui.column().classes("w-full p-6"))


@ui.page("/kemitraan")
def kemitraan():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/kemitraan")
    container = ui.column().classes("w-full p-6")
    create_kemitraan_page(container)


@ui.page("/lead-partnership")
def lead_partnership():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/lead-partnership")
    container = ui.column().classes("w-full p-6")
    create_lp_page(container)


@ui.page("/comparison")
def comparison():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/comparison")
    create_comparison_page(ui.column().classes("w-full p-6"))


@ui.page("/crud")
def crud():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/crud")
    container = ui.column().classes("w-full p-6")
    create_crud_page(container)


@ui.page("/admin")
def admin():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/admin")
    container = ui.column().classes("w-full p-6")
    create_admin_page(container)


@ui.page("/master-data")
def master_data():
    """Master Data page — database field reference."""
    _auth_guard()
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/master-data")
    container = ui.column().classes("w-full p-6")
    create_master_data_page(container)


@ui.page("/creative-team")
def creative_team():
    """Creative Team page — leads & outlet optimasi."""
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/creative-team")
    container = ui.column().classes("w-full p-6")
    create_creative_team_page(container)


@ui.page("/upload")
def upload():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/upload")
    container = ui.column().classes("w-full p-6")
    create_upload_page(container)


@ui.page("/revenue-sharing")
def revenue_sharing():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/revenue-sharing")
    create_revenue_page(ui.column().classes("w-full p-6"))


# ── Pending Confirmation Page ──

@ui.page("/pending")
def pending():
    """Pending confirmation page for guest users."""
    if not is_authenticated():
        return RedirectResponse(url="/login")
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/pending", minimal=True)
    container = ui.column().classes("w-full p-6")
    create_pending_page(container)


# ── Login Page ──

@ui.page("/login")
def login():
    """Login page — minimal nav, no menu."""
    # If already logged in, redirect to dashboard
    if is_authenticated():
        return RedirectResponse(url="/")
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/login", minimal=True)
    container = ui.column().classes("w-full p-6")
    create_login_page(container)


# ── Run ──

@ui.page("/problem-booth")
def problem_booth():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/problem-booth")
    container = ui.column().classes("w-full p-6")
    create_problem_booth_page(container)



@ui.page("/kpi-sistem")
def kpi_sistem_page():
    if _auth_guard():
        return
    ui.dark_mode().enable()
    ui.add_head_html(PAGE_STYLES)
    build_nav("/kpi-sistem")
    from pages import kpi_sistem
    container = ui.column().classes("w-full p-6")
    kpi_sistem.create_page(container)


if __name__ == "__main__":
    import os
    os.chdir(PROJECT_ROOT)
    ui.run(
        title="Difotoin Dashboard",
        host="0.0.0.0",
        port=8502,
        dark=True,
        reload=False,
        favicon="📊",
        show=False,
        storage_secret="difotoin-dashboard-secret-2026",
    )
