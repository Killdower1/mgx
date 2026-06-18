"""
Dashboard page — main overview, outlet table, and omset trend table.
Extracted from app.py during refactor (Task 12).
"""
import io
from typing import List, Optional, Tuple, Dict
import streamlit as st
import pandas as pd
import numpy as np
from config import Config
from utils import generate_insights
from components.compat import cache_data, rerun, text_col, number_col, table_height, df_show, DEFAULT_TABLE_MAX_HEIGHT, HAS_COLUMN_CONFIG, HAS_CAPTION
from components.ui_helpers import render_mobile_cards, s_caption, bool_series, _clean_master_values, kemitraan_table_show


# ================= HELPERS =================

def format_number_with_dots(num):
    try:
        return f"{int(round(float(num))):,}".replace(",", ".")
    except Exception:
        return str(num)


def format_decimal_with_comma(num, digits=1, suffix=""):
    try:
        return f"{float(num):.{int(digits)}f}".replace(".", ",") + suffix
    except Exception:
        return str(num)


def _norm_name(s: str) -> str:
    return str(s).strip().lower()


def format_comparison_value(current_val, compare_val, is_percentage=False):
    """Format comparison value with delta indicator."""
    if compare_val == 0:
        return "0.0%" if not is_percentage else "0.0pp"
    if is_percentage:
        change = float(current_val) - float(compare_val)
        sign = "+" if change > 0 else ""
        return f"{sign}{change:.1f}pp" if change != 0 else "0.0pp"
    change_pct = ((float(current_val) - float(compare_val)) / float(compare_val)) * 100
    sign = "+" if change_pct > 0 else ""
    return f"{sign}{change_pct:.1f}%" if change_pct != 0 else "0.0%"


# ================= EXPORT EXCEL (OMSET TREND) =================
from io import BytesIO


def _export_trend_excel(df_display_sorted, value_cols):
    export_df = df_display_sorted.copy()

    for col in ["Rata-rata"] + value_cols:
        if col in export_df.columns:
            # ambil angka murni
            export_df[col] = (
                export_df[col]
                .astype(str)
                .str.replace(r"[^0-9]", "", regex=True)
                .replace("", "0")
                .astype(int)
            )

            # FIX: kurangin 1 digit nol (10x -> normal)
            export_df[col] = (export_df[col] // 10).astype(int)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Tren Omset")
    buffer.seek(0)

    st.download_button(
        "⬇️ Download Excel (Angka Murni)",
        data=buffer,
        file_name="tren_omset_outlet_12_bulan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )


# ================= OUTLET TABLE =================

def create_outlet_table(df, current_period, compare_period, full_df=None):
    st.markdown('<div class="outlet-table">', unsafe_allow_html=True)
    st.markdown("### 🏪 Outlet Performance Table")

    st.markdown('<div class="filter-buttons">', unsafe_allow_html=True)
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: show_keeper = st.checkbox("🟢 Keeper", value=True, key="filter_keeper")
    with col2: show_optimasi = st.checkbox("🟡 Optimasi", value=True, key="filter_optimasi")
    with col3: show_relocate = st.checkbox("🔴 Relocate", value=True, key="filter_relocate")
    with col4: show_inactive = st.checkbox("Tidak Aktif", value=True, key="filter_inactive")
    with col5: show_all = st.checkbox("Show All", value=False, key="filter_all")
    st.markdown('</div>', unsafe_allow_html=True)

    src = full_df if isinstance(full_df, pd.DataFrame) and not full_df.empty else df
    if src.empty or "outlet_name" not in src.columns:
        st.info("No outlets match the selected filters")
        st.markdown('</div>', unsafe_allow_html=True); return

    source_df = src.copy(deep=True)
    source_df["outlet_name"] = source_df["outlet_name"].fillna("").astype(str).str.strip()
    source_df = source_df[source_df["outlet_name"] != ""]
    if source_df.empty:
        st.info("No outlets match the selected filters")
        st.markdown('</div>', unsafe_allow_html=True); return

    current_src = source_df[source_df["periode"].astype(str) == str(current_period)].copy() if current_period and "periode" in source_df.columns else df.copy(deep=True)
    if "outlet_name" in current_src.columns:
        current_src["outlet_name"] = current_src["outlet_name"].fillna("").astype(str).str.strip()
    current_map = {}
    if not current_src.empty and "outlet_name" in current_src.columns:
        current_src["_key"] = current_src["outlet_name"].map(_norm_name)
        current_map = current_src.drop_duplicates("_key", keep="last").set_index("_key").to_dict(orient="index")

    meta = source_df.drop_duplicates("outlet_name", keep="last").set_index("outlet_name").to_dict(orient="index")

    compare_map = {}
    if compare_period:
        cmp_df = src[src["periode"] == compare_period].copy()
        if not cmp_df.empty:
            cmp_df["_key"] = cmp_df["outlet_name"].map(_norm_name)
            compare_map = cmp_df.set_index("_key").to_dict(orient="index")

    rows = []
    for name in sorted(source_df["outlet_name"].dropna().astype(str).unique().tolist()):
        key = _norm_name(name)
        is_active = key in current_map
        r = current_map.get(key, meta.get(name, {}))
        omset = float(r.get("total_revenue", 0) or 0) if is_active else 0.0
        foto = int(r.get("foto_qty", 0) or 0) if is_active else 0
        unlock = int(r.get("unlock_qty", 0) or 0) if is_active else 0
        conv = float(r.get("conversion_rate", 0) or 0) if is_active else 0.0
        status = str(r.get("outlet_status", "")) if is_active else "Tidak Aktif"
        if not show_all:
            keep = []
            if show_keeper: keep.append("Keeper")
            if show_optimasi: keep.append("Optimasi")
            if show_relocate: keep.append("Relocate")
            if show_inactive: keep.append("Tidak Aktif")
            if status not in keep:
                continue
        rec = {
            "Outlet": name, "Area": r.get("area",""),
            "_omset_sort": int(omset), "_foto_sort": int(foto), "_unlock_sort": int(unlock), "_conversion_sort": float(conv),
            "Omset": float(omset), "Omset Compare": "New Outlet",
            "Foto": int(foto), "Foto Compare": "New Outlet",
            "Unlock": int(unlock), "Unlock Compare": "New Outlet",
            "Conversion": float(conv), "Conversion Compare": "New Outlet",
            "Status": status,
            "_omset_delta": np.nan, "_foto_delta": np.nan, "_unlock_delta": np.nan, "_conv_delta": np.nan
        }
        if compare_period and key in compare_map:
            p = compare_map[key]
            p_omset = float(p.get("total_revenue", 0) or 0)
            p_foto  = int(p.get("foto_qty", 0) or 0)
            p_unlock= int(p.get("unlock_qty", 0) or 0)
            p_conv  = float(p.get("conversion_rate", 0) or 0)
            rec["Omset Compare"]      = format_comparison_value(omset, p_omset, False)
            rec["Foto Compare"]       = format_comparison_value(foto, p_foto, False)
            rec["Unlock Compare"]     = format_comparison_value(unlock, p_unlock, False)
            rec["Conversion Compare"] = format_comparison_value(conv, p_conv, True)
            rec["_omset_delta"] = 0 if p_omset==0 else ((omset - p_omset)/p_omset)*100
            rec["_foto_delta"]  = 0 if p_foto ==0 else ((foto  - p_foto )/p_foto )*100
            rec["_unlock_delta"]= 0 if p_unlock==0 else ((unlock- p_unlock)/p_unlock)*100
            rec["_conv_delta"]  = (conv - p_conv)
        rows.append(rec)

    if not rows:
        st.info("No outlets match the selected filters")
        st.markdown('</div>', unsafe_allow_html=True); return

    table_df = pd.DataFrame(rows)
    visible = (["Outlet","Area","Omset","Omset Compare","Foto","Foto Compare","Unlock","Unlock Compare","Conversion","Conversion Compare","Status"]
               if compare_period else ["Outlet","Area","Omset","Foto","Unlock","Conversion","Status"])

    st.info("💡 **Sorting**: gunakan dropdown untuk mengurutkan")
    c1, c2 = st.columns([2,1])
    with c1: sort_col_name = st.selectbox("Sort by:", ["Omset","Foto","Unlock","Conversion"], key="sort_column")
    with c2: order = st.selectbox("Order:", ["Descending (High to Low)","Ascending (Low to High)"], key="sort_order")
    sort_key = {"Omset":"_omset_sort","Foto":"_foto_sort","Unlock":"_unlock_sort","Conversion":"_conversion_sort"}[sort_col_name]
    ascending = order == "Ascending (Low to High)"
    table_sorted = table_df.sort_values(sort_key, ascending=ascending).reset_index(drop=True)
    display_df = table_sorted[visible].copy()

    def style_status(val):
        if val == 'Keeper': return 'color:#10b981;font-weight:bold'
        if val == 'Optimasi': return 'color:#f59e0b;font-weight:bold'
        if val == 'Relocate': return 'color:#ef4444;font-weight:bold'
        if val == 'Tidak Aktif': return 'color:#94a3b8;font-weight:bold'
        return ''
    styled = display_df.style.map(style_status, subset=["Status"])

    def color_by_delta(series, delta_series):
        d = delta_series.reindex(series.index).fillna(0)
        return ['color:#10b981;font-weight:600' if x>0 else ('color:#ef4444;font-weight:600' if x<0 else '') for x in d]

    if compare_period:
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_omset_delta']), axis=0, subset=['Omset Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_foto_delta']), axis=0, subset=['Foto Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_unlock_delta']), axis=0, subset=['Unlock Compare'])
        styled = styled.apply(lambda s: color_by_delta(s, table_sorted['_conv_delta']), axis=0, subset=['Conversion Compare'])
    styled = styled.format({
        "Omset": format_number_with_dots,
        "Foto": format_number_with_dots,
        "Unlock": format_number_with_dots,
        "Conversion": lambda v: format_decimal_with_comma(v, 1, "%"),
    })

    column_config = None
    if HAS_COLUMN_CONFIG:
        column_config = {
            "Outlet": text_col("Outlet", width="medium"),
            "Area": text_col("Area", width="small"),
            "Omset Compare": text_col("Omset Compare", width="medium"),
            "Foto Compare": text_col("Foto Compare", width="small"),
            "Unlock Compare": text_col("Unlock Compare", width="small"),
            "Conversion Compare": text_col("Conversion Compare", width="small"),
            "Status": text_col("Status", width="small"),
        }

    mobile_df = display_df.copy()
    for col in ("Omset", "Foto", "Unlock"):
        if col in mobile_df.columns:
            mobile_df[col] = mobile_df[col].apply(format_number_with_dots)
    if "Conversion" in mobile_df.columns:
        mobile_df["Conversion"] = mobile_df["Conversion"].apply(lambda v: format_decimal_with_comma(v, 1, "%"))
    mobile_rows = [
        ("Area", "Area"),
        ("Omset", "Omset"),
        ("Foto", "Foto"),
        ("Unlock", "Unlock"),
        ("Conversion", "Conversion"),
    ]
    if compare_period:
        mobile_rows.extend([
            ("Omset vs compare", "Omset Compare"),
            ("Foto vs compare", "Foto Compare"),
            ("Unlock vs compare", "Unlock Compare"),
            ("Conversion vs compare", "Conversion Compare"),
        ])
    render_mobile_cards(mobile_df, "Outlet", mobile_rows, status_col="Status", max_rows=25)
    st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
    df_show(styled, use_container_width=True, hide_index=True, column_config=column_config)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ================= OMSET TREND TABLE =================

def _list_last_n_periods(anchor_period: str, n: int) -> List[str]:
    try:
        y, m = map(int, anchor_period.split("-"))
    except Exception:
        dt = pd.to_datetime(anchor_period, errors="coerce")
        if pd.isna(dt): return []
        y, m = dt.year, dt.month
    out = []
    for k in range(n):
        total = y * 12 + (m - 1) - k
        yy = total // 12
        mm = (total % 12) + 1
        out.append(f"{yy:04d}-{mm:02d}")
    return out


def show_omset_trend_table(df_filtered: pd.DataFrame, df_full: pd.DataFrame, config: Config, current_period: Optional[str], months: int = 12):
    st.subheader("📆 Tren Omset Outlet (12 Bulan)")
    if df_full.empty or "outlet_name" not in df_full.columns or "periode" not in df_full.columns:
        st.info("Data tidak cukup untuk menampilkan tren omset."); return

    visible_outlets = df_full["outlet_name"].dropna().astype(str).str.strip().unique().tolist()
    trend_df = df_full[df_full["outlet_name"].astype(str).str.strip().isin(visible_outlets)].copy()
    if trend_df.empty:
        st.info("Tidak ada data tren untuk outlet terpilih."); return

    trend_df["outlet_name"] = trend_df["outlet_name"].astype(str).str.strip()
    trend_df["total_revenue"] = pd.to_numeric(trend_df.get("total_revenue", 0), errors="coerce").fillna(0.0)

    from app import _sort_periods_str
    anchor = current_period if (current_period and isinstance(current_period, str)) else (
        _sort_periods_str([str(x) for x in trend_df["periode"].dropna().unique().tolist()])[-1]
        if trend_df["periode"].notna().any() else None
    )
    if not anchor:
        st.info("Periode kosong."); return

    periods_window = _list_last_n_periods(anchor, months)
    if not periods_window:
        st.info("Gagal menentukan window periode."); return

    active_period = current_period if current_period else anchor
    active_outlets = set(
        trend_df.loc[trend_df["periode"].astype(str) == str(active_period), "outlet_name"]
        .dropna().astype(str).str.strip().tolist()
    )

    pivot = (
        trend_df.pivot_table(
            index="outlet_name",
            columns="periode",
            values="total_revenue",
            aggfunc="sum",
        )
        .reindex(columns=periods_window)
        .sort_index()
    )

    value_cols = periods_window

    def _avg_real_row(row: pd.Series) -> float:
        vals = [float(v) for v in row.tolist() if (pd.notna(v) and float(v) > 0.0)]
        return float(np.mean(vals)) if len(vals) > 0 else 0.0

    avg_real = pivot.apply(_avg_real_row, axis=1)
    display_pivot = pivot.fillna(0.0)

    display_df = display_pivot.reset_index().rename(columns={"outlet_name": "Outlet"})
    display_df.insert(1, "Rata-rata", avg_real.values)

    st.info("🔽 Sorting Tren Omset")
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        sort_by = st.selectbox("Urutkan berdasarkan", ["Rata-rata", "Outlet"], index=0, key="trend_sort_by")
    with sc2:
        sort_order = st.selectbox("Urutan", ["Descending (High to Low)", "Ascending (Low to High)"], index=0, key="trend_sort_order")
    ascending = (sort_order == "Ascending (Low to High)")
    if sort_by == "Outlet":
        display_df_sorted = display_df.sort_values(by="Outlet", ascending=ascending, kind="mergesort")
    else:
        display_df_sorted = display_df.sort_values(by="Rata-rata", ascending=ascending, kind="mergesort")
    display_df_sorted["_aktif_current"] = display_df_sorted["Outlet"].astype(str).isin(active_outlets)

    def _growth_colors(row: pd.Series):
        vals = row[value_cols]
        cells = []
        last_index = len(vals) - 1
        for j in range(len(vals)):
            if j == last_index:
                cells.append("")
            else:
                cur = float(vals.iloc[j]) if pd.notna(vals.iloc[j]) else 0.0
                prv = float(vals.iloc[j+1]) if pd.notna(vals.iloc[j+1]) else 0.0
                if cur > prv:
                    cells.append("color:#10b981;font-weight:600")
                elif cur < prv:
                    cells.append("color:#ef4444;font-weight:600")
                else:
                    cells.append("")
        return cells

    def _fmt_currency(x, _cfg=config):
        try:
            v = 0.0 if (x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x)))) else float(x)
            return _cfg.format_currency(v)
        except Exception:
            return _cfg.format_currency(0.0)

    fmt_map = {col: _fmt_currency for col in value_cols}
    fmt_map["Rata-rata"] = _fmt_currency

    column_config = None
    if HAS_COLUMN_CONFIG:
        column_config = {
            "Outlet": text_col("Outlet", width="medium"),
        }

    active_df = display_df_sorted[display_df_sorted["_aktif_current"]].drop(columns=["_aktif_current"])
    inactive_df = display_df_sorted[~display_df_sorted["_aktif_current"]].drop(columns=["_aktif_current"])

    st.markdown("**Outlet Aktif**")
    if active_df.empty:
        st.info("Tidak ada outlet aktif di periode ini.")
    else:
        active_mobile = active_df.copy()
        for col, formatter in fmt_map.items():
            if col in active_mobile.columns:
                active_mobile[col] = active_mobile[col].apply(formatter)
        render_mobile_cards(
            active_mobile,
            "Outlet",
            [("Rata-rata", "Rata-rata")] + [(p, p) for p in value_cols[:4]],
            max_rows=20,
        )
        styled_active = active_df.style.apply(_growth_colors, axis=1, subset=value_cols).format(fmt_map)
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(styled_active, use_container_width=True, hide_index=True, column_config=column_config)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("**Outlet Tidak Aktif di Periode Ini**")
    if inactive_df.empty:
        st.info("Tidak ada outlet tidak aktif di periode ini.")
    else:
        inactive_mobile = inactive_df.copy()
        for col, formatter in fmt_map.items():
            if col in inactive_mobile.columns:
                inactive_mobile[col] = inactive_mobile[col].apply(formatter)
        render_mobile_cards(
            inactive_mobile,
            "Outlet",
            [("Rata-rata", "Rata-rata")] + [(p, p) for p in value_cols[:4]],
            max_rows=20,
        )
        styled_inactive = inactive_df.style.apply(_growth_colors, axis=1, subset=value_cols).format(fmt_map)
        st.markdown('<div class="mobile-table-muted">', unsafe_allow_html=True)
        df_show(styled_inactive, use_container_width=True, hide_index=True, column_config=column_config)
        st.markdown('</div>', unsafe_allow_html=True)
    s_caption("Nilai kosong ditampilkan sebagai 0. Rata-rata dihitung dari 12 bulan tampil (termasuk current), hanya omset > 0 yang dihitung. Hijau=naik vs bulan lalu; Merah=turun.")

    # ===== DOWNLOAD EXCEL (ANGKA MURNI) =====
    st.markdown("### 📥 Download Data")
    _export_trend_excel(display_df_sorted.drop(columns=["_aktif_current"]), value_cols)


# ================= MAIN DASHBOARD PAGE =================

def show_main_dashboard(df, config, processor, viz, current_period, compare_period, full_df):
    st.markdown('<h1 class="main-header">📸 backup-dower</h1>', unsafe_allow_html=True)
    if df.empty:
        st.error("❌ Data tidak tersedia. Silakan upload data terlebih dahulu."); return

    m_df = df.copy(deep=True)
    for col in ["total_revenue","foto_qty","unlock_qty","print_qty","conversion_rate"]:
        if col in m_df.columns:
            m_df[col] = pd.to_numeric(m_df[col], errors="coerce").fillna(0)

    metrics = processor.calculate_metrics(m_df) if hasattr(processor, "calculate_metrics") else {
        "total_revenue": m_df["total_revenue"].sum(),
        "total_outlets": m_df["outlet_name"].nunique(),
        "avg_conversion": (m_df["conversion_rate"].mean() if "conversion_rate" in m_df.columns else 0),
        "total_photos": (m_df["foto_qty"].sum() if "foto_qty" in m_df.columns else 0),
    }

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("💰 Revenue", config.format_currency(metrics['total_revenue']))
    with c2: st.metric("🏪 Outlets", f"{metrics['total_outlets']}")
    with c3: st.metric("📈 Avg Conv Rate", f"{metrics['avg_conversion']:.1f}%")
    with c4: st.metric("📸 Photos", format_number_with_dots(metrics['total_photos']))
    st.markdown("---")

    create_outlet_table(m_df, current_period, compare_period, full_df=full_df)

    if m_df.empty:
        st.info("Tidak ada transaksi aktif di periode terpilih untuk filter ini. Outlet historis tetap tampil sebagai Tidak Aktif.")
        st.markdown("---")
        show_omset_trend_table(df_filtered=m_df, df_full=full_df, config=config, current_period=current_period, months=12)
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📊 Distribusi Status Outlet")
        st.plotly_chart(viz.create_status_distribution(m_df), use_container_width=True)
    with col2:
        st.subheader("🏆 Top 5 Performers")
        top = processor.get_top_performers(m_df, 5) if hasattr(processor, "get_top_performers") else m_df.sort_values("total_revenue", ascending=False).head(5)
        for _, row in top.iterrows():
            status_class = f"status-{str(row['outlet_status']).lower()}"
            st.markdown(f"""
            <div class="performer-card">
                <strong>{row['outlet_name']}</strong><br>
                <span class="{status_class}">{row['outlet_status']}</span> | 
                <span>{config.format_currency(row['total_revenue'])}</span> | 
                <span>{row['conversion_rate']:.1f}%</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    a, b = st.columns([2, 1])
    with a:
        st.subheader("💹 Revenue by Outlet")
        st.plotly_chart(viz.create_revenue_chart(m_df), use_container_width=True)
    with b:
        st.subheader("🔄 Conversion Funnel")
        st.plotly_chart(viz.create_conversion_funnel(m_df), use_container_width=True)

    st.markdown("---")
    st.subheader("💡 Key Insights")
    for insight in generate_insights(m_df, config):
        st.markdown(f'<div class="insight-box">{insight}</div>', unsafe_allow_html=True)

    st.markdown("---")
    show_omset_trend_table(df_filtered=m_df, df_full=full_df, config=config, current_period=current_period, months=12)
