"""Transaksi Harian — daily transaction dashboard, last 60 days."""
import json
from datetime import datetime
from pathlib import Path

from nicegui import ui
import pandas as pd

DAILY_SUMMARY_PATH = Path(__file__).resolve().parent.parent.parent
DAILY_SUMMARY_PATH = DAILY_SUMMARY_PATH / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"

CARD = "background:#1e1e2e;border-radius:12px;padding:20px;box-shadow:0 4px 12px rgba(0,0,0,0.3);"

_df_cache = None

def _load_data():
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    try:
        if not DAILY_SUMMARY_PATH.exists():
            return pd.DataFrame()
        with open(DAILY_SUMMARY_PATH) as f:
            data = json.load(f)
        _df_cache = pd.DataFrame(data)
        if "date" in _df_cache.columns:
            _df_cache["date"] = pd.to_datetime(_df_cache["date"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=90)
        _df_cache = _df_cache[_df_cache["date"] >= cutoff].copy()
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
        return "Rp " + ("{:,.0f}".format(round(float(v)))).replace(",", ".")
    except (ValueError, TypeError):
        return "Rp 0"

def _fmt_pct(v):
    try:
        return "{:.1f}".format(float(v)).replace(".", ",") + "%"
    except (ValueError, TypeError):
        return "0,0%"

def _fmt_n(v):
    try:
        return "{:,.0f}".format(round(float(v))).replace(",", ".")
    except (ValueError, TypeError):
        return str(v)

def create_page(container):
    df = _load_data()
    if df.empty or "date" not in df.columns:
        with container:
            ui.label("Data belum tersedia.").classes("text-gray-400")
        return

    all_dates = sorted(df["date"].dropna().unique())
    cutoff_60 = pd.Timestamp.now() - pd.Timedelta(days=60)
    recent_dates = sorted(d for d in all_dates if d >= cutoff_60)
    if not recent_dates:
        recent_dates = [all_dates[-1]] if all_dates else []
    if not recent_dates:
        with container:
            ui.label("Belum ada data transaksi harian.").classes("text-gray-400")
        return

    date_strs = [d.strftime("%Y-%m-%d") for d in recent_dates]
    selected_str = date_strs[-1]

    with container:
        ui.add_head_html("<style>.daily-card:hover{transform:translateY(-2px);transition:all 0.2s}</style>")

        with ui.row().classes("w-full items-center gap-3 mb-2"):
            ui.label("\U0001f4ca").classes("text-3xl")
            ui.label("Transaksi Harian").classes("text-2xl font-bold text-white")
            ui.label("— 60 Hari Terakhir").classes("text-lg text-gray-400")
            ui.label("\u2022 " + datetime.now().strftime("%d %b %Y %H:%M")).classes("text-xs text-gray-500 ml-auto")
        ui.separator().classes("mb-4")

        dp = ui.select(
            date_strs, value=selected_str, label="Pilih Tanggal",
        ).props("dense outlined dark").classes("w-72 mb-4")

        content = ui.column().classes("w-full")

        def _update(sel_str):
            content.clear()
            if not sel_str:
                return
            sel_dt = pd.Timestamp(sel_str)
            day_df = df[df["date"] == sel_dt]
            if day_df.empty:
                with content:
                    ui.label("Tidak ada data untuk " + sel_str).classes("text-gray-400")
                return

            rev = day_df["revenue"].sum()
            sess = day_df["sessions"].sum()
            unlocks = day_df["unlocks_paid"].sum()
            prints = day_df["prints"].sum()
            active = int((day_df["sessions"] > 0).sum())
            conv = (unlocks / sess * 100) if sess > 0 else 0

            with content:
                with ui.row().classes("w-full gap-4 mb-4"):
                    for lb, vl, cl in [
                        ("\U0001f4b0 Revenue", _fmt_rp(rev), "#89b4fa"),
                        ("\U0001f4f8 Sessions", _fmt_n(sess), "#a6e3a1"),
                        ("\U0001f513 Unlock Bayar", _fmt_n(unlocks), "#f9e2af"),
                        ("\U0001f5a8 Print", _fmt_n(prints), "#f38ba8"),
                        ("\U0001f3ea Outlet Aktif", _fmt_n(active), "#cba6f7"),
                        ("\U0001f4c8 Konversi", _fmt_pct(conv), "#94e2d5"),
                    ]:
                        with ui.card().classes("daily-card flex-1 min-w-[130px]").style(CARD):
                            ui.label(lb).classes("text-xs").style("color:" + cl + ";text-transform:uppercase;letter-spacing:.5px;")
                            ui.label(vl).classes("text-xl font-bold text-white mt-1")

                # Comparison with yesterday
                prev_dt = sel_dt - pd.Timedelta(days=1)
                prev_df = df[df["date"] == prev_dt]
                if not prev_df.empty:
                    prev_rev = prev_df["revenue"].sum()
                    diff = rev - prev_rev
                    pct = (diff / prev_rev * 100) if prev_rev > 0 else 0
                    arrow = "\U0001f7e2" if diff >= 0 else "\U0001f534"
                    ui.label("{} vs {}: {} ({:+.1f}%)".format(
                        arrow, prev_dt.strftime("%d %b"), _fmt_rp(diff), pct
                    )).classes("text-xs text-gray-400 mb-3")

                # Outlet ranking table
                ui.label("\U0001f4cb Outlet Ranking").classes("text-sm font-semibold text-gray-300 mb-2")

                tbl = day_df.sort_values("revenue", ascending=False).reset_index(drop=True)
                tbl["No"] = range(1, len(tbl) + 1)
                tbl["Outlet"] = tbl.get("outlet_name", "")
                tbl["Revenue"] = tbl["revenue"].apply(_fmt_rp)
                tbl["Sesi"] = tbl["sessions"].apply(_fmt_n)
                tbl["Unlock"] = tbl["unlocks_paid"].apply(_fmt_n)
                tbl["Print"] = tbl["prints"].apply(_fmt_n)
                tbl["Konv"] = tbl["conversion_rate"].apply(_fmt_pct)

                cols = ["No", "Outlet", "Revenue", "Sesi", "Unlock", "Print", "Konv"]

                rows_html = ""
                for i in range(len(tbl)):
                    r = tbl.iloc[i]
                    bg = "#2a2a3e" if i % 2 == 0 else ""
                    rows_html += "<tr style='background:{};border-bottom:1px solid #313244;'>".format(bg)
                    for c in cols:
                        al = "right" if c not in ("No", "Outlet") else "left"
                        style = "padding:6px 10px;text-align:{};font-size:12px;".format(al)
                        if c == "Revenue":
                            style += "color:#89b4fa;font-weight:600;"
                        rows_html += "<td style='{}'>{}</td>".format(style, r[c])
                    rows_html += "</tr>"

                hdr_html = ""
                for c in cols:
                    al = "right" if c not in ("No", "Outlet") else "left"
                    hdr_html += "<th style='padding:8px 10px;text-align:{};font-size:11px;color:#a6adc8;text-transform:uppercase;'>{}</th>".format(al, c)

                table_html = (
                    "<div style='overflow-x:auto;border-radius:8px;border:1px solid #313244;background:#1e1e2e;'>"
                    "<table style='width:100%;border-collapse:collapse;'>"
                    "<thead><tr style='background:#181825;border-bottom:2px solid #313244;'>"
                    + hdr_html + "</tr></thead><tbody>" + rows_html + "</tbody></table></div>"
                )
                ui.html(table_html).classes("w-full")

        def _on_change(e):
            _update(e.value)

        dp.on("update:model-value", _on_change)
        _update(selected_str)
