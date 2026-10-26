"""Ranking & Vitalitas Outlet v2.

Tujuan: dalam satu layar, owner bisa (1) lihat transaksi semua outlet per bulan,
(2) sortir kolom apa pun, (3) tahu outlet mana yang patut dipertahankan atau
diganti tempat. Semua angka berasal dari data harian (bukan ringkasan bulanan
yang sudah diolah), jadi hari aktif & transaksi terakhir bisa dihitung.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from nicegui import ui
from plotly import graph_objects as go

ROOT = Path(__file__).resolve().parents[2]
DAILY = ROOT / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"

C_PANEL = "#1a1a24"
C_LINE = "#26262f"
C_TXT = "#eceef4"
C_MUT = "#8e93a6"
C_MINT = "#3ddc97"
C_AMBER = "#f5b83d"
C_RED = "#ff6b6b"
C_BLUE = "#5b8cff"
JUNK = ("test", "coba", "dummy", "sample")

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
_cache: dict = {"data": None, "mtime": None}


# ── util ──────────────────────────────────────────────────────────────────

def fmt_jt(v: float) -> str:
    return f"{v:,.1f}".replace(",", ".")


def lbl_month(p: str) -> str:
    y, m = p.split("-")
    return BULAN[int(m) - 1] + " " + y[2:]


def rp_short(v: float) -> str:
    v = float(v or 0)
    a = abs(v)
    if a >= 1_000_000_000:
        return "Rp " + f"{v / 1e9:.1f}".replace(".", ",") + " M"
    if a >= 1_000_000:
        return "Rp " + f"{v / 1e6:.1f}".replace(".", ",") + " jt"
    if a >= 1_000:
        return "Rp " + f"{v / 1e3:,.0f}".replace(",", ".") + " rb"
    return "Rp " + f"{v:,.0f}".replace(",", ".")


# ── data ──────────────────────────────────────────────────────────────────

def load_daily() -> pd.DataFrame:
    try:
        mtime = DAILY.stat().st_mtime
    except OSError:
        return pd.DataFrame()
    if _cache["data"] is not None and _cache["mtime"] == mtime:
        return _cache["data"]
    df = pd.DataFrame(json.loads(DAILY.read_text()))
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["outlet_name"] = df["outlet_name"].astype(str).str.strip()
    df = df[~df["outlet_name"].str.lower().str.startswith(JUNK)]
    for c in ("revenue", "sessions", "prints"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(0.0)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    _cache["data"] = df
    _cache["mtime"] = mtime
    return df


def _areas() -> dict:
    try:
        from services.dashboard_adapter import get_adapter

        m = get_adapter().load_data().dropna(subset=["area"])
        m = m[m["area"].astype(str).str.strip() != ""].sort_values("periode")
        return m.groupby("outlet_name")["area"].last().to_dict()
    except Exception:
        return {}


def build(df: pd.DataFrame, month: str, span: int = 6) -> dict:
    months = sorted(df["month"].unique())
    idx = months.index(month) if month in months else len(months) - 1
    end = idx + 1
    start = max(0, end - span)
    window = months[start:end]
    prev = months[idx - 1] if idx > 0 else None
    yoy_month = None
    if idx >= 12:
        yoy_month = months[idx - 12]
    else:
        cand = f"{int(month[:4]) - 1}-{month[5:]}"
        yoy_month = cand if cand in months else None

    rev = df.pivot_table(index="outlet_name", columns="month", values="revenue", aggfunc="sum").fillna(0.0)
    ses = df.pivot_table(index="outlet_name", columns="month", values="sessions", aggfunc="sum").fillna(0.0)
    prn = df.pivot_table(index="outlet_name", columns="month", values="prints", aggfunc="sum").fillna(0.0)

    last_seen = df.groupby("outlet_name")["date"].max()
    active_days = df[df["month"] == month].groupby("outlet_name")["date"].nunique()
    areas = _areas()
    all_outlets = sorted(rev.index)

    def val(frame, o, m):
        return float(frame.at[o, m]) if (o in frame.index and m in frame.columns) else 0.0

    rows = []
    for o in all_outlets:
        r_now = val(rev, o, month)
        r_prev = val(rev, o, prev) if prev else 0.0
        r_yoy = val(rev, o, yoy_month) if yoy_month else 0.0
        s_now = val(ses, o, month)
        p_now = val(prn, o, month)
        conv = (p_now / s_now * 100) if s_now else 0.0
        arps = (r_now / s_now) if s_now else 0.0
        days_active = int(active_days.get(o, 0))
        last_dt = last_seen.get(o)
        days_since = (df["date"].max() - last_dt).days if pd.notna(last_dt) else 999

        m3 = [val(rev, o, m) for m in months[max(0, idx - 2):end]]
        avg3 = sum(m3) / len(m3) if m3 else 0.0
        streak_down = len(m3) == 3 and m3[0] > m3[1] > m3[2] > 0
        streak_up = len(m3) == 3 and 0 < m3[0] < m3[1] < m3[2]
        mom = ((r_now / r_prev - 1) * 100) if r_prev else None
        yoy = ((r_now / r_yoy - 1) * 100) if r_yoy else None

        # ── verdict: pertahankan / perbaiki / ganti tempat ────────────────
        active_months = 0
        for m in months[:end]:
            if o in rev.index and m in rev.columns and rev.at[o, m] > 0:
                active_months += 1

        if days_since > 90:
            verdict, why = "ARSIP", f"tidak ada transaksi {days_since} hari"
        elif r_now <= 0 and days_since >= 21:
            verdict, why = "GANTI", f"berhenti {days_since} hari"
        elif avg3 < 2_000_000 and days_since >= 14:
            verdict, why = "GANTI", f"rata-rata 3 bln {rp_short(avg3)}, sepi {days_since} hari"
        elif streak_down and avg3 < 5_000_000:
            verdict, why = "GANTI", "turun 3 bulan berturut-turut"
        elif streak_down:
            verdict, why = "PERBAIKI", "turun 3 bulan berturut-turut"
        elif mom is not None and mom <= -25 and r_prev >= 3_000_000:
            verdict, why = "PERBAIKI", f"turun {abs(mom):.0f}% vs bulan lalu"
        elif s_now >= 150 and conv < 15:
            verdict, why = "PERBAIKI", f"konversi {conv:.1f}% (traffic ada, cetak sedikit)"
        elif 0 < days_active < 10:
            verdict, why = "PERBAIKI", f"cuma aktif {days_active} hari"
        elif active_months < 3:
            verdict, why = "BARU", "data < 3 bulan"
        else:
            verdict, why = "PERTAHANKAN", ("tren naik" if streak_up else "stabil")

        row = {
            "outlet": o,
            "area": areas.get(o) or "—",
            "verdict": {"GANTI": "GANTI TEMPAT", "PERBAIKI": "PERBAIKI",
                        "PERTAHANKAN": "PERTAHANKAN", "BARU": "BARU",
                        "ARSIP": "ARSIP"}[verdict],
            "omzet": round(r_now / 1e6, 1),
            "mom": round(mom, 1) if mom is not None else None,
            "yoy": round(yoy, 1) if yoy is not None else None,
            "avg3": round(avg3 / 1e6, 1),
            "tren": "↓ 3 bln" if streak_down else ("↑ 3 bln" if streak_up else ("↓" if (mom or 0) < -10 else ("↑" if (mom or 0) > 10 else "→"))),
            "sesi": int(s_now),
            "conv": round(conv, 1),
            "arps": int(arps),
            "hari": days_active,
            "sepi": days_since,
            "why": why,
            "_verdict": verdict,
        }
        for m in window:
            key = m.replace("-", "")
            row["m_" + key] = round(val(rev, o, m) / 1e6, 1)
            i_m = months.index(m)
            if i_m > 0:
                before = val(rev, o, months[i_m - 1])
                now = val(rev, o, m)
                row["u_" + key] = 1 if now > before else (-1 if now < before else 0)
            else:
                row["u_" + key] = 0
        rows.append(row)

    rows.sort(key=lambda r: -r["omzet"])
    kpi = {
        "omzet": float(rev[month].sum()) if month in rev.columns else 0.0,
        "aktif": int((rev[month] > 0).sum()) if month in rev.columns else 0,
        "total": len(all_outlets),
        "ganti": sum(1 for r in rows if r["_verdict"] == "GANTI"),
        "perbaiki": sum(1 for r in rows if r["_verdict"] == "PERBAIKI"),
        "arsip": sum(1 for r in rows if r["_verdict"] == "ARSIP"),
        "potensi": sum(r["avg3"] * 1e6 for r in rows if r["_verdict"] == "GANTI"),
        "naik": sum(1 for r in rows if r["mom"] is not None and r["mom"] > 5),
        "turun": sum(1 for r in rows if r["mom"] is not None and r["mom"] < -5),
    }
    detail = {
        o: {
            "months": months[-12:],
            "rev": [val(rev, o, m) for m in months[-12:]],
            "ses": [val(ses, o, m) for m in months[-12:]],
        }
        for o in all_outlets
    }
    return {"rows": rows, "window": window, "month": month, "kpi": kpi, "detail": detail,
            "prev": prev, "yoy_month": yoy_month}


# ── ui ────────────────────────────────────────────────────────────────────

def _css() -> str:
    return """
  .rk-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
  .rk-kpi { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; padding: 12px 14px;
            display: flex; flex-direction: column; gap: 2px; min-height: 86px; }
  .rk-kpi .l { font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: @MUT@; font-weight: 700; }
  .rk-kpi .v { font-size: 19px; font-weight: 700; letter-spacing: -.02em; }
  .rk-kpi .s { font-size: 11px; color: @MUT@; }
  .ag-theme-balham-dark { --ag-background-color: #1a1a24; --ag-header-background-color: #15151d;
      --ag-odd-row-background-color: #171720; --ag-row-hover-color: #23233a;
      --ag-border-color: #26262f; --ag-font-size: 12px; --ag-header-height: 40px; --ag-row-height: 36px;
      --ag-foreground-color: #eceef4; --ag-header-foreground-color: #8e93a6; }
  .ag-theme-balham-dark .rk-up { color: #3ddc97 !important; font-weight: 650; }
  .ag-theme-balham-dark .rk-down { color: #ff6b6b !important; font-weight: 650; }
  .rk-note { font-size: 10.5px; color: @MUT@; line-height: 1.55; margin-top: 10px; }
  @media (max-width: 768px) {
    .ag-theme-balham-dark { --ag-row-height: 46px !important; --ag-font-size: 11px !important; }
  }
""".replace("@TXT@", C_TXT).replace("@MUT@", C_MUT).replace("@PANEL@", C_PANEL).replace("@LINE@", C_LINE)


def kpis_html(m: dict) -> str:
    k = m["kpi"]

    def card(label, value, sub, color=None):
        return (f'<div class="rk-kpi"><div class="l">{label}</div>'
                f'<div class="v" style="color:{color or C_TXT}">{value}</div>'
                f'<div class="s">{sub}</div></div>')

    return ('<div class="rk-kpis">'
            + card("Omzet " + lbl_month(m["month"]), rp_short(k["omzet"]),
                   f'{k["aktif"]} aktif · {k["arsip"]} arsip dari {k["total"]} outlet')
            + card("Naik / turun", f'{k["naik"]} / {k["turun"]}', "vs bulan lalu (>5%)", C_MINT)
            + card("Perlu perbaikan", str(k["perbaiki"]), "masih layak diperbaiki", C_AMBER)
            + card("Kandidat ganti", str(k["ganti"]), "relokasi / lepas", C_RED)
            + card("Nilai dipertaruhkan", rp_short(k["potensi"]), "rata-rata 3 bln outlet kandidat ganti", C_RED)
            + card("Arsip", str(k["arsip"]), "tidak transaksi > 90 hari", C_MUT)
            + '</div>')


def _columns(window: list) -> list:
    cols = [
        {"headerName": "Outlet", "field": "outlet", "pinned": "left", "minWidth": 185, "flex": 2,
         "cellStyle": {"fontWeight": "600"}},
        {"headerName": "Area", "field": "area", "minWidth": 100, "flex": 1},
        {"headerName": "Putusan", "field": "verdict", "minWidth": 118},
    ]
    # bulan terbaru di kiri, rapat, hijau kalau naik dari bulan sebelumnya
    for m in list(window)[::-1]:
        key = m.replace("-", "")
        cols.append({
            "headerName": lbl_month(m),
            "field": "m_" + key,
            "width": 78,
            "minWidth": 70,
            "maxWidth": 92,
            "type": "numericColumn",
            ":cellStyle": (
                "(p) => ({"
                "color: p.data.u_" + key + " > 0 ? '#3ddc97'"
                " : (p.data.u_" + key + " < 0 ? '#ff6b6b' : '#cdd3e2'),"
                "fontWeight: 600})"
            ),
        })
    cols += [
        {"headerName": "Omzet (jt)", "field": "omzet", "minWidth": 100, "type": "numericColumn"},
        {"headerName": "Δ MoM %", "field": "mom", "minWidth": 92, "type": "numericColumn"},
        {"headerName": "Δ YoY %", "field": "yoy", "minWidth": 92, "type": "numericColumn"},
        {"headerName": "Rata2 3bln (jt)", "field": "avg3", "minWidth": 112, "type": "numericColumn"},
        {"headerName": "Tren", "field": "tren", "minWidth": 82},
        {"headerName": "Sesi", "field": "sesi", "minWidth": 78, "type": "numericColumn"},
        {"headerName": "Konv %", "field": "conv", "minWidth": 78, "type": "numericColumn"},
        {"headerName": "Rp/sesi", "field": "arps", "minWidth": 92, "type": "numericColumn"},
        {"headerName": "Hari aktif", "field": "hari", "minWidth": 92, "type": "numericColumn"},
        {"headerName": "Sepi (hari)", "field": "sepi", "minWidth": 96, "type": "numericColumn"},
        {"headerName": "Kenapa", "field": "why", "minWidth": 185, "flex": 2},
    ]
    return cols


def detail_html(m: dict, outlet: str) -> str:
    d = m["detail"][outlet]
    labels = [lbl_month(x) for x in d["months"]]
    vals = d["rev"]
    peak = max(vals) if vals else 0
    last3 = vals[-3:]
    row = next((r for r in m["rows"] if r["outlet"] == outlet), None)
    trend = row["tren"].lower() if row else "—"
    return (f'<div style="font-size:12px;color:{C_MUT}">12 bulan terakhir · puncak {rp_short(peak)} · '
            f'tren 3 bulan: <b style="color:{C_TXT}">{trend}</b> · '
            f'rata-rata 3 bln {rp_short(sum(last3) / 3 if last3 else 0)}</div>'
            f'<div style="font-size:11px;color:{C_MUT};margin-top:2px">{labels[0]} – {labels[-1]}</div>')


def create_page(container: ui.column):
    ui.add_head_html("<style>" + _css() + "</style>")
    df = load_daily()
    with container:
        if df.empty:
            ui.label("Data harian belum tersedia.").classes("text-red-400")
            return

        months = sorted(df["month"].unique())
        state = {"month": months[-1], "outlet": None}

        head = ui.row().classes("w-full items-end gap-3 mb-2")

        with head:
            ui.html('<div><div style="font-size:19px;font-weight:750;letter-spacing:-.02em">🏆 Ranking &amp; Vitalitas Outlet</div>'
                    '<div style="font-size:11.5px;color:' + C_MUT + '">Semua outlet, semua bulan. Klik header kolom untuk '
                    'sortir, pakai filter di bawah header. Pilih outlet untuk lihat tren 12 bulan.</div></div>',
                    sanitize=False)

        with ui.row().classes("w-full items-center gap-3 mb-3"):
            sel = ui.select({m: lbl_month(m) for m in months[::-1]}, value=state["month"],
                            label="Bulan acuan").props("dense outlined dark").classes("w-[150px]")
            span_sel = ui.select({6: "6 bulan", 12: "12 bulan"}, value=6,
                                 label="Rentang").props("dense outlined dark").classes("w-[130px]")
            outlet_sel = ui.select([], label="Lihat tren outlet", with_input=True,
                                   on_change=lambda e: draw_detail(e.value)).props(
                "dense outlined dark use-input input-debounce=200").classes("w-[260px]")
            state["arsip"] = ui.checkbox("Tampilkan arsip", value=False).props("dense dark")
            state["arsip"].on("change", lambda e: render())

        body = ui.column().classes("w-full")
        pane = ui.column().classes("w-full mt-3")

        def draw_detail(outlet: str | None):
            pane.clear()
            month = sel.value or months[-1]
            m = build(df, month, int(span_sel.value or 6))
            if not outlet or outlet not in m["detail"]:
                return
            d = m["detail"][outlet]
            with pane:
                with ui.card().classes("w-full").style(
                        "background:" + C_PANEL + ";border:1px solid " + C_LINE):
                    ui.html(f'<div style="font-size:14px;font-weight:700">{outlet}</div>'
                            + detail_html(m, outlet), sanitize=False).classes("w-full")
                    fig = go.Figure()
                    fig.add_bar(x=[lbl_month(x) for x in d["months"]], y=[v / 1e6 for v in d["rev"]],
                                marker_color=C_BLUE, name="Omzet (jt)")
                    fig.update_layout(template="plotly_dark", height=250,
                                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      margin=dict(l=8, r=8, t=8, b=8), showlegend=False,
                                      yaxis=dict(title="jt", gridcolor="#24242f"),
                                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
                    ui.plotly(fig).classes("w-full h-[250px]")

        def render():
            month = sel.value or months[-1]
            m = build(df, month, int(span_sel.value or 6))
            show_archive = bool(state["arsip"].value)
            rows = [r for r in m["rows"] if show_archive or r["_verdict"] != "ARSIP"]
            body.clear()
            with body:
                ui.html(kpis_html(m), sanitize=False).classes("w-full")
                ui.label(f"{len(rows)} outlet ditampilkan · {lbl_month(month)} vs "
                         f"{lbl_month(m['prev']) if m['prev'] else '—'}").classes("text-xs mt-2").style(
                    "color:" + C_MUT)
                ui.aggrid({
                    "columnDefs": _columns(m["window"]),
                    "rowData": rows,
                    "defaultColDef": {"sortable": True, "filter": True, "floatingFilter": True,
                                      "resizable": True, "suppressHeaderMenuButton": True},
                    "pagination": True,
                    "paginationPageSize": 25,
                    "paginationPageSizeSelector": [25, 50, 100],
                    "animateRows": True,
                    "suppressCellFocus": True,
                    "initialSort": [{"colId": "omzet", "sort": "desc"}],
                }, theme="balham").classes("w-full ag-theme-balham-dark").style("height: 580px")
                ui.html(
                    '<div class="rk-note">Angka omzet dalam juta rupiah. '
                    '<b>GANTI TEMPAT</b> = berhenti ≥21 hari, atau rata-rata 3 bulan &lt; Rp2 jt &amp; sepi ≥14 hari, '
                    'atau turun 3 bulan berturut dengan rata-rata &lt; Rp5 jt. '
                    '<b>PERBAIKI</b> = turun 3 bulan berturut, atau −25% vs bulan lalu (basis ≥Rp3 jt), '
                    'atau konversi &lt;15% padahal ≥150 sesi, atau aktif &lt;10 hari. '
                    '<b>ARSIP</b> = tidak ada transaksi &gt;90 hari (disembunyikan secara default). '
                    'Pembanding memakai bulan yang sama (1–26) supaya bulan berjalan tidak dihukum.</div>',
                    sanitize=False).classes("w-full")

            names = [r["outlet"] for r in rows]
            outlet_sel.set_options(names)
            current = outlet_sel.value
            pick = current if current in names else (names[0] if names else None)
            if pick != outlet_sel.value:
                outlet_sel.value = pick
                outlet_sel.update()
            draw_detail(pick)

        sel.on("change", lambda e: render())
        span_sel.on("change", lambda e: render())
        render()
