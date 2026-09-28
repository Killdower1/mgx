"""Mobile-first outlet sales view for APK/PWA MVP."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from nicegui import ui

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "streamlit_template" / "data" / "api_cache"
DAILY_SUMMARY_PATH = DATA_ROOT / "daily_summary.json"

_DF_CACHE = None
_DF_CACHE_MTIME = None

BG = "#0b1020"
PANEL = "#111827"
PANEL_2 = "#162033"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
BLUE = "#60a5fa"
GREEN = "#34d399"
RED = "#fb7185"
YELLOW = "#fbbf24"
PURPLE = "#c084fc"

STYLE = """
<style>
.mobile-shell { max-width: 560px; margin: 0 auto; padding: 14px 12px 88px; background:#0b1020; min-height:100vh; }
.mobile-card { background:#111827; border:1px solid rgba(148,163,184,.14); border-radius:18px; box-shadow:0 10px 30px rgba(0,0,0,.25); }
.metric-card { background:linear-gradient(145deg,#111827,#162033); border:1px solid rgba(148,163,184,.12); border-radius:16px; padding:12px; }
.outlet-row { background:#111827; border:1px solid rgba(148,163,184,.12); border-radius:14px; padding:10px 12px; }
.sticky-filter { position:sticky; top:54px; z-index:5; background:rgba(11,16,32,.92); backdrop-filter: blur(10px); padding:8px 0; }
@media (max-width: 640px) {
  .nicegui-content { padding:0 !important; }
  body { background:#0b1020 !important; }
}
</style>
"""


def _load_df(force: bool = False) -> pd.DataFrame:
    """Load daily summary cache. Keep the frame small enough for mobile views."""
    global _DF_CACHE, _DF_CACHE_MTIME
    try:
        if not DAILY_SUMMARY_PATH.exists():
            return pd.DataFrame()
        mtime = DAILY_SUMMARY_PATH.stat().st_mtime
        if _DF_CACHE is not None and _DF_CACHE_MTIME == mtime and not force:
            return _DF_CACHE.copy()
        with DAILY_SUMMARY_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        df = pd.DataFrame(raw)
        if df.empty:
            return df
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        for col in ["revenue", "total_revenue", "sessions", "foto_qty", "unlocks", "unlocks_paid", "unlock_qty", "prints", "print_qty", "conversion_rate", "print_rate"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        if "revenue" not in df.columns and "total_revenue" in df.columns:
            df["revenue"] = df["total_revenue"]
        if "sessions" not in df.columns and "foto_qty" in df.columns:
            df["sessions"] = df["foto_qty"]
        if "unlocks_paid" not in df.columns and "unlock_qty" in df.columns:
            df["unlocks_paid"] = df["unlock_qty"]
        if "prints" not in df.columns and "print_qty" in df.columns:
            df["prints"] = df["print_qty"]
        if "outlet_name" not in df.columns:
            df["outlet_name"] = "Unknown"
        _DF_CACHE = df
        _DF_CACHE_MTIME = mtime
        return df.copy()
    except Exception as exc:
        print(f"[mobile_sales] load error: {exc}")
        return pd.DataFrame()


def _fmt_rp(value) -> str:
    try:
        return "Rp " + f"{float(value):,.0f}".replace(",", ".")
    except Exception:
        return "Rp 0"


def _fmt_short_rp(value) -> str:
    try:
        v = float(value)
        if abs(v) >= 1_000_000_000:
            return "Rp " + f"{v/1_000_000_000:.1f}".replace(".", ",") + " M"
        if abs(v) >= 1_000_000:
            return "Rp " + f"{v/1_000_000:.1f}".replace(".", ",") + " jt"
        return _fmt_rp(v)
    except Exception:
        return "Rp 0"


def _fmt_n(value) -> str:
    try:
        return f"{float(value):,.0f}".replace(",", ".")
    except Exception:
        return "0"


def _fmt_pct(value) -> str:
    try:
        return f"{float(value):.1f}%".replace(".", ",")
    except Exception:
        return "0,0%"


def _date_label(ts: pd.Timestamp) -> str:
    days = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    return f"{days[ts.weekday()]}, {ts.day} {months[ts.month-1]} {ts.year}"


def _latest_complete_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    dates = sorted(df["date"].dropna().unique()) if "date" in df.columns else []
    if not dates:
        return None
    today = pd.Timestamp.now().normalize()
    completed = [pd.Timestamp(d).normalize() for d in dates if pd.Timestamp(d).normalize() < today]
    return completed[-1] if completed else pd.Timestamp(dates[-1]).normalize()


def _safe_date(date_str: Optional[str], df: pd.DataFrame) -> Optional[pd.Timestamp]:
    if date_str:
        parsed = pd.to_datetime(date_str, errors="coerce")
        if not pd.isna(parsed):
            return pd.Timestamp(parsed).normalize()
    return _latest_complete_date(df)


def _sales_for_date(df: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    day_df = df[df["date"] == day].copy()
    if day_df.empty:
        return day_df
    grouped = day_df.groupby("outlet_name", dropna=False).agg({
        "revenue": "sum",
        "sessions": "sum",
        "unlocks_paid": "sum",
        "prints": "sum",
    }).reset_index()
    grouped = grouped.sort_values(["revenue", "sessions"], ascending=[False, False]).reset_index(drop=True)
    grouped["rank"] = grouped.index + 1
    return grouped


def get_sales_context(date_str: Optional[str] = None, search: str = "") -> dict:
    """Build a pure-Python context for tests, UI, and future API routes."""
    df = _load_df()
    if df.empty or "date" not in df.columns:
        return {"ok": False, "error": "Data penjualan belum tersedia", "rows": []}

    selected = _safe_date(date_str, df)
    if selected is None:
        return {"ok": False, "error": "Tanggal penjualan belum tersedia", "rows": []}

    today = pd.Timestamp.now().normalize()
    date_options = [pd.Timestamp(d).normalize() for d in sorted(df["date"].dropna().unique()) if pd.Timestamp(d).normalize() >= today - pd.Timedelta(days=45)]
    day_sales = _sales_for_date(df, selected)
    prev_week = _sales_for_date(df, selected - pd.Timedelta(days=7))
    prev_map = dict(zip(prev_week.get("outlet_name", []), prev_week.get("revenue", []))) if not prev_week.empty else {}

    if search:
        q = str(search).strip().lower()
        day_sales = day_sales[day_sales["outlet_name"].astype(str).str.lower().str.contains(q, na=False)].copy()

    rows = []
    for _, r in day_sales.iterrows():
        name = str(r.get("outlet_name") or "Unknown")
        revenue = float(r.get("revenue") or 0)
        sessions = float(r.get("sessions") or 0)
        unlocks = float(r.get("unlocks_paid") or 0)
        prints = float(r.get("prints") or 0)
        prev_rev = float(prev_map.get(name, 0) or 0)
        delta = revenue - prev_rev
        delta_pct = (delta / prev_rev * 100) if prev_rev > 0 else None
        rows.append({
            "rank": int(r.get("rank", 0) or 0),
            "outlet": name,
            "revenue": revenue,
            "sessions": sessions,
            "unlocks_paid": unlocks,
            "prints": prints,
            "conversion_rate": (unlocks / sessions * 100) if sessions > 0 else 0,
            "print_rate": (prints / unlocks * 100) if unlocks > 0 else 0,
            "prev_week_revenue": prev_rev,
            "delta": delta,
            "delta_pct": delta_pct,
        })

    all_day = _sales_for_date(df, selected)
    total_revenue = float(all_day["revenue"].sum()) if not all_day.empty else 0
    total_sessions = float(all_day["sessions"].sum()) if not all_day.empty else 0
    total_unlocks = float(all_day["unlocks_paid"].sum()) if not all_day.empty else 0
    total_prints = float(all_day["prints"].sum()) if not all_day.empty else 0
    active = int((all_day["revenue"] > 0).sum()) if not all_day.empty else 0
    total_outlets = int(all_day["outlet_name"].nunique()) if not all_day.empty else 0

    month_mask = (df["date"].dt.to_period("M") == selected.to_period("M")) & (df["date"] <= selected)
    mtd_revenue = float(df.loc[month_mask, "revenue"].sum()) if month_mask.any() else 0

    return {
        "ok": True,
        "selected_date": selected.strftime("%Y-%m-%d"),
        "selected_label": _date_label(selected),
        "is_partial_today": selected == today,
        "last_sync": datetime.fromtimestamp(DAILY_SUMMARY_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") if DAILY_SUMMARY_PATH.exists() else "-",
        "source_file": str(DAILY_SUMMARY_PATH),
        "date_options": [(d.strftime("%Y-%m-%d"), _date_label(d)) for d in date_options],
        "summary": {
            "revenue": total_revenue,
            "sessions": total_sessions,
            "unlocks_paid": total_unlocks,
            "prints": total_prints,
            "active_outlets": active,
            "total_outlets": total_outlets,
            "conversion_rate": (total_unlocks / total_sessions * 100) if total_sessions > 0 else 0,
            "print_rate": (total_prints / total_unlocks * 100) if total_unlocks > 0 else 0,
            "mtd_revenue": mtd_revenue,
        },
        "rows": rows,
    }


def _metric(label: str, value: str, sub: str, color: str):
    with ui.element("div").classes("metric-card"):
        ui.label(label).classes("text-[11px] uppercase tracking-wide").style(f"color:{color};")
        ui.label(value).classes("text-xl font-bold mt-1").style(f"color:{TEXT};")
        if sub:
            ui.label(sub).classes("text-[11px] mt-1").style(f"color:{MUTED};")


def _render_outlet_row(row: dict):
    delta = row.get("delta", 0)
    delta_pct = row.get("delta_pct")
    if delta_pct is None:
        delta_text = "vs minggu lalu: -"
        delta_color = MUTED
    else:
        arrow = "▲" if delta >= 0 else "▼"
        delta_text = f"{arrow} {_fmt_pct(abs(delta_pct))} vs H-7"
        delta_color = GREEN if delta >= 0 else RED

    with ui.element("div").classes("outlet-row w-full"):
        with ui.row().classes("w-full items-start gap-2 no-wrap"):
            ui.label(str(row["rank"])).classes("text-xs font-bold rounded-full w-7 h-7 items-center justify-center flex shrink-0").style(f"background:{PANEL_2};color:{MUTED};")
            with ui.column().classes("gap-0 flex-1 min-w-0"):
                ui.label(row["outlet"]).classes("text-sm font-semibold leading-tight").style(f"color:{TEXT};")
                ui.label(f"{_fmt_n(row['sessions'])} foto • {_fmt_n(row['unlocks_paid'])} unlock • {_fmt_n(row['prints'])} print").classes("text-[11px] mt-1").style(f"color:{MUTED};")
                ui.label(delta_text).classes("text-[11px] mt-1 font-semibold").style(f"color:{delta_color};")
            with ui.column().classes("gap-0 items-end shrink-0"):
                ui.label(_fmt_short_rp(row["revenue"])).classes("text-sm font-bold").style(f"color:{BLUE};")
                ui.label(_fmt_pct(row["conversion_rate"])).classes("text-[11px]").style(f"color:{MUTED};")


def create_page(container):
    """Render mobile/PWA sales page."""
    container.clear()
    state = {"date": None, "search": ""}

    with container:
        ui.add_head_html(STYLE)
        shell = ui.column().classes("mobile-shell w-full gap-3")

    def render():
        shell.clear()
        ctx = get_sales_context(state["date"], state["search"])
        with shell:
            with ui.row().classes("w-full items-center gap-2"):
                ui.label("📱").classes("text-2xl")
                with ui.column().classes("gap-0 flex-1"):
                    ui.label("Sales Outlet").classes("text-xl font-bold").style(f"color:{TEXT};")
                    ui.label("APK MVP — Penjualan Harian").classes("text-xs").style(f"color:{MUTED};")
                ui.button(icon="refresh", on_click=lambda: (_load_df(force=True), render())).props("flat round dense color=white")

            if not ctx.get("ok"):
                with ui.card().classes("mobile-card w-full p-4"):
                    ui.label(ctx.get("error", "Data belum tersedia")).classes("text-red-300")
                return

            summary = ctx["summary"]
            with ui.element("div").classes("mobile-card w-full p-4"):
                ui.label(ctx["selected_label"]).classes("text-sm font-semibold").style(f"color:{MUTED};")
                ui.label(_fmt_rp(summary["revenue"])).classes("text-3xl font-black mt-1").style(f"color:{TEXT};")
                partial = " • HARI INI/PARTIAL" if ctx["is_partial_today"] else " • hari lengkap"
                ui.label(f"{_fmt_n(summary['active_outlets'])}/{_fmt_n(summary['total_outlets'])} outlet aktif{partial}").classes("text-xs mt-1").style(f"color:{MUTED};")

            with ui.grid(columns=2).classes("w-full gap-2"):
                _metric("Foto/Sessions", _fmt_n(summary["sessions"]), "total foto", GREEN)
                _metric("Unlock Bayar", _fmt_n(summary["unlocks_paid"]), _fmt_pct(summary["conversion_rate"]), YELLOW)
                _metric("Print", _fmt_n(summary["prints"]), _fmt_pct(summary["print_rate"]), RED)
                _metric("MTD", _fmt_short_rp(summary["mtd_revenue"]), "bulan berjalan", PURPLE)

            with ui.column().classes("sticky-filter w-full gap-2"):
                options = {label: value for value, label in ctx["date_options"]}
                selected_label = next((label for label, value in options.items() if value == ctx["selected_date"]), ctx["selected_label"])
                ui.select(list(options.keys()), value=selected_label, label="Tanggal", on_change=lambda e: set_date(options.get(e.value))).props("dense outlined dark").classes("w-full")
                search = ui.input("Cari outlet", value=state["search"], placeholder="Ketik nama outlet...").props("dense outlined dark clearable").classes("w-full")
                search.on_value_change(lambda e: set_search(e.value or ""))

            ui.label(f"Semua Outlet ({len(ctx['rows'])})").classes("text-sm font-bold mt-1").style(f"color:{TEXT};")
            if not ctx["rows"]:
                ui.label("Tidak ada outlet cocok.").classes("text-sm").style(f"color:{MUTED};")
            else:
                for row in ctx["rows"]:
                    _render_outlet_row(row)

            ui.label(f"Sync: {ctx['last_sync']} • source: daily_summary.json").classes("text-[10px] mt-2 mb-3").style(f"color:{MUTED};")

    def set_date(date_value: Optional[str]):
        state["date"] = date_value
        render()

    def set_search(value: str):
        state["search"] = value
        render()

    render()
