"""Unit mesin mitra v2 — mesin per mitra, lokasi ditempel dari tanggal transaksi.

Konsep (sesuai pemilik):
- Mitra beli mesin per pcs. Satu mitra bisa punya banyak mesin.
- Mesin bisa pindah lokasi; jumlah lokasi yang pernah dipakai bisa lebih banyak
  dari jumlah mesin (mis. 5 mesin, 8 lokasi).
- Bagi hasil per outlet: Kemitraan (pemilik mesin), Broker (tempat), Difotoin.
- Modal dicatat per mesin (harga jual ke mitra), opsional HPP Difotoin.

File: streamlit_template/data/mitra_units.json
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parents[2] / "streamlit_template" / "data" / "mitra_units.json"

STATUS = ["aktif", "idle", "rusak", "dijual", "stok"]
GAP_TOLERANCE = 2  # bulan; jeda <= 2 bulan di outlet yang sama tidak dianggap pindah


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


def _prev_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def _month_idx(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7])


# ── penyimpanan ───────────────────────────────────────────────────────────

def empty_doc() -> dict:
    return {"version": 2, "partners": [], "unassigned": []}


def load() -> dict:
    try:
        doc = json.loads(DATA_PATH.read_text())
    except Exception:
        return empty_doc()
    doc.setdefault("partners", [])
    doc.setdefault("unassigned", [])
    doc.setdefault("version", 2)
    return doc


def save(doc: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(DATA_PATH.parent), prefix=".mitra_units_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        json.loads(Path(tmp).read_text())
        os.replace(tmp, DATA_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def next_id(doc: dict, prefix: str, scope: list) -> str:
    used = {x.get("id") for x in scope}
    i = 1
    while f"{prefix}-{i:02d}" in used:
        i += 1
    return f"{prefix}-{i:02d}"


# ── turunkan penempatan dari transaksi ────────────────────────────────────

def episodes_for(outlet: str, rs: pd.DataFrame, daily: pd.DataFrame | None = None) -> list[dict]:
    """Rentetan bulan berturut-turut dengan omzet > 0 di satu outlet."""
    sub = rs[(rs["outlet_name"] == outlet) & (rs["total_revenue"] > 0)]
    months = sorted({str(m) for m in sub["periode"]})
    if not months:
        return []

    runs, start, prev = [], months[0], months[0]
    for cur in months[1:]:
        if _month_idx(cur) - _month_idx(prev) > GAP_TOLERANCE:
            runs.append((start, prev))
            start = cur
        prev = cur
    runs.append((start, prev))

    out = []
    for a, b in runs:
        first = last = None
        if daily is not None and not daily.empty:
            d = daily[(daily["outlet_name"] == outlet) & daily["date"].notna()]
            d = d[d["date"].dt.strftime("%Y-%m").between(a, b)]
            if not d.empty:
                first = d["date"].min().strftime("%Y-%m-%d")
                last = d["date"].max().strftime("%Y-%m-%d")
        out.append({"outlet": outlet, "start": a, "end": b, "first_date": first, "last_date": last})
    return out


def assign_machines(eps: list[dict]) -> list[list[dict]]:
    """Interval coloring: satu mesin hanya bisa di satu tempat pada satu waktu."""
    machines: list[list[dict]] = []
    for e in sorted(eps, key=lambda x: x["start"]):
        for m in machines:
            if _month_idx(m[-1]["end"]) < _month_idx(e["start"]):
                m.append(e)
                break
        else:
            machines.append([e])
    return machines


def derive_partner(name: str, aliases: list[str], outlets: list[str], rs: pd.DataFrame,
                   daily: pd.DataFrame | None, harga_map: dict) -> dict:
    eps = []
    for o in outlets:
        eps.extend(episodes_for(o, rs, daily))
    groups = assign_machines(eps)
    machines = []
    for i, chain in enumerate(groups, 1):
        harga = 0.0
        for e in chain:
            if harga_map.get(_norm(e["outlet"])):
                harga = harga_map[_norm(e["outlet"])]
                break
        machines.append({
            "id": f"M-{i:02d}",
            "label": f"Mesin {i}",
            "harga": harga,
            "hpp": None,
            "tgl_beli": None,
            "status": "aktif",
            "placements": [
                {"outlet": e["outlet"], "start": e["start"], "end": e["end"], "derived": True}
                for e in chain
            ],
        })
    no_tx = [o for o in outlets if not any(e["outlet"] == o for e in eps)]
    return {"id": "", "name": name, "aliases": aliases, "machines": machines, "no_tx": no_tx}


def seed(rs: pd.DataFrame, daily: pd.DataFrame, sharing: pd.DataFrame, outlets: pd.DataFrame) -> dict:
    doc = empty_doc()
    harga_map = {}
    if outlets is not None and not outlets.empty and "initial_cost" in outlets.columns:
        for _, r in outlets.iterrows():
            v = _num(r.get("initial_cost"))
            if v > 0:
                harga_map[_norm(r.get("name"))] = v

    if sharing is None or sharing.empty:
        return doc
    seen = {}
    for _, r in sharing.iterrows():
        name = str(r.get("investor_name") or "").strip()
        if name.lower() in ("", "-", "nan", "none"):
            continue
        seen.setdefault(name, []).append(r["outlet_name"])

    machine_counter = 0
    for name, outlets_list in seen.items():
        p = derive_partner(name, [name], sorted(set(outlets_list)), rs, daily, harga_map)
        p["id"] = next_id(doc, "P", doc["partners"])
        for m in p["machines"]:
            machine_counter += 1
            m["id"] = f"M-{machine_counter:02d}"  # id unik lintas mitra
        doc["partners"].append(p)
    return doc


def ensure_doc(rs: pd.DataFrame, daily: pd.DataFrame, sharing: pd.DataFrame, outlets: pd.DataFrame) -> dict:
    if DATA_PATH.exists():
        return load()
    doc = seed(rs, daily, sharing, outlets)
    if doc["partners"]:
        save(doc)
    return doc


# ── penempatan ────────────────────────────────────────────────────────────

def placements(machine: dict) -> list[dict]:
    return [p for p in (machine.get("placements") or []) if p.get("outlet")]


def current_placement(machine: dict, month: str | None = None) -> dict | None:
    pl = placements(machine)
    if not pl:
        return None
    if month:
        for p in pl:
            if (p.get("start") or "0000-00") <= month <= (p.get("end") or "9999-99"):
                return p
        return None
    open_pl = [p for p in pl if not p.get("end")]
    return sorted(open_pl or pl, key=lambda p: p.get("start") or "")[-1]


def move_machine(machine: dict, outlet: str, month: str) -> None:
    cur = current_placement(machine)
    pl = machine.setdefault("placements", [])
    if cur is not None:
        if cur.get("start") and month <= cur["start"]:
            cur["outlet"] = outlet
            cur["end"] = None
            return
        cur["end"] = _prev_month(month)
        cur["derived"] = False
    pl.append({"outlet": outlet, "start": month, "end": None, "derived": False})


def move_count(machine: dict) -> int:
    return max(0, len(placements(machine)) - 1)


def next_machine_id(doc: dict) -> str:
    used = {m.get("id") for p in doc.get("partners", []) for m in p.get("machines", [])}
    i = 1
    while f"M-{i:02d}" in used:
        i += 1
    return f"M-{i:02d}"


def partner_of(doc: dict, machine_id: str) -> dict | None:
    for p in doc.get("partners", []):
        for m in p.get("machines", []):
            if m.get("id") == machine_id:
                return p
    return None


# ── hitungan ──────────────────────────────────────────────────────────────

def attribution(doc: dict, rs: pd.DataFrame) -> pd.DataFrame:
    """Bagi partner_amount per outlet-bulan ke mesin yang ada di situ bulan itu."""
    cols = ["machine_id", "partner", "month", "outlet", "amount"]
    if rs is None or rs.empty:
        return pd.DataFrame(columns=cols)

    spans: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
    for p in doc.get("partners", []):
        for m in p.get("machines", []):
            for pl in placements(m):
                key = (_norm(pl["outlet"]), p.get("id", ""), m["id"])
                spans.setdefault(key, []).append(
                    (pl.get("start") or "0000-00", pl.get("end") or "9999-99")
                )

    rows = []
    for _, r in rs.iterrows():
        key_outlet = _norm(r["outlet_name"])
        month = str(r["periode"])
        hits = [
            (pid, mid) for (k, pid, mid), sp in spans.items()
            if k == key_outlet and any(a <= month <= b for a, b in sp)
        ]
        if not hits:
            continue
        amt = _num(r.get("partner_amount")) / len(hits)
        for pid, mid in hits:
            rows.append({"machine_id": mid, "partner": pid, "month": month,
                         "outlet": r["outlet_name"], "amount": amt})
    return pd.DataFrame(rows, columns=cols)


def payback(doc: dict, rs: pd.DataFrame, avg_months: int = 3) -> pd.DataFrame:
    attr = attribution(doc, rs)
    months = sorted(rs["periode"].astype(str).unique()) if rs is not None and not rs.empty else []
    tail = months[-avg_months:] if months else []

    cum = attr.groupby("machine_id")["amount"].sum() if not attr.empty else pd.Series(dtype=float)
    recent = attr[attr["month"].isin(tail)].groupby("machine_id")["amount"].sum() if not attr.empty else pd.Series(dtype=float)

    rows = []
    for p in doc.get("partners", []):
        for m in p.get("machines", []):
            harga = _num(m.get("harga"))
            kembali = float(cum.get(m.get("id"), 0.0))
            per_bulan = float(recent.get(m.get("id"), 0.0)) / max(1, len(tail)) if tail else 0.0
            remain = max(0.0, harga - kembali) if harga > 0 else 0.0
            rows.append({
                "machine_id": m.get("id"),
                "label": m.get("label") or m.get("id"),
                "mitra": p.get("name") or "",
                "partner_id": p.get("id"),
                "status": m.get("status") or "aktif",
                "harga": harga,
                "hpp": _num(m.get("hpp"), None) if m.get("hpp") not in (None, "") else None,
                "tgl_beli": m.get("tgl_beli"),
                "outlet": (current_placement(m) or {}).get("outlet") or "—",
                "chains": " → ".join(pl["outlet"] for pl in placements(m)) or "—",
                "pindah": move_count(m),
                "kembali": kembali,
                "per_bulan": per_bulan,
                "remain": remain,
                "progress": (kembali / harga * 100) if harga > 0 else 0.0,
                "months_left": (remain / per_bulan) if per_bulan > 0 and remain > 0 else None,
            })
    return pd.DataFrame(rows)


def by_partner(pb: pd.DataFrame, attr: pd.DataFrame, month: str) -> pd.DataFrame:
    if pb is None or pb.empty:
        return pd.DataFrame()
    cur = attr[attr["month"] == month].groupby("machine_id")["amount"].sum() if not attr.empty else pd.Series(dtype=float)
    df = pb.copy()
    df["payout_now"] = df["machine_id"].map(lambda x: float(cur.get(x, 0.0)))
    out = df.groupby(["partner_id", "mitra"], as_index=False).agg(
        mesin=("machine_id", "size"),
        harga=("harga", "sum"),
        kembali=("kembali", "sum"),
        payout_now=("payout_now", "sum"),
        lokasi=("chains", lambda s: len({x for v in s for x in str(v).split(" → ")})),
    )
    out["progress"] = out["kembali"] / out["harga"].replace(0, pd.NA) * 100
    return out.sort_values("harga", ascending=False)


def adu_rows(doc: dict, pb: pd.DataFrame) -> pd.DataFrame:
    """Bandingkan yang tercatat di sistem vs yang diinput (mesin & lokasi)."""
    rows = []
    for p in doc.get("partners", []):
        sub = pb[pb["partner_id"] == p.get("id")] if pb is not None and not pb.empty else pd.DataFrame()
        lokasi_tx = {x for v in sub.get("chains", pd.Series(dtype=str)) for x in str(v).split(" → ") if x != "—"}
        rows.append({
            "mitra": p.get("name"),
            "alias": ", ".join(p.get("aliases") or []),
            "mesin": len(p.get("machines", [])),
            "lokasi": len(lokasi_tx) + len(p.get("no_tx") or []),
            "lokasi_tanpa_transaksi": len(p.get("no_tx") or []),
            "berharga": int((sub["harga"] > 0).sum()) if not sub.empty else 0,
            "modal": float(sub["harga"].sum()) if not sub.empty else 0.0,
        })
    return pd.DataFrame(rows)
