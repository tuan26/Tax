#!/bin/sh
# Tạo role của app. Chạy tự động một lần khi DB được tạo; chạy lại an toàn (role đã có thì bỏ qua):
#   docker compose ... exec db sh /docker-entrypoint-initdb.d/10-roles.sh
# Ba role đăng nhập, không superuser, không BYPASSRLS, mỗi role chỉ có quyền nó cần:
#   tax_app_login    API: dữ liệu trong tenant đã đặt
#   tax_auth_login   bước đăng nhập: chỉ gọi được auth_lookup, không đọc được bảng nào
#   tax_worker_login worker: như API, thêm quyền nhận việc của mọi tenant (claim_job)
# Mật khẩu được truyền qua biến psql và trích dẫn bằng format(%L), nên chứa ký tự đặc biệt vẫn an toàn.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
     -v app_pw="$APP_DB_PASSWORD" -v auth_pw="$AUTH_DB_PASSWORD" -v worker_pw="$WORKER_DB_PASSWORD" <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_app') THEN CREATE ROLE tax_app NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_auth') THEN CREATE ROLE tax_auth NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_worker') THEN CREATE ROLE tax_worker NOLOGIN; END IF;
END $$;
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %L IN ROLE %I', r.login, r.pw, r.grp)
FROM (VALUES ('tax_app_login', :'app_pw', 'tax_app'),
             ('tax_auth_login', :'auth_pw', 'tax_auth'),
             ('tax_worker_login', :'worker_pw', 'tax_worker')) AS r(login, pw, grp)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.login) \gexec
SQL
