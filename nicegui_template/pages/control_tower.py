"""Control Tower — halaman utama dashboard Difotoin.

Varian A dari redesign: ringkasan bulan berjalan (MTD vs MTD bulan sebelumnya,
apple to apple), panel temuan yang butuh keputusan, bauran area, tabel outlet
exception-first, dan strip omzet harian.

Semua angka dihitung dari `daily_summary.json` (per outlet per hari) dan
`dashboard_summary.json` (metadata area/kategori per periode). Nol angka hardcode.
"""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import date
from pathlib import Path

from nicegui import ui

ROOT = Path(__file__).resolve().parents[2]
DAILY_PATH = ROOT / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"
SUMMARY_PATH = ROOT / "streamlit_template" / "data" / "api_cache" / "dashboard_summary.json"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

C_BG = "#0c0c12"
C_PANEL = "#15151e"
C_LINE = "#24242f"
C_TXT = "#eceef4"
C_MUT = "#8b90a3"
C_MINT = "#3ddc97"
C_AMBER = "#f5b942"
C_RED = "#f2685f"
C_BLUE = "#5b9cff"

CT_CSS = """
<style>
  .ct-wrap { max-width: 1360px; margin: 0 auto; padding: 4px 6px 28px; color: %(txt)s;
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 13px; }
  .ct-wrap .num { font-variant-numeric: tabular-nums; }
  .ct-head { display: flex; align-items: center; gap: 12px; padding-bottom: 16px;
    border-bottom: 1px solid %(line)s; flex-wrap: wrap; }
  .ct-brand { font-weight: 700; font-size: 15px; }
  .ct-brand span { color: %(mut)s; font-weight: 500; }
  .ct-pill { border: 1px solid %(line)s; background: %(panel)s; color: %(mut)s;
    padding: 5px 11px; border-radius: 999px; font-size: 11px; }
  .ct-live { margin-left: auto; display: flex; align-items: center; gap: 7px; color: %(mut)s; font-size: 11px; }
  .ct-dot { width: 6px; height: 6px; border-radius: 50%%; background: %(mint)s; box-shadow: 0 0 0 3px %(mint)s22; }
  .ct-sec { margin-top: 22px; }
  .ct-h { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
  .ct-h b { font-size: 13px; font-weight: 650; }
  .ct-h i { font-style: normal; color: %(mut)s; font-size: 11px; }
  .ct-grid4 { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
  .ct-kpi { background: %(panel)s; border: 1px solid %(line)s; border-radius: 11px; padding: 13px 14px 11px; }
  .ct-kpi-top { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
  .ct-lab { color: %(mut)s; font-size: 10.5px; letter-spacing: .8px; text-transform: uppercase; }
  .ct-chip { font-size: 10.5px; font-weight: 600; padding: 2px 6px; border-radius: 5px; white-space: nowrap; }
  .ct-val { font-size: 25px; font-weight: 650; margin: 7px 0 6px; letter-spacing: -.4px; }
  .ct-sub { color: %(mut)s; font-size: 10.5px; }
  .ct-cols { display: grid; grid-template-columns: 1.55fr 1fr; gap: 12px; align-items: start; }
  .ct-card { background: %(panel)s; border: 1px solid %(line)s; border-radius: 11px; padding: 14px; }
  .ct-issue { display: grid; grid-template-columns: 3px 1fr auto; gap: 12px; align-items: center; padding: 10px 0; }
  .ct-issue + .ct-issue { border-top: 1px solid %(line)s; }
  .ct-sev { width: 3px; height: 32px; border-radius: 2px; }
  .ct-issue p { margin: 0; }
  .ct-t { font-weight: 600; font-size: 12.5px; }
  .ct-d { color: %(mut)s; font-size: 11px; margin-top: 3px; }
  .ct-n { font-size: 19px; font-weight: 650; font-variant-numeric: tabular-nums; }
  .ct-mix { display: grid; grid-template-columns: 86px 1fr 86px; gap: 9px; align-items: center; padding: 5px 0; }
  .ct-mix-name { color: %(mut)s; font-size: 11.5px; }
  .ct-track { display: block; height: 6px; border-radius: 3px; background: #1e1e29; overflow: hidden; }
  .ct-fill { display: block; height: 6px; border-radius: 3px;
    background-image: linear-gradient(90deg, %(blue)s, %(mint)s); }
  .ct-mix-val { text-align: right; font-size: 11px; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .ct-table { width: 100%%; border-collapse: collapse; }
  .ct-table th { text-align: left; font-size: 10px; letter-spacing: .7px; text-transform: uppercase;
    color: %(mut)s; font-weight: 600; padding: 0 10px 7px; border-bottom: 1px solid %(line)s; }
  .ct-table th.r { text-align: right; }
  .ct-table td { padding: 8px 10px; border-bottom: 1px solid #1b1b25; font-size: 12px; }
  .ct-table tr.zero td:first-child { box-shadow: inset 3px 0 0 %(red)s; }
  .ct-table tr.warn td:first-child { box-shadow: inset 3px 0 0 %(amber)s; }
  .ct-on { font-weight: 550; }
  .ct-note { color: %(mut)s; font-size: 10px; margin-left: 7px; border: 1px solid %(line)s;
    padding: 1px 5px; border-radius: 4px; white-space: nowrap; }
  .ct-mut { color: %(mut)s; }
  .ct-r { text-align: right; }
  .ct-up { color: %(mint)s; }
  .ct-down { color: %(red)s; }
  .ct-bad { color: %(amber)s; }
  .ct-foot { display: flex; justify-content: space-between; color: %(mut)s; font-size: 10.5px; padding-top: 9px; }
  .ct-strip { display: flex; align-items: flex-end; gap: 3px; height: 54px; margin-top: 6px; }
  .ct-bar { flex: 1; background: #2b3654; border-radius: 2px 2px 0 0; }
  .ct-bar.last { background: %(mint)s; }
  .ct-empty { color: %(mut)s; padding: 18px 0; }
  @media (max-width: 900px) {
    .ct-grid4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .ct-cols { grid-template-columns: 1fr; }
    .ct-live { margin-left: 0; }
    .ct-val { font-size: 21px; }
  }
</style>
""" % {"txt": C_TXT, "panel": C_PANEL, "line": C_LINE, "mut": C_MUT, "mint": C_MINT,
       "amber": C_AMBER, "red": C_RED, "blue": C_BLUE}

_cache: dict = {"daily": None, "daily_mtime": None, "summary": None, "summary_mtime": None}


# ── data ──────────────────────────────────────────────────────────────────

def _read_json(path: Path, key: str):
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    if _cache[key] is not None and _cache[key + "_mtime"] == mtime:
        return _cache[key]
    try:
        data = json.loads(path.read_text())
    except Exception:
        data = []
    _cache[key] = data
    _cache[key + "_mtime"] = mtime
    return data


def _daily() -> list:
    return _read_json(DAILY_PATH, "daily")


def _summary() -> list:
    return _read_json(SUMMARY_PATH, "summary")


def _periods(daily: list) -> list:
    return sorted({str(r.get("date", ""))[:7] for r in daily if r.get("date")})


def _month_label(period: str) -> str:
    y, mo = period.split("-")
    return f"{MONTHS[int(mo) - 1]} {y}"


def _prev_period(period: str) -> str:
    y, mo = int(period[:4]), int(period[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def _cutoff(period: str, today: date) -> int:
    """Hari terakhir yang dihitung di dalam periode (clamp ke panjang bulan)."""
    y, mo = int(period[:4]), int(period[5:7])
    last = monthrange(y, mo)[1]
    if (y, mo) == (today.year, today.month):
        return min(today.day, last)
    return last


def _prev_cutoff(period: str, prev: str, cut: int, today: date) -> int:
    """Cutoff pembanding: periode yang sama hari, bukan bulan penuh.

    Bulan berjalan dibanding potongan hari yang sama (1..cut). Bulan lampau
    dibanding bulan penuh sebelumnya.
    """
    y, mo = int(period[:4]), int(period[5:7])
    last_prev = monthrange(int(prev[:4]), int(prev[5:7]))[1]
    if (y, mo) == (today.year, today.month):
        return min(cut, last_prev)
    return last_prev


# ── format ────────────────────────────────────────────────────────────────

def rp(v: float) -> str:
    v = float(v or 0)
    if abs(v) >= 1e9:
        return "Rp " + f"{v / 1e9:.1f}".replace(".", ",") + " M"
    if abs(v) >= 1e6:
        return "Rp " + f"{v / 1e6:.1f}".replace(".", ",") + " jt"
    if abs(v) >= 1e3:
        return "Rp " + f"{v / 1e3:.1f}".replace(".", ",") + " rb"
    return "Rp 0"


def num(v) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def pct(v, d: int = 1) -> str:
    try:
        return f"{float(v):.{d}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def idn(v, d: int = 1) -> str:
    try:
        return f"{float(v):.{d}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def tgl(iso: str) -> str:
    try:
        y, mo, d = iso.split("-")
        return f"{int(d)} {MONTHS[int(mo) - 1]}"
    except Exception:
        return iso


# ── hitung ────────────────────────────────────────────────────────────────

def _agg(rows, start: str, end: str) -> dict:
    rev = ses = unl = pr = 0.0
    outlets = set()
    for r in rows:
        d = str(r.get("date", ""))
        if not (start <= d <= end):
            continue
        rev += float(r.get("revenue") or 0)
        ses += float(r.get("sessions") or 0)
        unl += float(r.get("unlocks") or 0)
        pr += float(r.get("prints") or 0)
        outlets.add(str(r.get("outlet_name", "")).strip())
    return {
        "revenue": rev, "sessions": ses, "unlocks": unl, "prints": pr, "outlets": len(outlets),
        "conv": (unl / ses * 100) if ses else 0.0,
        "rps": (rev / ses) if ses else 0.0,
    }


def compute(period: str, today: date | None = None) -> dict:
    today = today or date.today()
    daily = _daily()
    prev = _prev_period(period)
    cut = _cutoff(period, today)
    pcut = _prev_cutoff(period, prev, cut, today)

    cur = _agg(daily, f"{period}-01", f"{period}-{cut:02d}")
    base = _agg(daily, f"{prev}-01", f"{prev}-{pcut:02d}")

    area_map: dict[str, str | None] = {}
    for r in _summary():
        if str(r.get("periode")) == period:
            area_map[str(r.get("outlet_name", "")).strip()] = (r.get("area") or None)

    by: dict[str, dict] = {}
    for r in daily:
        d = str(r.get("date", ""))
        if not (f"{period}-01" <= d <= f"{period}-{cut:02d}"):
            continue
        name = str(r.get("outlet_name", "")).strip()
        o = by.setdefault(name, {"revenue": 0.0, "sessions": 0.0, "unlocks": 0.0, "prints": 0.0})
        o["revenue"] += float(r.get("revenue") or 0)
        o["sessions"] += float(r.get("sessions") or 0)
        o["unlocks"] += float(r.get("unlocks") or 0)
        o["prints"] += float(r.get("prints") or 0)

    prev_by: dict[str, float] = {}
    for r in daily:
        d = str(r.get("date", ""))
        if not (f"{prev}-01" <= d <= f"{prev}-{pcut:02d}"):
            continue
        name = str(r.get("outlet_name", "")).strip()
        prev_by[name] = prev_by.get(name, 0.0) + float(r.get("revenue") or 0)

    outlets = []
    for name, o in by.items():
        ses = o["sessions"]
        outlets.append({
            "name": name,
            "area": area_map.get(name),
            "revenue": o["revenue"],
            "sessions": ses,
            "prints": o["prints"],
            "conv": (o["unlocks"] / ses * 100) if ses else 0.0,
            "prev_rev": prev_by.get(name, 0.0),
        })

    zero = [x for x in outlets if x["revenue"] == 0 and x["sessions"] >= 20]
    noarea = [x for x in outlets if not x["area"]]
    hiconv = [x for x in outlets if x["conv"] > 100]

    areas: dict[str, float] = {}
    for x in outlets:
        key = x["area"] or "Tanpa area"
        areas[key] = areas.get(key, 0.0) + x["revenue"]
    mix = sorted(areas.items(), key=lambda kv: -kv[1])
    if len(mix) > 7:
        head, tail = mix[:7], mix[7:]
        mix = head + [(f"{len(tail)} area lain", sum(v for _, v in tail))]

    series = []
    for r in daily:
        d = str(r.get("date", ""))
        if d >= f"{period}-01" and d <= f"{period}-{cut:02d}":
            series.append((d, float(r.get("revenue") or 0)))
    merged: dict[str, float] = {}
    for d, v in series:
        merged[d] = merged.get(d, 0.0) + v
    series = sorted(merged.items())[-30:]

    def delta(a, b):
        return (a / b - 1) * 100 if b else 0.0

    return {
        "period": period,
        "prev": prev,
        "cut": cut,
        "pcut": pcut,
        "cur": cur,
        "base": base,
        "d_rev": delta(cur["revenue"], base["revenue"]),
        "d_ses": delta(cur["sessions"], base["sessions"]),
        "d_conv": cur["conv"] - base["conv"],
        "d_print": delta(cur["prints"], base["prints"]),
        "outlets": outlets,
        "zero": zero,
        "noarea": noarea,
        "hiconv": hiconv,
        "mix": mix,
        "series": series,
    }


def _severity(x: dict) -> int:
    s = 0
    if x["revenue"] == 0 and x["sessions"] >= 20:
        s += 3
    if not x["area"]:
        s += 2
    if x["conv"] > 100:
        s += 2
    return s


# ── render ────────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, sub: str, d: float, unit: str) -> str:
    col = C_MINT if d >= 0 else C_RED
    arrow = "&#9650;" if d >= 0 else "&#9660;"
    return (
        '<div class="ct-kpi"><div class="ct-kpi-top"><span class="ct-lab">%s</span>'
        '<span class="ct-chip" style="color:%s;background:%s18">%s %s%s</span></div>'
        '<div class="ct-val">%s</div><div class="ct-sub">%s</div></div>'
        % (label, col, col, arrow, idn(abs(d)), unit, value, sub)
    )


def _row(x: dict) -> str:
    note, cls = "", ""
    if x["revenue"] == 0 and x["sessions"] >= 20:
        cls, note = "zero", "omzet 0"
    elif not x["area"]:
        cls, note = "warn", "area kosong"
    elif x["conv"] > 100:
        cls, note = "warn", "konv &gt; 100%"
    dd = x["revenue"] - x["prev_rev"]
    if x["prev_rev"] == 0 and x["revenue"] == 0:
        dtxt, dcls = "&mdash;", "ct-mut"
    elif x["prev_rev"] == 0:
        dtxt, dcls = "baru", "ct-up"
    elif abs(dd) < 500000:
        dtxt, dcls = "&plusmn;0", "ct-mut"
    else:
        dtxt = ("+" if dd >= 0 else "&#8722;") + rp(abs(dd)).replace("Rp ", "")
        dcls = "ct-up" if dd >= 0 else "ct-down"
    conv = pct(x["conv"]) if x["conv"] <= 100 else '<span class="ct-bad">' + pct(x["conv"]) + "</span>"
    note_html = ' <span class="ct-note">' + note + "</span>" if note else ""
    return (
        '<tr class="%s"><td class="ct-on">%s%s</td><td class="ct-mut">%s</td>'
        '<td class="ct-r num">%s</td><td class="ct-r num %s">%s</td>'
        '<td class="ct-r num">%s</td><td class="ct-r num">%s</td></tr>'
        % (cls, x["name"], note_html, x["area"] or "&mdash;", rp(x["revenue"]), dcls, dtxt,
           num(x["sessions"]), conv)
    )


def build_html(m: dict) -> str:
    cur, base = m["cur"], m["base"]
    cmp_label = "1–%d %s" % (m["pcut"], _month_label(m["prev"])[:3])
    zero, noarea, hiconv = m["zero"], m["noarea"], m["hiconv"]
    zero_sessions = sum(x["sessions"] for x in zero)
    zero_prints = sum(x["prints"] for x in zero)
    noarea_rev = sum(x["revenue"] for x in noarea)
    total = cur["revenue"] or 1

    kpis = "".join([
        _kpi("Omzet MTD", rp(cur["revenue"]), cmp_label + " " + rp(base["revenue"]), m["d_rev"], "%"),
        _kpi("Sesi foto", num(cur["sessions"]), cmp_label + " " + num(base["sessions"]), m["d_ses"], "%"),
        _kpi("Konversi", pct(cur["conv"]), cmp_label + " " + pct(base["conv"]), m["d_conv"], " pt"),
        _kpi("Cetak", num(cur["prints"]), "unlock " + num(cur["unlocks"]), m["d_print"], "%"),
    ])

    mix_html = "".join(
        '<div class="ct-mix"><span class="ct-mix-name">%s</span>'
        '<span class="ct-track"><span class="ct-fill" style="width:%.1f%%"></span></span>' 
        '<span class="ct-mix-val">%s</span></div>' % (k, v / total * 100, rp(v))
        for k, v in m["mix"]
    )

    ranked = sorted(m["outlets"], key=lambda x: (-_severity(x), -x["revenue"]))
    rows = "".join(_row(x) for x in ranked[:14])

    series = m["series"]
    peak = max(series, key=lambda p: p[1]) if series else ("-", 0)
    bars = "".join(
        '<div class="ct-bar%s" style="height:%.1f%%"></div>'
        % (" last" if i == len(series) - 1 else "", max(4.0, v / (peak[1] or 1) * 100))
        for i, (_, v) in enumerate(series)
    )

    as_of = tgl(series[-1][0]) if series else "-"
    period_label = _month_label(m["period"])

    return """
<div class="ct-wrap">
  <div class="ct-head">
    <div class="ct-brand">difotoin.id <span>&mdash; Control Tower</span></div>
    <div class="ct-pill">1&ndash;%(cut)d %(period_label)s</div>
    <div class="ct-live"><span class="ct-dot"></span> data %(as_of)s &middot; dibanding 1&ndash;%(pcut)d %(prev_label)s</div>
  </div>

  <div class="ct-sec">
    <div class="ct-h"><b>Ringkasan bulan berjalan</b><i>apple to apple &mdash; periode sama, bukan bulan penuh</i></div>
    <div class="ct-grid4">%(kpis)s</div>
  </div>

  <div class="ct-sec ct-cols">
    <div class="ct-card">
      <div class="ct-h"><b>Perlu keputusan</b><i>%(n_findings)d temuan yang menahan omzet</i></div>
      <div class="ct-issue"><div class="ct-sev" style="background:%(red)s"></div>
        <div><p class="ct-t">%(nz)d outlet ada sesi tapi omzet Rp 0</p>
        <p class="ct-d">%(zs)s sesi &middot; %(zp)s cetak &middot; mayoritas booth event, cek penagihan</p></div>
        <div class="ct-n" style="color:%(red)s">%(nz)d</div></div>
      <div class="ct-issue"><div class="ct-sev" style="background:%(amber)s"></div>
        <div><p class="ct-t">%(na)d outlet tanpa area</p>
        <p class="ct-d">%(nar)s (%(nas)s dari total) tidak masuk peta kota</p></div>
        <div class="ct-n" style="color:%(amber)s">%(na)d</div></div>
      <div class="ct-issue"><div class="ct-sev" style="background:%(amber)s"></div>
        <div><p class="ct-t">%(nh)d outlet konversi di atas 100%%</p>
        <p class="ct-d">unlock lebih banyak dari sesi &mdash; mapping mesin/outlet perlu dicek</p></div>
        <div class="ct-n" style="color:%(amber)s">%(nh)d</div></div>
      <div class="ct-foot"><span>ambang: omzet 0 &amp; &ge; 20 sesi &middot; konversi &gt; 100%%</span>
        <span>detail &rarr; Ranking &amp; Problem Booth</span></div>
    </div>

    <div class="ct-card">
      <div class="ct-h"><b>Bauran area</b><i>omzet MTD</i></div>
      %(mix)s
      <div class="ct-foot"><span>%(nout)d outlet aktif</span><span>%(total)s</span></div>
    </div>
  </div>

  <div class="ct-sec ct-card">
    <div class="ct-h"><b>Outlet</b><i>masalah di atas, lalu kontributor terbesar</i></div>
    <div style="overflow-x:auto">
    <table class="ct-table">
      <thead><tr><th>Outlet</th><th>Area</th><th class="r">Omzet MTD</th><th class="r">&Delta; vs periode sama</th><th class="r">Sesi</th><th class="r">Konv.</th></tr></thead>
      <tbody>%(rows)s</tbody>
    </table>
    </div>
    <div class="ct-foot"><span>menampilkan %(shown)d dari %(nout)d outlet</span><span>semua outlet &rarr; Ranking Outlet</span></div>
  </div>

  <div class="ct-sec ct-card">
    <div class="ct-h"><b>Omzet harian</b><i>%(ndays)d hari terakhir &middot; puncak %(peakd)s %(peakv)s</i></div>
    <div class="ct-strip">%(bars)s</div>
    <div class="ct-foot"><span>%(first)s</span><span>%(last)s</span></div>
  </div>
</div>
""" % {
        "cut": m["cut"], "pcut": m["pcut"], "period_label": period_label,
        "prev_label": _month_label(m["prev"]), "as_of": as_of,
        "kpis": kpis, "n_findings": sum(1 for n in (len(zero), len(noarea), len(hiconv)) if n),
        "nz": len(zero), "zs": num(zero_sessions), "zp": num(zero_prints),
        "na": len(noarea), "nar": rp(noarea_rev), "nas": pct(noarea_rev / total * 100),
        "nh": len(hiconv), "mix": mix_html, "nout": len(m["outlets"]), "total": rp(cur["revenue"]),
        "rows": rows or '<tr><td colspan="6" class="ct-empty">Belum ada transaksi di periode ini.</td></tr>',
        "shown": min(14, len(ranked)), "ndays": len(series),
        "peakd": tgl(peak[0]), "peakv": rp(peak[1]), "bars": bars,
        "first": tgl(series[0][0]) if series else "-", "last": as_of,
        "red": C_RED, "amber": C_AMBER,
    }


# ── page ──────────────────────────────────────────────────────────────────

def create_page(container, period: str | None = None) -> None:
    """Render Control Tower ke dalam container NiceGUI."""
    ui.add_head_html(CT_CSS, shared=True)
    daily = _daily()
    periods = _periods(daily)
    if not periods:
        with container:
            ui.label("Data harian belum tersedia (daily_summary.json kosong).").classes("text-gray-400 p-4")
        return

    selected = period if period in periods else periods[-1]
    options = {p: _month_label(p) for p in reversed(periods[-12:])}

    holder = {}

    def render(p: str):
        holder["body"].clear()
        with holder["body"]:
            ui.html(build_html(compute(p)), sanitize=False).classes("w-full")

    with container:
        with ui.row().classes("w-full items-center gap-3 flex-wrap pb-1"):
            ui.select(options, value=selected, label="Periode",
                      on_change=lambda e: render(e.value)).props("dense outlined dark").classes("w-44")
            ui.label("Angka dihitung ulang tiap kali halaman dibuka.").classes("text-xs text-gray-500")
        holder["body"] = ui.column().classes("w-full")
        render(selected)
