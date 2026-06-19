"""ERPNext REST API client — fetch, create, update Lead Partnership & Lead records."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import requests

from config import CONFIG_DIR, load_erpnext_config as _load_cfg, save_erpnext_config as _save_cfg

# ================= CONFIG =================

ERPNEXT_CONFIG_PATH = CONFIG_DIR / "erpnext_config.json"

# Lead Partnership fields (existing)
LEAD_PARTNERSHIP_FIELDS = [
    "name", "lead_name", "jenis", "tempat", "pic", "kota",
    "lokasi", "skema", "status", "status_kemitraan",
    "creation", "modified", "custom_note", "custom_phone",
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

    Uses the LEAD_FIELDS list. Returns empty DataFrame on error.
    """
    return _fetch_all("Lead", LEAD_FIELDS, limit=limit)


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


# ================= LEAD PARTNERSHIP FUNCTIONS (existing) =================

def fetch_lead_partnerships(limit: int = 200) -> pd.DataFrame:
    """Fetch Lead Partnership records as a DataFrame. Returns empty on error."""
    cfg = load_erpnext_config()
    if not cfg.get("url"):
        return pd.DataFrame()

    try:
        fields = '["name","lead_name","jenis","tempat","pic","kota","lokasi","skema","status","creation","modified"]'
        r = requests.get(
            f"{_base_url(cfg)}/api/resource/Lead%20Partnership",
            headers=_headers(cfg),
            params={
                "limit_page_length": min(limit, 200),
                "fields": fields,
            },
            timeout=30,
        )
        if r.status_code != 200:
            return pd.DataFrame()

        data = r.json().get("data", [])
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Normalise column types
        for col in ["creation", "modified"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        return df

    except Exception:
        return pd.DataFrame()


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
    if not payload.get("lead_name"):
        return False, "Nama lead (lead_name) wajib diisi."

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


# ================= FIELD OPTIONS =================

def get_jenis_options() -> list:
    """Possible values for Lead Partnership 'jenis' field."""
    return [
        "", "Lokasi Permanen", "Lokasi Semi Permanen",
        "Pop Up", "Event", "Lainnya",
    ]


def get_skema_options() -> list:
    return ["", "Sewa", "Bagi Hasil", "Sewa + Bagi Hasil", "Kerjasama", "Lainnya"]


def get_lokasi_options() -> list:
    return [
        "", "Indoor", "Outdoor", "Semi-Outdoor",
        "Indoor, < 500 pengunjung/hari",
        "Indoor, 500-2000 pengunjung/hari",
        "Indoor, > 2000 pengunjung/hari",
        "Outdoor, < 500 pengunjung/hari",
        "Outdoor, 500-2000 pengunjung/hari",
        "Outdoor, > 2000 pengunjung/hari",
    ]


def get_status_options() -> list:
    return [
        "", "Open", "Contact", "Negotiation", "Won", "Lost",
        "On Hold", "Spam",
    ]


def get_status_kemitraan_options() -> list:
    return ["", "Aktif", "Non-Aktif", "Proses"]
