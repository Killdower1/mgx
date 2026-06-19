"""ERPNext REST API client — fetch, create, update Lead Partnership records."""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import requests

from config import CONFIG_DIR

# ================= CONFIG =================

ERPNEXT_CONFIG_PATH = CONFIG_DIR / "erpnext_config.json"
LEAD_PARTNERSHIP_FIELDS = [
    "name", "lead_name", "jenis", "tempat", "pic", "kota",
    "lokasi", "skema", "status", "status_kemitraan",
    "creation", "modified", "custom_note", "custom_phone",
]


def load_erpnext_config() -> dict:
    try:
        with open(ERPNEXT_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_erpnext_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ERPNEXT_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _headers(config: dict) -> dict:
    key = (config.get("api_key") or "").strip()
    secret = (config.get("api_secret") or "").strip()
    return {"Authorization": f"token {key}:{secret}"}


def _base_url(config: dict) -> str:
    url = (config.get("url") or "").strip().rstrip("/")
    return url


# ================= CONNECTION =================

def check_connection() -> Tuple[bool, str]:
    """Test ERPNext connection by fetching 1 Lead Partnership record."""
    cfg = load_erpnext_config()
    if not cfg.get("url") or not cfg.get("api_key"):
        return False, "Konfigurasi ERPNext belum lengkap (URL, API Key, API Secret)."
    try:
        r = requests.get(
            f"{_base_url(cfg)}/api/resource/Lead%20Partnership",
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


# ================= FETCH LEAD PARTNERSHIPS =================

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


# ================= CREATE / UPDATE =================

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
            headers={** _headers(cfg), "Content-Type": "application/json"},
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
            headers={** _headers(cfg), "Content-Type": "application/json"},
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
