"""Transaksi Harian — tampilan harian yang terukur.

Satu tanggal dipilih, lalu semua angka dibandingkan ke basis yang adil:
- kemarin (D-1)
- hari yang sama minggu lalu (D-7)
- rata-rata 7 hari sebelumnya per outlet (untuk tabel & panel "perlu dicek")
- MTD vs MTD (bulan berjalan 1..tgl vs bulan lalu 1..tgl yang sama)

Semua angka dihitung dari `daily_summary.json` (per outlet per hari);
area diambil dari `dashboard_summary.json`. Tidak ada angka hardcode.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from nicegui import ui
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DAILY_PATH = ROOT / "streamlit_template" / "data" / "api_cache" / "daily_summary.json"
SUMMARY_PATH = ROOT / "streamlit_template" / "data" / "api_cache" / "dashboard_summary.json"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

C_BG = "#0c0c12"
C_PANEL = "#15151e"
C_LINE = "#24242f"
C_TXT = "#eceef4"
C_MUT = "#8b90a3"
C_MINT = "#3ddc97"
C_AMBER = "#f5b942"
C_RED = "#f2685f"
C_BLUE = "#5b9cff"

DT_CSS = """<style>
  .dt-wrap { color: @TXT@; font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 13px; }
  .dt-wrap .num { font-variant-numeric: tabular-nums; }
  .dt-grid6 { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 11px; }
  .dt-grid2 { display: grid; grid-template-columns: 1.55fr 1fr; gap: 12px; align-items: start; margin-top: 14px; }
  .dt-kpi { background: @PANEL@; border: 1px solid @LINE@; border-radius: 11px; padding: 12px 13px 10px; }
  .dt-lab { color: @MUT@; font-size: 10.5px; letter-spacing: .8px; text-transform: uppercase; }
  .dt-val { font-size: 22px; font-weight: 650; margin: 6px 0 5px; letter-spacing: -.4px; }
  .dt-sub { color: @MUT@; font-size: 10.5px; }
  .dt-deltas { display: flex; flex-direction: column; gap: 1px; font-size: 10.5px; color: @MUT@; }
  .dt-deltas b { font-weight: 650; }
  .dt-chip { display: inline-block; font-size: 10.5px; font-weight: 600; padding: 2px 6px; border-radius: 5px; white-space: nowrap; }
  .dt-up { color: @MINT@; background: @MINT@1a; }
  .dt-down { color: @RED@; background: @RED@1a; }
  .dt-flat { color: @MUT@; background: #ffffff0d; }
  .dt-warn { color: @AMBER@; background: @AMBER@1a; }
  .dt-card { background: @PANEL@; border: 1px solid @LINE@; border-radius: 11px; padding: 14px; }
  .dt-h { display: flex; align-items: baseline; gap: 9px; margin-bottom: 10px; flex-wrap: wrap; }
  .dt-h b { font-size: 13px; font-weight: 650; }
  .dt-h i { font-style: normal; color: @MUT@; font-size: 11px; }
  .dt-bars { display: flex; align-items: flex-end; gap: 3px; height: 132px; margin-top: 8px;
    border-bottom: 1px solid @LINE@; position: relative; }
  .dt-bar { flex: 1; background: #2b3654; border-radius: 2px 2px 0 0; min-height: 2px; }
  .dt-bar.hi { background: @MINT@; }
  .dt-bar.avg-under { background: #22304d; }
  .dt-avg { position: absolute; left: 0; right: 0; border-top: 1px dashed @MUT@66; }
  .dt-avg span { position: absolute; right: 0; top: -14px; font-size: 9.5px; color: @MUT@; }
  .dt-x { display: flex; justify-content: space-between; color: @MUT@; font-size: 10px; margin-top: 6px; }
  .dt-rows { display: flex; flex-direction: column; }
  .dt-row { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; padding: 7px 0;
    border-bottom: 1px solid #1b1b25; align-items: center; }
  .dt-row:last-child { border-bottom: 0; }
  .dt-row .k { color: @MUT@; font-size: 11.5px; }
  .dt-row .v { font-weight: 600; font-variant-numeric: tabular-nums; }
  .dt-table { width: 100%; border-collapse: collapse; }
  .dt-table thead th { position: sticky; top: 0; background: @PANEL@; z-index: 1; }
  .dt-table th { text-align: left; font-size: 10px; letter-spacing: .7px; text-transform: uppercase;
    color: @MUT@; font-weight: 600; padding: 0 10px 7px; border-bottom: 1px solid @LINE@; white-space: nowrap; }
  .dt-table th.r { text-align: right; }
  .dt-table td { padding: 8px 10px; border-bottom: 1px solid #1b1b25; font-size: 12px; white-space: nowrap; }
  .dt-table td.r { text-align: right; font-variant-numeric: tabular-nums; }
  .dt-table tr.zero td:first-child { box-shadow: inset 3px 0 0 @RED@; }
  .dt-table tr.warn td:first-child { box-shadow: inset 3px 0 0 @AMBER@; }
  .dt-table tfoot td { border-top: 1px solid @LINE@; font-weight: 650; color: @TXT@; padding-top: 9px; }
  .dt-on { font-weight: 550; }
  .dt-mut { color: @MUT@; }
  .dt-foot { display: flex; justify-content: space-between; color: @MUT@; font-size: 10.5px; padding-top: 9px; gap: 10px; flex-wrap: wrap; }
  .dt-issue { display: grid; grid-template-columns: 3px 1fr auto; gap: 11px; align-items: center; padding: 9px 0; }
  .dt-issue + .dt-issue { border-top: 1px solid @LINE@; }
  .dt-sev { width: 3px; height: 30px; border-radius: 2px; }
  .dt-issue .t { font-weight: 600; font-size: 12.5px; }
  .dt-issue .d { color: @MUT@; font-size: 11px; margin-top: 2px; }
  .dt-issue .n { font-size: 15px; font-weight: 650; font-variant-numeric: tabular-nums; }
  .dt-empty { color: @MUT@; padding: 16px 0; }
  .dt-note { color: @MUT@; font-size: 10.5px; margin-top: 10px; }
  @media (max-width: 1200px) { .dt-grid6 { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
  @media (max-width: 900px) {
    .dt-grid6 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .dt-grid2 { grid-template-columns: 1fr; }
    .dt-val { font-size: 19px; }
  }
</style>"""
for _tok, _val in (
    ("@TXT@", C_TXT), ("@PANEL@", C_PANEL), ("@LINE@", C_LINE), ("@MUT@", C_MUT),
    ("@MINT@", C_MINT), ("@AMBER@", C_AMBER), ("@RED@", C_RED), ("@BLUE@", C_BLUE),
):
    DT_CSS = DT_CSS.replace(_tok, _val)

_cache: dict = {"df": None, "mtime": None, "area": None, "area_mtime": None}


# ── data ──────────────────────────────────────────────────────────────────

def _area_map() -> dict:
    """outlet_name -> area, dari dashboard_summary.json."""
    try:
        mtime = SUMMARY_PATH.stat().st_mtime
    except OSError:
        return {}
    if _cache["area"] is not None and _cache["area_mtime"] == mtime:
        return _cache["area"]
    mapping: dict = {}
    try:
        rows = json.loads(SUMMARY_PATH.read_text())
        for r in rows if isinstance(rows, list) else []:
            name = str(r.get("outlet_name", "")).strip()
            area = str(r.get("area") or "").strip()
            if name and area and name not in mapping:
                mapping[name] = area
    except Exception:
        mapping = {}
    _cache["area"] = mapping
    _cache["area_mtime"] = mtime
    return mapping


def _load_data(force: bool = False) -> pd.DataFrame:
    try:
        if not DAILY_PATH.exists():
            _cache["df"] = pd.DataFrame()
            _cache["mtime"] = None
            return _cache["df"]
        mtime = DAILY_PATH.stat().st_mtime
        if _cache["df"] is not None and _cache["mtime"] == mtime and not force:
            return _cache["df"]

        data = json.loads(DAILY_PATH.read_text())
        df = pd.DataFrame(data)
        if "date" not in df.columns:
            _cache["df"] = pd.DataFrame()
            return _cache["df"]
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        df = df[df["date"].notna()].copy()
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=430)
        df = df[df["date"] >= cutoff].copy()
        for col in ("sessions", "unlocks", "unlocks_paid", "prints"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        for col in ("revenue", "conversion_rate", "print_rate", "avg_revenue_per_session"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        if "outlet_name" in df.columns:
            df["outlet_name"] = df["outlet_name"].astype(str).str.strip()
        _cache["df"] = df
        _cache["mtime"] = mtime
        return df
    except Exception:
        _cache["df"] = pd.DataFrame()
        return _cache["df"]


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
        return "Rp " + num(round(val / 1_000.0)) + " rb".replace("rb", "rb")
    return "Rp " + format(int(round(val)), ",").replace(",", ".")


def num(v) -> str:
    try:
        return format(int(round(float(v))), ",").replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def pct(v) -> str:
    try:
        return ("%.1f" % float(v)).replace(".", ",") + "%"
    except (TypeError, ValueError):
        return "0,0%"


def day_label(ts: pd.Timestamp) -> str:
    return DAY_NAMES[ts.weekday()] + ", " + ts.strftime("%d %b %Y")


def delta_chip(cur, base) -> tuple[str, str]:
    """(css_class, text) untuk delta persen terhadap base. None kalau base tidak ada."""
    try:
        cur_f, base_f = float(cur), float(base)
    except (TypeError, ValueError):
        return ("dt-flat", "&mdash;")
    if base_f <= 0:
        return ("dt-flat", "&mdash;")
    d = (cur_f - base_f) / base_f * 100.0
    cls = "dt-up" if d >= 0.5 else ("dt-down" if d <= -0.5 else "dt-flat")
    arrow = "&uarr;" if d >= 0.5 else ("&darr;" if d <= -0.5 else "&rarr;")
    txt = ("%s %.1f%%" % (arrow, abs(d))).replace(".", ",")
    return (cls, txt)


# ── compute ───────────────────────────────────────────────────────────────

def _sum(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"revenue": 0.0, "sessions": 0, "prints": 0, "unlocks_paid": 0, "unlocks": 0,
                "outlets": 0, "arps": 0.0, "conv": 0.0, "paid_share": 0.0}
    rev = float(df["revenue"].sum())
    sess = int(df["sessions"].sum())
    prints = int(df["prints"].sum())
    paid = int(df["unlocks_paid"].sum()) if "unlocks_paid" in df.columns else 0
    unlocks = int(df["unlocks"].sum()) if "unlocks" in df.columns else 0
    active = int((df["sessions"] > 0).sum())
    return {
        "revenue": rev,
        "sessions": sess,
        "prints": prints,
        "unlocks": unlocks,
        "unlocks_paid": paid,
        "outlets": active,
        "arps": (rev / sess) if sess else 0.0,
        # konversi = unlock per sesi (definisi yang sama dengan field conversion_rate)
        "conv": (unlocks / sess * 100.0) if sess else 0.0,
        "paid_share": (paid / unlocks * 100.0) if unlocks else 0.0,
    }


def compute(sel: pd.Timestamp, sort_key: str = "omzet", query: str = "") -> dict:
    df = _load_data()
    if df.empty:
        return {"empty": True}

    area_map = _area_map()
    today = pd.Timestamp.now().normalize()
    sel = pd.Timestamp(sel).normalize()

    day = df[df["date"] == sel]
    prev1 = df[df["date"] == sel - pd.Timedelta(days=1)]
    prev7 = df[df["date"] == sel - pd.Timedelta(days=7)]

    cur = _sum(day)
    d1 = _sum(prev1)
    d7 = _sum(prev7)

    # jendela 7 hari sebelum tanggal terpilih
    win_start = sel - pd.Timedelta(days=7)
    win = df[(df["date"] >= win_start) & (df["date"] < sel)]
    win_avg = {}
    if not win.empty:
        agg = win.groupby("outlet_name").agg(rev=("revenue", "mean"), days=("date", "nunique"))
        win_avg = {k: (float(r["rev"]), int(r["days"])) for k, r in agg.iterrows()}

    # 30 hari untuk chart
    chart_start = sel - pd.Timedelta(days=29)
    chart_df = df[(df["date"] >= chart_start) & (df["date"] <= sel)]
    series = []
    if not chart_df.empty:
        s = chart_df.groupby("date")["revenue"].sum().sort_index()
        series = [(d, float(v)) for d, v in s.items()]

    # MTD vs MTD (bulan berjalan 1..tgl vs bulan lalu 1..tgl yang sama)
    cur_start = sel.replace(day=1)
    prev_month_end = cur_start - pd.Timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    prev_day = min(sel.day, prev_month_end.day)
    prev_cut = prev_month_start + pd.Timedelta(days=prev_day - 1)
    mtd_cur = _sum(df[(df["date"] >= cur_start) & (df["date"] <= sel)])
    mtd_prev = _sum(df[(df["date"] >= prev_month_start) & (df["date"] <= prev_cut)])

    # per outlet
    rows = []
    if not day.empty:
        for _, r in day.iterrows():
            name = str(r.get("outlet_name", "")).strip()
            rev = float(r.get("revenue", 0) or 0)
            sess = int(r.get("sessions", 0) or 0)
            prints = int(r.get("prints", 0) or 0)
            paid = int(r.get("unlocks_paid", 0) or 0)
            unlocks = int(r.get("unlocks", 0) or 0)
            base, ndays = win_avg.get(name, (None, 0))
            dcls, dtxt = delta_chip(rev, base) if base else ("dt-flat", "&mdash;")
            dval = None
            if base and base > 0:
                dval = (rev - base) / base * 100.0
            status = ""
            row_cls = ""
            if rev <= 0 and base and base > 0:
                status = ('<span class="dt-chip dt-down">0 transaksi</span>')
                row_cls = "zero"
            elif dval is not None and dval <= -40:
                status = ('<span class="dt-chip dt-warn">turun tajam</span>')
                row_cls = "warn"
            elif dval is not None and dval >= 40:
                status = ('<span class="dt-chip dt-up">naik</span>')
            elif base is None or ndays < 3:
                status = ('<span class="dt-chip dt-flat">basis tipis</span>')
            rows.append({
                "name": name,
                "area": area_map.get(name, "") or "",
                "revenue": rev,
                "sessions": sess,
                "prints": prints,
                "paid": paid,
                "unlocks": unlocks,
                "arps": (rev / sess) if sess else 0.0,
                "conv": (unlocks / sess * 100.0) if sess else 0.0,
                "base": base,
                "dval": dval,
                "dcls": dcls,
                "dtxt": dtxt,
                "status": status,
                "row_cls": row_cls,
            })

    if query:
        q = query.lower().strip()
        rows = [x for x in rows if q in x["name"].lower() or q in x["area"].lower()]

    if sort_key == "turun":
        rows.sort(key=lambda x: (x["dval"] if x["dval"] is not None else 999))
    elif sort_key == "sesi":
        rows.sort(key=lambda x: -x["sessions"])
    elif sort_key == "konversi":
        rows.sort(key=lambda x: x["conv"])
    else:
        rows.sort(key=lambda x: -x["revenue"])

    # panel "perlu dicek" — saat hari masih berjalan, aturan berbasis delta dilewati
    partial = (sel == today)
    wib_hour = (datetime.utcnow().hour + 7) % 24
    issues = []
    for x in rows:
        base = x["base"]
        zero_day = x["revenue"] <= 0 and bool(base) and base > 0
        if partial and not (zero_day and wib_hour >= 12):
            # hari berjalan: angka belum penuh, jadi hanya outlet yang benar-benar
            # nol sesi setelah tengah hari yang ditandai
            continue
        if zero_day:
            issues.append({"tone": "red", "name": x["name"], "area": x["area"],
                           "why": "tidak ada transaksi, biasanya " + rp_short(base) + "/hari",
                           "impact": (base or 0) - x["revenue"]})
        elif x["dval"] is not None and x["dval"] <= -40 and (base or 0) >= 200_000:
            issues.append({"tone": "amber", "name": x["name"], "area": x["area"],
                           "why": "omzet turun tajam vs rata-rata 7 hari (" + rp_short(base) + ")",
                           "impact": (base or 0) - x["revenue"]})
        elif x["sessions"] >= 30 and x["conv"] < 5:
            issues.append({"tone": "amber", "name": x["name"], "area": x["area"],
                           "why": "konversi rendah " + pct(x["conv"]) + " dari " + num(x["sessions"]) + " sesi",
                           "impact": 0})
    issues.sort(key=lambda i: -i["impact"])

    # posisi hari terpilih dalam 30 hari
    rank = None
    if series:
        vals = sorted([v for _, v in series], reverse=True)
        rank = vals.index(cur["revenue"]) + 1 if cur["revenue"] in vals else None
        avg30 = sum(v for _, v in series) / len(series)
    else:
        avg30 = 0.0

    return {
        "empty": False,
        "sel": sel,
        "is_today": sel == today,
        "partial": partial,
        "cur": cur,
        "d1": d1,
        "d7": d7,
        "mtd_cur": mtd_cur,
        "mtd_prev": mtd_prev,
        "mtd_label": "%d\u2013%d %s" % (1, sel.day, MONTHS[sel.month - 1]),
        "mtd_prev_label": "%d\u2013%d %s" % (1, prev_day, MONTHS[prev_month_start.month - 1]),
        "series": series,
        "avg30": avg30,
        "rank30": rank,
        "rows": rows,
        "issues": issues[:8],
        "n_issues": len(issues),
        "area_count": len({x["area"] for x in rows if x["area"]}),
        "no_area": sum(1 for x in rows if not x["area"]),
    }


# ── html ──────────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, chip_d1: tuple, chip_d7: tuple, title: str = "") -> str:
    def chip(c):
        cls, txt = c
        tone = C_MINT if cls == "dt-up" else (C_RED if cls == "dt-down" else C_MUT)
        return '<b style="color:' + tone + '">' + txt + "</b>"
    tip = (' title="' + title + '"') if title else ""
    return (
        '<div class="dt-kpi">'
        '<div class="dt-lab">' + label + "</div>"
        '<div class="dt-val num"' + tip + ">" + value + "</div>"
        '<div class="dt-deltas"><span>kemarin ' + chip(chip_d1) + "</span>"
        "<span>7hr " + chip(chip_d7) + "</span></div>"
        "</div>"
    )


def _delta_sub(cur, base) -> str:
    if base in (None, 0):
        return "&mdash;"
    d = (float(cur) - float(base)) / float(base) * 100.0
    cls = "dt-up" if d >= 0.5 else ("dt-down" if d <= -0.5 else "dt-mut")
    sign = "+" if d >= 0 else ""
    return '<span class="' + cls + '">' + (sign + "%.1f" % d).replace(".", ",") + "%</span>"


def build_html(m: dict) -> str:
    if m.get("empty"):
        return '<div class="dt-empty">Data harian belum tersedia.</div>'

    cur, d1, d7 = m["cur"], m["d1"], m["d7"]

    def d7chip(cur_v, base_v):
        cls_txt = delta_chip(cur_v, base_v)
        return cls_txt

    kpis = "".join([
        _kpi("Omzet", rp_short(cur["revenue"]), delta_chip(cur["revenue"], d1["revenue"]),
             d7chip(cur["revenue"], d7["revenue"]), "tepat: " + rp(cur["revenue"])),
        _kpi("Sesi foto", num(cur["sessions"]), delta_chip(cur["sessions"], d1["sessions"]),
             d7chip(cur["sessions"], d7["sessions"]), "tepat: " + num(cur["sessions"])),
        _kpi("Cetak", num(cur["prints"]), delta_chip(cur["prints"], d1["prints"]),
             d7chip(cur["prints"], d7["prints"])),
        _kpi("Unlock bayar", num(cur["unlocks_paid"]), delta_chip(cur["unlocks_paid"], d1["unlocks_paid"]),
             d7chip(cur["unlocks_paid"], d7["unlocks_paid"])),
        _kpi("ARPS", rp(cur["arps"]), delta_chip(cur["arps"], d1["arps"]),
             d7chip(cur["arps"], d7["arps"]), "omzet per sesi"),
        _kpi("Konversi", pct(cur["conv"]), delta_chip(cur["conv"], d1["conv"]),
             d7chip(cur["conv"], d7["conv"]), "unlock per sesi"),
    ])

    # chart 30 hari
    series = m["series"]
    bars = ""
    if series:
        peak = max(v for _, v in series) or 1.0
        for d, v in series:
            h = max(2, int(round(v / peak * 100)))
            cls = "dt-bar hi" if d == m["sel"] else "dt-bar"
            bars += '<div class="%s" style="height:%d%%" title="%s &middot; %s"></div>' % (
                cls, h, d.strftime("%d %b"), rp(v))
        avg_pct = max(0, min(100, int(round((m["avg30"] / peak) * 100)))) if peak else 0
        avg_line = '<div class="dt-avg" style="bottom:%d%%"><span>rata-rata %s</span></div>' % (
            avg_pct, rp_short(m["avg30"]))
    else:
        avg_line = ""
        bars = '<div class="dt-empty">Belum ada data 30 hari terakhir.</div>'
    x_first = series[0][0].strftime("%d %b") if series else "-"
    x_last = series[-1][0].strftime("%d %b") if series else "-"

    # MTD vs MTD
    mc, mp = m["mtd_cur"], m["mtd_prev"]
    mtd_rows = ""
    for label, a, b, fmt in (
        ("Omzet", mc["revenue"], mp["revenue"], rp_short),
        ("Sesi", mc["sessions"], mp["sessions"], num),
        ("ARPS", mc["arps"], mp["arps"], rp),
        ("Cetak", mc["prints"], mp["prints"], num),
    ):
        mtd_rows += (
            '<div class="dt-row"><span class="k">' + label + '</span>'
            '<span class="v num">' + fmt(a) + "</span>"
            '<span class="dt-chip ' + delta_chip(a, b)[0] + '">' + delta_chip(a, b)[1] + "</span></div>"
        )

    # tabel
    rows_html = ""
    tot_rev = tot_sess = tot_print = 0
    for x in m["rows"]:
        tot_rev += x["revenue"]
        tot_sess += x["sessions"]
        tot_print += x["prints"]
        rows_html += (
            '<tr class="' + x["row_cls"] + '">'
            '<td class="dt-on">' + x["name"] + "</td>"
            '<td class="dt-mut">' + (x["area"] or "&mdash;") + "</td>"
            '<td class="r">' + rp(x["revenue"]) + "</td>"
            '<td class="r"><span class="' + x["dcls"] + '" style="font-weight:600">' + x["dtxt"] + "</span></td>"
            '<td class="r">' + num(x["sessions"]) + "</td>"
            '<td class="r">' + num(x["prints"]) + "</td>"
            '<td class="r">' + rp(x["arps"]) + "</td>"
            '<td class="r">' + pct(x["conv"]) + "</td>"
            "<td>" + x["status"] + "</td>"
            "</tr>"
        )
    if not rows_html:
        rows_html = '<tr><td colspan="9" class="dt-empty">Tidak ada outlet yang cocok.</td></tr>'
    total_row = (
        "<tfoot><tr>"
        "<td>Total &middot; " + num(len(m["rows"])) + " outlet</td><td></td>"
        '<td class="r">' + rp(tot_rev) + "</td><td></td>"
        '<td class="r">' + num(tot_sess) + "</td>"
        '<td class="r">' + num(tot_print) + "</td>"
        '<td class="r">' + rp((tot_rev / tot_sess) if tot_sess else 0) + "</td>"
        '<td class="r">' + pct((cur["unlocks"] / tot_sess * 100) if tot_sess else 0) + "</td>"
        "<td></td></tr></tfoot>"
    )

    # perlu dicek
    issues_html = ""
    for i in m["issues"]:
        color = C_RED if i["tone"] == "red" else C_AMBER
        issues_html += (
            '<div class="dt-issue">'
            '<span class="dt-sev" style="background:' + color + '"></span>'
            "<div><p class='t'>" + i["name"] + '</p><p class="d">' + (i["area"] or "tanpa area") + " &middot; " + i["why"] + "</p></div>"
            '<span class="n num">' + (rp_short(i["impact"]) if i["impact"] else "&mdash;") + "</span>"
            "</div>"
        )
    if not issues_html:
        issues_html = '<div class="dt-empty">Tidak ada outlet yang mencolok hari ini.</div>'

    pos_line = []
    if m.get("rank30") and not m.get("partial"):
        pos_line.append("Omzet hari ini peringkat <b>#%d</b> dari %d hari terakhir" % (m["rank30"], len(series)))
    pos_line.append("rata-rata 30 hari <b>%s</b>" % rp_short(m["avg30"]))

    note_today = (
        '<div class="dt-note">Hari berjalan &mdash; angka masih parsial sampai 23.59 WIB; '
        'delta dan panel &ldquo;perlu dicek&rdquo; sengaja tidak dipakai untuk menilai penurunan.</div>'
        if m.get("partial") else ""
    )

    return (
        '<div class="dt-wrap">'
        '<div class="dt-grid6">' + kpis + "</div>"
        + note_today +
        '<div class="dt-grid2">'
        # kiri: chart
        '<div class="dt-card">'
        '<div class="dt-h"><b>Omzet harian</b><i>30 hari sampai tanggal terpilih &middot; ' + " &middot; ".join(pos_line) + "</i></div>"
        '<div class="dt-bars">' + avg_line + bars + "</div>"
        '<div class="dt-x"><span>' + x_first + "</span><span>" + x_last + "</span></div>"
        "</div>"
        # kanan: MTD vs MTD
        '<div class="dt-card">'
        '<div class="dt-h"><b>MTD vs MTD</b><i>' + m["mtd_label"] + " vs " + m["mtd_prev_label"] + " &middot; apple to apple</i></div>"
        '<div class="dt-rows">' + mtd_rows + "</div>"
        '<div class="dt-note">Dibanding bulan lalu pada jumlah hari yang sama, bukan bulan penuh.</div>'
        "</div>"
        "</div>"
        # panel perlu dicek
        '<div class="dt-card" style="margin-top:14px">'
        '<div class="dt-h"><b>Perlu dicek</b><i>' + num(len(m["issues"])) + " dari " + num(m["n_issues"]) +
        " temuan &middot; diurut dari dampak omzet terbesar</i></div>"
        + issues_html +
        "</div>"
        # tabel
        '<div class="dt-card" style="margin-top:14px">'
        '<div class="dt-h"><b>Rincian per outlet</b><i>&Delta; = omzet vs rata-rata 7 hari sebelumnya</i></div>'
        '<div style="overflow:auto;max-height:560px"><table class="dt-table">'
        "<thead><tr><th>Outlet</th><th>Area</th><th class='r'>Omzet</th><th class='r'>&Delta; 7hr</th>"
        "<th class='r'>Sesi</th><th class='r'>Cetak</th><th class='r'>ARPS</th><th class='r'>Konv.</th><th>Status</th></tr></thead>"
        "<tbody>" + rows_html + "</tbody>" + total_row + "</table></div>"
        '<div class="dt-foot"><span>ARPS = omzet per sesi &middot; Konv. = unlock per sesi</span>'
        "<span>" + num(m["area_count"]) + " area &middot; " + num(m["no_area"]) + " outlet tanpa area</span></div>"
        "</div>"
        "</div>"
    )


# ── page ──────────────────────────────────────────────────────────────────

def create_page(container) -> None:
    ui.add_head_html(DT_CSS, shared=True)
    df = _load_data()
    if df.empty:
        with container:
            ui.label("Data transaksi harian belum tersedia.").classes("text-gray-400")
        return

    dates = sorted(df["date"].dropna().unique())
    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=60)
    recent = [d for d in dates if d >= cutoff] or [dates[-1]]
    date_options = {pd.Timestamp(d).strftime("%Y-%m-%d"): day_label(pd.Timestamp(d)) for d in reversed(recent)}
    selected = next(iter(date_options))

    holder: dict = {}

    def render():
        holder["body"].clear()
        m = compute(pd.Timestamp(holder["date"].value), holder["sort"].value or "omzet",
                    (holder["q"].value or "").strip())
        with holder["body"]:
            ui.html(build_html(m), sanitize=False).classes("w-full")

    with container:
        with ui.row().classes("w-full items-center gap-3 flex-wrap pb-2"):
            ui.label("\U0001f4c8").classes("text-2xl")
            ui.label("Transaksi Harian").classes("text-xl font-bold text-white")
            ui.label("dibanding basis yang adil, bukan sekadar kemarin").classes("text-xs text-gray-500")
            holder["date"] = ui.select(
                date_options, value=selected, label="Tanggal",
                on_change=lambda e: render(),
            ).props("dense outlined dark").classes("w-56")
            holder["sort"] = ui.select(
                {"omzet": "Omzet terbesar", "turun": "Penurunan terbesar", "sesi": "Sesi terbanyak", "konversi": "Konversi terendah"},
                value="omzet", label="Urutkan",
                on_change=lambda e: render(),
            ).props("dense outlined dark").classes("w-52")
            holder["q"] = ui.input("Cari outlet / area", on_change=lambda e: render()).props(
                "dense outlined dark clearable").classes("w-56")
            ui.label("Data: " + datetime.now().strftime("%d %b %Y %H:%M")).classes("text-xs text-gray-500 ml-auto")

        holder["body"] = ui.column().classes("w-full")
        render()
