"""🤝 Kemitraan v2 — ekonomi kemitraan untuk owner.

Menjawab 4 pertanyaan:
1. Bulan ini, dari omzet outlet kemitraan, berapa yang jadi hak mitra/broker
   dan berapa yang tinggal di Difotoin (sebelum & sesudah sewa)?
2. Modal yang sudah ditanam mitra, sudah kembali berapa persen?
3. Outlet mana yang paling jauh dari balik modal (risiko mitra mengeluh)?
4. Di outlet mana Difotoin bekerja paling mahal (bagian mitra besar)?

Sumber (semua sudah ada di server, tidak ada hitungan asumsi):
- `api_cache/rs_outlet.json`   → Rp aktual per outlet per bulan (mitra/broker/difotoin).
- `api_cache/outlets.json`     → kontrak hidup: partner_share, monthly_rent, initial_cost.
- `data/sharing_outlets/*.json`→ nama investor & jaminan minimum (pelengkap).

Catatan kejujuran angka:
- Payout mitra kumulatif dihitung sejak Jul 2025 karena di situ batas data
  transaksi yang tersedia; outlet yang buka sebelum itu progresnya understated.
- Halaman lama membaca data_processor (CSV berhenti Mar 2024) sehingga omzet
  selalu 0 dan BEP selalu "-". Halaman ini membaca cache API yang live.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from nicegui import ui
from plotly import graph_objects as go

from services import unit_mesin_store as ums

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "streamlit_template" / "data" / "api_cache"
SHARING = ROOT / "streamlit_template" / "data" / "sharing_outlets"
PARTNERSHIPS = ROOT / "streamlit_template" / "data" / "outlet_partnerships.json"

C_PANEL = "#1a1a24"
C_LINE = "#26262f"
C_TXT = "#eceef4"
C_MUT = "#8e93a6"
C_BLUE = "#5b8cff"
C_MINT = "#3ddc97"
C_AMBER = "#f5b83d"
C_RED = "#ff6b6b"
C_VIOLET = "#a78bfa"
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

_cache: dict = {}


# ── format ────────────────────────────────────────────────────────────────

def rp_short(v: float) -> str:
    v = float(v or 0)
    a = abs(v)
    if a >= 1e9:
        return "Rp " + f"{v / 1e9:.2f}".replace(".", ",") + " M"
    if a >= 1e6:
        return "Rp " + f"{v / 1e6:.1f}".replace(".", ",") + " jt"
    if a >= 1e3:
        return "Rp " + f"{v / 1e3:.0f}".replace(".", ",") + " rb"
    return "Rp " + f"{v:,.0f}".replace(",", ".")


def rp_full(v: float) -> str:
    return "Rp " + f"{float(v or 0):,.0f}".replace(",", ".")


def pct(v: float, dec: int = 1) -> str:
    return f"{float(v or 0):.{dec}f}".replace(".", ",")


def nfmt(v: float) -> str:
    return f"{float(v or 0):,.0f}".replace(",", ".")


def lbl_month(p: str) -> str:
    y, m = str(p).split("-")
    return BULAN[int(m) - 1] + " " + y[2:]


def _norm(s) -> str:
    s = str(s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _num(v, default=0.0) -> float:
    try:
        f = float(v)
        return f if np.isfinite(f) else default
    except (TypeError, ValueError):
        return default


# ── data ──────────────────────────────────────────────────────────────────

def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _sharing_latest() -> tuple[str | None, pd.DataFrame]:
    files = sorted(p for p in SHARING.glob("*.json") if re.match(r"^\d{4}-\d{2}$", p.stem))
    if not files:
        return None, pd.DataFrame()
    df = pd.DataFrame(_read_json(files[-1], []))
    return files[-1].stem, df


def _staleness_days(period: str | None) -> int | None:
    if not period:
        return None
    try:
        last = pd.Timestamp(period + "-01") + pd.offsets.MonthEnd(0)
    except Exception:
        return None
    return max(0, int((pd.Timestamp.now().normalize() - last).days))


def load_data() -> dict:
    """Muat semua sumber sekali; cache sampai file berubah."""
    paths = [CACHE / "rs_outlet.json", CACHE / "outlets.json", PARTNERSHIPS]
    stamp = tuple(p.stat().st_mtime if p.exists() else 0 for p in paths)
    per, sharing = _sharing_latest()
    stamp = stamp + (per,)
    if _cache.get("stamp") == stamp:
        return _cache["data"]

    rs = pd.DataFrame(_read_json(CACHE / "rs_outlet.json", []))
    if rs.empty:
        return {"rs": rs}
    rs["periode"] = rs["periode"].astype(str)
    for c in ("total_revenue", "partner_amount", "broker_amount", "difotoin_amount", "avg_partner_pct"):
        rs[c] = pd.to_numeric(rs.get(c), errors="coerce").fillna(0.0)
    rs["key"] = rs["outlet_name"].map(_norm)

    outlets = pd.DataFrame(_read_json(CACHE / "outlets.json", []))
    if not outlets.empty:
        outlets["key"] = outlets["name"].map(_norm)
        for c in ("partner_share", "monthly_rent", "initial_cost", "broker_share", "partner_minimal_share"):
            outlets[c] = pd.to_numeric(outlets.get(c), errors="coerce")
        outlets = outlets.drop_duplicates("key", keep="last")

    if not sharing.empty:
        sharing["key"] = sharing["outlet_name"].map(_norm)
        for c in ("partner_share", "monthly_rent", "minimum_payment", "harga_beli_kemitraan", "broker_share"):
            sharing[c] = pd.to_numeric(sharing.get(c), errors="coerce")
        sharing = sharing.drop_duplicates("key", keep="last")

    op = _read_json(PARTNERSHIPS, {})
    op_outlets = {_norm(k): v for k, v in (op.get("outlets") or {}).items()}

    # ── gabungkan kontrak: API outlet dulu, master sharing sebagai pelengkap
    term = pd.DataFrame({"key": rs["key"].unique()})
    term["outlet"] = term["key"].map(rs.drop_duplicates("key").set_index("key")["outlet_name"])
    if not outlets.empty:
        term = term.merge(
            outlets[["key", "partner_share", "monthly_rent", "initial_cost", "partner_minimal_share"]],
            on="key", how="left",
        )
    else:
        for c in ("partner_share", "monthly_rent", "initial_cost", "partner_minimal_share"):
            term[c] = np.nan

    if not sharing.empty:
        add = sharing[["key", "investor_name", "minimum_payment", "harga_beli_kemitraan"]].copy()
        term = term.merge(add, on="key", how="left")
        term["in_master"] = term["investor_name"].notna()
    else:
        term["investor_name"] = None
        term["minimum_payment"] = np.nan
        term["harga_beli_kemitraan"] = np.nan
        term["in_master"] = False

    term["investor"] = term.apply(
        lambda r: (str(r["investor_name"]).strip() if isinstance(r["investor_name"], str) else "")
        or str((op_outlets.get(r["key"]) or {}).get("investor_name") or "").strip(),
        axis=1,
    )
    bad = {"-", "nan", "none", ""}
    term["investor"] = term["investor"].apply(lambda s: "" if s.strip().lower() in bad else s.strip())
    term["initial_cost"] = term["initial_cost"].fillna(term["harga_beli_kemitraan"]).fillna(0.0)
    term["rent"] = term["monthly_rent"].fillna(0.0)
    term["contract_pct"] = term["partner_share"]

    data = {
        "rs": rs,
        "term": term,
        "outlets": outlets,
        "sharing": sharing,
        "sharing_period": per,
        "sharing_age": _staleness_days(per),
    }
    _cache["stamp"] = stamp
    _cache["data"] = data
    return data


# ── hitungan ──────────────────────────────────────────────────────────────

def build(month: str) -> dict:
    d = load_data()
    rs = d["rs"]
    if rs.empty:
        return {"empty": True}

    term = d["term"].set_index("key")
    months = sorted(rs["periode"].unique())
    idx = months.index(month) if month in months else len(months) - 1
    month = months[idx]

    cur = rs[rs["periode"] == month].copy()
    cur = cur.join(term, on="key")
    cur["rent"] = cur["rent"].fillna(0.0)
    cur["difotoin_pct"] = np.where(cur["total_revenue"] > 0, cur["difotoin_amount"] / cur["total_revenue"] * 100, 0.0)
    cur["partner_pct"] = np.where(cur["total_revenue"] > 0, cur["partner_amount"] / cur["total_revenue"] * 100, 0.0)

    live = cur[cur["total_revenue"] > 0]
    tot_rev = float(cur["total_revenue"].sum())
    tot_partner = float(cur["partner_amount"].sum())
    tot_broker = float(cur["broker_amount"].sum())
    tot_dif = float(cur["difotoin_amount"].sum())
    rent_now = float(live["rent"].sum())

    # ── modal & balik modal per MESIN (investasi ikut unit, bukan outlet)
    doc = ums.ensure_doc(d["outlets"], d["sharing"], months[0])
    attr = ums.attribution(doc, rs)
    pb = ums.payback(doc, rs)

    def status(p: float) -> tuple[str, str]:
        if p >= 100:
            return "Balik modal", C_MINT
        if p >= 75:
            return "Hampir", C_BLUE
        if p >= 25:
            return "Jalan", C_AMBER
        return "Seret", C_RED

    if pb is not None and not pb.empty:
        pb["status"], pb["tone"] = zip(*[status(p) for p in pb["progress"]])
        payback_rows = pb.sort_values("progress").reset_index(drop=True)
        capital = float(pb["harga_jual"].sum())
        capital_back = float(pb["kembali"].sum())
        capital_remain = float(pb["remain"].sum())
        capital_done = int((pb["progress"] >= 100).sum())
        capital_units = int(len(pb))
        idle_mask = (pb["per_bulan"] <= 0) & (pb["status"] != "dijual")
        machines_idle = int(idle_mask.sum())
        machines_idle_rp = float(pb.loc[idle_mask, "harga_jual"].sum())
        hpp_filled = int(pb["modal"].notna().sum())
        hpp_total = float(pd.to_numeric(pb["modal"], errors="coerce").fillna(0).sum())
        margin_rows = pb[pb["modal"].notna()].copy()
        margin_rows["margin"] = margin_rows["harga_jual"] - margin_rows["modal"]
        margin_rows["margin_pct"] = np.where(
            margin_rows["harga_jual"] > 0, margin_rows["margin"] / margin_rows["harga_jual"] * 100, 0.0
        )
        margin_total = float(margin_rows["margin"].sum())
        no_beli = int(pb["tgl_beli"].isna().sum())
        moved = int((pb["pindah"] > 0).sum())
        partners = ums.by_partner(pb, attr, month)
    else:
        payback_rows = pb if pb is not None else pd.DataFrame()
        capital = capital_back = capital_remain = hpp_total = margin_total = 0.0
        capital_done = capital_units = machines_idle = hpp_filled = no_beli = moved = 0
        machines_idle_rp = 0.0
        margin_rows = pd.DataFrame()
        partners = pd.DataFrame()

    # ── trend 13 bulan
    tm = months[max(0, idx - 12): idx + 1]
    trend = rs[rs["periode"].isin(tm)].groupby("periode")[["partner_amount", "broker_amount", "difotoin_amount"]].sum()

    # ── margin outlet (bulan terpilih)
    margins = live.sort_values("total_revenue", ascending=False)[
        ["outlet_name", "total_revenue", "partner_amount", "difotoin_amount", "partner_pct", "difotoin_pct"]
    ].head(15)

    # ── kualitas data
    no_contract = cur[(cur["total_revenue"] > 0) & (~cur["in_master"].fillna(False))]
    hygiene = {
        "no_contract": int(len(no_contract)),
        "no_contract_rev": float(no_contract["total_revenue"].sum()),
        "cap_outlets": capital_units,
        "idle_cap": machines_idle,
        "idle_cap_rp": machines_idle_rp,
        "sharing_period": d["sharing_period"],
        "sharing_age": d["sharing_age"],
        "no_investor": int((pb["mitra"].fillna("") == "").sum()) if (pb is not None and not pb.empty) else 0,
        "hpp_filled": hpp_filled,
        "no_beli": no_beli,
        "moved": moved,
    }

    return {
        "empty": False,
        "month": month,
        "prev": months[idx - 1] if idx > 0 else None,
        "months": months,
        "tot_rev": tot_rev,
        "tot_partner": tot_partner,
        "tot_broker": tot_broker,
        "tot_dif": tot_dif,
        "rent_now": rent_now,
        "outlets": int(len(live)),
        "partner_pct": (tot_partner / tot_rev * 100) if tot_rev else 0.0,
        "dif_pct": (tot_dif / tot_rev * 100) if tot_rev else 0.0,
        "capital": capital,
        "capital_outlets": capital_units,
        "capital_back": capital_back,
        "capital_progress": (capital_back / capital * 100) if capital else 0.0,
        "capital_done": capital_done,
        "capital_remain": capital_remain,
        "hpp_filled": hpp_filled,
        "hpp_total": hpp_total,
        "margin_total": margin_total,
        "margin_rows": margin_rows,
        "partners": partners,
        "payback": payback_rows,
        "trend": trend,
        "margins": margins,
        "hygiene": hygiene,
        "generated": pd.Timestamp.now().strftime("%d %b %H:%M"),
    }


# ── ui ────────────────────────────────────────────────────────────────────

def _css() -> str:
    return """
  .km-kpis { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
  .km-kpi { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; padding: 12px 14px;
            display: flex; flex-direction: column; gap: 3px; min-height: 92px; justify-content: center; }
  .km-kpi .l { font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase; color: @MUT@;
               font-weight: 700; min-height: 26px; line-height: 1.25; }
  .km-kpi .v { font-size: 20px; font-weight: 750; letter-spacing: -.02em; line-height: 1.1; }
  .km-kpi .s { font-size: 11px; color: @MUT@; line-height: 1.35; }
  .km-sec { margin-top: 18px; font-size: 11px; text-transform: uppercase; letter-spacing: .07em;
            color: @MUT@; font-weight: 700; }
  .km-sub { font-size: 11px; color: @MUT@; margin: -4px 0 8px 0; }
  .km-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .km-table th { text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: .05em;
                 color: @MUT@; padding: 7px 8px; border-bottom: 1px solid @LINE@; white-space: nowrap; }
  .km-table td { padding: 7px 8px; border-bottom: 1px solid rgba(255,255,255,.045); white-space: nowrap; }
  .km-table tr:hover td { background: rgba(255,255,255,.02); }
  .km-table td.num, .km-table th.num { text-align: right; }
  .km-chip { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: 10px; font-weight: 700; }
  .km-bar { display: block; height: 6px; border-radius: 999px; background: rgba(255,255,255,.08); overflow: hidden; width: 100%; min-width: 52px; }
  .km-bar > i { display: block; height: 6px; border-radius: 999px; }
  .km-note { font-size: 10.5px; color: @MUT@; line-height: 1.55; }
  .km-meta { font-size: 9.5px; color: @MUT@; }
  .modebar { display: none !important; }
  @media (max-width: 900px) {
    .km-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .km-kpi .v { font-size: 17px; }
    .km-hide-sm { display: none; }
    .km-table { font-size: 11px; }
    .km-table td, .km-table th { padding: 6px; }
  }
""".replace("@PANEL@", C_PANEL).replace("@LINE@", C_LINE).replace("@MUT@", C_MUT)


def kpis_html(m: dict) -> str:
    def card(label, value, sub, color=None):
        return (
            '<div class="km-kpi"><div class="l">' + label + "</div>"
            '<div class="v" style="color:' + (color or C_TXT) + '">' + value + "</div>"
            '<div class="s">' + sub + "</div></div>"
        )

    net = m["tot_dif"] - m["rent_now"]
    net_pct = (net / m["tot_rev"] * 100) if m["tot_rev"] else 0.0
    tone_back = C_MINT if m["capital_progress"] >= 100 else C_AMBER
    return (
        '<div class="km-kpis">'
        + card("Omzet kemitraan", rp_short(m["tot_rev"]), f'{m["outlets"]} outlet bertransaksi')
        + card("Bagian Kemitraan", rp_short(m["tot_partner"]),
               pct(m["partner_pct"]) + "% dari omzet · pemilik mesin", C_VIOLET)
        + card("Bagian Difotoin", rp_short(m["tot_dif"]),
               "net " + rp_short(net) + " (" + pct(net_pct) + "%) setelah sewa", C_MINT)
        + card("Broker / tempat", rp_short(m["tot_broker"]),
               "sewa " + rp_short(m["rent_now"]) + " · sharing/ minimum", C_AMBER)
        + card("Modal mitra (mesin)", rp_short(m["capital"]),
               f'{m["capital_outlets"]} unit · HPP terisi {m["hpp_filled"]}', C_BLUE)
        + card("Balik modal", pct(m["capital_progress"]) + "%",
               f'{m["capital_done"]}/{m["capital_outlets"]} unit 100% · sisa {rp_short(m["capital_remain"])}',
               tone_back)
        + "</div>"
    )


def partners_html(m: dict) -> str:
    head = (
        "<tr><th>Mitra</th><th class=\"num\">Unit</th><th class=\"num\">Harga jual</th>"
        "<th class=\"num\">Kembali</th><th class=\"num\">Payout bulan ini</th>"
        "<th style=\"width:130px\">Progres balik modal</th><th class=\"num km-hide-sm\">%</th></tr>"
    )
    body = []
    for _, r in m["partners"].iterrows():
        prog = float(r["progress"] or 0)
        tone = C_MINT if prog >= 100 else (C_BLUE if prog >= 75 else (C_AMBER if prog >= 25 else C_RED))
        w = min(100.0, max(2.0, prog))
        body.append(
            "<tr>"
            f"<td><b>{html.escape(str(r['mitra_name']))}</b></td>"
            f"<td class=\"num\">{int(r['unit'])}</td>"
            f"<td class=\"num\">{rp_short(r['jual'])}</td>"
            f"<td class=\"num\">{rp_short(r['kembali'])}</td>"
            f"<td class=\"num\">{rp_short(r['payout_now'])}</td>"
            f"<td><span class=\"km-bar\"><i style=\"width:{w:.0f}%;background:{tone}\"></i></span></td>"
            f"<td class=\"num km-hide-sm\" style=\"color:{tone};font-weight:700\">{pct(prog)}%</td>"
            "</tr>"
        )
    if not body:
        body.append('<tr><td colspan="7" style="color:' + C_MUT + '">Belum ada unit mesin. Isi di Setting Unit Mesin.</td></tr>')
    return '<div style="overflow:auto"><table class="km-table">' + head + "".join(body) + "</table></div>"


def payback_html(m: dict) -> str:
    head = (
        "<tr><th>Mesin</th><th class=\"km-hide-sm\">Mitra</th><th>Outlet</th>"
        "<th class=\"num\">Harga jual</th><th class=\"num\">Kembali</th><th class=\"num\">Sisa</th>"
        "<th class=\"num\">%</th><th class=\"num km-hide-sm\">Sisa bln</th>"
        "<th class=\"num km-hide-sm\">Pindah</th><th>Status</th></tr>"
    )
    body = []
    for _, r in m["payback"].iterrows():
        mi = r["months_left"]
        if mi is None or not np.isfinite(mi) or float(mi) <= 0:
            mi_txt = "—"
        elif float(mi) > 60:
            mi_txt = ">60"
        else:
            mi_txt = f"{float(mi):.0f}"
        body.append(
            "<tr>"
            f"<td><b>{html.escape(str(r['label']))}</b><div class=\"km-meta\">{html.escape(str(r['id']))}</div></td>"
            f"<td class=\"km-hide-sm\" style=\"color:{C_MUT}\">{html.escape(str(r['mitra'] or '—'))}</td>"
            f"<td>{html.escape(str(r['outlet']))}</td>"
            f"<td class=\"num\">{rp_short(r['harga_jual'])}</td>"
            f"<td class=\"num\">{rp_short(r['kembali'])}</td>"
            f"<td class=\"num\" style=\"color:{C_MUT}\">{rp_short(r['remain'])}</td>"
            f"<td class=\"num\" style=\"color:{r['tone']};font-weight:700\">{pct(r['progress'])}%</td>"
            f"<td class=\"num km-hide-sm\" style=\"color:{C_MUT}\">{mi_txt}</td>"
            f"<td class=\"num km-hide-sm\" style=\"color:{C_MUT}\">{int(r['pindah'])}×</td>"
            f"<td><span class=\"km-chip\" style=\"background:{r['tone']}22;color:{r['tone']}\">{r['status']}</span></td>"
            "</tr>"
        )
    if not body:
        body.append('<tr><td colspan="10" style="color:' + C_MUT + '">Belum ada unit mesin.</td></tr>')
    return '<div style="overflow:auto"><table class="km-table">' + head + "".join(body) + "</table></div>"


def machines_html(m: dict) -> str:
    rows = m.get("margin_rows")
    if rows is None or len(rows) == 0:
        return ('<div class="km-note">Modal/HPP mesin belum diisi. Isi di '
                '<a href="/kemitraan-setting" style="color:#5b8cff;text-decoration:none">Setting Unit Mesin</a> '
                'supaya margin penjualan mesin bisa dihitung.</div>')
    head = (
        "<tr><th>Mesin</th><th class=\"km-hide-sm\">Mitra</th><th class=\"num\">Harga jual ke mitra</th>"
        "<th class=\"num\">Modal / HPP</th><th class=\"num\">Margin</th>"
        "<th class=\"num\">Margin %</th></tr>"
    )
    body = []
    for _, r in rows.sort_values("margin", ascending=False).iterrows():
        mp = float(r["margin_pct"] or 0)
        tone = C_MINT if mp >= 0 else C_RED
        body.append(
            "<tr>"
            f"<td><b>{html.escape(str(r['label']))}</b></td>"
            f"<td class=\"km-hide-sm\" style=\"color:{C_MUT}\">{html.escape(str(r['mitra'] or '—'))}</td>"
            f"<td class=\"num\">{rp_short(r['harga_jual'])}</td>"
            f"<td class=\"num\">{rp_short(r['modal'])}</td>"
            f"<td class=\"num\" style=\"color:{tone};font-weight:700\">{rp_short(r['margin'])}</td>"
            f"<td class=\"num\" style=\"color:{tone}\">{pct(mp)}%</td>"
            "</tr>"
        )
    body.append(
        "<tr><td><b>Total</b></td><td class=\"km-hide-sm\"></td>"
        f"<td class=\"num\">{rp_short(rows['harga_jual'].sum())}</td>"
        f"<td class=\"num\">{rp_short(rows['modal'].sum())}</td>"
        f"<td class=\"num\">{rp_short(rows['margin'].sum())}</td><td></td></tr>"
    )
    return '<div style="overflow:auto"><table class="km-table">' + head + "".join(body) + "</table></div>"


def margins_html(m: dict) -> str:
    head = (
        "<tr><th>Outlet</th><th class=\"num\">Omzet</th><th class=\"num\">Hak mitra</th>"
        "<th class=\"num km-hide-sm\">Bagian Difotoin</th><th class=\"num\">Mitra %</th>"
        "<th class=\"num km-hide-sm\">Difotoin %</th></tr>"
    )
    body = []
    for _, r in m["margins"].iterrows():
        pp = float(r["partner_pct"] or 0)
        tone = C_RED if pp >= 60 else (C_AMBER if pp >= 40 else C_TXT)
        body.append(
            "<tr>"
            f"<td><b>{html.escape(str(r['outlet_name']))}</b></td>"
            f"<td class=\"num\">{rp_short(r['total_revenue'])}</td>"
            f"<td class=\"num\">{rp_short(r['partner_amount'])}</td>"
            f"<td class=\"num km-hide-sm\">{rp_short(r['difotoin_amount'])}</td>"
            f"<td class=\"num\" style=\"color:{tone};font-weight:700\">{pct(pp)}%</td>"
            f"<td class=\"num km-hide-sm\">{pct(r['difotoin_pct'])}%</td>"
            "</tr>"
        )
    return '<div style="overflow:auto"><table class="km-table">' + head + "".join(body) + "</table></div>"


# ── page ──────────────────────────────────────────────────────────────────

def create_page(container: ui.column):
    ui.add_head_html("<style>" + _css() + "</style>")
    data = load_data()
    with container:
        rs = data.get("rs")
        if rs is None or rs.empty:
            ui.label("Cache transaksi belum tersedia.").classes("text-red-400")
            return
        months = sorted(data["rs"]["periode"].unique())

        ui.html(
            '<div style="font-size:19px;font-weight:750;letter-spacing:-.02em">🤝 Kemitraan</div>'
            '<div style="font-size:11.5px;color:' + C_MUT + '">Modal mitra, bagi hasil, dan balik modal '
            "— dihitung dari transaksi aktual.</div>",
            sanitize=False,
        )

        with ui.row().classes("w-full items-center gap-3 mt-2 mb-1"):
            sel = ui.select({m: lbl_month(m) for m in months[::-1]}, value=months[-1],
                            label="Bulan").props("dense outlined dark").classes("w-[150px]")
            info = ui.label("").classes("text-xs")
            info.style("color:" + C_MUT)

        body = ui.column().classes("w-full")

        def render():
            month = sel.value or months[-1]
            m = build(month)
            if m.get("empty"):
                body.clear()
                with body:
                    ui.label("Belum ada data kemitraan.").classes("text-gray-400 italic")
                return
            info.set_text(f'{lbl_month(m["month"])} · {m["outlets"]} outlet · '
                          f'kontrak master {m["hygiene"]["sharing_period"]}')
            body.clear()
            with body:
                ui.html(kpis_html(m), sanitize=False).classes("w-full")

                ui.html('<div class="km-sec">Pembagian omzet kemitraan · 13 bulan</div>'
                        '<div class="km-sub">Dalam Rp juta — aktual: bagian kemitraan, broker (tempat), dan Difotoin.</div>',
                        sanitize=False).classes("w-full")
                tr = m["trend"]
                fig = go.Figure()
                fig.add_bar(x=[lbl_month(p) for p in tr.index], y=tr["partner_amount"] / 1e6,
                            name="Kemitraan (mesin)", marker_color=C_VIOLET)
                fig.add_bar(x=[lbl_month(p) for p in tr.index], y=tr["broker_amount"] / 1e6,
                            name="Broker (tempat)", marker_color=C_AMBER)
                fig.add_bar(x=[lbl_month(p) for p in tr.index], y=tr["difotoin_amount"] / 1e6,
                            name="Difotoin", marker_color=C_MINT)
                fig.update_layout(
                    template="plotly_dark", barmode="stack", height=280,
                    margin=dict(l=6, r=6, t=6, b=6),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
                    yaxis=dict(title=None, gridcolor="#24242f", zeroline=False, tickfont=dict(size=10)),
                    xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                )
                ui.plotly(fig).classes("w-full h-[280px]")

                ui.html('<div class="km-sec">Mitra & mesinnya</div>'
                        '<div class="km-sub">Modal dihitung dari harga jual mesin ke mitra, bukan dari outlet.</div>',
                        sanitize=False).classes("w-full")
                ui.html(partners_html(m), sanitize=False).classes("w-full")

                ui.html('<div class="km-sec">Balik modal per mesin</div>'
                        '<div class="km-sub">Diurut dari yang paling jauh dari balik modal. '
                        'Kalau mesin pindah, payout dari lokasi lama dan baru tetap dijumlahkan '
                        'ke mesin yang sama. Kumulatif sejak Jul 2025.</div>',
                        sanitize=False).classes("w-full")
                ui.html(payback_html(m), sanitize=False).classes("w-full")

                ui.html('<div class="km-sec">Margin penjualan mesin</div>'
                        '<div class="km-sub">Harga jual ke mitra dibanding modal/HPP Difotoin per unit.</div>',
                        sanitize=False).classes("w-full")
                ui.html(machines_html(m), sanitize=False).classes("w-full")

                ui.html(f'<div class="km-sec">Margin per outlet · {lbl_month(m["month"])}</div>'
                        '<div class="km-sub">15 outlet omzet terbesar. Kemitraan ≥60% diberi warna merah: '
                        'di situ Difotoin bekerja paling mahal.</div>', sanitize=False).classes("w-full")
                ui.html(margins_html(m), sanitize=False).classes("w-full")

                h = m["hygiene"]
                ui.html(
                    '<div class="km-sec">Yang perlu dilengkapi</div>'
                    '<div class="km-note" style="margin-top:4px">'
                    f'• {h["no_contract"]} outlet bertransaksi tanpa baris kontrak di master '
                    f'(omzet {rp_short(h["no_contract_rev"])} bulan ini) — bagi hasilnya jalan, '
                    'tapi syaratnya tidak tercatat.<br>'
                    f'• {h["cap_outlets"]} unit mesin mitra; {h["idle_cap"]} di antaranya tidak '
                    f'menghasilkan payout 3 bulan terakhir (harga jual {rp_short(h["idle_cap_rp"])}).<br>'
                    f'• HPP terisi {h["hpp_filled"]}/{h["cap_outlets"]} unit, tgl beli kosong '
                    f'{h["no_beli"]} unit — margin penjualan mesin baru bisa dihitung kalau HPP diisi '
                    'di Setting Unit Mesin.<br>'
                    f'• {h["moved"]} unit pernah pindah lokasi; payout-nya tetap dihitung ke mesin '
                    'yang sama.<br>'
                    f'• Master kontrak terakhir {h["sharing_period"]} '
                    f'({h["sharing_age"] if h["sharing_age"] is not None else "?"} hari lalu); '
                    'halaman ini memakai kontrak live dari API outlet, master hanya untuk nama mitra.'
                    "</div>", sanitize=False).classes("w-full")

                ui.html('<div class="km-note" style="margin-top:10px">'
                        "Sumber: rs_outlet (Rp aktual per outlet per bulan) · outlet master API "
                        "(partner share, sewa, initial cost) · master sharing (nama mitra). "
                        "Bagian Difotoin = sebelum sewa; sewa " + rp_short(m["rent_now"]) +
                        " sudah dikurangkan di kartu. Dihitung " + m["generated"] + ".</div>",
                        sanitize=False).classes("w-full")

                ui.html('<div class="km-note" style="margin-top:8px">'
                        '⚙️ <a href="/kemitraan-setting" style="color:#5b8cff;text-decoration:none">'
                        'Setting Unit Mesin</a> — modal, HPP, tanggal beli, pindah lokasi · '
                        'tabel kontrak lama: <a href="/kemitraan-classic" '
                        'style="color:#5b8cff;text-decoration:none">/kemitraan-classic</a></div>',
                        sanitize=False).classes("w-full")

        sel.on("change", lambda e: render())
        render()
