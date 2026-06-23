"""
🗃️ CRUD Data Outlet & Master Data — NiceGUI edition.
Port of Streamlit's crud_outlet.py with full functional parity.
"""
import hashlib
import json
import importlib.util
import sys
from pathlib import Path
from typing import Optional, List, Dict

from nicegui import ui
import pandas as pd
import numpy as np

# ── Styling ──
CARD = "background-color: #1e1e2e; border-radius: 12px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
SECTION_T = "font-size: 0.95rem; font-weight: 600; color: #cdd6f4; margin-bottom: 8px;"

# ── Paths ──
ST_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
MAPPING_PATH = ST_DIR / "data" / "difotoin_outlet_mapping.csv"


def _add_to_sys_path():
    """Ensure streamlit_template is importable."""
    if str(ST_DIR) not in sys.path:
        sys.path.insert(0, str(ST_DIR))


# ── Inline copies from streamlit_template/app.py (pure Python, no streamlit deps) ──
# These avoid the namespace collision when trying to import app.py directly.

# Add streamlit_template to sys.path for config import
if str(ST_DIR) not in sys.path:
    sys.path.insert(0, str(ST_DIR))
from config import MASTER_DATA_PATH

INDONESIA_AREAS = ["Jakarta Pusat","Jakarta Utara","Jakarta Barat","Jakarta Selatan","Jakarta Timur","Jakarta","Surabaya","Bandung","Medan","Bekasi","Tangerang","Depok","Semarang","Palembang","Makassar","Batam","Bogor","Pekanbaru","Bandar Lampung","Malang","Padang","Denpasar","Samarinda","Tasikmalaya","Balikpapan","Pontianak","Jambi","Cimahi","Sukabumi","Bengkulu","Mataram","Yogyakarta","Solo","Purwokerto","Magelang","Tegal","Pekalongan","Kudus","Jepara","Demak","Kendal","Temanggung","Wonosobo","Purworejo","Kebumen","Banjarnegara","Cilacap","Banyumas","Brebes","Pemalang","Batang","Blora","Rembang","Pati","Grobogan","Sragen","Karanganyar","Wonogiri","Sukoharjo","Klaten","Boyolali","Sleman","Bantul","Kulon Progo","Gunungkidul","Madiun","Ngawi","Bojonegoro","Tuban","Lamongan","Gresik","Bangkalan","Sampang","Pamekasan","Sumenep","Kediri","Blitar","Tulungagung","Trenggalek","Nganjuk","Jombang","Mojokerto","Pasuruan","Probolinggo","Situbondo","Bondowoso","Banyuwangi","Jember","Lumajang","Malang","Batu","Bali","Denpasar","Badung","Gianyar","Klungkung","Bangli","Karangasem","Buleleng","Jembrana","Tabanan"]
KATEGORI_TEMPAT = ["Mall","Wisata","Restoran","Hotel","Komunitas","Sekolah","Universitas","Rumah Sakit","Perkantoran","Apartemen","Cafe","Gym","Salon","Spa","Bioskop","Taman","Museum","Galeri","Event Space","Co-working Space","Transportasi","Lainnya"]
SUB_KATEGORI_TEMPAT = ["Food Court","Shopping Center","Department Store","Supermarket","Boutique","Electronics Store","Bookstore","Pantai","Gunung","Danau","Taman Nasional","Taman/Wisata Alam","Candi","Kebun Binatang","Waterpark","Fine Dining","Fast Food","Street Food","Bakery","Coffee Shop","Bar","Lounge","Budget Hotel","Luxury Hotel","Resort","Resort/Hotel","Homestay","Guest House","Hostel","Community Space","Creative Space","Airport","Tidak Terkategorisasi","Lainnya"]
TIPE_TEMPAT = ["Indoor", "Outdoor", "Semi-Outdoor"]

DEFAULT_MASTER_DATA = {"areas": INDONESIA_AREAS.copy(), "kategori_tempat": KATEGORI_TEMPAT.copy(), "sub_kategori_tempat": SUB_KATEGORI_TEMPAT.copy(), "tipe_tempat": TIPE_TEMPAT.copy()}


def _load_master_data() -> dict:
    """Load master data lists from file."""
    try:
        with open(MASTER_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {k: v.copy() for k, v in DEFAULT_MASTER_DATA.items()}
    except (FileNotFoundError, Exception):
        return {k: v.copy() for k, v in DEFAULT_MASTER_DATA.items()}
    result = {}
    for key, defaults in DEFAULT_MASTER_DATA.items():
        values = data.get(key)
        result[key] = _clean_master_values(values if isinstance(values, list) else defaults)
        if not result[key]:
            result[key] = defaults.copy()
    return result


def _save_master_data(data: dict) -> None:
    """Save master data lists to file."""
    MASTER_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "areas": _clean_master_values(data.get("areas", [])),
        "kategori_tempat": _clean_master_values(data.get("kategori_tempat", [])),
        "sub_kategori_tempat": _clean_master_values(data.get("sub_kategori_tempat", [])),
        "tipe_tempat": _clean_master_values(data.get("tipe_tempat", [])),
    }
    with open(MASTER_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _apply_master_data():
    """Reload master data and update global constants."""
    data = _load_master_data()
    global INDONESIA_AREAS, KATEGORI_TEMPAT, SUB_KATEGORI_TEMPAT, TIPE_TEMPAT
    INDONESIA_AREAS = data["areas"]
    KATEGORI_TEMPAT = data["kategori_tempat"]
    SUB_KATEGORI_TEMPAT = data["sub_kategori_tempat"]
    TIPE_TEMPAT = data["tipe_tempat"]


def _cache_clear():
    """Clear cached app data."""
    try:
        _add_to_sys_path()
        from app import cache_clear, load_app_data
        cache_clear(load_app_data)
    except Exception:
        pass


def _import_auth_module():
    """Import services.auth from streamlit_template via importlib."""
    _add_to_sys_path()
    spec = importlib.util.spec_from_file_location("streamlit_auth", str(ST_DIR / "services" / "auth.py"))
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.load_deleted_outlets, mod.save_deleted_outlets
    raise ImportError("Cannot load streamlit auth module")


def _import_ui_helpers():
    """Import ui_helpers for _clean_master_values."""
    _add_to_sys_path()
    spec = importlib.util.spec_from_file_location("ui_helpers", str(ST_DIR / "components" / "ui_helpers.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _import_config():
    """Import config module to get OUTLET_MAPPING_PATH."""
    _add_to_sys_path()
    from config import OUTLET_MAPPING_PATH, Config
    return OUTLET_MAPPING_PATH, Config


def _render_table(df, max_rows=100):
    """Render a pandas DataFrame as a NiceGUI table."""
    if df.empty:
        ui.label("(kosong)").classes("text-gray-400 italic text-xs")
        return
    cols = [{"name": c, "label": c, "field": c, "align": "left"} for c in df.columns]
    ui.table(
        rows=df.head(max_rows).to_dict("records"),
        columns=cols,
        pagination={"rowsPerPage": 15, "rowsNumber": min(len(df), max_rows)},
    ).classes("w-full").props("dark flat dense")


def _safe_unique_str(df: pd.DataFrame, col: str) -> List[str]:
    """Get sorted unique string values from a column."""
    if col not in df.columns:
        return []
    return sorted(df[col].dropna().astype(str).unique().tolist())


def _clean_master_values(values: List[str]) -> List[str]:
    """Deduplicate and strip master data values."""
    cleaned = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text.lower() in seen:
            continue
        cleaned.append(text)
        seen.add(text.lower())
    return cleaned


# ── AI Suggest Logic ──

def _suggest_outlet_metadata(outlet_name: str, current_row: Optional[dict] = None) -> dict:
    """Guess area, kategori, sub_kategori, tipe from outlet name."""
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

    # Ensure values are valid using module-level constants
    _add_to_sys_path()
    try:
        from pages.crud import KATEGORI_TEMPAT as KT_LIST, SUB_KATEGORI_TEMPAT as SKT_LIST
        if kategori not in KT_LIST:
            kategori = "Lainnya"
        if sub not in SKT_LIST:
            sub = "Lainnya"
    except Exception:
        pass
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
        "reason": f"{area_reason}; {cat_reason}",
        "needs_update": needs_update,
    }


# ═══════════════════════════════════════════════
#  MASTER DATA RENDERER
# ═══════════════════════════════════════════════

def _render_master_data_editor(title: str, key: str, values: List[str], container: ui.column,
                                load_master_data_fn, save_master_data_fn, apply_master_data_fn):
    """Render an editable master data list (areas, kategori, sub-kategori)."""
    _add_to_sys_path()
    with container:
        ui.label(title).style(SECTION_T)

        # Current values display
        if values:
            df_vals = pd.DataFrame({"value": values})
            _render_table(df_vals, max_rows=200)
        else:
            ui.label("(kosong)").classes("text-gray-400 italic text-xs")

        # Add new value
        ui.separator().classes("my-2")
        new_input = ui.input(f"Tambah {title} baru", placeholder=f"Nama {title}...").props("dense outlined dark").classes("w-full")
        add_status = ui.label("").classes("text-sm mt-1")

        def add_value():
            new_val = new_input.value.strip()
            if not new_val:
                add_status.classes("text-red-400")
                add_status.set_text("❌ Nama tidak boleh kosong!")
                return
            master = load_master_data_fn()
            current_list = master.get(key, [])
            if new_val in current_list:
                add_status.classes("text-red-400")
                add_status.set_text(f"❌ '{new_val}' sudah ada!")
                return
            current_list.append(new_val)
            master[key] = _clean_master_values(current_list)
            save_master_data_fn(master)
            apply_master_data_fn()
            new_input.value = ""
            add_status.classes("text-green-400")
            add_status.set_text(f"✅ '{new_val}' berhasil ditambahkan!")

        ui.button(f"Tambah {title}", on_click=add_value, color="primary").props("dense").classes("mt-2")


# ═══════════════════════════════════════════════
#  PAGE
# ═══════════════════════════════════════════════

def create_page(container: ui.column):
    """Build the CRUD Outlet & Master Data page."""
    container.clear()
    _add_to_sys_path()

    # Lazy imports
    from services.dashboard_adapter import get_adapter
    load_deleted_outlets_fn, save_deleted_outlets_fn = _import_auth_module()
    ui_helpers_mod = _import_ui_helpers()
    OUTLET_MAPPING_PATH_ST, ConfigCls = _import_config()

    adapter = get_adapter()
    config = adapter.config
    processor = adapter.processor

    # Master data constants — defined at module level
    def load_master_data_fn():
        return _load_master_data()

    def save_master_data_fn(data):
        _save_master_data(data)

    def apply_master_data_fn():
        _apply_master_data()

    # ── Load outlet mapping ──
    outlet_mapping = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()

    # If no mapping, build from data
    adapter2 = get_adapter()
    df = adapter2.load_data()
    if outlet_mapping.empty and df is not None and not df.empty:
        base = df.copy(deep=True)
        outlets = base["outlet_name"].dropna().astype(str).unique()
        outlet_mapping = pd.DataFrame({
            "outlet_name": outlets,
            "area": base.groupby("outlet_name")["area"].first().reindex(outlets).fillna("").values if "area" in base.columns else "",
            "kategori_tempat": base.groupby("outlet_name")["kategori_tempat"].first().reindex(outlets).fillna("Tidak Terkategorisasi").values if "kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            "sub_kategori_tempat": base.groupby("outlet_name")["sub_kategori_tempat"].first().reindex(outlets).fillna("Tidak Terkategorisasi").values if "sub_kategori_tempat" in base.columns else "Tidak Terkategorisasi",
            "tipe_tempat": base.groupby("outlet_name")["tipe_tempat"].first().reindex(outlets).fillna("Indoor").values if "tipe_tempat" in base.columns else "Indoor",
        })

    required_cols = ["outlet_name", "area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]
    for col in required_cols:
        if col not in outlet_mapping.columns:
            outlet_mapping[col] = ""
    outlet_mapping = outlet_mapping[[c for c in required_cols if c in outlet_mapping.columns]].copy()
    for col in outlet_mapping.columns:
        outlet_mapping[col] = outlet_mapping[col].fillna("").astype(str)
    outlet_mapping["outlet_name"] = outlet_mapping["outlet_name"].str.strip()
    outlet_mapping = outlet_mapping[outlet_mapping["outlet_name"] != ""].drop_duplicates("outlet_name", keep="last")

    # ── Auto-add missing outlets from transaction data ──
    deleted_outlets = set(load_deleted_outlets_fn())
    if df is not None and not df.empty and "outlet_name" in df.columns:
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
                outlet_mapping = outlet_mapping[[c for c in required_cols if c in outlet_mapping.columns]].drop_duplicates("outlet_name", keep="last")
                outlet_mapping = outlet_mapping.sort_values("outlet_name").reset_index(drop=True)
                outlet_mapping.to_csv(OUTLET_MAPPING_PATH_ST, index=False)
                ui.notification(f"✅ {len(new_rows)} outlet dari database transaksi otomatis ditambahkan.", type="info", timeout=5000)

    with container:
        ui.label("🗃️ CRUD Data Outlet & Master Data").classes("text-2xl font-bold text-white mb-4")

        # ── Main Tabs ──
        tabs = ui.tabs().classes("w-full")
        panels = ui.tab_panels(tabs, value="outlet").classes("w-full")

        with tabs:
            ui.tab("outlet", label="🏪 Outlet Management")
            ui.tab("master", label="📋 Master Data")
            ui.tab("deleted", label="🗑️ Deleted Outlets")

        # ════════════════════════════════════════
        # TAB 1: OUTLET MANAGEMENT
        # ════════════════════════════════════════
        with panels:
            with ui.tab_panel("outlet"):
                # Sub-tabs for CRUD operations
                subtabs = ui.tabs().classes("w-full")
                subpanels = ui.tab_panels(subtabs, value="edit").classes("w-full")

                with subtabs:
                    ui.tab("edit", label="✏️ Edit")
                    ui.tab("add", label="➕ Add")
                    ui.tab("delete", label="🗑️ Delete")
                    ui.tab("ai", label="🤖 AI Suggest")

                with subpanels:
                    # ── EDIT TAB ──
                    with ui.tab_panel("edit"):
                        with ui.card().style(CARD).classes("w-full"):
                            ui.label("✏️ Edit Outlet Data").style(SECTION_T)

                            # Metrics row
                            with ui.row().classes("w-full gap-4 mb-4"):
                                total_outlets = len(outlet_mapping)
                                unique_areas = outlet_mapping["area"].replace("", np.nan).nunique() if "area" in outlet_mapping.columns else 0
                                unique_tipes = outlet_mapping["tipe_tempat"].replace("", np.nan).nunique() if "tipe_tempat" in outlet_mapping.columns else 0
                                with ui.card().style("background-color: #181825; border-radius: 8px; padding: 12px; flex: 1;"):
                                    ui.label("Total Outlet").classes("text-xs text-gray-400")
                                    ui.label(f"{total_outlets:,}").classes("text-xl font-bold text-white")
                                with ui.card().style("background-color: #181825; border-radius: 8px; padding: 12px; flex: 1;"):
                                    ui.label("Area").classes("text-xs text-gray-400")
                                    ui.label(f"{unique_areas:,}").classes("text-xl font-bold text-white")
                                with ui.card().style("background-color: #181825; border-radius: 8px; padding: 12px; flex: 1;"):
                                    ui.label("Tipe").classes("text-xs text-gray-400")
                                    ui.label(f"{unique_tipes:,}").classes("text-xl font-bold text-white")

                            # Search & Filters row
                            with ui.row().classes("w-full gap-2 items-center"):
                                search_input = ui.input("🔍 Search outlet", placeholder="Ketik nama outlet...").props("dense outlined dark").classes("flex-1")
                                area_filter = ui.select(
                                    ["Semua"] + _safe_unique_str(outlet_mapping, "area"),
                                    value="Semua", label="Area",
                                ).props("dense outlined dark").classes("w-48")
                                kategori_filter = ui.select(
                                    ["Semua"] + _safe_unique_str(outlet_mapping, "kategori_tempat"),
                                    value="Semua", label="Kategori",
                                ).props("dense outlined dark").classes("w-48")
                                tipe_filter = ui.select(
                                    ["Semua"] + _safe_unique_str(outlet_mapping, "tipe_tempat"),
                                    value="Semua", label="Tipe",
                                ).props("dense outlined dark").classes("w-40")

                            ui.label("Edit area, kategori, sub kategori, dan tipe langsung di tabel. Outlet name dikunci agar identitas outlet tidak berubah tanpa sengaja.").classes("text-xs text-gray-400 mb-2")

                            # Table area
                            table_area = ui.column().classes("w-full")
                            edit_status = ui.label("").classes("text-sm mt-2")

                            # Build editor data for the table
                            visible = outlet_mapping.copy()
                            cols_display = [c for c in required_cols if c in visible.columns]

                            def refresh_edit_table():
                                table_area.clear()
                                with table_area:
                                    s = search_input.value
                                    af = area_filter.value
                                    kf = kategori_filter.value
                                    tf = tipe_filter.value

                                    v = outlet_mapping.copy()
                                    if s:
                                        v = v[v["outlet_name"].str.contains(s, case=False, na=False)]
                                    if af != "Semua":
                                        v = v[v["area"] == af]
                                    if kf != "Semua":
                                        v = v[v["kategori_tempat"] == kf]
                                    if tf != "Semua":
                                        v = v[v["tipe_tempat"] == tf]

                                    if v.empty:
                                        ui.label("Tidak ada outlet yang cocok dengan filter.").classes("text-gray-400 italic")
                                        return

                                    # Show editable table with inline selects
                                    with ui.row().classes("w-full gap-2 mb-2"):
                                        ui.label(f"Menampilkan {len(v):,} dari {len(outlet_mapping):,} outlet.").classes("text-xs text-gray-400")
                                        ui.button("💾 Save Changes", on_click=lambda: save_edit_changes(v), color="primary").props("dense")

                                    # Build a grid-like editable table
                                    for idx, (_, row) in enumerate(v.iterrows()):
                                        with ui.card().style("background-color: #181825; border-radius: 6px; padding: 8px 12px; margin-bottom: 4px;").classes("w-full"):
                                            with ui.row().classes("w-full gap-2 items-center"):
                                                # Outlet name (read-only)
                                                ui.label(str(row.get("outlet_name", ""))).classes("text-sm text-white font-bold w-48")

                                                # Area select
                                                area_opts = sorted(set(INDONESIA_AREAS) | set(_safe_unique_str(outlet_mapping, "area")))
                                                area_sel = ui.select(
                                                    area_opts,
                                                    value=str(row.get("area", "")) if str(row.get("area", "")) in area_opts else area_opts[0],
                                                    label="Area",
                                                ).props("dense outlined dark").classes("w-40")

                                                # Kategori select
                                                kat_opts = sorted(set(KATEGORI_TEMPAT) | set(_safe_unique_str(outlet_mapping, "kategori_tempat")))
                                                kat_sel = ui.select(
                                                    kat_opts,
                                                    value=str(row.get("kategori_tempat", "")) if str(row.get("kategori_tempat", "")) in kat_opts else kat_opts[0],
                                                    label="Kategori",
                                                ).props("dense outlined dark").classes("w-40")

                                                # Sub kategori select
                                                sub_opts = sorted(set(SUB_KATEGORI_TEMPAT) | set(_safe_unique_str(outlet_mapping, "sub_kategori_tempat")))
                                                sub_sel = ui.select(
                                                    sub_opts,
                                                    value=str(row.get("sub_kategori_tempat", "")) if str(row.get("sub_kategori_tempat", "")) in sub_opts else sub_opts[0],
                                                    label="Sub Kategori",
                                                ).props("dense outlined dark").classes("w-44")

                                                # Tipe select
                                                tipe_opts = sorted(set(["Indoor", "Outdoor", "Semi-Outdoor"]) | set(_safe_unique_str(outlet_mapping, "tipe_tempat")))
                                                tipe_sel = ui.select(
                                                    tipe_opts,
                                                    value=str(row.get("tipe_tempat", "")) if str(row.get("tipe_tempat", "")) in tipe_opts else tipe_opts[0],
                                                    label="Tipe",
                                                ).props("dense outlined dark").classes("w-36")

                                                # Store refs for save
                                                area_sel._outlet_name = str(row.get("outlet_name", ""))
                                                kat_sel._outlet_name = str(row.get("outlet_name", ""))
                                                sub_sel._outlet_name = str(row.get("outlet_name", ""))
                                                tipe_sel._outlet_name = str(row.get("outlet_name", ""))

                                                # We need to store these for the save function
                                                # Use a closure-based approach
                                                row_data = row.to_dict()
                                                area_sel._row_data = row_data
                                                kat_sel._row_data = row_data
                                                sub_sel._row_data = row_data
                                                tipe_sel._row_data = row_data

                                                # Store these references for the save function to find
                                                if not hasattr(refresh_edit_table, "_edit_rows"):
                                                    refresh_edit_table._edit_rows = []
                                                refresh_edit_table._edit_rows.append({
                                                    "name": str(row.get("outlet_name", "")),
                                                    "area_sel": area_sel,
                                                    "kat_sel": kat_sel,
                                                    "sub_sel": sub_sel,
                                                    "tipe_sel": tipe_sel,
                                                })

                            def save_edit_changes(visible_df):
                                """Save changes from inline editors."""
                                nonlocal outlet_mapping
                                try:
                                    updated = outlet_mapping.copy()
                                    edited_rows = getattr(refresh_edit_table, "_edit_rows", [])
                                    for ed in edited_rows:
                                        name = ed["name"]
                                        if name in updated["outlet_name"].values:
                                            mask = updated["outlet_name"] == name
                                            updated.loc[mask, "area"] = ed["area_sel"].value
                                            updated.loc[mask, "kategori_tempat"] = ed["kat_sel"].value
                                            updated.loc[mask, "sub_kategori_tempat"] = ed["sub_sel"].value
                                            updated.loc[mask, "tipe_tempat"] = ed["tipe_sel"].value

                                    updated = updated[[c for c in required_cols if c in updated.columns]]
                                    updated = updated.sort_values("outlet_name").reset_index(drop=True)
                                    updated.to_csv(OUTLET_MAPPING_PATH_ST, index=False)

                                    # Refresh global
                                    outlet_mapping = updated

                                    edit_status.classes("text-green-400")
                                    edit_status.set_text("✅ Outlet mapping berhasil disimpan.")
                                    refresh_edit_table._edit_rows = []
                                    refresh_edit_table()
                                except Exception as ex:
                                    edit_status.classes("text-red-400")
                                    edit_status.set_text(f"❌ Gagal menyimpan: {ex}")

                            # Call refresh to populate
                            refresh_edit_table()

                    # ── ADD TAB ──
                    with ui.tab_panel("add"):
                        with ui.card().style(CARD).classes("w-full"):
                            ui.label("➕ Add New Outlet").style(SECTION_T)
                            new_name = ui.input("Outlet Name *", placeholder="Nama outlet...").props("dense outlined dark").classes("w-full mb-3")
                            with ui.row().classes("w-full gap-4"):
                                new_area = ui.select(INDONESIA_AREAS, value=INDONESIA_AREAS[0] if INDONESIA_AREAS else "", label="Area").props("dense outlined dark").classes("flex-1")
                                new_kategori = ui.select(KATEGORI_TEMPAT, value=KATEGORI_TEMPAT[0] if KATEGORI_TEMPAT else "", label="Kategori").props("dense outlined dark").classes("flex-1")
                            with ui.row().classes("w-full gap-4"):
                                new_sub = ui.select(SUB_KATEGORI_TEMPAT, value=SUB_KATEGORI_TEMPAT[0] if SUB_KATEGORI_TEMPAT else "", label="Sub Kategori").props("dense outlined dark").classes("flex-1")
                                new_tipe = ui.select(["Indoor", "Outdoor", "Semi-Outdoor"], value="Indoor", label="Tipe").props("dense outlined dark").classes("flex-1")
                            add_status = ui.label("").classes("text-sm mt-2")

                            def add_outlet():
                                nonlocal outlet_mapping
                                name = new_name.value.strip()
                                if not name:
                                    add_status.classes("text-red-400")
                                    add_status.set_text("❌ Outlet name wajib diisi.")
                                    return
                                if name in outlet_mapping["outlet_name"].values:
                                    add_status.classes("text-red-400")
                                    add_status.set_text(f"❌ Outlet '{name}' sudah ada.")
                                    return
                                new_row = pd.DataFrame([{
                                    "outlet_name": name,
                                    "area": new_area.value,
                                    "kategori_tempat": new_kategori.value,
                                    "sub_kategori_tempat": new_sub.value,
                                    "tipe_tempat": new_tipe.value,
                                }])
                                updated = pd.concat([outlet_mapping, new_row], ignore_index=True)
                                updated = updated[[c for c in required_cols if c in updated.columns]]
                                updated = updated.sort_values("outlet_name").reset_index(drop=True)
                                updated.to_csv(OUTLET_MAPPING_PATH_ST, index=False)
                                # Remove from deleted list if present
                                deleted = [x for x in load_deleted_outlets_fn() if x != name]
                                save_deleted_outlets_fn(deleted)
                                outlet_mapping = updated
                                new_name.value = ""
                                add_status.classes("text-green-400")
                                add_status.set_text(f"✅ Outlet '{name}' berhasil ditambahkan!")

                            ui.button("Add Outlet", on_click=add_outlet, color="primary")

                    # ── DELETE TAB ──
                    with ui.tab_panel("delete"):
                        with ui.card().style(CARD).classes("w-full"):
                            ui.label("🗑️ Delete Outlet").style(SECTION_T)
                            ui.label("Centang outlet yang mau dihapus dari mapping CRUD. Data transaksi historis tidak ikut dihapus.").classes("text-xs text-gray-400 mb-3")

                            delete_table_area = ui.column().classes("w-full")
                            delete_status = ui.label("").classes("text-sm mt-2")

                            # Checkbox list of outlets
                            selected_for_delete = set()

                            def refresh_delete_table():
                                delete_table_area.clear()
                                selected_for_delete.clear()
                                with delete_table_area:
                                    sorted_mapping = outlet_mapping.sort_values("outlet_name").reset_index(drop=True)
                                    if sorted_mapping.empty:
                                        ui.label("Tidak ada outlet untuk dihapus.").classes("text-gray-400 italic")
                                        return

                                    for _, row in sorted_mapping.iterrows():
                                        name = str(row.get("outlet_name", ""))
                                        with ui.row().classes("w-full items-center gap-3 py-1"):
                                            cb = ui.checkbox(text="").props("dense")
                                            cb._outlet_name = name
                                            ui.label(name).classes("text-sm text-white w-48")
                                            ui.label(str(row.get("area", ""))).classes("text-sm text-gray-400 w-32")
                                            ui.label(str(row.get("kategori_tempat", ""))).classes("text-sm text-gray-400 w-32")
                                            ui.label(str(row.get("tipe_tempat", ""))).classes("text-sm text-gray-400 w-24")

                                            def toggle_outlet(cb=cb, n=name):
                                                if cb.value:
                                                    selected_for_delete.add(n)
                                                else:
                                                    selected_for_delete.discard(n)
                                            cb.on("update:model-value", lambda _, cb=cb, n=name: toggle_outlet(cb, n))

                            refresh_delete_table()

                            with ui.row().classes("w-full gap-2 mt-3"):
                                ui.button("🗑️ Delete Selected", color="negative", on_click=lambda: confirm_delete_selected())
                                ui.button("Clear Selection", on_click=lambda: refresh_delete_table()).props("flat")

                            def confirm_delete_selected():
                                outlets_to_delete = list(selected_for_delete)
                                if not outlets_to_delete:
                                    delete_status.classes("text-red-400")
                                    delete_status.set_text("❌ Pilih minimal 1 outlet untuk dihapus.")
                                    return
                                # Show confirmation dialog
                                with ui.dialog() as dialog, ui.card():
                                    ui.label(f"Hapus {len(outlets_to_delete)} outlet?").classes("text-lg font-bold text-white mb-2")
                                    ui.label("Ketik DELETE untuk konfirmasi:").classes("text-sm text-gray-400")
                                    confirm_input = ui.input("Ketik DELETE").props("dense outlined dark").classes("w-full")
                                    with ui.row().classes("gap-2 mt-3"):
                                        ui.button("Konfirmasi Hapus", color="negative", on_click=lambda: do_delete(outlets_to_delete, confirm_input, dialog))
                                        ui.button("Batal", on_click=dialog.close).props("flat")
                                    dialog.open()

                            def do_delete(outlets_to_delete, confirm_input, dialog):
                                if confirm_input.value != "DELETE":
                                    delete_status.classes("text-red-400")
                                    delete_status.set_text("❌ Konfirmasi belum benar. Ketik DELETE untuk menghapus.")
                                    dialog.close()
                                    return
                                nonlocal outlet_mapping
                                updated = outlet_mapping[~outlet_mapping["outlet_name"].isin(outlets_to_delete)].copy()
                                updated.to_csv(OUTLET_MAPPING_PATH_ST, index=False)
                                deleted_now = set(load_deleted_outlets_fn())
                                deleted_now.update(str(x).strip() for x in outlets_to_delete if str(x).strip())
                                save_deleted_outlets_fn(list(deleted_now))
                                outlet_mapping = updated
                                dialog.close()
                                delete_status.classes("text-green-400")
                                delete_status.set_text(f"✅ {len(outlets_to_delete)} outlet berhasil dihapus dari mapping CRUD.")
                                refresh_delete_table()

                    # ── AI SUGGEST TAB ──
                    with ui.tab_panel("ai"):
                        with ui.card().style(CARD).classes("w-full"):
                            ui.label("🤖 AI Suggest Outlet Mapping").style(SECTION_T)
                            ui.label("AI lokal membaca nama outlet untuk menebak area, kategori, sub kategori, dan tipe. Lo tetap bisa edit hasilnya sebelum apply.").classes("text-xs text-gray-400 mb-3")

                            with ui.row().classes("w-full gap-4 items-center"):
                                only_needs = ui.checkbox("Tampilkan yang belum lengkap saja", value=True)
                                min_conf = ui.slider(min=0, max=100, value=55, step=5, label="Minimum confidence").props("label-always").classes("w-64")

                            ai_status = ui.label("").classes("text-sm mt-2")
                            ai_table_area = ui.column().classes("w-full")

                            def run_ai_suggest():
                                ai_table_area.clear()
                                with ai_table_area:
                                    ai_source = outlet_mapping.copy()
                                    suggestions = []

                                    for _, row in ai_source.iterrows():
                                        suggestion = _suggest_outlet_metadata(row.get("outlet_name", ""), row.to_dict())
                                        if only_needs.value and not suggestion["needs_update"]:
                                            continue
                                        if int(suggestion["confidence"]) < int(min_conf.value):
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
                                        ui.label("Tidak ada outlet yang cocok dengan filter AI Suggest.").classes("text-gray-400 italic")
                                        return

                                    ui.label(f"{len(suggestions)} rekomendasi ditemukan.").classes("text-sm text-gray-300 mb-2")

                                    # Store suggestions in a way we can edit them inline
                                    suggestion_df = pd.DataFrame(suggestions)
                                    selected_apply = {}

                                    # Render each suggestion as a row with checkbox
                                    for idx, (_, srow) in enumerate(suggestion_df.iterrows()):
                                        with ui.card().style("background-color: #181825; border-radius: 6px; padding: 8px 12px; margin-bottom: 4px;").classes("w-full"):
                                            with ui.row().classes("w-full gap-2 items-center"):
                                                cb = ui.checkbox(text="Apply").props("dense")
                                                cb._idx = idx
                                                selected_apply[idx] = False
                                                def on_apply_change(e, i=idx):
                                                    selected_apply[i] = e.value
                                                cb.on("update:model-value", on_apply_change)

                                                ui.label(str(srow.get("outlet_name", ""))).classes("text-sm text-white font-bold w-40")

                                                # Current values
                                                ui.label(f"Area: {srow.get('current_area', '')}").classes("text-xs text-gray-400 w-28")
                                                ui.label(f"Kat: {srow.get('current_kategori', '')}").classes("text-xs text-gray-400 w-28")

                                                # Suggested editable selects
                                                area_opts = sorted(set(INDONESIA_AREAS) | set(_safe_unique_str(outlet_mapping, "area")) | {"Lainnya"})
                                                area_ai = ui.select(area_opts, value=str(srow.get("suggested_area", "Lainnya")), label="Area AI").props("dense outlined dark").classes("w-36")
                                                kat_opts = sorted(set(KATEGORI_TEMPAT) | {"Lainnya"})
                                                kat_ai = ui.select(kat_opts, value=str(srow.get("suggested_kategori_tempat", "Lainnya")), label="Kat AI").props("dense outlined dark").classes("w-36")
                                                sub_opts = sorted(set(SUB_KATEGORI_TEMPAT) | {"Lainnya"})
                                                sub_ai = ui.select(sub_opts, value=str(srow.get("suggested_sub_kategori_tempat", "Lainnya")), label="Sub AI").props("dense outlined dark").classes("w-40")
                                                tipe_ai = ui.select(["Indoor", "Outdoor", "Semi-Outdoor"], value=str(srow.get("suggested_tipe_tempat", "Indoor")), label="Tipe AI").props("dense outlined dark").classes("w-32")
                                                ui.label(f"Conf: {srow.get('confidence', 0)}%").classes("text-xs text-gray-400 w-16")

                                                # Store selections for apply
                                                area_ai._idx = idx
                                                kat_ai._idx = idx
                                                sub_ai._idx = idx
                                                tipe_ai._idx = idx
                                                area_ai._outlet_name = str(srow.get("outlet_name", ""))
                                                kat_ai._outlet_name = str(srow.get("outlet_name", ""))
                                                sub_ai._outlet_name = str(srow.get("outlet_name", ""))
                                                tipe_ai._outlet_name = str(srow.get("outlet_name", ""))

                                                # Store refs for apply function
                                                if not hasattr(run_ai_suggest, "_ai_rows"):
                                                    run_ai_suggest._ai_rows = []
                                                run_ai_suggest._ai_rows.append({
                                                    "idx": idx,
                                                    "outlet_name": str(srow.get("outlet_name", "")),
                                                    "area_sel": area_ai,
                                                    "kat_sel": kat_ai,
                                                    "sub_sel": sub_ai,
                                                    "tipe_sel": tipe_ai,
                                                })

                                    # Apply button
                                    def apply_ai_suggestions():
                                        selected = [r for r in getattr(run_ai_suggest, "_ai_rows", []) if selected_apply.get(r["idx"], False)]
                                        if not selected:
                                            ai_status.classes("text-red-400")
                                            ai_status.set_text("❌ Tidak ada yang dicentang untuk di-apply.")
                                            return

                                        nonlocal outlet_mapping
                                        updated = outlet_mapping.copy()
                                        for r in selected:
                                            name = r["outlet_name"]
                                            if name in updated["outlet_name"].values:
                                                mask = updated["outlet_name"] == name
                                                updated.loc[mask, "area"] = r["area_sel"].value
                                                updated.loc[mask, "kategori_tempat"] = r["kat_sel"].value
                                                updated.loc[mask, "sub_kategori_tempat"] = r["sub_sel"].value
                                                updated.loc[mask, "tipe_tempat"] = r["tipe_sel"].value

                                        updated = updated[[c for c in required_cols if c in updated.columns]]
                                        updated = updated.sort_values("outlet_name").reset_index(drop=True)
                                        updated.to_csv(OUTLET_MAPPING_PATH_ST, index=False)
                                        outlet_mapping = updated
                                        run_ai_suggest._ai_rows = []
                                        ai_status.classes("text-green-400")
                                        ai_status.set_text(f"✅ {len(selected)} outlet berhasil diupdate dari rekomendasi AI.")
                                        run_ai_suggest()

                                    ui.button("Apply AI Suggestions", on_click=apply_ai_suggestions, color="primary").classes("mt-2")

                            ui.button("🔍 Generate AI Suggestions", on_click=run_ai_suggest, color="primary").classes("mb-2")
                            run_ai_suggest()

        # ════════════════════════════════════════
        # TAB 2: MASTER DATA
        # ════════════════════════════════════════
        with panels:
            with ui.tab_panel("master"):
                with ui.card().style(CARD).classes("w-full"):
                    ui.label("📋 Master Data Kategori & Area").style(SECTION_T)
                    ui.label("Edit nilai master data. Perubahan dipakai sebagai opsi di Add/Edit/AI Suggest.").classes("text-xs text-gray-400 mb-3")

                    # Three columns for master data editors
                    with ui.row().classes("w-full gap-4"):
                        col1 = ui.column().classes("flex-1")
                        col2 = ui.column().classes("flex-1")
                        col3 = ui.column().classes("flex-1")

                    _render_master_data_editor(
                        "Area", "areas", INDONESIA_AREAS,
                        col1, load_master_data_fn, save_master_data_fn, apply_master_data_fn
                    )
                    _render_master_data_editor(
                        "Kategori Tempat", "kategori_tempat", KATEGORI_TEMPAT,
                        col2, load_master_data_fn, save_master_data_fn, apply_master_data_fn
                    )
                    _render_master_data_editor(
                        "Sub Kategori Tempat", "sub_kategori_tempat", SUB_KATEGORI_TEMPAT,
                        col3, load_master_data_fn, save_master_data_fn, apply_master_data_fn
                    )

        # ════════════════════════════════════════
        # TAB 3: DELETED OUTLETS
        # ════════════════════════════════════════
        with panels:
            with ui.tab_panel("deleted"):
                with ui.card().style(CARD).classes("w-full"):
                    ui.label("🗑️ Deleted Outlets").style(SECTION_T)
                    ui.label("Outlet yang sudah dihapus dari mapping CRUD. Data transaksi historis tetap aman.").classes("text-xs text-gray-400 mb-3")

                    deleted_list = load_deleted_outlets_fn()
                    if deleted_list:
                        df_del = pd.DataFrame({"outlet_name": sorted(deleted_list)})
                        _render_table(df_del)
                    else:
                        ui.label("Belum ada outlet yang dihapus.").classes("text-gray-400 italic")

                    # Restore functionality
                    ui.separator().classes("my-3")
                    ui.label("Pulihkan outlet yang sudah dihapus:").classes("text-sm text-gray-300 mb-2")
                    if deleted_list:
                        restore_select = ui.select(
                            sorted(deleted_list),
                            value=None,
                            label="Pilih outlet untuk dipulihkan",
                        ).props("dense outlined dark use-chips").classes("w-full mb-2")
                        restore_status = ui.label("").classes("text-sm")

                        def restore_outlet():
                            name = restore_select.value
                            if not name:
                                return
                            # Add back to mapping
                            new_row = pd.DataFrame([{
                                "outlet_name": name,
                                "area": "",
                                "kategori_tempat": "Tidak Terkategorisasi",
                                "sub_kategori_tempat": "Tidak Terkategorisasi",
                                "tipe_tempat": "Indoor",
                            }])
                            nonlocal outlet_mapping
                            updated = pd.concat([outlet_mapping, new_row], ignore_index=True)
                            updated = updated[[c for c in required_cols if c in updated.columns]]
                            updated = updated.sort_values("outlet_name").reset_index(drop=True)
                            updated.to_csv(OUTLET_MAPPING_PATH_ST, index=False)
                            # Remove from deleted list
                            deleted = [x for x in load_deleted_outlets_fn() if x != name]
                            save_deleted_outlets_fn(deleted)
                            outlet_mapping = updated
                            restore_status.classes("text-green-400")
                            restore_status.set_text(f"✅ Outlet '{name}' berhasil dipulihkan!")

                        ui.button("Pulihkan Outlet", on_click=restore_outlet, color="primary")
                    else:
                        ui.label("Tidak ada outlet yang bisa dipulihkan.").classes("text-gray-400 italic")
