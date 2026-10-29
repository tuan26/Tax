# Specification — Epic 1: Project Foundation & Authentication

**Project**: Accounting Intake Agent  
**Source of truth**: `docs/overview/constitution.md` (Version `3.0.0.0`)  
**Epic**: `4.1 Epic 1: Project Foundation & Authentication`  
**Status**: Updated draft for implementation planning

---

## 1) Scope Guardrails (Locked)

1. Giữ nguyên 10 Epic đã chốt trong Constitution.
2. Không mở rộng ngoài MVP V1 scope.
3. Giữ nguyên Tech Stack: Python/FastAPI, PostgreSQL (multi-tenant, RLS), Next.js, kênh Zalo (pilot nhập thủ công, chưa Zalo OA), OCR theo kiến trúc đã duyệt, không LLM hoặc dịch vụ AI bên ngoài, Docker.
4. Giữ nguyên Language Policy.
5. Future Roadmap V2–V5 chỉ để tham chiếu, không triển khai trong Epic 1.

---

## 2) Cross-Epic Design Principles (Applied before Epic details)

### DP-001 Authentication Boundary

1. Customer tương tác qua kênh tiếp nhận (Zalo; trong pilot đầu tiên kế toán nhập thủ công thay khách), **không bắt buộc** có tài khoản Web Dashboard trong MVP V1.
2. Dashboard Authentication chỉ áp dụng cho Accountant, Manager, Admin.
3. Mọi route dashboard/API nội bộ phải kiểm tra danh tính và quyền truy cập theo vai trò.

### DP-002 Customer Mapping Model

1. Không giả định quan hệ `1 người gửi trên kênh tiếp nhận = 1 Customer`.
2. Một người gửi (ví dụ một tài khoản Zalo) có thể đại diện nhiều Customer.
3. Khi chưa xác định được ownership, dữ liệu phải vào `UNVERIFIED_QUEUE` và yêu cầu xác minh thủ công.
4. AI không được tự suy đoán ownership nếu thiếu căn cứ.

### DP-003 Centralized Document Lifecycle Control

1. Trách nhiệm Epic 4/6/7 phải dùng **một cơ chế quản lý trạng thái tập trung**.
2. Chuyển trạng thái phải qua validation + authorization + audit log.
3. Không cho phép từng module tự cập nhật `Document Status` tùy ý.

### DP-004 Testable Acceptance Criteria Quality

1. Acceptance Criteria phải có đủ happy path, error path, retry, duplicate, uncertainty, concurrency, authorization.
2. Mỗi AC phải kiểm thử được bằng điều kiện đầu vào và kết quả mong đợi rõ ràng.

### DP-005 Tenant Isolation

1. Mỗi công ty dịch vụ kế toán là một tenant; mọi dữ liệu nghiệp vụ, user, session và audit gắn `tenant_id`.
2. Cô lập tenant được thực thi bằng PostgreSQL Row Level Security dưới role ứng dụng không phải superuser, không BYPASSRLS (Constitution mục 3.14).
3. Kiểm tra authz ở tầng API không thay thế RLS; RLS không thay thế authz theo vai trò.

---

## 3) Epic 1 Specification — Project Foundation & Authentication

### 3.1 Objective

Thiết lập nền tảng kỹ thuật và bảo mật cho MVP V1, bao gồm authentication/authorization cho dashboard users (Accountant/Manager/Admin), session tracking phía server, chuẩn audit log và error/reason codes dùng chung, để Epic 2–10 triển khai nhất quán, an toàn, có khả năng truy vết.

### 3.2 In Scope

1. Dashboard authentication cho Accountant/Manager/Admin.
2. RBAC cơ bản theo vai trò.
3. Session/token lifecycle: access token, refresh token, rotation, revoke.
4. Login protection: retry/lockout/rate limit cho auth endpoints.
5. Chuẩn hóa auth/authz error codes và audit reason codes.
6. Chuẩn hóa audit envelope cho các hành động bảo mật/nghiệp vụ nhạy cảm.
7. Thiết lập nguyên tắc cấu hình secrets/environment (không hard-code).
8. Nền tảng idempotency/correlation ID ở mức framework cho API nội bộ.
9. Guardrails kỹ thuật để hỗ trợ `UNVERIFIED_QUEUE` và lifecycle control ở các Epic sau.

### 3.3 Out of Scope

1. Đăng nhập web cho Customer.
2. OCR, intent classification, validation nghiệp vụ chi tiết.
3. Workflow xác minh người gửi ↔ Customer chi tiết (thực thi ở Epic 3), chỉ chuẩn bị nền tảng authz/audit.
4. Follow-up workflow gửi yêu cầu bổ sung cho khách (Epic 7).
5. Export schema chi tiết (Epic 9).
6. Bắt buộc triển khai MFA cho Admin trong MVP V1 (chỉ yêu cầu MFA-ready architecture).

### 3.4 Actors

1. **Admin**: quản trị user dashboard và phân quyền.
2. **Manager**: giám sát, truy cập báo cáo và phạm vi quản lý được cấp.
3. **Accountant**: thao tác xử lý chứng từ/exceptions theo phân quyền.
4. **System Service**: backend services thực thi workflow, ghi audit, áp dụng authz.
5. **Customer (channel-only actor)**: tác nhân nghiệp vụ gửi chứng từ qua kênh tiếp nhận (Zalo), không thuộc dashboard auth trong MVP V1.

### 3.5 Inputs / Outputs

#### Inputs

1. Vai trò chuẩn: Customer, Accountant, Manager, Admin.
2. Policy từ Constitution: Human-in-the-loop, AI Uncertainty Handling, Document/Exception lifecycle.
3. Quyết định thiết kế xác nhận: token+server session, lockout policy, MFA-ready, code catalog chuẩn.

#### Outputs

1. Cơ chế đăng nhập dashboard cho Accountant/Manager/Admin.
2. RBAC enforcement trên API/dashboard actions.
3. Chuẩn audit log: actor, action, resource, timestamp, result, correlation_id, reason_code.
4. Chuẩn idempotency/correlation để các Epic sau dùng cho retry/duplicate safety.
5. Chuẩn error codes/reason codes dùng chung cho auth/authz và audit.
6. Chính sách từ chối truy cập mặc định (deny-by-default) cho mọi endpoint cần bảo vệ.

### 3.6 Functional Requirements

- **FR-E1-001 (Dashboard Authentication)**: Hệ thống phải cung cấp cơ chế xác thực cho Accountant/Manager/Admin truy cập dashboard.
- **FR-E1-002 (Role-Based Authorization)**: Hệ thống phải áp dụng RBAC cho mọi API/dashboard action thuộc phạm vi quản trị và nghiệp vụ kế toán.
- **FR-E1-003 (Customer Web Exclusion)**: Hệ thống không yêu cầu hoặc cấp dashboard login cho Customer trong MVP V1.
- **FR-E1-004 (Session/Token Control)**: Hệ thống phải dùng mô hình `access token + refresh token + server-side session tracking`.
- **FR-E1-005 (Token Lifetime Policy)**: Access token có thời hạn 15 phút; refresh token tối đa 7 ngày.
- **FR-E1-006 (Refresh Rotation & Revocation)**: Hệ thống phải hỗ trợ refresh token rotation, logout, session revocation, và invalidate token cũ sau refresh.
- **FR-E1-007 (Refresh Token Storage Security)**: Chỉ lưu hash refresh token; không lưu plaintext refresh token.
- **FR-E1-008 (Cookie & CSRF Security)**: Token phải truyền/lưu theo cơ chế `HttpOnly + Secure + SameSite` cookies và có CSRF protection phù hợp.
- **FR-E1-009 (No LocalStorage Token)**: Không lưu access/refresh token trong localStorage.
- **FR-E1-010 (Login Protection Policy)**: Áp dụng lockout: 5 lần login sai/15 phút/tài khoản thì khóa 15 phút, kết hợp rate limit theo IP và account.
- **FR-E1-011 (Non-Enumerating Auth Errors)**: Thông báo login lỗi không tiết lộ tài khoản có tồn tại hay không.
- **FR-E1-012 (Audit Envelope Standard)**: Mọi hành động nhạy cảm (auth, role change, approval-related operations) phải ghi audit theo schema thống nhất.
- **FR-E1-013 (Error/Reason Code Catalog)**: Hệ thống phải định nghĩa catalog error codes cho auth/authz và catalog reason codes cho audit events.
- **FR-E1-014 (Secrets & Config Security)**: Secrets phải lấy từ environment/secret manager; cấm hard-code trong source/config committed.
- **FR-E1-015 (Authorization Guardrails for Future Flows)**: Các endpoint thay đổi trạng thái nghiệp vụ phải dùng middleware/policy check chuẩn để hỗ trợ centralized lifecycle control ở Epic 4/6/7.
- **FR-E1-016 (Request Correlation & Idempotency Foundation)**: API foundation phải hỗ trợ correlation ID và idempotency key handling cho các thao tác cần retry-safe.
- **FR-E1-017 (Multi-Customer Mapping Readiness)**: Mô hình phân quyền và identity phải không khóa cứng giả định `1 người gửi trên kênh tiếp nhận = 1 Customer`.
- **FR-E1-018 (Unverified Queue Access Control Readiness)**: Chuẩn phân quyền phải sẵn sàng cho việc chỉ Accountant/Manager/Admin phù hợp mới được thao tác dữ liệu `UNVERIFIED_QUEUE` ở Epic 3.
- **FR-E1-019 (MFA-ready Architecture)**: Authentication architecture không được cản trở việc bổ sung MFA cho Admin ở phase sau.
- **FR-E1-020 (Password Policy Baseline)**: Password dashboard users tối thiểu 12 ký tự, hỗ trợ passphrase, hash bằng Argon2id.
- **FR-E1-021 (Password Reset Security)**: Password reset dùng token một lần, TTL ngắn, và không tiết lộ tài khoản có tồn tại hay không.
- **FR-E1-022 (Manager Assignment Scope Enforcement)**: Manager chỉ truy cập resource thuộc assignment hợp lệ do Admin quản lý; mặc định deny khi thiếu assignment.
- **FR-E1-023 (Refresh/Sensitive Endpoint Rate Limit)**: Endpoint refresh token và endpoint nhạy cảm phải có rate limit riêng theo policy.
- **FR-E1-024 (Configurable Security Thresholds)**: Ngưỡng lockout/rate-limit phải cấu hình được qua environment variables.
- **FR-E1-025 (Tenant Isolation)**: Mọi bảng chứa dữ liệu tenant phải bật và FORCE Row Level Security; ứng dụng chỉ truy cập dữ liệu qua role không có BYPASSRLS; khi chưa xác định tenant thì không trả dữ liệu tenant nào. Hàm chạy với quyền nâng cao (SECURITY DEFINER) phải được rà soát để không làm lộ hoặc thay đổi dữ liệu của tenant khác.

### 3.7 Business Rules

- **BR-E1-001**: Chỉ Admin mới được tạo/sửa/vô hiệu hóa dashboard user accounts.
- **BR-E1-002**: Customer không có dashboard account trong MVP V1; mọi tương tác Customer đi qua kênh tiếp nhận (Zalo; trong pilot đầu tiên kế toán nhập thủ công thay khách).
- **BR-E1-003**: Mọi quyết định ảnh hưởng dữ liệu kế toán phải truy vết được qua audit log với actor rõ ràng.
- **BR-E1-004**: Authorization áp dụng nguyên tắc deny-by-default khi role/policy không rõ ràng.
- **BR-E1-005**: Không dùng confidence score làm điều kiện duy nhất để bypass human approval/authorization.
- **BR-E1-006**: Secrets lộ trong repository được coi là vi phạm nghiêm trọng và phải chặn release.
- **BR-E1-007**: Thao tác retry phải không tạo side-effect trùng nếu có cùng idempotency context.
- **BR-E1-008**: Sau 5 lần đăng nhập sai trong 15 phút cho cùng account, account bị khóa tạm 15 phút.
- **BR-E1-009**: Hệ thống phải áp dụng rate limiting đồng thời theo account và IP cho login endpoints.
- **BR-E1-010**: Response lỗi login không phân biệt account không tồn tại và password sai.
- **BR-E1-011**: Không lưu secrets/password/access token/refresh token vào logs hoặc audit payload.
- **BR-E1-012**: Pilot với dữ liệu thật không được cho phép khi chưa hoàn tất security review (bao gồm đánh giá MFA cho Admin).
- **BR-E1-013**: IP login rate limit mặc định: 30 lần trong 5 phút, vượt ngưỡng trả HTTP 429.
- **BR-E1-014**: Không khóa vĩnh viễn account hoặc IP trong MVP V1.
- **BR-E1-015**: Audit reason codes dùng taxonomy `AUDIT_*` ổn định, độc lập ngôn ngữ hiển thị.
- **BR-E1-016**: User, session và mọi thao tác chỉ thuộc một tenant; không có thao tác nào của tenant này đọc, sửa, xóa hoặc tham chiếu được dữ liệu của tenant khác.

### 3.8 User Stories

- **US-E1-001 (Admin Authentication Setup)**: Là Admin, tôi muốn quản lý dashboard accounts theo vai trò để kiểm soát ai được truy cập hệ thống.
- **US-E1-002 (Accountant Secure Access)**: Là Accountant, tôi muốn đăng nhập an toàn và chỉ thấy chức năng đúng vai trò để xử lý nghiệp vụ đúng quyền.
- **US-E1-003 (Manager Oversight Access)**: Là Manager, tôi muốn truy cập phạm vi dữ liệu quản lý được cấp mà không thấy dữ liệu ngoài phạm vi.
- **US-E1-004 (System Auditability)**: Là người vận hành, tôi muốn mọi hành động nhạy cảm được audit để điều tra sự cố và tuân thủ governance.
- **US-E1-005 (Platform Consistency)**: Là team phát triển, tôi muốn dùng cùng cơ chế authz/idempotency/correlation để tránh sai khác giữa các Epic.
- **US-E1-006 (Security Operator Protection)**: Là Security/Ops, tôi muốn có lockout/rate-limit và token rotation để giảm rủi ro brute force và session abuse.

### 3.9 Acceptance Criteria (Given/When/Then)

#### AC-E1-001 — Happy Path: Dashboard login success
**Given** một user role `Accountant` hợp lệ và account đang active  
**When** user gửi thông tin đăng nhập hợp lệ  
**Then** hệ thống cấp access token TTL 15 phút + refresh token TTL tối đa 7 ngày, tạo server-side session, và ghi audit reason `AUDIT_AUTH_LOGIN_SUCCESS`.

#### AC-E1-002 — Authorization boundary for Customer
**Given** một principal được nhận diện là `Customer`  
**When** principal cố truy cập dashboard endpoint yêu cầu dashboard auth  
**Then** hệ thống từ chối với error code chuẩn authz, ghi audit reason `AUDIT_AUTHZ_DENIED`, và không trả thông tin nội bộ nhạy cảm.

#### AC-E1-003 — Error Path: Invalid credentials
**Given** tài khoản dashboard tồn tại nhưng thông tin đăng nhập sai  
**When** user thực hiện login  
**Then** hệ thống từ chối đăng nhập, không cấp token, ghi audit reason `AUDIT_AUTH_LOGIN_FAILED`, và thông điệp lỗi không tiết lộ account có tồn tại hay không.

#### AC-E1-004 — Lockout policy enforcement
**Given** một account có 5 lần login sai trong cửa sổ 15 phút  
**When** có lần login sai tiếp theo trong thời gian khóa  
**Then** hệ thống từ chối với error code lockout, duy trì khóa 15 phút, và ghi audit reason `AUDIT_AUTH_ACCOUNT_LOCKED`.

#### AC-E1-005 — Rate limiting by IP and account
**Given** lưu lượng login vượt ngưỡng rate limit theo IP hoặc account  
**When** yêu cầu mới đến login endpoint  
**Then** hệ thống throttle/reject theo policy, trả HTTP 429 với error code rate-limit chuẩn và ghi audit/security event tương ứng.

#### AC-E1-006 — Refresh rotation success
**Given** refresh token hợp lệ gắn với server-side session active  
**When** client gọi refresh endpoint  
**Then** hệ thống cấp token mới, rotate refresh token, revoke token refresh cũ, và ghi audit reason `AUDIT_AUTH_REFRESH_ROTATED`.

#### AC-E1-007 — Duplicate/replay refresh rejection
**Given** refresh token cũ đã bị rotate/revoke  
**When** token cũ được gửi lại do replay hoặc retry muộn  
**Then** hệ thống từ chối request, không cấp token mới, ghi audit reason `AUDIT_AUTH_REFRESH_REPLAY_REJECTED`.

#### AC-E1-008 — Logout & session revocation
**Given** một session đang active  
**When** user thực hiện logout hoặc Admin revoke session  
**Then** server-side session bị vô hiệu hóa ngay, refresh token không dùng lại được, và ghi audit event phù hợp.

#### AC-E1-009 — Concurrency: role update conflict
**Given** Admin A và Admin B cùng sửa quyền của một user gần đồng thời  
**When** update thứ hai dùng dữ liệu stale (version cũ)  
**Then** hệ thống phát hiện conflict, từ chối update stale, ghi audit `ROLE_UPDATE_CONFLICT`, và giữ trạng thái quyền nhất quán.

#### AC-E1-010 — Authorization: privileged action restriction
**Given** user role `Accountant`  
**When** user gọi API quản trị user/role (chỉ dành cho Admin)  
**Then** hệ thống trả về forbidden với error code chuẩn, không thay đổi dữ liệu, ghi audit reason `AUDIT_AUTHZ_DENIED`.

#### AC-E1-011 — Uncertainty-ready handling baseline
**Given** một request thay đổi trạng thái nghiệp vụ nhưng không đủ context identity/ownership đã xác minh  
**When** request vào lớp API protected cho business-state mutation  
**Then** hệ thống không cho commit trạng thái, route sang trạng thái chờ xác minh/exception theo policy, và ghi audit reason `AUDIT_INSUFFICIENT_VERIFIED_EVIDENCE`.

#### AC-E1-012 — Secret hygiene gate
**Given** pipeline kiểm tra cấu hình phát hiện secret hard-coded trong mã nguồn hoặc file cấu hình bị commit  
**When** chạy security gate của Epic 1  
**Then** build/release gate thất bại và tạo log cảnh báo bảo mật theo chuẩn vận hành.

#### AC-E1-013 — Password policy enforcement
**Given** Admin tạo hoặc reset password cho dashboard user  
**When** password ngắn hơn 12 ký tự hoặc không đạt policy đã định  
**Then** hệ thống từ chối với error code auth chuẩn, không lưu password, và ghi audit event tương ứng.

#### AC-E1-014 — Password reset anti-enumeration
**Given** request password reset với email/username có thể tồn tại hoặc không tồn tại  
**When** endpoint reset được gọi  
**Then** response bên ngoài là thông điệp trung lập, còn hệ thống nội bộ chỉ tạo reset token một lần (TTL ngắn) cho account hợp lệ.

#### AC-E1-015 — Manager assignment-based access
**Given** user role `Manager` có danh sách assignment cụ thể  
**When** Manager truy cập resource ngoài assignment  
**Then** hệ thống từ chối với `AUTHZ_*`, không trả dữ liệu resource, và ghi audit reason `AUDIT_AUTHZ_DENIED`.

#### AC-E1-016 — Concurrent login attempts under protection
**Given** nhiều login attempts đồng thời trên cùng account trong cửa sổ 15 phút  
**When** tổng số lần sai vượt ngưỡng lockout  
**Then** hệ thống khóa tạm account đúng policy, tránh race condition gây sai trạng thái lock.

#### AC-E1-017 — Tenant isolation under application role
**Given** hai tenant A và B có dữ liệu trên mọi bảng chứa dữ liệu tenant, và kết nối dùng role ứng dụng (không superuser, không BYPASSRLS)  
**When** phiên của tenant A thực hiện: đọc, sửa, xóa dòng của B; chèn dòng mang `tenant_id` của B; ghi dòng tham chiếu (khóa ngoại) tới dòng của B; truy vấn khi chưa đặt tenant; gọi các hàm SECURITY DEFINER được cấp cho role ứng dụng; gọi API với ID thuộc B  
**Then** không thao tác nào đọc được, thay đổi được hoặc tạo được tham chiếu tới dữ liệu của B; dữ liệu của B không đổi sau bộ test; test chạy tự động trong CI và kết quả không được thay bằng việc migration chạy thành công.

### 3.10 Dependencies

#### Upstream

1. Constitution v3.0.0.0 được phê duyệt.
2. Vai trò và scope MVP V1 đã chốt.

#### Downstream (Epic handoff)

1. **Epic 2** dùng auth/audit foundation cho import thủ công (tải chứng từ lên, chép chat) và secure internal APIs; webhook kênh chỉ áp dụng khi Zalo OA được duyệt.
2. **Epic 3** dùng RBAC + audit + unverified access controls.
3. **Epic 4/5/6/7** dùng centralized authorization guard + correlation/idempotency foundation.
4. **Epic 8/9/10** dùng dashboard auth, audit envelope, error/reason code catalog và security gates.

### 3.11 Error & Edge Cases

1. Sai thông tin đăng nhập nhiều lần liên tiếp dẫn tới lockout tạm.
2. Token hết hạn giữa phiên thao tác.
3. Refresh token replay sau khi đã rotate.
4. Retry request do timeout mạng gây duplicate request.
5. Race condition khi cập nhật phân quyền đồng thời.
6. Principal không rõ role hoặc role mapping không hợp lệ.
7. Request thiếu correlation ID/idempotency key với endpoint yêu cầu bắt buộc.
8. Hành động nghiệp vụ đòi bằng chứng ownership nhưng context chưa xác minh.
9. Request không xác định được tenant hoặc tham chiếu ID thuộc tenant khác.

### 3.12 Security & Audit Requirements

1. Áp dụng deny-by-default cho endpoint cần bảo vệ.
2. Mọi login success/failure, lockout, refresh, logout, revoke, role change, authorization denial phải ghi audit.
3. Audit record tối thiểu gồm: `actor`, `action`, `resource`, `timestamp`, `result`, `correlation_id`, `reason_code`.
4. Log/audit không chứa secrets, password, access token, refresh token.
5. Refresh token chỉ lưu hash, hỗ trợ rotation + revocation.
6. Token transport/storage qua `HttpOnly`, `Secure`, `SameSite` cookies và có CSRF protection.
7. Có chuẩn error codes dùng chung cho auth/authz (nhóm `AUTH_*`, `AUTHZ_*`) và chuẩn reason codes `AUDIT_*`.
8. Thiết kế hiện tại phải cho phép bổ sung MFA cho Admin mà không phá API contracts cốt lõi.
9. Cô lập tenant bằng RLS theo FR-E1-025 và kiểm chứng theo AC-E1-017.

### 3.13 Shared Code Catalog Baseline (Epic 1)

#### Authentication/Authorization Error Codes

1. `AUTH_INVALID_CREDENTIALS`
2. `AUTH_ACCOUNT_LOCKED`
3. `AUTH_RATE_LIMITED`
4. `AUTH_TOKEN_EXPIRED`
5. `AUTH_REFRESH_REPLAY_REJECTED`
6. `AUTH_SESSION_REVOKED`
7. `AUTHZ_FORBIDDEN`
8. `AUTHZ_DENIED_CUSTOMER_DASHBOARD`
9. `AUTHZ_DENIED_PRIVILEGED_ACTION`

#### Audit Reason Codes

1. `AUDIT_AUTH_LOGIN_SUCCESS`
2. `AUDIT_AUTH_LOGIN_FAILED`
3. `AUDIT_AUTH_ACCOUNT_LOCKED`
4. `AUDIT_AUTH_REFRESH_ROTATED`
5. `AUDIT_AUTH_REFRESH_REPLAY_REJECTED`
6. `AUDIT_AUTH_SESSION_REVOKED`
7. `AUDIT_AUTHZ_DENIED`
8. `AUDIT_ROLE_UPDATE_CONFLICT`
9. `AUDIT_INSUFFICIENT_VERIFIED_EVIDENCE`

---

## 4) Design Decisions (Epic 1)

1. **Auth boundary rõ ràng**: Dashboard chỉ dành cho Accountant/Manager/Admin; Customer không có web login trong MVP V1.
2. **Session model đã chốt**: token + server-side session tracking, access 15 phút, refresh 7 ngày, refresh rotation, revoke và logout.
3. **Storage/transport bảo mật**: dùng cookie `HttpOnly/Secure/SameSite`, có CSRF protection, không dùng localStorage cho token.
4. **Abuse protection**: lockout 5 sai/15 phút, khóa 15 phút, kết hợp rate limit theo account + IP.
5. **MFA strategy**: chưa bắt buộc trong MVP V1 (dữ liệu giả lập), nhưng kiến trúc phải MFA-ready và cần đánh giá lại trước pilot dữ liệu thật.
6. **Foundation-first cho workflow**: Epic 1 không xử lý OCR/intent/validation nhưng bắt buộc tạo guardrails authz/audit/idempotency cho toàn chuỗi end-to-end.

## 5) Consistency Check with Constitution v3.0.0.0

1. Phù hợp `Language Policy` và vai trò người dùng ở phần `3.12` Constitution.
2. Giữ nguyên ranh giới MVP V1, không đưa chức năng V2–V5 vào scope.
3. Tương thích `Document & Exception Lifecycle`, `Customer Verification`, `AI Uncertainty Handling` trong Constitution mục `3.8–3.11`.
4. Bảo toàn nguyên tắc Human-in-the-loop, traceability, auditability.
5. Phù hợp quyết định kênh (Zalo-first, pilot nhập thủ công), `AI & Data Policy` (mục 3.13), `Multi-tenant & Tenant Isolation` (mục 3.14) và `Requirement Sources` (mục 3.15).

## 6) Confirmed Inputs for Implementation Planning

1. CSRF dùng `Signed Double-Submit Cookie Pattern`, token gắn session và gửi qua custom header.
2. Password policy: tối thiểu 12 ký tự, hỗ trợ passphrase, hash Argon2id, reset token một lần TTL ngắn, anti-enumeration.
3. Manager authorization theo assignment-based access; mặc định deny khi thiếu assignment hợp lệ.
4. Rate limit: account lockout 5 sai/15 phút và khóa 15 phút; IP login 30 requests/5 phút trả HTTP 429; refresh/sensitive endpoints có limit riêng.
5. Security thresholds cấu hình qua environment variables; không dùng Redis chỉ cho CSRF/rate-limit nếu PostgreSQL đáp ứng.

