"""Analisis Trend v2 — tren bulanan yang terukur.

Halaman pengganti /trend: satu alur baca (tanpa tab), setiap angka punya
pembanding yang jelas (MoM, YoY, rata-rata, MA3), plus daftar outlet yang
perlu dicek dan tabel periode yang bisa dibaca sekali lihat.

Sumber: `services.dashboard_adapter.get_adapter().load_data()` (bulanan per outlet).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from nicegui import ui
import pandas as pd
import plotly.graph_objects as go

from services.dashboard_adapter import get_adapter

ROOT = Path(__file__).resolve().parents[2]
FORECAST_PATH = ROOT / "streamlit_template" / "data" / "api_cache" / "forecast_monthly.json"
_fc_cache: dict = {"data": None, "mtime": None}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
JUNK = ("test", "coba", "dummy", "sample")

C_PANEL = "#15151e"
C_LINE = "#24242f"
C_TXT = "#eceef4"
C_MUT = "#8b90a3"
C_MINT = "#3ddc97"
C_AMBER = "#f5b942"
C_RED = "#f2685f"
C_BLUE = "#5b9cff"

TR_CSS = """<style>
  .tr-wrap { color: @TXT@; font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 13px; }
  .tr-grid6 { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 11px; }
  .tr-grid2 { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; margin-top: 14px; align-items: start; }
  .tr-grid2b { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px; align-items: start; }
  .tr-kpi { background: @PANEL@; border: 1px solid @LINE@; border-radius: 11px; padding: 12px 13px 10px; }
  .tr-lab { color: @MUT@; font-size: 10.5px; letter-spacing: .8px; text-transform: uppercase; }
  .tr-val { font-size: 22px; font-weight: 650; margin: 6px 0 5px; letter-spacing: -.4px; }
  .tr-deltas { display: flex; flex-direction: column; gap: 1px; font-size: 10.5px; color: @MUT@; }
  .tr-card { background: @PANEL@; border: 1px solid @LINE@; border-radius: 11px; padding: 14px; }
  .tr-h { display: flex; align-items: baseline; gap: 9px; margin-bottom: 8px; flex-wrap: wrap; }
  .tr-h b { font-size: 13px; font-weight: 650; }
  .tr-h i { font-style: normal; color: @MUT@; font-size: 11px; }
  .tr-table { width: 100%; border-collapse: collapse; }
  .tr-table thead th { position: sticky; top: 0; background: @PANEL@; z-index: 1; text-align: left;
    font-size: 10px; letter-spacing: .7px; text-transform: uppercase; color: @MUT@; font-weight: 600;
    padding: 0 10px 7px; border-bottom: 1px solid @LINE@; white-space: nowrap; }
  .tr-table th.r, .tr-table td.r { text-align: right; }
  .tr-table td { padding: 8px 10px; border-bottom: 1px solid #1b1b25; font-size: 12px; white-space: nowrap;
    font-variant-numeric: tabular-nums; }
  .tr-table tfoot td { border-top: 1px solid @LINE@; font-weight: 650; padding-top: 9px; }
  .tr-up { color: @MINT@; }
  .tr-down { color: @RED@; }
  .tr-mut { color: @MUT@; }
  .tr-chip { display: inline-block; font-size: 10.5px; font-weight: 600; padding: 2px 6px; border-radius: 5px; }
  .tr-chip.up { color: @MINT@; background: @MINT@1a; }
  .tr-chip.down { color: @RED@; background: @RED@1a; }
  .tr-chip.warn { color: @AMBER@; background: @AMBER@1a; }
  .tr-chip.flat { color: @MUT@; background: #ffffff0d; }
  .tr-issue { display: grid; grid-template-columns: 3px 1fr auto; gap: 11px; align-items: center; padding: 9px 0; }
  .tr-issue + .tr-issue { border-top: 1px solid @LINE@; }
  .tr-sev { width: 3px; height: 30px; border-radius: 2px; }
  .tr-issue .t { font-weight: 600; font-size: 12.5px; color: @TXT@; margin: 0; }
  .tr-issue .d { color: @MUT@; font-size: 11px; margin: 2px 0 0; }
  .tr-issue .n { font-size: 14px; font-weight: 650; text-align: right; }
  .tr-row { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; padding: 7px 0;
    border-bottom: 1px solid #1b1b25; align-items: center; }
  .tr-row:last-child { border-bottom: 0; }
  .tr-row .k { color: @MUT@; font-size: 11.5px; }
  .tr-row .v { font-weight: 600; font-variant-numeric: tabular-nums; }
  .tr-empty { color: @MUT@; padding: 14px 0; }
  .tr-note { color: @MUT@; font-size: 10.5px; margin-top: 9px; }
  @media (max-width: 1200px) { .tr-grid6 { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  @media (max-width: 900px) {
    .tr-grid6 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .tr-grid2, .tr-grid2b { grid-template-columns: 1fr; }
    .tr-val { font-size: 19px; }
  }
</style>"""
for _tok, _val in (("@TXT@", C_TXT), ("@PANEL@", C_PANEL), ("@LINE@", C_LINE), ("@MUT@", C_MUT),
                   ("@MINT@", C_MINT), ("@AMBER@", C_AMBER), ("@RED@", C_RED), ("@BLUE@", C_BLUE)):
    TR_CSS = TR_CSS.replace(_tok, _val)


# ── format ────────────────────────────────────────────────────────────────

def rp(v) -> str:
    try:
        return "Rp " + format(int(round(float(v))), ",").replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


def rp_short(v) -> str:
    try:
        val = float(v)
    except (TypeError, ValueError):
        return "Rp 0"
    if abs(val) >= 1_000_000_000:
        return ("Rp %.1f M" % (val / 1_000_000_000)).replace(".", ",")
    if abs(val) >= 1_000_000:
        return ("Rp %.1f jt" % (val / 1_000_000)).replace(".", ",")
    if abs(val) >= 1_000:
        return "Rp " + num(round(val / 1000.0)) + " rb"
    return rp(val)


def num(v) -> str:
    try:
        return format(int(round(float(v))), ",").replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def pct(v, dec: int = 1) -> str:
    try:
        return ("%." + str(dec) + "f%%") % float(v)
    except (TypeError, ValueError):
        return "-"


def pct_id(v, dec: int = 1) -> str:
    return pct(v, dec).replace(".", ",")


def month_label(p: str) -> str:
    try:
        y, mo = str(p).split("-")[:2]
        return MONTHS[int(mo) - 1] + " " + y
    except Exception:
        return str(p)


def delta(cur, base):
    """-> (cls, text) dengan cls: up|down|flat."""
    try:
        c, b = float(cur), float(base)
    except (TypeError, ValueError):
        return ("flat", "—")
    if b == 0:
        return ("flat", "—")
    d = (c - b) / b * 100.0
    cls = "up" if d >= 0.5 else ("down" if d <= -0.5 else "flat")
    arrow = "↑" if d >= 0.5 else ("↓" if d <= -0.5 else "→")
    return (cls, ("%s %s%%" % (arrow, pct_id(abs(d)))).replace("  ", " "))


def chip(cls: str, txt: str) -> str:
    return '<span class="tr-chip ' + cls + '">' + txt + "</span>"


# ── data ──────────────────────────────────────────────────────────────────

def _clean() -> pd.DataFrame:
    df = get_adapter().load_data()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["periode"] = df["periode"].astype(str)
    for col in ("total_revenue", "foto_qty", "unlock_qty", "print_qty", "sessions", "unlocks_paid"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["outlet_name"] = df["outlet_name"].astype(str).str.strip()
    df = df[~df["outlet_name"].str.lower().str.startswith(JUNK)]
    df = df[df["outlet_name"].str.len() > 1]
    return df


def _agg(frame: pd.DataFrame) -> dict:
    if frame is None or frame.empty:
        return {"revenue": 0.0, "foto": 0, "print": 0, "sessions": 0, "outlets": 0,
                "arps": 0.0, "conv": 0.0}
    rev = float(frame["total_revenue"].sum())
    foto = int(frame["foto_qty"].sum())
    prints = int(frame["print_qty"].sum())
    sess = int(frame["sessions"].sum()) if "sessions" in frame.columns else foto
    active = int(frame.loc[frame["total_revenue"] > 0, "outlet_name"].nunique())
    return {
        "revenue": rev,
        "foto": foto,
        "print": prints,
        "sessions": sess,
        "outlets": active,
        "arps": (rev / sess) if sess else 0.0,
        "conv": (prints / foto * 100.0) if foto else 0.0,
    }


def _monthly(df: pd.DataFrame, periods: list) -> pd.DataFrame:
    rows = []
    for p in periods:
        f = df[df["periode"] == p]
        a = _agg(f)
        a["periode"] = p
        rows.append(a)
    out = pd.DataFrame(rows)
    if not out.empty:
        out["ma3"] = out["revenue"].rolling(3, min_periods=1).mean()
        out["mom"] = out["revenue"].pct_change() * 100.0
    return out


def build_model(df: pd.DataFrame, start: str, end: str) -> dict:
    all_periods = sorted(df["periode"].dropna().unique().tolist())
    periods = [p for p in all_periods if start <= p <= end]
    if not periods:
        return {"empty": True}

    monthly = _monthly(df, periods)
    latest = periods[-1]
    prev = periods[-2] if len(periods) > 1 else None

    cur = _agg(df[df["periode"] == latest])
    prev_a = _agg(df[df["periode"] == prev]) if prev else _agg(pd.DataFrame())

    # YoY: bulan yang sama tahun lalu (walau di luar range)
    y, mo = latest.split("-")
    yoy_key = "%04d-%s" % (int(y) - 1, mo)
    yoy_a = _agg(df[df["periode"] == yoy_key]) if yoy_key in all_periods else _agg(pd.DataFrame())

    # per outlet
    cur_df = df[df["periode"] == latest]
    prev_df = df[df["periode"] == prev] if prev else pd.DataFrame()
    outlets = []
    prev_by = {}
    if not prev_df.empty:
        prev_by = prev_df.groupby("outlet_name")["total_revenue"].sum().to_dict()
        prev_by = {k: float(v) for k, v in prev_by.items()}
    for name, g in cur_df.groupby("outlet_name"):
        rev = float(g["total_revenue"].sum())
        if rev <= 0 and name not in prev_by:
            continue
        prev_rev = prev_by.get(name)
        d = ((rev - prev_rev) / prev_rev * 100.0) if prev_rev else None
        outlets.append({
            "name": name,
            "area": str(g["area"].iloc[0]) if "area" in g.columns and pd.notna(g["area"].iloc[0]) else "",
            "revenue": rev,
            "prev": prev_rev,
            "delta": d,
            "foto": int(g["foto_qty"].sum()),
            "print": int(g["print_qty"].sum()),
            "arps": (rev / float(g["sessions"].sum())) if float(g["sessions"].sum()) else 0.0,
            "conv": (float(g["print_qty"].sum()) / float(g["foto_qty"].sum()) * 100.0) if float(g["foto_qty"].sum()) else 0.0,
        })
    # outlet yang hilang bulan ini
    cur_names = set(cur_df["outlet_name"])
    for name, prev_rev in prev_by.items():
        if name not in cur_names and prev_rev > 0:
            outlets.append({"name": name, "area": "", "revenue": 0.0, "prev": prev_rev,
                            "delta": -100.0, "foto": 0, "print": 0, "arps": 0.0, "conv": 0.0})

    total_rev = cur["revenue"] or 1.0
    for o in outlets:
        o["share"] = o["revenue"] / total_rev * 100.0
        o["impact"] = (o["prev"] or 0) - o["revenue"]

    top_share = sum(sorted([o["revenue"] for o in outlets], reverse=True)[:5]) / total_rev * 100.0

    # turun 3 bulan berturut-turut
    streak = set()
    if len(periods) >= 3:
        p1, p2, p3 = periods[-3], periods[-2], periods[-1]
        by = df[df["periode"].isin([p1, p2, p3])].groupby(["outlet_name", "periode"])["total_revenue"].sum()
        for name in df["outlet_name"].unique():
            try:
                a, b, c = float(by.loc[(name, p1)]), float(by.loc[(name, p2)]), float(by.loc[(name, p3)])
            except KeyError:
                continue
            if a > b > c and a >= 5_000_000:
                streak.add(name)

    # isu
    issues = []
    zero_names = []
    for o in outlets:
        if o["revenue"] <= 0:
            if (o["prev"] or 0) >= 3_000_000:
                zero_names.append(o["name"])
                issues.append(("red", o["name"], o["area"],
                               "tidak ada omzet bulan ini (bulan lalu " + rp_short(o["prev"] or 0) + ")", o["impact"]))
            continue
        if o["delta"] is not None and o["delta"] <= -30 and (o["prev"] or 0) >= 5_000_000 and o["impact"] >= 3_000_000:
            issues.append(("amber", o["name"], o["area"],
                           "turun %s vs bulan lalu (%s → %s)" % (pct_id(abs(o["delta"])), rp_short(o["prev"]), rp_short(o["revenue"])),
                           o["impact"]))
    for name in sorted(streak):
        if any(i[1] == name for i in issues):
            continue
        issues.append(("amber", name, "", "turun 3 bulan berturut-turut", 0))

    issues.sort(key=lambda i: -i[4])

    return {
        "empty": False,
        "periods": periods,
        "latest": latest,
        "prev": prev,
        "yoy_key": yoy_key if yoy_a["revenue"] else "",
        "cur": cur,
        "prev_a": prev_a,
        "yoy_a": yoy_a,
        "monthly": monthly,
        "outlets": outlets,
        "issues": issues[:6],
        "n_issues": len(issues),
        "n_zero": len(zero_names),
        "top_share": top_share,
        "n_outlets": len(outlets),
    }


# ── html ──────────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, d_mom, d_yoy, title: str = "") -> str:
    def chip_html(c):
        cls, txt = c
        tone = C_MINT if cls == "up" else (C_RED if cls == "down" else C_MUT)
        return '<b style="color:' + tone + '">' + txt + "</b>"
    tip = (' title="' + title + '"') if title else ""
    return (
        '<div class="tr-kpi"><div class="tr-lab">' + label + "</div>"
        '<div class="tr-val num"' + tip + ">" + value + "</div>"
        '<div class="tr-deltas"><span>MoM ' + chip_html(d_mom) + "</span>"
        "<span>YoY " + chip_html(d_yoy) + "</span></div></div>"
    )


def _period_table(monthly: pd.DataFrame) -> str:
    rows = ""
    for i in range(len(monthly) - 1, -1, -1):
        r = monthly.iloc[i]
        dcls, dtxt = delta(r["revenue"], monthly.iloc[i - 1]["revenue"]) if i > 0 else ("flat", "—")
        status = ""
        if i > 0:
            if r["mom"] >= 10:
                status = chip("up", "naik")
            elif r["mom"] <= -10:
                status = chip("down", "turun")
            elif r["mom"] <= -3:
                status = chip("warn", "melemah")
        rows += (
            "<tr><td>" + month_label(r["periode"]) + "</td>"
            '<td class="r">' + rp_short(r["revenue"]) + "</td>"
            '<td class="r"><span class="tr-' + dcls + '">' + dtxt + "</span></td>"
            '<td class="r">' + num(r["foto"]) + "</td>"
            '<td class="r">' + num(r["print"]) + "</td>"
            '<td class="r">' + rp(r["arps"]) + "</td>"
            '<td class="r">' + pct_id(r["conv"]) + "</td>"
            '<td class="r">' + num(r["outlets"]) + "</td>"
            "<td>" + status + "</td></tr>"
        )
    total = (
        "<tfoot><tr><td>Rata-rata / bulan</td>"
        '<td class="r">' + rp_short(monthly["revenue"].mean()) + "</td><td></td>"
        '<td class="r">' + num(monthly["foto"].mean()) + "</td>"
        '<td class="r">' + num(monthly["print"].mean()) + "</td>"
        '<td class="r">' + rp(monthly["arps"].mean()) + "</td>"
        '<td class="r">' + pct_id(monthly["conv"].mean()) + "</td>"
        '<td class="r">' + num(monthly["outlets"].mean()) + "</td><td></td></tr></tfoot>"
    )
    return ('<div style="overflow:auto;max-height:420px"><table class="tr-table">'
            "<thead><tr><th>Periode</th><th class='r'>Omzet</th><th class='r'>Δ MoM</th>"
            "<th class='r'>Foto</th><th class='r'>Print</th><th class='r'>ARPS</th>"
            "<th class='r'>Konv.</th><th class='r'>Outlet</th><th>Status</th></tr></thead>"
            "<tbody>" + rows + "</tbody>" + total + "</table></div>")


def _movers(outlets: list) -> tuple[str, str]:
    base = [o for o in outlets if o["prev"] and o["prev"] >= 1_000_000]
    up = sorted([o for o in base if (o["delta"] or 0) > 0], key=lambda o: -(o["revenue"] - o["prev"]))[:5]
    down = sorted([o for o in base if (o["delta"] or 0) < 0], key=lambda o: (o["revenue"] - o["prev"]))[:5]

    def rows(items):
        if not items:
            return '<div class="tr-empty">Belum ada data pembanding.</div>'
        out = ""
        for o in items:
            cls, txt = delta(o["revenue"], o["prev"])
            out += ('<div class="tr-row"><span class="k"><b style="color:#eceef4">' + o["name"] + "</b>"
                    + (" · " + o["area"] if o["area"] else "") + "</span>"
                    '<span class="v">' + rp_short(o["revenue"]) + "</span>"
                    '<span class="tr-' + cls + '" style="font-weight:650">' + txt + "</span></div>")
        return out

    return rows(up), rows(down)


def kpis_html(m: dict) -> str:
    cur, prev_a, yoy_a = m["cur"], m["prev_a"], m["yoy_a"]
    return '<div class="tr-wrap"><div class="tr-grid6">' + "".join([
        _kpi("Omzet", rp_short(cur["revenue"]), delta(cur["revenue"], prev_a["revenue"]),
             delta(cur["revenue"], yoy_a["revenue"]), "tepat: " + rp(cur["revenue"])),
        _kpi("Foto", num(cur["foto"]), delta(cur["foto"], prev_a["foto"]), delta(cur["foto"], yoy_a["foto"])),
        _kpi("Print", num(cur["print"]), delta(cur["print"], prev_a["print"]), delta(cur["print"], yoy_a["print"])),
        _kpi("ARPS", rp(cur["arps"]), delta(cur["arps"], prev_a["arps"]), delta(cur["arps"], yoy_a["arps"]),
             "omzet per sesi"),
        _kpi("Konversi", pct_id(cur["conv"]), delta(cur["conv"], prev_a["conv"]), delta(cur["conv"], yoy_a["conv"]),
             "print per foto"),
        _kpi("Outlet aktif", num(cur["outlets"]), delta(cur["outlets"], prev_a["outlets"]),
             delta(cur["outlets"], yoy_a["outlets"])),
    ]) + "</div></div>"


def issues_html(m: dict) -> str:
    rows = ""
    for tone, name, area, why, impact in m["issues"]:
        color = C_RED if tone == "red" else C_AMBER
        rows += ('<div class="tr-issue"><span class="tr-sev" style="background:' + color + '"></span>'
                 '<div><p class="t">' + name + '</p><p class="d">'
                 + (area + " · " if area else "") + why + "</p></div>"
                 '<span class="n" style="color:' + color + '">'
                 + (rp_short(impact) if impact else "—") + "</span></div>")
    if not rows:
        rows = '<div class="tr-empty">Tidak ada outlet yang mencolok di periode ini.</div>'
    return ('<div class="tr-wrap"><div class="tr-h"><b>Perlu dicek</b><i>' + num(len(m["issues"]))
            + " dari " + num(m["n_issues"]) + " temuan · urut dampak Rupiah</i></div>" + rows
            + '<div class="tr-note">' + num(m.get("n_zero", 0)) + " outlet tanpa omzet bulan ini · konsentrasi top-5 = "
            + pct_id(m["top_share"]) + " dari omzet bulan ini.</div></div>")


def movers_html(m: dict) -> str:
    up_rows, down_rows = _movers(m["outlets"])
    return ('<div class="tr-wrap"><div class="tr-grid2b">'
            '<div><div class="tr-h"><b>Naik terbesar</b><i>vs bulan lalu</i></div>' + up_rows + "</div>"
            '<div><div class="tr-h"><b>Turun terbesar</b><i>vs bulan lalu</i></div>' + down_rows + "</div>"
            "</div></div>")


def table_html(m: dict) -> str:
    ma3 = m["monthly"]["ma3"].iloc[-1] if not m["monthly"].empty else 0
    note = ""
    if len(m["monthly"]) >= 3:
        last3 = m["monthly"]["revenue"].tail(3).tolist()
        if last3[0] > last3[1] > last3[2]:
            note = " · 3 bulan terakhir turun terus"
        elif last3[0] < last3[1] < last3[2]:
            note = " · 3 bulan terakhir naik terus"
    return ('<div class="tr-wrap"><div class="tr-h"><b>Tabel periode</b><i>Δ MoM = perubahan omzet vs bulan sebelumnya · MA3 '
            + rp_short(ma3) + note + "</i></div>" + _period_table(m["monthly"]) + "</div>")


def _fig_revenue(m: dict) -> go.Figure:
    monthly = m["monthly"]
    labels = [month_label(p) for p in monthly["periode"]]
    fig = go.Figure()
    fig.add_bar(x=labels, y=monthly["revenue"], name="Omzet",
                marker_color=[C_MINT if p == m["latest"] else "#2b3654" for p in monthly["periode"]],
                hovertemplate="%{x}<br>Rp %{y:,.0f}<extra></extra>")
    fig.add_scatter(x=labels, y=monthly["ma3"], name="MA3", mode="lines+markers",
                    line=dict(color=C_AMBER, width=2), hovertemplate="MA3 %{x}<br>Rp %{y:,.0f}<extra></extra>")
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=10, b=10), height=340, showlegend=True,
                      legend=dict(orientation="h", y=1.12, x=0),
                      yaxis=dict(tickformat=".2s", gridcolor="#24242f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig


def _fig_conv(m: dict) -> go.Figure:
    monthly = m["monthly"]
    labels = [month_label(p) for p in monthly["periode"]]
    fig = go.Figure()
    fig.add_scatter(x=labels, y=monthly["conv"], name="Konversi %", mode="lines+markers",
                    line=dict(color=C_BLUE, width=2), hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>")
    avg = float(monthly["conv"].mean())
    fig.add_hline(y=avg, line_dash="dash", line_color=C_MUT,
                  annotation_text=("rata-rata " + pct_id(avg)), annotation_font_color=C_MUT)
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=10, b=10), height=300, showlegend=False,
                      yaxis=dict(ticksuffix="%", gridcolor="#24242f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig



# ── proyeksi Prophet ──────────────────────────────────────────────────────

def load_forecast() -> dict | None:
    try:
        mtime = FORECAST_PATH.stat().st_mtime
    except OSError:
        return None
    if _fc_cache["data"] is not None and _fc_cache["mtime"] == mtime:
        return _fc_cache["data"]
    try:
        data = json.loads(FORECAST_PATH.read_text())
    except Exception:
        return None
    _fc_cache["data"] = data
    _fc_cache["mtime"] = mtime
    return data


def forecast_html(fc: dict) -> str:
    proj = fc.get("projected_total") or 0
    lo, hi = fc.get("projected_lower") or 0, fc.get("projected_upper") or 0
    prev_full = fc.get("prev_month_total") or 0
    dcls, dtxt = delta(proj, prev_full)
    tone = C_MINT if dcls == "up" else (C_RED if dcls == "down" else C_MUT)
    mape = fc.get("mape_14d")
    rows = [
        ("Realisasi 1–%d" % int(fc.get("day_of_data") or fc.get("day_of_month") or 0), rp_short(fc.get("mtd_actual") or 0)),
        ("Proyeksi sisa %d hari" % int(fc.get("days_left") or 0), rp_short(fc.get("projected_remaining") or 0)),
        ("Bulan lalu (pace %d hari)" % int(fc.get("prev_same_days") or 0), rp_short(fc.get("prev_month_pace") or 0)),
        ("Bulan lalu penuh", rp_short(prev_full)),
    ]
    rows_html = "".join(
        '<div class="tr-row"><span class="k">' + k + '</span><span class="v">' + v + "</span><span></span></div>"
        for k, v in rows
    )
    hol = fc.get("holidays_remaining") or []
    hol_txt = ", ".join(h["date"][5:] + " " + h["name"] for h in hol) if hol else "tidak ada hari libur tersisa"
    acc = ("±" + pct_id(mape) + " harian (backtest %d hari)" % int(fc.get("backtest_days") or 0)) if mape else "belum dihitung"
    est = fc.get("mape_total_est")
    if est:
        acc += " · estimasi galat total ±" + pct_id(est)
    return (
        '<div class="tr-wrap">'
        '<div class="tr-lab">Proyeksi akhir bulan · Prophet + kalender libur</div>'
        '<div class="tr-val num" style="font-size:26px">' + rp_short(proj) + "</div>"
        '<div class="tr-deltas" style="font-size:11px"><span style="color:' + tone + ';font-weight:650">'
        + dtxt + " vs bulan lalu penuh</span>"
        '<span>rentang ' + rp_short(lo) + " – " + rp_short(hi) + "</span></div>"
        '<div style="margin-top:10px">' + rows_html + "</div>"
        '<div class="tr-note">Akurasi model ' + acc + " · libur tersisa: " + hol_txt
        + " · diperbarui " + (fc.get("generated_at") or "-").replace("T", " ") + "</div>"
        "</div>"
    )


def _fig_forecast(fc: dict) -> go.Figure:
    hist = fc.get("history") or []
    fcast = [f for f in (fc.get("forecast") or []) if f["date"] > fc.get("today", "")]
    fig = go.Figure()
    if hist:
        fig.add_scatter(x=[h["date"] for h in hist], y=[h["y"] for h in hist], name="Realisasi",
                        mode="lines", line=dict(color=C_BLUE, width=2))
    if fcast:
        xs = [h["date"] for h in hist[-1:]] + [f["date"] for f in fcast]
        ys_lo = [(hist[-1]["y"] if hist else 0)] + [f["lower"] for f in fcast]
        ys_hi = [(hist[-1]["y"] if hist else 0)] + [f["upper"] for f in fcast]
        fig.add_scatter(x=xs, y=ys_hi, mode="lines", line=dict(width=0), showlegend=False,
                        hoverinfo="skip")
        fig.add_scatter(x=xs, y=ys_lo, mode="lines", line=dict(width=0), fill="tonexty",
                        fillcolor="rgba(61,220,151,0.16)", showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=[f["date"] for f in fcast], y=[f["yhat"] for f in fcast],
                        name="Proyeksi", mode="lines+markers",
                        line=dict(color=C_MINT, width=2, dash="dash"))
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=10, b=10), height=260,
                      legend=dict(orientation="h", y=1.12, x=0),
                      yaxis=dict(tickformat=".2s", gridcolor="#24242f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig


# ── page ──────────────────────────────────────────────────────────────────

def create_page(container) -> None:
    ui.add_head_html(TR_CSS, shared=True)
    df = _clean()
    if df.empty:
        with container:
            ui.label("Data trend belum tersedia.").classes("text-gray-400")
        return

    periods = sorted(df["periode"].unique().tolist())
    default_start = periods[-12] if len(periods) >= 12 else periods[0]
    opts = {p: month_label(p) for p in periods}
    holder: dict = {}

    def render():
        holder["body"].clear()
        start, end = holder["start"].value, holder["end"].value
        if start > end:
            with holder["body"]:
                ui.label("Periode mulai tidak boleh lebih baru dari periode akhir.").classes("text-yellow-400")
            return
        m = build_model(df, start, end)
        if m.get("empty"):
            with holder["body"]:
                ui.label("Tidak ada periode pada rentang itu.").classes("text-gray-400")
            return
        fc = load_forecast()
        with holder["body"]:
            ui.html(kpis_html(m), sanitize=False).classes("w-full")
            if fc and fc.get("month") == m["latest"]:
                with ui.row().classes("w-full gap-3 mt-3 flex-wrap items-start"):
                    with ui.card().classes("w-full lg:w-[420px]").style("background:" + C_PANEL + ";border:1px solid " + C_LINE):
                        ui.html(forecast_html(fc), sanitize=False)
                    with ui.card().classes("flex-1 min-w-[280px]").style("background:" + C_PANEL + ";border:1px solid " + C_LINE):
                        ui.label("Realisasi 60 hari + proyeksi sampai akhir bulan").classes("text-xs").style("color:" + C_MUT)
                        ui.plotly(_fig_forecast(fc)).classes("w-full h-[260px]")
                ui.label("Proyeksi memakai Prophet (trend + pola mingguan/tahunan + kalender libur & long weekend). "
                         "Angka sisa bulan adalah rata-rata model, bukan janji.").classes("text-xs").style("color:" + C_MUT + ";margin-top:4px")
            with ui.row().classes("w-full gap-3 mt-3 flex-wrap items-start"):
                with ui.card().classes("flex-1 min-w-[280px]").style("background:" + C_PANEL + ";border:1px solid " + C_LINE + ";align-self:flex-start"):
                    ui.label("Omzet per bulan · bar = omzet, garis = MA3").classes("text-xs").style("color:" + C_MUT)
                    ui.plotly(_fig_revenue(m)).classes("w-full h-[300px]")
                with ui.card().classes("w-full lg:w-[360px]").style("background:" + C_PANEL + ";border:1px solid " + C_LINE):
                    ui.html(issues_html(m), sanitize=False)
            ui.html(movers_html(m), sanitize=False).classes("w-full mt-3")
            with ui.card().classes("w-full mt-3").style("background:" + C_PANEL + ";border:1px solid " + C_LINE):
                ui.label("Konversi per bulan · print per foto").classes("text-xs").style("color:" + C_MUT)
                ui.plotly(_fig_conv(m)).classes("w-full h-[260px]")
            with ui.card().classes("w-full mt-3").style("background:" + C_PANEL + ";border:1px solid " + C_LINE):
                ui.html(table_html(m), sanitize=False).classes("w-full")

    with container:
        with ui.row().classes("w-full items-center gap-3 flex-wrap pb-2"):
            ui.label("\U0001f4c8").classes("text-2xl")
            ui.label("Analisis Trend").classes("text-xl font-bold text-white")
            ui.label("bulanan · dibanding bulan lalu, tahun lalu, dan rata-rata").classes("text-xs text-gray-500")
            holder["start"] = ui.select(opts, value=default_start, label="Dari",
                                        on_change=lambda e: render()).props("dense outlined dark").classes("w-36")
            holder["end"] = ui.select(opts, value=periods[-1], label="Sampai",
                                      on_change=lambda e: render()).props("dense outlined dark").classes("w-36")
            ui.label("Data: " + datetime.now().strftime("%d %b %Y %H:%M")).classes("text-xs text-gray-500 ml-auto")

        holder["body"] = ui.column().classes("w-full")
        render()
