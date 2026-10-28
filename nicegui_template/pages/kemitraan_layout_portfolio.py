"""Old Kemitraan visual language with the confirmed investor-portfolio ledger.

No machine prices, placements, or ownership are inferred on this page.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
from nicegui import ui
from plotly import graph_objects as go

from pages.kemitraan_v2 import (_css, lbl_month, pct, rp_short, C_AMBER, C_BLUE,
                                 C_MINT, C_MUT, C_TXT, C_VIOLET)
from services import mitra_portfolio as portfolio

RS = Path(__file__).resolve().parents[2] / 'streamlit_template/data/api_cache/rs_outlet.json'


def _h(value):
    return html.escape(str(value), quote=True)


def _card(label, value, sub, color=C_TXT):
    return ('<div class="km-kpi"><div class="l">' + _h(label) + '</div>'
            '<div class="v" style="color:' + color + '">' + _h(value) + '</div>'
            '<div class="s">' + _h(sub) + '</div></div>')


def _table(headers, rows, empty):
    head = ''.join('<th>' + _h(label) + '</th>' for label in headers)
    if not rows:
        rows = ['<tr><td colspan="' + str(len(headers)) + '" style="color:' + C_MUT + '">' + _h(empty) + '</td></tr>']
    return '<div style="overflow:auto"><table class="km-table"><thead><tr>' + head + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def build(month, rs, doc):
    """Compute every investor figure from the same reconciliation as /kemitraan."""
    owners = portfolio.reconcile(doc, rs, month)
    accepted = {portfolio.key(o['outlet']) for s in owners for o in s['outlets']
                if o['state'] == 'confirmed' and not o['conflict']}
    # Preserve the old monthly/trend visual, but only for explicitly confirmed outlets.
    subset = [r for r in rs if portfolio.key(r.get('outlet_name')) in accepted and r.get('periode', '') <= month]
    current = [r for r in subset if r.get('periode') == month]
    sums = {name: sum(portfolio.money(r.get(name)) for r in current)
            for name in ('total_revenue', 'partner_amount', 'broker_amount', 'difotoin_amount')}
    capital = sum(s['capital'] for s in owners)
    returned = sum(s['returned'] for s in owners)
    pending = sum(s['pending'] for s in owners)
    confirmed = sum(o['state'] == 'confirmed' and not o['conflict'] for s in owners for o in s['outlets'])
    conflicts = sum(s['conflicts'] for s in owners)
    return dict(owners=owners, accepted=accepted, subset=subset, current=current,
                sums=sums, capital=capital, returned=returned, pending=pending,
                confirmed=confirmed, conflicts=conflicts, month=month,
                unassigned=len(doc.get('unassigned_outlets', [])))


def create_page(container):
    ui.add_head_html('<style>' + _css() + '</style>')
    try:
        rs = json.loads(RS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        rs = []
    months = sorted({r['periode'] for r in rs if r.get('periode')})
    with container:
        if not months:
            ui.label('Cache transaksi belum tersedia.').classes('text-red-400')
            return
        ui.html('<div style="font-size:19px;font-weight:750;letter-spacing:-.02em">🤝 Kemitraan</div>'
                '<div style="font-size:11.5px;color:' + C_MUT + '">Modal mitra, bagi hasil, dan balik modal — dihitung dari transaksi aktual.</div>',
                sanitize=False)
        with ui.row().classes('w-full items-center gap-3 mt-2 mb-1'):
            selector = ui.select({m: lbl_month(m) for m in months[::-1]}, value=months[-1], label='Bulan').props('dense outlined dark').classes('w-[150px]')
            info = ui.label('').classes('text-xs').style('color:' + C_MUT)
            ui.link('⚙️ Kelola modal & outlet', '/kemitraan-setting').classes('text-blue-400 text-xs')
        body = ui.column().classes('w-full')

        def render():
            month = selector.value or months[-1]
            doc = portfolio.load()
            m = build(month, rs, doc)
            owners = m['owners']
            totals = m['sums']
            rev = totals['total_revenue']
            info.set_text(f"{lbl_month(month)} · {len({portfolio.key(r['outlet_name']) for r in m['current']})} outlet terkonfirmasi · {m['confirmed']} outlet cocok")
            body.clear()
            with body:
                cards = (
                    _card('Omzet kemitraan', rp_short(rev), 'Outlet terkonfirmasi · bulan dipilih') +
                    _card('Bagian Kemitraan', rp_short(totals['partner_amount']), 'Hak mitra dari transaksi bulan dipilih', C_VIOLET) +
                    _card('Bagian Difotoin', rp_short(totals['difotoin_amount']), 'Sebelum sewa · outlet terkonfirmasi', C_MINT) +
                    _card('Broker / tempat', rp_short(totals['broker_amount']), 'Bagi hasil tempat · bukan sewa tetap', C_AMBER) +
                    _card('Modal mitra', rp_short(m['capital']) if m['capital'] else 'Belum diisi',
                          f"{sum(s['entries'] for s in owners)} entri modal · {len(owners)} mitra", C_BLUE) +
                    _card('Balik modal', pct(m['returned'] / m['capital'] * 100) + '%' if m['capital'] else '—',
                          f"Hasil {rp_short(m['returned'])} · sisa {rp_short(max(0, m['capital'] - m['returned']))}" if m['capital'] else 'Isi modal di panel admin',
                          C_MINT if m['capital'] and m['returned'] >= m['capital'] else C_AMBER))
                ui.html('<div class="km-kpis">' + cards + '</div>', sanitize=False).classes('w-full')

                ui.html('<div class="km-sec">Pembagian omzet kemitraan · 13 bulan</div>'
                        '<div class="km-sub">Dalam Rp juta — hanya outlet yang sudah dikonfirmasi; sebelum sewa tetap.</div>', sanitize=False).classes('w-full')
                trend = pd.DataFrame(m['subset'])
                fig = go.Figure()
                if not trend.empty:
                    for name, label, color in [('partner_amount', 'Kemitraan', C_VIOLET),
                                               ('broker_amount', 'Broker (tempat)', C_AMBER),
                                               ('difotoin_amount', 'Difotoin', C_MINT)]:
                        trend[name] = pd.to_numeric(trend.get(name), errors='coerce').fillna(0)
                    trend = trend.groupby('periode')[['partner_amount', 'broker_amount', 'difotoin_amount']].sum()
                    all_months = [p for p in months if p <= month][-13:]
                    trend = trend.reindex(all_months, fill_value=0)
                    for name, label, color in [('partner_amount', 'Kemitraan', C_VIOLET),
                                               ('broker_amount', 'Broker (tempat)', C_AMBER),
                                               ('difotoin_amount', 'Difotoin', C_MINT)]:
                        fig.add_bar(x=[lbl_month(p) for p in trend.index], y=trend[name] / 1e6,
                                    name=label, marker_color=color)
                fig.update_layout(template='plotly_dark', barmode='stack', height=280,
                                  margin=dict(l=6, r=6, t=6, b=6),
                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                  legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, font=dict(size=10)),
                                  yaxis=dict(gridcolor='#24242f', zeroline=False, tickfont=dict(size=10)))
                ui.plotly(fig).classes('w-full h-[280px]')

                ui.html('<div class="km-sec">Mitra & modalnya</div>'
                        '<div class="km-sub">Modal dari entri yang diinput; hasil dari hak mitra outlet terkonfirmasi sejak bulan pembelian pertama.</div>',
                        sanitize=False).classes('w-full')
                partner_rows = []
                for s in owners:
                    progress = s['progress']
                    width = min(100, max(0, progress or 0))
                    tone = C_MINT if progress is not None and progress >= 100 else C_AMBER
                    bar = ('<span class="km-bar"><i style="width:' + str(width) + '%;background:' + tone + '"></i></span>' if progress is not None else '—')
                    partner_rows.append('<tr><td><b>' + _h(s['name']) + '</b></td>'
                                        '<td>' + str(s['entries']) + '</td><td>' + str(sum(o['state'] == 'confirmed' and not o['conflict'] for o in s['outlets'])) + '</td>'
                                        '<td>' + _h(rp_short(s['capital']) if s['capital'] else 'Belum diisi') + '</td>'
                                        '<td>' + _h(rp_short(s['returned'])) + '</td><td>' + _h(rp_short(s['current'])) + '</td>'
                                        '<td style="min-width:110px">' + bar + '</td><td>' + (pct(progress) + '%' if progress is not None else '—') + '</td></tr>')
                ui.html(_table(['Mitra', 'Entri modal', 'Outlet cocok', 'Modal', 'Hasil', 'Bulan ini', 'Progres', '%'],
                               partner_rows, 'Belum ada mitra.'), sanitize=False).classes('w-full')

                ui.html('<div class="km-sec">Adu: outlet tercatat vs dikonfirmasi</div>'
                        '<div class="km-sub">Usulan tidak masuk hasil. Konflik kepemilikan ditahan dari seluruh hitungan.</div>', sanitize=False).classes('w-full')
                audit_rows = []
                for s in owners:
                    candidates = sum(o['state'] == 'candidate' for o in s['outlets'])
                    excluded = sum(o['state'] == 'excluded' for o in s['outlets'])
                    audit_rows.append('<tr><td><b>' + _h(s['name']) + '</b></td><td>' + str(len(s['outlets'])) + '</td>'
                                      '<td>' + str(sum(o['state'] == 'confirmed' and not o['conflict'] for o in s['outlets'])) + '</td>'
                                      '<td>' + str(candidates) + '</td><td>' + str(excluded) + '</td><td>' + str(s['conflicts']) + '</td>'
                                      '<td>' + _h(rp_short(s['pending'])) + '</td></tr>')
                ui.html(_table(['Mitra', 'Tercatat', 'Cocok', 'Usulan', 'Dikecualikan', 'Konflik', 'Potensi belum cocok'],
                               audit_rows, 'Belum ada outlet tercatat.'), sanitize=False).classes('w-full')

                ui.html('<div class="km-sec">Balik modal per mitra</div>'
                        '<div class="km-sub">Diurut dari yang paling jauh; tidak dipecah per mesin karena outlet belum dipetakan ke unit fisik.</div>',
                        sanitize=False).classes('w-full')
                pay_rows = []
                for s in sorted(owners, key=lambda x: (x['progress'] is None, x['progress'] or 0)):
                    progress = s['progress']
                    status = 'Modal belum diisi' if progress is None else ('Balik modal' if progress >= 100 else 'Berjalan')
                    pay_rows.append('<tr><td><b>' + _h(s['name']) + '</b></td><td>' + _h(rp_short(s['capital']) if s['capital'] else '—') + '</td>'
                                    '<td>' + _h(rp_short(s['returned'])) + '</td><td>' + _h(rp_short(s['remaining']) if s['remaining'] is not None else '—') + '</td>'
                                    '<td>' + (pct(progress) + '%' if progress is not None else '—') + '</td><td>' + _h(rp_short(s['current'])) + '</td>'
                                    '<td><span class="km-chip" style="color:' + (C_MINT if progress is not None and progress >= 100 else C_AMBER) + '">' + status + '</span></td></tr>')
                ui.html(_table(['Mitra', 'Modal', 'Hasil', 'Sisa', 'Progres', 'Bulan ini', 'Status'],
                               pay_rows, 'Belum ada mitra.'), sanitize=False).classes('w-full')

                ui.html('<div class="km-sec">Margin per outlet · ' + _h(lbl_month(month)) + '</div>'
                        '<div class="km-sub">15 outlet terkonfirmasi beromzet terbesar · bagian Difotoin sebelum sewa.</div>', sanitize=False).classes('w-full')
                outlet_rows = []
                for r in sorted(m['current'], key=lambda x: portfolio.money(x.get('total_revenue')), reverse=True)[:15]:
                    gross = portfolio.money(r.get('total_revenue'))
                    share = portfolio.money(r.get('partner_amount'))
                    company = portfolio.money(r.get('difotoin_amount'))
                    outlet_rows.append('<tr><td><b>' + _h(r.get('outlet_name', '')) + '</b></td>'
                                       '<td>' + _h(rp_short(gross)) + '</td><td>' + _h(rp_short(share)) + '</td>'
                                       '<td>' + _h(rp_short(company)) + '</td><td>' + (pct(share / gross * 100) if gross else '—') + '%</td></tr>')
                ui.html(_table(['Outlet', 'Omzet', 'Hak mitra', 'Difotoin', 'Mitra %'],
                               outlet_rows, 'Tidak ada outlet terkonfirmasi bertransaksi bulan ini.'), sanitize=False).classes('w-full')

                ui.html('<div class="km-sec">Yang perlu dilengkapi</div>'
                        '<div class="km-note">• Potensi hasil outlet usulan ' + _h(rp_short(m['pending'])) + ' — belum dihitung balik modal.<br>'
                        '• ' + str(m['unassigned']) + ' outlet baru belum ditentukan mitranya; ' + str(m['conflicts']) + ' konflik kepemilikan ditahan.<br>'
                        '• Hasil adalah hak mitra dalam transaksi, bukan bukti transfer. Cakupan ledger mulai ' + _h(months[0]) + '; bulan kosong tidak diimputasi.<br>'
                        '• Perhitungan pembelian dimulai awal bulan tanggal beli. Sewa tetap dan HPP mesin tidak dimasukkan.</div>',
                        sanitize=False).classes('w-full')
                ui.html('<div class="km-note" style="margin-top:10px">Sumber: rs_outlet.json · mitra_portfolio.json. '
                        '<a href="/kemitraan-setting" style="color:#5b8cff">Kelola modal & outlet</a> · '
                        '<a href="/kemitraan-mesin-arsip" style="color:#5b8cff">Arsip tampilan & data mesin lama</a></div>',
                        sanitize=False).classes('w-full')

        selector.on('change', lambda _: render())
        render()
