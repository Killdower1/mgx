"""Penyimpanan unit mesin mitra — investasi ikut mesin, bukan outlet.

Model bisnis Difotoin:
- Status outlet "mitra" berarti mesinnya milik kemitraan (dibeli mitra per pcs).
- Omzet di outlet dibagi 3: Difotoin, Kemitraan (pemilik mesin), Broker (tempat:
  sewa atau sharing dengan minimum payment).
- Mesin bisa pindah tempat; modalnya tidak berubah. Karena itu modal dicatat per
  UNIT, dan pendapatan dihitung dari lokasi tempat unit itu berdiri per bulan.

File data: streamlit_template/data/unit_mesin.json
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pandas as pd

DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "streamlit_template"
    / "data"
    / "unit_mesin.json"
)

STATUS = ["aktif", "idle", "rusak", "dijual"]


def _norm(s) -> str:
    s = str(s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def empty_doc() -> dict:
    return {"version": 1, "units": []}


def load() -> dict:
    try:
        doc = json.loads(DATA_PATH.read_text())
    except FileNotFoundError:
        return empty_doc()
    except Exception:
        return empty_doc()
    doc.setdefault("units", [])
    doc.setdefault("version", 1)
    return doc


def save(doc: dict) -> None:
    """Tulis atomik: file lama utuh kalau penulisan gagal."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(DATA_PATH.parent), prefix=".unit_mesin_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        json.loads(Path(tmp).read_text())
        os.replace(tmp, DATA_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def next_id(doc: dict) -> str:
    used = {u.get("id") for u in doc.get("units", [])}
    i = 1
    while f"KM-{i:03d}" in used:
        i += 1
    return f"KM-{i:03d}"


def seed_from_outlets(outlets: pd.DataFrame, sharing: pd.DataFrame, start_month: str | None) -> dict:
    """Buat unit awal dari outlet yang sudah punya initial_cost (harga beli mitra)."""
    doc = empty_doc()
    if outlets is None or outlets.empty or "initial_cost" not in outlets.columns:
        return doc
    sh = {}
    if sharing is not None and not sharing.empty and "outlet_name" in sharing.columns:
        sh = {_norm(r["outlet_name"]): r.get("investor_name") for _, r in sharing.iterrows()}

    rows = outlets[pd.to_numeric(outlets["initial_cost"], errors="coerce").fillna(0) > 0]
    for _, r in rows.iterrows():
        name = str(r.get("name") or "").strip()
        mitra = str(sh.get(_norm(name)) or "").strip()
        if mitra.lower() in ("-", "nan", "none"):
            mitra = ""
        doc["units"].append(
            {
                "id": next_id(doc),
                "label": name,
                "mitra": mitra,
                "ownership": "kemitraan",
                "harga_jual": _num(r.get("initial_cost")),
                "modal": None,
                "tgl_beli": None,
                "status": "aktif",
                "placements": [
                    {"outlet": name, "start": start_month, "end": None}
                ],
            }
        )
    return doc


def ensure_doc(outlets: pd.DataFrame, sharing: pd.DataFrame, start_month: str | None) -> dict:
    """Muat dokumen; kalau belum ada, seed sekali dari data outlet."""
    if DATA_PATH.exists():
        return load()
    doc = seed_from_outlets(outlets, sharing, start_month)
    if doc["units"]:
        save(doc)
    return doc


def placements(unit: dict) -> list[dict]:
    pl = unit.get("placements") or []
    return [p for p in pl if p.get("outlet")]


def current_placement(unit: dict, month: str | None = None) -> dict | None:
    """Penempatan yang aktif pada bulan itu (atau yang terakhir kalau month None)."""
    pl = placements(unit)
    if not pl:
        return None
    if month:
        for p in pl:
            start = p.get("start") or "0000-00"
            end = p.get("end") or "9999-99"
            if start <= month <= end:
                return p
        return None
    open_pl = [p for p in pl if not p.get("end")]
    return sorted(open_pl or pl, key=lambda p: (p.get("start") or ""))[-1]


def move_unit(unit: dict, outlet: str, month: str) -> None:
    """Tutup penempatan berjalan sebelum `month`, buka yang baru mulai `month`."""
    cur = current_placement(unit)
    pl = unit.setdefault("placements", [])
    if cur is not None:
        if cur.get("start") and month <= cur["start"]:
            cur["outlet"] = outlet
            cur["end"] = None
            return
        cur["end"] = _prev_month(month)
    pl.append({"outlet": outlet, "start": month, "end": None})


def _prev_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    if mo == 1:
        return f"{y - 1}-12"
    return f"{y}-{mo - 1:02d}"


def unit_outlets(unit: dict) -> list[str]:
    return [p["outlet"] for p in placements(unit)]


def move_count(unit: dict) -> int:
    return max(0, len(placements(unit)) - 1)


def attribution(doc: dict, rs: pd.DataFrame) -> pd.DataFrame:
    """Bagi partner_amount tiap outlet-bulan ke unit yang berdiri di situ.

    Kalau satu outlet punya >1 unit pada bulan itu, nilainya dibagi rata.
    """
    cols = ["unit_id", "month", "outlet", "amount", "share"]
    if rs is None or rs.empty:
        return pd.DataFrame(columns=cols)

    by_place: dict[tuple[str, str], list[str]] = {}
    for u in doc.get("units", []):
        for p in placements(u):
            by_place.setdefault((_norm(p["outlet"]), u["id"]), []).append(
                (p.get("start") or "0000-00", p.get("end") or "9999-99")
            )

    rows = []
    for _, r in rs.iterrows():
        key = _norm(r["outlet_name"])
        month = str(r["periode"])
        cands = [
            uid for (k, uid), spans in by_place.items()
            if k == key and any(s <= month <= e for s, e in spans)
        ]
        if not cands:
            continue
        amt = _num(r.get("partner_amount"))
        share = len(cands)
        for uid in cands:
            rows.append(
                {"unit_id": uid, "month": month, "outlet": r["outlet_name"], "amount": amt / share, "share": share}
            )
    return pd.DataFrame(rows, columns=cols)


def payback(doc: dict, rs: pd.DataFrame, avg_months: int = 3) -> pd.DataFrame:
    """Tabel balik modal per unit: harga jual vs payout kemitraan kumulatif."""
    units = doc.get("units", [])
    if not units:
        return pd.DataFrame()

    attr = attribution(doc, rs)
    months = sorted(rs["periode"].astype(str).unique()) if rs is not None and not rs.empty else []
    tail = months[-avg_months:] if months else []

    cum = attr.groupby("unit_id")["amount"].sum() if not attr.empty else pd.Series(dtype=float)
    recent = attr[attr["month"].isin(tail)].groupby("unit_id")["amount"].sum() if not attr.empty else pd.Series(dtype=float)

    rows = []
    for u in units:
        uid = u["id"]
        jual = _num(u.get("harga_jual"))
        kembali = float(cum.get(uid, 0.0))
        per_bulan = float(recent.get(uid, 0.0)) / max(1, len(tail)) if tail else 0.0
        remain = max(0.0, jual - kembali)
        prog = (kembali / jual * 100) if jual > 0 else 0.0
        rows.append(
            {
                "id": uid,
                "label": u.get("label") or uid,
                "mitra": u.get("mitra") or "",
                "ownership": u.get("ownership") or "kemitraan",
                "status": u.get("status") or "aktif",
                "harga_jual": jual,
                "modal": _num(u.get("modal"), None) if u.get("modal") not in (None, "") else None,
                "tgl_beli": u.get("tgl_beli"),
                "outlet": (current_placement(u) or {}).get("outlet") or "—",
                "mulai": (current_placement(u) or {}).get("start") or "—",
                "pindah": move_count(u),
                "kembali": kembali,
                "per_bulan": per_bulan,
                "remain": remain,
                "progress": prog,
                "months_left": (remain / per_bulan) if per_bulan > 0 and remain > 0 else None,
            }
        )
    return pd.DataFrame(rows)


def by_partner(pb: pd.DataFrame, attr: pd.DataFrame, month: str) -> pd.DataFrame:
    """Ringkas per mitra: unit, harga jual, payout kumulatif, payout bulan ini."""
    if pb is None or pb.empty:
        return pd.DataFrame()
    cur = attr[attr["month"] == month].groupby("unit_id")["amount"].sum() if not attr.empty else pd.Series(dtype=float)
    df = pb.copy()
    df["mitra_name"] = df["mitra"].replace("", "Tanpa nama")
    df["payout_now"] = df["id"].map(lambda u: float(cur.get(u, 0.0)))
    out = df.groupby("mitra_name", as_index=False).agg(
        unit=("id", "size"),
        jual=("harga_jual", "sum"),
        kembali=("kembali", "sum"),
        payout_now=("payout_now", "sum"),
    )
    out["progress"] = out["kembali"] / out["jual"].replace(0, pd.NA) * 100
    return out.sort_values("jual", ascending=False)
