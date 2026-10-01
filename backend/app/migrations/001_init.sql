-- Schema pilot. Chạy bằng role sở hữu schema; app kết nối bằng role tax_app.
--
-- Ba đảm bảo nằm ở DB, không phụ thuộc code API:
-- 1. Dữ liệu gốc chỉ được thêm: trigger chặn UPDATE/DELETE, tax_app không có quyền DELETE.
-- 2. Mọi thao tác ghi đều có audit: trigger ghi audit_event cho mọi INSERT/UPDATE.
-- 3. Cô lập tenant: Row Level Security theo app.tenant_id; chưa đặt tenant thì không thấy gì.

CREATE TABLE schema_migration (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());

-- ------------------------------------------------------------------ tenant, user, session

CREATE TABLE tenant (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app_user (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    email           text NOT NULL UNIQUE,
    display_name    text NOT NULL,
    password_hash   text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id)
);

CREATE TABLE user_session (
    token_hash  text PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    user_id     uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    FOREIGN KEY (tenant_id, user_id) REFERENCES app_user(tenant_id, id)
);

-- ------------------------------------------------------------------ hộ kinh doanh

CREATE TABLE customer (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenant(id),
    name                 text NOT NULL,
    timezone             text NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    business_day_cutoff  text NOT NULL DEFAULT '04:00' CHECK (business_day_cutoff ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'),
    created_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id)
);

-- ------------------------------------------------------------------ dữ liệu gốc (chỉ thêm)

CREATE TABLE import_batch (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL,
    customer_id    uuid NOT NULL,
    source_type    text NOT NULL CHECK (source_type IN ('ZALO_API', 'ZALO_MANUAL', 'FILE_UPLOAD', 'MANUAL_ENTRY')),
    business_date  date,
    note           text,
    created_by     uuid,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id)
);

CREATE TABLE message (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL,
    customer_id      uuid NOT NULL,
    batch_id         uuid,
    external_id      text NOT NULL,
    conversation_id  text NOT NULL,
    sender_id        text,
    sent_at          timestamptz,
    business_date    date,
    sequence         integer,
    kind             text NOT NULL CHECK (kind IN ('text', 'image', 'file', 'sticker', 'link', 'voice', 'system', 'deleted', 'unsupported')),
    text             text,
    source_type      text NOT NULL CHECK (source_type IN ('ZALO_API', 'ZALO_MANUAL', 'FILE_UPLOAD', 'MANUAL_ENTRY')),
    provenance       jsonb NOT NULL,
    received_at      timestamptz NOT NULL DEFAULT now(),
    -- Không có giờ gửi thì phải có ngày kinh doanh do kế toán chọn. Không bao giờ đoán giờ gửi.
    CHECK (sent_at IS NOT NULL OR business_date IS NOT NULL),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, customer_id, external_id),
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id),
    FOREIGN KEY (tenant_id, batch_id) REFERENCES import_batch(tenant_id, id)
);

CREATE TABLE attachment (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL,
    message_id   uuid NOT NULL,
    external_id  text NOT NULL,
    kind         text NOT NULL CHECK (kind IN ('image', 'pdf', 'file', 'voice')),
    mime_type    text NOT NULL,
    file_name    text,
    size_bytes   bigint,
    sha256       text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    storage_key  text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (message_id, external_id),
    FOREIGN KEY (tenant_id, message_id) REFERENCES message(tenant_id, id)
);

CREATE TABLE extraction (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL,
    attachment_id  uuid NOT NULL,
    engine         text NOT NULL,
    fields         jsonb NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, attachment_id) REFERENCES attachment(tenant_id, id)
);

CREATE TABLE ai_call (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    provider        text NOT NULL,
    destination     text NOT NULL CHECK (destination IN ('domestic', 'foreign')),
    allowed         boolean NOT NULL,
    reason          text NOT NULL,
    payload_sha256  text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ gom nhóm và quyết định

CREATE TABLE grouping_run (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL,
    customer_id     uuid NOT NULL,
    engine_version  text NOT NULL,
    message_count   integer NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id)
);

CREATE TABLE message_group (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL,
    customer_id           uuid NOT NULL,
    run_id                uuid,
    kind                  text NOT NULL CHECK (kind IN ('document', 'self_declared')),
    status                text NOT NULL CHECK (status IN ('CONFIDENT', 'AMBIGUOUS')),
    segment               text,
    facts                 jsonb NOT NULL DEFAULT '{}',
    partition_candidates  jsonb,
    created_by            text NOT NULL CHECK (created_by IN ('engine', 'user')),
    created_at            timestamptz NOT NULL DEFAULT now(),
    superseded_at         timestamptz,
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id)
);

-- Mỗi item có đúng một quyết định đang hiệu lực cho mỗi vai trò. Sửa = thêm quyết định mới và
-- đánh dấu quyết định cũ hết hiệu lực, không bao giờ sửa nội dung quyết định cũ.
CREATE TABLE item_decision (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL,
    customer_id        uuid NOT NULL,
    run_id             uuid,
    item_ref           text NOT NULL,
    message_id         uuid NOT NULL,
    attachment_id      uuid,
    decision           text NOT NULL CHECK (decision IN ('anchor', 'link', 'unmatched')),
    role               text,
    status             text NOT NULL CHECK (status IN ('CONFIDENT', 'AMBIGUOUS', 'UNMATCHED')),
    group_id           uuid,
    target_group_ids   uuid[] NOT NULL DEFAULT '{}',
    candidates         jsonb,
    reason             text,
    needs_review       boolean NOT NULL DEFAULT false,
    note               text,
    data               jsonb NOT NULL DEFAULT '{}',
    decided_by         text NOT NULL CHECK (decided_by IN ('engine', 'user')),
    user_id            uuid,
    created_at         timestamptz NOT NULL DEFAULT now(),
    superseded_at      timestamptz,
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id),
    FOREIGN KEY (tenant_id, message_id) REFERENCES message(tenant_id, id),
    FOREIGN KEY (tenant_id, group_id) REFERENCES message_group(tenant_id, id)
);
CREATE INDEX item_decision_active ON item_decision (customer_id, item_ref) WHERE superseded_at IS NULL;

-- ------------------------------------------------------------------ bản ghi thu chi

CREATE TABLE record (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL,
    customer_id          uuid NOT NULL,
    group_id             uuid NOT NULL,
    fields_ai            jsonb NOT NULL,
    decision_confidence  jsonb NOT NULL,
    fields_confirmed     jsonb,
    evidence_items       jsonb NOT NULL,
    evidence_kind        text NOT NULL,
    sent_date            date,
    review_required      boolean NOT NULL,
    review_reasons       jsonb NOT NULL DEFAULT '[]',
    description          text,
    status               text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'MERGED')),
    supersedes_id        uuid,
    confirmed_by         uuid,
    confirmed_at         timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (group_id),
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id),
    FOREIGN KEY (tenant_id, group_id) REFERENCES message_group(tenant_id, id)
);

-- ------------------------------------------------------------------ vận hành

CREATE TABLE processing_job (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL,
    customer_id  uuid NOT NULL,
    status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'done', 'failed')),
    error        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    started_at   timestamptz,
    finished_at  timestamptz,
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id)
);

CREATE TABLE activity_log (
    id           bigserial PRIMARY KEY,
    tenant_id    uuid NOT NULL REFERENCES tenant(id),
    user_id      uuid NOT NULL,
    customer_id  uuid,
    screen       text NOT NULL,
    at           timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------ audit

CREATE TABLE audit_event (
    id          bigserial PRIMARY KEY,
    tenant_id   uuid NOT NULL,
    actor_kind  text NOT NULL,
    actor_id    uuid,
    table_name  text NOT NULL,
    row_id      text NOT NULL,
    action      text NOT NULL,
    old_row     jsonb,
    new_row     jsonb,
    at          timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX audit_event_row ON audit_event (table_name, row_id);

CREATE FUNCTION audit_row() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    actor text := nullif(current_setting('app.user_id', true), '');
BEGIN
    INSERT INTO audit_event (tenant_id, actor_kind, actor_id, table_name, row_id, action, old_row, new_row)
    VALUES (
        NEW.tenant_id,
        coalesce(nullif(current_setting('app.actor_kind', true), ''), 'system'),
        actor::uuid,
        TG_TABLE_NAME,
        NEW.id::text,
        TG_OP,
        CASE WHEN TG_OP = 'UPDATE' THEN to_jsonb(OLD) END,
        to_jsonb(NEW)
    );
    RETURN NULL;
END $$;

CREATE FUNCTION forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Bảng % chỉ được thêm, không được % ', TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
END $$;

-- Chỉ cho phép đổi superseded_at từ NULL sang có giá trị; mọi cột khác bất biến.
CREATE FUNCTION allow_only_supersede() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Bảng % không được xóa', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.superseded_at IS NOT NULL
       OR (to_jsonb(NEW) - 'superseded_at' - 'status') <> (to_jsonb(OLD) - 'superseded_at' - 'status')
       OR (TG_TABLE_NAME = 'item_decision' AND NEW.status <> OLD.status) THEN
        RAISE EXCEPTION 'Bảng %: chỉ được đánh dấu hết hiệu lực', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['import_batch', 'message', 'attachment', 'extraction', 'ai_call', 'grouping_run', 'audit_event'] LOOP
        EXECUTE format('CREATE TRIGGER %I_append_only BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION forbid_mutation()', t, t);
    END LOOP;
    FOREACH t IN ARRAY ARRAY['message_group', 'item_decision'] LOOP
        EXECUTE format('CREATE TRIGGER %I_supersede_only BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION allow_only_supersede()', t, t);
    END LOOP;
    FOREACH t IN ARRAY ARRAY['customer', 'import_batch', 'message', 'attachment', 'extraction', 'ai_call', 'grouping_run',
                             'message_group', 'item_decision', 'record'] LOOP
        EXECUTE format('CREATE TRIGGER %I_audit AFTER INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION audit_row()', t, t);
    END LOOP;
    -- Không có bảng nghiệp vụ nào được xóa.
    FOREACH t IN ARRAY ARRAY['customer', 'record'] LOOP
        EXECUTE format('CREATE TRIGGER %I_no_delete BEFORE DELETE ON %I FOR EACH ROW EXECUTE FUNCTION forbid_mutation()', t, t);
    END LOOP;
END $$;

-- ------------------------------------------------------------------ cô lập tenant

CREATE FUNCTION current_tenant() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['app_user', 'user_session', 'customer', 'import_batch', 'message', 'attachment', 'extraction',
                             'ai_call', 'grouping_run', 'message_group', 'item_decision', 'record', 'processing_job',
                             'activity_log', 'audit_event'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I_tenant ON %I USING (tenant_id = current_tenant()) WITH CHECK (tenant_id = current_tenant())', t, t);
    END LOOP;
END $$;
ALTER TABLE tenant ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_self ON tenant USING (id = current_tenant());

-- Đăng nhập cần tìm user trước khi biết tenant: hàm SECURITY DEFINER chỉ trả đúng một dòng theo email.
CREATE FUNCTION auth_lookup(p_email text)
RETURNS TABLE (user_id uuid, tenant_id uuid, password_hash text, display_name text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public SET row_security = off AS $$
    SELECT id, tenant_id, password_hash, display_name FROM app_user WHERE email = lower(p_email)
$$;

CREATE FUNCTION session_lookup(p_token_hash text)
RETURNS TABLE (user_id uuid, tenant_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public SET row_security = off AS $$
    SELECT user_id, tenant_id FROM user_session
    WHERE token_hash = p_token_hash AND revoked_at IS NULL AND expires_at > now()
$$;

-- ------------------------------------------------------------------ quyền cho role của app

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tax_app') THEN
        CREATE ROLE tax_app NOLOGIN;
    END IF;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM tax_app;
GRANT SELECT ON tenant TO tax_app;
GRANT SELECT, INSERT ON app_user, import_batch, message, attachment, extraction, ai_call, grouping_run, audit_event,
    activity_log TO tax_app;
GRANT SELECT, INSERT, UPDATE ON user_session, customer, message_group, item_decision, record, processing_job TO tax_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO tax_app;
GRANT EXECUTE ON FUNCTION auth_lookup(text), session_lookup(text), current_tenant() TO tax_app;


-- Worker cần nhận việc của mọi tenant: hàm SECURITY DEFINER chỉ trả về id, không trả dữ liệu.
CREATE FUNCTION claim_job()
RETURNS TABLE (job_id uuid, tenant_id uuid, customer_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public SET row_security = off AS $$
BEGIN
    RETURN QUERY
    UPDATE processing_job j SET status = 'running', started_at = now(), error = NULL
    WHERE j.id = (SELECT id FROM processing_job WHERE status IN ('pending', 'failed')
                  ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
    RETURNING j.id, j.tenant_id, j.customer_id;
END $$;
GRANT EXECUTE ON FUNCTION claim_job() TO tax_app;

INSERT INTO schema_migration (version) VALUES ('001_init');
