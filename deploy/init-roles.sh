#!/bin/sh
# Chạy một lần khi DB được tạo. Role của app không phải superuser, không có BYPASSRLS.
# Mật khẩu được truyền qua biến psql và trích dẫn bằng :'pw', nên chứa ký tự đặc biệt vẫn an toàn.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -v pw="$APP_DB_PASSWORD" -v login_role="${APP_DB_LOGIN_ROLE:-tax_app_login}" <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_app') THEN CREATE ROLE tax_app NOLOGIN; END IF;
END $$;
CREATE ROLE :"login_role" LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD :'pw' IN ROLE tax_app;
SQL
