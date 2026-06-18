"""Services for kemitraan/sharing outlet data management.

Contains all helper functions for processing sharing outlet Excel files,
managing kemitraan financial calculations, and formatting kemitraan tables.
"""

import re
import json
import io
import os
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

import pandas as pd
import numpy as np

from data_processor import normalize_outlet_name
from config import Config, DATA_CSV_PATH

# ================= CONSTANTS =================

SHARING_OUTLETS_DIR = Path(DATA_CSV_PATH).parent / "sharing_outlets"

SHARING_MASTER_COLUMNS = [
    "outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master",
    "investor_name", "partner_share", "broker_share", "sharing_bagi_hasil",
    "monthly_rent", "minimum_payment", "harga_beli_kemitraan", "created_at",
]


# ================= HELPERS =================

def _share_num(value):
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return np.nan
        text = str(value).strip()
        if text == "":
            return np.nan
        n = float(re.sub(r"[^\d\.\-]", "", text))
        if n > 1:
            n = n / 100.0
        return max(0.0, min(1.0, n))
    except Exception:
        return np.nan


def _money_num(value):
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return np.nan
        text = str(value).strip()
        if text == "":
            return np.nan
        return float(re.sub(r"[^\d\.\-]", "", text) or 0)
    except Exception:
        return np.nan


def _pick_col(row, names):
    for name in names:
        if name in row and str(row.get(name, "")).strip() != "":
            return row.get(name)
    return ""


def infer_period_from_filename(filename: str) -> str:
    m = re.search(r"(\d{4})[-_](\d{2})(?:[-_]\d{2})?", str(filename or ""))
    return "{}-{}".format(m.group(1), m.group(2)) if m else ""


def excel_engine_from_filename(filename: str) -> str:
    ext = os.path.splitext(str(filename).lower())[1]
    if ext == ".xlsx":
        return "openpyxl"
    if ext == ".xls":
        return "xlrd"
    raise ValueError(f"Format file '{ext}' tidak didukung. Gunakan .xlsx atau .xls.")


# ================= SHARING OUTLET CRUD =================

def list_sharing_periods() -> List[str]:
    try:
        if not SHARING_OUTLETS_DIR.exists():
            return []
        return sorted([p.stem for p in SHARING_OUTLETS_DIR.glob("*.json") if re.match(r"^\d{4}-\d{2}$", p.stem)])
    except Exception:
        return []


def load_sharing_outlets(period: Optional[str] = None) -> Tuple[Optional[str], pd.DataFrame]:
    periods = list_sharing_periods()
    if not periods:
        return None, pd.DataFrame()
    resolved = str(period or "").strip()
    if not re.match(r"^\d{4}-\d{2}$", resolved) or resolved not in periods:
        resolved = periods[-1]
    try:
        with open(SHARING_OUTLETS_DIR / f"{resolved}.json", "r", encoding="utf-8") as f:
            rows = json.load(f)
        df = pd.DataFrame(rows if isinstance(rows, list) else [])
        return resolved, df
    except Exception:
        return None, pd.DataFrame()


def load_sharing_outlets_exact(period: Optional[str]) -> Tuple[Optional[str], pd.DataFrame]:
    resolved = str(period or "").strip()
    if not re.match(r"^\d{4}-\d{2}$", resolved):
        return None, pd.DataFrame()
    path = SHARING_OUTLETS_DIR / f"{resolved}.json"
    if not path.exists():
        return None, pd.DataFrame()
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return resolved, pd.DataFrame(rows if isinstance(rows, list) else [])
    except Exception:
        return None, pd.DataFrame()


def save_sharing_outlets(period: str, df: pd.DataFrame) -> None:
    SHARING_OUTLETS_DIR.mkdir(parents=True, exist_ok=True)
    clean_df = normalize_sharing_master_df(df)
    if "harga_mesin" in clean_df.columns:
        clean_df = clean_df.drop(columns=["harga_mesin"])
    payload = clean_df.where(pd.notna(clean_df), None).to_dict(orient="records")
    with open(SHARING_OUTLETS_DIR / f"{period}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def parse_sharing_outlet_excel(uploaded_file) -> pd.DataFrame:
    engine = excel_engine_from_filename(getattr(uploaded_file, "name", "xlsx"))
    raw = pd.read_excel(uploaded_file, engine=engine).fillna("")
    rows = []
    for _, row in raw.iterrows():
        name = str(_pick_col(row, ["NAME", "Name", "name", "Nama", "Outlet", "outlet_name"])).strip()
        if not name:
            continue
        partner_share = _share_num(_pick_col(row, ["PARTNER_SHARE", "Partner Share", "partner_share", "partnerShare"]))
        broker_share = _share_num(_pick_col(row, ["BROKER_SHARE", "Broker Share", "broker_share", "brokerShare"]))
        explicit_share = _share_num(_pick_col(row, ["SHARING_BAGI_HASIL", "Sharing Bagi Hasil", "sharing_bagi_hasil", "DIFOTOIN_SHARE", "Difotoin Share"]))
        sharing_bagi_hasil = explicit_share
        if pd.isna(sharing_bagi_hasil) and (pd.notna(partner_share) or pd.notna(broker_share)):
            sharing_bagi_hasil = max(0.0, min(1.0, 1.0 - (0.0 if pd.isna(partner_share) else partner_share) - (0.0 if pd.isna(broker_share) else broker_share)))
        harga_beli_kemitraan = _money_num(_pick_col(row, [
            "HARGA_BELI_KEMITRAAN", "Harga Beli Kemitraan", "harga_beli_kemitraan", "Harga Beli", "harga_beli",
            "INITIAL_COST", "Harga Mesin", "harga_mesin", "MACHINE_PRICE", "Machine Price", "machine_price",
        ]))
        rows.append({
            "outlet_id": str(_pick_col(row, ["ID", "Id", "id"])).strip(),
            "outlet_name": name,
            "area": str(_pick_col(row, ["BRANCH", "Branch", "branch", "Area", "area"])).strip(),
            "outlet_status_master": str(_pick_col(row, ["STATUS", "Status", "status"])).strip(),
            "outlet_type_master": str(_pick_col(row, ["TYPE", "Type", "type"])).strip(),
            "investor_name": str(_pick_col(row, ["OWNER", "Owner", "owner", "INVESTOR_NAME", "Investor Name", "investor_name", "NAMA_INVESTOR", "Nama Investor", "NAMA_KEMITRAAN", "Nama Kemitraan", "Nama Orang/Mitra", "Partner", "Partner Name"])).strip(),
            "partner_share": partner_share,
            "broker_share": broker_share,
            "sharing_bagi_hasil": sharing_bagi_hasil,
            "harga_beli_kemitraan": harga_beli_kemitraan,
            "monthly_rent": _money_num(_pick_col(row, ["MONTHLY_RENT", "Monthly Rent", "monthly_rent", "monthlyRent"])),
            "minimum_payment": _money_num(_pick_col(row, ["MINIMUM_PAYMENT", "Minimum Payment", "minimum_payment", "minimumPayment"])),
            "created_at": str(_pick_col(row, ["CREATED_AT", "Created At", "created_at", "createdAt"])).strip(),
        })
    return pd.DataFrame(rows)


def normalize_sharing_master_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    rename_map = {
        "ID": "outlet_id", "Name": "outlet_name", "NAME": "outlet_name",
        "BRANCH": "area", "STATUS": "outlet_status_master", "TYPE": "outlet_type_master",
        "OWNER": "investor_name", "PARTNER_SHARE": "partner_share", "BROKER_SHARE": "broker_share",
        "MONTHLY_RENT": "monthly_rent", "MINIMUM_PAYMENT": "minimum_payment", "INITIAL_COST": "harga_beli_kemitraan",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})
    if "harga_beli_kemitraan" not in out.columns:
        out["harga_beli_kemitraan"] = np.nan
    if "harga_mesin" in out.columns:
        out["harga_beli_kemitraan"] = out["harga_beli_kemitraan"].combine_first(out["harga_mesin"])
    for col in SHARING_MASTER_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan if col not in ["outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master", "investor_name", "created_at"] else ""
    out = out[SHARING_MASTER_COLUMNS].copy()
    for col in ["outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master", "investor_name", "created_at"]:
        out[col] = out[col].fillna("").astype(str).str.strip()
    for col in ["partner_share", "broker_share", "sharing_bagi_hasil"]:
        out[col] = out[col].apply(_share_num)
    for col in ["monthly_rent", "minimum_payment", "harga_beli_kemitraan"]:
        out[col] = out[col].apply(_money_num)
    out["harga_mesin"] = out["harga_beli_kemitraan"]
    missing_share = out["sharing_bagi_hasil"].isna() & (out["partner_share"].notna() | out["broker_share"].notna())
    out.loc[missing_share, "sharing_bagi_hasil"] = (
        1 - out.loc[missing_share, "partner_share"].fillna(0) - out.loc[missing_share, "broker_share"].fillna(0)
    ).clip(lower=0, upper=1)
    out = out[out["outlet_name"].astype(str).str.strip() != ""].copy()
    out["_key"] = out["outlet_name"].map(normalize_outlet_name)
    out = out.drop_duplicates("_key", keep="last").drop(columns=["_key"])
    return out.reset_index(drop=True)


def apply_sharing_to_mapping(mapping_df: pd.DataFrame, period: Optional[str] = None) -> pd.DataFrame:
    resolved, sharing = load_sharing_outlets(period)
    if mapping_df.empty or sharing.empty or "outlet_name" not in mapping_df.columns:
        return mapping_df
    out = mapping_df.copy()
    sharing = sharing.copy()
    if "harga_beli_kemitraan" not in sharing.columns:
        sharing["harga_beli_kemitraan"] = np.nan
    if "harga_mesin" in sharing.columns:
        sharing["harga_beli_kemitraan"] = sharing["harga_beli_kemitraan"].combine_first(sharing["harga_mesin"])
    sharing["_key"] = sharing["outlet_name"].map(normalize_outlet_name)
    sharing = sharing.drop_duplicates("_key", keep="last")
    out["_key"] = out["outlet_name"].map(normalize_outlet_name)
    merge_cols = [
        "outlet_id", "area", "outlet_status_master", "partner_share", "broker_share",
        "sharing_bagi_hasil", "monthly_rent", "minimum_payment", "investor_name",
        "harga_beli_kemitraan", "harga_mesin",
    ]
    sharing_owned_cols = {
        "partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent",
        "minimum_payment", "investor_name", "harga_beli_kemitraan", "harga_mesin",
    }
    merged = out.merge(sharing[["_key"] + [c for c in merge_cols if c in sharing.columns]], on="_key", how="left", suffixes=("", "_sharing"))
    for col in merge_cols:
        s_col = f"{col}_sharing"
        if s_col in merged.columns:
            vals = merged[s_col].replace("", np.nan)
            if col not in merged.columns:
                merged[col] = np.nan
            if col in sharing_owned_cols:
                merged[col] = vals
            else:
                merged[col] = vals.combine_first(merged[col])
            merged = merged.drop(columns=[s_col])
    for col in ["partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent", "minimum_payment", "harga_beli_kemitraan", "harga_mesin"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")
    if "harga_beli_kemitraan" in merged.columns:
        merged["harga_mesin"] = merged["harga_beli_kemitraan"]
    has_terms = (
        merged.get("partner_share", pd.Series(index=merged.index)).notna()
        | merged.get("broker_share", pd.Series(index=merged.index)).notna()
        | merged.get("minimum_payment", pd.Series(index=merged.index)).notna()
        | merged.get("monthly_rent", pd.Series(index=merged.index)).notna()
        | merged.get("harga_beli_kemitraan", pd.Series(index=merged.index)).notna()
        | merged.get("harga_mesin", pd.Series(index=merged.index)).notna()
    )
    if "ownership_status" not in merged.columns:
        merged["ownership_status"] = ""
    merged["ownership_status"] = np.where(has_terms, "kemitraan", "")
    return merged.drop(columns=["_key"], errors="ignore")


def sync_sharing_to_mapping(sharing_df: pd.DataFrame, period: Optional[str] = None) -> Tuple[int, int]:
    from config import OUTLET_MAPPING_PATH
    try:
        mapping = pd.read_csv(OUTLET_MAPPING_PATH)
    except Exception:
        mapping = pd.DataFrame(columns=["outlet_name"])
    if mapping.empty:
        mapping = pd.DataFrame(columns=["outlet_name"])
    if "outlet_name" not in mapping.columns:
        mapping["outlet_name"] = ""
    mapping["_key"] = mapping["outlet_name"].map(normalize_outlet_name)
    existing_keys = set(mapping["_key"].dropna().astype(str))
    additions = []
    for _, row in sharing_df.iterrows():
        key = normalize_outlet_name(row.get("outlet_name", ""))
        if key and key not in existing_keys:
            additions.append({"outlet_name": row.get("outlet_name", "")})
            existing_keys.add(key)
    if additions:
        mapping = pd.concat([mapping.drop(columns=["_key"], errors="ignore"), pd.DataFrame(additions)], ignore_index=True)
    else:
        mapping = mapping.drop(columns=["_key"], errors="ignore")
    mapping = apply_sharing_to_mapping(mapping, period)
    mapping.to_csv(OUTLET_MAPPING_PATH, index=False)
    return len(mapping), len(additions)


# ================= KEMITRAAN FINANCIALS =================

def build_kemitraan_financials(transactions_df: pd.DataFrame, sharing_df: pd.DataFrame, mapping_df: pd.DataFrame, period: Optional[str]) -> pd.DataFrame:
    master = normalize_sharing_master_df(sharing_df)
    if master.empty:
        return master

    master["_key"] = master["outlet_name"].map(normalize_outlet_name)

    if isinstance(mapping_df, pd.DataFrame) and not mapping_df.empty and "outlet_name" in mapping_df.columns:
        mapping_cols = ["outlet_name", "kategori_tempat", "sub_kategori_tempat", "tipe_tempat"]
        mapping = mapping_df[[c for c in mapping_cols if c in mapping_df.columns]].copy()
        mapping["_key"] = mapping["outlet_name"].map(normalize_outlet_name)
        mapping = mapping.drop_duplicates("_key", keep="last").drop(columns=["outlet_name"], errors="ignore")
        master = master.merge(mapping, on="_key", how="left")

    if isinstance(transactions_df, pd.DataFrame) and not transactions_df.empty and "outlet_name" in transactions_df.columns:
        tx = transactions_df.copy()
        if period and "periode" in tx.columns:
            tx = tx[tx["periode"].astype(str) == str(period)].copy()
        tx["_key"] = tx["outlet_name"].map(normalize_outlet_name)
        if "total_revenue" not in tx.columns:
            tx["total_revenue"] = 0
        revenue = tx.groupby("_key", as_index=False).agg(total_revenue=("total_revenue", "sum"))
    else:
        revenue = pd.DataFrame(columns=["_key", "total_revenue"])

    master = master.merge(revenue, on="_key", how="left")
    master["total_revenue"] = pd.to_numeric(master.get("total_revenue", 0), errors="coerce").fillna(0.0)
    master["basis_bagi_hasil"] = np.where(master["total_revenue"] > 0, master["total_revenue"], master["minimum_payment"].fillna(0))
    master["partner_share"] = master["partner_share"].clip(lower=0, upper=1)
    master["broker_share"] = master["broker_share"].fillna(0).clip(lower=0, upper=1)
    master["sharing_bagi_hasil"] = master["sharing_bagi_hasil"].clip(lower=0, upper=1)
    master["pendapatan_mitra"] = np.where(
        master["partner_share"].notna(),
        master["basis_bagi_hasil"] * master["partner_share"],
        master["basis_bagi_hasil"] * (1 - master["sharing_bagi_hasil"].fillna(0) - master["broker_share"].fillna(0)),
    )
    master["pendapatan_broker"] = master["basis_bagi_hasil"] * master["broker_share"].fillna(0)
    master["pendapatan_difotoin"] = master["basis_bagi_hasil"] * master["sharing_bagi_hasil"].fillna(0)
    master["profit_difotoin"] = master["pendapatan_difotoin"].fillna(0) - master["monthly_rent"].fillna(0)
    master["estimasi_bep_bulan"] = np.where(
        (master["harga_beli_kemitraan"] > 0) & (master["pendapatan_mitra"] > 0),
        master["harga_beli_kemitraan"] / master["pendapatan_mitra"],
        np.nan,
    )
    master["yield_bulanan"] = np.where(
        master["harga_beli_kemitraan"] > 0,
        master["pendapatan_mitra"] / master["harga_beli_kemitraan"],
        np.nan,
    )
    master["yield_tahunan"] = master["yield_bulanan"] * 12
    return master.drop(columns=["_key"], errors="ignore")


def format_kemitraan_table(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    display = df.copy()
    money_cols = [
        "total_revenue", "basis_bagi_hasil", "revenue", "pendapatan_mitra", "pendapatan_broker",
        "pendapatan_difotoin", "profit_difotoin", "monthly_rent", "minimum_payment",
        "harga_beli_kemitraan", "harga_beli",
    ]
    pct_cols = ["partner_share", "broker_share", "sharing_bagi_hasil", "yield_bulanan", "yield_tahunan"]
    for col in money_cols:
        if col in display.columns:
            display[col] = display[col].apply(lambda x: config.format_currency(float(x)) if pd.notna(x) and float(x) > 0 else "-")
    for col in pct_cols:
        if col in display.columns:
            display[col] = display[col].apply(lambda x: "-" if pd.isna(x) else f"{float(x)*100:.1f}%")
    if "estimasi_bep_bulan" in display.columns:
        display["estimasi_bep_bulan"] = display["estimasi_bep_bulan"].apply(lambda x: "-" if pd.isna(x) else f"{float(x):.1f} bulan")
    return display


def add_profit_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["total_revenue", "minimum_payment", "partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent"]:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["basis_bagi_hasil"] = np.where(out["total_revenue"].fillna(0) > 0, out["total_revenue"].fillna(0), out["minimum_payment"].fillna(0))
    missing_share = out["sharing_bagi_hasil"].isna() & (out["partner_share"].notna() | out["broker_share"].notna())
    out.loc[missing_share, "sharing_bagi_hasil"] = (1 - out.loc[missing_share, "partner_share"].fillna(0) - out.loc[missing_share, "broker_share"].fillna(0)).clip(lower=0, upper=1)
    out["pendapatan_operator"] = out["basis_bagi_hasil"].fillna(0) * out["sharing_bagi_hasil"].fillna(0)
    out["estimasi_profit_difotoin"] = out["pendapatan_operator"].fillna(0) - out["monthly_rent"].fillna(0)
    return out


# ================= RENDER SHARING UPLOAD PANEL (used by admin & kemitraan pages) =================

def render_sharing_upload_panel(config: Config) -> None:
    import streamlit as st
    from components.compat import rerun

    periods = list_sharing_periods()
    latest_period = periods[-1] if periods else None
    latest_rows = 0
    if latest_period:
        _, latest_df = load_sharing_outlets(latest_period)
        latest_rows = len(latest_df)
    st.subheader("Upload Data Sharing Outlet")
    st.caption("Upload file outlet-list Excel per bulan. Contoh file bulanan: sftp://killdower@103.250.10.163/home/killdower/dower/outlet_update.xlsx. Data ini menimpa partner share, broker share, minimum payment, dan rent sesuai periode kontrak.")
    c1, c2 = st.columns([1, 2])
    with c1:
        period_input = st.text_input("Periode sharing (YYYY-MM)", value=datetime.now().strftime("%Y-%m"), key="sharing_period_input")
    with c2:
        sharing_file = st.file_uploader("File Excel sharing outlet", type=["xlsx", "xls"], key="sharing_upload_file")
    if sharing_file is not None:
        if not re.match(r"^\d{4}-\d{2}$", str(period_input or "")):
            inferred = infer_period_from_filename(sharing_file.name)
            if inferred:
                period_input = inferred
        if st.button("Upload & Terapkan Sharing", type="primary", key="sharing_upload_submit"):
            if not re.match(r"^\d{4}-\d{2}$", str(period_input or "")):
                st.error("Periode wajib format YYYY-MM.")
            else:
                sharing_df = parse_sharing_outlet_excel(sharing_file)
                if sharing_df.empty:
                    st.error("File tidak berisi outlet yang valid.")
                else:
                    save_sharing_outlets(period_input, sharing_df)
                    total, added = sync_sharing_to_mapping(sharing_df, period_input)
                    try:
                        from app import cache_clear, load_app_data
                        cache_clear(load_app_data)
                    except Exception:
                        pass
                    st.success(f"{period_input}: {len(sharing_df)} outlet sharing tersimpan. Master outlet: {total} baris, tambah baru: {added}.")
                    rerun()
    st.info(f"Sharing terbaru: {latest_period or '-'} ({latest_rows} outlet). Periode tersimpan: {', '.join(periods) if periods else '-'}.")
