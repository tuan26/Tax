# Deploy môi trường pilot

Một máy chủ duy nhất đặt tại Việt Nam. Không cần Kubernetes, autoscaling hay HA cho pilot
2 kế toán × 2–3 hộ × 2 tuần.

```
Internet ──HTTPS──▶ Caddy ──▶ Next.js ──/api──▶ FastAPI ──▶ PostgreSQL
                                                   │
                                     Worker ───────┤──▶ Kho file gốc (volume)
```

## 1. Máy chủ

- VM Linux tại Việt Nam (Viettel IDC, FPT Cloud, VNG Cloud, …): 2 vCPU, 4 GB RAM, 60 GB SSD là đủ.
- Một tên miền trỏ bản ghi A về IP của máy. Mở cổng 80 và 443.
- Cài Docker Engine và Docker Compose plugin.

## 2. Cấu hình

```bash
git clone <repo> tax && cd tax
cp deploy/.env.example deploy/.env
# Sửa deploy/.env: DOMAIN, bốn mật khẩu DB (dài, ngẫu nhiên, khác nhau)
```

`FOREIGN_AI_ENABLED` luôn là `false` trong compose. Không gửi dữ liệu khách hàng tới dịch vụ AI nước ngoài trong giai đoạn hiện tại (Constitution mục 3.13); chỉ đổi khi có đề xuất nêu nhà cung cấp, nơi xử lý, loại dữ liệu, chi phí, pháp lý và đã được duyệt, cập nhật Constitution.

## 3. Chạy

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
docker compose -f deploy/docker-compose.yml --env-file deploy/.env ps
```

Lần đầu chạy, `db` tạo role của app (`deploy/init-roles.sh`: role đăng nhập riêng cho API, bước đăng nhập và
worker), `migrate` tạo schema, rồi backend, worker,
frontend và Caddy khởi động. Caddy tự xin chứng chỉ HTTPS cho `DOMAIN`.

## 4. Tạo văn phòng và tài khoản kế toán

```bash
C="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
$C run --rm ops python -m app.cli create-tenant "Văn phòng kế toán A"     # in ra tenant_id
$C run --rm -e PASSWORD='mat-khau-tam-thoi' ops \
   python -m app.cli create-user <tenant_id> ketoan@vanphong-a.vn "Tên kế toán"
```

Mỗi văn phòng kế toán là một tenant. Dữ liệu giữa các tenant bị cô lập ở tầng DB (Row Level Security).
Mật khẩu owner chỉ có trong service `ops`, không có trong backend và worker đang chạy.

## 5. Trước khi đưa dữ liệu thật vào: chạy release gate

Trên máy phát triển, với một PostgreSQL 16 thử nghiệm:

```bash
cd backend && TEST_PG_ADMIN_URL=postgresql://postgres@localhost/postgres python -m pytest
```

Toàn bộ test phải qua, gồm 7 gate trong `backend/README.md`. Sau đó trên máy chủ thật, làm một lần
diễn tập backup và khôi phục (mục 6) trước ngày đầu pilot.

## 6. Sao lưu và khôi phục

Sao lưu hằng ngày bằng cron trên máy chủ:

```cron
30 2 * * * cd /srv/tax && docker compose -f deploy/docker-compose.yml --env-file deploy/.env run --rm -T -e BACKUP_DIR=/data/backups ops /srv/ops/backup.sh >> /var/log/tax-backup.log 2>&1
```

Bản sao lưu nằm trong volume `backups`. Chép thêm ra ngoài máy chủ (object storage trong nước) hằng ngày.

Diễn tập khôi phục, ít nhất một lần trước pilot và một lần giữa pilot:

```bash
$C exec db createdb -U owner tax_restore_drill
$C run --rm -e BACKUP=/data/backups/<thời điểm> \
        -e TARGET_ADMIN_URL=postgresql://owner:<mật khẩu>@db/tax_restore_drill \
        -e TARGET_STORAGE_DIR=/tmp/restore-drill ops /srv/ops/restore.sh
```

Kết quả phải in `RESTORE ĐẠT`: file gốc khớp sha256, trigger chỉ-thêm và audit còn đủ, RLS còn bật.

## 7. Theo dõi trong 2 tuần pilot

```bash
$C logs -f backend worker          # lỗi xử lý
$C run --rm ops python -m app.metrics   # STOR, tỷ lệ duyệt, phát hiện hữu ích, số phút theo hộ
```

Người phụ trách xem log mỗi sáng. Lỗi chặn kế toán sửa trong ngày; còn lại đưa vào backlog.

## 8. Cập nhật phiên bản

```bash
git pull
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

`migrate` chạy lại và chỉ áp các migration mới. Sao lưu trước mỗi lần cập nhật.

Khi cập nhật lên bản có migration `004_tenant_isolation_hardening` trên DB đã tạo từ trước: thêm
`AUTH_DB_PASSWORD` và `WORKER_DB_PASSWORD` vào `deploy/.env`, chạy lại `init-roles.sh` (lệnh ở đầu file đó)
để tạo hai role đăng nhập mới, rồi mới `up -d --build`. Không làm bước này thì đăng nhập và worker sẽ lỗi quyền.

## Đã kiểm chứng và chưa kiểm chứng

- Đã kiểm chứng: cấu hình compose hợp lệ; `init-roles.sh` tạo ba role đăng nhập đúng quyền (không superuser,
  không BYPASSRLS), chạy lại không lỗi, mật khẩu có ký tự đặc biệt; migration chạy trên DB mới; backup và
  khôi phục qua `ops/` (test tự động); cô lập tenant bằng role ứng dụng (`backend/tests/test_tenant_isolation.py`).
- Đã kiểm chứng ngày 2026-10-29 trong môi trường phát triển, bằng image build **không có** gói Debian
  (`SYSTEM_PACKAGES=""`): `docker compose up` chạy db, migrate, backend, worker, frontend, Caddy; backend và worker
  không có mật khẩu owner trong biến môi trường; tạo tenant và user qua `run --rm ops`; đăng nhập qua Caddy;
  smoke test giao diện đi hết đăng nhập, thêm hộ, nhập dữ liệu, duyệt hàng chờ, mở màn hình việc cần xử lý.
- Chưa kiểm chứng: image đầy đủ có Tesseract và `postgresql-client`, vì môi trường phát triển không tải được gói
  Debian (`deb.debian.org` bị chặn). Do đó chưa chạy được OCR, sao lưu `pg_dump` trong container, và phần
  smoke test cần OCR (ghép chuyển khoản với hóa đơn). Cần chạy `docker compose ... up --build`, `npm run smoke`
  và diễn tập sao lưu, khôi phục trên máy chủ thật, với dữ liệu giả lập, trước khi đưa dữ liệu thật vào.
