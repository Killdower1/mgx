# Difotoin Dashboard

Dashboard analisis performa outlet Difotoin berbasis **Streamlit**.

## Fitur

| Menu | Fungsi |
|------|--------|
| 🏠 **Dashboard Utama** | Omzet, foto, unlock, print, conversion rate per outlet |
| 📊 **Analisis Trend** | Tren 12 bulan, KPI, heatmap, AI insight |
| 🤖 **AI Decision** | Ringkasan performa, risiko, eksperimen, outlet prioritas |
| 🔄 **Analisis Konversi** | Funnel photo → unlock → print |
| 🏆 **Ranking Outlet** | Outlet Keeper / Optimasi / Relocate |
| 🤝 **Kemitraan** | Manajemen partnership & bagi hasil |
| 📅 **Perbandingan Periode** | Compare omzet antar periode |
| 🗃️ **CRUD Data Outlet** | Inline editor, master data, AI Suggest |
| ⚙️ **Admin Panel** | User access, database bulanan, threshold config |
| 📤 **Upload Data** | Upload Excel bulanan, overwrite per periode |

## Tech Stack

- **Python** 3.9+
- **Streamlit** — web framework
- **Pandas + NumPy** — data processing
- **Plotly** — charts
- **pytest** — smoke tests

## Quick Start (Lokal)

```bash
cd streamlit_template
pip install -r requirements.txt

# Set admin credentials
export DIFOTOIN_ADMIN_EMAIL=admin@difotoin.local
export DIFOTOIN_ADMIN_PASSWORD=your_password_here

streamlit run app.py
```

Buka `http://localhost:8501` di browser.

## Setup Production

Untuk deploy di server (AlmaLinux + Nginx + PM2), lihat panduan lengkap di:

👉 **[DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)**

## Struktur Proyek

```
difotoin-dashboard/
├── streamlit_template/        # 🎯 Aplikasi utama
│   ├── app.py                 # Router utama
│   ├── config.py              # Konfigurasi path & data
│   ├── data_processor.py      # Logika pemrosesan data
│   ├── visualizations.py      # Helper chart
│   ├── utils.py               # Utility functions
│   ├── pages/                 # Modul halaman
│   ├── components/            # UI components bersama
│   ├── services/              # Business logic (validation, auth)
│   ├── data/                  # 📁 Data runtime canonical
│   └── tests/                 # Smoke tests
├── uploads/                   # Staging / manual import
├── DEPLOY_GUIDE.md            # Panduan deploy server
└── README.md                  # (file ini)
```

## Kebijakan Data

| Lokasi | Status |
|--------|--------|
| `streamlit_template/data/` | **Canonical** — sumber data runtime |
| `uploads/` | **Staging only** — Excel mentah, jangan di-commit |
| File `.xlsx` mentah | Jangan pernah di-commit ke Git |

## Menjalankan Test

```bash
cd streamlit_template
pytest tests/ -v
```

## Lisensi

**Proprietary** — Internal Difotoin. Tidak untuk distribusi publik.
