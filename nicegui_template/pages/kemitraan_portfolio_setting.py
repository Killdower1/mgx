"""Admin: investment per partner and confirmation of historical outlet candidates."""
from __future__ import annotations

import json
from pathlib import Path

from nicegui import ui
from services import mitra_portfolio as portfolio

ROOT = Path(__file__).resolve().parents[2]
RS = ROOT / 'streamlit_template/data/api_cache/rs_outlet.json'


def rp(v):
    return 'Rp ' + f'{float(v or 0):,.0f}'.replace(',', '.')


def create_page(container):
    rs = json.loads(RS.read_text())
    months = sorted({str(r['periode']) for r in rs})
    outlet_names = sorted({r['outlet_name'] for r in rs if r.get('outlet_name')})
    month = months[-1]
    # Keep accordion instances alive while outlet statuses change in place.
    views = {}
    with container:
        ui.label('⚙️ Modal & Outlet Mitra').classes('text-xl font-bold')
        ui.label('Isi modal yang benar-benar dibeli mitra. Cocokkan seluruh lokasi lama dan baru ke mitra; tidak perlu menebak identitas mesin.').classes('text-xs text-gray-400')
        ui.label('Data outlet dari model mesin lama hanya USULAN. Harga lama tidak disalin sebagai modal. Arsip lama tetap disimpan.').classes('text-xs text-amber-400')
        header = ui.column().classes('w-full')
        body = ui.column().classes('w-full')

    def persist(doc, message):
        portfolio.save(doc)
        ui.notify(message, type='positive')
        refresh()

    def add_owner():
        with ui.dialog() as dlg, ui.card().classes('w-full max-w-md'):
            ui.label('Tambah mitra').classes('font-bold')
            name = ui.input('Nama mitra').classes('w-full')
            aliases = ui.input('Alias (pisah koma)').classes('w-full')
            def commit():
                doc = portfolio.load()
                n = (name.value or '').strip()
                if not n or any(portfolio.key(p['name']) == portfolio.key(n) for p in doc['partners']):
                    ui.notify('Nama kosong atau sudah dipakai', type='warning'); return
                doc['partners'].append({'id': portfolio.next_id(doc['partners'], 'P'), 'name': n,
                    'aliases': [x.strip() for x in (aliases.value or '').split(',') if x.strip()],
                    'investments': [], 'outlets': []})
                dlg.close(); persist(doc, 'Mitra ditambahkan')
            ui.button('Simpan', on_click=commit)
        dlg.open()

    def edit_owner(pid):
        doc = portfolio.load(); owner = next(p for p in doc['partners'] if p['id'] == pid)
        with ui.dialog() as dlg, ui.card().classes('w-full max-w-md'):
            ui.label('Identitas mitra').classes('font-bold')
            name = ui.input('Nama kanon', value=owner['name']).classes('w-full')
            aliases = ui.input('Alias (pisah koma)', value=', '.join(owner.get('aliases', []))).classes('w-full')
            def commit():
                n = (name.value or '').strip()
                if not n:
                    ui.notify('Nama wajib diisi', type='warning'); return
                owner['name'] = n
                owner['aliases'] = [a.strip() for a in (aliases.value or '').split(',') if a.strip()]
                dlg.close(); persist(doc, 'Identitas disimpan')
            ui.button('Simpan', on_click=commit)
        dlg.open()

    def edit_investment(pid, inv_id=None):
        doc = portfolio.load(); owner = next(p for p in doc['partners'] if p['id'] == pid)
        inv = next((v for v in owner['investments'] if v['id'] == inv_id), None)
        with ui.dialog() as dlg, ui.card().classes('w-full max-w-md'):
            ui.label('Modal yang dibeli mitra').classes('font-bold')
            amount = ui.number('Nominal (Rp)', value=inv.get('amount') if inv else None, min=1, format='%.0f').classes('w-full')
            purchased = ui.input('Tanggal beli (YYYY-MM-DD)', value=inv.get('date') if inv else '').classes('w-full')
            note = ui.input('Keterangan (opsional)', value=inv.get('note') if inv else '').classes('w-full')
            def commit():
                try:
                    portfolio.validate_investment(amount.value, purchased.value)
                except ValueError as exc:
                    ui.notify(str(exc), type='warning'); return
                entry = inv if inv is not None else {'id': portfolio.next_id(owner['investments'], 'I')}
                entry.update({'amount': float(amount.value), 'date': purchased.value, 'note': (note.value or '').strip()})
                if inv is None:
                    owner['investments'].append(entry)
                dlg.close(); persist(doc, 'Modal disimpan')
            ui.button('Simpan modal', on_click=commit)
            if inv is not None:
                def remove():
                    owner['investments'].remove(inv)
                    dlg.close(); persist(doc, 'Catatan modal dihapus')
                ui.button('Hapus catatan ini', on_click=remove).props('outline color=red')
        dlg.open()

    def set_outlet(pid, name, state):
        doc = portfolio.load(); owner = next(p for p in doc['partners'] if p['id'] == pid)
        target = next((o for o in owner['outlets'] if portfolio.key(o['name']) == portfolio.key(name)), None)
        if target is None:
            owner['outlets'].append({'name': name, 'state': state})
        else:
            target['state'] = state
        portfolio.save(doc)
        update_outlet_views()
        ui.notify(f'{name}: {state}', type='positive')

    def add_outlet(pid, picker):
        name = (picker.value or '').strip()
        if not name:
            ui.notify('Pilih outlet', type='warning'); return
        doc = portfolio.load(); owner = next(p for p in doc['partners'] if p['id'] == pid)
        if any(portfolio.key(o['name']) == portfolio.key(name) for o in owner['outlets']):
            ui.notify('Sudah ada di daftar mitra', type='warning'); return
        owner['outlets'].append({'name': name, 'state': 'candidate'})
        persist(doc, 'Outlet masuk usulan; konfirmasi untuk menghitung hasilnya')

    def outlet_actions(pid, outlet, status_label, actions):
        """Replace only the controls of this row, never its parent expansion."""
        state, name = outlet['state'], outlet['outlet']
        status_label.text = 'KONFLIK' if outlet['conflict'] else state.upper()
        actions.clear()
        with actions:
            if state != 'confirmed':
                ui.button('Milik mitra', on_click=lambda p=pid, n=name: set_outlet(p, n, 'confirmed')).props('dense outline color=positive size=sm')
            if state != 'excluded':
                ui.button('Bukan milik mitra', on_click=lambda p=pid, n=name: set_outlet(p, n, 'excluded')).props('dense flat color=grey size=sm')

    def update_outlet_views():
        """Refresh labels and button states without clearing the page or losing scroll."""
        doc = portfolio.load()
        summaries = {s['id']: s for s in portfolio.reconcile(doc, rs, month)}
        for owner in doc['partners']:
            view = views.get(owner['id'])
            if view is None:
                continue
            summary = summaries[owner['id']]
            confirmed = sum(o['state'] == 'confirmed' for o in summary['outlets'])
            view['expansion'].text = (
                f"{owner['name']} · modal {rp(summary['capital'])} · "
                f"{confirmed}/{len(summary['outlets'])} outlet dikonfirmasi"
            )
            view['returned'].text = 'Hasil kemitraan tercatat: ' + rp(summary['returned'])
            view['progress'].text = 'Progres: ' + (
                f"{summary['progress']:.1f}%" if summary['progress'] is not None else 'modal belum diisi'
            )
            view['pending'].text = (
                'Potensi hasil dari outlet usulan: ' + rp(summary['pending']) +
                ' (belum masuk balik modal).' if summary['pending'] else ''
            )
            view['conflicts'].text = (
                f"{summary['conflicts']} outlet terkonfirmasi ke >1 mitra: hasilnya DITAHAN sampai konflik selesai."
                if summary['conflicts'] else ''
            )
            for outlet in summary['outlets']:
                row = view['rows'].get(portfolio.key(outlet['outlet']))
                if row is not None:
                    outlet_actions(owner['id'], outlet, row[0], row[1])

    def owner_card(owner, summary):
        n_confirmed = sum(o['state'] == 'confirmed' for o in summary['outlets'])
        title = f"{owner['name']} · modal {rp(summary['capital'])} · {n_confirmed}/{len(summary['outlets'])} outlet dikonfirmasi"
        with ui.expansion(title, value=portfolio.key(owner['name']) == 'widi official').classes('w-full').style('background:#1a1a24;border:1px solid #333;border-radius:12px') as expansion:
            view = {'expansion': expansion, 'rows': {}}
            views[owner['id']] = view
            ui.label('Alias: ' + ', '.join(owner.get('aliases', []))).classes('text-xs text-gray-400')
            ui.button('Edit nama / alias', on_click=lambda p=owner['id']: edit_owner(p)).props('dense flat')
            with ui.row().classes('w-full gap-3 flex-wrap'):
                ui.label('Modal: ' + rp(summary['capital'])).classes('font-bold')
                view['returned'] = ui.label('Hasil kemitraan tercatat: ' + rp(summary['returned'])).classes('font-bold')
                view['progress'] = ui.label('Progres: ' + (f"{summary['progress']:.1f}%" if summary['progress'] is not None else 'modal belum diisi')).classes('font-bold')
            ui.label('Hanya outlet terkonfirmasi dihitung. Angka hasil ≠ bukti uang sudah ditransfer.').classes('text-xs text-gray-400')
            ui.separator()
            with ui.row().classes('items-center'):
                ui.label('Pembelian / tambahan modal').classes('font-bold')
                ui.button('+ Catat modal', on_click=lambda p=owner['id']: edit_investment(p)).props('dense outline color=primary')
            if not owner.get('investments'):
                ui.label('Belum ada modal terkonfirmasi; harga outlet lama tidak otomatis menjadi modal.').classes('text-xs text-amber-400')
            for inv in sorted(owner.get('investments', []), key=lambda i: i['date']):
                with ui.row().classes('items-center gap-3'):
                    ui.label(f"{inv['date']} · {rp(inv['amount'])} · {inv.get('note') or '—'}").classes('text-sm')
                    ui.button('Edit', on_click=lambda p=owner['id'], i=inv['id']: edit_investment(p, i)).props('dense flat')
            ui.separator()
            ui.label('Adu lokasi dengan data transaksi').classes('font-bold')
            ui.label('Tanggal pertama/terakhir = transaksi teramati, BUKAN tanggal perpindahan mesin.').classes('text-xs text-gray-400')
            view['conflicts'] = ui.label(
                f"{summary['conflicts']} outlet terkonfirmasi ke >1 mitra: hasilnya DITAHAN sampai konflik selesai."
                if summary['conflicts'] else ''
            ).classes('text-xs text-red-400')
            view['pending'] = ui.label(
                'Potensi hasil dari outlet usulan: ' + rp(summary['pending']) + ' (belum masuk balik modal).'
                if summary['pending'] else ''
            ).classes('text-xs text-amber-400')
            for outlet in summary['outlets']:
                outlet['state']; name = outlet['outlet']
                with ui.row().classes('w-full items-center gap-2 flex-wrap py-1').style('border-bottom:1px solid #30303a'):
                    ui.label(name).classes('w-52 text-sm font-medium')
                    ui.label(f"{outlet['first']}—{outlet['last']}").classes('w-32 text-xs text-gray-400')
                    ui.label(rp(outlet['observed'])).classes('w-28 text-xs')
                    status_label = ui.label().classes('w-20 text-xs')
                    actions = ui.row().classes('items-center gap-2')
                    view['rows'][portfolio.key(name)] = (status_label, actions)
                    outlet_actions(owner['id'], outlet, status_label, actions)
            with ui.row().classes('items-center gap-2 mt-2 flex-wrap'):
                picker = ui.select(outlet_names, with_input=True, label='Cari outlet lain').props('dense outlined dark').classes('w-64')
                ui.button('+ Tambah usulan', on_click=lambda p=owner['id'], c=picker: add_outlet(p,c)).props('dense outline')

    def refresh():
        doc = portfolio.load()
        summaries = {s['id']: s for s in portfolio.reconcile(doc, rs, month)}
        header.clear(); body.clear()
        with header:
            with ui.row().classes('w-full items-center gap-3 mt-2'):
                ui.label(f"{len(doc['partners'])} mitra · {sum(len(p.get('investments', [])) for p in doc['partners'])} catatan modal").classes('text-sm')
                ui.button('+ Mitra', on_click=add_owner).props('dense unelevated color=primary')
        with body:
            for owner in doc['partners']:
                owner_card(owner, summaries[owner['id']])
    refresh()
