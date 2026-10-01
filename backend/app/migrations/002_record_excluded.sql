-- Kế toán loại một giao dịch khỏi sổ (khách gửi nhầm, chứng từ của hộ khác). Không xóa: bản ghi giữ
-- nguyên với trạng thái EXCLUDED, các item gốc chuyển thành 'không thuộc giao dịch nào' có lý do.
ALTER TABLE record DROP CONSTRAINT record_status_check;
ALTER TABLE record ADD CONSTRAINT record_status_check CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'MERGED', 'EXCLUDED'));
ALTER TABLE record ADD COLUMN excluded_reason text;
INSERT INTO schema_migration (version) VALUES ('002_record_excluded');
