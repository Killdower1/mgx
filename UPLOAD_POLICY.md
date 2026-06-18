# Kebijakan Data & Upload

## Direktori Data

| Direktori | Tujuan | Dicommit? |
|-----------|--------|-----------|
| `streamlit_template/data/` | **Sumber data runtime (canonical)** untuk aplikasi. CSV/JSON di sini dipakai dashboard saat berjalan. | Ya (CSV/JSON hasil agregasi) |
| `uploads/` | Staging / manual import sementara. Tempat taruh file Excel mentah sebelum diproses ke `data/`. | **Tidak** (sudah di-.gitignore) |
| `streamlit_template/config/` | Konfigurasi lokal: users, sessions, master data, dll. | Tidak (sudah di-.gitignore) |

## Aturan Upload

1. File Excel mentah (`.xlsx`, `.xls`) wajib ditaruh di `uploads/` saat proses upload via UI.
2. Setelah diproses, data final (CSV) harus disimpan ke `streamlit_template/data/`.
3. File Excel mentah **tidak boleh** dicommit ke Git.
4. `uploads/` hanya untuk staging; jangan dijadikan sumber runtime.

## Migrasi

Jika ada file `.csv` di `uploads/` yang lebih baru dari `data/`, admin harus memindahkan secara manual. Tidak ada auto-migrate untuk menghindari overwrite tak sengaja.
