#!/usr/bin/env bash
# Sao lưu DB và kho file gốc. DB trước, file sau: file luôn được ghi trước khi dòng DB commit,
# nên mọi attachment có trong bản dump đều có file trong bản sao kho.
#
#   ADMIN_DATABASE_URL=... STORAGE_DIR=... BACKUP_DIR=... ops/backup.sh
set -euo pipefail
: "${ADMIN_DATABASE_URL:?}" "${STORAGE_DIR:?}" "${BACKUP_DIR:?}"
ts=$(date -u +%Y%m%dT%H%M%SZ)
out="$BACKUP_DIR/$ts"
mkdir -p "$out"
pg_dump --format=custom --file="$out/db.dump" "$ADMIN_DATABASE_URL"
tar -C "$STORAGE_DIR" -czf "$out/storage.tar.gz" .
(cd "$out" && sha256sum db.dump storage.tar.gz > SHA256SUMS)
echo "$out"
