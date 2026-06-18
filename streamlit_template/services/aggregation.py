"""Data aggregation and helper services for Difotoin Dashboard.

Contains column mapping, data normalization, aggregation, and
period-management helpers extracted from app.py.
"""

import re
import os
from typing import List, Tuple, Dict, Optional

import pandas as pd
import numpy as np

from config import Config

# ================= TYPE DETECTION RE =================

FOTO_RE = re.compile(r"\b(foto|photo|photos|capture|shoot)\b", re.I)
UNLOCK_RE = re.compile(r"\b(unlock|qr|scan)\b", re.I)
PRINT_RE = re.compile(r"\b(print|printed|cetak|printout|print-out)\b", re.I)

# ================= COLUMN MAPPING =================

EXCEL_TO_APP_COLMAP = {
    "outlet": "outlet_name", "nama outlet": "outlet_name", "outlet name": "outlet_name", "toko": "outlet_name",
    "harga": "harga", "amount": "harga", "price": "harga", "nominal": "harga", "omset": "harga",
    "tanggal": "tanggal", "date": "tanggal", "waktu": "tanggal", "created at": "tanggal",
    "area": "area", "kota": "area", "city": "area",
    "type": "type", "tipe": "type", "jenis": "type", "event": "type",
}


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [" ".join(str(c).strip().split()) for c in df.columns]
    return df


def apply_column_mapping_auto(df: pd.DataFrame) -> dict:
    lower_map = {k.lower(): v for k, v in EXCEL_TO_APP_COLMAP.items()}
    used = {}
    for col in df.columns:
        k = col.lower()
        if k in lower_map and lower_map[k] not in used:
            used[lower_map[k]] = col
    return used


def to_numeric_clean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0)
    s = series.astype(str).str.strip()
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    s = s.str.replace(r"\.0+$", "", regex=True)
    s = s.str.replace(r"[^\d\-,\.]", "", regex=True)
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


# ================= EXCEL UTILITIES =================

def excel_engine_from_filename(filename: str) -> str:
    ext = os.path.splitext(str(filename).lower())[1]
    if ext == ".xlsx":
        return "openpyxl"
    if ext == ".xls":
        return "xlrd"
    raise ValueError(f"Format file '{ext}' tidak didukung. Gunakan .xlsx atau .xls.")


def suggest_default_sheets(sheet_names: List[str]) -> List[str]:
    picks = [s for s in sheet_names if any(k in s.lower() for k in ["data", "transaksi", "raw", "detail"])]
    return picks or sheet_names[:1]


def read_selected_sheets(file_bytes: bytes, selected_sheets: List[str], engine: str) -> pd.DataFrame:
    import io
    buf = io.BytesIO(file_bytes)
    xls = pd.ExcelFile(buf, engine=engine)
    frames = []
    for name in selected_sheets:
        df = pd.read_excel(xls, sheet_name=name, engine=engine)
        if df is None or df.empty:
            continue
        frames.append(normalize_headers(df))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def deduplicate_rows(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    df = df.copy()
    subset = [c for c in ["outlet_name", "tanggal", "harga", "type"] if c in df.columns] or [c for c in ["outlet_name", "harga"] if c in df.columns]
    before_rows = len(df)
    before_sum = df["harga"].sum() if "harga" in df.columns else 0.0
    df = df.drop_duplicates(subset=subset, keep="first")
    after_rows = len(df)
    after_sum = df["harga"].sum() if "harga" in df.columns else 0.0
    audit = {
        "subset": subset, "rows_before": before_rows, "rows_after": after_rows,
        "dup_removed": before_rows - after_rows, "sum_before": float(before_sum),
        "sum_after": float(after_sum), "sum_diff": float(after_sum - before_sum),
    }
    return df, audit


# ================= STATUS & AGGREGATION =================

def compute_status(total_revenue: float, config: Config) -> str:
    keep = config.get_threshold('keeper_minimum')
    opt = config.get_threshold('optimasi_minimum')
    if total_revenue >= keep:
        return "Keeper"
    if total_revenue >= opt:
        return "Optimasi"
    return "Relocate"


def derive_counts_from_type(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    d = df.copy()
    t = d["type"].astype(str).str.strip().str.lower().fillna("") if "type" in d.columns else pd.Series([""] * len(d), index=d.index)
    d["_foto_qty"] = t.str.contains(FOTO_RE).astype(int)
    d["_unlock_qty"] = t.str.contains(UNLOCK_RE).astype(int)
    d["_print_qty"] = t.str.contains(PRINT_RE).astype(int)
    audit = {
        "match_foto": int(d["_foto_qty"].sum()),
        "match_unlock": int(d["_unlock_qty"].sum()),
        "match_print": int(d["_print_qty"].sum()),
    }
    return d, audit


def aggregate_monthly(mapped_df: pd.DataFrame, config: Config, fallback_period: Optional[str] = None) -> Tuple[pd.DataFrame, dict]:
    from datetime import datetime
    df = mapped_df.copy()
    if "tanggal" in df.columns and df["tanggal"].notna().any():
        df["periode"] = pd.to_datetime(df["tanggal"], errors="coerce").dt.strftime("%Y-%m")
    else:
        df["periode"] = fallback_period or datetime.now().strftime("%Y-%m")

    have_cols = all(c in df.columns for c in ["foto", "unlock", "print"])
    totals_zero = False
    if have_cols:
        df["_foto_qty"] = pd.to_numeric(df["foto"], errors="coerce").fillna(0).astype(int)
        df["_unlock_qty"] = pd.to_numeric(df["unlock"], errors="coerce").fillna(0).astype(int)
        df["_print_qty"] = pd.to_numeric(df["print"], errors="coerce").fillna(0).astype(int)
        totals_zero = (df["_foto_qty"].sum() == 0) and (df["_unlock_qty"].sum() == 0) and (df["_print_qty"].sum() == 0)

    audit_derive = {"match_foto": 0, "match_unlock": 0, "match_print": 0}
    if (not have_cols or totals_zero) and ("type" in df.columns):
        df, audit_derive = derive_counts_from_type(df)

    if "outlet_name" not in df.columns:
        raise ValueError("Kolom 'Outlet' tidak ditemukan (harap set mapping kolom Outlet di UI).")

    group_keys = ["periode", "outlet_name"]
    if "area" in df.columns:
        group_keys.append("area")
    df["harga"] = pd.to_numeric(df["harga"], errors="coerce").fillna(0.0)

    agg = df.groupby(group_keys, dropna=False).agg(
        total_revenue=("harga", "sum"),
        foto_qty=("_foto_qty", "sum"),
        unlock_qty=("_unlock_qty", "sum"),
        print_qty=("_print_qty", "sum"),
    ).reset_index()

    agg["conversion_rate"] = np.where(agg["foto_qty"] > 0, agg["print_qty"] / agg["foto_qty"] * 100, 0.0)
    agg["outlet_status"] = agg["total_revenue"].apply(lambda x: compute_status(float(x), config))
    for col in ["kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]:
        if col not in agg.columns:
            agg[col] = "Tidak Terkategorisasi"
    if "area" in agg.columns:
        agg["area"] = agg["area"].astype(str).replace({"nan": ""})
    else:
        agg["area"] = ""

    cols = ["periode", "outlet_name", "area", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat",
            "total_revenue", "foto_qty", "unlock_qty", "print_qty", "conversion_rate", "outlet_status"]
    for c in cols:
        if c not in agg.columns:
            agg[c] = np.nan

    return agg[cols], audit_derive


def save_overwrite_periods(new_df: pd.DataFrame, path: str) -> Tuple[pd.DataFrame, dict]:
    periods = sorted(new_df["periode"].astype(str).unique().tolist())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        old = pd.read_csv(path)
        before_total = float(pd.to_numeric(old.get("total_revenue", 0), errors="coerce").fillna(0).sum())
        before_periods = sorted(old.get("periode", pd.Series(dtype=str)).astype(str).unique().tolist())
        remaining = old[~old["periode"].astype(str).isin(periods)].copy()
        merged = pd.concat([remaining, new_df], ignore_index=True)
    else:
        before_total = 0.0
        before_periods = []
        merged = new_df.copy()

    merged = merged.sort_values(["periode", "outlet_name"]).reset_index(drop=True)
    merged.to_csv(path, index=False)
    after_total = float(pd.to_numeric(merged["total_revenue"], errors="coerce").fillna(0).sum())
    return merged, {
        "periods_overwritten": periods, "before_total": before_total,
        "after_total": after_total, "before_periods": before_periods,
        "remaining_periods": sorted(merged["periode"].astype(str).unique().tolist()),
    }


def _sort_periods_str(periods: List[str]) -> List[str]:
    s = pd.Series(periods, dtype=object)
    dt = pd.to_datetime(s, format="%Y-%m", errors="coerce")
    helper = pd.DataFrame({"p": s, "dt": dt}).sort_values(by=["dt", "p"], na_position="last")
    return helper["p"].astype(str).tolist()
