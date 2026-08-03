"""
Dashboard adapter for NiceGUI — wraps Streamlit's Config, DataProcessor,
Visualizations and data loading for full functional parity.
"""
import sys
from pathlib import Path
from typing import Optional, List

import pandas as pd
import numpy as np

# Add streamlit_template to path so we can import its modules
STREAMLIT_DIR = Path(__file__).resolve().parent.parent.parent / "streamlit_template"
if str(STREAMLIT_DIR) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_DIR))

from config import Config
from data_processor import DataProcessor
from visualizations import Visualizations
from utils import generate_insights


def _sort_periods_str(periods: List[str]) -> List[str]:
    """Sort period strings like '2024-01' chronologically."""
    s = pd.Series(periods, dtype=object)
    dt = pd.to_datetime(s, format="%Y-%m", errors="coerce")
    helper = pd.DataFrame({"p": s, "dt": dt}).sort_values(by=["dt", "p"], na_position="last")
    return helper["p"].astype(str).tolist()


class DashboardAdapter:
    """Wraps Streamlit dashboard classes for NiceGUI use."""

    def __init__(self):
        self.config = Config()
        self.processor = DataProcessor()
        self.viz = Visualizations(self.config)

    def load_data(self) -> pd.DataFrame:
        """Load main dashboard data from dashboard_summary.json (built from raw_by_month).
        Falls back to CSV if cache is missing."""
        try:
            from services.difotoin_api_adapter import load_dashboard_summary
            data = load_dashboard_summary()
            if data:
                df = pd.DataFrame(data)
                if not df.empty:
                    df = self.processor.apply_outlet_mapping(df)
                    return df
        except Exception as e:
            print("[WARN] Dashboard cache error: %s. Falling back to CSV." % e)
        print("[WARN] Dashboard cache unavailable. Using CSV fallback.")
        return self.processor.load_data()

    def load_full_data(self) -> pd.DataFrame:
        """Load full unfiltered data (same as load_data now)."""
        return self.load_data()

    def get_periods(self, df: pd.DataFrame) -> List[str]:
        """Get sorted list of unique periods."""
        if df.empty or "periode" not in df.columns:
            return []
        periods = sorted([str(p) for p in df["periode"].dropna().unique()])
        return periods

    def filter_data(self, df: pd.DataFrame, area: str = "Semua",
                    kategori: str = "Semua", tipe: str = "Semua",
                    periode: Optional[str] = None) -> pd.DataFrame:
        """Apply filters matching Streamlit sidebar behavior."""
        return self.processor.filter_data(df, area, kategori, tipe, periode)

    def get_unique_values(self, df: pd.DataFrame, col: str) -> List[str]:
        """Get sorted unique values for a column."""
        if df.empty or col not in df.columns:
            return []
        vals = df[col].dropna().unique().tolist()
        vals.sort(key=str.lower)
        return vals

    def calculate_metrics(self, df: pd.DataFrame) -> dict:
        """Calculate KPI metrics — same as Streamlit."""
        return self.processor.calculate_metrics(df)

    def get_top_performers(self, df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
        """Top N performers by revenue."""
        return self.processor.get_top_performers(df, n)

    def get_worst_performers(self, df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
        """Bottom N performers by revenue."""
        return df.nsmallest(n, "total_revenue")

    def format_currency(self, amount: float) -> str:
        """Format as IDR currency."""
        return self.config.format_currency(amount)

    def get_insights(self, df: pd.DataFrame) -> List[str]:
        """Generate insight text."""
        return generate_insights(df, self.config)

    def get_status_distribution(self, df: pd.DataFrame) -> dict:
        """Get outlet status distribution counts."""
        if df.empty or "outlet_status" not in df.columns:
            return {}
        return df["outlet_status"].value_counts().to_dict()

    def format_number(self, num) -> str:
        """Format number with dot separators (Indonesian style)."""
        try:
            return f"{int(round(float(num))):,}".replace(",", ".")
        except (ValueError, TypeError):
            return str(num)

    def format_pct(self, val, decimals: int = 1) -> str:
        """Format as percentage with comma decimal."""
        try:
            return f"{float(val):.{decimals}f}".replace(".", ",") + "%"
        except (ValueError, TypeError):
            return str(val)

    def format_comparison(self, current_val, compare_val, is_pct=False):
        """Format comparison delta matching Streamlit."""
        if compare_val == 0:
            return "0.0%" if not is_pct else "0.0pp"
        if is_pct:
            change = float(current_val) - float(compare_val)
            sign = "+" if change > 0 else ""
            return f"{sign}{change:.1f}pp" if change != 0 else "0.0pp"
        change_pct = ((float(current_val) - float(compare_val)) / float(compare_val)) * 100
        sign = "+" if change_pct > 0 else ""
        return f"{sign}{change_pct:.1f}%" if change_pct != 0 else "0.0%"

    # ── Trend Table Helpers ──

    def get_last_n_periods(self, anchor_period: str, n: int = 12) -> List[str]:
        """Get last N periods from anchor."""
        try:
            y, m = map(int, anchor_period.split("-"))
        except Exception:
            dt = pd.to_datetime(anchor_period, errors="coerce")
            if pd.isna(dt):
                return []
            y, m = dt.year, dt.month
        out = []
        for k in range(n):
            total = y * 12 + (m - 1) - k
            yy = total // 12
            mm = (total % 12) + 1
            out.append(f"{yy:04d}-{mm:02d}")
        return out

    def build_trend_table(self, df_full: pd.DataFrame, current_period: Optional[str],
                          visible_outlets: list, months: int = 12) -> dict:
        """Build omset trend table data matching Streamlit's show_omset_trend_table.

        Returns dict with:
          - active_df: DataFrame for active outlets
          - inactive_df: DataFrame for inactive outlets
          - value_cols: list of period column names
          - has_data: bool
        """
        result = {
            "active_df": pd.DataFrame(),
            "inactive_df": pd.DataFrame(),
            "value_cols": [],
            "has_data": False,
        }

        if df_full.empty or "outlet_name" not in df_full.columns or "periode" not in df_full.columns:
            return result

        trend_df = df_full[df_full["outlet_name"].astype(str).str.strip().isin(visible_outlets)].copy()
        if trend_df.empty:
            return result

        trend_df["outlet_name"] = trend_df["outlet_name"].astype(str).str.strip()
        trend_df["total_revenue"] = pd.to_numeric(trend_df.get("total_revenue", 0), errors="coerce").fillna(0.0)

        # Determine anchor period
        if current_period and isinstance(current_period, str):
            anchor = current_period
        else:
            periods = [str(x) for x in trend_df["periode"].dropna().unique().tolist()]
            if periods:
                sorted_p = _sort_periods_str(periods)
                anchor = sorted_p[-1] if sorted_p else None
            else:
                anchor = None

        if not anchor:
            return result

        periods_window = self.get_last_n_periods(anchor, months)
        if not periods_window:
            return result

        active_period = current_period if current_period else anchor
        active_outlets = set(
            trend_df.loc[trend_df["periode"].astype(str) == str(active_period), "outlet_name"]
            .dropna().astype(str).str.strip().tolist()
        )

        # Pivot
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

        # Bulan berjalan (masih berjalan / datanya partial) TIDAK dihitung dalam rata-rata.
        # Hanya exclude kalau periode aktif == bulan kalender sekarang (masih jalan).
        # Kalau periode aktif adalah bulan lampau yang sudah selesai, tetap dihitung.
        current_cal_month = pd.Timestamp.now().strftime("%Y-%m")
        avg_exclude = str(active_period) if str(active_period) == current_cal_month else None
        avg_cols = [c for c in periods_window if str(c) != avg_exclude] if avg_exclude else periods_window

        def _avg_real_row(row: pd.Series) -> float:
            vals = [
                float(row[c]) for c in avg_cols
                if (pd.notna(row[c]) and float(row[c]) > 0.0)
            ]
            return float(np.mean(vals)) if len(vals) > 0 else 0.0

        avg_real = pivot.apply(_avg_real_row, axis=1)
        display_pivot = pivot.fillna(0.0)

        display_df = display_pivot.reset_index().rename(columns={"outlet_name": "Outlet"})
        display_df.insert(1, "Rata-rata", avg_real.values)

        display_df["_aktif_current"] = display_df["Outlet"].astype(str).isin(active_outlets)

        # Sort by Rata-rata descending (like Streamlit default)
        display_df_sorted = display_df.sort_values(by="Rata-rata", ascending=False, kind="mergesort")

        active = display_df_sorted[display_df_sorted["_aktif_current"]].drop(columns=["_aktif_current"]).reset_index(drop=True)
        inactive = display_df_sorted[~display_df_sorted["_aktif_current"]].drop(columns=["_aktif_current"]).reset_index(drop=True)

        # Format currency columns — pakai TITIK ribuan (konsisten dgn tabel dashboard lain,
        # dan bikin comparator sort numerik di AG Grid bekerja: Rp 133.872.727)
        def fmt_func(v):
            return "Rp {:,.0f}".format(round(float(v or 0))).replace(",", ".")
        for col in value_cols + ["Rata-rata"]:
            if col in active.columns:
                active[col] = active[col].apply(fmt_func)
            if col in inactive.columns:
                inactive[col] = inactive[col].apply(fmt_func)

        result["active_df"] = active
        result["inactive_df"] = inactive
        result["value_cols"] = value_cols
        result["has_data"] = True
        return result

    def build_daily_trend_table(self, daily_df, visible_outlets, days=30, end_date=None) -> dict:
        """Build daily omset trend: outlet rows x last N days (ending H-1/yesterday).

        daily_df must have columns: outlet_name, date (YYYY-MM-DD), revenue.
        Returns dict: {df, value_cols, has_data}
        - value_cols: day columns newest -> oldest
        - df columns: Outlet, Total 30 Hari, then one column per day (formatted "Rp 1.234.567")
        - rows sorted by Total 30 Hari descending
        """
        result = {"df": pd.DataFrame(), "value_cols": [], "has_data": False}
        if (
            daily_df is None or daily_df.empty
            or "outlet_name" not in daily_df.columns
            or "date" not in daily_df.columns
            or "revenue" not in daily_df.columns
        ):
            return result
        df = daily_df.copy()
        df["outlet_name"] = df["outlet_name"].astype(str).str.strip()
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["revenue"] = pd.to_numeric(df.get("revenue", 0), errors="coerce").fillna(0.0)
        df = df[df["outlet_name"].isin(visible_outlets)].copy()
        if df.empty:
            return result

        if end_date is None:
            end_date = pd.Timestamp.now().normalize() - pd.Timedelta(days=1)  # H-1
        else:
            end_date = pd.Timestamp(end_date).normalize()
        start_date = end_date - pd.Timedelta(days=days - 1)

        date_asc = pd.date_range(start_date, end_date).strftime("%Y-%m-%d").tolist()
        date_desc = list(reversed(date_asc))

        df = df[
            (df["date"] >= date_asc[0]) & (df["date"] <= date_asc[-1])
        ]
        if df.empty:
            return result

        pivot = (
            df.pivot_table(index="outlet_name", columns="date", values="revenue", aggfunc="sum")
            .reindex(columns=date_asc)
            .fillna(0.0)
        )
        display_df = pivot.reset_index().rename(columns={"outlet_name": "Outlet"})
        total = pivot.sum(axis=1)
        display_df.insert(1, "Total 30 Hari", total.values)
        display_df = display_df.sort_values("Total 30 Hari", ascending=False).reset_index(drop=True)

        def _fmt(v):
            return "Rp {:,.0f}".format(round(float(v or 0))).replace(",", ".")

        for col in ["Total 30 Hari"] + date_desc:
            display_df[col] = display_df[col].apply(_fmt)

        result["df"] = display_df
        result["value_cols"] = date_desc
        result["has_data"] = True
        return result


# Singleton
_adapter: Optional[DashboardAdapter] = None


def get_adapter() -> DashboardAdapter:
    global _adapter
    if _adapter is None:
        _adapter = DashboardAdapter()
    return _adapter
