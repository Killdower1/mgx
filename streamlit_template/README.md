# 📸 Difotoin Sales Dashboard

Dashboard analisis penjualan untuk bisnis photo booth Difotoin dengan fitur lengkap untuk monitoring performa outlet, analisis konversi, dan manajemen data.

## 🚀 Fitur Utama

- **Dashboard Utama**: Overview metrics, tabel performa outlet dengan comparison
- **Analisis Trend**: Trend penjualan per area, kategori, dan tipe tempat
- **Analisis Konversi**: Funnel conversion dan awareness analysis
- **Ranking Outlet**: Peringkat outlet berdasarkan performa
- **Perbandingan Periode**: Growth metrics dan side-by-side comparison
- **CRUD Data**: Management outlet dan master data (kategori, sub kategori, area)
- **Admin Panel**: Konfigurasi threshold dan system settings
- **Upload Data**: Import data Excel bulanan

## 📋 Requirements

- Python 3.8 atau lebih tinggi
- pip (Python package installer)
- 4GB RAM minimum
- 1GB storage space

## 🛠️ Instalasi

### 1. Download dan Extract

```bash
# Download aplikasi dan extract ke folder yang diinginkan
cd /path/to/your/folder
# Extract difotoin-dashboard.zip
```

### 2. Setup Python Environment (Opsional tapi Direkomendasikan)

```bash
# Buat virtual environment
python -m venv venv

# Aktivasi virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install semua dependencies
pip install -r requirements.txt
```

### 4. Setup Data Folder

```bash
# Buat folder data jika belum ada
mkdir data
```

## 🎯 Cara Menjalankan

### Menjalankan Dashboard

```bash
# Jalankan aplikasi
streamlit run app.py

# Atau dengan port spesifik
streamlit run app.py --server.port 8501
```

Dashboard akan terbuka di browser pada `http://localhost:8501`

### Menghentikan Aplikasi

- Tekan `Ctrl + C` di terminal untuk menghentikan server

## 📊 Setup Data Awal

### 1. Format Data Excel

Aplikasi mendukung upload file Excel dengan kolom:

**Required:**
- `outlet_name`: Nama outlet
- `harga`: Revenue per transaksi

**Optional:**
- `tanggal`: Tanggal transaksi (YYYY-MM-DD)
- `area`: Area/kota outlet
- `kategori_tempat`: Kategori tempat (Mall, Wisata, dll)
- `sub_kategori_tempat`: Sub kategori
- `tipe_tempat`: Indoor/Outdoor/Semi-Outdoor

### 2. Sample Data

File `sample_data.xlsx` disediakan sebagai contoh format data yang benar.

### 3. Upload Data

1. Buka halaman "📤 Upload Data"
2. Pilih file Excel
3. Preview data akan muncul
4. Klik "🚀 Process and Update Dashboard"

## 🗃️ Master Data Management

### Kategori Tempat (21+ kategori):
Mall, Wisata, Restoran, Hotel, Komunitas, Sekolah, Universitas, Rumah Sakit, Perkantoran, Apartemen, Cafe, Gym, Salon, Spa, Bioskop, Taman, Museum, Galeri, Event Space, Co-working Space, Lainnya

### Area Indonesia (100+ kota/kabupaten):
Seluruh kota dan kabupaten di Indonesia dari Jakarta hingga Papua

### Sub Kategori (28+ sub kategori):
Food Court, Department Store, Pantai, Gunung, Fine Dining, Budget Hotel, dll

## ⚙️ Konfigurasi

### Threshold Settings

Di halaman Admin Panel, Anda dapat mengatur:

- **Keeper Minimum**: Batas minimum revenue untuk status Keeper
- **Optimasi Minimum**: Batas minimum revenue untuk status Optimasi
- Outlet di bawah Optimasi Minimum akan mendapat status Relocate

### File Konfigurasi

- `config/config.json`: Pengaturan threshold dan konfigurasi sistem
- `data/`: Folder penyimpanan data dan mapping outlet

## 🔧 Troubleshooting

### Error: ModuleNotFoundError

```bash
# Pastikan semua dependencies terinstall
pip install -r requirements.txt

# Atau install manual:
pip install streamlit pandas plotly numpy openpyxl
```

### Error: Port Already in Use

```bash
# Gunakan port lain
streamlit run app.py --server.port 8502
```

### Error: Data tidak muncul

1. Pastikan file Excel format benar
2. Check folder `data/` ada dan writable
3. Upload ulang data melalui halaman Upload Data

### Performance Issues

1. **Memory**: Tutup aplikasi lain yang tidak perlu
2. **Speed**: Gunakan data sample kecil untuk testing
3. **Browser**: Gunakan Chrome atau Firefox terbaru

## 📱 Penggunaan Dashboard

### 1. Dashboard Utama
- **Periode Selection**: Pilih periode current dan compare
- **Filter Buttons**: Filter outlet berdasarkan status (Keeper/Optimasi/Relocate)
- **Outlet Table**: Tabel performa dengan frozen column dan sorting
- **Compare Columns**: Muncul otomatis saat periode compare dipilih

### 2. Analisis Trend
- Analisis per area geografis
- Breakdown per kategori tempat
- Perbandingan Indoor vs Outdoor
- Performance heatmap

### 3. Analisis Konversi
- Conversion funnel (Foto → Unlock → Print)
- High/Low conversion outlets
- Awareness analysis

### 4. Ranking Outlet
- Ranking berdasarkan revenue
- Filter berdasarkan status
- Analysis per kategori status

### 5. Perbandingan Periode
- Growth metrics (Revenue, Photo, Conversion)
- Side-by-side comparison
- Trend analysis charts

### 6. CRUD Data Outlet
- **Outlet Management**: Add, Edit, Delete outlet
- **Master Data Kategori**: Manage kategori dan sub kategori
- **Master Data Area**: Manage kota/kabupaten Indonesia

### 7. Admin Panel
- Threshold configuration
- System information
- Configuration backup

### 8. Upload Data
- Excel file upload
- Data validation
- Processing dan update dashboard

## 🔒 Keamanan Data

- Data disimpan lokal di folder `data/`
- Tidak ada koneksi ke server eksternal
- Backup data secara berkala direkomendasikan

## 📈 Tips Optimasi

1. **Data Size**: Gunakan data maksimal 100K rows untuk performa optimal
2. **Browser**: Tutup tab lain untuk menghemat memory
3. **Refresh**: Refresh browser jika dashboard terasa lambat
4. **Backup**: Backup folder `data/` secara berkala

## 🆘 Support

Jika mengalami masalah:

1. Check troubleshooting guide di atas
2. Pastikan Python dan dependencies up-to-date
3. Restart aplikasi dengan `Ctrl+C` dan jalankan ulang
4. Check log error di terminal

## 📄 File Structure

```
difotoin-dashboard/
├── app.py                 # Main application
├── requirements.txt       # Dependencies
├── README.md             # Dokumentasi ini
├── sample_data.xlsx      # Sample data
├── data/                 # Data storage
│   ├── difotoin_dashboard_data.csv
│   └── difotoin_outlet_mapping.csv
├── config/               # Configuration files
└── assets/              # Static assets
```

## 🔄 Update Aplikasi

Untuk update aplikasi:
1. Backup folder `data/`
2. Replace file aplikasi dengan versi baru
3. Jalankan `pip install -r requirements.txt`
4. Restore folder `data/`

## 📊 Data Format Reference

### Excel Upload Format:
| outlet_name | tanggal | area | kategori_tempat | harga | foto_qty | unlock_qty | print_qty |
|-------------|---------|------|-----------------|-------|----------|------------|-----------|
| Mall Taman Anggrek | 2024-01-15 | Jakarta | Mall | 25000 | 150 | 120 | 45 |

### Status Classification:
- **Keeper**: Revenue ≥ Keeper Minimum
- **Optimasi**: Optimasi Minimum ≤ Revenue < Keeper Minimum  
- **Relocate**: Revenue < Optimasi Minimum

---

**Difotoin Sales Dashboard v1.0**  
Developed for Difotoin Photo Booth Business Analytics