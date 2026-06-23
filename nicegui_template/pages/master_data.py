"""
Master Data page — shows all available database fields from every data source.
Gives users a reference of what data fields exist for analysis/processing.
"""

from nicegui import ui


FIELDS = {
    "Dashboard (CSV)": {
        "description": "Data performa outlet per periode — omzet, foto, unlock, dll.",
        "source": "difotoin_dashboard_data.csv (manual upload)",
        "fields": [
            ("outlet_name", "Nama outlet", "Teks"),
            ("periode", "Bulan-tahun data (e.g. 2025-01)", "Teks"),
            ("area", "Wilayah outlet", "Teks"),
            ("kategori_tempat", "Kategori tempat (e.g. Kafe, Restoran)", "Teks"),
            ("sub_kategori_tempat", "Sub-kategori tempat", "Teks"),
            ("tipe_tempat", "Tipe tempat (e.g. Indoor, Outdoor)", "Teks"),
            ("foto_qty", "Jumlah foto digital", "Angka"),
            ("unlock_qty", "Jumlah unlock", "Angka"),
            ("print_qty", "Jumlah cetak", "Angka"),
            ("total_revenue", "Total pendapatan", "Angka"),
            ("conversion_rate", "Rasio konversi (foto ke revenue)", "Persen"),
            ("unlock_to_print_rate", "Rasio unlock ke print", "Persen"),
            ("outlet_status", "Status outlet (Aktif/Nonaktif)", "Teks"),
        ],
    },
    "Outlet Mapping": {
        "description": "Data mapping outlet — untuk referensi area & kategori tempat.",
        "source": "difotoin_outlet_mapping.csv",
        "fields": [
            ("outlet_name", "Nama outlet", "Teks"),
            ("area", "Wilayah outlet", "Teks"),
            ("kategori_tempat", "Kategori tempat", "Teks"),
            ("sub_kategori_tempat", "Sub-kategori tempat", "Teks"),
            ("tipe_tempat", "Tipe tempat", "Teks"),
        ],
    },
    "Lead Partnership (ERPNext)": {
        "description": "Data calon partner penempatan mesin difotoin dari ERPNext.",
        "source": "ERPNext DocType: Lead Partnership",
        "label": "Lead Partnership",
        "fields": [
            ("name", "ID unik record di ERPNext", "Teks"),
            ("nama_tempat", "Nama tempat/lokasi", "Teks"),
            ("nama_pic", "Nama PIC (penanggung jawab)", "Teks"),
            ("nama_perusahaan__lembaga__venue_jika_ada", "Nama perusahaan/lembaga/venue", "Teks"),
            ("email_pic", "Email PIC", "Teks"),
            ("nomor_whatsapp_pic", "Nomor WhatsApp PIC", "Teks"),
            ("jabatan_pic", "Jabatan PIC", "Teks"),
            ("jabatan_pic_lainnya", "Jabatan PIC (lainnya)", "Teks"),
            ("jenis_partnership", "Jenis partnership/kerjasama", "Teks"),
            ("jenis_lokasi", "Jenis lokasi (e.g. Ruko, Mall)", "Teks"),
            ("jenis_lokasi_lainnya", "Jenis lokasi (lainnya)", "Teks"),
            ("tipe_lokasi", "Tipe lokasi (e.g. Indoor, Outdoor)", "Teks"),
            ("kota_lokasi", "Kota lokasi tempat", "Teks"),
            ("kota_lokasi_lainnya", "Kota lokasi (lainnya)", "Teks"),
            ("area_penempatan", "Area penempatan mesin", "Teks"),
            ("alamat__link_google_maps", "Alamat / Google Maps link", "Teks"),
            ("skema_kerja_sama_yang_terbuka", "Skema kerjasama yang tersedia", "Teks"),
            ("skema_final", "Skema final yang disepakati", "Teks"),
            ("harga_sewa", "Harga sewa per bulan", "Angka"),
            ("potensi_revenue", "Potensi revenue per bulan", "Angka"),
            ("revenue_share", "Revenue share (%)", "Persen"),
            ("minimum_kontrak", "Minimum kontrak (bulan)", "Angka"),
            ("minimum_payment", "Minimum pembayaran", "Angka"),
            ("estimasi_pengunjung_per_hari", "Estimasi pengunjung per hari", "Angka"),
            ("space_tersedia", "Space tersedia (ukuran)", "Teks"),
            ("listrik_tersedia", "Listrik tersedia", "Teks"),
            ("kelayakan_space", "Kelayakan space", "Teks"),
            ("kelayakan_listrik", "Kelayakan listrik", "Teks"),
            ("kelayakan_operasional", "Kelayakan operasional", "Teks"),
            ("location_score", "Skor lokasi (rating)", "Angka"),
            ("pic_responsif", "Apakah PIC responsif?", "Teks"),
            ("source_lead", "Sumber lead", "Teks"),
            ("source_lead_lainnya", "Sumber lead (lainnya)", "Teks"),
            ("status_lead", "Status lead (New, Contacted, Qualified, etc)", "Teks"),
            ("priority", "Prioritas (High, Medium, Low)", "Teks"),
            ("decision", "Keputusan (Approve, Reject, etc)", "Teks"),
            ("lost_reason", "Alasan lost/gagal", "Teks"),
            ("sales_pic", "Sales PIC (penanggung jawab)", "Teks"),
            ("sales_pic_full", "Sales PIC (nama lengkap)", "Teks"),
            ("hasil_follow_up", "Hasil follow-up terbaru", "Teks"),
            ("last_follow_up", "Tanggal follow-up terakhir", "Tanggal"),
            ("next_follow_up", "Tanggal follow-up berikutnya", "Tanggal"),
            ("note", "Catatan internal", "Teks"),
            ("status_change", "Riwayat perubahan status (JSON)", "Teks"),
            ("tanggal_masuk", "Tanggal masuk lead", "Tanggal"),
            ("datetime_qualified", "Waktu qualified", "Datetime"),
            ("datetime_contact", "Waktu di-contact", "Datetime"),
            ("datetime_negotiation", "Waktu negosiasi", "Datetime"),
            ("datetime_approved", "Waktu approved", "Datetime"),
            ("datetime_live", "Waktu live/go-live", "Datetime"),
            ("datetime_lost", "Waktu lost", "Datetime"),
            ("datetime_need_info", "Waktu need info", "Datetime"),
            ("creation", "Tanggal dibuat di ERPNext", "Datetime"),
            ("modified", "Tanggal terakhir diubah", "Datetime"),
            ("owner", "Pemilik record ERPNext", "Teks"),
            ("modified_by", "Pengubah terakhir", "Teks"),
            ("docstatus", "Dokumen status (0=Draft, 1=Submitted)", "Angka"),
            ("idx", "Index row", "Angka"),
        ],
    },
    "Lead Kemitraan (ERPNext)": {
        "description": "Data calon mitra franchise difotoin dari ERPNext.",
        "source": "ERPNext DocType: Lead Kemitraan",
        "label": "Lead Kemitraan",
        "fields": [
            ("name", "ID unik record di ERPNext", "Teks"),
            ("nama_lengkap", "Nama lengkap calon mitra", "Teks"),
            ("lead_name", "Nama lead", "Teks"),
            ("first_name", "Nama depan", "Teks"),
            ("last_name", "Nama belakang", "Teks"),
            ("nomor_whatsapp", "Nomor WhatsApp", "Teks"),
            ("email", "Email", "Teks"),
            ("email_id", "Email ID", "Teks"),
            ("mobile_no", "Nomor handphone", "Teks"),
            ("phone", "Nomor telepon", "Teks"),
            ("website", "Website", "Teks"),
            ("gender", "Jenis kelamin", "Teks"),
            ("city", "Kota", "Teks"),
            ("state", "Provinsi", "Teks"),
            ("country", "Negara", "Teks"),
            ("provinsi", "Provinsi", "Teks"),
            ("kota_domisili", "Kota domisili", "Teks"),
            ("kota_domisili_lainnya", "Kota domisili (lainnya)", "Teks"),
            ("kota_penempatan_mesin", "Kota penempatan mesin", "Teks"),
            ("kota_penempatan_mesin_lainnya", "Kota penempatan mesin (lainnya)", "Teks"),
            ("kota_lokasi", "Kota lokasi", "Teks"),
            ("kota_lokasi_lainnya", "Kota lokasi (lainnya)", "Teks"),
            ("alamat", "Alamat", "Teks"),
            ("nama_tempat", "Nama tempat", "Teks"),
            ("nama_lokasi", "Nama lokasi", "Teks"),
            ("tempat", "Tempat", "Teks"),
            ("jenis_lokasi", "Jenis lokasi", "Teks"),
            ("jenis_lokasi_lainnya", "Jenis lokasi (lainnya)", "Teks"),
            ("sudah_punya_lokasi", "Sudah punya lokasi? (Sudah/Belum)", "Teks"),
            ("status_lokasi", "Status lokasi", "Teks"),
            ("pekerjaan_bisnis_saat_ini", "Pekerjaan/bisnis saat ini", "Teks"),
            ("dari_mana_tahu_difotoin", "Dari mana tahu difotoin?", "Teks"),
            ("dari_mana_tahu_difotoin_lainnya", "Dari mana tahu difotoin (lainnya)", "Teks"),
            ("jumlah_unit_diminati", "Jumlah unit yang diminati", "Angka"),
            ("jumlah_unit_final", "Jumlah unit final", "Angka"),
            ("budget_investasi", "Budget investasi", "Angka"),
            ("harga_investasi_dibahas", "Harga investasi yang dibahas", "Angka"),
            ("skema_pembayaran", "Skema pembayaran", "Teks"),
            ("kesiapan_dp", "Kesiapan DP (Down Payment)", "Teks"),
            ("target_bep", "Target BEP (break even point)", "Teks"),
            ("kapan_ingin_mulai", "Kapan ingin mulai", "Teks"),
            ("status_lead", "Status lead (New, Contacted, Qualified, etc)", "Teks"),
            ("priority", "Prioritas (High, Medium, Low)", "Teks"),
            ("source_lead", "Sumber lead", "Teks"),
            ("source_lead_lainnya", "Sumber lead (lainnya)", "Teks"),
            ("source", "Source dari ERPNext", "Teks"),
            ("sales_pic", "Sales PIC", "Teks"),
            ("lead_owner", "Pemilik lead", "Teks"),
            ("hasil_follow_up_terakhir", "Hasil follow-up terakhir", "Teks"),
            ("last_follow_up", "Tanggal follow-up terakhir", "Tanggal"),
            ("next_follow_up", "Tanggal follow-up berikutnya", "Tanggal"),
            ("next_step", "Langkah selanjutnya", "Teks"),
            ("jadwal_meeting", "Jadwal meeting", "Datetime"),
            ("set_jadwal", "Set jadwal", "Teks"),
            ("ringkasan_meeting", "Ringkasan meeting", "Teks"),
            ("tipe_meeting", "Tipe meeting (Online/Offline)", "Teks"),
            ("note", "Catatan internal", "Teks"),
            ("note1", "Catatan 1", "Teks"),
            ("note_contact", "Catatan kontak", "Teks"),
            ("note_cancel", "Catatan pembatalan", "Teks"),
            ("nurturing_reason", "Alasan nurturing", "Teks"),
            ("lost_reason", "Alasan lost/gagal", "Teks"),
            ("qualification_status", "Status kualifikasi", "Teks"),
            ("qualified_by", "Dikualifikasi oleh", "Teks"),
            ("qualified_on", "Tanggal kualifikasi", "Tanggal"),
            ("disabled", "Dinonaktifkan? (0/1)", "Angka"),
            ("company", "Perusahaan", "Teks"),
            ("company_name", "Nama perusahaan", "Teks"),
            ("title", "Title", "Teks"),
            ("industry", "Industri", "Teks"),
            ("market_segment", "Segmen pasar", "Teks"),
            ("territory", "Teritori", "Teks"),
            ("annual_revenue", "Pendapatan tahunan", "Angka"),
            ("no_of_employees", "Jumlah karyawan", "Angka"),
            ("mesin", "Jenis mesin", "Teks"),
            ("request_type", "Tipe permintaan", "Teks"),
            ("campaign_name", "Nama campaign", "Teks"),
            ("bekerja_sama_sebagai", "Bekerja sama sebagai", "Teks"),
            ("language", "Bahasa", "Teks"),
            ("creation", "Tanggal dibuat di ERPNext", "Datetime"),
            ("modified", "Tanggal terakhir diubah", "Datetime"),
            ("owner", "Pemilik record ERPNext", "Teks"),
            ("modified_by", "Pengubah terakhir", "Teks"),
            ("docstatus", "Dokumen status (0=Draft, 1=Submitted)", "Angka"),
            ("idx", "Index row", "Angka"),
        ],
    },
}


CATEGORIES_WITH_SUBFIELDS = [
    "Lead Partnership (ERPNext)",
    "Lead Kemitraan (ERPNext)",
]


def create_page(container):
    """Build the Master Data page."""
    with container:
        ui.label("[Master Data] Referensi Field Database").classes(
            "text-2xl font-bold text-white mb-2"
        )
        ui.label(
            "Daftar lengkap semua field/data yang tersedia di dashboard ini. "
            "Gunakan sebagai referensi untuk mengetahui data apa aja yang bisa diolah."
        ).classes("text-sm text-gray-400 mb-6")

        # Simple tables section
        simple_tables = [
            cat
            for cat in FIELDS
            if cat not in CATEGORIES_WITH_SUBFIELDS
        ]

        for cat_name in simple_tables:
            cat = FIELDS[cat_name]
            _render_table_section(cat_name, cat)

        # ERPNext section with sub-tabs
        ui.separator().classes("my-6")
        ui.label("[ERPNext] Sumber Data ERPNext").classes(
            "text-xl font-bold text-white mb-3"
        )
        ui.label(
            "Data berikut diambil langsung dari ERPNext via API. "
            "Bisa di-fetch manual di halaman masing-masing."
        ).classes("text-sm text-gray-400 mb-4")

        tabs = ui.tabs().classes("w-full mb-4")
        tab_panels = ui.tab_panels(tabs).classes("w-full")

        for cat_name in CATEGORIES_WITH_SUBFIELDS:
            cat = FIELDS[cat_name]
            label = cat.get("label", cat_name)
            tab_label = label.replace("Lead ", "").replace(" (ERPNext)", "")
            with tabs:
                ui.tab(tab_label, icon="dataset")
            with tab_panels:
                with ui.tab_panel(tab_label):
                    _render_table_section(cat_name, cat, sub=True)

        # Legend
        ui.separator().classes("my-6")
        ui.label("Keterangan Tipe Data").classes(
            "text-lg font-bold text-white mb-3"
        )
        legend_items = [
            ("Teks", "Data berupa tulisan/karakter - bisa difilter, dicari, dikelompokkan"),
            ("Angka", "Data berupa angka - bisa dijumlah, dirata-rata, di-chart"),
            ("Persen", "Data berupa persentase - bisa dirata-rata"),
            ("Tanggal", "Data berupa tanggal - bisa diurutkan, difilter berdasarkan waktu"),
            ("Datetime", "Data berupa tanggal dan jam - lebih detail dari tanggal biasa"),
        ]
        ui.table(
            columns=[
                {"name": "type", "label": "Tipe", "field": "type", "align": "left"},
                {"name": "desc", "label": "Keterangan", "field": "desc", "align": "left"},
            ],
            rows=[{"type": f"  {t}", "desc": d} for t, d in legend_items],
            row_key="type",
            pagination={"rowsPerPage": 10},
        ).classes("w-full").props("dark flat dense")

        ui.label(
            "Tip: Field-field di atas bisa lo pake buat filter, chart, analisis, "
            "dan pengolahan data lainnya di dashboard ini."
        ).classes("text-xs text-gray-500 mt-3")


def _render_table_section(cat_name, cat, sub=False):
    """Render one section: header + field table."""
    ui.label(cat_name).classes("text-lg font-semibold text-white mb-1")
    ui.label(cat["description"]).classes("text-xs text-gray-400 mb-1")
    ui.label(f"Sumber: {cat['source']}").classes("text-xs text-gray-500 mb-3 italic")

    rows = [{"field": f, "label": l, "type": t} for f, l, t in cat["fields"]]
    total = len(rows)

    ui.label(f"{total} field").classes("text-sm text-gray-500 mb-2")

    ui.table(
        columns=[
            {"name": "field", "label": "Field Name", "field": "field", "align": "left", "sortable": True},
            {"name": "label", "label": "Deskripsi", "field": "label", "align": "left", "sortable": True},
            {"name": "type", "label": "Tipe", "field": "type", "align": "center", "sortable": True},
        ],
        rows=rows,
        row_key="field",
        pagination={"rowsPerPage": 25, "rowsNumber": total},
    ).classes("w-full mb-6").props("dark flat dense")
