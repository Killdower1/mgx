#!/usr/bin/env bash
set -euo pipefail

REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-$(git branch --show-current)}"
MESSAGE="${1:-${MESSAGE:-}}"

if [ ! -d ".git" ]; then
  echo "ERROR: Jalankan script dari root Git repository."
  exit 1
fi

if [ -z "$BRANCH" ]; then
  echo "ERROR: Tidak bisa membaca branch aktif."
  exit 1
fi

echo
echo "==> Repository status"
git status --short

if [ -z "$MESSAGE" ]; then
  printf "Commit message: "
  read -r MESSAGE
fi

if [ -z "$MESSAGE" ]; then
  echo "ERROR: Commit message wajib diisi."
  exit 1
fi

echo
echo "==> Staging changes"
git add -A

if git diff --cached --quiet; then
  echo "Tidak ada perubahan untuk di-commit."
else
  echo
  echo "==> Committing"
  git commit -m "$MESSAGE"
fi

echo
echo "==> Pushing to $REMOTE/$BRANCH"
git push "$REMOTE" "$BRANCH"

echo
echo "==> Done"
git status --short
