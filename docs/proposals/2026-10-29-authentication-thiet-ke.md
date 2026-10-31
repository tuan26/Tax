# Thiết kế: xác thực và phân quyền bắt buộc trước pilot

**Ngày**: 2026-10-29
**Trạng thái**: Chờ duyệt. Chưa triển khai. Thay thế phần phương án của `2026-10-29-authentication-truoc-pilot.md`; phần hiện trạng ở file đó vẫn đúng.
**Quyết định đã có**: K1 = phiên phía server với cookie bảo mật. K4 = kế toán chỉ xem hộ được phân công; phân công là quyền quản trị riêng.
**Nguyên tắc**: không bỏ yêu cầu bảo mật nào của spec để rút ngắn thời gian. Chỗ nào K1 làm một yêu cầu không còn áp dụng nguyên văn (refresh token), thiết kế nêu rõ thuộc tính bảo mật mà yêu cầu đó bảo vệ và cơ chế thay thế, kèm đề xuất sửa spec để bạn duyệt (mục 8).

## 1. Phạm vi

Bắt buộc trước pilot: A1–A12 (mục 7). Hoãn sau pilot, không làm yếu bảo mật: tự phục vụ quên mật khẩu qua email (cần dịch vụ email, C4), My Profile, vai trò Manager được cấp cho người thật, lịch sử mật khẩu (đã deferred trong spec), triển khai MFA (đánh giá ở A10).

## 2. Vai trò và phân quyền (K4)

| Vai trò | Dữ liệu hộ | Quản trị |
|-|-|-|
| `ACCOUNTANT` | Chỉ hộ đang được phân công cho mình | Không |
| `ADMIN` | Xem quyết định K5 | Tạo/khóa tài khoản, đổi vai trò, phân công hộ, thu hồi phiên, tạo link kích hoạt/đặt lại mật khẩu |
| `MANAGER` | Theo assignment (có sẵn trong mô hình, chưa cấp cho ai trong pilot) | Không |

**Phân công** (`customer_assignment`): `(tenant_id, customer_id, user_id, assigned_by, assigned_at, revoked_at, revoked_by)`. Không xóa dòng; thu hồi bằng `revoked_at`. Mỗi thay đổi có audit, fail-closed (FR-E1-030).

**Hộ mới**: kế toán tạo hộ thì hộ được tự phân công cho chính người tạo (một dòng phân công, có audit). Admin phân công thêm hoặc chuyển giao.

**Cưỡng chế ở hai lớp**:

1. API: mọi route khai báo vai trò được phép; route theo hộ gọi kiểm tra phân công trước khi làm gì. Thiếu khai báo thì từ chối (deny-by-default).
2. PostgreSQL: thêm policy RLS loại `RESTRICTIVE` cho role `tax_app` trên mọi bảng có `customer_id`: chỉ thấy dòng của hộ mà `app.user_id` đang được phân công (hoặc theo K5 với Admin). Bảng không có `customer_id` (`attachment`, `extraction`) đi qua bảng cha (`message`). Như vậy lỗi ở API không làm lộ hộ chưa được phân công.
3. Worker: tách khỏi `tax_app` (cấp quyền bảng trực tiếp cho `tax_worker`), để policy phân công không áp lên worker; worker vẫn bị policy tenant như hiện tại.

`app.user_id` và `app.tenant_id` do API đặt từ phiên đã xác minh ở server. Rủi ro còn lại: nếu có lỗi SQL injection, kẻ tấn công có thể tự đặt các biến này. Giảm thiểu: chỉ dùng truy vấn tham số hóa, không ghép chuỗi SQL (thêm kiểm tra tự động trong CI ở A12).

## 3. Phiên (K1)

| Thuộc tính | Thiết kế |
|-|-|
| Mã phiên | 256 bit ngẫu nhiên, chỉ trả về trong cookie; DB chỉ lưu SHA-256 |
| Cookie | `__Host-tax_session`; `HttpOnly; Secure; SameSite=Strict; Path=/`; không đặt `Domain` |
| Idle timeout | 30 phút; `last_seen_at` cập nhật tối đa mỗi 60 giây |
| Hết hạn tuyệt đối | 7 ngày từ lúc đăng nhập, không gia hạn |
| Số phiên | Tối đa 3/user; phiên thứ 4 thu hồi phiên cũ nhất trong cùng transaction |
| Cấp mới mã phiên | Mỗi lần đăng nhập luôn tạo mã mới (chống session fixation); không bao giờ nhận mã phiên do client đề xuất |
| Thu hồi | Đăng xuất (phiên hiện tại), đăng xuất mọi nơi, Admin thu hồi; tự thu hồi mọi phiên khi đổi/đặt lại mật khẩu, đổi vai trò, khóa tài khoản |
| Kiểm tra mỗi request | Hàm DB kiểm tra: chưa thu hồi, chưa quá idle, chưa quá hạn tuyệt đối, tài khoản `ACTIVE`; trả `user_id`, `tenant_id`, `role` |
| Dùng lại phiên đã thu hồi | Từ chối và ghi sự kiện bảo mật mức cao `AUDIT_AUTH_REVOKED_SESSION_USED` (tương đương phát hiện replay ở mô hình refresh) |

**CSRF** (Signed Double-Submit, như spec mục 6.1): cookie `__Host-tax_csrf` (không HttpOnly) chứa `nonce.HMAC(secret, session_hash‖nonce)`. Mọi request `POST/PATCH/PUT/DELETE` phải gửi header `X-CSRF-Token` trùng cookie và chữ ký đúng với phiên hiện tại. Thêm kiểm tra header `Origin` phải là origin của app. Các endpoint chưa có phiên (`/auth/login`, `/auth/activate`, `/auth/reset`) kiểm `Origin`.

**CSP**: Next.js sinh script inline khi hydrate, nên dùng nonce mỗi request (middleware Next.js) với `script-src 'self' 'nonce-…' 'strict-dynamic'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`. Trang thành động (không prerender); với pilot không đáng kể.

## 4. Mật khẩu, kích hoạt, đặt lại

- Argon2id (`argon2-cffi`, tham số mặc định RFC 9106 low-memory); băm lại user scrypt cũ ở lần đăng nhập đúng đầu tiên.
- Tối thiểu 12 ký tự, hỗ trợ passphrase, chặn danh sách mật khẩu yếu phổ biến (file trong repo, khoảng 10.000 mục), chặn mật khẩu chứa email.
- **Kích hoạt** (FR-E1-026): Admin tạo tài khoản ở `PENDING_ACTIVATION`; hệ thống tạo link một lần, hạn 24 giờ, lưu hash; link hiển thị **một lần** cho Admin, Admin chuyển cho người dùng qua kênh của văn phòng (C4 phương án b). Người dùng tự đặt mật khẩu; không ai biết mật khẩu ngoài họ. Đáp ứng lý do của E1-QA02 (không chia sẻ mật khẩu tạm).
- **Đặt lại** (FR-E1-021, 028): Admin tạo link đặt lại một lần, hạn 30 phút, cấp link mới làm link cũ mất hiệu lực; dùng xong thu hồi mọi phiên. Tự phục vụ qua email hoãn tới khi chốt C4.
- **Đổi mật khẩu**: cần mật khẩu hiện tại; xong thu hồi mọi phiên khác và cấp phiên mới.
- **Admin đầu tiên** (FR-E1-031): lệnh `ops create-admin` tạo tài khoản `PENDING_ACTIVATION` và in link kích hoạt; không có mật khẩu trong biến môi trường (xem K6).

## 5. Chống dò mật khẩu

- Bảng `auth_attempt` không thuộc tenant: `account_key` (HMAC của email chuẩn hóa), `ip_key` (HMAC của IP), thời điểm, kết quả. Chỉ role `tax_auth` truy cập qua hàm; giữ 30 ngày.
- Thứ tự: kiểm tần suất theo IP (30/5 phút → 429) → kiểm khóa account (5 lần sai/15 phút → khóa 15 phút) → mới kiểm mật khẩu. Đúng thì bộ đếm về 0. Khóa xác định bằng truy vấn đếm có khóa hàng theo `account_key` để nhiều request đồng thời không vượt ngưỡng (AC-E1-016).
- Endpoint kích hoạt, đặt lại, đổi mật khẩu có giới hạn riêng (FR-E1-023). Ngưỡng qua biến môi trường (FR-E1-024). Không khóa vĩnh viễn (BR-E1-014).
- Không lộ tài khoản: cùng thông điệp, cùng mã lỗi, và băm giả khi email không tồn tại để thời gian xử lý tương đương.

## 6. Audit và truy vết

- `audit_event` thêm `reason_code`, `correlation_id`. Sự kiện xác thực khi đã biết tenant ghi vào `audit_event`; sự kiện chưa biết tenant (email không tồn tại, IP bị chặn) ghi vào `security_event` (không thuộc tenant, chỉ `tax_auth` ghi, chỉ vận hành đọc).
- Middleware nhận hoặc sinh `X-Correlation-Id`, trả lại trong response, ghi vào mọi dòng audit của request.
- Mã: dùng catalog mục 3.13 của spec, bổ sung theo C2: `AUTH_SESSION_EXPIRED`, `AUTH_CSRF_INVALID`, `AUTH_PASSWORD_CHANGE_REQUIRED`, `AUTH_LINK_INVALID`, `AUDIT_AUTH_LOGOUT`, `AUDIT_AUTH_PASSWORD_ROTATED`, `AUDIT_AUTH_REVOKED_SESSION_USED`, `AUDIT_ADMIN_ASSIGNMENT_CHANGED`, `AUDIT_ADMIN_ROLE_CHANGED`.
- Không ghi mật khẩu, mã phiên, hash, link kích hoạt vào log hay audit (có test quét).

## 7. Hạng mục, công số, acceptance criteria

| Mã | Hạng mục | Công (ngày) |
|-|-|-|
| A1 | Cookie phiên, CSRF, kiểm Origin, CSP nonce | 3 |
| A2 | Vòng đời phiên (idle, tuyệt đối, 3 phiên, thu hồi, phiên đã thu hồi bị dùng lại) | 1,5 |
| A3 | Khóa account, giới hạn IP, giới hạn endpoint nhạy cảm | 1,5 |
| A4 | Argon2id, chính sách mật khẩu, danh sách mật khẩu yếu | 0,75 |
| A5 | Kích hoạt, đặt lại bằng link một lần, đổi mật khẩu, Admin đầu tiên; màn hình S03, S07, S09 | 2,5 |
| A6 | Vai trò, phân công hộ (K4), RLS restrictive, tách quyền worker | 3,5 |
| A7 | Audit xác thực, `security_event`, correlation id, catalog mã | 1,5 |
| A8 | Không lộ tài khoản (thông điệp, thời gian) | 0,25 |
| A9 | Quét secret trong CI | 0,5 |
| A10 | Tài liệu rà soát bảo mật, đánh giá MFA cho Admin | 0,5 |
| A11 | Màn hình quản trị tối thiểu: tài khoản, phân công, phiên (K7) | 2,5 |
| A12 | Mở rộng test cô lập: phân công, bảng mới, kiểm tra SQL tham số hóa | 1 |
| | **Cộng** | **19**; cộng 20% dự phòng: **khoảng 23 ngày công** cho một người |

Tăng so với ước tính 12–13 ngày trước đó vì K4 (phân công ở hai lớp), màn hình quản trị và link kích hoạt thay cho mật khẩu tạm.

**Acceptance criteria** (chạy tự động trong CI, dữ liệu giả lập; mã AC spec tương ứng trong ngoặc):

- **A1.1** Đăng nhập đúng: response đặt `__Host-tax_session` với `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`, không `Domain`; body không chứa mã phiên; frontend không ghi gì vào `localStorage`/`sessionStorage` (kiểm bằng trình duyệt trong smoke test). (AC-E1-001)
- **A1.2** Request thay đổi trạng thái thiếu hoặc sai `X-CSRF-Token`, hoặc token của phiên khác, hoặc `Origin` lạ: 403 `AUTH_CSRF_INVALID`, không đổi dữ liệu, có audit.
- **A1.3** Mọi trang HTML có CSP với nonce khác nhau giữa hai request; trình duyệt không báo vi phạm CSP trong smoke test.
- **A2.1** Không hoạt động 30 phút: 401 `AUTH_SESSION_EXPIRED`. Hoạt động liên tục quá 7 ngày từ lúc đăng nhập: 401. (thời gian giả lập trong test)
- **A2.2** Đăng nhập lần thứ 4: phiên cũ nhất 401 ở request kế tiếp; có audit.
- **A2.3** Đăng xuất, Admin thu hồi, đổi mật khẩu, đổi vai trò, khóa tài khoản: mọi phiên liên quan 401 ngay request kế tiếp. Dùng lại mã phiên đã thu hồi: 401 và một dòng `AUDIT_AUTH_REVOKED_SESSION_USED`. (AC-E1-008)
- **A2.4** Mã phiên luôn mới sau đăng nhập; gửi kèm cookie phiên cũ khi đăng nhập không làm phiên cũ được dùng tiếp.
- **A3.1** 5 lần sai trong 15 phút: lần thử tiếp theo (kể cả đúng mật khẩu) bị `AUTH_ACCOUNT_LOCKED` trong 15 phút; 20 request sai gửi đồng thời không làm bộ đếm sai. (AC-E1-004, 016)
- **A3.2** 31 lần thử từ một IP trong 5 phút: HTTP 429 `AUTH_RATE_LIMITED`. (AC-E1-005)
- **A3.3** Đăng nhập đúng đưa bộ đếm của account về 0.
- **A4.1** Mật khẩu dưới 12 ký tự, nằm trong danh sách yếu hoặc chứa email: bị từ chối, không lưu. (AC-E1-013)
- **A4.2** User có hash scrypt: đăng nhập đúng thì hash chuyển sang Argon2id; đăng nhập lần sau vẫn đúng.
- **A5.1** Link kích hoạt: dùng được đúng một lần, trong 24 giờ; tài khoản `DISABLED` không kích hoạt được; link sai/hết hạn/đã dùng trả cùng một thông điệp `AUTH_LINK_INVALID`.
- **A5.2** Link đặt lại: một lần, 30 phút; cấp link mới thì link cũ hỏng; đặt lại xong mọi phiên cũ 401. (AC-E1-014 phần token)
- **A5.3** Đổi mật khẩu sai mật khẩu hiện tại: bị từ chối, có tính vào giới hạn tần suất.
- **A6.1** Một test quét toàn bộ route: route nào không khai báo vai trò thì test đỏ. (BR-E1-004)
- **A6.2** Accountant gọi API quản trị: 403 `AUTHZ_FORBIDDEN`, audit `AUDIT_AUTHZ_DENIED`, không đổi dữ liệu. (AC-E1-010)
- **A6.3** Accountant gọi mọi API theo hộ với hộ chưa được phân công: 404, dữ liệu không đổi. Cùng thao tác chạy thẳng SQL bằng role `tax_app` với `app.user_id` của kế toán đó: 0 dòng (RLS), không sửa được. (AC-E1-015 mở rộng cho Accountant)
- **A6.4** Thu hồi phân công: request kế tiếp của kế toán đó với hộ đó trả 404. Thêm phân công: request kế tiếp thấy hộ.
- **A6.5** Ghi phân công khi audit không ghi được: thay đổi không được commit. (FR-E1-030)
- **A6.6** Worker xử lý được việc của mọi hộ trong tenant của việc đó, không phụ thuộc phân công.
- **A7.1** Mỗi loại sự kiện xác thực tạo đúng một dòng audit hoặc `security_event` có `reason_code`, `correlation_id` khớp header response; quét toàn bộ log và audit không thấy mật khẩu, mã phiên, hash, link. (AC-E1-003, mục 3.12)
- **A8.1** Email không tồn tại và email đúng nhưng sai mật khẩu: cùng thông điệp, cùng mã; chênh lệch trung vị thời gian xử lý dưới 20% trên 50 lần đo. (AC-E1-003)
- **A9.1** Commit chứa mẫu secret (private key, mật khẩu trong URL kết nối, token dạng AWS): CI đỏ. (AC-E1-012)
- **A10.1** Có tài liệu rà soát gồm kết quả A1–A12, ma trận cô lập tenant, kết luận MFA cho Admin; bạn ký duyệt trước khi đưa dữ liệu thật vào. (BR-E1-012)
- **A11.1** Admin tạo tài khoản, đổi vai trò (kèm kiểm tra phiên bản để chặn sửa đồng thời, AC-E1-009), phân công/thu hồi phân công, xem và thu hồi phiên qua giao diện; Accountant không thấy menu quản trị và gọi API trực tiếp thì 403.
- **A12.1** Test cô lập tenant bao gồm bảng mới (`customer_assignment`, `auth_token`, `user_session` mở rộng) và xác nhận `auth_attempt`, `security_event` không đọc được bằng `tax_app`.

## 8. Đề xuất sửa spec theo K1 (chờ duyệt)

| Spec hiện tại | Đề xuất | Thuộc tính bảo mật được giữ bằng |
|-|-|-|
| FR-E1-004: access token + refresh token + session server | Session phía server, mã phiên ngẫu nhiên trong cookie `HttpOnly` | Thu hồi tức thì (mạnh hơn access token 15 phút) |
| FR-E1-005: access 15 phút; refresh tối đa 7 ngày | Idle 30 phút; tuyệt đối 7 ngày | Cửa sổ dùng mã bị lộ: tối đa 30 phút nếu không hoạt động, 7 ngày tuyệt đối, cắt ngay khi thu hồi |
| FR-E1-006: refresh rotation, revoke, invalidate token cũ | Cấp mã mới mỗi lần đăng nhập; thu hồi khi đăng xuất, đổi mật khẩu, đổi vai trò, khóa | Chống fixation, thu hồi chủ động |
| FR-E1-007: chỉ lưu hash refresh token | Chỉ lưu hash mã phiên (đang làm) | Lộ DB không lộ mã phiên |
| FR-E1-029: replay → thu hồi token family | Mã phiên đã thu hồi bị dùng lại → từ chối, sự kiện bảo mật mức cao | Phát hiện mã bị đánh cắp |
| AC-E1-001, 006, 007 | Thay bằng A1.1, A2.1–A2.4 | |
| Mã `AUTH_REFRESH_REPLAY_REJECTED`, `AUDIT_AUTH_REFRESH_ROTATED`, `AUDIT_AUTH_REFRESH_REPLAY_REJECTED` | Đánh dấu không dùng; thêm mã ở mục 6 | |
| E1-D03 (sơ đồ refresh đồng thời) | Thay bằng sơ đồ kiểm tra phiên | |

## 9. Quyết định còn cần bạn chọn

| Mã | Câu hỏi | Phương án | Đề xuất |
|-|-|-|-|
| K5 | Admin có xem dữ liệu hộ không | (a) Admin xem mọi hộ trong tenant; (b) Admin chỉ quản trị, xem dữ liệu hộ khi tự phân công cho mình (có audit) | **(b)**: quyền tối thiểu; quyền quản trị tách khỏi quyền xem dữ liệu, đúng tinh thần K4 |
| K6 | Admin đầu tiên | (a) mật khẩu qua biến môi trường, bắt đổi lần đầu (E1-QA12); (b) lệnh `ops` in link kích hoạt | **(b)**: không có mật khẩu nằm trong cấu hình; cần sửa E1-QA12 |
| K7 | Màn hình quản trị trong pilot | (a) màn hình tối thiểu (A11); (b) chỉ dùng lệnh `ops` | **(a)**: lệnh `ops` chạy bằng quyền owner, audit ghi “system” thay vì người thật; dùng hằng ngày là sai nguyên tắc quyền tối thiểu |
| K8 | Quét secret | (a) gitleaks, tải bản phát hành có kiểm sha256; (b) script tự viết | **(a)**, ghim phiên bản và checksum |

## 10. Thứ tự

K5–K8 và mục 8 cần duyệt trước. Sau đó: A6 → A1 → A2 → A3 → A4 → A5 → A7/A8 → A11 → A9 → A12 → A10. Mỗi bước có test, đưa diff để duyệt trước khi commit.
