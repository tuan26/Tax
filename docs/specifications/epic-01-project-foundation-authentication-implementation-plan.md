# Draft Implementation Plan — Epic 1: Project Foundation & Authentication

**Project**: Accounting Intake Agent  
**Epic**: Project Foundation & Authentication  
**Input spec**: `docs/specifications/epic-01-project-foundation-authentication-spec.md`  
**Constitution alignment**: `docs/overview/constitution.md` v`4.0.0.0`  
**Status**: Draft plan (design-level only, no code/migration)

---

## 1) Planning Scope

Plan này chỉ áp dụng cho Epic 1 và chuẩn bị nền tảng cho Epic 2–10:

1. Authentication/Authorization cho dashboard users (Accountant/Manager/Admin).
2. Session/token model có server-side tracking.
3. Security baseline: lockout/rate-limit/cookie+CSRF/secrets hygiene.
4. Audit envelope, error code catalog, reason code catalog.
5. Correlation/idempotency foundations phục vụ workflow end-to-end.
6. Nền tảng multi-tenant: cô lập tenant bằng PostgreSQL RLS (spec DP-005, FR-E1-025).

Không bao gồm OCR, intent, workflow xác minh người gửi ↔ Customer chi tiết, document validation nghiệp vụ hoặc export logic.

---

## 2) Architecture (Modular Monolith)

### 2.1 Target Architecture

1. **Backend**: FastAPI modular monolith.
2. **Database**: PostgreSQL.
3. **Frontend**: Next.js dashboard.
4. **Local runtime**: Docker Compose.

### 2.2 Module Boundaries (Backend)

1. `identity_module`
   - User identity, role mapping, account status.
2. `auth_module`
   - Login, refresh, logout, session/revocation, lockout logic.
3. `authz_module`
   - RBAC policies + middleware guards.
4. `security_module`
   - Rate limit adapter, CSRF validation, secret/config validation hooks.
5. `audit_module`
   - Audit event writer + reason code validation.
6. `platform_module`
   - Correlation ID, idempotency primitives, error response standardization.

### 2.3 Integration Style

1. Internal sync calls giữa modules qua service interfaces rõ ràng.
2. Shared kernel chỉ chứa types/contracts chuẩn (`AuthErrorCode`, `AuditReasonCode`, `ActorContext`).
3. No direct cross-module DB writes ngoài repository boundary.

---

## 3) Components

### 3.1 Backend Components

1. **Auth API Controller**
   - `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`.
2. **Session Service**
   - Issue/rotate/revoke token + session tracking server-side.
3. **Lockout Service**
   - Đếm thất bại theo account/time-window và enforce lock.
4. **Rate Limit Guard**
   - Enforce theo IP và account tại login/refresh endpoints.
5. **Authorization Middleware**
   - Guard theo role/policy cho protected endpoints.
6. **Audit Publisher**
   - Ghi audit chuẩn actor/action/resource/result/correlation/reason.
7. **Error Mapper**
   - Chuẩn hóa lỗi về catalog `AUTH_*`, `AUTHZ_*`.

### 3.2 Frontend Components (Next.js)

1. **Auth client flows**
   - Login form, logout action, session-expired handling.
2. **Route guards**
   - Protect dashboard pages theo role.
3. **CSRF token handling layer**
   - Tương thích cơ chế CSRF backend chọn.
4. **Error display adapter**
   - Hiển thị lỗi thân thiện, không rò rỉ thông tin account existence.

---

## 4) Data Model (Design-Level)

> Mức thiết kế logical; chưa tạo migration.

1. **users**
   - `id`, `email_or_username`, `password_hash`, `status`, `created_at`, `updated_at`.
2. **user_roles**
   - `user_id`, `role` (`ADMIN|MANAGER|ACCOUNTANT`), `scope_ref` (optional for future assignment).
3. **manager_customer_assignments**
   - `manager_user_id`, `customer_id`, `assigned_by_admin_id`, `assigned_at`, `status`.
4. **auth_sessions**
   - `id`, `user_id`, `session_status`, `issued_at`, `expires_at`, `revoked_at`, `last_seen_at`, `device_info`, `ip_snapshot`.
5. **refresh_token_store**
   - `session_id`, `refresh_token_hash`, `token_version`, `expires_at`, `rotated_from_version`, `revoked_at`.
6. **login_failure_counters**
   - `account_key`, `window_start`, `failure_count`, `locked_until`.
7. **ip_rate_limit_counters**
   - `ip_address_hash`, `window_start`, `attempt_count`, `blocked_until`.
8. **password_reset_tokens**
   - `user_id`, `reset_token_hash`, `issued_at`, `expires_at`, `used_at`, `request_correlation_id`.
9. **audit_events**
   - `event_id`, `timestamp`, `actor_id`, `actor_role`, `action`, `resource_type`, `resource_id`, `result`, `reason_code`, `correlation_id`, `metadata_json`.
10. **idempotency_records** (foundation)
   - `idempotency_key`, `scope`, `request_fingerprint`, `status`, `response_snapshot`, `expires_at`.

Design notes:
1. Refresh token lưu hash (không plaintext).
2. Session + refresh tách bảng để rotation/revoke rõ ràng.
3. Manager scoping áp dụng assignment-based access control ngay từ Epic 1 foundation.
4. Mọi bảng trên (trừ counter chỉ chứa khóa đã băm không gắn tenant, nếu có) mang `tenant_id`, bật và FORCE RLS; khóa ngoại giữa bảng tenant dùng cặp `(tenant_id, id)` để không tham chiếu được sang tenant khác.

---

## 5) API Contracts (Draft)

### 5.1 Auth Endpoints

1. `POST /api/v1/auth/login`
   - Input: credentials + optional client metadata.
   - Output success: auth context + role summary; token qua secure cookie.
   - Errors: `AUTH_INVALID_CREDENTIALS`, `AUTH_ACCOUNT_LOCKED`, `AUTH_RATE_LIMITED`.

2. `POST /api/v1/auth/refresh`
   - Input: refresh cookie + CSRF proof.
   - Output: refreshed access + rotated refresh cookie.
   - Errors: `AUTH_TOKEN_EXPIRED`, `AUTH_REFRESH_REPLAY_REJECTED`, `AUTH_SESSION_REVOKED`, `AUTH_RATE_LIMITED`.

3. `POST /api/v1/auth/logout`
   - Input: authenticated context.
   - Output: session revoked for current session.

4. `POST /api/v1/auth/logout-all`
   - Input: authenticated context.
   - Output: revoke all active sessions of current user.

### 5.2 Admin Auth Management Endpoints

1. `POST /api/v1/admin/users`
2. `PATCH /api/v1/admin/users/{id}`
3. `PATCH /api/v1/admin/users/{id}/roles`
4. `PATCH /api/v1/admin/users/{id}/status`

All admin endpoints require role `ADMIN`; unauthorized calls return standardized `AUTHZ_*` errors.

### 5.3 Response Envelope

1. Success: `data`, `meta.correlation_id`.
2. Error: `error.code`, `error.message`, `error.details`, `meta.correlation_id`.
3. Message policy: không tiết lộ account existence hoặc thông tin nhạy cảm.

---

## 6) Security Design

### 6.1 Token & Session

1. Access token TTL: 15 phút.
2. Refresh token TTL: tối đa 7 ngày.
3. Server-side session tracking bắt buộc.
4. Refresh token rotation mỗi lần refresh thành công.
5. Revocation support: current session và all sessions.

### 6.2 Storage & Transport

1. Cookie flags: `HttpOnly`, `Secure`, `SameSite`.
2. Không dùng localStorage cho access/refresh token.
3. Hash refresh token trước khi lưu DB.

### 6.3 CSRF Protection

1. Dùng `Signed Double-Submit Cookie Pattern`.
2. CSRF token gắn với session, có chữ ký để kiểm tra integrity.
3. CSRF token truyền qua custom header cho các state-changing endpoints dùng cookie auth.
4. Thiết kế cơ chế cấp token an toàn cho Next.js client mà không lộ secrets.
5. Không thêm Redis chỉ để quản lý CSRF.

### 6.4 Brute-force & Abuse Protection

1. Lockout: 5 failed attempts / 15 phút / account.
2. Lock duration: 15 phút.
3. Rate limit theo IP và account.
4. Đồng nhất message lỗi login để chống account enumeration.
5. IP login limit mặc định: 30 attempts / 5 phút, vượt ngưỡng trả HTTP 429.
6. Refresh token endpoint và các endpoint nhạy cảm có rate limit riêng.
7. Ngưỡng bảo mật cấu hình qua environment variables.
8. Không khóa vĩnh viễn account/IP.

### 6.5 Audit & Logging Safety

1. Ghi audit cho login success/failure, lockout, refresh, revoke, logout, authz denied, role changes.
2. Không log password, secrets, access token, refresh token.
3. Reason codes theo catalog chuẩn của Epic 1.

### 6.6 MFA-readiness

1. Thiết kế auth flow cho phép gắn bước challenge thứ hai sau password phase.
2. Pilot dữ liệu thật phải qua security review và đánh giá MFA cho Admin trước khi mở.

### 6.7 Password Policy & Reset

1. Password tối thiểu 12 ký tự, hỗ trợ passphrase.
2. Hash password bằng Argon2id.
3. Không bắt buộc complexity rule quá cứng (không ép ký tự đặc biệt bắt buộc).
4. Có kiểm tra mật khẩu phổ biến/yếu nếu khả thi trong MVP.
5. Reset password dùng one-time token TTL ngắn, anti-enumeration response.

---

## 7) Task Breakdown (No Code)

### Phase A — Architecture & Contracts

1. Chốt module boundaries và interface contracts.
2. Chốt auth/authz error code catalog.
3. Chốt audit reason code catalog + payload schema.
4. Chốt correlation/idempotency middleware contract.

### Phase B — Security Model Design

1. Chốt token/session lifecycle diagrams.
2. Đóng băng lockout/rate-limit policy parameters qua env configs.
3. Đóng băng cơ chế CSRF Signed Double-Submit + custom header contract.
4. Chốt secret/config governance checklist.

### Phase C — API & Data Design

1. Chốt endpoint contracts (request/response/errors).
2. Chốt logical data model cho users/roles/sessions/tokens/audit.
3. Chốt optimistic concurrency rule cho role updates.

### Phase D — Test Design

1. Viết test matrix cho happy/error/retry/duplicate/concurrency/authorization.
2. Chốt integration scenarios cho auth lifecycle.
3. Chốt audit verification criteria.

### Phase E — Readiness Review

1. Rà soát nhất quán với Constitution v4.0.0.0.
2. Rà soát security baseline trước coding.
3. Ký duyệt Epic 1 implementation-ready checklist.

---

## 8) Dependencies

1. Constitution v4.0.0.0 đã approved.
2. Quyết định token/session/lockout/MFA strategy đã confirmed.
3. Hạ tầng Docker Compose baseline sẵn sàng cho backend/frontend/postgres.
4. Quy tắc vai trò và phân quyền nghiệp vụ đã thống nhất.

External/Deferred:
1. MFA bắt buộc cho Admin (defer sau MVP/pilot readiness review).

---

## 9) Testing Strategy

### 9.1 Unit Tests

1. Password verify + auth policy helpers.
2. Lockout window logic.
3. Token rotation/revocation state transitions.
4. Error-code mapping and reason-code validation.

### 9.2 Integration Tests

1. Login → refresh → logout flow.
2. Replay refresh token rejection.
3. Lockout after failed attempts.
4. Admin-only endpoint authorization.
5. Concurrent role update conflict path.
6. Assignment-based manager access allow/deny cases.
7. Password reset one-time-token lifecycle.

### 9.3 Security-Focused Tests

1. CSRF failure/success cases.
2. Cookie flags validation.
3. Non-enumerating login error responses.
4. Log scrubbing (no secret/token leakage).
5. IP rate limit HTTP 429 behavior.
6. Refresh endpoint-specific rate limiting.
7. Tenant isolation theo AC-E1-017, chạy bằng role ứng dụng (không superuser, không BYPASSRLS): đọc/sửa/xóa/chèn chéo tenant, khóa ngoại sang tenant khác, truy vấn khi chưa đặt tenant, và từng hàm SECURITY DEFINER được cấp cho role ứng dụng.

### 9.4 Audit Verification

1. Verify mandatory fields in every required auth/audit event.
2. Verify correlation_id propagation across request chain.
3. Verify reason_code correctness by event type.

---

## 10) Definition of Done (Epic 1)

Epic 1 được coi là hoàn thành khi:

1. Dashboard auth chỉ cho Accountant/Manager/Admin hoạt động đúng policy.
2. Customer không thể truy cập dashboard endpoints.
3. Access/refresh lifecycle hoạt động theo TTL + rotation + revoke đã chốt.
4. Lockout/rate-limit policy hoạt động đúng ngưỡng đã chốt.
5. Error codes và audit reason codes được chuẩn hóa và tái sử dụng được.
6. Audit logs đạt đủ trường tối thiểu, không chứa secrets/tokens.
7. AC trong spec Epic 1 có test coverage tương ứng (unit/integration/security).
8. Rà soát nhất quán với Constitution v4.0.0.0 đạt yêu cầu.

---

## 11) Technical Decisions Captured in this Plan

1. Modular Monolith là kiến trúc mục tiêu cho MVP.
2. Auth model dùng token + server-side session tracking (PostgreSQL-first, chưa thêm Redis).
3. Cookie-based secure token transport với CSRF protection.
4. Shared code catalogs (`AUTH_*`, `AUTHZ_*`, `AUDIT_*`) là contract xuyên Epic.
5. Security/audit foundations được hoàn tất ở Epic 1 để các Epic sau tái sử dụng.
6. Manager scope enforcement theo assignment-based access và deny-by-default.

## 12) Confirmed Baseline Before Coding

1. CSRF: Signed Double-Submit Cookie Pattern + custom header validation.
2. Password: min 12, passphrase-friendly, Argon2id, one-time reset token TTL ngắn.
3. Manager scope: assignment-based, deny-by-default khi thiếu assignment.
4. Rate-limit: account lockout 5/15 + lock 15; IP 30/5 trả 429; refresh/sensitive endpoints có limit riêng.
5. Taxonomy: `AUTH_*`, `AUTHZ_*`, `AUDIT_*`, mã ổn định độc lập ngôn ngữ.

## 13) Execution-Ready Work Packages (No Code Yet)

### WP-01 Contracts & Catalogs

1. Khóa file chuẩn error taxonomy + audit taxonomy.
2. Khóa response envelope contract cho toàn bộ auth/authz endpoints.
3. Định nghĩa mapping table: exception nội bộ → `AUTH_*`/`AUTHZ_*`/HTTP status.

### WP-02 Session & Token Mechanics

1. Chốt state machine cho `auth_sessions` và `refresh_token_store`.
2. Chốt refresh rotation/replay handling rules.
3. Chốt logout current/all sessions semantics.

### WP-03 CSRF & Cookie Security

1. Chốt cookie naming + flag matrix theo môi trường.
2. Chốt signed token format, signature inputs, verification flow.
3. Chốt Next.js token delivery flow (custom header injection points).

### WP-04 Access Control & Assignment

1. Chốt policy matrix theo role/action/resource.
2. Chốt manager assignment query filters và deny-by-default guard.
3. Chốt optimistic concurrency policy cho role/assignment updates.

### WP-05 Abuse Protection

1. Chốt env vars cho account/IP/refresh limits.
2. Chốt windowing strategy và counter reset behavior.
3. Chốt concurrent attempt handling để tránh race condition lockout.

### WP-06 Password & Reset Security

1. Chốt Argon2id params baseline.
2. Chốt weak-password check strategy cho MVP.
3. Chốt reset token one-time lifecycle + anti-enumeration messaging.

### WP-07 Test Design Freeze

1. Lập traceability matrix: FR/BR/AC ↔ test cases.
2. Tách test suites: unit, integration, security, concurrency.
3. Chốt pass/fail gates cho Definition of Done.

