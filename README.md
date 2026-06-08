# Difotoin Dashboard

Dashboard Streamlit untuk monitoring performa outlet Difotoin: omzet, foto, unlock, print, conversion, ranking outlet, upload data transaksi, CRUD outlet, dan pengelolaan akun akses.

## Struktur

- `streamlit_template/app.py`: aplikasi utama.
- `streamlit_template/data/`: data dashboard runtime.
- `streamlit_template/config/`: config lokal runtime. File akun dan config lokal tidak ikut Git.
- `requirements.txt`: dependency Python untuk server.
- `install.sh`: installer awal untuk server Linux/Ubuntu.
- `ecosystem.config.js`: konfigurasi PM2.
- `nginx.conf`: contoh reverse proxy Nginx ke Streamlit.

## Setup Server Baru

Masuk ke server, clone repo, lalu dari root repo:

```bash
chmod +x install.sh
./install.sh
```

Edit credential admin fallback di `ecosystem.config.js` sebelum start:

```js
DIFOTOIN_ADMIN_EMAIL: "email-admin@domain.com",
DIFOTOIN_ADMIN_PASSWORD: "password-kuat"
```

Start aplikasi:

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

## Setup Nginx

Copy config:

```bash
sudo cp nginx.conf /etc/nginx/sites-available/difotoin-dashboard
sudo ln -s /etc/nginx/sites-available/difotoin-dashboard /etc/nginx/sites-enabled/difotoin-dashboard
sudo nginx -t
sudo systemctl reload nginx
```

Kalau sudah punya domain, ganti `server_name _;` di `nginx.conf` menjadi domain, misalnya:

```nginx
server_name dashboard.difotoin.id;
```

## Login Dan Akun

Login pertama bisa memakai credential fallback dari `ecosystem.config.js`.

Setelah masuk, buka `Admin Panel` lalu bagian `User Access` untuk membuat akun:

- Nama
- Email
- Password

Password akun lokal disimpan sebagai hash di:

```text
streamlit_template/config/users.json
```

File itu sengaja masuk `.gitignore` agar akun server tidak ikut ke GitHub.

## Upload Data

Upload transaksi dilakukan dari halaman `Upload Data`.

Catatan:

- Upload data per bulan.
- Periode memakai format `YYYY-MM`.
- Save upload akan overwrite data pada periode yang sama.
- Cek audit total sebelum save.
- Harga normal tidak perlu pilih `divide by 10`; parser sudah menjaga angka Excel seperti `35000.0` tetap menjadi `35000`.

## Perintah Operasional

Restart app:

```bash
pm2 restart difotoin-dashboard
```

Lihat log:

```bash
pm2 logs difotoin-dashboard
```

Stop app:

```bash
pm2 stop difotoin-dashboard
```

Update dari GitHub:

```bash
git pull
./install.sh
pm2 restart difotoin-dashboard
```

## Local Development

Dari root repo:

```bash
python -m venv streamlit_template/.venv
streamlit_template/.venv/Scripts/pip install -r requirements.txt
```

Jalankan di Windows PowerShell:

```powershell
$env:DIFOTOIN_ADMIN_EMAIL="octadimas@gmail.com"
$env:DIFOTOIN_ADMIN_PASSWORD="password-local"
cd streamlit_template
.\.venv\Scripts\streamlit run app.py
```

Atau double-click `Run Difotoin Dashboard.exe` di root project.
