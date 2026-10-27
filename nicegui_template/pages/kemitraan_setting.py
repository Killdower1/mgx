"""⚙️ Setting Unit Mesin Mitra.

Semua yang berhubungan dengan investasi dicatat di sini, bukan di outlet:
- mitra pemilik, harga jual mesin ke mitra, modal/HPP Difotoin, tanggal beli
- lokasi sekarang + riwayat pindah (mesin boleh pindah, modalnya tetap)

Dipakai oleh halaman /kemitraan untuk menghitung balik modal per mesin.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from nicegui import ui

from services import unit_mesin_store as store

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "streamlit_template" / "data" / "api_cache"

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


def _outlet_names() -> list[str]:
    outlets = pd.DataFrame(_read(CACHE / "outlets.json", []))
    if outlets.empty or "name" not in outlets.columns:
        return []
    return sorted({str(n).strip() for n in outlets["name"].dropna() if str(n).strip()})


def _months() -> list[str]:
    rs = pd.DataFrame(_read(CACHE / "rs_outlet.json", []))
    if rs.empty or "periode" not in rs.columns:
        return []
    return sorted({str(p) for p in rs["periode"].dropna()})


def _css() -> str:
    return """
  .us-wrap { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; padding: 10px 14px; }
  .us-meta { font-size: 11px; color: @MUT@; }
  .us-h { font-size: 12.5px; font-weight: 700; }
  .q-expansion-item { background: @PANEL@; border: 1px solid @LINE@; border-radius: 14px; }
""".replace("@PANEL@", C_PANEL).replace("@LINE@", C_LINE).replace("@MUT@", C_MUT)


def create_page(container: ui.column):
    ui.add_head_html("<style>" + _css() + "</style>")
    months = _months()
    outlet_names = _outlet_names()

    with container:
        ui.html(
            '<div style="font-size:19px;font-weight:750;letter-spacing:-.02em">⚙️ Setting Unit Mesin</div>'
            '<div style="font-size:11.5px;color:' + C_MUT + '">Modal nempel di mesin, bukan di outlet. '
            "Kalau mesin pindah tempat, riwayatnya tetap di sini.</div>",
            sanitize=False,
        )

        head = ui.row().classes("w-full items-center gap-2 mt-2 mb-1")
        body = ui.column().classes("w-full")

    def current_doc() -> dict:
        outlets = pd.DataFrame(_read(CACHE / "outlets.json", []))
        sharing = pd.DataFrame([])
        try:
            files = sorted(Path(CACHE).parent.joinpath("sharing_outlets").glob("*.json"))
            if files:
                sharing = pd.DataFrame(_read(files[-1], []))
        except Exception:
            pass
        return store.ensure_doc(outlets, sharing, months[0] if months else None)

    def refresh():
        doc = current_doc()
        head.clear()
        body.clear()
        total_jual = sum(store._num(u.get("harga_jual")) for u in doc["units"])
        priced = sum(1 for u in doc["units"] if store._num(u.get("modal"), None) not in (None, 0))
        with head:
            ui.html(
                f'<div class="us-meta"><b style="color:{C_TXT}">{len(doc["units"])} unit</b> · '
                f'harga jual {_rp(total_jual)} · modal/HPP terisi {priced}/{len(doc["units"])}</div>',
                sanitize=False,
            ).classes("w-full")
            ui.button("+ Tambah unit", on_click=lambda: add_unit(doc)).props("dense unelevated color=primary")

        with body:
            if not doc["units"]:
                ui.label("Belum ada unit. Klik “Tambah unit”.").classes("text-gray-400 italic")
                return
            for u in sorted(doc["units"], key=lambda x: str(x.get("id"))):
                unit_block(doc, u)

    def unit_block(doc: dict, u: dict):
        cur = store.current_placement(u) or {}
        title = (
            f'{u.get("id")} · {u.get("label") or "tanpa nama"} · {u.get("mitra") or "tanpa mitra"} '
            f'· {cur.get("outlet") or "belum ditempatkan"} · {_rp(u.get("harga_jual"))}'
        )
        with ui.expansion(title).classes("w-full mb-2"):
            with ui.column().classes("w-full gap-2"):
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    label = ui.input("Label mesin", value=u.get("label") or "").props("dense outlined dark").classes("w-[260px]")
                    mitra = ui.input("Mitra pemilik", value=u.get("mitra") or "").props("dense outlined dark").classes("w-[200px]")
                    own = ui.select(
                        {"kemitraan": "Kemitraan (milik mitra)", "difotoin": "Milik Difotoin"},
                        value=u.get("ownership") or "kemitraan", label="Kepemilikan",
                    ).props("dense outlined dark").classes("w-[220px]")
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    jual = ui.number("Harga jual ke mitra", value=store._num(u.get("harga_jual")),
                                     format="%.0f").props("dense outlined dark").classes("w-[190px]")
                    modal = ui.number("Modal / HPP Difotoin", value=(u.get("modal") if u.get("modal") not in (None, "") else None),
                                      format="%.0f").props("dense outlined dark").classes("w-[190px]")
                    beli = ui.input("Tgl beli (YYYY-MM-DD)", value=u.get("tgl_beli") or "").props("dense outlined dark").classes("w-[190px]")
                    st = ui.select(store.STATUS, value=u.get("status") or "aktif", label="Status").props(
                        "dense outlined dark").classes("w-[130px]")

                with ui.row().classes("w-full items-center gap-3 mt-1"):
                    ui.html(
                        '<div class="us-meta">Lokasi sekarang: <b style="color:' + C_TXT + '">'
                        + str(cur.get("outlet") or "—") + "</b> · mulai " + str(cur.get("start") or "—")
                        + " · pindah " + str(store.move_count(u)) + "×</div>", sanitize=False)

                with ui.row().classes("w-full gap-2 items-end flex-wrap mt-1"):
                    new_outlet = ui.select(outlet_names, value=None, label="Pindah ke outlet",
                                           with_input=True).props("dense outlined dark").classes("w-[300px]")
                    new_month = ui.select(months, value=months[-1] if months else None,
                                          label="Efektif bulan").props("dense outlined dark").classes("w-[150px]")
                    ui.button("Pindahkan", on_click=lambda: do_move(doc, u, new_outlet.value, new_month.value)) \
                        .props("dense outline color=amber")
                    ui.button("Simpan", on_click=lambda: save_unit(doc, u, label, mitra, own, jual, modal, beli, st)) \
                        .props("dense unelevated color=primary")
                    ui.button("Riwayat", on_click=lambda: show_history(u)).props("dense flat color=grey")

    def save_unit(doc, u, label, mitra, own, jual, modal, beli, st):
        u["label"] = (label.value or "").strip()
        u["mitra"] = (mitra.value or "").strip()
        u["ownership"] = own.value or "kemitraan"
        u["harga_jual"] = store._num(jual.value)
        u["modal"] = store._num(modal.value, None) if modal.value not in (None, "") else None
        u["tgl_beli"] = (beli.value or "").strip() or None
        u["status"] = st.value or "aktif"
        if u["tgl_beli"] and not re.match(r"^\d{4}-\d{2}-\d{2}$", u["tgl_beli"]):
            ui.notify("Tgl beli harus YYYY-MM-DD", type="warning")
            return
        store.save(doc)
        ui.notify(f'{u["id"]} disimpan', type="positive")
        refresh()

    def do_move(doc, u, outlet, month):
        if not outlet or not month:
            ui.notify("Pilih outlet dan bulan efektif", type="warning")
            return
        cur = store.current_placement(u) or {}
        if str(cur.get("outlet") or "").strip().lower() == str(outlet).strip().lower():
            ui.notify("Mesin sudah di outlet itu", type="warning")
            return
        store.move_unit(u, outlet, month)
        store.save(doc)
        ui.notify(f'{u["id"]} pindah ke {outlet} mulai {month}', type="positive")
        refresh()

    def show_history(u):
        with ui.dialog(), ui.card().style(
                "background:" + C_PANEL + ";border:1px solid " + C_LINE + ";min-width:320px"):
            ui.label(f'Riwayat {u.get("id")}').classes("text-sm font-bold")
            rows = "".join(
                f'<div class="us-meta" style="margin:3px 0">{p.get("outlet")} · '
                f'{p.get("start") or "?"} → {p.get("end") or "sekarang"}</div>'
                for p in store.placements(u)
            ) or '<div class="us-meta">Belum ada penempatan.</div>'
            ui.html(rows, sanitize=False)
            ui.button("Tutup", on_click=d.close).props("flat dense")
        d.open()

    def add_unit(doc):
        with ui.dialog() as dlg, ui.card().style(
                "background:" + C_PANEL + ";border:1px solid " + C_LINE + ";min-width:340px"):
            ui.label("Tambah unit mesin").classes("text-sm font-bold")
            label = ui.input("Label / nama mesin").props("dense outlined dark").classes("w-full")
            mitra = ui.input("Mitra pemilik").props("dense outlined dark").classes("w-full")
            jual = ui.number("Harga jual ke mitra", value=0, format="%.0f").props("dense outlined dark").classes("w-full")
            modal = ui.number("Modal / HPP (opsional)", value=None, format="%.0f").props("dense outlined dark").classes("w-full")
            outlet = ui.select(outlet_names, value=None, label="Outlet sekarang", with_input=True).props(
                "dense outlined dark").classes("w-full")
            month = ui.select(months, value=months[-1] if months else None, label="Mulai bulan").props(
                "dense outlined dark").classes("w-full")

            def commit():
                if not (label.value or "").strip():
                    ui.notify("Label mesin wajib", type="warning")
                    return
                doc["units"].append({
                    "id": store.next_id(doc),
                    "label": (label.value or "").strip(),
                    "mitra": (mitra.value or "").strip(),
                    "ownership": "kemitraan",
                    "harga_jual": store._num(jual.value),
                    "modal": store._num(modal.value, None) if modal.value not in (None, "") else None,
                    "tgl_beli": None,
                    "status": "aktif",
                    "placements": ([{"outlet": outlet.value, "start": month.value, "end": None}]
                                   if outlet.value else []),
                })
                store.save(doc)
                dlg.close()
                ui.notify("Unit ditambahkan", type="positive")
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Batal", on_click=dlg.close).props("flat dense")
                ui.button("Simpan", on_click=commit).props("dense unelevated color=primary")
        dlg.open()

    refresh()
