#!/usr/bin/env bash
# Khôi phục vào một DB trống và một thư mục kho trống, rồi kiểm tra.
# Server đích phải có sẵn role tax_app và role sở hữu schema giống server nguồn.
#
#   BACKUP=<thư mục backup> TARGET_ADMIN_URL=... TARGET_STORAGE_DIR=... ops/restore.sh
set -euo pipefail
: "${BACKUP:?}" "${TARGET_ADMIN_URL:?}" "${TARGET_STORAGE_DIR:?}"
(cd "$BACKUP" && sha256sum --check --quiet SHA256SUMS)
if [ -n "$(ls -A "$TARGET_STORAGE_DIR" 2>/dev/null)" ]; then
  echo "TARGET_STORAGE_DIR không trống, dừng để tránh ghi đè" >&2
  exit 1
fi
mkdir -p "$TARGET_STORAGE_DIR"
pg_restore --exit-on-error --dbname="$TARGET_ADMIN_URL" "$BACKUP/db.dump"
tar -C "$TARGET_STORAGE_DIR" -xzf "$BACKUP/storage.tar.gz"
cd "$(dirname "$0")/../backend"
python3 -m app.backup_verify "$TARGET_ADMIN_URL" "$TARGET_STORAGE_DIR"
