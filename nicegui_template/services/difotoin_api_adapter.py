"""
Difotoin.id API Adapter — auth, fetch transactions, aggregate, cache.
"""
import json
import os
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List, Tuple

import requests
import pandas as pd
import numpy as np
from services.transaction_classifier import classify_transactions

# ── Paths ──
ST_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
CONFIG_DIR = ST_DIR / "config"
API_CONFIG_PATH = CONFIG_DIR / "difotoin_api_config.json"
APP_CONFIG_PATH = CONFIG_DIR / "config.json"
DATA_CSV_PATH = ST_DIR / "data" / "difotoin_dashboard_data.csv"
OUTLET_MAPPING_PATH = ST_DIR / "data" / "difotoin_outlet_mapping.csv"
CACHE_DIR = ST_DIR / "data" / "api_cache"
RAW_TXNS_PATH = CACHE_DIR / "raw_transactions.json"
DASHBOARD_SUMMARY_PATH = CACHE_DIR / "dashboard_summary.json"
DAILY_SUMMARY_PATH = CACHE_DIR / "daily_summary.json"

# ── API Endpoints ──
BASE_URL = "https://difotoin.id"
LOGIN_URL = BASE_URL + "/login"
CSRF_URL = BASE_URL + "/sanctum/csrf-cookie"
TOKEN_CREATE_URL = BASE_URL + "/api/tokens/create"
TRANSACTIONS_URL = BASE_URL + "/api/transactions"

# ── Default Account ──
DEFAULT_EMAIL = None  # Moved to config
DEFAULT_PASSWORD = None  # Moved to config


# ═══════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════

def _load_config() -> dict:
    try:
        with open(API_CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_save_json(cfg, API_CONFIG_PATH)


def get_credentials() -> tuple:
    """Return (email, password) from config file.
    
    Raises ValueError if email/password are not configured.
    Credentials belong in streamlit_template/config/difotoin_api_config.json.
    """
    cfg = _load_config()
    email = cfg.get("email") or DEFAULT_EMAIL
    password = cfg.get("password") or DEFAULT_PASSWORD
    if not email or not password:
        raise ValueError(
            "API credentials not configured! "
            "Add email/password to streamlit_template/config/difotoin_api_config.json"
        )
    return (email, password)


def get_stored_token() -> Optional[str]:
    cfg = _load_config()
    return cfg.get("token") or None


def save_token(token: str):
    cfg = _load_config()
    cfg["token"] = token
    cfg["token_created_at"] = datetime.now().isoformat()
    _save_config(cfg)


def save_last_sync(ok: bool, message: str = ""):
    cfg = _load_config()
    cfg["last_sync"] = {
        "success": ok,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    _save_config(cfg)


def get_last_sync() -> dict:
    cfg = _load_config()
    return cfg.get("last_sync", {})



def _atomic_save_json(obj, path):
    """Save as JSON using atomic write (tmp + rename)."""
    tmp = str(path) + ".tmp." + str(os.getpid())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(obj, "to_json"):
            obj.to_json(tmp, orient="records")
        else:
            with open(tmp, "w") as f:
                json.dump(obj, f, indent=2, default=str)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _atomic_save_csv(df, path):
    """Save DataFrame as CSV using atomic write (tmp + rename)."""
    tmp = str(path) + ".tmp." + str(os.getpid())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(tmp, index=False)
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

def _load_status_thresholds() -> tuple:
    """Load status thresholds used by admin/settings."""
    try:
        with open(APP_CONFIG_PATH) as f:
            cfg = json.load(f)
        thresholds = cfg.get("thresholds", {})
        keeper_min = float(thresholds.get("keeper_minimum", 15000000))
        optimasi_min = float(thresholds.get("optimasi_minimum", 8000000))
        return keeper_min, optimasi_min
    except Exception:
        return 15000000.0, 8000000.0


def save_raw_by_month(txns, period):
    """
    Save transactions to raw_by_month/ with completeness validation.
    Rules:
    1. If new fetch has FEWER records than existing: REJECT (incomplete)
    2. Deduplicate by transaction ID (records are immutable)
    3. Sort by date
    4. Atomic save
    Returns (success, message)
    """
    RAW_BY_MONTH_DIR.mkdir(parents=True, exist_ok=True)
    period_path = RAW_BY_MONTH_DIR / (period + ".json")
    
    existing = []
    existing_count = 0
    if period_path.exists():
        try:
            with open(period_path) as f:
                existing = json.load(f)
            existing_count = len(existing)
        except Exception:
            existing = []
            existing_count = 0
    
    new_count = len(txns)
    
    # CRITICAL: Reject if new fetch is smaller (incomplete pagination)
    if new_count < existing_count:
        msg = (f"{period}: REJECTED — fetch incomplete. "
               f"Got {new_count} records vs existing {existing_count}. "
               f"Keeping existing data.")
        return False, msg
    
    # Deduplicate by ID: existing + new, new overwrites if same ID
    tx_by_id = {str(t.get("id", "")): t for t in existing if t.get("id")}
    for t in txns:
        tx_id = str(t.get("id", ""))
        if tx_id:
            tx_by_id[tx_id] = t
    
    merged = list(tx_by_id.values())
    merged.sort(key=lambda t: t.get("date", ""))
    
    _atomic_save_json(merged, period_path)
    
    added = len(merged) - existing_count
    msg = f"{period}: Saved {len(merged)} records ({added} new vs previous {existing_count})"
    return True, msg


    cfg = _load_config()
    return cfg.get("last_sync", {})


# ═══════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════


def validate_fetch_completeness(txns, period):
    """Validate that a fetch is complete by comparing with previous data."""
    period_path = RAW_BY_MONTH_DIR / (period + ".json")
    
    report = {
        "period": period,
        "fetched_count": len(txns),
        "existing_count": 0,
        "new_ids": 0,
        "missing_ids": 0,
        "is_complete": True,
        "warnings": [],
    }
    
    if not period_path.exists():
        return report
    
    try:
        with open(period_path) as f:
            existing = json.load(f)
        report["existing_count"] = len(existing)
        
        existing_ids = set(str(t.get("id", "")) for t in existing)
        new_ids = set(str(t.get("id", "")) for t in txns)
        
        report["new_ids"] = len(new_ids - existing_ids)
        report["missing_ids"] = len(existing_ids - new_ids)
        
        if report["missing_ids"] > 0:
            report["is_complete"] = False
            report["warnings"].append(
                f"{report['missing_ids']} records from previous fetch are missing"
            )
        
        if len(txns) < len(existing):
            report["is_complete"] = False
            report["warnings"].append(
                f"Count dropped: {len(txns)} < {len(existing)}"
            )
            
    except Exception as e:
        report["warnings"].append(f"Could not read existing data: {e}")
    
    return report


def backup_derived_caches():
    """Backup all derived cache files before rebuild.

    Keep only a small number of recent backups so the host does not fill up with
    copied monthly caches.
    """
    import shutil
    from datetime import datetime

    backup_root = CACHE_DIR / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)

    # Prune older backups first to preserve free space.
    keep_latest = 3
    existing_backups = sorted(
        [p for p in backup_root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old_dir in existing_backups[keep_latest:]:
        shutil.rmtree(old_dir, ignore_errors=True)

    backup_dir = backup_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    files_backed = 0
    for f in [DASHBOARD_SUMMARY_PATH, DAILY_SUMMARY_PATH, RS_OUTLET_PATH]:
        if f.exists():
            shutil.copy2(f, backup_dir / f.name)
            files_backed += 1

    if RS_PERIODS_DIR.exists():
        shutil.copytree(RS_PERIODS_DIR, backup_dir / "rs_periods", dirs_exist_ok=True)
        files_backed += 1

    print(f"[BACKUP] {files_backed} items backed up to {backup_dir}")
    return backup_dir


def _stream_json_records(filepath, chunk_size=1000):
    """Stream JSON array records in chunks to avoid OOM.
    Yields lists of records (each chunk is a list)."""
    import json
    import gc
    with open(filepath) as fh:
        data = json.load(fh)
    total = len(data)
    for i in range(0, total, chunk_size):
        yield data[i:i+chunk_size]
        gc.collect()

def _process_file_streaming(filepath, classifier=None, chunk_size=5000):
    """Process a large JSON file using streaming to avoid OOM.
    Returns (rows_list, total_records)."""
    import gc
    
    all_rows = []
    total_records = 0
    
    from services.transaction_classifier import classify_transaction as _ct
    _classifier = classifier or _ct
    for chunk in _stream_json_records(filepath, chunk_size):
        rows = []
        for t in chunk:
            c = _classifier(t)
            tx_date = c["date"]
            if not tx_date:
                continue
            periode = tx_date[:7]
            rows.append({
                "outlet_name": c["outlet_name"],
                "periode": periode,
                "role": c["role"],
                "amount": c["amount"] if c["is_revenue"] else 0.0,
                "sessions": 1 if c["role"] == "session" else 0,
                "unlocks": 1 if c["role"] in ("unlock", "free_unlock", "voucher_unlock") else 0,
                "unlocks_paid": 1 if c["role"] == "unlock" else 0,
                "prints": 1 if c["role"] == "print" else 0,
            })
        all_rows.extend(rows)
        total_records += len(chunk)
        del chunk, rows
        gc.collect()
    
    return all_rows, total_records

def _get_periods_to_rebuild(force_all=False):
    """Get list of periods that need rebuilding.
    If force_all=False, only rebuild periods where raw_by_month file
    is newer than the corresponding derived cache entry."""
    if force_all or not DASHBOARD_SUMMARY_PATH.exists():
        if RAW_BY_MONTH_DIR.exists():
            return sorted([f.stem for f in RAW_BY_MONTH_DIR.glob("*.json")])
        return []
    
    # Check which raw files are newer than dashboard cache
    cache_mtime = DASHBOARD_SUMMARY_PATH.stat().st_mtime
    to_rebuild = []
    
    if RAW_BY_MONTH_DIR.exists():
        for f in RAW_BY_MONTH_DIR.glob("*.json"):
            if f.stat().st_mtime > cache_mtime:
                to_rebuild.append(f.stem)
    
    return sorted(to_rebuild)

def authenticate(force: bool = False) -> Optional[str]:
    """Get a bearer token. Uses stored token if valid, or creates new one."""
    if not force:
        token = get_stored_token()
        if token:
            if _validate_token(token):
                return token

    # Create new token directly via the API token creation endpoint
    # (Does NOT need CSRF/session login first)
    email, password = get_credentials()

    try:
        token_resp = requests.post(
            TOKEN_CREATE_URL,
            json={
                "email": email,
                "password": password,
                "token_name": "dashboard-sync-" + datetime.now().strftime("%Y%m%d"),
            },
            timeout=15,
        )
        if token_resp.status_code != 200:
            return None

        data = token_resp.json()
        token = data.get("token")
        if token:
            save_token(token)
            return token
        return None
    except requests.RequestException:
        return None



def _validate_token(token: str) -> bool:
    """Test if token is still valid by fetching 1 transaction."""
    try:
        resp = requests.post(
            TRANSACTIONS_URL,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"per_page": 1},
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


# ═══════════════════════════════════════════════
#  FETCH
# ═══════════════════════════════════════════════

def fetch_all_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    per_page: int = 100,
    token: Optional[str] = None,
    progress_callback=None,
) -> Tuple[List[dict], str]:
    """Fetch all transactions with cursor pagination.

    Returns (list_of_transactions, status_message).
    """
    if not token:
        token = authenticate()
        if not token:
            return [], "Gagal autentikasi ke difotoin.id"

    all_txns = []
    cursor = None
    page = 0

    while True:
        page += 1
        params = {"per_page": per_page}
        if cursor:
            params["cursor"] = cursor
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        # Build filters
        filters = {
            "status": {"operation": "equal", "value": "done"},
            "payment_status": {"operation": "equal", "value": "paid"},
        }

        try:
            resp = requests.post(
                TRANSACTIONS_URL,
                params=params,
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=filters,
                timeout=30,
            )
            if resp.status_code != 200:
                return all_txns, "HTTP " + str(resp.status_code) + " pada page " + str(page) + ": " + resp.text[:200]

            data = resp.json()
            tx_data = data.get("data", {}).get("transactions", {})
            batch = tx_data.get("data", [])

            if not batch:
                break

            all_txns.extend(batch)
            cursor = tx_data.get("next_cursor")

            if progress_callback:
                progress_callback(page, len(batch), len(all_txns))

            if not cursor:
                break
        except requests.RequestException as e:
            return all_txns, "Error fetch page " + str(page) + ": " + str(e)

    status = "Berhasil fetch " + str(len(all_txns)) + " transaksi (" + str(page) + " halaman)"
    return all_txns, status


# ═══════════════════════════════════════════════
#  AGGREGATE
# ═══════════════════════════════════════════════

def aggregate_transactions(txns: List[dict]) -> pd.DataFrame:
    """Aggregate raw transactions to monthly outlet-level DataFrame."""
    if not txns:
        return pd.DataFrame()

    rows = []
    for t in txns:
        details = t.get("details", []) or []
        capture_qty = 1 if any(int(d.get("capture_qty", 0) or 0) > 0 for d in details) else 0

        print_qty = 1 if t.get("type") == "print" else 0
        unlock_qty_tx = 1
        amount = float(t.get("processed_gross_amount", 0) or 0)

        tx_date = t.get("date", "")
        try:
            dt = pd.to_datetime(tx_date)
            periode = dt.strftime("%Y-%m")
        except Exception:
            periode = datetime.now().strftime("%Y-%m")

        rows.append({
            "outlet_name": str(t.get("outlet_name", "")).strip(),
            "outlet_id": t.get("outlet_id"),
            "periode": periode,
            "total_revenue": amount,
            "foto_qty": capture_qty,
            "unlock_qty": unlock_qty_tx,
            "print_qty": print_qty,
            "partner_share": float(t.get("partner_share", 0) or 0),
            "broker_share": float(t.get("broker_share", 0) or 0),
            "employee_id": t.get("employee_id"),
            "employee_name": t.get("employee_name"),
        })

    df = pd.DataFrame(rows)

    agg = df.groupby(["outlet_name", "periode"], as_index=False).agg(
        total_revenue=("total_revenue", "sum"),
        foto_qty=("foto_qty", "sum"),
        unlock_qty=("unlock_qty", "sum"),
        print_qty=("print_qty", "sum"),
        partner_share=("partner_share", "mean"),
        broker_share=("broker_share", "mean"),
        outlet_id=("outlet_id", "first"),
    )

    agg["paid_per_photo_rate"] = np.where(
        agg["foto_qty"] > 0,
        (agg["unlock_qty"] / agg["foto_qty"] * 100),
        0.0,
    )

    # NOTE: paid_per_photo_rate = paid_transactions / total_captures
    # Ini BUKAN conversion rate sesungguhnya (karena hanya dari data paid/done).
    # Data unpaid/all sessions belum stabil di-fetch dari API.
    # Untuk conversion real, diperlukan fetch data all sessions (termasuk unpaid/cancel).
    agg["outlet_status"] = agg["total_revenue"].apply(
        lambda v: "Keeper" if v >= 15_000_000
        else ("Optimasi" if v >= 8_000_000 else "Relocate")
    )

    _join_outlet_mapping(agg)

    for col in ["area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]:
        if col not in agg.columns:
            agg[col] = ""

    col_order = [
        "outlet_name", "periode", "area", "kategori_tempat",
        "sub_kategori_tempat", "tipe_tempat", "foto_qty", "unlock_qty",
        "print_qty", "total_revenue", "paid_per_photo_rate", "outlet_status",
    ]
    for col in col_order:
        if col not in agg.columns:
            agg[col] = ""
    agg = agg[[c for c in col_order if c in agg.columns]]

    return agg


def _join_outlet_mapping(df: pd.DataFrame):
    """Join area/kategori/tipe from outlet mapping CSV."""
    try:
        mapping = pd.read_csv(OUTLET_MAPPING_PATH, dtype=str)
        mapping["outlet_name"] = mapping["outlet_name"].astype(str).str.strip()

        df["outlet_name"] = df["outlet_name"].astype(str).str.strip()
        merged = df.merge(
            mapping[["outlet_name", "area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]],
            on="outlet_name",
            how="left",
            suffixes=("", "_mapping"),
        )
        for col in ["area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]:
            mapping_col = col + "_mapping"
            if mapping_col in merged.columns:
                merged[col] = merged[col].fillna(merged[mapping_col])
                merged[col] = np.where(
                    (merged[col] == "") & (merged[mapping_col].notna()),
                    merged[mapping_col],
                    merged[col],
                )
                merged.drop(columns=[mapping_col], inplace=True)

        for col in ["outlet_id"]:
            if col in merged.columns:
                merged.drop(columns=[col], inplace=True)

        for col in merged.columns:
            if col in ["outlet_name", "periode"]:
                continue
            if col in df.columns:
                df[col] = merged[col]
            else:
                df[col] = merged[col]
    except (FileNotFoundError, Exception):
        pass


# ═══════════════════════════════════════════════
#  SAVE TO CSV
# ═══════════════════════════════════════════════

def save_to_csv(df: pd.DataFrame) -> Tuple[bool, str]:
    """Save aggregated data to CSV, overwriting by period."""
    if df.empty:
        return False, "Tidak ada data untuk disimpan"

    periods = df["periode"].dropna().unique().tolist() if "periode" in df.columns else []

    try:
        existing = pd.read_csv(DATA_CSV_PATH, dtype=str)
    except (FileNotFoundError, Exception):
        existing = pd.DataFrame()

    if not existing.empty and "total_revenue" in existing.columns:
        float(
            existing["total_revenue"].fillna(0).astype(float).sum()
        )

    if not existing.empty and periods:
        existing = existing[
            ~existing["periode"].astype(str).str.strip().isin(periods)
        ].copy()

    df_str = df.astype(str)

    merged = pd.concat([existing, df_str], ignore_index=True)

    for col in ["total_revenue", "foto_qty", "unlock_qty", "print_qty"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

    DATA_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    _atomic_save_csv(merged, DATA_CSV_PATH)

    after_total = 0.0
    if "total_revenue" in merged.columns:
        after_total = float(merged["total_revenue"].fillna(0).astype(float).sum())

    msg = (
        "Data tersimpan. " + str(len(periods)) + " periode diupdate. "
        "Total CSV: Rp " + str(int(after_total))
    )
    return True, msg


# ═══════════════════════════════════════════════
#  CACHE RAW TRANSACTIONS (for revenue sharing)
# ═══════════════════════════════════════════════

def cache_raw_transactions(txns: List[dict]):
    """Save raw transactions to JSON cache. Merges with existing."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        existing = load_raw_transactions()
        seen_ids = set()
        for t in txns:
            tx_id = t.get("id")
            if tx_id:
                seen_ids.add(str(tx_id))
        # Filter existing: keep only those NOT in current batch (by transaction ID)
        filtered = [t for t in existing if str(t.get("id","")) not in seen_ids]
        merged = filtered + txns
    except Exception:
        merged = txns
    _atomic_save_json(merged, RAW_TXNS_PATH)


def load_raw_transactions() -> List[dict]:
    try:
        with open(RAW_TXNS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ═══════════════════════════════════════════════
#  REVENUE SHARING DATA
# ═══════════════════════════════════════════════

def compute_revenue_sharing(
    txns: Optional[List[dict]] = None
) -> pd.DataFrame:
    """Compute per-outlet-per-month revenue sharing from raw transactions."""
    if txns is None:
        txns = load_raw_transactions()

    if not txns:
        return pd.DataFrame()

    rows = []
    for t in txns:
        amount = float(t.get("processed_gross_amount", 0) or 0)
        partner_share = float(t.get("partner_share", 0) or 0)
        broker_share = float(t.get("broker_share", 0) or 0)

        partner_amount = amount * partner_share / 100
        broker_amount = amount * broker_share / 100
        difotoin_amount = amount - partner_amount - broker_amount

        tx_date = t.get("date", "")
        try:
            dt = pd.to_datetime(tx_date)
            periode = dt.strftime("%Y-%m")
        except Exception:
            periode = datetime.now().strftime("%Y-%m")

        rows.append({
            "id": str(t.get("id", "")),
            "outlet_name": str(t.get("outlet_name", "")).strip(),
            "outlet_id": t.get("outlet_id"),
            "date": tx_date,
            "periode": periode,
            "total_revenue": amount,
            "partner_share_pct": partner_share,
            "broker_share_pct": broker_share,
            "difotoin_share_pct": round(100 - partner_share - broker_share, 1),
            "partner_amount": round(partner_amount, 2),
            "broker_amount": round(broker_amount, 2),
            "difotoin_amount": round(difotoin_amount, 2),
            "employee_name": t.get("employee_name"),
            "payment_type": t.get("payment_type"),
            "pg_platform": t.get("pg_platform"),
            "customer_name": t.get("customer_name"),
        })

    return pd.DataFrame(rows)


RS_OUTLET_PATH = CACHE_DIR / "rs_outlet.json"
RS_PERIODS_DIR = CACHE_DIR / "rs_periods"
RAW_BY_MONTH_DIR = CACHE_DIR / "raw_by_month"


def _cache_revenue_sharing(txns: List[dict], prefer_raw_by_month: bool = True):
    """Pre-compute revenue sharing data and save as lightweight cache.
    Also split raw transactions by period for on-demand detail loading.
    
    When prefer_raw_by_month=True (default), reads from raw_by_month/<period>.json 
    for each period instead of using the passed-in txns. This ensures RS cache
    always uses COMPLETE data, not partial fetch results.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RS_PERIODS_DIR.mkdir(parents=True, exist_ok=True)

    if not txns:
        return

    # Prefer raw_by_month/ data when available (always complete, never partial)
    if prefer_raw_by_month:
        _periods_found = set()
        for t in txns:
            d = t.get("date", "")
            try:
                _dt = pd.to_datetime(d)
                _periods_found.add(_dt.strftime("%Y-%m"))
            except Exception:
                pass
        
        _raw_txns = []
        for _p in sorted(_periods_found):
            _rp = RAW_BY_MONTH_DIR / (_p + ".json")
            if _rp.exists():
                with open(_rp) as _f:
                    _raw_txns.extend(json.load(_f))
        
        if _raw_txns:
            txns = _raw_txns  # Use complete raw_by_month data instead of partial fetch

    # Compute full revenue sharing
    df = compute_revenue_sharing(txns)
    if df.empty:
        return

    # 1. Save per-outlet-per-month aggregated (small) - MERGE with existing
    new_agg = df.groupby(["outlet_name", "periode"], as_index=False).agg(
        total_revenue=("total_revenue", "sum"),
        partner_amount=("partner_amount", "sum"),
        broker_amount=("broker_amount", "sum"),
        difotoin_amount=("difotoin_amount", "sum"),
        transactions=("total_revenue", "count"),
        avg_partner_pct=("partner_share_pct", "mean"),
        avg_broker_pct=("broker_share_pct", "mean"),
    )
    # Load existing cache and merge: update rows for (outlet,period) that exist, add new ones
    try:
        existing = pd.read_json(str(RS_OUTLET_PATH))
        # Remove ALL existing rows for periods we are about to reprocess
        new_periods = set(new_agg["periode"].unique())
        existing = existing[~existing["periode"].isin(new_periods)]
        merged = pd.concat([existing, new_agg], ignore_index=True)
    except (FileNotFoundError, ValueError, Exception):
        merged = new_agg

    _atomic_save_json(merged, RS_OUTLET_PATH)

    # 2. Split raw detail by period — REPLACE each period file (prevent duplicate accumulation)
    periods = df["periode"].dropna().unique().tolist() if "periode" in df.columns else []
    for period in periods:
        period_df = df[df["periode"] == period]
        if period_df.empty:
            continue
        period_path = RS_PERIODS_DIR / (period + ".json")
        # Deduplicate by transaction ID before saving (keep latest)
        if "id" in period_df.columns:
            period_df = period_df.drop_duplicates(subset=["id"], keep="last")
        else:
            period_df = period_df.drop_duplicates(keep="last")
        _atomic_save_json(period_df, period_path)


def load_rs_outlet_summary() -> list:
    """Load lightweight per-outlet-per-month revenue sharing data."""
    try:
        import pandas as pd
        df = pd.read_json(str(RS_OUTLET_PATH))
        return df.to_dict("records") if not df.empty else []
    except (FileNotFoundError, ValueError, Exception):
        return []


def load_rs_period_detail(period: str) -> list:
    """Load detailed transactions for a specific period only."""
    period_path = RS_PERIODS_DIR / (period + ".json")
    try:
        import pandas as pd
        df = pd.read_json(str(period_path))
        return df.to_dict("records") if not df.empty else []
    except (FileNotFoundError, ValueError, Exception):
        return []


def get_rs_periods() -> list:
    """Get sorted list of available periods from cache."""
    if not RS_PERIODS_DIR.exists():
        return []
    periods = [f.stem for f in sorted(RS_PERIODS_DIR.iterdir()) if f.suffix == ".json"]
    return sorted(periods, reverse=True)


# ═══════════════════════════════════════════════
#  SYNC TRACKER — prevent re-fetching same months
# ═══════════════════════════════════════════════

SYNC_TRACKER_PATH = CACHE_DIR / "sync_tracker.json"


def load_sync_tracker() -> dict:
    """Load sync tracker — records which periods have been fetched."""
    try:
        with open(SYNC_TRACKER_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"fetched_periods": [], "failed_periods": [], "last_sync": None}


def save_sync_tracker(tracker: dict):
    """Save sync tracker."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_save_json(tracker, SYNC_TRACKER_PATH)


def get_tracked_periods() -> List[str]:
    """Get sorted list of periods already fetched."""
    tracker = load_sync_tracker()
    return sorted(tracker.get("fetched_periods", []))


def get_csv_periods() -> List[str]:
    """Get sorted list of periods from the CSV data."""
    try:
        df = pd.read_csv(DATA_CSV_PATH)
        if "periode" in df.columns:
            return sorted(df["periode"].dropna().unique().tolist())
    except Exception:
        pass
    return []


def get_missing_periods(target_periods: Optional[List[str]] = None) -> List[str]:
    """Get periods that exist in CSV/target but not yet fetched.
    If target_periods is None, checks CSV periods."""
    if target_periods is None:
        target_periods = get_csv_periods()
    fetched = set(get_tracked_periods())
    return [p for p in target_periods if p not in fetched]


# ═══════════════════════════════════════════════
#  PER-PERIOD FETCH — 1 month at a time, with retry
# ═══════════════════════════════════════════════

def _month_date_range(period: str) -> Tuple[str, str]:
    """Convert 'YYYY-MM' to (start_date, end_date) strings."""
    year, month = int(period[:4]), int(period[5:7])
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def fetch_period(
    period: str,
    per_page: int = 100,
    token: Optional[str] = None,
    max_retries: int = 3,
    update_legacy_raw: bool = False,
) -> Tuple[bool, str]:
    """Fetch ONE specific month (YYYY-MM) from difotoin API, with retry.

    Source of truth for current dashboard sync is raw_by_month/*.json.
    update_legacy_raw defaults False because merging raw_transactions.json loads
    a 600MB+ legacy file and repeatedly OOM-kills CCC cron.
    Returns (success, message)."""
    if not token:
        token = authenticate()
        if not token:
            return False, "Gagal autentikasi"

    start_str, end_str = _month_date_range(period)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            txns, msg = fetch_all_transactions(
                start_date=start_str, end_date=end_str,
                per_page=per_page, token=token,
            )

            # REJECT partial data: if msg contains "Error", data is incomplete
            is_partial = "Error" in msg and txns

            if not txns or is_partial:
                if is_partial:
                    last_error = f"PARTIAL ({len(txns)} txns before error): {msg}"
                else:
                    last_error = msg
                if attempt < max_retries:
                    continue
                break

            # Validate fetch completeness
            validation = validate_fetch_completeness(txns, period)
            if not validation["is_complete"]:
                for w in validation["warnings"]:
                    print(f"  [WARN] {period}: {w}")
            
            # Save to raw_by_month with completeness check
            ok_save, msg_save = save_raw_by_month(txns, period)
            if not ok_save:
                # Incomplete fetch — do not update tracker or caches
                tracker = load_sync_tracker()
                failed = tracker.setdefault('failed_periods', [])
                if period not in failed:
                    failed.append(period)
                save_sync_tracker(tracker)
                return False, msg_save
            
            # Legacy raw_transactions.json is intentionally not updated during
            # normal cron sync; loading/merging it is the OOM hot path on CCC.
            if update_legacy_raw:
                cache_raw_transactions(txns)
            
            # Build revenue sharing cache from raw_by_month (complete data)
            _cache_revenue_sharing(txns)

            # Update tracker
            tracker = load_sync_tracker()
            fetched = tracker.setdefault("fetched_periods", [])
            if period not in fetched:
                fetched.append(period)
                fetched.sort()
            failed = tracker.setdefault("failed_periods", [])
            if period in failed:
                failed.remove(period)
            tracker["last_sync"] = datetime.now().isoformat()
            save_sync_tracker(tracker)

            return True, f"{period}: {msg}"

        except requests.RequestException as e:
            last_error = str(e)
            if attempt < max_retries:
                continue
            break

    # All retries exhausted
    tracker = load_sync_tracker()
    failed = tracker.setdefault("failed_periods", [])
    if period not in failed:
        failed.append(period)
    save_sync_tracker(tracker)

    return False, f"{period}: gagal setelah {max_retries}x percobaan: {last_error}"


def sync_missing_periods(
    max_periods: int = 0,
    per_page: int = 100,
) -> List[str]:
    """Find missing periods from CSV and fetch them one by one.
    Args:
        max_periods: max months to fetch (0 = all missing).
        per_page: transactions per API page.
    Returns list of result messages.
    """
    missing = get_missing_periods()
    if not missing:
        return ["Semua periode sudah tersinkronasi."]

    if max_periods > 0:
        missing = missing[:max_periods]

    results = []
    token = authenticate()
    if not token:
        return ["Gagal autentikasi"]

    for period in missing:
        ok, msg = fetch_period(period, per_page=per_page, token=token)
        results.append(msg)
        if not ok:
            # Stop on first failure — don't hammer the API
            results.append("Berhenti karena kegagalan. Lanjutkan nanti.")
            break

    return results


def sync_current_month(per_page: int = 100) -> Tuple[bool, str]:
    """Cron-friendly: always re-fetch current and previous month.
    Re-fetching is needed to catch status changes (pending -> paid).
    """
    now = datetime.now()
    current = now.strftime("%Y-%m")
    prev = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    # Always fetch current + previous month (ignore tracker for these)
    to_fetch = [prev, current]

    results = []
    token = authenticate()
    if not token:
        return False, "Gagal autentikasi"

    for period in to_fetch:
        ok, msg = fetch_period(period, per_page=per_page, token=token)
        results.append(msg)

    return True, " | ".join(results)


# ── Seed: import sync_tracker periods from existing rs_periods/ ──

# ═══════════════════════════════════════════════
#  DASHBOARD SUMMARY CACHE (from raw_by_month)
# ═══════════════════════════════════════════════

def build_dashboard_from_raw() -> Tuple[bool, str]:
    """Build dashboard summary cache from raw_by_month data with conversion funnel.
    Processes ONE file at a time to avoid OOM on 3.4GB raw data.
    Returns (success, message).
    """
    if not RAW_BY_MONTH_DIR.exists():
        return False, f"raw_by_month dir not found at {RAW_BY_MONTH_DIR}"
    
    import gc
    
    all_agg = []
    period_counts = []
    files_loaded = 0
    files_total = len(list(RAW_BY_MONTH_DIR.glob("*.json")))
    
    for f in sorted(RAW_BY_MONTH_DIR.glob("*.json")):
        try:
            with open(f) as fh:
                txns = json.load(fh)
        except Exception as e:
            print(f"Error loading {f.name}: {e}")
            continue
        
        if not txns:
            continue
        
        classified = classify_transactions(txns)
        
        rows = []
        for c in classified:
            tx_date = c["date"]
            if not tx_date:
                continue
            periode = tx_date[:7]
            
            rows.append({
                "outlet_name": c["outlet_name"],
                "periode": periode,
                "role": c["role"],
                "amount": c["amount"] if c["is_revenue"] else 0.0,
                "sessions": 1 if c["role"] == "session" else 0,
                "unlocks": 1 if c["role"] in ("unlock", "free_unlock", "voucher_unlock") else 0,
                "unlocks_paid": 1 if c["role"] == "unlock" else 0,
                "prints": 1 if c["role"] == "print" else 0,
            })
        
        if rows:
            df = pd.DataFrame(rows)
            agg_month = df.groupby(["outlet_name", "periode"], as_index=False).agg(
                sessions=("sessions", "sum"),
                unlocks=("unlocks", "sum"),
                unlocks_paid=("unlocks_paid", "sum"),
                prints=("prints", "sum"),
                total_revenue=("amount", "sum"),
            )
            all_agg.append(agg_month)
            period_counts.append((f.stem, len(txns)))
            
            del txns, classified, rows, df, agg_month
            gc.collect()
        
        files_loaded += 1
        txns_count = len(txns) if "txns" in dir() else "?"
        print(f"  [{files_loaded}/{files_total}] {f.stem}: {txns_count} txns")
    
    if not all_agg:
        return False, "No transactions found in raw_by_month"
    
    agg = pd.concat(all_agg, ignore_index=True)
    del all_agg
    gc.collect()
    
    agg = agg.groupby(["outlet_name", "periode"], as_index=False).agg(
        sessions=("sessions", "sum"),
        unlocks=("unlocks", "sum"),
        unlocks_paid=("unlocks_paid", "sum"),
        prints=("prints", "sum"),
        total_revenue=("total_revenue", "sum"),
    )
    
    # Conversion rate: unlocks / sessions * 100
    agg["conversion_rate"] = np.where(
        agg["sessions"] > 0,
        (agg["unlocks"] / agg["sessions"] * 100),
        0.0,
    )
    
    # Print rate: prints / unlocks_paid * 100
    agg["print_rate"] = np.where(
        agg["unlocks_paid"] > 0,
        (agg["prints"] / agg["unlocks_paid"] * 100),
        0.0,
    )
    
    # Revenue per session
    agg["revenue_per_session"] = np.where(
        agg["sessions"] > 0,
        agg["total_revenue"] / agg["sessions"],
        0.0,
    )
    
    # Outlet status based on revenue
    agg["outlet_status"] = agg["total_revenue"].apply(
        lambda v: "Keeper" if v >= 15_000_000
        else ("Optimasi" if v >= 8_000_000 else "Relocate")
    )
    
    # Apply outlet mapping for area/kategori/tipe
    _join_outlet_mapping(agg)
    
    # Ensure all expected columns exist
    for col in ["area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]:
        if col not in agg.columns:
            agg[col] = ""
    
    # Save as JSON
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_save_json(agg, DASHBOARD_SUMMARY_PATH)
    
    total_txns = sum(c for _, c in period_counts)
    total_rev = float(agg["total_revenue"].sum())
    total_sessions = int(agg["sessions"].sum())
    total_unlocks = int(agg["unlocks"].sum())
    total_prints = int(agg["prints"].sum())
    msg = f"Dashboard cache: {len(agg)} entries, {total_txns} txns ({files_loaded} files). Sessions={total_sessions}, Unlocks={total_unlocks}, Prints={total_prints}, Revenue=Rp {total_rev:,.0f}"
    return True, msg


def _daily_summary_from_transactions(txns: List[dict]) -> pd.DataFrame:
    """Aggregate raw transactions into daily outlet rows."""
    if not txns:
        return pd.DataFrame()

    classified = classify_transactions(txns)
    rows = []
    for c in classified:
        tx_date = c["date"]
        if not tx_date:
            continue
        rows.append({
            "date": tx_date,
            "outlet_name": c["outlet_name"],
            "revenue": c["amount"] if c["is_revenue"] else 0.0,
            "sessions": 1 if c["role"] == "session" else 0,
            "unlocks": 1 if c["role"] in ("unlock", "free_unlock", "voucher_unlock") else 0,
            "unlocks_paid": 1 if c["role"] == "unlock" else 0,
            "prints": 1 if c["role"] == "print" else 0,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df.groupby(["date", "outlet_name"], as_index=False).agg(
        sessions=("sessions", "sum"),
        unlocks=("unlocks", "sum"),
        unlocks_paid=("unlocks_paid", "sum"),
        prints=("prints", "sum"),
        revenue=("revenue", "sum"),
    )


def _finalize_daily_summary_df(agg: pd.DataFrame) -> pd.DataFrame:
    """Normalize, de-duplicate, and add calculated daily metrics."""
    if agg.empty:
        return agg

    agg["date"] = agg["date"].astype(str).str[:10]
    agg["outlet_name"] = agg["outlet_name"].astype(str).str.strip()
    for col in ["sessions", "unlocks", "unlocks_paid", "prints", "revenue"]:
        if col in agg.columns:
            agg[col] = pd.to_numeric(agg[col], errors="coerce").fillna(0.0)
        else:
            agg[col] = 0.0

    agg = agg.groupby(["date", "outlet_name"], as_index=False).agg(
        sessions=("sessions", "sum"),
        unlocks=("unlocks", "sum"),
        unlocks_paid=("unlocks_paid", "sum"),
        prints=("prints", "sum"),
        revenue=("revenue", "sum"),
    )

    agg["conversion_rate"] = np.where(
        agg["sessions"] > 0,
        (agg["unlocks"] / agg["sessions"] * 100),
        0.0,
    )
    agg["print_rate"] = np.where(
        agg["unlocks_paid"] > 0,
        (agg["prints"] / agg["unlocks_paid"] * 100),
        0.0,
    )
    agg["avg_revenue_per_session"] = np.where(
        agg["sessions"] > 0,
        agg["revenue"] / agg["sessions"],
        0.0,
    )
    return agg.sort_values(["date", "outlet_name"]).reset_index(drop=True)


def build_daily_summary_for_periods(periods: List[str]) -> Tuple[bool, str]:
    """Incrementally rebuild daily summary for selected YYYY-MM periods only.

    Existing rows for other periods are preserved. Target-period rows are removed
    and rebuilt from raw_by_month/<period>.json, then the whole daily summary is
    de-duplicated and atomically saved. This avoids the OOM-prone full-history
    rebuild on CCC.
    """
    if not RAW_BY_MONTH_DIR.exists():
        return False, "raw_by_month dir not found"

    import gc

    periods = sorted({str(p)[:7] for p in periods if p})
    if not periods:
        return True, "No daily periods need rebuilding"

    existing_df = pd.DataFrame()
    if DAILY_SUMMARY_PATH.exists():
        try:
            existing_df = pd.read_json(str(DAILY_SUMMARY_PATH))
            if not existing_df.empty and "date" in existing_df.columns:
                existing_df["date"] = existing_df["date"].astype(str).str[:10]
                existing_df = existing_df[~existing_df["date"].str[:7].isin(periods)]
        except Exception as e:
            print("[WARN] Could not read existing daily summary: {}".format(e))
            existing_df = pd.DataFrame()

    new_aggs = []
    total_txns = 0
    for period in periods:
        f = RAW_BY_MONTH_DIR / (period + ".json")
        if not f.exists():
            print("[WARN] {} missing, skipping daily rebuild".format(f.name))
            continue
        try:
            with open(f) as fh:
                txns = json.load(fh)
        except Exception as e:
            print("Error loading {}: {}".format(f.name, e))
            continue

        total_txns += len(txns)
        agg = _daily_summary_from_transactions(txns)
        if not agg.empty:
            new_aggs.append(agg)
        del txns, agg
        gc.collect()

    if not new_aggs and existing_df.empty:
        return False, "No transactions found"

    pieces = []
    if not existing_df.empty:
        pieces.append(existing_df)
    pieces.extend(new_aggs)

    combined = pd.concat(pieces, ignore_index=True, sort=False) if pieces else pd.DataFrame()
    combined = _finalize_daily_summary_df(combined)
    _atomic_save_json(combined, DAILY_SUMMARY_PATH)

    total_rev = float(combined["revenue"].sum()) if "revenue" in combined.columns else 0.0
    total_days = combined["date"].nunique() if "date" in combined.columns else 0
    total_sessions = int(combined["sessions"].sum()) if "sessions" in combined.columns else 0
    total_unlocks = int(combined["unlocks"].sum()) if "unlocks" in combined.columns else 0
    total_prints = int(combined["prints"].sum()) if "prints" in combined.columns else 0
    msg = "Daily summary incremental: periods={}, entries={}, days={}, txns={}, sessions={}, unlocks={}, prints={}, revenue=Rp {:,.0f}".format(
        ",".join(periods), len(combined), total_days, total_txns,
        total_sessions, total_unlocks, total_prints, total_rev)
    return True, msg


def build_daily_summary() -> Tuple[bool, str]:
    """Build daily sales summary from raw_by_month/ data with conversion funnel.
    Groups by (date, outlet_name) for fast daily queries.
    Updates DAILY_SUMMARY_PATH with pre-aggregated daily data.
    Returns (success, message).
    """
    if not RAW_BY_MONTH_DIR.exists():
        return False, "raw_by_month dir not found"
    
    import gc
    all_agg = []
    
    for f in sorted(RAW_BY_MONTH_DIR.glob("*.json")):
        try:
            with open(f) as fh:
                txns = json.load(fh)
        except Exception as e:
            print("Error loading {}: {}".format(f.name, e))
            continue
        
        if not txns:
            continue
        
        classified = classify_transactions(txns)
        
        rows = []
        for c in classified:
            tx_date = c["date"]
            if not tx_date:
                continue
            
            rows.append({
                "date": tx_date,
                "outlet_name": c["outlet_name"],
                "revenue": c["amount"] if c["is_revenue"] else 0.0,
                "sessions": 1 if c["role"] == "session" else 0,
                "unlocks": 1 if c["role"] in ("unlock", "free_unlock", "voucher_unlock") else 0,
                "unlocks_paid": 1 if c["role"] == "unlock" else 0,
                "prints": 1 if c["role"] == "print" else 0,
            })
        
        if rows:
            df = pd.DataFrame(rows)
            agg = df.groupby(["date", "outlet_name"], as_index=False).agg(
                sessions=("sessions", "sum"),
                unlocks=("unlocks", "sum"),
                unlocks_paid=("unlocks_paid", "sum"),
                prints=("prints", "sum"),
                revenue=("revenue", "sum"),
            )
            all_agg.append(agg)
        
        del txns, classified, rows, df, agg
        gc.collect()
    
    if not all_agg:
        return False, "No transactions found"
    
    agg = pd.concat(all_agg, ignore_index=True)
    agg = agg.groupby(["date", "outlet_name"], as_index=False).agg(
        sessions=("sessions", "sum"),
        unlocks=("unlocks", "sum"),
        unlocks_paid=("unlocks_paid", "sum"),
        prints=("prints", "sum"),
        revenue=("revenue", "sum"),
    )
    
    # Conversion rates
    agg["conversion_rate"] = np.where(
        agg["sessions"] > 0,
        (agg["unlocks"] / agg["sessions"] * 100),
        0.0,
    )
    
    agg["print_rate"] = np.where(
        agg["unlocks_paid"] > 0,
        (agg["prints"] / agg["unlocks_paid"] * 100),
        0.0,
    )
    
    agg["avg_revenue_per_session"] = np.where(
        agg["sessions"] > 0,
        agg["revenue"] / agg["sessions"],
        0.0,
    )
    
    _atomic_save_json(agg, DAILY_SUMMARY_PATH)
    total_rev = float(agg["revenue"].sum())
    total_days = agg["date"].nunique()
    total_sessions = int(agg["sessions"].sum())
    total_unlocks = int(agg["unlocks"].sum())
    total_prints = int(agg["prints"].sum())
    msg = "Daily summary: {} entries, {} days, sessions={}, unlocks={}, prints={}, revenue=Rp {:,.0f}".format(
        len(agg), total_days, total_sessions, total_unlocks, total_prints, total_rev)
    return True, msg


def _cache_dashboard_summary(txns: List[dict], files_loaded: int = 0) -> Tuple[bool, str]:
    """Aggregate raw transactions into dashboard format (with qty fields).
    
    Produces dashboard_summary.json for the Dashboard page.
    Does NOT affect rs_outlet.json or rs_periods/ (revenue sharing).
    """
    if not txns:
        return False, "No transactions to aggregate"
    
    rows = []
    for t in txns:
        details = t.get("details", []) or []
        capture_qty = 1 if any(int(d.get("capture_qty", 0) or 0) > 0 for d in details) else 0

        print_qty = 1 if t.get("type") == "print" else 0
        unlock_qty = sum(int(d.get("unlocked_photo", 0) or 0) for d in details)
        amount = float(t.get("processed_gross_amount", 0) or 0)
        
        tx_date = t.get("date", "")
        try:
            dt = pd.to_datetime(tx_date)
            periode = dt.strftime("%Y-%m")
        except Exception:
            continue
        
        rows.append({
            "outlet_name": str(t.get("outlet_name", "")).strip(),
            "outlet_id": t.get("outlet_id"),
            "periode": periode,
            "total_revenue": amount,
            "foto_qty": capture_qty,
            "unlock_qty": unlock_qty,
            "print_qty": print_qty,
        })
    
    if not rows:
        return False, "No valid rows after parsing"
    
    df = pd.DataFrame(rows)
    
    agg = df.groupby(["outlet_name", "periode"], as_index=False).agg(
        total_revenue=("total_revenue", "sum"),
        foto_qty=("foto_qty", "sum"),
        unlock_qty=("unlock_qty", "sum"),
        print_qty=("print_qty", "sum"),
        outlet_id=("outlet_id", "first"),
    )
    
    # Conversion rate: unlock / foto * 100
    agg["paid_per_photo_rate"] = np.where(
        agg["foto_qty"] > 0,
        (agg["unlock_qty"] / agg["foto_qty"] * 100),
        0.0,
    )
    
    # unlock_to_print_rate
    agg["unlock_to_print_rate"] = np.where(
        agg["unlock_qty"] > 0,
        (agg["print_qty"] / agg["unlock_qty"] * 100),
        0.0,
    )
    
    # Outlet status based on revenue
    agg["outlet_status"] = agg["total_revenue"].apply(
        lambda v: "Keeper" if v >= 15_000_000
        else ("Optimasi" if v >= 8_000_000 else "Relocate")
    )
    
    # Apply outlet mapping for area/kategori/tipe
    _join_outlet_mapping(agg)
    
    # Ensure all expected columns exist
    for col in ["area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]:
        if col not in agg.columns:
            agg[col] = ""
    
    # Save as JSON
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_save_json(agg, DASHBOARD_SUMMARY_PATH)
    
    total_rev = float(agg["total_revenue"].sum())
    msg = f"Dashboard cache: {len(agg)} entries dari {len(txns)} transaksi ({files_loaded} files). Total: Rp {total_rev:,.0f}"
    return True, msg



def load_dashboard_summary() -> list:
    """Load the dashboard summary cache with backward compatibility."""
    try:
        if not DASHBOARD_SUMMARY_PATH.exists():
            return []
        df = pd.read_json(str(DASHBOARD_SUMMARY_PATH))
        records = df.to_dict("records") if not df.empty else []
        keeper_min, optimasi_min = _load_status_thresholds()
        for r in records:
            try:
                revenue = float(r.get("total_revenue", 0) or 0)
                if revenue >= keeper_min:
                    r["outlet_status"] = "Keeper"
                elif revenue >= optimasi_min:
                    r["outlet_status"] = "Optimasi"
                else:
                    r["outlet_status"] = "Relocate"
            except Exception:
                r["outlet_status"] = r.get("outlet_status", "")
        # Normalize old/new column names
        for r in records:
            if "sessions" in r and "foto_qty" not in r:
                r["foto_qty"] = r["sessions"]
            if "unlocks" in r and "unlock_qty" not in r:
                r["unlock_qty"] = r["unlocks"]
            if "prints" in r and "print_qty" not in r:
                r["print_qty"] = r["prints"]
            if "conversion_rate" in r and "paid_per_photo_rate" not in r:
                r["paid_per_photo_rate"] = r["conversion_rate"]
            if "print_rate" in r and "unlock_to_print_rate" not in r:
                r["unlock_to_print_rate"] = r["print_rate"]
            # Reverse mapping
            if "foto_qty" in r and "sessions" not in r:
                r["sessions"] = r["foto_qty"]
            if "unlock_qty" in r and "unlocks" not in r:
                r["unlocks"] = r["unlock_qty"]
            if "print_qty" in r and "prints" not in r:
                r["prints"] = r["print_qty"]
            if "paid_per_photo_rate" in r and "conversion_rate" not in r:
                r["conversion_rate"] = r["paid_per_photo_rate"]
            if "unlock_to_print_rate" in r and "print_rate" not in r:
                r["print_rate"] = r["unlock_to_print_rate"]
        return records
    except Exception:
        return []

def rebuild_rs_period(period: str) -> Tuple[bool, str]:
    """Rebuild RS cache for a single period from raw_by_month data.
    Reads raw_by_month/<period>.json and replaces rs cache entries.
    Returns (success, message).
    """
    period_path = Path(str(RAW_BY_MONTH_DIR)) / (period + ".json")
    if not period_path.exists():
        return False, f"{period}: raw_by_month file not found"
    
    try:
        with open(period_path) as f:
            txns = json.load(f)
    except Exception as e:
        return False, f"{period}: error reading raw_by_month: {e}"
    
    if not txns:
        return False, f"{period}: empty data"
    
    # Compute RS from raw_by_month data
    df = compute_revenue_sharing(txns)
    if df.empty:
        return False, f"{period}: no valid RS data"
    
    # Pass RAW txns directly to _cache_revenue_sharing
    _cache_revenue_sharing(txns, prefer_raw_by_month=False)
    return True, f"{period}: RS rebuilt ({len(txns)} txns)"



def rebuild_all_from_raw() -> Tuple[bool, str]:
    """Rebuild ALL derived caches from raw_by_month/ data.
    Runs build_dashboard_from_raw() + rebuild RS for all periods.
    This is the single-source-of-truth rebuild function.
    """
    # Backup existing caches first
    backup_derived_caches()
    results = []
    
    # 1. Rebuild dashboard
    ok_d, msg_d = build_dashboard_from_raw()
    results.append(msg_d)
    
    # 2. Also rebuild daily summary
    results.append("Building daily summary...")
    ok_daily, msg_daily = build_daily_summary()
    results.append("  " + msg_daily)
    
    # 3. Rebuild RS for all periods
    if RAW_BY_MONTH_DIR.exists():
        for f in sorted(RAW_BY_MONTH_DIR.glob("*.json")):
            period = f.stem
            try:
                with open(f) as fh:
                    txns = json.load(fh)
                if not txns:
                    continue
                df = compute_revenue_sharing(txns)
                if df.empty:
                    continue
                _cache_revenue_sharing(txns, prefer_raw_by_month=False)
                results.append(f"  {period}: RS rebuilt ({len(txns)} txns)")
            except Exception as e:
                results.append(f"  {period}: ERROR: {e}")
    
    return True, "\n".join(results)



def seed_tracker_from_cache():
    """One-time: populate tracker with periods already in RS cache."""
    tracker = load_sync_tracker()
    fetched = set(tracker.get("fetched_periods", []))

    try:
        if RS_PERIODS_DIR.exists():
            existing = [f.stem for f in sorted(RS_PERIODS_DIR.iterdir()) if f.suffix == ".json"]
            added = [p for p in existing if p not in fetched]
            if added:
                tracker["fetched_periods"] = sorted(fetched | set(added))
                save_sync_tracker(tracker)
                print(f"Tracker seeded: {len(added)} periods added from cache ({', '.join(added)})")
            else:
                print("Tracker already up-to-date.")
    except Exception as e:
        print(f"Seed error: {e}")



# ═══════════════════════════════════════════════
#  MAIN SYNC
# ═══════════════════════════════════════════════


def run_sync(
    months_back: int = 12,
    per_page: int = 100,
    progress_callback=None,
) -> Tuple[bool, str]:
    """Main sync function: auth -> fetch -> aggregate -> save.

    Returns (success, message).
    """
    end = date.today()
    start = end - timedelta(days=months_back * 30)

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    try:
        token = authenticate()
        if not token:
            save_last_sync(False, "Gagal autentikasi")
            return False, "Gagal autentikasi ke difotoin.id"

        txns, fetch_msg = fetch_all_transactions(
            start_date=start_str,
            end_date=end_str,
            per_page=per_page,
            token=token,
            progress_callback=progress_callback,
        )

        if not txns:
            save_last_sync(False, fetch_msg)
            return False, fetch_msg

        cache_raw_transactions(txns)

        # Pre-compute & cache revenue sharing data (so page doesn't load 92MB raw)
        _cache_revenue_sharing(txns)

        df = aggregate_transactions(txns)

        ok, save_msg = save_to_csv(df)

        msg = fetch_msg + ". " + save_msg
        save_last_sync(ok, msg)
        return ok, msg

    except Exception as e:
        save_last_sync(False, "Error: " + str(e))
        return False, "Sync gagal: " + str(e)


def rebuild_all_from_raw_safe(force_all=False, max_files_per_batch=5) -> Tuple[bool, str]:
    """Memory-safe rebuild with batching and incremental support.
    
    Args:
        force_all: If True, rebuild all periods. If False, only rebuild changed periods.
        max_files_per_batch: Process at most N files before saving intermediate results.
    
    Returns:
        (success, message)
    """
    import gc
    
    # Backup existing caches
    backup_derived_caches()
    
    periods = _get_periods_to_rebuild(force_all=force_all)
    if not periods:
        return True, "No periods need rebuilding (all up to date)"
    
    print(f"[REBUILD] Processing {len(periods)} periods (batch size: {max_files_per_batch})")
    
    all_agg = []
    total_txns = 0
    files_processed = 0
    
    for period in periods:
        filepath = RAW_BY_MONTH_DIR / (period + ".json")
        if not filepath.exists():
            continue
        
        try:
            # Use streaming for large files (>100MB)
            file_size = filepath.stat().st_size
            if file_size > 100 * 1024 * 1024:  # 100MB
                print(f"  [{period}] Using streaming parser ({file_size/1024/1024:.0f}MB)")
                rows, n_txns = _process_file_streaming(str(filepath), chunk_size=5000)
            else:
                with open(filepath) as fh:
                    txns = json.load(fh)
                n_txns = len(txns)
                classified = classify_transactions(txns)
                rows = []
                for c in classified:
                    tx_date = c["date"]
                    if not tx_date:
                        continue
                    periode = tx_date[:7]
                    rows.append({
                        "outlet_name": c["outlet_name"],
                        "periode": periode,
                        "role": c["role"],
                        "amount": c["amount"] if c["is_revenue"] else 0.0,
                        "sessions": 1 if c["role"] == "session" else 0,
                        "unlocks": 1 if c["role"] in ("unlock", "free_unlock", "voucher_unlock") else 0,
                        "unlocks_paid": 1 if c["role"] == "unlock" else 0,
                        "prints": 1 if c["role"] == "print" else 0,
                    })
                del txns, classified
            
            if rows:
                df = pd.DataFrame(rows)
                agg = df.groupby(["outlet_name", "periode"], as_index=False).agg(
                    sessions=("sessions", "sum"),
                    unlocks=("unlocks", "sum"),
                    unlocks_paid=("unlocks_paid", "sum"),
                    prints=("prints", "sum"),
                    total_revenue=("amount", "sum"),
                )
                all_agg.append(agg)
                total_txns += n_txns
                files_processed += 1
                print(f"  [{period}] {n_txns} txns -> {len(agg)} outlets")
            
            del rows
            gc.collect()
            
            # Save intermediate results every N files to free memory
            if files_processed % max_files_per_batch == 0 and all_agg:
                print(f"  [BATCH SAVE] Saving {files_processed} files...")
                combined = pd.concat(all_agg, ignore_index=True)
                # Save to temp
                temp_path = CACHE_DIR / "_dashboard_summary_temp.json"
                _atomic_save_json(combined, temp_path)
                del combined
                gc.collect()
            
        except Exception as e:
            print(f"  ERROR processing {period}: {e}")
            continue
    
    if not all_agg:
        return False, "No data to rebuild"
    
    # Final aggregation
    print("[FINAL] Combining all periods...")

    existing_df = pd.DataFrame()
    if not force_all and DASHBOARD_SUMMARY_PATH.exists():
        try:
            existing_df = pd.read_json(str(DASHBOARD_SUMMARY_PATH))
            if not existing_df.empty and "periode" in existing_df.columns:
                existing_df["periode"] = existing_df["periode"].astype(str)
                existing_df = existing_df[~existing_df["periode"].isin(periods)]
        except Exception as e:
            print(f"[WARN] Could not load existing dashboard summary: {e}")
            existing_df = pd.DataFrame()

    new_df = pd.concat(all_agg, ignore_index=True)
    merged = pd.concat([existing_df, new_df], ignore_index=True, sort=False)

    if merged.empty:
        return False, "No data to rebuild"

    merged["outlet_name"] = merged["outlet_name"].astype(str)
    merged["periode"] = merged["periode"].astype(str)
    for col in ["sessions", "unlocks", "unlocks_paid", "prints", "total_revenue"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)

    # Re-aggregate after merging to guarantee one row per outlet+periode
    agg_dict = {
        "sessions": ("sessions", "sum"),
        "unlocks": ("unlocks", "sum"),
        "unlocks_paid": ("unlocks_paid", "sum"),
        "prints": ("prints", "sum"),
        "total_revenue": ("total_revenue", "sum"),
    }
    for col in ["area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat", "outlet_status"]:
        if col in merged.columns:
            agg_dict[col] = (col, "first")
    merged = merged.groupby(["outlet_name", "periode"], as_index=False).agg(**agg_dict)

    # Calculate rates
    merged["conversion_rate"] = merged.apply(
        lambda r: round((r["unlocks"] / r["sessions"]) * 100, 2) if r["sessions"] > 0 else 0.0,
        axis=1,
    )
    merged["print_rate"] = merged.apply(
        lambda r: round((r["prints"] / r["unlocks"]) * 100, 2) if r["unlocks"] > 0 else 0.0,
        axis=1,
    )
    merged["revenue_per_session"] = merged.apply(
        lambda r: round(r["total_revenue"] / r["sessions"], 0) if r["sessions"] > 0 else 0.0,
        axis=1,
    )

    # Join outlet mapping
    _join_outlet_mapping(merged)

    # Add outlet_status (revenue > 0 = Optimasi, else = Keeper/Tidak Aktif)
    merged["outlet_status"] = merged["total_revenue"].apply(
        lambda x: "Optimasi" if float(x or 0) > 0 else "Keeper"
    )

    # Save final
    _atomic_save_json(merged, DASHBOARD_SUMMARY_PATH)

    summary_msg = (
        f"Dashboard cache: {len(merged)} entries, {total_txns} txns ({files_processed} files). "
        f"Sessions={int(merged['sessions'].sum())}, Unlocks={int(merged['unlocks'].sum())}, "
        f"Prints={int(merged['prints'].sum())}, Revenue=Rp {int(merged['total_revenue'].sum()):,}"
    )
    print(f"[DONE] {summary_msg}")
    
    # Also rebuild daily summary. In incremental mode, only rebuild changed
    # periods; full-history daily rebuild is reserved for explicit force_all=True.
    if force_all:
        print("[DAILY] Rebuilding full daily summary...")
        ok_d, msg_d = build_daily_summary()
    else:
        print("[DAILY] Rebuilding daily summary for changed periods...")
        ok_d, msg_d = build_daily_summary_for_periods(periods)
    
    return ok_d, summary_msg + " | Daily: " + msg_d

