#!/usr/bin/env bash
set -euo pipefail

APP_NAME="difotoin-dashboard"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_APP_DIR="$APP_DIR/streamlit_template"
VENV_DIR="$PY_APP_DIR/.venv"

echo "==> Installing OS packages"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip nginx curl nodejs npm
else
  echo "apt-get not found. Install python3, python3-venv, python3-pip, nginx, curl, nodejs, and npm manually."
fi

echo "==> Creating Python virtual environment"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> Ensuring runtime folders exist"
mkdir -p "$PY_APP_DIR/config" "$PY_APP_DIR/data"

echo "==> Installing PM2 if available through npm"
if command -v npm >/dev/null 2>&1 && ! command -v pm2 >/dev/null 2>&1; then
  sudo npm install -g pm2
fi

echo "==> Install complete"
echo
echo "Next steps:"
echo "1. Edit ecosystem.config.js and set DIFOTOIN_ADMIN_EMAIL / DIFOTOIN_ADMIN_PASSWORD."
echo "2. Start app: pm2 start ecosystem.config.js"
echo "3. Save PM2: pm2 save"
echo "4. Copy nginx.conf to /etc/nginx/sites-available/difotoin-dashboard and enable it."
echo
echo "Local app command:"
echo "cd $PY_APP_DIR && source .venv/bin/activate && streamlit run app.py --server.address 127.0.0.1 --server.port 8501"
