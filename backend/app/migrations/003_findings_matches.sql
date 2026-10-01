-- Phát hiện (finding) từ rule và ghép chứng từ (match). Vòng khép kín:
-- phát hiện mở → yêu cầu khách → kế toán ghép chứng từ và xác nhận → phát hiện đóng.
-- Phát hiện chỉ đóng bằng quyết định của kế toán, hoặc khi điều kiện không còn (ghi rõ lý do).

CREATE TABLE match (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL,
    customer_id      uuid NOT NULL,
    payment_record_id   uuid NOT NULL,   -- khoản chi cần chứng từ (ảnh chuyển khoản, chi tự khai)
    document_record_id  uuid NOT NULL,   -- chứng từ đi kèm
    match_type       text NOT NULL CHECK (match_type IN ('payment_document')),
    evidence         jsonb NOT NULL,
    status           text NOT NULL CHECK (status IN ('CONFIRMED', 'UNDONE')),
    created_by       text NOT NULL CHECK (created_by IN ('user', 'engine')),
    user_id          uuid,
    created_at       timestamptz NOT NULL DEFAULT now(),
    undone_at        timestamptz,
    undone_by        uuid,
    UNIQUE (tenant_id, id),
    CHECK (payment_record_id <> document_record_id),
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id),
    FOREIGN KEY (tenant_id, payment_record_id) REFERENCES record(tenant_id, id),
    FOREIGN KEY (tenant_id, document_record_id) REFERENCES record(tenant_id, id)
);

CREATE TABLE finding (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL,
    customer_id      uuid NOT NULL,
    rule_id          text NOT NULL,
    rule_version     text NOT NULL,
    fingerprint      text NOT NULL,
    severity         text NOT NULL CHECK (severity IN ('check', 'confirm')),
    record_id        uuid NOT NULL,
    title            text NOT NULL,
    detail           text NOT NULL,
    amount           bigint,
    evidence         jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) > 0),
    status           text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'REQUESTED', 'RESOLVED', 'DISMISSED')),
    resolution       text CHECK (resolution IN ('matched', 'has_document', 'no_longer_applies')),
    resolution_note  text,
    match_id         uuid,
    requested_at     timestamptz,
    decided_at       timestamptz,
    decided_by       uuid,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (customer_id, fingerprint),
    -- Đóng phát hiện luôn phải có lý do; bỏ qua phải có ghi chú của kế toán.
    CHECK (status <> 'RESOLVED' OR resolution IS NOT NULL),
    CHECK (status <> 'DISMISSED' OR (resolution_note IS NOT NULL AND length(trim(resolution_note)) > 0)),
    CHECK (resolution <> 'matched' OR match_id IS NOT NULL),
    FOREIGN KEY (tenant_id, customer_id) REFERENCES customer(tenant_id, id),
    FOREIGN KEY (tenant_id, record_id) REFERENCES record(tenant_id, id),
    FOREIGN KEY (tenant_id, match_id) REFERENCES match(tenant_id, id)
);
CREATE INDEX finding_customer_status ON finding (customer_id, status);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['finding', 'match'] LOOP
        EXECUTE format('CREATE TRIGGER %I_audit AFTER INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION audit_row()', t, t);
        EXECUTE format('CREATE TRIGGER %I_no_delete BEFORE DELETE ON %I FOR EACH ROW EXECUTE FUNCTION forbid_mutation()', t, t);
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I_tenant ON %I USING (tenant_id = current_tenant()) WITH CHECK (tenant_id = current_tenant())', t, t);
    END LOOP;
END $$;
GRANT SELECT, INSERT, UPDATE ON finding, match TO tax_app;

INSERT INTO schema_migration (version) VALUES ('003_findings_matches');
