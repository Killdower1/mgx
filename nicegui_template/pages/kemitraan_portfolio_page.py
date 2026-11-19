"""Kemitraan machine-level entitlement and payback; no inferred ownership."""
from __future__ import annotations

import json
from pathlib import Path
from nicegui import ui
from services import mitra_portfolio as portfolio
from services import kemitraan_machine as ledger

RS = Path(__file__).resolve().parents[2] / 'streamlit_template/data/api_cache/rs_outlet.json'


def rp(value):
    return 'Rp ' + f'{float(value or 0):,.0f}'.replace(',', '.')


def create_page(container):
    cache, stale = ledger.read_cache()
    with container:
        ui.label('🤝 Kemitraan · Mesin Fisik').classes('text-xl font-bold')
        with ui.row().classes('items-center gap-4'):
            ui.link('⚙️ Konfirmasi mesin & input modal', '/kemitraan-setting').classes('text-blue-400')
            ui.link('Arsip perhitungan lama', '/kemitraan-mesin-arsip').classes('text-gray-400 text-xs')
        ui.label('Hasil = hak mitra dari transaksi lunas/selesai, bukan bukti transfer. Modal hanya harga aktual yang dikonfirmasi admin per mesin.').classes('text-xs text-amber-400')
        if not cache:
            ui.label('Cache penjualan mesin belum dibuat. Buka pengaturan lalu rebuild dari RAW.').classes('text-amber-400')
            return
        months = sorted(cache['periods'])
        if not months: return
        if stale:
            ui.label('Cache belum mutakhir; periode RAW berubah: '+', '.join(stale[:12])+' — rebuild di pengaturan. Angka di bawah dapat tertinggal.').classes('text-amber-400')
        selector = ui.select({m:m for m in reversed(months)}, value=months[-1], label='Sampai bulan').props('dense outlined dark').classes('w-48')
        content = ui.column().classes('w-full gap-4 mt-3')

    def render():
        month = selector.value
        doc = portfolio.load()
        rs = json.loads(RS.read_text(encoding='utf-8')) if RS.exists() else []
        view = ledger.reconcile(doc, cache, month, rs)
        machines = [m for o in view['owners'] for m in o['machines']]
        priced = [m for m in machines if not m['unpriced'] and not m['conflict']]
        capital = sum(m['amount'] for m in priced)
        earned = sum(m['entitlement'] for m in priced)
        untagged = view['untagged']
        content.clear()
        with content:
            ui.label(f"Modal mesin terkonfirmasi {rp(capital)} · hak mitra {rp(earned)} · progres {earned/capital*100:.1f}%" if capital else 'Belum ada harga mesin terkonfirmasi; progres belum dapat dihitung.').classes('font-bold')
            ui.label('Sisa modal '+rp(max(capital-earned,0)) if capital else 'Modal belum dicatat per mesin').classes('text-sm')
            ui.label(f"{len(machines)} mesin mitra dikonfirmasi · {len(priced)} bermodal dan bertanggal · {sum(m['progress'] >= 100 for m in priced)} balik modal · {sum(m['poor_sales'] for m in priced)} penjualan rendah").classes('text-sm')
            ui.label('Indikator rendah: hak mitra rata-rata 3 bulan < modal/12 per bulan; bulan berjalan parsial, jadi hanya sinyal awal.').classes('text-xs text-gray-400')
            ui.label(f"Cakupan RAW: {', '.join(view['covered_months'])}. Transaksi tanpa machine ID (terutama sebelum 2026-10-29) tidak dialokasikan ke mesin/mitra. Bulan tanpa RAW tidak dihitung.").classes('text-xs text-gray-400')
            if view['reconciliation_differences']:
                ui.label(f"⚠ {len(view['reconciliation_differences'])} outlet-bulan berbeda dari rs_outlet; angka perlu diaudit sebelum dipakai sebagai keputusan.").classes('text-amber-400')
                with ui.expansion('Selisih rekonsiliasi'):
                    for d in view['reconciliation_differences'][:100]:
                        ui.label(f"{d['period']} · {d['outlet']} · bruto Δ {rp(d['gross_delta'])} · hak Δ {rp(d['share_delta'])}").classes('text-xs')
            for owner in view['owners']:
                with ui.expansion(owner['name']+f" · {len(owner['machines'])} mesin", value=True).classes('w-full').style('background:#1a1a24'):
                    if not owner['machines']:
                        ui.label('Belum ada machine ID dikonfirmasi; outlet usulan tidak otomatis menjadi mesin.').classes('text-xs text-amber-400')
                    for m in sorted(owner['machines'], key=lambda x: (x['progress'] is None, x['progress'] if x['progress'] is not None else 0)):
                        with ui.card().classes('w-full').style('background:#222230;border:1px solid #393947'):
                            ui.label(m['machine_id']).classes('text-sm font-bold break-all')
                            if m['conflict']: ui.label('Konflik: ID ini dimiliki >1 mitra; hasil ditahan.').classes('text-red-400')
                            if m['unpriced']: ui.label('Harga/tanggal belum lengkap; dipisah dari progres modal.').classes('text-amber-400')
                            ui.label(f"Beli {m['date'] or '—'} · modal {rp(m['amount'])} · bruto teratribusi {rp(m['gross'])} · hak mitra {rp(m['entitlement'])}").classes('text-sm')
                            if m['progress'] is not None:
                                ui.linear_progress(min(1,m['progress']/100)).props('color=positive')
                                ui.label(f"Progres {m['progress']:.1f}% · sisa {rp(m['remaining'])} · run-rate 3 bulan {rp(m['run_rate'])}/bulan · estimasi sisa {m['months_to_payback']:.1f} bulan" if m['months_to_payback'] is not None else f"Progres {m['progress']:.1f}% · sisa {rp(m['remaining'])} · run-rate belum cukup untuk estimasi").classes('text-xs')
                                if m['poor_sales']: ui.label('Penjualan rendah: run-rate di bawah modal/12 per bulan (indikator, bukan janji balik modal).').classes('text-xs text-amber-400')
                            with ui.expansion('Jejak outlet/placement & hasil bulanan'):
                                for t in m['trail']:
                                    ui.label(f"{t['first']}–{t['last']} · placement {t['placement_id'] or 'tidak ada'} · {t['outlet']} · {t['transactions']} transaksi · hak {rp(t['entitlement'])}").classes('text-xs')
                                for p,a in sorted(m['monthly'].items()):
                                    ui.label(f'{p}: {rp(a)}').classes('text-xs')
            ui.label(f"Belum ditetapkan: {len(view['unassigned_ids'])} machine ID; tidak masuk hasil mitra.").classes('text-sm text-amber-400')
            if view['unassigned_ids']:
                with ui.expansion('ID mesin belum ditetapkan'):
                    for mid in view['unassigned_ids']:ui.label(mid).classes('text-xs break-all')
            ui.label(f"Tanpa machine ID: {sum(a[0] for a in untagged.values())} transaksi · bruto {rp(sum(a[1] for a in untagged.values()))} · bagian partner outlet {rp(sum(a[2] for a in untagged.values()))}; TIDAK dialokasikan.").classes('text-sm text-amber-400')
            with ui.expansion('Cakupan tanpa ID per bulan'):
                for p,a in sorted(untagged.items()): ui.label(f'{p}: {a[0]} transaksi · {rp(a[1])} bruto · {rp(a[2])} bagian outlet').classes('text-xs')
    selector.on_value_change(lambda _: render())
    render()
