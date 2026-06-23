"""
ERPNext adapter for NiceGUI — wraps the streamlit_template/services/erpnext.py
and provides clean data access functions for dashboard pages.

Reads from cache files (already synced by Streamlit) for speed,
with optional fresh-fetch fallback.
"""
import sys
import json
from pathlib import Path

import pandas as pd
import importlib.util
STREAMLIT_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"

# Add to sys.path so we can import erpnext directly
if str(STREAMLIT_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_DIR))

DATA_DIR = STREAMLIT_DIR / "data"
LP_CACHE_PATH = DATA_DIR / "lead_partnership_cache.json"
LK_CACHE_PATH = DATA_DIR / "lead_kemitraan_cache.json"
OUTLET_MAPPING_PATH = DATA_DIR / "difotoin_outlet_mapping.csv"


def load_lp_data() -> pd.DataFrame:
    """Load Lead Partnership data from cache."""
    try:
        if not LP_CACHE_PATH.exists():
            return pd.DataFrame()
        with open(LP_CACHE_PATH, "r", encoding="utf-8") as f:
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


def load_lk_data() -> pd.DataFrame:
    """Load Lead Kemitraan data from cache."""
    try:
        if not LK_CACHE_PATH.exists():
            return pd.DataFrame()
        with open(LK_CACHE_PATH, "r", encoding="utf-8") as f:
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


def load_outlet_mapping() -> pd.DataFrame:
    """Load outlet mapping CSV data."""
    try:
        if not OUTLET_MAPPING_PATH.exists():
            return pd.DataFrame()
        return pd.read_csv(OUTLET_MAPPING_PATH)
    except Exception:
        return pd.DataFrame()


def filter_by_staff(df: pd.DataFrame, user_email: str, user_name: str) -> pd.DataFrame:
    """Filter leads DataFrame to only show records assigned to this staff member.

    Matches against sales_pic (name or email), sales_pic_full (name),
    and lead_owner (email). Returns empty DataFrame for non-staff roles
    (admin/manager see all data — this function should only be called for staff).

    If no matches found, returns DataFrame with zero rows (not original df).
    """
    if df.empty:
        return df

    email_lower = (user_email or "").strip().lower()
    name_lower = (user_name or "").strip().lower()
    # Normalize whitespace — collapse multiple spaces (e.g. "Suci  Lestari" -> "suci lestari")
    name_normalized = " ".join(name_lower.split())
    email_normalized = " ".join(email_lower.split())

    if not email_lower and not name_lower:
        return pd.DataFrame()  # Not logged in — show nothing

    # Build match mask — try all known assignment fields
    mask = pd.Series(False, index=df.index)
    query = None

    # Helper: collapse multiple spaces in string series
    def _norm(sr):
        return sr.str.strip().str.lower().str.replace(r"\s+", " ", regex=True)

    # sales_pic: may contain employee ID (HR-EMP-xxx), full name, or email
    if "sales_pic" in df.columns:
        sp = _norm(df["sales_pic"])
        if email_normalized:
            query = (sp == email_normalized)
        if name_normalized and (query is None or not query.any()):
            query = (sp == name_normalized)
        if query is not None:
            mask = mask | query

    # sales_pic_full: usually the full name
    if "sales_pic_full" in df.columns and (query is None or not query.any()):
        spf = _norm(df["sales_pic_full"])
        if name_normalized:
            query = (spf == name_normalized)
            if query.any():
                mask = mask | query

    # lead_owner: usually an email
    if "lead_owner" in df.columns and (query is None or not query.any()):
        lo = _norm(df["lead_owner"])
        if email_normalized:
            query = (lo == email_normalized)
            if query.any():
                mask = mask | query

    return df[mask].copy()


def get_cache_info() -> dict:
    """Get sync info for both caches."""
    info = {}
    for name, path in [("lead_partnership", LP_CACHE_PATH), ("lead_kemitraan", LK_CACHE_PATH)]:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                info[name] = {
                    "last_sync": cache.get("last_sync", "N/A"),
                    "count": len(cache.get("records", [])),
                }
            else:
                info[name] = {"last_sync": None, "count": 0}
        except Exception:
            info[name] = {"last_sync": None, "count": 0}
    return info


def compute_dashboard_stats(lp_df: pd.DataFrame, lk_df: pd.DataFrame) -> dict:
    """Compute summary stats for the main dashboard."""
    outlet_df = load_outlet_mapping()

    total_lp = len(lp_df)
    total_lk = len(lk_df)
    total_outlet = len(outlet_df) if not outlet_df.empty else 0

    # Count unique sales PICs from Lead Partnership
    pic_count = 0
    if "sales_pic" in lp_df.columns:
        pic_count = int(lp_df["sales_pic"].dropna().nunique())
    if pic_count == 0 and "sales_pic_full" in lp_df.columns:
        pic_count = int(lp_df["sales_pic_full"].dropna().nunique())

    # Lead per month (from LP creation date, group by month)
    monthly_lp = {}
    if "creation" in lp_df.columns and not lp_df.empty:
        lp_monthly = lp_df["creation"].dropna().dt.to_period("M").value_counts().sort_index()
        monthly_lp = {str(k): int(v) for k, v in lp_monthly.items()}

    monthly_lk = {}
    if "creation" in lk_df.columns and not lk_df.empty:
        lk_monthly = lk_df["creation"].dropna().dt.to_period("M").value_counts().sort_index()
        monthly_lk = {str(k): int(v) for k, v in lk_monthly.items()}

    # Merge months
    all_months = sorted(set(list(monthly_lp.keys()) + list(monthly_lk.keys())))
    merged = []
    for m in all_months:
        merged.append({
            "month": m,
            "partnership": monthly_lp.get(m, 0),
            "kemitraan": monthly_lk.get(m, 0),
        })

    # Latest 10 Lead Partnership
    latest_lp = pd.DataFrame()
    if not lp_df.empty and "creation" in lp_df.columns:
        latest_lp = lp_df.sort_values("creation", ascending=False).head(10)

    # Latest 10 Lead Kemitraan
    latest_lk = pd.DataFrame()
    if not lk_df.empty and "creation" in lk_df.columns:
        latest_lk = lk_df.sort_values("creation", ascending=False).head(10)

    # Status distribution
    status_lp = {}
    if "status_lead" in lp_df.columns:
        status_lp = lp_df["status_lead"].fillna("Unknown").value_counts().to_dict()

    status_lk = {}
    if "status_lead" in lk_df.columns:
        status_lk = lk_df["status_lead"].fillna("Unknown").value_counts().to_dict()

    return {
        "total_lp": total_lp,
        "total_lk": total_lk,
        "total_outlet": total_outlet,
        "total_pic": pic_count,
        "monthly_leads": merged,
        "latest_lp": latest_lp,
        "latest_lk": latest_lk,
        "status_lp": status_lp,
        "status_lk": status_lk,
    }


# ═══════════════════════════════════════════════
#  Lead Permanen helpers (wraps streamlit's services/erpnext.py)
# ═══════════════════════════════════════════════

def _load_erpnext_module():
    """Load streamlit_template's services/erpnext.py module dynamically to avoid namespace collision."""
    module_path = STREAMLIT_DIR / "services" / "erpnext.py"
    if not module_path.exists():
        raise ImportError(f"streamlit erpnext module not found: {module_path}")

    spec = importlib.util.spec_from_file_location("streamlit_erpnext", str(module_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_lead_permanen_config() -> dict:
    """Load ERPNext config for Lead Permanen."""
    mod = _load_erpnext_module()
    return mod.load_erpnext_config()


def save_lead_permanen_config(cfg: dict):
    """Save ERPNext config for Lead Permanen."""
    mod = _load_erpnext_module()
    mod.save_erpnext_config(cfg)


def check_lead_connection() -> tuple:
    """Check ERPNext connection for Lead doctype."""
    mod = _load_erpnext_module()
    return mod.check_connection(doctype="Lead")


def fetch_lead_permanen_data(limit: int = 5000) -> pd.DataFrame:
    """Fetch leads from ERPNext."""
    mod = _load_erpnext_module()
    return mod.fetch_leads(limit=limit)


def aggregate_lead_data(df: pd.DataFrame) -> dict:
    """Aggregate lead data for global summary."""
    mod = _load_erpnext_module()
    return mod.aggregate_lead_data(df)


def aggregate_team_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate team performance data."""
    mod = _load_erpnext_module()
    return mod.aggregate_team_performance(df)


def get_lead_field_display_names() -> dict:
    """Get field display names mapping."""
    mod = _load_erpnext_module()
    return getattr(mod, "FIELD_DISPLAY_NAMES", {})
