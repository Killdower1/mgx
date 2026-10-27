"""⚙️ Setting Mitra & Mesin.

Input dari sisi mitra: nama (plus alias), jumlah mesin, harga & tanggal beli per
mesin. Lokasi tiap mesin sudah diturunkan otomatis dari tanggal transaksi
(termasuk riwayat pindah), dan bisa dikoreksi di sini.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from nicegui import ui

from services import mitra_units_store as mus

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "streamlit_template" / "data" / "api_cache"
SHARING = ROOT / "streamlit_template" / "data" / "sharing_outlets"

C_PANEL = "#1a1a24"
C_LINE = "#26262f"
C_TXT = "#eceef4"
C_MUT = "#8e93a6"
C_MINT = "#3ddc97"
C_AMBER = "#f5b83d"
C_RED = "#ff6b6b"
C_BLUE = "#5b8cff"


def _rp(v) -> str:
    try:
        return "Rp " + f"{float(v):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _frames():
    rs = pd.DataFrame(_read(CACHE / "rs_outlet.json", []))
    if not rs.empty:
        rs["periode"] = rs["periode"].astype(str)
        for c in ("total_revenue", "partner_amount"):
            rs[c] = pd.to_numeric(rs.get(c), errors="coerce").fillna(0.0)
    # daily_summary 5 MB+; tidak dibaca di halaman ini supaya render tetap ringan.
    daily = pd.DataFrame()
    outlets = pd.DataFrame(_read(CACHE / "outlets.json", []))
    sharing = pd.DataFrame([])
    try:
        files = sorted(p for p in SHARING.glob("*.json") if re.match(r"^\d{4}-\d{2}$", p.stem))
        if files:
            sharing = pd.DataFrame(_read(files[-1], []))
    except Exception:
        pass
    return rs, daily, sharing, outlets


def _outlet_names(outlets: pd.DataFrame) -> list[str]:
    if outlets.empty or "name" not in outlets.columns:
        return []
    return sorted({str(n).strip() for n in outlets["name"].dropna() if str(n).strip()})


def _css() -> str:
    return """
  .us-meta { font-size: 11px; color: @MUT@; }
  .us-chip { display:inline-block; padding:1px 7px; border-radius:999px; font-size:10px;
             background:rgba(255,255,255,.06); color:@MUT@; margin:1px 2px; }
  .q-expansion-item { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; }
  .us-table { width:100%; border-collapse:collapse; font-size:11.5px; }
  .us-table th { text-align:left; font-size:9.5px; text-transform:uppercase; letter-spacing:.05em;
                 color:@MUT@; padding:6px 8px; border-bottom:1px solid @LINE@; white-space:nowrap; }
  .us-table td { padding:6px 8px; border-bottom:1px solid rgba(255,255,255,.045); }
""".replace("@PANEL@", C_PANEL).replace("@LINE@", C_LINE).replace("@MUT@", C_MUT)


def create_page(container: ui.column):
    ui.add_head_html("<style>" + _css() + "</style>")
    rs, daily, sharing, outlets = _frames()
    months = sorted(rs["periode"].unique()) if not rs.empty else []
    names = _outlet_names(outlets)

    with container:
        ui.html(
            '<div style="font-size:19px;font-weight:750;letter-spacing:-.02em">⚙️ Setting Mitra & Mesin</div>'
            '<div style="font-size:11.5px;color:' + C_MUT + '">Input per mitra: mesin apa saja yang dia punya, '
            "harga & tanggal beli. Lokasi sudah diturunkan dari tanggal transaksi dan bisa dikoreksi.</div>",
            sanitize=False,
        )
        head = ui.column().classes("w-full")
        body = ui.column().classes("w-full")

    def doc_now() -> dict:
        return mus.ensure_doc(rs, daily, sharing, outlets)

    def refresh():
        doc = doc_now()
        pb = mus.payback(doc, rs)
        adu = mus.adu_rows(doc, pb)
        head.clear()
        body.clear()
        with head:
            ui.html(
                f'<div class="us-meta" style="margin-top:6px"><b style="color:{C_TXT}">{len(doc["partners"])} mitra</b>'
                f' · {int(adu["mesin"].sum()) if not adu.empty else 0} mesin'
                f' · {int(adu["lokasi"].sum()) if not adu.empty else 0} lokasi tercatat'
                f' · modal {_rp(adu["modal"].sum() if not adu.empty else 0)}</div>'
                '<div class="us-meta" style="margin:2px 0 10px">Mesin dihitung dari bentrokan waktu: '
                'satu mesin tidak bisa ada di dua lokasi pada bulan yang sama.</div>',
                sanitize=False,
            ).classes("w-full")
            if not adu.empty:
                rows = "".join(
                    "<tr>"
                    f"<td><b>{r['mitra']}</b><div class='us-meta'>{r['alias']}</div></td>"
                    f"<td>{int(r['mesin'])}</td><td>{int(r['lokasi'])}</td>"
                    f"<td>{int(r['lokasi_tanpa_transaksi'])}</td>"
                    f"<td>{int(r['berharga'])}</td><td>{_rp(r['modal'])}</td></tr>"
                    for _, r in adu.iterrows()
                )
                ui.html(
                    '<div style="overflow:auto"><table class="us-table"><tr><th>Mitra</th><th>Mesin</th>'
                    "<th>Lokasi</th><th>Lokasi tanpa transaksi</th><th>Mesin berharga</th><th>Modal</th></tr>"
                    + rows + "</table></div>", sanitize=False).classes("w-full mb-2")
            with ui.row().classes("w-full gap-2"):
                ui.button("+ Tambah mitra", on_click=lambda: add_partner(doc)).props("dense unelevated color=primary")
                ui.button("Hitung ulang lokasi dari transaksi",
                          on_click=lambda: rederive(doc)).props("dense outline color=grey")

        with body:
            if not doc["partners"]:
                ui.label("Belum ada mitra.").classes("text-gray-400 italic")
                return
            for p in doc["partners"]:
                partner_block(doc, p)

    def partner_block(doc: dict, p: dict):
        pb = mus.payback(doc, rs)
        sub = pb[pb["partner_id"] == p["id"]]
        modal = float(sub["harga"].sum()) if not sub.empty else 0.0
        kembali = float(sub["kembali"].sum()) if not sub.empty else 0.0
        prog = (kembali / modal * 100) if modal else 0.0
        title = (f'{p.get("name")} · {len(p.get("machines", []))} mesin · {_rp(modal)} '
                 f'· balik modal {prog:.0f}%')
        with ui.expansion(title).classes("w-full mb-2"):
            with ui.column().classes("w-full gap-2"):
                with ui.row().classes("w-full gap-2 items-end flex-wrap"):
                    nm = ui.input("Nama mitra", value=p.get("name") or "").props("dense outlined dark").classes("w-[200px]")
                    al = ui.input("Alias (pisah koma)", value=", ".join(p.get("aliases") or [])).props(
                        "dense outlined dark").classes("w-[260px]")
                    ui.button("Simpan mitra", on_click=lambda: save_partner(doc, p, nm, al)).props(
                        "dense unelevated color=primary")
                    ui.button("+ Mesin", on_click=lambda: add_machine(doc, p)).props("dense outline color=amber")
                    ui.button("Hapus mitra", on_click=lambda: del_partner(doc, p)).props("dense flat color=red")

                if p.get("no_tx"):
                    ui.html('<div class="us-meta">Lokasi tercatat tapi tanpa transaksi: '
                            + ", ".join(f"<span class='us-chip'>{x}</span>" for x in p["no_tx"]) + "</div>",
                            sanitize=False)

                for m in p.get("machines", []):
                    machine_row(doc, p, m)

    def machine_row(doc: dict, p: dict, m: dict):
        chain = " → ".join(pl["outlet"] for pl in mus.placements(m)) or "belum ditempatkan"
        pb = mus.payback(doc, rs)
        row = pb[pb["machine_id"] == m["id"]]
        r = row.iloc[0] if not row.empty else None
        with ui.card().classes("w-full").style(
                "background:#15151d;border:1px solid " + C_LINE + ";border-radius:12px;padding:10px"):
            ui.html(f'<div class="us-meta"><b style="color:{C_TXT}">{m.get("id")} · {m.get("label")}</b>'
                    f' — {chain}</div>', sanitize=False)
            if r is not None:
                tone = C_MINT if r["progress"] >= 100 else C_AMBER
                ui.html(f'<div class="us-meta" style="margin-top:2px">Kembali {_rp(r["kembali"])} dari '
                        f'{_rp(r["harga"])} · <b style="color:{tone}">{r["progress"]:.0f}%</b>'
                        f' · payout/bln {_rp(r["per_bulan"])} · pindah {int(r["pindah"])}×</div>',
                        sanitize=False)
            with ui.row().classes("w-full gap-2 flex-wrap mt-1"):
                lab = ui.input("Label", value=m.get("label") or "").props("dense outlined dark").classes("w-[150px]")
                harga = ui.number("Harga jual", value=mus._num(m.get("harga")),
                                  format="%.0f").props("dense outlined dark").classes("w-[150px]")
                hpp = ui.number("HPP (opsional)", value=(m.get("hpp") if m.get("hpp") not in (None, "") else None),
                                format="%.0f").props("dense outlined dark").classes("w-[150px]")
                beli = ui.input("Tgl beli (YYYY-MM-DD)", value=m.get("tgl_beli") or "").props(
                    "dense outlined dark").classes("w-[170px]")
                st = ui.select(mus.STATUS, value=m.get("status") or "aktif", label="Status").props(
                    "dense outlined dark").classes("w-[120px]")
                ui.button("Simpan", on_click=lambda: save_machine(doc, m, lab, harga, hpp, beli, st)).props(
                    "dense unelevated color=primary")
            with ui.row().classes("w-full gap-2 items-end flex-wrap"):
                dest = ui.select(names, value=None, label="Pindah ke", with_input=True).props(
                    "dense outlined dark").classes("w-[260px]")
                mo = ui.select(months, value=months[-1] if months else None, label="Mulai bulan").props(
                    "dense outlined dark").classes("w-[140px]")
                ui.button("Pindahkan", on_click=lambda: do_move(doc, m, dest, mo)).props("dense outline color=amber")
                ui.button("Riwayat", on_click=lambda: history(m)).props("dense flat color=grey")

    # ── aksi ──────────────────────────────────────────────────────────────
    def save_partner(doc, p, nm, al):
        p["name"] = (nm.value or "").strip()
        p["aliases"] = [a.strip() for a in (al.value or "").split(",") if a.strip()]
        mus.save(doc)
        ui.notify("Mitra disimpan", type="positive")
        refresh()

    def save_machine(doc, m, lab, harga, hpp, beli, st):
        m["label"] = (lab.value or "").strip()
        m["harga"] = mus._num(harga.value)
        m["hpp"] = mus._num(hpp.value, None) if hpp.value not in (None, "") else None
        tgl = (beli.value or "").strip()
        if tgl and not re.match(r"^\d{4}-\d{2}-\d{2}$", tgl):
            ui.notify("Tgl beli harus YYYY-MM-DD", type="warning")
            return
        m["tgl_beli"] = tgl or None
        m["status"] = st.value or "aktif"
        mus.save(doc)
        ui.notify(f'{m["id"]} disimpan', type="positive")
        refresh()

    def do_move(doc, m, dest, mo):
        if not dest.value or not mo.value:
            ui.notify("Pilih outlet & bulan", type="warning")
            return
        mus.move_machine(m, dest.value, mo.value)
        mus.save(doc)
        ui.notify(f'{m["id"]} pindah ke {dest.value} mulai {mo.value}', type="positive")
        refresh()

    def history(m):
        with ui.dialog() as dlg, ui.card().style(
                "background:" + C_PANEL + ";border:1px solid " + C_LINE + ";min-width:340px"):
            ui.label(f'Riwayat {m.get("id")}').classes("text-sm font-bold")
            rows = "".join(
                f'<div class="us-meta" style="margin:3px 0">{pl.get("outlet")} · '
                f'{pl.get("start") or "?"} → {pl.get("end") or "sekarang"}'
                f'{" · dari transaksi" if pl.get("derived") else " · manual"}</div>'
                for pl in mus.placements(m)
            ) or '<div class="us-meta">Belum ada penempatan.</div>'
            ui.html(rows, sanitize=False)
            ui.button("Tutup", on_click=dlg.close).props("flat dense")
        dlg.open()

    def add_partner(doc):
        with ui.dialog() as dlg, ui.card().style(
                "background:" + C_PANEL + ";border:1px solid " + C_LINE + ";min-width:340px"):
            ui.label("Tambah mitra").classes("text-sm font-bold")
            nm = ui.input("Nama mitra").props("dense outlined dark").classes("w-full")
            al = ui.input("Alias (pisah koma)").props("dense outlined dark").classes("w-full")

            def commit():
                if not (nm.value or "").strip():
                    ui.notify("Nama wajib", type="warning")
                    return
                doc["partners"].append({
                    "id": mus.next_id(doc, "P", doc["partners"]),
                    "name": nm.value.strip(),
                    "aliases": [a.strip() for a in (al.value or "").split(",") if a.strip()],
                    "machines": [],
                    "no_tx": [],
                })
                mus.save(doc)
                dlg.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Batal", on_click=dlg.close).props("flat dense")
                ui.button("Simpan", on_click=commit).props("dense unelevated color=primary")
        dlg.open()

    def add_machine(doc, p):
        p.setdefault("machines", []).append({
            "id": mus.next_machine_id(doc),
            "label": f'Mesin {len(p.get("machines", [])) + 1}',
            "harga": 0,
            "hpp": None,
            "tgl_beli": None,
            "status": "aktif",
            "placements": [],
        })
        mus.save(doc)
        refresh()

    def del_partner(doc, p):
        doc["partners"] = [x for x in doc["partners"] if x["id"] != p["id"]]
        mus.save(doc)
        ui.notify(f'{p.get("name")} dihapus', type="warning")
        refresh()

    def rederive(doc):
        """Hitung ulang semua penempatan dari transaksi (menimpa koreksi manual)."""
        with ui.dialog() as dlg, ui.card().style(
                "background:" + C_PANEL + ";border:1px solid " + C_LINE + ";min-width:340px"):
            ui.label("Hitung ulang lokasi dari transaksi?").classes("text-sm font-bold")
            ui.html('<div class="us-meta">Semua riwayat yang diisi manual akan ditimpa. '
                    "Harga, HPP, tanggal beli, dan nama mitra tetap.</div>", sanitize=False)

            def commit():
                fresh = mus.seed(rs, daily, sharing, outlets)
                for p in doc["partners"]:
                    match = next((f for f in fresh["partners"] if f["name"].lower() == p["name"].lower()), None)
                    if match:
                        p["machines"] = match["machines"]
                        p["no_tx"] = match["no_tx"]
                mus.save(doc)
                dlg.close()
                ui.notify("Lokasi dihitung ulang dari transaksi", type="positive")
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Batal", on_click=dlg.close).props("flat dense")
                ui.button("Hitung ulang", on_click=commit).props("dense unelevated color=amber")
        dlg.open()

    refresh()
