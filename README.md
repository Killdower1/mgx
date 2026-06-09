# Difotoin Dashboard - Panduan Setup Pribadi

Panduan ini dibuat sebagai catatan operasional untuk setup, upload ke GitHub, deploy ke server, dan maintenance dashboard Difotoin.

Dashboard ini dibuat dengan Streamlit untuk memantau performa outlet Difotoin:

- Omzet per outlet dan periode.
- Foto, unlock, print.
- Conversion rate.
- Ranking outlet.
- CRUD outlet.
- Upload data transaksi bulanan.
- User access untuk membuat akun login.

## 1. Struktur Project

File penting di root repo:

```text
mgx/
  README.md
  requirements.txt
  install.sh
  ecosystem.config.js
  nginx.conf
  START_UPDATE_MGX.md
  Run Difotoin Dashboard.exe
  streamlit_template/
    app.py
    config.py
    data_processor.py
    visualizations.py
    utils.py
    data/
    config/
```

Fungsi file:

- `README.md`: panduan setup ini.
- `requirements.txt`: dependency Python untuk server.
- `install.sh`: script install awal di server Linux/Ubuntu.
- `ecosystem.config.js`: konfigurasi PM2 supaya dashboard terus hidup.
- `nginx.conf`: contoh konfigurasi Nginx untuk reverse proxy.
- `Run Difotoin Dashboard.exe`: launcher lokal Windows.
- `streamlit_template/app.py`: aplikasi utama.
- `streamlit_template/data/`: data dashboard.
- `streamlit_template/config/`: config runtime lokal/server.

File yang sengaja tidak masuk GitHub:

- `streamlit_template/config/users.json`
- `streamlit_template/config/config.json`
- `.env`
- `.venv/`
- file Excel upload mentah

## 2. Cara Jalanin Di Laptop Windows

Cara paling gampang:

1. Buka folder project `mgx`.
2. Double-click `Run Difotoin Dashboard.exe`.
3. Isi email dan password.
4. Tunggu status launcher sampai `ready`.
5. Browser akan buka `http://localhost:8501`.
6. Login pakai email dan password yang tadi diisi.

Kalau mau jalanin manual lewat PowerShell:

```powershell
cd C:\Users\octadimas\Documents\GitHub\mgx
$env:DIFOTOIN_ADMIN_EMAIL="octadimas@gmail.com"
$env:DIFOTOIN_ADMIN_PASSWORD="password-local"
cd streamlit_template
python -m streamlit run app.py
```

Kalau dependency belum ada:

```powershell
cd C:\Users\octadimas\Documents\GitHub\mgx
python -m pip install -r requirements.txt
```

## 3. Sebelum Commit Ke GitHub

Cek status:

```bash
git status
```

Cek file yang berubah:

```bash
git diff --stat
```

Pastikan tidak ada file sensitif ikut commit:

- Password asli.
- `.env`
- `users.json`
- `.venv`
- file Excel mentah.

Kalau semua aman, commit:

```bash
git add .
git commit -m "prepare difotoin dashboard deployment"
```

Push ke GitHub:

```bash
git push origin main
```

Kalau branch bukan `main`, cek branch:

```bash
git branch
```

Lalu push sesuai branch:

```bash
git push origin nama-branch
```

## 4. Setup Repo GitHub Dari Nol

Kalau repo belum ada di GitHub:

1. Buka GitHub.
2. Create new repository.
3. Isi nama repo, misalnya `difotoin-dashboard`.
4. Jangan centang initialize README kalau project lokal sudah ada.
5. Copy remote URL GitHub.

Hubungkan folder lokal ke GitHub:

```bash
git remote add origin https://github.com/USERNAME/REPO.git
git branch -M main
git push -u origin main
```

Kalau remote sudah ada tapi mau cek:

```bash
git remote -v
```

Kalau remote salah:

```bash
git remote set-url origin https://github.com/USERNAME/REPO.git
```

## 5. Setup Server Baru

Asumsi server memakai Ubuntu.

Login ke server:

```bash
ssh username@IP_SERVER
```

Update server:

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

Install Git:

```bash
sudo apt-get install -y git
```

Clone repo:

```bash
cd /var/www
sudo git clone https://github.com/USERNAME/REPO.git difotoin-dashboard
sudo chown -R $USER:$USER difotoin-dashboard
cd difotoin-dashboard
```

Jalankan installer:

```bash
chmod +x install.sh
./install.sh
```

Script ini akan setup:

- Python 3.
- Python venv.
- Pip dependency.
- Nginx.
- Node.js dan npm.
- PM2.

## 6. Set Credential Admin Fallback

Edit `ecosystem.config.js`:

```bash
nano ecosystem.config.js
```

Ganti bagian ini:

```js
DIFOTOIN_ADMIN_EMAIL: "admin@difotoin.local",
DIFOTOIN_ADMIN_PASSWORD: "CHANGE_ME_BEFORE_START"
```

Menjadi email dan password admin sementara:

```js
DIFOTOIN_ADMIN_EMAIL: "email-admin@domain.com",
DIFOTOIN_ADMIN_PASSWORD: "password-kuat"
```

Credential ini dipakai untuk login pertama. Setelah masuk dashboard, bikin akun permanen dari:

```text
Admin Panel > User Access
```

## 7. Start App Dengan PM2

Dari root repo di server:

```bash
pm2 start ecosystem.config.js
```

Cek status:

```bash
pm2 status
```

Cek log:

```bash
pm2 logs difotoin-dashboard
```

Simpan proses supaya hidup lagi setelah reboot:

```bash
pm2 save
pm2 startup
```

Perintah `pm2 startup` biasanya menampilkan command tambahan. Copy dan jalankan command yang muncul.

## 8. Tes App Di Server

Cek dari server:

```bash
curl http://127.0.0.1:8501
```

Kalau keluar HTML, app sudah hidup.

Kalau belum hidup, cek:

```bash
pm2 logs difotoin-dashboard
```

## 9. Setup Nginx

Copy config Nginx:

```bash
sudo cp nginx.conf /etc/nginx/sites-available/difotoin-dashboard
```

Enable config:

```bash
sudo ln -s /etc/nginx/sites-available/difotoin-dashboard /etc/nginx/sites-enabled/difotoin-dashboard
```

Tes Nginx:

```bash
sudo nginx -t
```

Reload Nginx:

```bash
sudo systemctl reload nginx
```

Buka:

```text
http://IP_SERVER
```

## 10. Setup Domain

Di DNS provider domain, buat record:

```text
Type: A
Name: dashboard
Value: IP_SERVER
```

Contoh domain:

```text
dashboard.difotoin.id
```

Edit Nginx config:

```bash
sudo nano /etc/nginx/sites-available/difotoin-dashboard
```

Ganti:

```nginx
server_name _;
```

Menjadi:

```nginx
server_name dashboard.difotoin.id;
```

Tes dan reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 11. Setup HTTPS SSL

Install Certbot:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

Generate SSL:

```bash
sudo certbot --nginx -d dashboard.difotoin.id
```

Ikuti instruksi Certbot.

Tes auto renew:

```bash
sudo certbot renew --dry-run
```

## 12. Login Dan Buat Akun

Login pertama pakai credential fallback dari `ecosystem.config.js`.

Setelah masuk:

1. Buka `Admin Panel`.
2. Cari section `User Access`.
3. Klik tab `Add Account`.
4. Isi nama, email, password.
5. Klik `Create Account`.

Setelah akun dibuat, login berikutnya bisa pakai akun itu.

Data akun disimpan di server:

```text
streamlit_template/config/users.json
```

Password tidak disimpan mentah, tapi dalam bentuk hash.

## 13. Upload Data Bulanan

Masuk ke halaman:

```text
Upload Data
```

Alur aman:

1. Upload file Excel transaksi.
2. Pilih sheet yang benar.
3. Pastikan mapping kolom:
   - Outlet ke `outlet_name`
   - Harga ke `harga`
   - Tanggal ke `tanggal`
   - Tipe ke `type`
4. Pastikan periode format `YYYY-MM`.
5. Biarkan `Harga Scale` di `x1 (normal)`.
6. Cek audit total raw vs agregasi.
7. Kalau total sudah benar, klik save.

Catatan penting:

- Save upload akan overwrite data untuk periode yang sama.
- Kalau upload September lagi, data September lama diganti.
- Parser harga sudah dibenerin, jadi angka seperti `35000.0` tetap jadi `35000`.
- Tidak perlu pilih `divide by 10` kecuali file sumber benar-benar beda format.

## 14. Update Aplikasi Dari GitHub Ke Server

Masuk ke server:

```bash
ssh username@IP_SERVER
```

Masuk folder project:

```bash
cd /var/www/difotoin-dashboard
```

Pull update:

```bash
git pull origin main
```

Install dependency terbaru:

```bash
./install.sh
```

Restart app:

```bash
pm2 restart difotoin-dashboard
```

Cek log:

```bash
pm2 logs difotoin-dashboard
```

## 15. Backup Data Server

Minimal backup folder:

```text
streamlit_template/data/
streamlit_template/config/
```

Backup manual:

```bash
cd /var/www/difotoin-dashboard
tar -czf backup-difotoin-$(date +%Y-%m-%d).tar.gz streamlit_template/data streamlit_template/config
```

Download backup ke laptop:

```bash
scp username@IP_SERVER:/var/www/difotoin-dashboard/backup-difotoin-YYYY-MM-DD.tar.gz .
```

Restore backup:

```bash
tar -xzf backup-difotoin-YYYY-MM-DD.tar.gz
pm2 restart difotoin-dashboard
```

## 16. Troubleshooting

App tidak bisa dibuka:

```bash
pm2 status
pm2 logs difotoin-dashboard
```

Port 8501 tidak hidup:

```bash
curl http://127.0.0.1:8501
```

Nginx error:

```bash
sudo nginx -t
sudo systemctl status nginx
```

Domain belum masuk:

```bash
ping dashboard.difotoin.id
```

Permission error:

```bash
sudo chown -R $USER:$USER /var/www/difotoin-dashboard
```

Dependency error:

```bash
cd /var/www/difotoin-dashboard
./install.sh
pm2 restart difotoin-dashboard
```

Lupa password akun lokal:

1. Login pakai admin fallback dari `ecosystem.config.js`.
2. Buka `Admin Panel > User Access`.
3. Reset password akun.

Kalau admin fallback juga lupa, edit `ecosystem.config.js`, ganti password fallback, lalu:

```bash
pm2 restart difotoin-dashboard
```

## 17. Checklist Deploy Cepat

Checklist dari laptop:

- Commit perubahan terbaru.
- Push ke GitHub.
- Pastikan tidak ada secret ikut commit.

Checklist di server:

- Clone repo.
- Jalankan `./install.sh`.
- Edit credential di `ecosystem.config.js`.
- Jalankan `pm2 start ecosystem.config.js`.
- Jalankan `pm2 save`.
- Setup Nginx.
- Setup domain.
- Setup SSL.
- Login dashboard.
- Buat akun utama di `Admin Panel > User Access`.
- Upload atau cek data.

## 18. Command Ringkas

Start:

```bash
pm2 start ecosystem.config.js
```

Restart:

```bash
pm2 restart difotoin-dashboard
```

Stop:

```bash
pm2 stop difotoin-dashboard
```

Logs:

```bash
pm2 logs difotoin-dashboard
```

Nginx reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Update app:

```bash
git pull origin main && ./install.sh && pm2 restart difotoin-dashboard
```
