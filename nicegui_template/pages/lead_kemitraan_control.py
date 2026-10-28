"""Read-only action dashboard for ERPNext Lead Kemitraan."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from nicegui import ui
from services.erpnext_adapter import load_lk_data, get_cache_info, filter_by_staff
from pages.login import get_current_email, get_current_name, get_current_role

JKT = ZoneInfo('Asia/Jakarta')
ERP = 'https://erp.midory.id/app/lead-kemitraan/'
TERMINAL = {'lost', 'cancelled', 'nurturing', 'active partner', 'live'}


def text(value):
    if value is None or pd.isna(value) if not isinstance(value, (list, dict)) else False:
        return ''
    s = str(value).strip()
    return '' if s.lower() in ('nan', 'nat', 'none') else s.encode('utf-8', 'replace').decode('utf-8')


def day(value):
    v = text(value)
    if not v:
        return None
    try:
        return datetime.fromisoformat(v[:10]).date()
    except ValueError:
        return None


def display_day(value):
    d = day(value)
    return d.strftime('%d %b %Y') if d else 'Belum tercatat'


def classify(row, today):
    status = text(row.get('status_lead')).lower()
    if status in TERMINAL:
        return 'Selesai / arsip'
    due = day(row.get('next_follow_up'))
    last = day(row.get('last_follow_up'))
    if due and due < today:
        return 'Terlambat'
    if due == today:
        return 'Hari ini'
    if not last:
        return 'Belum tercatat'
    if due:
        return 'Terjadwal'
    return 'Belum dijadwalkan'


def prepare(df, today):
    rows = []
    for _, record in df.iterrows():
        r = record.to_dict()
        state = classify(r, today)
        last = day(r.get('last_follow_up'))
        due = day(r.get('next_follow_up'))
        mod = text(r.get('modified'))
        label = text(r.get('nama_lengkap')) or text(r.get('lead_name')) or text(r.get('name'))
        rows.append({
            'ID': text(r.get('name')), 'Nama': label,
            'Kota': text(r.get('kota_penempatan_mesin')) or text(r.get('kota_domisili')) or '—',
            'Tahap': text(r.get('status_lead')) or 'Belum tercatat',
            'PIC': text(r.get('nama_sales_pic')) or text(r.get('sales_pic')) or 'Belum ditetapkan',
            'Unit': text(r.get('jumlah_unit_diminati')) or '—',
            'Prioritas': text(r.get('priority')) or '—',
            'Kondisi': state, 'Urutan': {'Terlambat': 0, 'Hari ini': 1, 'Belum tercatat': 2, 'Belum dijadwalkan': 3, 'Terjadwal': 4}.get(state, 5),
            'Kontak terakhir': display_day(last), 'Usia kontak': (today - last).days if last else None,
            'Hasil terakhir': text(r.get('hasil_follow_up_terakhir')) or 'Belum tercatat',
            'Langkah berikutnya': text(r.get('next_step')) or 'Belum tercatat',
            'Follow-up berikut': display_day(due), 'Tanggal berikut': due.isoformat() if due else '',
            'Diubah di ERP': display_day(mod), 'Diubah lengkap': mod[:16] if mod else '',
            'WA': text(r.get('nomor_whatsapp')), 'Email': text(r.get('email')),
            'Rapat': text(r.get('ringkasan_meeting')),
            'DP': text(r.get('kesiapan_dp')), 'PKS': text(r.get('pks')),
            'Unit final': text(r.get('jumlah_unit_final')),
            'Catatan': text(r.get('description')),
        })
    rows.sort(key=lambda r: (r['Urutan'], r['Tanggal berikut'] or '9999', -(r['Usia kontak'] or 0), r['Nama'].lower()))
    return rows


def create_page(container):
    container.clear()
    df = load_lk_data()
    role = get_current_role()
    if role not in ('admin', 'manager') and not df.empty:
        df = filter_by_staff(df, get_current_email(), get_current_name())
    info = get_cache_info().get('lead_kemitraan', {})
    sync_raw = info.get('last_sync') or ''
    try:
        synced = datetime.fromisoformat(sync_raw)
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=JKT)
        age = datetime.now(timezone.utc) - synced.astimezone(timezone.utc)
        sync_label = synced.astimezone(JKT).strftime('%d %b %Y, %H:%M WIB')
    except ValueError:
        age, sync_label = None, 'Tidak diketahui'
    rows = prepare(df, datetime.now(JKT).date()) if not df.empty else []
    palette = 'background:#1e1e2e;border:1px solid #313244;border-radius:14px;'
    with container:
        with ui.row().classes('w-full items-start justify-between gap-3'):
            with ui.column().classes('gap-0'):
                ui.label('Pipeline Kemitraan').classes('text-2xl font-bold text-white')
                ui.label('Calon investor mesin • tindakan, pemilik, dan progres nyata').classes('text-sm text-gray-400')
            ui.link('Tampilan lama ↗', '/lead-kemitraan-klasik').classes('text-blue-300 text-sm')
        if age is None or age.total_seconds() > 7200:
            ui.label(f'⚠ Data belum segar. Sync terakhir: {sync_label}. Jangan pakai angka ini sebagai kondisi ERP real-time.').classes('text-amber-300 text-sm font-semibold')
        else:
            ui.label(f'Sumber: ERPNext • sync {sync_label} • {len(rows)} lead dalam akses Anda').classes('text-xs text-gray-400')
        if not rows:
            ui.label('Belum ada lead dalam akses Anda.').classes('text-gray-400')
            return
        counts = {k: sum(r['Kondisi'] == k for r in rows) for k in ('Terlambat', 'Hari ini', 'Belum tercatat', 'Belum dijadwalkan', 'Terjadwal')}
        counts['Deal terverifikasi'] = sum(r['Tahap'].lower() in ('dp paid', 'installation', 'active partner', 'live') for r in rows)
        with ui.row().classes('w-full gap-3 flex-wrap'):
            cards = [('Terlambat', '#f38ba8'), ('Hari ini', '#f9e2af'), ('Belum tercatat', '#fab387'), ('Belum dijadwalkan', '#89b4fa'), ('Terjadwal', '#a6e3a1'), ('Deal terverifikasi', '#cba6f7')]
            for title, color in cards:
                with ui.card().classes('min-w-[148px] flex-1 cursor-pointer h-[112px]').style(palette) as card:
                    ui.label(title).classes('text-xs text-gray-300')
                    ui.label(str(counts[title])).style(f'font-size:2rem;font-weight:700;color:{color}')
                card.on('click', lambda _, value=title: set_focus(value))
        ui.label('“Belum tercatat” = tanggal kontak kosong, bukan bukti belum dihubungi. Deal hanya dihitung bila tahap ERP menyatakan DP Paid / Installation / Active Partner / Live.').classes('text-xs text-amber-200')
        with ui.row().classes('w-full items-end gap-3 flex-wrap'):
            focus = ui.select(['Semua', *[c[0] for c in cards]], value='Semua', label='Fokus').props('dense outlined dark').classes('min-w-[160px]')
            status = ui.select(['Semua tahap', *sorted({r['Tahap'] for r in rows})], value='Semua tahap', label='Tahap').props('dense outlined dark').classes('min-w-[160px]')
            search = ui.input('Cari nama, kota, PIC, ID').props('dense outlined dark clearable').classes('min-w-[220px] flex-1')
            ui.button('Muat ulang', on_click=lambda: create_page(container)).props('flat color=blue')
        table_box = ui.column().classes('w-full')

        def set_focus(value):
            focus.value = value
            render_table()

        def detail(row):
            with ui.dialog() as dialog, ui.card().classes('w-[720px] max-w-[95vw]').style(palette):
                ui.label(row['Nama']).classes('text-xl font-bold text-white')
                ui.label(f"{row['ID']} • {row['Kota']} • {row['Tahap']} • {row['PIC']}").classes('text-sm text-gray-300')
                ui.separator()
                for title, key in [('Tindakan', 'Kondisi'), ('Kontak terakhir', 'Kontak terakhir'), ('Hasil follow-up terakhir', 'Hasil terakhir'), ('Langkah berikutnya', 'Langkah berikutnya'), ('Follow-up berikut', 'Follow-up berikut'), ('Terakhir record ERP diubah', 'Diubah lengkap'), ('Ringkasan meeting', 'Rapat'), ('Unit diminati', 'Unit'), ('Unit final', 'Unit final'), ('Kesiapan DP', 'DP'), ('PKS', 'PKS'), ('WhatsApp', 'WA'), ('Email', 'Email')]:
                    with ui.row().classes('w-full justify-between gap-3 border-b border-gray-700 py-1'):
                        ui.label(title).classes('text-gray-400 text-sm')
                        ui.label(row[key] or 'Belum tercatat').classes('text-white text-sm max-w-[65%] break-words text-right')
                with ui.row().classes('gap-4 mt-3'):
                    ui.link('Buka di ERPNext ↗', ERP + row['ID'], new_tab=True).classes('text-blue-300')
                    ui.button('Tutup', on_click=dialog.close).props('flat')
            dialog.open()

        def render_table():
            table_box.clear()
            selected = [r for r in rows if (focus.value == 'Semua' or (r['Tahap'].lower() in ('dp paid','installation','active partner','live') if focus.value == 'Deal terverifikasi' else r['Kondisi'] == focus.value)) and (status.value == 'Semua tahap' or r['Tahap'] == status.value)]
            q = (search.value or '').strip().lower()
            if q:
                selected = [r for r in selected if q in ' '.join((r['Nama'], r['Kota'], r['PIC'], r['ID'])).lower()]
            with table_box:
                ui.label(f'{len(selected)} lead • klik nama untuk riwayat dan tautan ERP').classes('text-sm text-gray-300')
                columns = [
                    ('Nama', 170), ('Kota', 125), ('Tahap', 110), ('PIC', 150), ('Unit', 75),
                    ('Kondisi', 155), ('Kontak terakhir', 135), ('Hasil terakhir', 230),
                    ('Langkah berikutnya', 230), ('Follow-up berikut', 135), ('Diubah di ERP', 135),
                ]
                grid = ui.aggrid({
                    'columnDefs': [{'headerName': title, 'field': title, 'minWidth': width, 'sortable': True,
                                    'filter': True, 'floatingFilter': True, **({'pinned': 'left', 'cellStyle': {'color': '#89b4fa', 'cursor': 'pointer', 'textDecoration': 'underline'}} if title == 'Nama' else {})} for title, width in columns],
                    'rowData': selected, 'pagination': True, 'paginationPageSize': 25,
                    'paginationPageSizeSelector': [10, 25, 50], 'domLayout': 'autoHeight',
                    'defaultColDef': {'resizable': True, 'sortable': True, 'filter': True},
                    'rowHeight': 48, 'enableCellTextSelection': True,
                }, theme='balham').classes('w-full').style('min-height:300px')
                grid.on('cellClicked', lambda e: detail(e.args['data']) if e.args.get('colId') == 'Nama' and e.args.get('data') else None)
        for widget in (focus, status, search):
            widget.on('change', lambda _: render_table())
        render_table()
        ui.label('Analitik bulanan, grafik dan master data lama tetap tersedia melalui “Tampilan lama”.').classes('text-xs text-gray-400 mt-3')
