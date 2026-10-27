"""AI Decision v2 — keputusan operasional yang bisa dihitung dan ditindaklanjuti.

Bukan narasi: setiap baris = 1 keputusan dengan bukti angka, dampak Rupiah,
aksi spesifik, pemilik, dan SLA. Aturan deterministik (bisa diaudit), tanpa
LLM yang mengarang.

Basis perbandingan: MTD vs MTD (tanggal 1..hari terakhir data, bulan ini vs
bulan lalu pada tanggal yang sama), dampak diskalakan ke panjang bulan penuh.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from nicegui import ui

ROOT = Path(__file__).resolve().parents[2]
DAILY = ROOT / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"

C_BG = "#12121a"
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

_cache: dict = {"data": None, "mtime": None}

RULES = {
    "MATI": {"label": "Outlet mati", "owner": "Ops Area", "sla": "1×24 jam", "tone": C_RED},
    "TURUN": {"label": "Turun tajam", "owner": "Ops Area", "sla": "3 hari", "tone": C_RED},
    "TRAFIK": {"label": "Traffic jatuh", "owner": "Ops Area", "sla": "7 hari", "tone": C_AMBER},
    "KONVERSI": {"label": "Konversi jatuh", "owner": "Sales + Ops", "sla": "7 hari", "tone": C_AMBER},
    "ARPS": {"label": "Nilai per sesi turun", "owner": "Sales", "sla": "7 hari", "tone": C_AMBER},
    "NAIK": {"label": "Bisa diduplikasi", "owner": "Owner + Marketing", "sla": "14 hari", "tone": C_MINT},
    "TIPIS": {"label": "Basis data tipis", "owner": "Ops Area", "sla": "14 hari", "tone": C_MUT},
}


# ── format ────────────────────────────────────────────────────────────────

def num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def rp(v: float) -> str:
    return "Rp " + num(round(v))


def rp_short(v: float) -> str:
    v = float(v or 0)
    a = abs(v)
    if a >= 1_000_000_000:
        return "Rp " + f"{v / 1_000_000_000:.1f}".replace(".", ",") + " M"
    if a >= 1_000_000:
        return "Rp " + f"{v / 1_000_000:.1f}".replace(".", ",") + " jt"
    if a >= 1_000:
        return "Rp " + f"{v / 1_000:.0f}" + " rb"
    return rp(v)


def pct(v: float, sign: bool = True) -> str:
    if v is None:
        return "—"
    s = f"{v:+.1f}%" if sign else f"{v:.1f}%"
    return s.replace(".", ",")


def intp(v: float) -> str:
    return num(v)


def _delta_span(now: float, prev: float) -> str:
    if not prev:
        return "—"
    return pct((now / prev - 1) * 100)


# ── data ──────────────────────────────────────────────────────────────────

def load_daily() -> pd.DataFrame:
    try:
        mtime = DAILY.stat().st_mtime
    except OSError:
        return pd.DataFrame()
    if _cache["data"] is not None and _cache["mtime"] == mtime:
        return _cache["data"]
    rows = json.loads(DAILY.read_text())
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["outlet_name"] = df["outlet_name"].astype(str).str.strip()
    df = df[~df["outlet_name"].str.lower().str.startswith(JUNK)]
    for c in ("revenue", "sessions", "prints", "unlocks_paid"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(0.0)
    df = df.sort_values("date")
    _cache["data"] = df
    _cache["mtime"] = mtime
    return df


def _areas() -> dict:
    try:
        from services.dashboard_adapter import get_adapter

        m = get_adapter().load_data()
        m = m.dropna(subset=["area"])
        m = m[m["area"].astype(str).str.strip() != ""]
        m = m.sort_values("periode")
        return m.groupby("outlet_name")["area"].last().to_dict()
    except Exception:
        return {}


# ── engine ────────────────────────────────────────────────────────────────

def build_decisions() -> dict:
    df = load_daily()
    if df.empty:
        return {"error": "Data harian tidak tersedia."}

    last = df["date"].max()
    mstart = last.replace(day=1)
    pm_start = (mstart - pd.Timedelta(days=1)).replace(day=1)
    pm_same_end = pm_start + pd.Timedelta(days=last.day - 1)
    days_in_month = int((mstart + pd.offsets.MonthEnd(1)).day)
    scale = days_in_month / max(1, last.day)

    cur = df[(df["date"] >= mstart) & (df["date"] <= last)]
    prv = df[(df["date"] >= pm_start) & (df["date"] <= pm_same_end)]
    m2 = df[(df["date"] >= (pm_start - pd.offsets.MonthBegin(1))) & (df["date"] < pm_start)]
    m3 = df[(df["date"] >= (pm_start - pd.offsets.MonthBegin(2))) & (df["date"] < (pm_start - pd.offsets.MonthBegin(1)))]

    def agg(frame: pd.DataFrame) -> pd.DataFrame:
        g = frame.groupby("outlet_name").agg(
            rev=("revenue", "sum"), ses=("sessions", "sum"), pr=("prints", "sum")
        )
        g["conv"] = (g["pr"] / g["ses"].replace(0, pd.NA) * 100).fillna(0.0)
        g["arps"] = (g["rev"] / g["ses"].replace(0, pd.NA)).fillna(0.0)
        return g

    cur_g, prv_g, m2_g, m3_g = agg(cur), agg(prv), agg(m2), agg(m3)
    areas = _areas()

    outlets = sorted(set(cur_g.index) | set(prv_g.index))
    rows = []
    for o in outlets:
        c = cur_g.loc[o] if o in cur_g.index else None
        p = prv_g.loc[o] if o in prv_g.index else None
        rev_now = float(c["rev"]) if c is not None else 0.0
        rev_prev = float(p["rev"]) if p is not None else 0.0
        ses_now = float(c["ses"]) if c is not None else 0.0
        ses_prev = float(p["ses"]) if p is not None else 0.0
        pr_now = float(c["pr"]) if c is not None else 0.0
        conv_now = float(c["conv"]) if c is not None else 0.0
        conv_prev = float(p["conv"]) if p is not None else 0.0
        arps_now = float(c["arps"]) if c is not None else 0.0
        arps_prev = float(p["arps"]) if p is not None else 0.0
        float(m2_g.loc[o]["rev"]) if o in m2_g.index else 0.0
        float(m3_g.loc[o]["rev"]) if o in m3_g.index else 0.0

        area = areas.get(o) or "—"
        rev_per_print = (rev_now / pr_now) if pr_now > 0 else 0.0
        rev_per_session = arps_now

        def add(rule: str, impact: float, title: str, evidence: list[str], action: str, conf: str = "tinggi"):
            rows.append({
                "rule": rule, "outlet": o, "area": area,
                "impact": float(max(0.0, impact)), "title": title,
                "evidence": evidence, "action": action, "conf": conf,
                **RULES[rule],
            })

        # 1. outlet mati
        if rev_now <= 0 and rev_prev >= 3_000_000:
            add("MATI", rev_prev * scale,
                f"{o} berhenti produksi",
                [f"1–{last.day} bulan ini: Rp 0", f"periode sama bulan lalu: {rp_short(rev_prev)}",
                 f"sesi: {intp(ses_now)} vs {intp(ses_prev)}"],
                "Cek di tempat: listrik, jaringan, printer, dan posisi booth. Kalau pindah/relokasi, "
                "update status outlet supaya tidak dihitung mati.")
        # 2. turun tajam
        elif rev_prev > 0 and rev_now < rev_prev * 0.7 and (rev_prev - rev_now) >= 3_000_000:
            gap = (rev_prev - rev_now) * scale
            add("TURUN", gap, f"{o} kehilangan {rp_short(gap)}/bulan",
                [f"omzet {rp_short(rev_now)} vs {rp_short(rev_prev)} ({_delta_span(rev_now, rev_prev)})",
                 f"sesi {intp(ses_now)} vs {intp(ses_prev)} ({_delta_span(ses_now, ses_prev)})",
                 f"konversi {pct(conv_now, False)} vs {pct(conv_prev, False)}"],
                "Pisahkan penyebabnya dulu: kalau sesi turun → traffic/lokasi; kalau sesi sama tapi "
                "konversi turun → harga, tampilan, atau printer bermasalah.")
        # 3. traffic jatuh, konversi membaik
        elif ses_prev >= 150 and ses_now < ses_prev * 0.75 and conv_now >= conv_prev:
            gap = (ses_prev - ses_now) * scale * max(rev_per_session, 1)
            add("TRAFIK", gap, f"{o} kehilangan traffic",
                [f"sesi {intp(ses_now)} vs {intp(ses_prev)} ({_delta_span(ses_now, ses_prev)})",
                 f"konversi justru naik {pct(conv_now, False)} vs {pct(conv_prev, False)}",
                 f"nilai per sesi {rp(rev_per_session)}"],
                "Masalahnya di traffic, bukan mesin: cek jam buka, lokasi booth, dan apakah ada "
                "event/penutupan akses di sekitar outlet.")
        # 4. konversi jatuh
        elif conv_prev - conv_now >= 5 and ses_now >= 200:
            lost_prints = ses_now * (conv_prev - conv_now) / 100
            gap = lost_prints * (rev_per_print or rev_per_session * 3)
            add("KONVERSI", gap * scale, f"{o} konversi turun {str(round(conv_prev - conv_now, 1)).replace('.', ',')} pp",
                [f"konversi {pct(conv_now, False)} vs {pct(conv_prev, False)}",
                 f"sesi {intp(ses_now)} (cukup untuk disimpulkan)",
                 f"perkiraan cetak hilang {intp(lost_prints)} lembar"],
                "Cek harga/tampilan produk dan flow bayar di layar. Kalau printer error, ini yang "
                "pertama terlihat sebagai konversi jatuh.")
        # 5. nilai per sesi turun
        elif arps_prev > 0 and arps_now < arps_prev * 0.8 and ses_now >= 200:
            gap = (arps_prev - arps_now) * ses_now * scale
            add("ARPS", gap, f"{o} nilai per sesi turun",
                [f"nilai/sesi {rp(arps_now)} vs {rp(arps_prev)} ({_delta_span(arps_now, arps_prev)})",
                 f"sesi {intp(ses_now)} (stabil)",
                 f"konversi {pct(conv_now, False)}"],
                "Traffic aman tapi keranjang mengecil: cek komposisi produk (unlock vs print) dan "
                "apakah ada diskon/promo yang tidak terkontrol.")
        # 6. peluang duplikasi
        elif rev_prev > 0 and rev_now > rev_prev * 1.3 and (rev_now - rev_prev) >= 3_000_000:
            add("NAIK", (rev_now - rev_prev) * scale, f"Pola {o} bisa diduplikasi",
                [f"omzet {rp_short(rev_now)} vs {rp_short(rev_prev)} ({_delta_span(rev_now, rev_prev)})",
                 f"sesi {intp(ses_now)} vs {intp(ses_prev)}",
                 f"konversi {pct(conv_now, False)} vs {pct(conv_prev, False)}"],
                "Catat apa yang berbeda (tema foto, jam ramai, operator, event sekitar), lalu uji "
                "pola yang sama di 2 outlet dengan profil mirip.")
        # 7. data tipis
        elif 0 < rev_now < 1_000_000 and ses_now < 60:
            add("TIPIS", 0, f"{o} datanya terlalu tipis untuk dinilai",
                [f"sesi {intp(ses_now)} · omzet {rp_short(rev_now)}",
                 "tidak cukup untuk menyimpulkan tren"],
                "Jangan ambil keputusan dari outlet ini. Cek apakah mesin benar-benar aktif atau "
                "hanya sesekali dipakai.", conf="rendah")

    # prioritas: dampak Rupiah, kritis dulu
    grp = {"MATI": 0, "TURUN": 0, "TRAFIK": 0, "KONVERSI": 0, "ARPS": 0}
    rows.sort(key=lambda r: (grp.get(r["rule"], 1 if r["rule"] == "NAIK" else 2), -r["impact"]))

    # ringkasan jaringan
    tot_now, tot_prev = float(cur["revenue"].sum()), float(prv["revenue"].sum())
    ses_now_t, ses_prev_t = float(cur["sessions"].sum()), float(prv["sessions"].sum())
    pr_now_t, pr_prev_t = float(cur["prints"].sum()), float(prv["prints"].sum())
    conv_t = pr_now_t / ses_now_t * 100 if ses_now_t else 0
    conv_p = pr_prev_t / ses_prev_t * 100 if ses_prev_t else 0
    arps_t = tot_now / ses_now_t if ses_now_t else 0
    arps_p = tot_prev / ses_prev_t if ses_prev_t else 0

    lost = sum(r["impact"] for r in rows if r["rule"] in ("MATI", "TURUN", "TRAFIK", "KONVERSI", "ARPS"))
    gain = sum(r["impact"] for r in rows if r["rule"] == "NAIK")

    return {
        "rows": rows,
        "last": last.strftime("%Y-%m-%d"),
        "day": int(last.day),
        "days_in_month": days_in_month,
        "period_label": f"1–{last.day} {last.strftime('%b')} vs 1–{last.day} {pm_same_end.strftime('%b %Y')}",
        "net": {
            "rev_now": tot_now, "rev_prev": tot_prev,
            "ses_now": ses_now_t, "ses_prev": ses_prev_t,
            "conv_now": conv_t, "conv_prev": conv_p,
            "arps_now": arps_t, "arps_prev": arps_p,
            "outlets_now": int((cur.groupby("outlet_name")["revenue"].sum() > 0).sum()),
            "outlets_prev": int((prv.groupby("outlet_name")["revenue"].sum() > 0).sum()),
        },
        "lost": lost, "gain": gain,
        "counts": {k: sum(1 for r in rows if r["rule"] == k) for k in RULES},
        "generated": datetime.now().strftime("%d %b %Y %H:%M"),
    }


# ── html ──────────────────────────────────────────────────────────────────

def _css() -> str:
    return """
  .ad-wrap { font-family: 'DM Sans', system-ui, sans-serif; color: @TXT@; }
  .ad-lab { font-size: 10.5px; letter-spacing: .09em; text-transform: uppercase; color: @MUT@;
            font-weight: 700; margin: 0 0 4px; }
  .ad-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); gap: 10px; }
  .ad-kpi { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; padding: 12px 14px;
            display: flex; flex-direction: column; gap: 2px; min-height: 92px; }
  .ad-kpi .v { font-size: 20px; font-weight: 700; letter-spacing: -.02em; }
  .ad-kpi .d { font-size: 11px; color: @MUT@; }
  .ad-card { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; padding: 14px 16px;
             margin-top: 12px; border-left: 3px solid @LINE@; }
  .ad-card .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .ad-card h3 { margin: 0; font-size: 14.5px; font-weight: 700; }
  .ad-card .imp { font-size: 15px; font-weight: 700; white-space: nowrap; }
  .ad-card ul { margin: 8px 0 0; padding-left: 16px; }
  .ad-card li { font-size: 12px; color: #c9cede; line-height: 1.5; margin: 2px 0; }
  .ad-act { margin-top: 9px; font-size: 12.5px; color: @TXT@; background: rgba(91,140,255,.08);
            border: 1px solid rgba(91,140,255,.22); border-radius: 9px; padding: 8px 10px; line-height: 1.5; }
  .ad-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 9px; }
  .ad-chip { font-size: 10.5px; font-weight: 650; padding: 3px 8px; border-radius: 999px;
             background: rgba(255,255,255,.05); border: 1px solid @LINE@; color: #c9cede; }
  .ad-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .ad-table th { text-align: left; font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em;
                 color: @MUT@; padding: 8px; border-bottom: 1px solid @LINE@; position: sticky; top: 0;
                 background: @PANEL@; }
  .ad-table td { padding: 8px; border-bottom: 1px solid rgba(255,255,255,.04); vertical-align: top; }
  .ad-table tr:hover td { background: rgba(255,255,255,.02); }
  .ad-sec { margin-top: 18px; }
  @media (max-width: 560px) {
    .ad-card .top { flex-direction: column; gap: 4px; }
    .ad-card h3 { font-size: 13.5px; line-height: 1.35; }
    .ad-card .imp { align-self: flex-start; }
    .ad-kpis { grid-template-columns: repeat(2, 1fr); }
  }
""".replace("@TXT@", C_TXT).replace("@MUT@", C_MUT).replace("@PANEL@", C_PANEL).replace("@LINE@", C_LINE)


def kpis_html(m: dict) -> str:
    n = m["net"]

    def kpi(label, value, sub, color=None):
        return (f'<div class="ad-kpi"><div class="ad-lab">{label}</div>'
                f'<div class="v" style="color:{color or C_TXT}">{value}</div>'
                f'<div class="d">{sub}</div></div>')

    (n["rev_now"] / n["rev_prev"] - 1) * 100 if n["rev_prev"] else 0
    (n["ses_now"] / n["ses_prev"] - 1) * 100 if n["ses_prev"] else 0
    d_conv = n["conv_now"] - n["conv_prev"]
    (n["arps_now"] / n["arps_prev"] - 1) * 100 if n["arps_prev"] else 0
    net = m["gain"] - m["lost"]

    return (
        '<div class="ad-kpis">'
        + kpi("Dampak keputusan", rp_short(m["lost"]), f"potensi hilang s/d {m['days_in_month']} hari", C_RED)
        + kpi("Peluang diduplikasi", rp_short(m["gain"]), "kalau pola yang naik ditiru", C_MINT)
        + kpi("Selisih bersih", rp_short(abs(net)), ("surplus" if net >= 0 else "defisit") + " per bulan",
              C_MINT if net >= 0 else C_RED)
        + kpi("Omzet MTD", rp_short(n["rev_now"]), _delta_span(n["rev_now"], n["rev_prev"]) + " vs bulan lalu")
        + kpi("Sesi MTD", intp(n["ses_now"]), _delta_span(n["ses_now"], n["ses_prev"]) + " vs bulan lalu")
        + kpi("Konversi", pct(n["conv_now"], False), pct(d_conv, True) + " pp vs bulan lalu")
        + "</div>"
    )


def decisions_html(rows: list, limit: int = 6) -> str:
    out = []
    for r in rows[:limit]:
        tone = r["tone"]
        area_suffix = (" · " + r["area"]) if r["area"] not in ("—", "", None) else ""
        imp = rp_short(r["impact"]) if r["impact"] > 0 else "—"
        ev = "".join(f"<li>{e}</li>" for e in r["evidence"])
        out.append(
            f'<div class="ad-card" style="border-left-color:{tone}">'
            '<div class="top"><div>'
            f'<div class="ad-lab" style="color:{tone}">{r["label"]}{area_suffix}</div>'
            f'<h3>{r["title"]}</h3></div>'
            f'<div class="imp" style="color:{tone}">{imp}<span style="font-size:10px;color:{C_MUT};font-weight:500">/bln</span></div>'
            "</div>"
            f"<ul>{ev}</ul>"
            f'<div class="ad-act">{r["action"]}</div>'
            '<div class="ad-chips">'
            f'<span class="ad-chip">Owner: {r["owner"]}</span>'
            f'<span class="ad-chip">SLA: {r["sla"]}</span>'
            f'<span class="ad-chip">Keyakinan: {r["conf"]}</span>'
            f'<span class="ad-chip">{r["rule"]}</span>'
            "</div></div>"
        )
    return "".join(out)


def table_html(rows: list) -> str:
    head = ("<tr><th>#</th><th>Jenis</th><th>Outlet</th><th>Area</th><th>Dampak/bln</th>"
            "<th>Bukti</th><th>Aksi</th><th>Owner · SLA</th></tr>")
    body = []
    for i, r in enumerate(rows, 1):
        imp = rp_short(r["impact"]) if r["impact"] > 0 else "—"
        body.append(
            "<tr>"
            f"<td>{i}</td>"
            f'<td><span style="color:{r["tone"]};font-weight:650">{r["label"]}</span></td>'
            f"<td>{r['outlet']}</td><td>{r['area']}</td>"
            f'<td style="white-space:nowrap;font-weight:650">{imp}</td>'
            f'<td style="color:{C_MUT}">{"; ".join(r["evidence"][:2])}</td>'
            f"<td>{r['action']}</td>"
            f'<td style="white-space:nowrap">{r["owner"]}<br><span style="color:{C_MUT}">{r["sla"]}</span></td>'
            "</tr>"
        )
    return ('<div style="max-height:520px;overflow:auto;border:1px solid ' + C_LINE + ';border-radius:12px">'
            '<table class="ad-table">' + head + "".join(body) + "</table></div>")


# ── page ──────────────────────────────────────────────────────────────────

def create_page(container: ui.column):
    ui.add_head_html("<style>" + _css() + "</style>")
    m = build_decisions()
    with container:
        if m.get("error"):
            ui.label(m["error"]).classes("text-red-400")
            return

        holder = {}

        def render():
            rows = m["rows"]
            mode = holder["filter"].value
            view = rows if mode == "Semua" else [r for r in rows if r["rule"] == mode]
            with holder["body"]:
                holder["body"].clear()
                ui.html(kpis_html(m), sanitize=False).classes("w-full")
                ui.html('<div class="ad-sec"><div class="ad-lab">Keputusan teratas · diurut dampak Rupiah</div>'
                        + decisions_html(view, 6) + "</div>", sanitize=False).classes("w-full")
                ui.html('<div class="ad-sec"><div class="ad-lab">Semua temuan (' + str(len(view)) + ")</div></div>",
                        sanitize=False).classes("w-full")
                ui.html(table_html(view), sanitize=False).classes("w-full")
                ui.html(
                    '<div class="ad-note" style="color:' + C_MUT + ';font-size:11px;margin-top:10px">'
                    "Aturan deterministik: MATI (omzet 0, bulan lalu ≥ Rp3 jt), TURUN (>30% & ≥Rp3 jt), "
                    "TRAFIK (sesi −25%), KONVERSI (−5 pp), ARPS (−20%), NAIK (>30%), TIPIS (data kurang). "
                    "Dampak diskalakan ke " + str(m["days_in_month"]) + " hari. Basis: " + m["period_label"]
                    + " · dihitung " + m["generated"] + ".</div>",
                    sanitize=False).classes("w-full")

        with ui.row().classes("w-full items-center gap-3 mb-2"):
            ui.html(
                '<div class="ad-wrap"><div style="font-size:19px;font-weight:750;letter-spacing:-.02em">'
                "🎯 AI Decision</div>"
                '<div style="font-size:11.5px;color:' + C_MUT + '">Keputusan yang bisa dihitung: bukti angka, '
                "dampak Rupiah, satu aksi, satu pemilik. Basis " + m["period_label"] + ".</div></div>",
                sanitize=False)
            ui.space()
            holder["filter"] = ui.select(
                ["Semua"] + [k for k in RULES if m["counts"].get(k)],
                value="Semua", label="Jenis",
            ).props("dense outlined dark").classes("w-[190px]")
            holder["filter"].on("change", lambda e: render())

        holder["body"] = ui.column().classes("w-full")
        render()
