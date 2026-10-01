# Backend pilot

FastAPI + PostgreSQL. Lõi nghiệp vụ (`app/domain/`) là Python thuần, không phụ thuộc DB, và được
chấm bằng bộ spec trong `../spec/`.

## Chạy test

```bash
pip install -r requirements.txt
# Test lõi nghiệp vụ và bộ spec, không cần DB:
python -m pytest tests/test_parsers.py tests/test_spec_suite.py
# Toàn bộ, kể cả test tích hợp và release gate, cần một PostgreSQL 16 với quyền superuser:
TEST_PG_ADMIN_URL="postgresql://postgres@/postgres?host=/tmp&port=5432" python -m pytest
```

## Chạy app

```bash
export ADMIN_DATABASE_URL=postgresql://owner@db/tax        # role sở hữu schema
python -m app.cli migrate
psql "$ADMIN_DATABASE_URL" -c "CREATE ROLE tax_app_login LOGIN PASSWORD '...' IN ROLE tax_app"
python -m app.cli create-tenant "Văn phòng kế toán A"     # in ra tenant_id
python -m app.cli create-user <tenant_id> ketoan@example.com "Tên kế toán"

export DATABASE_URL=postgresql://tax_app_login:...@db/tax  # role của app, không phải superuser
export STORAGE_DIR=/data/storage
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m app.worker                                       # xử lý lại đợt nhập bị lỗi
```

`FOREIGN_AI_ENABLED` mặc định tắt. Chỉ bật khi đã có ý kiến pháp lý về pipeline hybrid.
`OCR_PROVIDER` mặc định `none`: ảnh vào hàng chờ để kế toán nhập. `tesseract` có sẵn làm mốc so sánh; chọn provider cho pilot bằng spike trong `../tools/ocr_spike/`.

## Pilot release gate

| Gate | Kiểm bằng | Trạng thái |
|---|---|---|
| 1. Dữ liệu gốc chỉ thêm | `test_raw_data_is_append_only`, `test_decisions_only_superseded_never_rewritten`, `test_storage_never_overwrites` | Qua |
| 2. Spec gom tin, 0 lần tự ghép sai | `tests/test_spec_suite.py` (22 ca: 20 Zalo API, 2 nhập tay) | Qua |
| 3. 100% thao tác ghi có audit | `test_every_write_is_audited` | Qua |
| 4. Cô lập tenant | `test_tenant_isolation_api`, `test_tenant_isolation_db`, `test_app_role_is_not_superuser` | Qua |
| 5. Backup và restore | `tests/test_backup_restore.py` (khôi phục thật, backup bị sửa thì từ chối, thiếu file thì phát hiện) | Qua |
| 6. AI nước ngoài fail-closed | `test_foreign_ai_fail_closed`, `test_default_config_disables_foreign_ai` | Qua |
| 7. OCR lỗi giảm cấp an toàn | `tests/test_ocr_degradation.py` (lỗi, quá thời gian, trả về rác, độ tin cậy thấp) | Qua |

Gate 5 dùng `ops/backup.sh` và `ops/restore.sh`. Bước kiểm tra sau khôi phục (`app/backup_verify.py`)
xác nhận file gốc khớp sha256, trigger chỉ-thêm và audit còn đủ, RLS còn bật FORCE.

Gate 7: OCR lỗi ở một ảnh không làm hỏng lượt xử lý; ảnh vẫn thành giao dịch chờ duyệt với file gốc
còn nguyên; giá trị OCR dưới 0,6 chỉ là gợi ý, không thành giá trị; `review.finding_inputs` trả về None
cho mọi bản ghi chưa chắc, nên rule tuần 2 không thể sinh phát hiện từ dữ liệu đoán.

Các đảm bảo nằm ở tầng DB (`app/migrations/001_init.sql`), không phụ thuộc code API:
trigger chặn sửa/xóa dữ liệu gốc (kể cả với role quản trị), trigger audit cho mọi INSERT/UPDATE
trên bảng nghiệp vụ, Row Level Security theo tenant với `FORCE`, khóa ngoại kép `(tenant_id, id)`
để không tham chiếu chéo tenant.

Deploy pilot: xem `../docs/deploy.md`.

Bảng vận hành không có audit: `user_session`, `processing_job`, `activity_log`.

## Chỉ số pilot

```bash
ADMIN_DATABASE_URL=... python -m app.metrics [customer_id]
```

Tách theo `source_type` (ZALO_API, ZALO_MANUAL, ...). Đọc STOR cùng silent_restructure_rate:

| Chỉ số | Ý nghĩa |
|---|---|
| `STOR` | Giao dịch trong sổ mà engine tự tổ chức đúng, kế toán không phải gán, tách, gộp hay chọn ứng viên |
| `silent_restructure_rate` | Quyết định CONFIDENT của engine bị kế toán thay. Chỉ số an toàn: engine đoán bừa thì STOR tăng nhưng chỉ số này tăng theo |
| `review_rate` | Quyết định engine đưa vào hàng chờ |
| `ai_wrong_field_rate` | Bản ghi đã xác nhận có loại, số tiền hoặc ngày AI đưa ra khác số kế toán chốt (không tính trường AI để trống) |
| `excluded:<lý do>` | Giao dịch kế toán loại khỏi sổ, theo lý do |
| `active_minutes_by_customer` | Số phút có thao tác trên từng hộ (từ nhịp hoạt động của giao diện) |

## Cấu trúc

- `app/domain/`: đọc số tiền, ngày, gom tin, chuẩn hóa bản ghi, bộ chấm điểm.
- `app/pipeline.py`: DB ↔ lõi. Quyết định đã có không bao giờ bị engine ghi đè.
- `app/review.py`: thao tác của kế toán. Chỉ thêm quyết định mới, đánh dấu quyết định cũ hết hiệu lực.
- `app/domain/rules.py`: rule DQ-01 (khoản chi chưa có chứng từ đi kèm), DQ-02 (có thể trùng), DQ-03 (chứng từ
  không có ngày, số khách nhắn khác số đã chốt). Chỉ chạy trên bản ghi đã xác nhận hoặc đủ chắc.
- `app/findings.py`: phát hiện, ghép tay, đóng và mở lại, tin nhắn đòi chứng từ.
- `app/api.py`: HTTP API. `app/ai_outbound.py`: cổng duy nhất ra AI nước ngoài.
