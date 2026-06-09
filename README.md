# Difotoin Dashboard - Panduan Deploy Pribadi

Panduan ini disesuaikan untuk server lo sekarang:

```text
OS      : AlmaLinux v8.x
User    : killdower
Public IP: 103.250.10.163
App     : Difotoin Dashboard / Streamlit
Port app: 8501
```

Dashboard ini dipakai untuk monitoring outlet Difotoin: omzet, foto, unlock, print, conversion, ranking outlet, CRUD outlet, upload data transaksi bulanan, dan user access.

## 1. File Penting

```text
mgx/
  README.md
  requirements.txt
  install.sh
  ecosystem.config.js
  nginx.conf
  START_UPDATE_MGX.md
  streamlit_template/
    app.py
    config.py
    data_processor.py
    visualizations.py
    utils.py
    data/
    config/
```

Fungsi file deploy:

- `requirements.txt`: dependency Python.
- `install.sh`: installer server, sudah support AlmaLinux/RHEL dan Ubuntu.
- `ecosystem.config.js`: konfigurasi PM2 untuk menjalankan Streamlit.
- `nginx.conf`: reverse proxy dari port 80 ke Streamlit `127.0.0.1:8501`.
- `streamlit_template/config/users.json`: akun login lokal, tidak ikut GitHub.

## 2. Jalanin Lokal Di Windows

Cara paling gampang:

1. Buka folder project `mgx`.
2. Double-click `Run Difotoin Dashboard.exe`.
3. Isi email dan password.
4. Tunggu status launcher sampai `ready`.
5. Browser buka `http://localhost:8501`.
6. Login pakai email/password yang tadi diisi.

Manual via PowerShell:

```powershell
cd C:\Users\octadimas\Documents\GitHub\mgx
python -m pip install -r requirements.txt
$env:DIFOTOIN_ADMIN_EMAIL="octadimas@gmail.com"
$env:DIFOTOIN_ADMIN_PASSWORD="password-local"
cd streamlit_template
python -m streamlit run app.py
```

## 3. Sebelum Push Ke GitHub

Cek status:

```bash
git status
```

Cek ringkasan perubahan:

```bash
git diff --stat
```

Pastikan file ini tidak ikut commit:

- `.env`
- `.venv/`
- `streamlit_template/config/users.json`
- `streamlit_template/config/config.json`
- file Excel mentah
- password asli di `ecosystem.config.js`

Commit:

```bash
git add .
git commit -m "prepare difotoin dashboard deployment"
```

Push:

```bash
git push origin main
```

Kalau branch bukan `main`:

```bash
git branch
git push origin nama-branch
```

## 4. Connect Project Lokal Ke GitHub

Kalau repo GitHub belum tersambung:

```bash
git remote add origin https://github.com/USERNAME/REPO.git
git branch -M main
git push -u origin main
```

Cek remote:

```bash
git remote -v
```

Ganti remote kalau salah:

```bash
git remote set-url origin https://github.com/USERNAME/REPO.git
```

## 5. Login Ke Server AlmaLinux

Dari terminal laptop:

```bash
ssh killdower@103.250.10.163
```

Kalau SSH pertama kali minta konfirmasi:

```text
Are you sure you want to continue connecting?
```

Ketik:

```bash
yes
```

## 6. Persiapan Server AlmaLinux

Update server:

```bash
sudo dnf update -y
```

Install Git:

```bash
sudo dnf install -y git
```

Buat folder app:

```bash
sudo mkdir -p /var/www
sudo chown -R killdower:killdower /var/www
cd /var/www
```

Clone repo:

```bash
git clone https://github.com/USERNAME/REPO.git difotoin-dashboard
cd difotoin-dashboard
```

Ganti `USERNAME/REPO` sesuai repo GitHub lo.

## 7. Install Dependency Server

Dari folder repo di server:

```bash
cd /var/www/difotoin-dashboard
chmod +x install.sh
./install.sh
```

Script ini akan install:

- Python 3.
- Pip.
- Virtualenv/venv.
- Nginx.
- Curl.
- Git.
- Node.js.
- npm.
- PM2.

Kalau `install.sh` gagal karena permission:

```bash
chmod +x install.sh
./install.sh
```

Kalau `dnf` minta password, isi password user server.

## 8. Set Admin Login Pertama

Edit PM2 config:

```bash
nano ecosystem.config.js
```

Cari:

```js
DIFOTOIN_ADMIN_EMAIL: "admin@difotoin.local",
DIFOTOIN_ADMIN_PASSWORD: "CHANGE_ME_BEFORE_START"
```

Ganti ke email dan password sementara yang kuat:

```js
DIFOTOIN_ADMIN_EMAIL: "email-admin@domain.com",
DIFOTOIN_ADMIN_PASSWORD: "password-kuat"
```

Simpan di nano:

```text
CTRL + O
ENTER
CTRL + X
```

Catatan: jangan commit password asli ke GitHub. Password ini hanya diedit langsung di server.

## 9. Start Dashboard Dengan PM2

Start app:

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

Simpan PM2 supaya hidup lagi setelah reboot:

```bash
pm2 save
pm2 startup systemd -u killdower --hp /home/killdower
```

Command `pm2 startup` biasanya akan menampilkan command tambahan dengan `sudo env ...`. Copy command itu lalu jalankan.

## 10. Tes Streamlit Dari Server

Tes app lokal server:

```bash
curl http://127.0.0.1:8501
```

Kalau keluar HTML, app sudah hidup.

Kalau gagal:

```bash
pm2 logs difotoin-dashboard
```

## 11. Setup Nginx Di AlmaLinux

Di AlmaLinux, config Nginx biasanya pakai:

```text
/etc/nginx/conf.d/
```

Copy config:

```bash
sudo cp nginx.conf /etc/nginx/conf.d/difotoin-dashboard.conf
```

Tes config:

```bash
sudo nginx -t
```

Enable dan start Nginx:

```bash
sudo systemctl enable nginx
sudo systemctl restart nginx
```

## 12. Buka Firewall AlmaLinux

Cek firewalld:

```bash
sudo systemctl status firewalld
```

Kalau firewalld aktif, buka HTTP dan HTTPS:

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

Kalau cuma mau test port Streamlit langsung:

```bash
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

Tapi untuk production, lebih bagus akses publik lewat Nginx port 80/443, bukan langsung port 8501.

## 13. SELinux AlmaLinux

AlmaLinux biasanya pakai SELinux. Supaya Nginx boleh proxy ke Streamlit:

```bash
sudo setsebool -P httpd_can_network_connect 1
```

Kalau command `setsebool` tidak ada:

```bash
sudo dnf install -y policycoreutils-python-utils
sudo setsebool -P httpd_can_network_connect 1
```

## 14. Test Dari Browser

Buka:

```text
http://103.250.10.163
```

Kalau belum bisa:

```bash
pm2 status
pm2 logs difotoin-dashboard
sudo nginx -t
sudo systemctl status nginx
sudo firewall-cmd --list-all
```

## 15. Setup Domain

Di DNS provider, buat record:

```text
Type : A
Name : dashboard
Value: 103.250.10.163
```

Contoh domain:

```text
dashboard.difotoin.id
```

Edit Nginx config:

```bash
sudo nano /etc/nginx/conf.d/difotoin-dashboard.conf
```

Ganti:

```nginx
server_name _;
```

Menjadi:

```nginx
server_name dashboard.difotoin.id;
```

Reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 16. Setup HTTPS SSL Di AlmaLinux

Install Certbot:

```bash
sudo dnf install -y epel-release
sudo dnf install -y certbot python3-certbot-nginx
```

Generate SSL:

```bash
sudo certbot --nginx -d dashboard.difotoin.id
```

Tes auto-renew:

```bash
sudo certbot renew --dry-run
```

## 17. Login Dan Buat Akun Aplikasi

Login pertama pakai admin fallback dari `ecosystem.config.js`.

Setelah masuk:

1. Buka `Admin Panel`.
2. Buka section `User Access`.
3. Klik `Add Account`.
4. Isi nama, email, password.
5. Klik `Create Account`.

Akun disimpan di:

```text
streamlit_template/config/users.json
```

Password disimpan sebagai hash, bukan plain text.

## 18. Upload Data Bulanan

Masuk ke halaman:

```text
Upload Data
```

Alur:

1. Upload file Excel transaksi.
2. Pilih sheet.
3. Mapping kolom:
   - Outlet ke `outlet_name`
   - Harga ke `harga`
   - Tanggal ke `tanggal`
   - Tipe ke `type`
4. Pastikan periode `YYYY-MM`.
5. Biarkan `Harga Scale` di `x1 (normal)`.
6. Cek audit total.
7. Save jika total sudah benar.

Catatan:

- Upload periode yang sama akan overwrite data lama di periode itu.
- Parser harga sudah dibenerin; `35000.0` tetap jadi `35000`.
- Tidak perlu pilih `divide by 10` kecuali file sumber memang beda format.

## 19. Update App Dari GitHub Ke Server

Masuk server:

```bash
ssh killdower@103.250.10.163
```

Masuk folder app:

```bash
cd /var/www/difotoin-dashboard
```

Backup dulu sebelum pull:

```bash
tar -czf backup-difotoin-$(date +%Y-%m-%d-%H%M).tar.gz streamlit_template/data streamlit_template/config
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

Cek:

```bash
pm2 logs difotoin-dashboard
```

## 20. Backup Data Server

Backup folder penting:

```text
streamlit_template/data/
streamlit_template/config/
```

Command backup:

```bash
cd /var/www/difotoin-dashboard
tar -czf backup-difotoin-$(date +%Y-%m-%d-%H%M).tar.gz streamlit_template/data streamlit_template/config
```

Download ke laptop:

```bash
scp killdower@103.250.10.163:/var/www/difotoin-dashboard/backup-difotoin-YYYY-MM-DD-HHMM.tar.gz .
```

Restore:

```bash
cd /var/www/difotoin-dashboard
tar -xzf backup-difotoin-YYYY-MM-DD-HHMM.tar.gz
pm2 restart difotoin-dashboard
```

## 21. Troubleshooting Cepat

App mati:

```bash
pm2 status
pm2 logs difotoin-dashboard
```

Streamlit tidak respon:

```bash
curl http://127.0.0.1:8501
```

Nginx error:

```bash
sudo nginx -t
sudo systemctl status nginx
```

Nginx masih proxy ke port lama seperti `127.0.0.1:8092`:

```bash
sudo nginx -T | grep -n -B5 -A12 "127.0.0.1:8092"
```

Cari nama file config yang muncul di atas block itu, lalu nonaktifkan atau edit. Biasanya ada di `/etc/nginx/conf.d/`.

Contoh cara cari file:

```bash
sudo grep -R "8092\|server_name 103.250.10.163" /etc/nginx -n
```

Kalau ada file lama yang tidak dipakai, pindahkan ke backup:

```bash
sudo mv /etc/nginx/conf.d/NAMA-FILE-LAMA.conf /etc/nginx/conf.d/NAMA-FILE-LAMA.conf.bak
```

Lalu aktifkan config dashboard:

```bash
cd /var/www/difotoin-dashboard
sudo cp nginx.conf /etc/nginx/conf.d/difotoin-dashboard.conf
sudo nginx -t
sudo systemctl restart nginx
```

Firewall:

```bash
sudo firewall-cmd --list-all
```

SELinux proxy error:

```bash
sudo setsebool -P httpd_can_network_connect 1
```

Streamlit sering muncul status `Connection...` atau auto logout:

```bash
cd /var/www/difotoin-dashboard
sudo cp nginx.conf /etc/nginx/conf.d/difotoin-dashboard.conf
sudo nginx -t
sudo systemctl restart nginx
pm2 restart difotoin-dashboard
```

Pastikan `curl` dari server tetap OK:

```bash
curl -I http://127.0.0.1:8501
curl -I http://103.250.10.163
```

App juga menyimpan session login ringan di:

```text
streamlit_template/config/sessions.json
```

File itu tidak ikut GitHub.

Permission error:

```bash
sudo chown -R killdower:killdower /var/www/difotoin-dashboard
```

Error `npm` bentrok dengan `nodejs` di AlmaLinux:

```text
package npm ... requires nodejs ... cannot install both nodejs...
```

Artinya server sudah punya `nodejs` dari NodeSource, tapi `dnf` mencoba install `npm` dari AppStream. Cek dulu:

```bash
node -v
npm -v
```

Kalau `npm -v` sudah keluar versi, ulang installer:

```bash
./install.sh
```

Kalau `npm` belum ada, coba:

```bash
sudo dnf install -y npm --allowerasing
```

atau:

```bash
sudo dnf install -y npm --nobest
```

Lalu ulang:

```bash
./install.sh
```

Lupa password akun aplikasi:

1. Login pakai admin fallback dari `ecosystem.config.js`.
2. Buka `Admin Panel > User Access`.
3. Reset password akun.

Lupa password fallback:

```bash
cd /var/www/difotoin-dashboard
nano ecosystem.config.js
pm2 restart difotoin-dashboard
```

## 22. Command Ringkas

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
cd /var/www/difotoin-dashboard
git pull origin main
./install.sh
pm2 restart difotoin-dashboard
```

## 23. Checklist Deploy Server Ini

- Push update terbaru ke GitHub.
- SSH ke `killdower@103.250.10.163`.
- Clone repo ke `/var/www/difotoin-dashboard`.
- Jalankan `./install.sh`.
- Edit `ecosystem.config.js` di server, isi admin fallback.
- Jalankan `pm2 start ecosystem.config.js`.
- Jalankan `pm2 save`.
- Jalankan `pm2 startup systemd -u killdower --hp /home/killdower`.
- Copy Nginx config ke `/etc/nginx/conf.d/difotoin-dashboard.conf`.
- Jalankan `sudo setsebool -P httpd_can_network_connect 1`.
- Buka firewall HTTP/HTTPS.
- Test `http://103.250.10.163`.
- Setup domain.
- Setup SSL.
- Login dashboard.
- Buat akun utama di `Admin Panel > User Access`.
