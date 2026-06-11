#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-difotoin-dashboard}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
PY_APP_DIR="$APP_DIR/streamlit_template"
VENV_DIR="$PY_APP_DIR/.venv"
NGINX_TARGET="${NGINX_TARGET:-/etc/nginx/conf.d/difotoin-dashboard.conf}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8501}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups/deploy}"

echo "==> Difotoin deploy"
echo "App dir : $APP_DIR"
echo "Branch  : $BRANCH"
echo "PM2 app : $APP_NAME"
echo

cd "$APP_DIR"

if [ ! -d ".git" ]; then
  echo "ERROR: $APP_DIR is not a git repository."
  exit 1
fi

echo "==> Creating deploy backup"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/deploy_backup_$STAMP.tar.gz"
tar \
  --exclude="streamlit_template/.venv" \
  --exclude="backups" \
  -czf "$BACKUP_FILE" \
  streamlit_template/data \
  streamlit_template/config \
  ecosystem.config.js \
  nginx.conf 2>/dev/null || true
echo "Backup: $BACKUP_FILE"
echo

echo "==> Fetching latest code"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
echo

echo "==> Ensuring Python virtual environment"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
    echo "python3 -m venv failed. Installing virtualenv fallback."
    python3 -m pip install --user virtualenv
    python3 -m virtualenv "$VENV_DIR"
  fi
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
echo

echo "==> Restarting PM2 app"
echo "A short reconnect page may appear while Streamlit starts again."
if pm2 describe "$APP_NAME" >/dev/null 2>&1; then
  pm2 restart "$APP_NAME" --update-env
else
  pm2 start ecosystem.config.js
fi
pm2 save
echo

echo "==> Waiting for Streamlit health"
for i in $(seq 1 30); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Health OK: $HEALTH_URL"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: app is not healthy after 30 seconds."
    echo "Check logs with: pm2 logs $APP_NAME"
    exit 1
  fi
  sleep 1
done
echo

echo "==> Updating nginx config"
if [ -f "$APP_DIR/nginx.conf" ] && command -v nginx >/dev/null 2>&1; then
  if [ -w "$(dirname "$NGINX_TARGET")" ]; then
    cp "$APP_DIR/nginx.conf" "$NGINX_TARGET"
  else
    sudo cp "$APP_DIR/nginx.conf" "$NGINX_TARGET"
  fi

  sudo nginx -t
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl reload nginx
  else
    sudo nginx -s reload
  fi
else
  echo "Skip nginx update: nginx command or nginx.conf not found."
fi
echo

echo "==> Deploy complete"
pm2 status "$APP_NAME" || true
echo
echo "Useful checks:"
echo "- pm2 logs $APP_NAME"
echo "- curl -I $HEALTH_URL"
