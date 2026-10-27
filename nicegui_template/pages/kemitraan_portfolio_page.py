"""Kemitraan — invested capital versus actual owner share, without machine inference."""
from __future__ import annotations

import json
from pathlib import Path

from nicegui import ui
from services import mitra_portfolio as portfolio

RS = Path(__file__).resolve().parents[2] / 'streamlit_template/data/api_cache/rs_outlet.json'


def rp(v):
    a = float(v or 0)
    if abs(a) >= 1e9:
        return 'Rp ' + f'{a / 1e9:.2f}'.replace('.', ',') + ' M'
    if abs(a) >= 1e6:
        return 'Rp ' + f'{a / 1e6:.1f}'.replace('.', ',') + ' jt'
    return 'Rp ' + f'{a:,.0f}'.replace(',', '.')


def create_page(container):
    rs = json.loads(RS.read_text())
    months = sorted({r['periode'] for r in rs})
    if not months:
        with container:
            ui.label('Data transaksi belum tersedia.')
        return
    first_ledger = months[0]
    ui.add_head_html('<style>.km-invest-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;width:100%}@media(max-width:1100px){.km-invest-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.km-invest-grid{grid-template-columns:1fr}}</style>')
    with container:
        ui.label('🤝 Kemitraan').classes('text-xl font-bold')
        ui.label('Modal yang dicatat pemilik vs bagian kemitraan aktual dari outlet yang sudah dicocokkan. Tanpa asumsi jumlah atau perpindahan mesin.').classes('text-xs text-gray-400')
        with ui.row().classes('items-center gap-3 mt-3'):
            selector = ui.select({m: m for m in reversed(months)}, value=months[-1], label='Sampai bulan').props('dense outlined dark').classes('w-40')
            ui.link('⚙️ Kelola modal & outlet', '/kemitraan-setting').classes('text-blue-400 text-sm')
        content = ui.column().classes('w-full gap-4 mt-4')

    def card(label, value, sub, color='#edf0f7'):
        with ui.card().style('background:#1a1a24;border:1px solid #2d2d38;min-height:120px;min-width:0;width:100%'):
            ui.label(label).classes('text-xs uppercase text-gray-400')
            ui.label(value).classes('text-xl font-bold').style('color:'+color)
            ui.label(sub).classes('text-xs text-gray-400')

    def render():
        month = selector.value
        doc = portfolio.load()
        owners = portfolio.reconcile(doc, rs, month)
        capital = sum(s['capital'] for s in owners)
        returned = sum(s['returned'] for s in owners)
        pending = sum(s['pending'] for s in owners)
        confirmed = sum(sum(o['state'] == 'confirmed' and not o['conflict'] for o in s['outlets']) for s in owners)
        content.clear()
        with content:
            with ui.element('div').classes('km-invest-grid'):
                card('Modal tercatat', rp(capital), f"{sum(s['entries'] for s in owners)} pembelian · {len(owners)} mitra", '#5b8cff')
                card('Hasil kemitraan tercatat', rp(returned), f'{confirmed} outlet sudah cocok', '#a78bfa')
                card('Progres balik modal', f'{returned/capital*100:.1f}%' if capital else '—',
                     'Belum termasuk outlet usulan' if capital else 'Isi modal dulu', '#3ddc97')
                card('Hasil perlu dicocokkan', rp(pending), 'Historis sebelum modal diisi; belum masuk hitungan', '#f5b83d')
            ui.label('Hasil kemitraan adalah bagian mitra dari transaksi, bukan omzet bruto atau bukti transfer ke rekening.').classes('text-xs text-amber-400')
            ui.label(f'Data transaksi mulai {first_ledger}, namun mungkin ada bulan yang kosong di cache; hasil di luar cakupan tidak tercakup. Pembelian dalam suatu bulan dihitung sejak awal bulan itu.').classes('text-xs text-gray-400')
            ui.label('Balik modal per mitra').classes('font-bold mt-3')
            with ui.row().classes('w-full gap-3'):
                for s in owners:
                    with ui.card().classes('w-full col-md-5').style('background:#1a1a24;border:1px solid #2d2d38;border-radius:14px'):
                        ui.label(s['name']).classes('font-bold text-base')
                        aliases = [a for a in s['aliases'] if portfolio.key(a) != portfolio.key(s['name'])]
                        if aliases:
                            ui.label('Alias: '+', '.join(aliases)).classes('text-xs text-gray-400')
                        with ui.row().classes('w-full justify-between'):
                            ui.label('Modal '+rp(s['capital'])).classes('text-sm')
                            ui.label('Hasil '+rp(s['returned'])).classes('text-sm')
                        progress = s['progress']
                        if progress is not None:
                            ui.linear_progress(min(1, progress/100)).props('color=positive')
                            ui.label(f"{progress:.1f}% · sisa {rp(s['remaining'])} · bulan ini {rp(s['current'])}").classes('text-sm')
                        else:
                            ui.label('Modal belum diisi — progres belum bisa dihitung.').classes('text-xs text-amber-400')
                        if s['pending']:
                            ui.label('Belum dicocokkan: '+rp(s['pending'])).classes('text-xs text-amber-400')
                        if s['conflicts']:
                            ui.label(f"{s['conflicts']} outlet konflik kepemilikan, hasil ditahan").classes('text-xs text-red-400')
                        with ui.expansion('Rincian outlet & jejak transaksi').classes('w-full'):
                            for outlet in s['outlets']:
                                tag = {'confirmed':'✓ Cocok','candidate':'? Usulan','excluded':'× Dikecualikan'}.get(outlet['state'], '?')
                                if outlet['conflict']:
                                    tag = '! Konflik'
                                with ui.row().classes('w-full justify-between gap-2').style('border-bottom:1px solid #30303a'):
                                    ui.label(outlet['outlet']+' · '+tag).classes('text-xs')
                                    ui.label(rp(outlet['returned']) if s['first'] else rp(outlet['observed'])+' (historis; belum dialokasikan)').classes('text-xs')
                                ui.label(f"Transaksi teramati: {outlet['first']}—{outlet['last']}").classes('text-xs text-gray-400')
            ui.label('Rincian hasil bulanan outlet terkonfirmasi').classes('font-bold mt-3')
            for s in owners:
                accepted = {portfolio.key(o['outlet']) for o in s['outlets'] if o['state']=='confirmed' and not o['conflict']}
                rows = [r for r in rs if portfolio.key(r['outlet_name']) in accepted and
                        s['first'] and s['first'] <= r['periode'] <= month and float(r.get('partner_amount') or 0) > 0]
                if not rows:
                    continue
                with ui.expansion(f"{s['name']} · {len(rows)} catatan outlet-bulan").classes('w-full').style('background:#1a1a24'):
                    for r in sorted(rows, key=lambda x:(x['periode'],x['outlet_name']), reverse=True):
                        with ui.row().classes('w-full justify-between text-xs').style('border-bottom:1px solid #30303a'):
                            ui.label(f"{r['periode']} · {r['outlet_name']}")
                            ui.label(rp(r['partner_amount']))
    selector.on_value_change(lambda _: render())
    render()
