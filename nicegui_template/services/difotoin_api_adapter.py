"""
Difotoin.id API Adapter — auth, fetch transactions, aggregate, cache.
"""
import json
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List, Tuple

import requests
import pandas as pd
import numpy as np

# ── Paths ──
ST_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
CONFIG_DIR = ST_DIR / "config"
API_CONFIG_PATH = CONFIG_DIR / "difotoin_api_config.json"
DATA_CSV_PATH = ST_DIR / "data" / "difotoin_dashboard_data.csv"
OUTLET_MAPPING_PATH = ST_DIR / "data" / "difotoin_outlet_mapping.csv"
CACHE_DIR = ST_DIR / "data" / "api_cache"
RAW_TXNS_PATH = CACHE_DIR / "raw_transactions.json"

# ── API Endpoints ──
BASE_URL = "https://difotoin.id"
LOGIN_URL = BASE_URL + "/login"
CSRF_URL = BASE_URL + "/sanctum/csrf-cookie"
TOKEN_CREATE_URL = BASE_URL + "/api/tokens/create"
TRANSACTIONS_URL = BASE_URL + "/api/transactions"

# ── Default Account ──
DEFAULT_EMAIL = "dataanalyst@difotoin.id"
DEFAULT_PASSWORD = "1125toki"


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
    with open(API_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_credentials() -> tuple:
    """Return (email, password)."""
    cfg = _load_config()
    return (
        cfg.get("email", DEFAULT_EMAIL),
        cfg.get("password", DEFAULT_PASSWORD),
    )


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


# ═══════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════

def authenticate(force: bool = False) -> Optional[str]:
    """Get a bearer token. Uses stored token if valid, or creates new one."""
    if not force:
        token = get_stored_token()
        if token:
            if _validate_token(token):
                return token

    # Create new token via session login
    email, password = get_credentials()
    session = requests.Session()

    try:
        # Step 1: Get CSRF cookie
        session.get(CSRF_URL, timeout=15)

        # Step 2: Login
        login_resp = session.post(
            LOGIN_URL,
            json={"email": email, "password": password},
            timeout=15,
        )
        if login_resp.status_code != 200:
            return None

        # Step 3: Create API token
        token_resp = session.post(
            TOKEN_CREATE_URL,
            json={
                "email": email,
                "password": password,
                "token_name": "dashboard-sync-" + datetime.now().strftime("%Y%m%d"),
            },
            timeout=15,
        )
        data = token_resp.json()
        token = data.get("token")
        if token:
            save_token(token)
            return token
        return None
    except requests.RequestException:
        return None
    finally:
        session.close()


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

        # Build filters
        filters = {
            "status": {"operation": "equal", "value": "done"},
            "payment_status": {"operation": "equal", "value": "paid"},
        }
        if start_date and end_date:
            filters["date"] = {"operation": "between", "value": [start_date, end_date]}
        elif start_date:
            filters["date"] = {"operation": "greater than equal", "value": start_date}

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
        capture_qty = sum(int(d.get("capture_qty", 0) or 0) for d in details)
        print_qty = sum(int(d.get("print_qty", 0) or 0) for d in details)
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

    agg["conversion_rate"] = np.where(
        agg["foto_qty"] > 0,
        (agg["unlock_qty"] / agg["foto_qty"] * 100),
        0.0,
    )

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
        "print_qty", "total_revenue", "conversion_rate", "outlet_status",
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
    merged.to_csv(DATA_CSV_PATH, index=False)

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
    """Save raw transactions to JSON cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_TXNS_PATH, "w") as f:
        json.dump(txns, f, indent=2, default=str)


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

        df = aggregate_transactions(txns)

        ok, save_msg = save_to_csv(df)

        msg = fetch_msg + ". " + save_msg
        save_last_sync(ok, msg)
        return ok, msg

    except Exception as e:
        save_last_sync(False, "Error: " + str(e))
        return False, "Sync gagal: " + str(e)
