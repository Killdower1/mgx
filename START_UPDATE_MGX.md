# start update mgx

Tanggal mulai: 2026-06-08

Dokumen ini adalah baseline kerja untuk merapikan dashboard web Difotoin agar lebih efisien, aman untuk GitHub, dan siap menerima update data berkala.

## Konteks Produk

Dashboard ini dipakai founder Difotoin untuk membaca performa outlet berbasis data yang diterima berkala. Fokus data utama:

- Omzet per outlet dan periode.
- Jumlah foto, unlock, print.
- Conversion rate dan unlock-to-print rate.
- Area, kategori tempat, sub kategori, dan tipe tempat.
- Status outlet: Keeper, Optimasi, Relocate.
- Upload Excel bulanan dengan overwrite berdasarkan periode.

## Struktur Saat Ini

- `streamlit_template/app.py`: aplikasi Streamlit utama, multi-page dashboard.
- `streamlit_template/data_processor.py`: load data, sample data, filter, agregasi.
- `streamlit_template/visualizations.py`: chart Plotly.
- `streamlit_template/config.py`: konfigurasi threshold dan path runtime.
- `streamlit_template/data/`: data dashboard yang dipakai app.
- `uploads/`: bahan data/prototype awal dari MGX atau proses sebelumnya.
- `code.ipynb`: notebook kerja/eksplorasi.

## Kondisi Data

Snapshot dari file dashboard complete:

- Periode data: `2025-06` sampai `2025-09`.
- Total outlet: 37.
- Total record agregat: 148.
- Threshold awal data: Keeper `20.000.000`, Optimasi `10.000.000`.

Kolom utama CSV dashboard:

- `outlet_name`
- `area`
- `kategori_tempat`
- `sub_kategori_tempat`
- `tipe_tempat`
- `periode`
- `foto_qty`
- `unlock_qty`
- `print_qty`
- `total_revenue`
- `conversion_rate`
- `unlock_to_print_rate`
- `avg_revenue_per_transaction`
- `avg_revenue_per_print`
- `outlet_status`
- `revenue_rank`

## Temuan Aneh / Salah

- Credential login sebelumnya hardcoded di `app.py`, termasuk password asli. Ini tidak aman untuk GitHub.
- `.venv`, `__pycache__`, `.MGXEnv.json`, `.MGXTools`, `.timeline.json`, config runtime, dan Excel upload mentah sempat tracked oleh Git.
- Path data/config sebelumnya relatif ke current working directory, sehingga rawan gagal kalau app dijalankan dari folder berbeda.
- Banyak teks UI/README terkena mojibake encoding, terutama emoji dan simbol.
- Ada `package-lock.json` di project Streamlit Python tanpa package Node yang relevan.
- Ada dua sumber data serupa: `uploads/` dan `streamlit_template/data/`. Perlu diputuskan mana canonical source.
- `DataProcessor.process_uploaded_file()` masih versi lama/sederhana dan tidak sejalan dengan upload flow baru di `app.py`.
- Master data kategori/area yang ditambah via UI masih hanya hidup di session list, belum persist sebagai master data terstruktur.

## Update Yang Sudah Dilakukan

- Login tidak lagi menyimpan email/password asli di source code.
- Login sekarang membaca:
  - `DIFOTOIN_ADMIN_EMAIL`
  - `DIFOTOIN_ADMIN_PASSWORD`
- Path data dan config dibuat berbasis lokasi file `streamlit_template`, bukan folder terminal.
- `DATA_CSV_PATH` dan `OUTLET_MAPPING_PATH` dipusatkan di `config.py`.
- Dependency `xlrd` ditambahkan karena upload flow mendukung `.xls`.
- `.gitignore` root dibuat untuk Python, Streamlit secrets, MGX artifacts, venv, cache, dan upload Excel lokal.
- Artefak lokal besar/sensitif dikeluarkan dari Git index tanpa menghapus file lokal.
- Parser harga upload diperbaiki agar angka Excel seperti `35000.0` tidak berubah menjadi `350000`.
- Menu CRUD outlet diperbarui menjadi inline table editor dengan search, filter, dropdown field, add outlet, master data view, dan delete multi-select.
- Admin Panel ditambah User Access untuk membuat akun lokal berisi nama, email, dan password hash.
- Paket deploy server ditambahkan: `requirements.txt`, `install.sh`, `ecosystem.config.js`, `nginx.conf`, dan root `README.md`.
- Login dibuat lebih tahan reconnect dengan session token lokal dan Nginx config diperkuat untuk websocket Streamlit.
- Data dashboard sekarang otomatis memakai outlet mapping terbaru dari CRUD, dan halaman Trend diperbarui dengan KPI, monthly trend, segment summary, outlet movers, dan heatmap.
- Admin Panel ditambah Database Bulanan untuk melihat ringkasan per periode dan menghapus data bulanan tertentu dengan backup otomatis.
- CRUD outlet sekarang otomatis menarik outlet yang ada di database transaksi tetapi belum ada di mapping, termasuk outlet event.
- Dashboard utama sekarang menampilkan semua outlet sesuai filter, termasuk outlet yang tidak aktif di periode terpilih, dan tabel Tren Omset 12 Bulan dipisah antara outlet aktif dan tidak aktif.
- Delete outlet di CRUD sekarang memakai checklist tabel dan wajib mengetik `DELETE` sebelum menghapus mapping outlet.
- Halaman Analisis Trend ditambah range periode, default 12 bulan terakhir dari periode data terbaru, agar perbandingan area/outlet lebih fair.
- Halaman Analisis Trend ditambah tab AI Insight lokal untuk merangkum performa, temuan penting, dan rekomendasi aksi berdasarkan range periode terpilih.
- AI Insight dirapikan menjadi satu tempat di tab, dibuat lebih tajam dengan decision brief, risiko, eksperimen, outlet prioritas, dan halaman khusus AI Decision.
- CRUD outlet ditambah tab AI Suggest untuk rekomendasi area, kategori, sub kategori, dan tipe dari nama outlet. Hasil AI bisa diedit manual sebelum di-apply.
- Deploy server dipermudah dengan `deploy.sh` untuk backup, pull dari GitHub, update dependency, restart PM2, health check, dan reload Nginx.
- Push ke GitHub dipermudah dengan `push.ps1` untuk Windows PowerShell dan `push.sh` untuk Git Bash/Linux.
- Delete outlet CRUD diperbaiki agar pilihan checklist tidak hilang saat konfirmasi `DELETE`.
- Delete outlet CRUD sekarang menyimpan blocklist lokal agar outlet yang masih ada di data transaksi tidak otomatis masuk lagi lewat auto-sync.
- CRUD outlet tidak lagi memakai tab Streamlit untuk mode utama agar tidak lompat saat rerun; kolom Outlet di editor dibuat sebagai index sticky saat scroll horizontal.
- App ditambah scroll guard dan status widget connection Streamlit disembunyikan agar reconnect/rerun tidak mengganggu posisi layar.

## Cara Menjalankan Lokal

Dari Windows tanpa terminal:

- Double-click `Run Difotoin Dashboard.exe` di root project.
- Isi email dan password admin.
- Browser akan terbuka ke `http://localhost:8501`.
- Biarkan window info launcher tetap terbuka selama dashboard dipakai.
- Klik `Restart Server` di launcher kalau dashboard macet, reconnect terus, atau perlu dinyalakan ulang.
- Klik `OK` di window launcher kalau ingin mematikan server dashboard.

Dari folder `streamlit_template`:

```bash
pip install -r requirements.txt
set DIFOTOIN_ADMIN_EMAIL=admin@difotoin.local
set DIFOTOIN_ADMIN_PASSWORD=isi_password_sendiri
streamlit run app.py
```

Untuk PowerShell:

```powershell
$env:DIFOTOIN_ADMIN_EMAIL="admin@difotoin.local"
$env:DIFOTOIN_ADMIN_PASSWORD="isi_password_sendiri"
streamlit run app.py
```

## Prinsip Update Data Berkala

- Upload data per bulan.
- Pastikan periode memakai format `YYYY-MM`.
- Saat save, data untuk periode yang sama akan dihapus lalu diganti hasil upload baru.
- Selalu cek audit total Excel raw vs hasil agregasi sebelum save.
- Kalau ada periode salah, hapus dari Admin Panel > Database Bulanan. Sistem akan membuat backup CSV otomatis sebelum data dihapus.
- Jangan commit file Excel mentah dari `uploads/` kecuali memang sengaja dijadikan sample publik.

## Prioritas Berikutnya

1. Bersihkan mojibake encoding di UI dan README.
2. Satukan sumber data canonical: pilih `streamlit_template/data/` sebagai runtime app, dan jadikan `uploads/` hanya staging/manual import.
3. Pecah `app.py` yang sudah terlalu besar menjadi modul page dan service kecil.
4. Persist master data area/kategori/sub kategori ke CSV/JSON, bukan list hardcoded/session.
5. Tambahkan validasi data upload yang lebih ketat: periode, outlet kosong, harga nol/negatif, type tidak dikenal.
6. Tambahkan smoke test minimal untuk load config, load data, dan agregasi upload.
7. Buat README GitHub yang ringkas: setup, env var, data policy, dan deploy.
8. Pertimbangkan Streamlit secrets untuk deployment, bukan env var manual.

## Catatan GitHub

File lokal yang sebaiknya tidak masuk repo:

- `.MGXEnv.json`
- `.MGXTools/`
- `.timeline.json`
- `streamlit_template/.venv/`
- `streamlit_template/__pycache__/`
- `streamlit_template/config/config.json`
- file Excel mentah di `uploads/`

Kalau repo pernah terlanjur dipush dengan credential/password atau file environment, perlu rotate password dan bersihkan history Git sebelum repo dibuat publik.
