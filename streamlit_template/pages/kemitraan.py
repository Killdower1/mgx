"""🤝 Kemitraan page — outlet partnership & financial analysis.
Extracted from app.py during refactor (Task 15)."""

from typing import Optional

import pandas as pd
import numpy as np
import streamlit as st

from config import Config
from data_processor import DataProcessor, normalize_outlet_name
from services.kemitraan import (
    list_sharing_periods,
    load_sharing_outlets_exact,
    build_kemitraan_financials,
    normalize_sharing_master_df,
    format_kemitraan_table,
    render_sharing_upload_panel,
    save_sharing_outlets,
    sync_sharing_to_mapping,
)
from components.compat import (
    df_show, rerun, table_height, DEFAULT_TABLE_MAX_HEIGHT,
    HAS_COLUMN_CONFIG,
)
from components.ui_helpers import kemitraan_table_show


def show_kemitraan_page(df: pd.DataFrame, config: Config, processor: DataProcessor):
    st.title("🤝 Kemitraan")
    mapping = processor.load_outlet_mapping() if hasattr(processor, "load_outlet_mapping") else pd.DataFrame()
    sharing_periods = list_sharing_periods()
    tx_periods = sorted([str(p) for p in df.get("periode", pd.Series(dtype=str)).dropna().unique()]) if isinstance(df, pd.DataFrame) and not df.empty else []
    periods = sorted(set(sharing_periods + tx_periods))
    selected_period = st.selectbox("Periode", periods, index=len(periods) - 1 if periods else 0, key="kemitraan_period") if periods else None
    _, sharing_master = load_sharing_outlets_exact(selected_period)
    kemitraan = build_kemitraan_financials(df, sharing_master, mapping, selected_period)

    section = st.radio(
        "Menu Kemitraan",
        ["Ringkasan Dashboard", "Kemitraan All", "Kemitraan Satuan", "Setting Kemitraan"],
        horizontal=True,
        key="kemitraan_section",
    )

    if section == "Ringkasan Dashboard":
        _show_kemitraan_ringkasan(df, config, selected_period, kemitraan, sharing_master)

    if section == "Kemitraan All":
        _show_kemitraan_all(kemitraan, config)

    if section == "Kemitraan Satuan":
        _show_kemitraan_satuan(kemitraan, config)

    if section == "Setting Kemitraan":
        _show_kemitraan_setting(config, sharing_periods)


def _show_kemitraan_ringkasan(df, config, selected_period, kemitraan, sharing_master):
    if selected_period and isinstance(df, pd.DataFrame) and not df.empty and "periode" in df.columns:
        dashboard_tx = df[df["periode"].astype(str) == str(selected_period)].copy()
    else:
        dashboard_tx = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if dashboard_tx.empty or "outlet_name" not in dashboard_tx.columns:
        st.info("Belum ada transaksi dashboard untuk periode ini.")
        return
    if "total_revenue" not in dashboard_tx.columns:
        dashboard_tx["total_revenue"] = 0
    dashboard_tx["_key"] = dashboard_tx["outlet_name"].map(normalize_outlet_name)
    agg_map = {"total_revenue": ("total_revenue", "sum")}
    if "area" in dashboard_tx.columns:
        agg_map["area"] = ("area", "first")
    if "kategori_tempat" in dashboard_tx.columns:
        agg_map["kategori_tempat"] = ("kategori_tempat", "first")
    if "tipe_tempat" in dashboard_tx.columns:
        agg_map["tipe_tempat"] = ("tipe_tempat", "first")
    outlet_summary = dashboard_tx.groupby(["_key", "outlet_name"], as_index=False).agg(**agg_map)

    master_cols = [
        "outlet_name", "area", "outlet_status_master", "outlet_type_master",
        "harga_beli_kemitraan", "partner_share", "broker_share", "sharing_bagi_hasil",
        "monthly_rent", "minimum_payment",
    ]
    master = normalize_sharing_master_df(sharing_master)
    if not master.empty:
        master["_key"] = master["outlet_name"].map(normalize_outlet_name)
        master = master[[c for c in master_cols if c in master.columns] + ["_key"]].drop_duplicates("_key", keep="last")
        outlet_summary = outlet_summary.merge(master.drop(columns=["outlet_name"], errors="ignore"), on="_key", how="left", suffixes=("", "_master"))
        if "area_master" in outlet_summary.columns:
            outlet_summary["area"] = outlet_summary["area_master"].replace("", np.nan).combine_first(outlet_summary.get("area", pd.Series(index=outlet_summary.index)))
            outlet_summary = outlet_summary.drop(columns=["area_master"])

    outlet_summary["harga_beli_kemitraan"] = pd.to_numeric(outlet_summary.get("harga_beli_kemitraan", np.nan), errors="coerce")
    for col in ["partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent", "minimum_payment"]:
        if col not in outlet_summary.columns:
            outlet_summary[col] = np.nan
        outlet_summary[col] = pd.to_numeric(outlet_summary[col], errors="coerce")
    outlet_summary["basis_bagi_hasil"] = np.where(
        outlet_summary["total_revenue"] > 0,
        outlet_summary["total_revenue"],
        outlet_summary["minimum_payment"].fillna(0),
    )
    missing_share = outlet_summary["sharing_bagi_hasil"].isna() & (
        outlet_summary["partner_share"].notna() | outlet_summary["broker_share"].notna()
    )
    outlet_summary.loc[missing_share, "sharing_bagi_hasil"] = (
        1
        - outlet_summary.loc[missing_share, "partner_share"].fillna(0)
        - outlet_summary.loc[missing_share, "broker_share"].fillna(0)
    ).clip(lower=0, upper=1)
    outlet_summary["pendapatan_mitra"] = np.where(
        outlet_summary["partner_share"].notna(),
        outlet_summary["basis_bagi_hasil"] * outlet_summary["partner_share"].clip(lower=0, upper=1),
        outlet_summary["basis_bagi_hasil"]
        * (1 - outlet_summary["sharing_bagi_hasil"].fillna(0).clip(lower=0, upper=1) - outlet_summary["broker_share"].fillna(0).clip(lower=0, upper=1)),
    )
    outlet_summary["pendapatan_broker"] = outlet_summary["basis_bagi_hasil"] * outlet_summary["broker_share"].fillna(0).clip(lower=0, upper=1)
    outlet_summary["pendapatan_difotoin"] = outlet_summary["basis_bagi_hasil"] * outlet_summary["sharing_bagi_hasil"].fillna(0).clip(lower=0, upper=1)
    outlet_summary["persen_pendapatan_mitra"] = np.where(
        outlet_summary["basis_bagi_hasil"] > 0,
        outlet_summary["pendapatan_mitra"] / outlet_summary["basis_bagi_hasil"],
        np.nan,
    )
    outlet_summary["persen_pendapatan_broker"] = np.where(
        outlet_summary["basis_bagi_hasil"] > 0,
        outlet_summary["pendapatan_broker"] / outlet_summary["basis_bagi_hasil"],
        np.nan,
    )
    outlet_summary["persen_pendapatan_difotoin"] = np.where(
        outlet_summary["basis_bagi_hasil"] > 0,
        outlet_summary["pendapatan_difotoin"] / outlet_summary["basis_bagi_hasil"],
        np.nan,
    )
    outlet_summary["yield_bulanan"] = np.where(
        outlet_summary["harga_beli_kemitraan"] > 0,
        outlet_summary["total_revenue"] / outlet_summary["harga_beli_kemitraan"],
        np.nan,
    )
    outlet_summary["yield_tahunan"] = outlet_summary["yield_bulanan"] * 12

    total_revenue_tx = float(outlet_summary["total_revenue"].sum())
    total_outlet_kemitraan = int(kemitraan["outlet_name"].nunique()) if not kemitraan.empty and "outlet_name" in kemitraan.columns else 0
    total_pendapatan_mitra = float(kemitraan["pendapatan_mitra"].sum()) if not kemitraan.empty and "pendapatan_mitra" in kemitraan.columns else 0.0
    total_pendapatan_broker = float(kemitraan["pendapatan_broker"].sum()) if not kemitraan.empty and "pendapatan_broker" in kemitraan.columns else 0.0
    total_pendapatan_difotoin = float(kemitraan["pendapatan_difotoin"].sum()) if not kemitraan.empty and "pendapatan_difotoin" in kemitraan.columns else 0.0
    total_harga_beli = float(outlet_summary["harga_beli_kemitraan"].fillna(0).sum())
    total_yield_bulanan = total_revenue_tx / total_harga_beli if total_harga_beli > 0 else np.nan
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Outlet Kemitraan", total_outlet_kemitraan)
    c2.metric("Total Pendapatan", config.format_currency(total_revenue_tx))
    c3.metric("Pendapatan Mitra", config.format_currency(total_pendapatan_mitra))
    c4.metric("Pendapatan Broker", config.format_currency(total_pendapatan_broker))
    c5.metric("Pendapatan Difotoin", config.format_currency(total_pendapatan_difotoin))
    c6.metric("Yield Bulanan", "-" if pd.isna(total_yield_bulanan) else f"{total_yield_bulanan*100:.1f}%")

    st.subheader("Ringkasan Semua Outlet")
    outlet_summary = outlet_summary[
        outlet_summary["outlet_type_master"].fillna("").astype(str).str.strip().str.lower() == "franchise"
    ].copy()
    display_cols = [
        "outlet_name", "area", "outlet_type_master", "total_revenue",
        "monthly_rent", "minimum_payment",
        "pendapatan_mitra", "pendapatan_broker", "pendapatan_difotoin",
        "persen_pendapatan_mitra", "persen_pendapatan_broker", "persen_pendapatan_difotoin",
        "harga_beli_kemitraan", "yield_bulanan", "yield_tahunan",
    ]
    display = outlet_summary[[c for c in display_cols if c in outlet_summary.columns]].sort_values("total_revenue", ascending=False).copy()
    display_pct = display[
        [c for c in ["persen_pendapatan_mitra", "persen_pendapatan_broker", "persen_pendapatan_difotoin"] if c in display.columns]
    ].copy()
    display = format_kemitraan_table(display, config)
    pct_pairs = {
        "pendapatan_mitra": "persen_pendapatan_mitra",
        "pendapatan_broker": "persen_pendapatan_broker",
        "pendapatan_difotoin": "persen_pendapatan_difotoin",
    }
    for amount_col, pct_col in pct_pairs.items():
        if amount_col in display.columns and pct_col in display_pct.columns:
            display[amount_col] = [
                f"{amount} ({float(pct) * 100:.1f}%)" if pd.notna(pct) else amount
                for amount, pct in zip(display[amount_col], display_pct[pct_col])
            ]
    display = display.drop(columns=list(pct_pairs.values()), errors="ignore").rename(columns={
        "outlet_name": "Outlet", "area": "Area", "outlet_type_master": "Type Master",
        "total_revenue": "Pendapatan Transaksi", "monthly_rent": "Monthly Rent",
        "minimum_payment": "Minimum Payment", "pendapatan_mitra": "Pendapatan Mitra",
        "pendapatan_broker": "Pendapatan Broker", "pendapatan_difotoin": "Pendapatan Difotoin",
        "harga_beli_kemitraan": "Harga Beli Kemitraan", "yield_bulanan": "Yield Bulanan",
        "yield_tahunan": "Yield Tahunan",
    })
    kemitraan_table_show(display, use_container_width=True, hide_index=True, height=table_height(len(display), 300, DEFAULT_TABLE_MAX_HEIGHT))


def _show_kemitraan_all(kemitraan, config):
    if kemitraan.empty:
        st.info("Belum ada data kemitraan untuk periode ini.")
        return
    query = st.text_input("Cari outlet / area / pemilik", key="kemitraan_all_search")
    view = kemitraan.copy()
    if query.strip():
        q = query.strip()
        mask = (
            view["outlet_name"].astype(str).str.contains(q, case=False, na=False)
            | view["area"].astype(str).str.contains(q, case=False, na=False)
            | view["investor_name"].astype(str).str.contains(q, case=False, na=False)
        )
        view = view[mask].copy()
    cols = [
        "outlet_id", "outlet_name", "area", "outlet_status_master", "outlet_type_master",
        "investor_name", "total_revenue", "minimum_payment", "basis_bagi_hasil",
        "partner_share", "broker_share", "sharing_bagi_hasil", "monthly_rent",
        "pendapatan_mitra", "pendapatan_broker", "pendapatan_difotoin", "profit_difotoin",
        "harga_beli_kemitraan", "estimasi_bep_bulan", "yield_bulanan", "yield_tahunan",
    ]
    display = format_kemitraan_table(view[[c for c in cols if c in view.columns]].sort_values("basis_bagi_hasil", ascending=False), config)
    display = display.rename(columns={
        "outlet_id": "ID", "outlet_name": "Outlet", "area": "Area",
        "outlet_status_master": "Status", "outlet_type_master": "Type",
        "investor_name": "Pemilik/Kemitraan", "total_revenue": "Revenue Transaksi",
        "minimum_payment": "Minimum Payment", "basis_bagi_hasil": "Revenue/Basis",
        "partner_share": "Partner Share", "broker_share": "Broker Share",
        "sharing_bagi_hasil": "Share Difotoin", "monthly_rent": "Monthly Rent",
        "pendapatan_mitra": "Pendapatan Mitra", "pendapatan_broker": "Pendapatan Broker",
        "pendapatan_difotoin": "Pendapatan Difotoin", "profit_difotoin": "Profit Difotoin",
        "harga_beli_kemitraan": "Harga Beli Kemitraan", "estimasi_bep_bulan": "BEP",
        "yield_bulanan": "Yield Bulanan", "yield_tahunan": "Yield Tahunan",
    })
    kemitraan_table_show(display, use_container_width=True, hide_index=True, height=table_height(len(display), 320, DEFAULT_TABLE_MAX_HEIGHT))


def _show_kemitraan_satuan(kemitraan, config):
    if kemitraan.empty:
        st.info("Belum ada data kemitraan untuk periode ini.")
        return
    people = kemitraan.copy()
    people["investor_name"] = people["investor_name"].fillna("").astype(str).str.strip().replace("", "Belum diisi")
    summary = people.groupby("investor_name", as_index=False).agg(
        outlet_count=("outlet_name", "nunique"),
        harga_beli=("harga_beli_kemitraan", "sum"),
        revenue=("basis_bagi_hasil", "sum"),
        pendapatan_mitra=("pendapatan_mitra", "sum"),
        pendapatan_broker=("pendapatan_broker", "sum"),
        pendapatan_difotoin=("pendapatan_difotoin", "sum"),
        profit_difotoin=("profit_difotoin", "sum"),
    )
    summary["estimasi_bep_bulan"] = np.where(
        (summary["harga_beli"] > 0) & (summary["pendapatan_mitra"] > 0),
        summary["harga_beli"] / summary["pendapatan_mitra"],
        np.nan,
    )
    summary["yield_bulanan"] = np.where(summary["harga_beli"] > 0, summary["pendapatan_mitra"] / summary["harga_beli"], np.nan)
    summary["yield_tahunan"] = summary["yield_bulanan"] * 12
    names = summary.sort_values("pendapatan_mitra", ascending=False)["investor_name"].tolist()

    st.subheader("Ringkasan Semua Kemitraan")
    summary_display = format_kemitraan_table(summary.sort_values("pendapatan_mitra", ascending=False), config).rename(columns={
        "investor_name": "Kemitraan", "outlet_count": "Jumlah Outlet",
        "harga_beli": "Total Harga Beli", "revenue": "Revenue/Basis",
        "pendapatan_mitra": "Pendapatan Mitra", "pendapatan_broker": "Pendapatan Broker",
        "pendapatan_difotoin": "Pendapatan Difotoin", "profit_difotoin": "Profit Difotoin",
        "estimasi_bep_bulan": "BEP", "yield_bulanan": "Yield Bulanan", "yield_tahunan": "Yield Tahunan",
    })
    kemitraan_table_show(
        summary_display,
        use_container_width=True,
        hide_index=True,
        height=table_height(len(summary_display), 260, DEFAULT_TABLE_MAX_HEIGHT),
    )

    selected_name = st.selectbox("Pilih kemitraan / pemilik", names, key="kemitraan_satuan_select") if names else None
    if selected_name:
        st.subheader("Detail Outlet Dimiliki")
        detail = people[people["investor_name"] == selected_name].copy()
        detail_cols = [
            "outlet_id", "outlet_name", "area", "outlet_status_master", "basis_bagi_hasil",
            "partner_share", "pendapatan_mitra", "harga_beli_kemitraan",
            "estimasi_bep_bulan", "yield_bulanan", "yield_tahunan",
        ]
        detail = format_kemitraan_table(detail[[c for c in detail_cols if c in detail.columns]].sort_values("basis_bagi_hasil", ascending=False), config)
        detail = detail.rename(columns={
            "outlet_id": "ID", "outlet_name": "Outlet", "area": "Area",
            "outlet_status_master": "Status", "basis_bagi_hasil": "Revenue/Basis",
            "partner_share": "Partner Share", "pendapatan_mitra": "Pendapatan Mitra",
            "harga_beli_kemitraan": "Harga Beli", "estimasi_bep_bulan": "BEP",
            "yield_bulanan": "Yield Bulanan", "yield_tahunan": "Yield Tahunan",
        })
        kemitraan_table_show(detail, use_container_width=True, hide_index=True, height=table_height(len(detail), 240, DEFAULT_TABLE_MAX_HEIGHT))


def _show_kemitraan_setting(config, sharing_periods):
    st.subheader("Upload Data Kemitraan")
    render_sharing_upload_panel(config)
    st.divider()
    st.subheader("Master Kemitraan Editable")
    edit_period = st.selectbox(
        "Periode master",
        sharing_periods,
        index=len(sharing_periods) - 1 if sharing_periods else 0,
        key="kemitraan_setting_period",
    ) if sharing_periods else None
    if not edit_period:
        st.info("Upload file outlet_update.xlsx dulu untuk membuat master kemitraan.")
        return
    _, edit_df = load_sharing_outlets_exact(edit_period)
    from services.kemitraan import normalize_sharing_master_df as _norm_master
    edit_df = _norm_master(edit_df)
    editor_config = None
    if HAS_COLUMN_CONFIG:
        try:
            editor_config = {
                "outlet_id": st.column_config.TextColumn("ID", width="small"),
                "outlet_name": st.column_config.TextColumn("Nama Outlet", width="large"),
                "area": st.column_config.TextColumn("Branch/Area", width="medium"),
                "outlet_status_master": st.column_config.SelectboxColumn("Status", options=["", "Active", "Inactive"], width="small"),
                "outlet_type_master": st.column_config.TextColumn("Type", width="small"),
                "investor_name": st.column_config.TextColumn("Nama Kemitraan/Pemilik", width="medium"),
                "partner_share": st.column_config.NumberColumn("Partner Share", min_value=0, max_value=1, step=0.01, format="%.2f"),
                "broker_share": st.column_config.NumberColumn("Broker Share", min_value=0, max_value=1, step=0.01, format="%.2f"),
                "sharing_bagi_hasil": st.column_config.NumberColumn("Share Difotoin", min_value=0, max_value=1, step=0.01, format="%.2f"),
                "monthly_rent": st.column_config.NumberColumn("Monthly Rent", min_value=0, step=100000, format="%.0f"),
                "minimum_payment": st.column_config.NumberColumn("Minimum Payment", min_value=0, step=100000, format="%.0f"),
                "harga_beli_kemitraan": st.column_config.NumberColumn("Harga Beli Kemitraan", min_value=0, step=1000000, format="%.0f"),
                "created_at": st.column_config.TextColumn("Created At", width="medium"),
            }
        except Exception:
            editor_config = None
    st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
    if hasattr(st, "data_editor"):
        edited = st.data_editor(
            edit_df,
            use_container_width=True,
            hide_index=True,
            height=table_height(len(edit_df), 340, DEFAULT_TABLE_MAX_HEIGHT),
            num_rows="dynamic",
            column_config=editor_config,
            key=f"kemitraan_master_editor_{edit_period}",
        )
    else:
        edited = edit_df
        df_show(edit_df, use_container_width=True, hide_index=True, height=table_height(len(edit_df), 340, DEFAULT_TABLE_MAX_HEIGHT))
    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("Simpan Master Kemitraan", type="primary", key="kemitraan_save_master"):
        from services.kemitraan import normalize_sharing_master_df as _norm_master2
        cleaned = _norm_master2(pd.DataFrame(edited))
        save_sharing_outlets(edit_period, cleaned)
        sync_sharing_to_mapping(cleaned, edit_period)
        try:
            from app import cache_clear, load_app_data
            cache_clear(load_app_data)
        except Exception:
            pass
        st.success(f"Master kemitraan {edit_period} tersimpan: {len(cleaned)} outlet.")
        rerun()
