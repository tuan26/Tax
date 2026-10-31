-- Vá các lỗ cô lập tenant tìm thấy khi kiểm tra bằng role ứng dụng (Constitution 3.14, spec AC-E1-017).

-- ------------------------------------------------------------------ khóa ngoại kèm tenant_id
-- Mọi cột tham chiếu tới dòng của bảng khác phải đi qua cặp (tenant_id, id), để dòng của tenant A
-- không trỏ được tới dòng của tenant B dù cả hai id đều có thật.

ALTER TABLE activity_log
    ADD FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id),
    ADD FOREIGN KEY (tenant_id, user_id) REFERENCES app_user(tenant_id, id);
ALTER TABLE audit_event
    ADD FOREIGN KEY (tenant_id, actor_id) REFERENCES app_user(tenant_id, id);
ALTER TABLE item_decision
    ADD FOREIGN KEY (tenant_id, attachment_id) REFERENCES attachment(tenant_id, id),
    ADD FOREIGN KEY (tenant_id, run_id) REFERENCES grouping_run(tenant_id, id),
    ADD FOREIGN KEY (tenant_id, user_id) REFERENCES app_user(tenant_id, id);
ALTER TABLE message_group
    ADD FOREIGN KEY (tenant_id, run_id) REFERENCES grouping_run(tenant_id, id);
ALTER TABLE record
    ADD FOREIGN KEY (tenant_id, supersedes_id) REFERENCES record(tenant_id, id);
ALTER TABLE match
    ADD FOREIGN KEY (tenant_id, user_id) REFERENCES app_user(tenant_id, id);

-- Mảng id không đặt khóa ngoại được: kiểm tra bằng trigger. Trigger chạy với quyền của người gọi nên
-- RLS vẫn áp dụng: id của tenant khác không thấy được, nên bị coi là không tồn tại.
CREATE FUNCTION check_target_groups() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.target_group_ids IS NOT NULL AND EXISTS (
        SELECT 1 FROM unnest(NEW.target_group_ids) AS t(id)
        WHERE NOT EXISTS (SELECT 1 FROM message_group g WHERE g.tenant_id = NEW.tenant_id AND g.id = t.id)
    ) THEN
        RAISE EXCEPTION 'target_group_ids tham chiếu nhóm không thuộc tenant hiện tại' USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER item_decision_target_groups BEFORE INSERT OR UPDATE OF target_group_ids ON item_decision
    FOR EACH ROW EXECUTE FUNCTION check_target_groups();

-- ------------------------------------------------------------------ hàm chạy với quyền nâng cao
-- PostgreSQL mặc định cho PUBLIC quyền EXECUTE trên mọi hàm mới. Thu hồi, rồi cấp đúng role cần.
-- tax_app:    role của API, truy cập dữ liệu trong tenant đã đặt.
-- tax_auth:   chỉ dùng cho bước đăng nhập (tìm user theo email trước khi biết tenant).
-- tax_worker: worker nhận việc của mọi tenant; xử lý việc thì đặt tenant của việc đó.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_auth') THEN
        CREATE ROLE tax_auth NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_worker') THEN
        CREATE ROLE tax_worker NOLOGIN;
    END IF;
END $$;
GRANT tax_app TO tax_worker;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE ALL ON FUNCTION auth_lookup(text), session_lookup(text), claim_job(), current_tenant(),
    check_target_groups() FROM PUBLIC;
REVOKE ALL ON FUNCTION auth_lookup(text), claim_job() FROM tax_app;
-- Hàm trigger không cần quyền EXECUTE lúc chạy, nên check_target_groups() không cấp cho ai.
GRANT EXECUTE ON FUNCTION session_lookup(text), current_tenant() TO tax_app;
GRANT EXECUTE ON FUNCTION auth_lookup(text) TO tax_auth;
GRANT EXECUTE ON FUNCTION claim_job() TO tax_worker;

INSERT INTO schema_migration (version) VALUES ('004_tenant_isolation_hardening');
