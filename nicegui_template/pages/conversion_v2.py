"""Analisis Konversi v2 — funnel sesi → unlock → cetak, dengan uang yang bocor.

Pertanyaan yang dijawab halaman ini:
1. Di langkah mana orang berhenti (unlock atau cetak)?
2. Outlet mana yang bocor paling besar, dalam Rupiah per bulan?
3. Apa penyebabnya: tidak unlock, atau unlock tapi tidak jadi cetak?
4. Bagaimana tren 13 bulan (konversi & nilai per sesi)?

Basis: bulan berjalan dibanding bulan lalu pada tanggal yang sama (1–N),
supaya bulan yang belum selesai tidak dihukum.
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
C_BLUE = "#5b8cff"
C_MINT = "#3ddc97"
C_AMBER = "#f5b83d"
C_RED = "#ff6b6b"
C_VIOLET = "#a78bfa"
JUNK = ("test", "coba", "dummy", "sample")
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

_cache: dict = {"data": None, "mtime": None}


# ── format ────────────────────────────────────────────────────────────────

def rp(v: float) -> str:
    return "Rp " + f"{float(v or 0):,.0f}".replace(",", ".")


def rp_short(v: float) -> str:
    v = float(v or 0)
    a = abs(v)
    if a >= 1e9:
        return "Rp " + f"{v / 1e9:.2f}".replace(".", ",") + " M"
    if a >= 1e6:
        return "Rp " + f"{v / 1e6:.1f}".replace(".", ",") + " jt"
    if a >= 1e3:
        return "Rp " + f"{v / 1e3:.0f}".replace(".", ",") + " rb"
    return rp(v)


def pct(v: float, dec: int = 1) -> str:
    return f"{float(v or 0):.{dec}f}".replace(".", ",")


def lbl_month(p: str) -> str:
    y, m = p.split("-")
    return BULAN[int(m) - 1] + " " + y[2:]


def nfmt(v: float) -> str:
    return f"{float(v or 0):,.0f}".replace(",", ".")


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
    for c in ("revenue", "sessions", "prints", "unlocks", "unlocks_paid"):
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


def build(df: pd.DataFrame, month: str) -> dict:
    months = sorted(df["month"].unique())
    idx = months.index(month) if month in months else len(months) - 1
    prev = months[idx - 1] if idx > 0 else None

    cur = df[df["month"] == month]
    prv = df[df["month"] == prev] if prev else df.iloc[0:0]
    last_day = int(cur["date"].dt.day.max()) if not cur.empty else 0
    if not prv.empty:
        prv = prv[prv["date"].dt.day <= last_day]

    areas = _areas()

    def totals(frame: pd.DataFrame) -> dict:
        s = float(frame["sessions"].sum())
        u = float(frame["unlocks"].sum())
        up = float(frame["unlocks_paid"].sum())
        p = float(frame["prints"].sum())
        r = float(frame["revenue"].sum())
        return {
            "sesi": s, "unlock": u, "unlock_bayar": up, "cetak": p, "omzet": r,
            "conv": (p / s * 100) if s else 0.0,           # cetak / sesi
            "unlock_rate": (u / s * 100) if s else 0.0,    # unlock / sesi
            "print_of_unlock": (p / u) if u else 0.0,      # cetak / unlock
            "rp_cetak": (r / p) if p else 0.0,
            "rp_sesi": (r / s) if s else 0.0,
        }

    t_now, t_prev = totals(cur), totals(prv)

    g = cur.groupby("outlet_name").agg(
        sesi=("sessions", "sum"), unlock=("unlocks", "sum"),
        unlock_bayar=("unlocks_paid", "sum"), cetak=("prints", "sum"), omzet=("revenue", "sum"),
    )
    g = g[g["sesi"] >= 30].copy()
    g["ups"] = g["unlock"] / g["sesi"]
    g["ppu"] = (g["cetak"] / g["unlock"].replace(0, pd.NA)).fillna(0.0)
    g["conv"] = g["cetak"] / g["sesi"] * 100
    g["rp_cetak"] = (g["omzet"] / g["cetak"].replace(0, pd.NA)).fillna(0.0)

    med_ups = float(g["ups"].median()) if not g.empty else 0.0
    med_ppu = float(g["ppu"].median()) if not g.empty else 1.0
    med_conv = float(g["conv"].median()) if not g.empty else 0.0

    rows = []
    for o, r in g.iterrows():
        harga = float(r["rp_cetak"]) or t_now["rp_cetak"]
        if r["ppu"] and r["ppu"] > 0.2 and r["ups"] < med_ups * 0.7:
            missing_unlock = r["sesi"] * (med_ups - r["ups"])
            potensi = missing_unlock * med_ppu * harga
            diagnose = "Tidak buka foto"
            action = "Orang foto tapi tidak membuka hasilnya: cek layar, harga unlock, dan ajakan di booth."
        elif r["ppu"] < med_ppu * 0.8:
            potensi = r["unlock"] * (med_ppu - r["ppu"]) * harga
            diagnose = "Buka tapi tak cetak"
            action = "Sudah buka tapi tidak lanjut cetak: cek printer/kertas & tawaran harga cetak."
        else:
            potensi = 0.0
            diagnose = "Sehat"
            action = "Pertahankan — pakai sebagai pembanding outlet lain."
        rows.append({
            "outlet": o, "area": areas.get(o) or "—",
            "sesi": int(r["sesi"]), "unlock_rate": float(r["ups"] * 100),
            "ppu": float(r["ppu"]), "conv": float(r["conv"]),
            "rp_cetak": harga, "potensi": float(max(0.0, potensi)),
            "diagnosa": diagnose, "aksi": action,
            "cetak": int(r["cetak"]), "omzet": float(r["omzet"]),
        })
    rows.sort(key=lambda x: -x["potensi"])

    potensi_total = sum(x["potensi"] for x in rows)
    bocor = {
        "Tidak buka foto": sum(x["potensi"] for x in rows if x["diagnosa"] == "Tidak buka foto"),
        "Buka tapi tak cetak": sum(x["potensi"] for x in rows if x["diagnosa"] == "Buka tapi tak cetak"),
    }

    buckets = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 60), (60, 100)]
    dist = []
    for lo, hi in buckets:
        sub = g[(g["conv"] >= lo) & (g["conv"] < hi)]
        dist.append({"label": f"{lo}–{hi}%", "n": len(sub), "omzet": float(sub["omzet"].sum())})

    trend_months = months[max(0, idx - 12):idx + 1]
    tm, tc, tu = [], [], []
    for m in trend_months:
        f = df[df["month"] == m]
        s_, u_, p_ = float(f["sessions"].sum()), float(f["unlocks"].sum()), float(f["prints"].sum())
        tm.append(lbl_month(m))
        tc.append((p_ / s_ * 100) if s_ else None)
        tu.append(round(u_ / s_, 2) if s_ else None)

    return {
        "month": month, "prev": prev, "day": last_day, "now": t_now, "prev_t": t_prev,
        "rows": rows, "median_conv": med_conv, "median_ups": med_ups, "median_ppu": med_ppu,
        "potensi": potensi_total, "bocor": bocor, "n_outlet": int(len(g)),
        "dist": dist, "trend": {"m": tm, "conv": tc, "ups": tu},
        "generated": pd.Timestamp.now().strftime("%d %b %H:%M"),
    }


# ── ui ────────────────────────────────────────────────────────────────────

def _css() -> str:
    return """
  .cv-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr)); gap: 10px; }
  .cv-kpi { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; padding: 12px 14px;
            display: flex; flex-direction: column; gap: 2px; min-height: 84px; }
  .cv-kpi .l { font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: @MUT@; font-weight: 700; }
  .cv-kpi .v { font-size: 19px; font-weight: 700; letter-spacing: -.02em; }
  .cv-kpi .s { font-size: 11px; color: @MUT@; }
  .cv-funnel { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 4px; }
  .cv-step { background: @PANEL@; border: 1px solid @LINE@; border-radius: 12px; padding: 12px; position: relative; }
  .cv-step .n { font-size: 10px; letter-spacing: .07em; text-transform: uppercase; color: @MUT@; font-weight: 700; }
  .cv-step .v { font-size: 21px; font-weight: 750; margin-top: 2px; }
  .cv-step .r { font-size: 11px; color: @MUT@; }
  .cv-drop { font-size: 11px; font-weight: 700; margin-top: 4px; }
  .cv-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .cv-table th { text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: .05em;
                 color: @MUT@; padding: 7px 8px; border-bottom: 1px solid @LINE@; white-space: nowrap; }
  .cv-table td { padding: 7px 8px; border-bottom: 1px solid rgba(255,255,255,.04); }
  .cv-table tr:hover td { background: rgba(255,255,255,.02); }
  .cv-bar { height: 6px; border-radius: 999px; background: rgba(255,255,255,.07); overflow: hidden; }
  .cv-bar > i { display: block; height: 100%; }
  .cv-sec { margin-top: 16px; font-size: 11px; text-transform: uppercase; letter-spacing: .07em;
            color: @MUT@; font-weight: 700; }
  @media (max-width: 760px) { .cv-funnel { grid-template-columns: repeat(2, 1fr); } }
""".replace("@PANEL@", C_PANEL).replace("@LINE@", C_LINE).replace("@MUT@", C_MUT)


def kpis_html(m: dict) -> str:
    n, p = m["now"], m["prev_t"]
    d_conv = n["conv"] - p["conv"]
    d_ups = n["unlock_rate"] - p["unlock_rate"]
    d_rp = (n["rp_cetak"] / p["rp_cetak"] - 1) * 100 if p["rp_cetak"] else 0

    def card(label, value, sub, color=None):
        return (f'<div class="cv-kpi"><div class="l">{label}</div>'
                f'<div class="v" style="color:{color or C_TXT}">{value}</div>'
                f'<div class="s">{sub}</div></div>')

    return ('<div class="cv-kpis">'
            + card("Konversi cetak", pct(n["conv"]) + "%",
                   ("+" if d_conv >= 0 else "") + pct(d_conv) + " pp vs bulan lalu",
                   C_MINT if d_conv >= 0 else C_RED)
            + card("Sesi foto", nfmt(n["sesi"]), f'{nfmt(n["cetak"])} cetakan')
            + card("Buka foto / sesi", pct(n["unlock_rate"]) + "%",
                   ("+" if d_ups >= 0 else "") + pct(d_ups) + " pp vs bulan lalu",
                   C_MINT if d_ups >= 0 else C_RED)
            + card("Cetak / buka", pct(n["print_of_unlock"], 2) + "×",
                   f'{nfmt(n["unlock"])} foto dibuka')
            + card("Rp per cetak", rp_short(n["rp_cetak"]), ("+" if d_rp >= 0 else "") + pct(d_rp) + "% vs bulan lalu")
            + card("Rp per sesi", rp_short(n["rp_sesi"]), f'omzet {rp_short(n["omzet"])}')
            + card("Potensi bocor", rp_short(m["potensi"]),
                   f'kejar median {pct(m["median_conv"])}% per bulan', C_AMBER)
            + '</div>')


def funnel_html(m: dict) -> str:
    n = m["now"]
    buka_pct = n["unlock"] / n["sesi"] * 100 if n["sesi"] else 0
    cetak_per_buka = n["print_of_unlock"]
    steps = [
        ("Sesi foto", nfmt(n["sesi"]), "titik awal", "", C_BLUE),
        ("Foto dibuka", nfmt(n["unlock"]), f"{pct(buka_pct)}% dari sesi",
         f'<div class="cv-drop" style="color:{C_RED}">−{pct(100 - buka_pct)}% tidak dibuka</div>', C_VIOLET),
        ("Cetak (bayar)", nfmt(n["cetak"]), f"{pct(cetak_per_buka, 2)}× per foto dibuka", "", C_MINT),
        ("Omzet", rp_short(n["omzet"]), f"{rp_short(n['rp_cetak'])} per cetak", "", C_AMBER),
    ]
    out = []
    for label, val, sub, drop, color in steps:
        out.append(
            f'<div class="cv-step"><div class="n">{label}</div>'
            f'<div class="v" style="color:{color}">{val}</div>'
            f'<div class="r">{sub}</div>{drop}</div>'
        )
    return '<div class="cv-funnel">' + "".join(out) + "</div>"


def table_html(m: dict, limit: int = 18) -> str:
    head = ("<tr><th>#</th><th>Outlet</th><th>Area</th><th>Sesi</th><th>Buka %</th>"
            "<th>Cetak/buka</th><th>Cetak/sesi</th><th>Rp/cetak</th><th>Potensi/bln</th>"
            "<th>Diagnosa</th><th>Aksi</th></tr>")
    body = []
    for i, r in enumerate(m["rows"][:limit], 1):
        tone = C_RED if r["diagnosa"] == "Tidak buka foto" else (
            C_AMBER if r["diagnosa"] == "Buka tapi tak cetak" else C_MINT)
        body.append(
            "<tr>"
            f"<td>{i}</td><td><b>{r['outlet']}</b></td><td>{r['area']}</td><td>{nfmt(r['sesi'])}</td>"
            f"<td>{pct(r['unlock_rate'])}</td><td>{pct(r['ppu'], 2)}×</td><td>{pct(r['conv'])}%</td>"
            f"<td>{rp_short(r['rp_cetak'])}</td>"
            f'<td style="font-weight:650;color:{C_AMBER}">{rp_short(r["potensi"])}</td>'
            f'<td style="color:{tone};font-weight:600">{r["diagnosa"]}</td>'
            f'<td style="color:{C_MUT}">{r["aksi"]}</td>'
            "</tr>"
        )
    return '<div style="overflow:auto"><table class="cv-table">' + head + "".join(body) + "</table></div>"


def dist_html(m: dict) -> str:
    top = max((b["n"] for b in m["dist"]), default=0) or 1
    out = []
    for b in m["dist"]:
        w = b["n"] / top * 100
        out.append(
            f'<div style="display:grid;grid-template-columns:66px 1fr 92px 92px;gap:8px;align-items:center;margin:5px 0">'
            f'<div style="font-size:11px;color:{C_MUT}">{b["label"]}</div>'
            f'<div class="cv-bar"><i style="width:{w:.0f}%;background:{C_BLUE}"></i></div>'
            f'<div style="font-size:11.5px;text-align:right">{b["n"]} outlet</div>'
            f'<div style="font-size:11.5px;text-align:right;color:{C_MUT}">{rp_short(b["omzet"])}</div>'
            "</div>"
        )
    return "".join(out)


# ── page ──────────────────────────────────────────────────────────────────

def create_page(container: ui.column):
    ui.add_head_html("<style>" + _css() + "</style>")
    df = load_daily()
    with container:
        if df.empty:
            ui.label("Data harian belum tersedia.").classes("text-red-400")
            return
        months = sorted(df["month"].unique())

        ui.html('<div style="font-size:19px;font-weight:750;letter-spacing:-.02em">🔄 Analisis Konversi</div>'
                '<div style="font-size:11.5px;color:' + C_MUT + '">Di langkah mana orang berhenti, dan berapa '
                'Rupiah yang tertinggal di situ.</div>', sanitize=False)

        with ui.row().classes("w-full items-center gap-3 mt-2 mb-2"):
            sel = ui.select({m: lbl_month(m) for m in months[::-1]}, value=months[-1],
                            label="Bulan").props("dense outlined dark").classes("w-[150px]")
            info = ui.label("").classes("text-xs")
            info.style("color:" + C_MUT)

        body = ui.column().classes("w-full")

        def render():
            month = sel.value or months[-1]
            m = build(df, month)
            info.set_text(f"1–{m['day']} {lbl_month(month)} vs 1–{m['day']} "
                          f"{lbl_month(m['prev']) if m['prev'] else '—'}")
            body.clear()
            with body:
                ui.html(kpis_html(m), sanitize=False).classes("w-full")

                ui.html('<div class="cv-sec">Funnel bulan ini</div>', sanitize=False).classes("w-full")
                ui.html(funnel_html(m), sanitize=False).classes("w-full")

                ui.html('<div class="cv-sec">Kebocoran per outlet · diurut potensi Rupiah</div>',
                        sanitize=False).classes("w-full")
                ui.html(table_html(m), sanitize=False).classes("w-full")

                with ui.row().classes("w-full gap-3 mt-4 flex-wrap items-start"):
                    with ui.card().classes("flex-1 min-w-[300px]").style(
                            "background:" + C_PANEL + ";border:1px solid " + C_LINE):
                        ui.html('<div class="cv-sec" style="margin-top:0">Sebaran konversi outlet (≥30 sesi)</div>'
                                + dist_html(m), sanitize=False).classes("w-full")
                    with ui.card().classes("flex-1 min-w-[300px]").style(
                            "background:" + C_PANEL + ";border:1px solid " + C_LINE):
                        ui.html('<div class="cv-sec" style="margin-top:0">Dari mana kebocoran terbesar</div>'
                                + "".join(
                                    f'<div style="display:flex;justify-content:space-between;font-size:12px;margin:6px 0">'
                                    f'<span style="color:{C_MUT}">{k}</span>'
                                    f'<b style="color:{C_AMBER}">{rp_short(v)}</b></div>'
                                    for k, v in m["bocor"].items())
                                + '<div style="font-size:10.5px;color:' + C_MUT + ';margin-top:8px;line-height:1.5">'
                                  "Potensi = sesi × selisih konversi ke median × Rp per cetak outlet itu sendiri. "
                                  "Angka ini batas atas, bukan janji.</div>",
                                sanitize=False).classes("w-full")

                with ui.card().classes("w-full mt-3").style(
                        "background:" + C_PANEL + ";border:1px solid " + C_LINE):
                    ui.html('<div class="cv-sec" style="margin-top:0">Tren 13 bulan · konversi cetak</div>',
                            sanitize=False).classes("w-full")
                    fig = go.Figure()
                    fig.add_scatter(x=m["trend"]["m"], y=m["trend"]["conv"], name="Konversi %",
                                    mode="lines+markers", line=dict(color=C_MINT, width=2))
                    fig.update_layout(template="plotly_dark", height=250, showlegend=False,
                                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      margin=dict(l=8, r=8, t=8, b=8),
                                      yaxis=dict(title="%", gridcolor="#24242f"),
                                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
                    ui.plotly(fig).classes("w-full h-[250px]")

                ui.html('<div style="font-size:10.5px;color:' + C_MUT + ';margin-top:8px;line-height:1.5">'
                        "Konversi = cetakan ÷ sesi foto. Buka foto = jumlah foto yang dibuka ÷ sesi (unlock gratis dari "
                        "bundel cetak ikut dihitung, karena itu yang dilihat pelanggan). Cetak/buka ≈ 1 berarti "
                        "hampir semua yang membuka langsung mencetak. Median dari " + str(m["n_outlet"]) +
                        " outlet dengan ≥30 sesi bulan ini · dihitung " + m["generated"] + ".</div>", sanitize=False).classes("w-full")

        sel.on("change", lambda e: render())
        render()
