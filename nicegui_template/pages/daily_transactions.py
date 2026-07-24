"""
📊 Transaksi Harian — daily transaction dashboard.
Data source: daily_summary.json (pre-computed from raw_by_month)
"""
import json
from datetime import datetime, timedelta, date
from pathlib import Path

from nicegui import ui
import pandas as pd

# ── Paths ──
DAILY_SUMMARY_PATH = Path(__file__).resolve().parent.parent.parent
DAILY_SUMMARY_PATH = DAILY_SUMMARY_PATH / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"

CARD = "background:#1e1e2e;border-radius:12px;padding:20px;box-shadow:0 4px 12px rgba(0,0,0,0.3);"
MV = "font-size:1.3rem;font-weight:700;color:#cdd6f4;"
ML = "font-size:0.8rem;color:#a6adc8;text-transform:uppercase;letter-spacing:0.5px;"

_df_cache = None


def _load_data() -> pd.DataFrame:
    """Load daily summary data."""
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    try:
        if not DAILY_SUMMARY_PATH.exists():
            return pd.DataFrame()
        with open(DAILY_SUMMARY_PATH) as f:
            data = json.load(f)
        _df_cache = pd.DataFrame(data)
        for col in ["date", "outlet_name"]:
            if col in _df_cache.columns:
                _df_cache[col] = _df_cache[col].astype(str)
        for col in ["sessions", "unlocks", "unlocks_paid", "prints"]:
            if col in _df_cache.columns:
                _df_cache[col] = pd.to_numeric(_df_cache[col], errors="coerce").fillna(0).astype(int)
        for col in ["revenue", "conversion_rate", "print_rate", "avg_revenue_per_session"]:
            if col in _df_cache.columns:
                _df_cache[col] = pd.to_numeric(_df_cache[col], errors="coerce").fillna(0)
        return _df_cache
    except Exception:
        return pd.DataFrame()


def _fmt_rp(v):
    try:
        return f"Rp {int(round(float(v))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"


def _fmt_pct(v):
    try:
        return f"{float(v):.1f}".replace(".", ",") + "%"
    except (ValueError, TypeError):
        return "0,0%"


def _fmt_n(v):
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(v)


def _get_available_dates(df: pd.DataFrame) -> list:
    if df.empty or "date" not in df.columns:
        return []
    dates = sorted(df["date"].dropna().unique().tolist(), reverse=True)
    return dates


def _date_label(d: str) -> str:
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        today = date.today()
        if dt.date() == today:
            return f"Hari Ini ({d})"
        yesterday = today - timedelta(days=1)
        if dt.date() == yesterday:
            return f"Kemarin ({d})"
        days = (today - dt.date()).days
        return f"{dt.strftime('%d %b %Y')} ({days}h lalu)"
    except Exception:
        return d


def create_page(container):
    """Create the daily transaction page."""
    df = _load_data()
    dates = _get_available_dates(df)
    
    if df.empty or not dates:
        with container:
            ui.label("📊 Transaksi Harian").classes("text-2xl font-bold text-white mb-4")
            ui.label("⏳ Data belum tersedia. Tunggu sync berikutnya.").classes("text-gray-400")
        return
    
    selected_date = dates[0]  # default to latest
    
    with container:
        ui.add_head_html("""<style>
            .daily-card:hover { transform: translateY(-2px); transition: all 0.2s; }
        </style>""")
        
        # ── Header ──
        with ui.row().classes("w-full items-center gap-3 mb-2"):
            ui.label("📊").classes("text-3xl")
            ui.label("Transaksi Harian").classes("text-2xl font-bold text-white")
            ui.label("— Per Outlet").classes("text-lg text-gray-400")
            ui.label(f"• {datetime.now().strftime('%d %b %Y %H:%M')}").classes(
                "text-xs text-gray-500 ml-auto"
            )
        ui.separator().classes("mb-4")
        
        # ── Date Picker ──
        date_select = ui.select(
            dates,
            value=selected_date,
            label="Pilih Tanggal",
        ).props("dense outlined dark").classes("w-72 mb-4")
        
        # Container for content
        content = ui.column().classes("w-full")
        
        def _render(sel_date: str):
            content.clear()
            if not sel_date or sel_date not in dates:
                return
            
            # Filter data for selected date
            day_df = df[df["date"] == sel_date].copy()
            if day_df.empty:
                with content:
                    ui.label(f"Tidak ada data untuk {sel_date}").classes("text-gray-400")
                return
            
            # ── Summary Cards ──
            total_rev = day_df["revenue"].sum()
            total_sessions = day_df["sessions"].sum()
            total_unlocks = day_df["unlocks_paid"].sum()
            total_prints = day_df["prints"].sum()
            active_outlets = len(day_df[day_df["sessions"] > 0])
            conv_rate = (total_unlocks / total_sessions * 100) if total_sessions > 0 else 0
            
            with content:
                with ui.row().classes("w-full gap-4 mb-6"):
                    cards = [
                        ("💰 Total Revenue", _fmt_rp(total_rev), "#89b4fa"),
                        ("📸 Sessions", _fmt_n(total_sessions), "#a6e3a1"),
                        ("🔓 Unlock Berbayar", _fmt_n(total_unlocks), "#f9e2af"),
                        ("🖨️ Print", _fmt_n(total_prints), "#f38ba8"),
                        ("🏪 Outlet Aktif", _fmt_n(active_outlets), "#cba6f7"),
                        ("📈 Konversi", _fmt_pct(conv_rate), "#94e2d5"),
                    ]
                    for label, value, color in cards:
                        with ui.card().classes("daily-card flex-1 min-w-[140px]").style(CARD):
                            ui.label(label).classes("text-xs").style(f"color:{color};text-transform:uppercase;letter-spacing:0.5px;")
                            ui.label(value).classes("text-xl font-bold text-white mt-1")
                
                # ── Date context ──
                try:
                    sel_dt = datetime.strptime(sel_date, "%Y-%m-%d").date()
                    prev_date = (sel_dt - timedelta(days=1)).isoformat()
                    if prev_date in dates:
                        prev_df = df[df["date"] == prev_date]
                        prev_rev = prev_df["revenue"].sum()
                        diff = total_rev - prev_rev
                        pct = (diff / prev_rev * 100) if prev_rev > 0 else 0
                        arrow = "🟢" if diff >= 0 else "🔴"
                        ui.label(f"{arrow} {_date_label(sel_date)} vs {prev_date}: {_fmt_rp(diff)} ({pct:+.1f}%)").classes(
                            "text-xs text-gray-400 mb-4"
                        )
                except Exception:
                    pass
                
                # ── Outlet Table ──
                ui.label("📋 Perbandingan Outlet").classes("text-sm font-semibold text-gray-300 mb-2")
                
                table_df = day_df.sort_values("revenue", ascending=False).reset_index(drop=True)
                table_df["#"] = range(1, len(table_df) + 1)
                table_df["Revenue"] = table_df["revenue"].apply(_fmt_rp)
                table_df["Sesi"] = table_df["sessions"].apply(_fmt_n)
                table_df["Unlock"] = table_df["unlocks_paid"].apply(_fmt_n)
                table_df["Print"] = table_df["prints"].apply(_fmt_n)
                table_df["Konversi"] = table_df["conversion_rate"].apply(_fmt_pct)
                
                display_cols = ["#", "outlet_name", "Revenue", "Sesi", "Unlock", "Print", "Konversi"]
                display_df = table_df[display_cols].rename(columns={"outlet_name": "Outlet"})
                
                # Highlight row styling
                rows_html = ""
                for _, row in display_df.iterrows():
                    bg = "background:#2a2a3e" if row["#"] % 2 == 0 else ""
                    rows_html += f"<tr style='{bg}border-bottom:1px solid #313244;'>"
                    for col in display_cols:
                        align = "right" if col != "#" and col != "Outlet" else "left"
                        style = f"padding:6px 10px;text-align:{align};font-size:12px;"
                        if col == "Revenue":
                            style += "color:#89b4fa;font-weight:600;"
                        rows_html += f"<td style='{style}'>{row[col]}</td>"
                    rows_html += "</tr>"
                
                html = f"""<div style="overflow-x:auto;border-radius:8px;border:1px solid #313244;background:#1e1e2e;">
                    <table style="width:100%;border-collapse:collapse;">
                        <thead>
                            <tr style="background:#181825;border-bottom:2px solid #313244;">
                                {''.join(f'<th style="padding:8px 10px;text-align:{"right" if c!="#" and c!="Outlet" else "left"};font-size:11px;color:#a6adc8;text-transform:uppercase;">{c}</th>' for c in display_cols)}
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                </div>"""
                ui.html(html).classes("w-full")
        
        # Date change handler
        def _on_date_change(e):
            _render(e.value)
        
        date_select.on("update:model-value", _on_date_change)
        
        # Initial render
        _render(selected_date)
