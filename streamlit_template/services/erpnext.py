"""ERPNext REST API client — fetch, create, update Lead Partnership & Lead records."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import requests

from config import CONFIG_DIR, DATA_DIR, load_erpnext_config as _load_cfg, save_erpnext_config as _save_cfg

# ================= CONFIG =================

ERPNEXT_CONFIG_PATH = CONFIG_DIR / "erpnext_config.json"
LEAD_PARTNERSHIP_CACHE_PATH = DATA_DIR / "lead_partnership_cache.json"
LEAD_CACHE_PATH = DATA_DIR / "lead_cache.json"
LEAD_KEMITRAAN_CACHE_PATH = DATA_DIR / "lead_kemitraan_cache.json"

# Lead Partnership fields (actual ERPNext field names — verified 2026-06-19)
LEAD_PARTNERSHIP_FIELDS = [
    "name",
    "nama_pic",                          # Nama PIC (kontak person)
    "nama_perusahaan__lembaga__venue_jika_ada",  # Perusahaan / Lembaga / Venue
    "nama_tempat",                       # Nama Tempat (venue)
    "jenis_partnership",                 # Jenis Partnership
    "kota_lokasi",                       # Kota / Lokasi
    "jenis_lokasi",                      # Jenis Lokasi (Mall, Hotel, Cafe, etc.)
    "tipe_lokasi",                       # Tipe Lokasi (Indoor/Outdoor)
    "skema_kerja_sama_yang_terbuka",     # Skema Kerjasama
    "status_lead",                       # Status Lead
    "source_lead",                       # Source / tahu dari mana
    "sales_pic",                         # Sales PIC (user ID)
    "sales_pic_full",                    # Sales PIC (full name)
    "jabatan_pic",                       # Jabatan PIC
    "nomor_whatsapp_pic",                # No. WhatsApp PIC
    "email_pic",                         # Email PIC
    "area_penempatan",                   # Area Penempatan
    "alamat__link_google_maps",          # Alamat / Google Maps
    "estimasi_pengunjung_per_hari",      # Estimasi Pengunjung/hari
    "space_tersedia",                    # Space Tersedia
    "listrik_tersedia",                  # Listrik Tersedia
    "kelayakan_space",                   # Kelayakan Space
    "kelayakan_listrik",                 # Kelayakan Listrik
    "kelayakan_operasional",             # Kelayakan Operasional
    "pic_responsif",                     # PIC Responsif
    "potensi_revenue",                   # Potensi Revenue
    "priority",                          # Prioritas
    "note",                              # Catatan
    "decision",                          # Keputusan
    "lost_reason",                       # Alasan Lost
    "last_follow_up",                    # Last Follow Up
    "next_follow_up",                    # Next Follow Up
    "hasil_follow_up",                   # Hasil Follow Up
    "harga_sewa",                        # Harga Sewa
    "revenue_share",                     # Revenue Share
    "minimum_payment",                   # Minimum Payment
    "minimum_kontrak",                   # Minimum Kontrak
    "skema_final",                       # Skema Final
    "datetime_contact",                  # Tgl Contact
    "datetime_qualified",                # Tgl Qualified
    "datetime_negotiation",              # Tgl Negotiation
    "datetime_approved",                 # Tgl Approved
    "datetime_live",                     # Tgl Live
    "datetime_lost",                     # Tgl Lost
    "creation",                          # Tgl Dibuat
    "modified",                          # Tgl Modifikasi
    "owner",                             # Pemilik Data
    "docstatus",                         # Status Dokumen
]

# Lead DocType fields for "Lead Permanen" page
# Core fields (confirmed existing on this ERPNext instance)
LEAD_FIELDS = [
    "name",
    "lead_name",                    # Nama
    "first_name",
    "title",
    "company_name",                 # Nama Perusahaan / Lembaga / Venue
    "email_id",                     # Email
    "mobile_no",                    # No. HP
    "phone",
    "website",
    "country",
    "tempat",                       # Kota/Lokasi Tempat (maps to city)
    "status",                       # Status Lead
    "lead_owner",                   # Sales PIC
    "social_media",                 # Source Lead / tahu dari mana
    "keperluan",                    # Keperluan / Purpose
    "qualification_status",
    "spot_foto",
    "spot_foto_event",
    "estimasi_kunjungan_harian",
    "total_kunjungan_harian",
    "type",
    "request_type",
    "no_of_employees",
    "annual_revenue",
    "language",
    "creation",                     # Datetime dibuat
    "modified",
    "notes",
    "akun_socmed",
    "image",
    "disabled",
]

# Extended fields (custom fields — add here when created on ERPNext)
# Uncomment / add after creating custom fields on ERPNext Lead DocType:
# "custom_kategori_tempat",        # Kategori Tempat (Mall, Restoran, dll)
# "custom_tipe_tempat",            # Tipe Lokasi (Indoor/Outdoor)
# "custom_tahu_difotoin_dari",     # Tahu Difotoin dari mana
# "custom_nama_tempat",            # Nama Tempat
# "custom_jabatan",                # Jabatan
# "custom_jenis_lokasi",           # Jenis Lokasi
# "custom_jenis_partnership",      # Jenis Partnership
# "custom_alamat_gmaps",           # Alamat / Link Google Maps
# "custom_estimasi_pengunjung",
# "custom_space_tersedia",
# "custom_area_penempatan",
# "custom_listrik_tersedia",
# "custom_skema_kerjasama",
# "custom_priority",
# "custom_datetime_new",
# "custom_datetime_contact",
# ...

# Field display name mapping untuk UI
FIELD_DISPLAY_NAMES = {
    "name": "ID Lead",
    "lead_name": "Nama",
    "first_name": "Nama Depan",
    "title": "Title",
    "company_name": "Perusahaan / Venue",
    "email_id": "Email",
    "mobile_no": "No. HP",
    "phone": "Telp",
    "tempat": "Lokasi / Kota",
    "country": "Negara",
    "status": "Status Lead",
    "lead_owner": "Sales PIC",
    "social_media": "Sumber Info",
    "keperluan": "Keperluan",
    "qualification_status": "Kualifikasi",
    "spot_foto": "Spot Foto",
    "estimasi_kunjungan_harian": "Estimasi Kunjungan/Hari",
    "total_kunjungan_harian": "Total Kunjungan/Hari",
    "type": "Tipe",
    "request_type": "Jenis Permintaan",
    "no_of_employees": "Karyawan",
    "annual_revenue": "Revenue Tahunan",
    "language": "Bahasa",
    "creation": "Tgl Dibuat",
    "modified": "Tgl Modifikasi",
    "akun_socmed": "Akun Sosmed",
    "disabled": "Nonaktif",
    # Custom field display names (when enabled)
    # "custom_kategori_tempat": "Kategori Tempat",
    # "custom_tipe_tempat": "Tipe Lokasi",
    # "custom_tahu_difotoin_dari": "Tahu Difotoin Dari",
    # "custom_nama_tempat": "Nama Tempat",
}

# Lead Partnership field display name mapping untuk UI
LEAD_PARTNERSHIP_DISPLAY_NAMES = {
    "name": "ID Lead",
    "nama_pic": "Nama PIC",
    "nama_perusahaan__lembaga__venue_jika_ada": "Perusahaan / Venue",
    "nama_tempat": "Nama Tempat",
    "jenis_partnership": "Jenis Partnership",
    "kota_lokasi": "Kota",
    "jenis_lokasi": "Jenis Lokasi",
    "tipe_lokasi": "Tipe Lokasi",
    "skema_kerja_sama_yang_terbuka": "Skema Kerjasama",
    "status_lead": "Status Lead",
    "source_lead": "Source Lead",
    "sales_pic": "Sales PIC",
    "sales_pic_full": "Sales PIC (Full)",
    "jabatan_pic": "Jabatan PIC",
    "nomor_whatsapp_pic": "No. WhatsApp",
    "email_pic": "Email PIC",
    "area_penempatan": "Area Penempatan",
    "alamat__link_google_maps": "Alamat / Google Maps",
    "estimasi_pengunjung_per_hari": "Estimasi Pengunjung/hari",
    "space_tersedia": "Space Tersedia",
    "listrik_tersedia": "Listrik Tersedia",
    "kelayakan_space": "Kelayakan Space",
    "kelayakan_listrik": "Kelayakan Listrik",
    "kelayakan_operasional": "Kelayakan Operasional",
    "pic_responsif": "PIC Responsif",
    "potensi_revenue": "Potensi Revenue",
    "priority": "Prioritas",
    "note": "Catatan",
    "decision": "Keputusan",
    "lost_reason": "Alasan Lost",
    "last_follow_up": "Last Follow Up",
    "next_follow_up": "Next Follow Up",
    "hasil_follow_up": "Hasil Follow Up",
    "harga_sewa": "Harga Sewa",
    "revenue_share": "Revenue Share",
    "minimum_payment": "Minimum Payment",
    "minimum_kontrak": "Minimum Kontrak",
    "skema_final": "Skema Final",
    "datetime_contact": "Tgl Contact",
    "datetime_qualified": "Tgl Qualified",
    "datetime_negotiation": "Tgl Negotiation",
    "datetime_approved": "Tgl Approved",
    "datetime_live": "Tgl Live",
    "datetime_lost": "Tgl Lost",
    "creation": "Tgl Dibuat",
    "modified": "Tgl Modifikasi",
    "owner": "Pemilik Data",
    "docstatus": "Status Dokumen",
}

# Lead Kemitraan field display name mapping untuk UI
LEAD_KEMITRAAN_DISPLAY_NAMES = {
    "name": "ID Kemitraan",
    "nama_lengkap": "Nama Lengkap",
    "nomor_whatsapp": "No. WhatsApp",
    "email": "Email",
    "kota_domisili": "Domisili",
    "pekerjaan_bisnis_saat_ini": "Pekerjaan / Bisnis",
    "kota_penempatan_mesin": "Kota Penempatan",
    "sudah_punya_lokasi": "Sudah Punya Lokasi",
    "tempat_instalasi": "Tempat Instalasi",
    "jumlah_unit_diminati": "Unit Diminati",
    "kapan_ingin_mulai": "Kapan Mulai",
    "dari_mana_tahu_difotoin": "Tahu Difotoin Dari",
    "source_lead": "Source Lead",
    "priority": "Prioritas",
    "status_lead": "Status Lead",
    "disposition": "Disposisi",
    "budget_investasi": "Budget Investasi",
    "jumlah_unit_final": "Unit Final",
    "harga_investasi_dibahas": "Nilai Investasi",
    "skema_pembayaran": "Skema Bayar",
    "kesiapan_dp": "Kesiapan DP",
    "target_bep": "Target BEP",
    "status_lokasi": "Status Lokasi",
    "jenis_lokasi": "Jenis Lokasi",
    "potensi_lokasi": "Potensi",
    "next_follow_up": "Follow-up Berikut",
    "hasil_follow_up_terakhir": "Hasil Follow-up",
    "next_step": "Next Step",
    "sales_pic": "Sales PIC",
    "creation": "Tgl Daftar",
    "modified": "Tgl Update",
}


def load_erpnext_config() -> dict:
    """Load ERPNext connection configuration (centralised via config.py)."""
    return _load_cfg()


def save_erpnext_config(data: dict) -> None:
    """Save ERPNext connection configuration (centralised via config.py)."""
    _save_cfg(data)


def _headers(config: dict) -> dict:
    key = (config.get("api_key") or "").strip()
    secret = (config.get("api_secret") or "").strip()
    return {"Authorization": f"token {key}:{secret}"}


def _base_url(config: dict) -> str:
    url = (config.get("url") or "").strip().rstrip("/")
    return url


# ================= CONNECTION =================

def check_connection(doctype: str = "Lead%20Partnership") -> Tuple[bool, str]:
    """Test ERPNext connection by fetching 1 record from given DocType."""
    cfg = load_erpnext_config()
    if not cfg.get("url") or not cfg.get("api_key"):
        return False, "Konfigurasi ERPNext belum lengkap (URL, API Key, API Secret)."
    try:
        r = requests.get(
            f"{_base_url(cfg)}/api/resource/{doctype}",
            headers=_headers(cfg),
            params={"limit_page_length": 1},
            timeout=15,
        )
        if r.status_code == 200:
            return True, "Koneksi ERPNext berhasil."
        elif r.status_code == 403:
            return False, "Akses ditolak (403). Periksa API Key / Secret."
        else:
            return False, f"Gagal ({r.status_code}): {r.text[:200]}"
    except requests.exceptions.ConnectionError:
        return False, "Tidak bisa terhubung ke server ERPNext. Periksa URL."
    except requests.exceptions.Timeout:
        return False, "Timeout — server ERPNext tidak merespon dalam 15 detik."
    except Exception as e:
        return False, f"Error: {e}"


# ================= GENERIC FETCH =================

def _fetch_all(doctype: str, fields: list, limit: int = 5000, filters: Optional[dict] = None) -> pd.DataFrame:
    """Fetch records from any ERPNext DocType with pagination.

    Uses limit_page_length + offset to handle >200 records.
    Returns a DataFrame with the requested fields, empty on error.
    """
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return pd.DataFrame()

    fields_json = json.dumps(fields)
    params: Dict[str, Any] = {
        "limit_page_length": min(200, limit),
        "fields": fields_json,
    }
    if filters:
        params["filters"] = json.dumps(filters)

    all_data = []
    offset = 0
    page_size = min(200, limit)

    try:
        while offset < limit:
            params["offset"] = offset
            r = requests.get(
                f"{_base_url(cfg)}/api/resource/{doctype}",
                headers=_headers(cfg),
                params=params,
                timeout=60,
            )
            if r.status_code != 200:
                break

            data = r.json().get("data", [])
            if not data:
                break

            all_data.extend(data)
            offset += page_size

            if len(data) < page_size:
                break

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)

        # Normalise datetime columns
        for col in ["creation", "modified"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        return df

    except Exception:
        return pd.DataFrame()


# ================= LEAD (DocType) FUNCTIONS =================

def fetch_leads(limit: int = 5000) -> pd.DataFrame:
    """Fetch Lead records from ERPNext as a DataFrame.

    Uses the LEAD_FIELDS list. Caches locally on success, falls back to cache on failure.
    Returns empty DataFrame on error.
    """
    df = _fetch_all("Lead", LEAD_FIELDS, limit=limit)
    if not df.empty:
        _save_lead_cache(df)
        return df

    cached = _load_lead_cache()
    if not cached.empty:
        return cached
    return pd.DataFrame()


def fetch_leads_by_owner(lead_owner: str, limit: int = 5000) -> pd.DataFrame:
    """Fetch Lead records filtered by lead_owner."""
    return _fetch_all("Lead", LEAD_FIELDS, limit=limit, filters={"lead_owner": lead_owner})


def fetch_lead_owners() -> List[str]:
    """Get distinct lead_owner values from Lead DocType."""
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return []

    try:
        r = requests.get(
            f"{_base_url(cfg)}/api/resource/Lead",
            headers=_headers(cfg),
            params={
                "fields": '["lead_owner"]',
                "limit_page_length": 5000,
                "filters": '["lead_owner", "!=", ""]',
            },
            timeout=30,
        )
        if r.status_code != 200:
            return []

        data = r.json().get("data", [])
        owners = sorted(set(
            d.get("lead_owner", "").strip()
            for d in data
            if d.get("lead_owner", "").strip()
        ))
        return owners
    except Exception:
        return []


def aggregate_lead_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute aggregate statistics from Lead DataFrame.

    Returns dict with keys:
      - total_all, total_today, total_this_week, total_this_month
      - status_distribution: {status: count}
      - city_top10: [(city, count), ...]
      - kategori_tempat: {kategori: count}
      - source_distribution: {source: count}
    """
    result: Dict[str, Any] = {
        "total_all": len(df),
        "total_today": 0,
        "total_this_week": 0,
        "total_this_month": 0,
        "status_distribution": {},
        "city_top10": [],
        "kategori_tempat": {},
        "source_distribution": {},
    }

    if df.empty:
        return result

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # Time-based counts
    if "creation" in df.columns:
        creation = pd.to_datetime(df["creation"], errors="coerce")
        result["total_today"] = int((creation >= today_start).sum())
        result["total_this_week"] = int((creation >= week_start).sum())
        result["total_this_month"] = int((creation >= month_start).sum())

    # Status distribution
    if "status" in df.columns:
        status_counts = df["status"].fillna("Unknown").value_counts()
        result["status_distribution"] = status_counts.to_dict()

    # City top 10 — use 'tempat' field (maps to location/city)
    city_col = None
    for col in ["tempat", "city", "kota", "location"]:
        if col in df.columns:
            city_col = col
            break
    if city_col:
        city_counts = df[city_col].fillna("Unknown").value_counts().head(10)
        result["city_top10"] = [(city, int(cnt)) for city, cnt in city_counts.items()]

    # Kategori Tempat — check custom field first, else use spot_foto / type as fallback
    kategori_col = None
    for col in ["custom_kategori_tempat", "kategori_tempat", "spot_foto", "type"]:
        if col in df.columns:
            kategori_col = col
            break
    if kategori_col:
        kat_counts = df[kategori_col].fillna("Tidak Ada").value_counts()
        result["kategori_tempat"] = kat_counts.to_dict()

    # Source distribution — use social_media field (maps to "tahu dari mana")
    source_col = None
    for col in ["social_media", "source", "custom_tahu_difotoin_dari", "source_custom", "keperluan"]:
        if col in df.columns:
            source_col = col
            break
    if source_col:
        src_counts = df[source_col].fillna("Unknown").value_counts()
        result["source_distribution"] = src_counts.to_dict()

    return result


def aggregate_team_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-lead_owner performance stats.

    Returns DataFrame with columns:
      lead_owner, Open, Contacted, Converted (Won), Lost, Total
    """
    if df.empty or "lead_owner" not in df.columns:
        return pd.DataFrame()

    # Define status mappings
    open_statuses = ["Open", "New", "Qualified", "Contact", ""]
    contacted_statuses = ["Contact", "Contacted", "Need Info"]
    converted_statuses = ["Won", "Converted", "Approved", "Live"]
    lost_statuses = ["Lost", "Closed", "Spam"]

    def categorize(status: str) -> Tuple[int, int, int, int]:
        s = str(status).strip()
        op = 1 if s in open_statuses or s in contacted_statuses else 0
        ct = 1 if s in contacted_statuses else 0
        cv = 1 if s in converted_statuses else 0
        ls = 1 if s in lost_statuses else 0
        return op, ct, cv, ls

    stats = []
    for owner, grp in df.groupby("lead_owner"):
        opens = contacts = converts = losses = 0
        for s in grp["status"].fillna("Open"):
            o, c, v, l = categorize(s)
            opens += o
            contacts += c
            converts += v
            losses += l

        stats.append({
            "lead_owner": owner,
            "Open": opens,
            "Contacted": contacts,
            "Converted": converts,
            "Lost": losses,
            "Total": len(grp),
        })

    result_df = pd.DataFrame(stats)
    if not result_df.empty:
        result_df = result_df.sort_values("Total", ascending=False).reset_index(drop=True)
    return result_df


# ================= LEAD PARTNERSHIP CACHE =================

def _save_lp_cache(df: pd.DataFrame) -> None:
    """Save Lead Partnership DataFrame to local JSON cache with timestamp."""
    if df.empty:
        return
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache = {
            "last_sync": datetime.now().isoformat(),
            "records": json.loads(df.to_json(orient="records", date_format="iso")),
        }
        with open(LEAD_PARTNERSHIP_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass

def _load_lp_cache() -> pd.DataFrame:
    """Load Lead Partnership DataFrame from local JSON cache."""
    try:
        if not LEAD_PARTNERSHIP_CACHE_PATH.exists():
            return pd.DataFrame()
        with open(LEAD_PARTNERSHIP_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        records = cache.get("records", [])
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        for col in ["creation", "modified"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

def get_lp_cache_info() -> dict:
    """Get cache info: last_sync time and record count. Returns {} if no cache."""
    try:
        if not LEAD_PARTNERSHIP_CACHE_PATH.exists():
            return {}
        with open(LEAD_PARTNERSHIP_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return {
            "last_sync": cache.get("last_sync", ""),
            "count": len(cache.get("records", [])),
        }
    except Exception:
        return {}

# ================= LEAD CACHE =================

def _save_lead_cache(df: pd.DataFrame) -> None:
    """Save Lead DataFrame to local JSON cache with timestamp."""
    if df.empty:
        return
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache = {
            "last_sync": datetime.now().isoformat(),
            "records": json.loads(df.to_json(orient="records", date_format="iso")),
        }
        with open(LEAD_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass

def _load_lead_cache() -> pd.DataFrame:
    """Load Lead DataFrame from local JSON cache."""
    try:
        if not LEAD_CACHE_PATH.exists():
            return pd.DataFrame()
        with open(LEAD_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        records = cache.get("records", [])
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        for col in ["creation", "modified"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

def get_lead_cache_info() -> dict:
    """Get Lead cache info: last_sync time and record count. Returns {} if no cache."""
    try:
        if not LEAD_CACHE_PATH.exists():
            return {}
        with open(LEAD_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return {
            "last_sync": cache.get("last_sync", ""),
            "count": len(cache.get("records", [])),
        }
    except Exception:
        return {}

# ================= LEAD KEMITRAAN CACHE =================

def _save_lk_cache(df: pd.DataFrame) -> None:
    """Save Lead Kemitraan DataFrame to local JSON cache with timestamp."""
    if df.empty:
        return
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cache = {
            "last_sync": datetime.now().isoformat(),
            "records": json.loads(df.to_json(orient="records", date_format="iso")),
        }
        with open(LEAD_KEMITRAAN_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass


def _load_lk_cache() -> pd.DataFrame:
    """Load Lead Kemitraan DataFrame from local JSON cache."""
    try:
        if not LEAD_KEMITRAAN_CACHE_PATH.exists():
            return pd.DataFrame()
        with open(LEAD_KEMITRAAN_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        records = cache.get("records", [])
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        for col in ["creation", "modified"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def get_lk_cache_info() -> dict:
    """Get Lead Kemitraan cache info: last_sync time and record count. Returns {} if no cache."""
    try:
        if not LEAD_KEMITRAAN_CACHE_PATH.exists():
            return {}
        with open(LEAD_KEMITRAAN_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return {
            "last_sync": cache.get("last_sync", ""),
            "count": len(cache.get("records", [])),
        }
    except Exception:
        return {}


# ================= LEAD KEMITRAAN FUNCTIONS =================

LEAD_KEMITRAAN_FIELDS = [
    "name", "nama_lengkap", "nomor_whatsapp", "email",
    "kota_domisili", "pekerjaan_bisnis_saat_ini", "kota_penempatan_mesin",
    "sudah_punya_lokasi", "tempat_instalasi", "jumlah_unit_diminati",
    "kapan_ingin_mulai", "dari_mana_tahu_difotoin", "source_lead",
    "priority", "status_lead", "disposition",
    "budget_investasi", "jumlah_unit_final", "harga_investasi_dibahas",
    "skema_pembayaran", "kesiapan_dp", "target_bep",
    "status_lokasi", "jenis_lokasi", "potensi_lokasi",
    "next_follow_up", "hasil_follow_up_terakhir", "next_step",
    "sales_pic", "creation", "modified",
]


def fetch_lead_kemitraan(limit: int = 5000) -> pd.DataFrame:
    """Fetch Lead Kemitraan records via API with caching fallback."""
    df = _fetch_all("Lead Kemitraan", LEAD_KEMITRAAN_FIELDS, limit=limit)
    if not df.empty:
        _save_lk_cache(df)
        return df
    cached = _load_lk_cache()
    if not cached.empty:
        return cached
    return pd.DataFrame()


def get_lead_kemitraan(record_name: str) -> dict:
    """Get single Lead Kemitraan record detail from ERPNext."""
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return {}
    try:
        r = requests.get(
            f"{_base_url(cfg)}/api/resource/Lead%20Kemitraan/{record_name}",
            headers=_headers(cfg),
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data", {})
        return {}
    except Exception:
        return {}


def create_lead_kemitraan(data: dict) -> Tuple[bool, str]:
    """Create a new Lead Kemitraan record. Returns (success, message)."""
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return False, "ERPNext belum dikonfigurasi."
    payload = {k: v for k, v in data.items() if v is not None and v != ""}
    try:
        r = requests.post(
            f"{_base_url(cfg)}/api/resource/Lead%20Kemitraan",
            headers={**_headers(cfg), "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            created = r.json().get("data", {})
            name = created.get("name", "")
            return True, f"Lead Kemitraan berhasil dibuat: {name}"
        msg = r.json().get("exc", r.text[:200])
        return False, f"Gagal membuat ({r.status_code}): {msg}"
    except Exception as e:
        return False, f"Error: {e}"


def update_lead_kemitraan(record_name: str, data: dict) -> Tuple[bool, str]:
    """Update an existing Lead Kemitraan record. Returns (success, message)."""
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return False, "ERPNext belum dikonfigurasi."
    if not record_name:
        return False, "Nama record tidak valid."
    payload = {k: v for k, v in data.items() if v is not None and v != ""}
    try:
        r = requests.put(
            f"{_base_url(cfg)}/api/resource/Lead%20Kemitraan/{record_name}",
            headers={**_headers(cfg), "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            return True, f"Lead Kemitraan {record_name} berhasil diupdate."
        msg = r.json().get("exc", r.text[:200])
        return False, f"Gagal update ({r.status_code}): {msg}"
    except Exception as e:
        return False, f"Error: {e}"


# ================= LEAD KEMITRAAN OPTIONS =================

def get_lk_status_lead_options() -> list:
    """Possible values for Lead Kemitraan 'status_lead' field."""
    return ["", "New", "Contact", "Meeting", "Qualified",
            "Negotiation", "Approved", "Live", "Lost"]


def get_lk_priority_options() -> list:
    """Possible values for Lead Kemitraan 'priority' field."""
    return ["", "High", "Medium", "Low"]


def get_lk_source_lead_options() -> list:
    """Possible values for Lead Kemitraan 'source_lead' field."""
    return ["", "Website", "Instagram", "WhatsApp", "TikTok",
            "Facebook", "Referral", "Event", "Lainnya"]


def get_lk_disposition_options() -> list:
    """Possible values for Lead Kemitraan 'disposition' field."""
    return ["", "Active", "Passive", "Warm", "Cold", "Closed"]


def get_lk_kesiapan_dp_options() -> list:
    """Possible values for 'kesiapan_dp' field."""
    return ["", "Siap", "Butuh Waktu", "Belum Siap"]


def get_lk_skema_pembayaran_options() -> list:
    """Possible values for 'skema_pembayaran' field."""
    return ["", "Cash", "Termin", "DP + pelunasan", "Kredit", "Lainnya"]


def get_lk_status_lokasi_options() -> list:
    """Possible values for 'status_lokasi' field."""
    return ["", "Sudah punya", "Ingin dibantu cari lokasi", "Minta dibantu Difotoin"]


def get_lk_jenis_lokasi_options() -> list:
    """Possible values for 'jenis_lokasi' field."""
    return ["", "Mall", "Cafe", "Restoran", "Hotel", "Ruko",
            "area publik", "kantor", "sekolah", "Lainnya"]


def get_lk_potensi_lokasi_options() -> list:
    """Possible values for 'potensi_lokasi' field."""
    return ["", "High", "Medium", "Low"]


# ================= LEAD PARTNERSHIP FUNCTIONS (existing) =================

def fetch_lead_partnerships(limit: int = 5000) -> pd.DataFrame:
    """Fetch Lead Partnership records as a DataFrame using _fetch_all() with wildcard fields.

    On success, caches data locally. On failure, returns cached data if available.
    Uses ["*"] to bypass ERPNext field-level restrictions on Lead Partnership DocType.
    Returns DataFrame with only LEAD_PARTNERSHIP_FIELDS columns, empty on error.
    """
    df = _fetch_all("Lead Partnership", ["*"], limit=limit)
    if not df.empty:
        avail = [c for c in LEAD_PARTNERSHIP_FIELDS if c in df.columns]
        result = df[avail]
        _save_lp_cache(result)
        return result

    # If fetch failed, try cache
    cached = _load_lp_cache()
    if not cached.empty:
        return cached
    return pd.DataFrame()


# ================= LEAD PARTNERSHIP AGGREGATION =================

def aggregate_lp_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute aggregate KPI funnel stats from Lead Partnership DataFrame.

    Returns dict with keys:
      - total_all, total_today, total_this_week, total_this_month
      - status_lead_distribution: {status: count}
      - jenis_partnership_distribution: {jenis: count}
      - source_lead_distribution: {source: count}
      - kota_top10: [(kota, count), ...]
      - jenis_lokasi_distribution: {jenis_lokasi: count}
      - sales_pic_count: number of unique sales PICs
      - priority_distribution: {priority: count}
      - conversion_funnel: {stage: count} — New→Contact→Qualified→Negotiation→Approved→Live
      - rata_rata_harga_sewa: mean harga_sewa (if numeric data exists)
    """
    result: Dict[str, Any] = {
        "total_all": len(df),
        "total_today": 0,
        "total_this_week": 0,
        "total_this_month": 0,
        "status_lead_distribution": {},
        "jenis_partnership_distribution": {},
        "source_lead_distribution": {},
        "kota_top10": [],
        "jenis_lokasi_distribution": {},
        "sales_pic_count": 0,
        "priority_distribution": {},
        "conversion_funnel": {},
        "rata_rata_harga_sewa": None,
    }

    if df.empty:
        return result

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # Time-based counts
    if "creation" in df.columns:
        creation = pd.to_datetime(df["creation"], errors="coerce")
        result["total_today"] = int((creation >= today_start).sum())
        result["total_this_week"] = int((creation >= week_start).sum())
        result["total_this_month"] = int((creation >= month_start).sum())

    # Status Lead distribution
    if "status_lead" in df.columns:
        sc = df["status_lead"].fillna("Unknown").value_counts()
        result["status_lead_distribution"] = sc.to_dict()

    # Jenis Partnership distribution
    if "jenis_partnership" in df.columns:
        jc = df["jenis_partnership"].fillna("Tidak Ada").value_counts()
        result["jenis_partnership_distribution"] = jc.to_dict()

    # Source Lead distribution
    if "source_lead" in df.columns:
        src = df["source_lead"].fillna("Unknown").value_counts()
        result["source_lead_distribution"] = src.to_dict()

    # Kota top 10
    if "kota_lokasi" in df.columns:
        kc = df["kota_lokasi"].fillna("Unknown").value_counts().head(10)
        result["kota_top10"] = [(k, int(c)) for k, c in kc.items()]

    # Jenis Lokasi distribution
    if "jenis_lokasi" in df.columns:
        jlc = df["jenis_lokasi"].fillna("Tidak Ada").value_counts()
        result["jenis_lokasi_distribution"] = jlc.to_dict()

    # Sales PIC unique count
    if "sales_pic" in df.columns:
        result["sales_pic_count"] = int(df["sales_pic"].dropna().nunique())

    # Priority distribution
    if "priority" in df.columns:
        pc = df["priority"].fillna("Unknown").value_counts()
        result["priority_distribution"] = pc.to_dict()

    # Conversion funnel — ordered stages
    funnel_order = ["New", "Contact", "Need Info", "Qualified",
                    "Negotiation", "Approved", "Live"]
    if "status_lead" in df.columns:
        funnel = {}
        for stage in funnel_order:
            count = int((df["status_lead"].astype(str).str.strip() == stage).sum())
            if count > 0:
                funnel[stage] = count
        result["conversion_funnel"] = funnel

    # Rata-rata harga sewa
    if "harga_sewa" in df.columns:
        numeric_sewa = pd.to_numeric(df["harga_sewa"], errors="coerce").dropna()
        if not numeric_sewa.empty:
            result["rata_rata_harga_sewa"] = float(numeric_sewa.mean())

    return result


def aggregate_lp_by_pic(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-sales_pic performance stats.

    Returns DataFrame with columns:
      sales_pic, total, New, Contact, Need Info, Qualified,
      Negotiation, Approved, Live, Lost, conversion_rate (Approved+Live / Total)
    """
    if df.empty or "sales_pic" not in df.columns:
        return pd.DataFrame()

    # Define status categories
    status_cols = ["New", "Contact", "Need Info", "Qualified",
                   "Negotiation", "Approved", "Live", "Lost"]

    stats = []
    for pic, grp in df.groupby("sales_pic"):
        if not pic or str(pic).strip() == "":
            continue

        row = {"sales_pic": pic, "total": len(grp)}
        # Count each status
        for s in status_cols:
            row[s] = int((grp["status_lead"].astype(str).str.strip() == s).sum()) if "status_lead" in grp.columns else 0

        # Conversion rate: (Approved + Live) / Total
        won = row.get("Approved", 0) + row.get("Live", 0)
        row["conversion_rate"] = round(won / max(row["total"], 1) * 100, 1)

        stats.append(row)

    if not stats:
        return pd.DataFrame()

    result_df = pd.DataFrame(stats)
    result_df = result_df.sort_values("total", ascending=False).reset_index(drop=True)
    return result_df


def aggregate_lp_by_source(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-source_lead distribution stats.

    Returns DataFrame with columns:
      source_lead, total, New, Contact, Qualified, Approved, Live, Lost
    """
    if df.empty or "source_lead" not in df.columns:
        return pd.DataFrame()

    status_cols = ["New", "Contact", "Qualified", "Approved", "Live", "Lost"]

    stats = []
    for src, grp in df.groupby("source_lead"):
        if not src or str(src).strip() == "":
            continue

        row = {"source_lead": src, "total": len(grp)}
        for s in status_cols:
            row[s] = int((grp["status_lead"].astype(str).str.strip() == s).sum()) if "status_lead" in grp.columns else 0
        stats.append(row)

    if not stats:
        return pd.DataFrame()

    result_df = pd.DataFrame(stats)
    result_df = result_df.sort_values("total", ascending=False).reset_index(drop=True)
    return result_df


def aggregate_lp_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly aggregation of Lead Partnership data.

    Groups by month (from `creation` field) and counts total leads
    plus breakdown per status_lead stage.

    Returns DataFrame with columns:
      bulan, total, New, Contact, Need Info, Qualified,
      Negotiation, Approved, Live, Lost, won_rate (Approved+Live / Total)
    """
    if df.empty or "creation" not in df.columns:
        return pd.DataFrame()

    # Extract month period
    months = pd.to_datetime(df["creation"], errors="coerce").dt.to_period("M")
    status_cols = ["New", "Contact", "Need Info", "Qualified",
                   "Negotiation", "Approved", "Live", "Lost"]

    rows = []
    for period, grp in df.groupby(months):
        if period is None or pd.isna(period):
            continue
        row = {"bulan": str(period)}
        row["total"] = len(grp)
        for s in status_cols:
            row[s] = int((grp["status_lead"].astype(str).str.strip() == s).sum()) if "status_lead" in grp.columns else 0
        won = row.get("Approved", 0) + row.get("Live", 0)
        row["won_rate"] = round(won / max(row["total"], 1) * 100, 1)
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    result_df = pd.DataFrame(rows)
    # Sort by bulan ascending
    result_df = result_df.sort_values("bulan").reset_index(drop=True)
    return result_df


def aggregate_lp_by_sales_pic_full(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-sales_pic_full performance stats.

    Groups by the sales_pic_full field (full name of the sales person)
    and returns aggregate counts per status stage + conversion rate.

    Returns DataFrame with columns:
      sales_pic_full, total, New, Contact, Need Info, Qualified,
      Negotiation, Approved, Live, Lost, conversion_rate (Approved+Live / Total)
    """
    if df.empty or "sales_pic_full" not in df.columns:
        return pd.DataFrame()

    status_cols = ["New", "Contact", "Need Info", "Qualified",
                   "Negotiation", "Approved", "Live", "Lost"]

    stats = []
    for pic, grp in df.groupby("sales_pic_full"):
        pic_name = str(pic).strip() if pic and str(pic).strip() else "(Tidak Ada)"
        row = {"sales_pic_full": pic_name, "total": len(grp)}
        for s in status_cols:
            row[s] = int((grp["status_lead"].astype(str).str.strip() == s).sum()) if "status_lead" in grp.columns else 0
        won = row.get("Approved", 0) + row.get("Live", 0)
        row["conversion_rate"] = round(won / max(row["total"], 1) * 100, 1)
        stats.append(row)

    if not stats:
        return pd.DataFrame()

    result_df = pd.DataFrame(stats)
    result_df = result_df.sort_values("total", ascending=False).reset_index(drop=True)
    return result_df


def get_lead_partnership(record_name: str) -> Optional[dict]:
    """Fetch a single Lead Partnership record by name (LP-xxxxx)."""
    cfg = load_erpnext_config()
    if not cfg.get("url") or not record_name:
        return None
    try:
        r = requests.get(
            f"{_base_url(cfg)}/api/resource/Lead%20Partnership/{record_name}",
            headers=_headers(cfg),
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data")
        return None
    except Exception:
        return None


def create_lead_partnership(data: dict) -> Tuple[bool, str]:
    """Create a new Lead Partnership record. Returns (success, message)."""
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return False, "ERPNext belum dikonfigurasi."

    payload = {k: v for k, v in data.items() if v is not None and v != ""}
    if not payload.get("nama_pic"):
        return False, "Nama PIC (nama_pic) wajib diisi."

    try:
        r = requests.post(
            f"{_base_url(cfg)}/api/resource/Lead%20Partnership",
            headers={**_headers(cfg), "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            created = r.json().get("data", {})
            name = created.get("name", "")
            return True, f"Lead Partnership berhasil dibuat: {name}"
        else:
            msg = r.json().get("exc", r.text[:200])
            return False, f"Gagal membuat lead ({r.status_code}): {msg}"
    except Exception as e:
        return False, f"Error: {e}"


def update_lead_partnership(record_name: str, data: dict) -> Tuple[bool, str]:
    """Update an existing Lead Partnership record. Returns (success, message)."""
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return False, "ERPNext belum dikonfigurasi."
    if not record_name:
        return False, "Nama record tidak valid."

    # Only send fields that have values
    payload = {k: v for k, v in data.items() if v is not None and v != ""}

    try:
        r = requests.put(
            f"{_base_url(cfg)}/api/resource/Lead%20Partnership/{record_name}",
            headers={**_headers(cfg), "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.status_code in (200, 201):
            return True, f"Lead {record_name} berhasil diupdate."
        else:
            msg = r.json().get("exc", r.text[:200])
            return False, f"Gagal update ({r.status_code}): {msg}"
    except Exception as e:
        return False, f"Error: {e}"


# ================= FIELD OPTIONS (Lead Partnership) =================

def get_jenis_partnership_options() -> list:
    """Possible values for Lead Partnership 'jenis_partnership' field."""
    return [
        "", "Lokasi Permanen", "Lokasi Semi Permanen",
        "Pop Up", "Event", "Lainnya",
    ]


def get_jenis_options() -> list:
    """Backward-compat alias for get_jenis_partnership_options()."""
    return get_jenis_partnership_options()


def get_skema_kerjasama_options() -> list:
    """Possible values for 'skema_kerja_sama_yang_terbuka' field."""
    return ["", "Sewa", "Revenue Sharing", "Bagi Hasil", "Sewa + Bagi Hasil", "Kerjasama", "Lainnya"]


def get_skema_options() -> list:
    """Backward-compat alias for get_skema_kerjasama_options()."""
    return get_skema_kerjasama_options()


def get_jenis_lokasi_options() -> list:
    """Possible values for 'jenis_lokasi' field (Mall, Hotel, Cafe, etc.)."""
    return [
        "", "Mall / Pusat Perbelanjaan", "Tempat Wisata", "Hotel",
        "Cafe / Restoran", "Taman / Area Publik", "Lainnya",
    ]


def get_lokasi_options() -> list:
    """Backward-compat alias for get_jenis_lokasi_options()."""
    return get_jenis_lokasi_options()


def get_tipe_lokasi_options() -> list:
    """Possible values for 'tipe_lokasi' field (Indoor/Outdoor)."""
    return ["", "Indoor", "Outdoor", "Semi-Outdoor"]


def get_status_lead_options() -> list:
    """Possible values for Lead Partnership 'status_lead' field."""
    return [
        "", "New", "Contact", "Need Info", "Qualified",
        "Negotiation", "Approved", "Live", "Lost",
    ]


def get_status_options() -> list:
    """Backward-compat alias for get_status_lead_options()."""
    return get_status_lead_options()


def get_source_lead_options() -> list:
    """Possible values for 'source_lead' field."""
    return ["", "Website", "Instagram", "WhatsApp", "Facebook", "Referensi", "Lainnya"]


def get_priority_options() -> list:
    """Possible values for 'priority' field."""
    return ["", "High", "Medium", "Low"]
