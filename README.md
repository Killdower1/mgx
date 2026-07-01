# Difotoin Dashboard

Dashboard analisis & monitoring operasional Difotoin — **NiceGUI** + **ERPNext** + **API Adam**.

> ⚡ Dashboard internal untuk tim Difotoin (CEO, Head Operasional, Marketing, Finance, Creative).

---

## Fitur

### 📊 Core Dashboard
| Menu | Fungsi |
|------|--------|
| 📊 **Dashboard** | Omzet, foto, unlock, print, conversion rate per outlet |
| 📈 **Analisis Trend** | Tren 12 bulan, KPI, heatmap, AI insight |
| 🤖 **AI Decision** | Ringkasan performa, risiko, eksperimen, outlet prioritas |
| 🔄 **Analisis Konversi** | Funnel photo → unlock → print |
| 🏆 **Ranking Outlet** | Outlet Keeper / Optimasi / Relocate |
| 📅 **Perbandingan Periode** | Compare omzet antar periode |

### 🤝 Kemitraan & Lead Management
| Menu | Fungsi |
|------|--------|
| 🤝 **Kemitraan** | Manajemen partnership & bagi hasil |
| 📋 **Lead Partnership** | Data calon partner penempatan mesin dari ERPNext |
| 👥 **Lead Kemitraan** | Data franchise/kemitraan dari ERPNext |
| [MD] **Master Data** | Database field reference |

### 🔧 Operasional
| Menu | Fungsi |
|------|--------|
| 🔧 **Problem Booth** | Dashboard problem booth — monitoring oleh Head (Dino) |
| 🎨 **Creative Team** | Manajemen tim kreatif |
| 💵 **Revenue Sharing** | Bagi hasil per outlet & per bulan |
| 🗃️ **CRUD Outlet** | Inline editor, master data, AI Suggest |

### ⚙️ Admin
| Menu | Fungsi |
|------|--------|
| ⚙️ **Admin Panel** | User access, ERPNext config, roles, database |
| 📤 **Upload Data** | Upload Excel bulanan |

---

## Tech Stack

- **Python** 3.11
- **NiceGUI** — web framework (replacing Streamlit)
- **Pandas + NumPy** — data processing
- **Plotly** — charts
- **AG Grid** — data tables
- **ERPNext REST API** — lead & operational data
- **API Adam** — transaction data
- **PM2** — process manager (production)
- **Nginx** — reverse proxy

---

## Halaman Utama

### 🔧 Problem Booth
`/problem-booth` — Dashboard operasional monitoring problem booth.

**4 Tab:**
| Tab | Data | Ukuran |
|-----|------|--------|
| 📊 Dashboard | KPI, Top Problems, Open list, Branch/PIC breakdown | 6KB |
| 📋 Data Per Bulan | 34 bulan — Total, Open, Closed, per tipe problem | 27KB |
| 🔍 Cari ID | Search by PB-xxxxx → full detail + link ERPNext | lazy |
| 📈 Statistik | Monthly trend + Status distribution | 6KB |

**Fitur:**
- 📥 Tombol **Sync dari ERPNext** (manual)
- ⏰ **Cron auto-sync** tiap jam 6 pagi
- 🔗 Link detail ke ERPNext

---

## Struktur Proyek

```
difotoin-dashboard/
├── nicegui_template/           # 🎯 Aplikasi utama (NiceGUI)
│   ├── main.py                 # Router utama + route definitions
│   ├── pages/                  # Modul halaman
│   │   ├── dashboard.py        # Dashboard utama
│   │   ├── problem_booth.py    # Problem Booth (baru)
│   │   ├── lead_partnership.py # Lead Partnership
│   │   ├── lead_kemitraan.py   # Lead Kemitraan
│   │   ├── admin.py            # Admin Panel
│   │   ├── login.py            # Login page
│   │   └── ...                 # Halaman lainnya
│   ├── services/               # Business logic
│   │   ├── auth_service.py     # Authentication & roles
│   │   ├── erpnext_adapter.py  # ERPNext API adapter
│   │   └── dashboard_adapter.py
│   └── .venv/                  # Python virtual environment
├── streamlit_template/         # 🗄️ Legacy (Streamlit — not active)
├── scripts/                    # Utility scripts
│   └── sync_problem_booth.py   # Sync Problem Booth dari ERPNext
├── problem_booth_summary.json  # Ringkasan data (6KB)
├── problem_booth_monthly.json  # Data per bulan (27KB)
├── problem_booth_cache_light.json  # Cache penuh (10MB, gitignored)
└── README.md
```

---

## Auth & Roles

| Role | Akses |
|------|-------|
| **admin** | Full akses semua halaman |
| **manager** | Dashboard, Trend, Ranking, Kemitraan, Lead, Problem Booth |
| **staff** | Dashboard, Ranking, Kemitraan, Lead, Problem Booth, Master Data |
| **creative** | Creative Team + Dashboard |
| **viewer** | Dashboard only |

Login bisa pake:
1. **Akun lokal** (users.json)
2. **Akun ERPNext** (email & password ERPNext)
3. **Admin env var** (fallback)

---

## Quick Start (Development)

```bash
cd nicegui_template
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
# Buka http://localhost:8502
```

---

## Deployment

Production: **AlmaLinux + Nginx + PM2**

```bash
pm2 start ecosystem.config.js
pm2 save
```

Akses via: `http://103.250.10.163`

---

## Lisensi

**Proprietary** — Internal Difotoin. Tidak untuk distribusi publik.
