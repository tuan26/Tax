# Đề xuất: bảo mật xác thực tối thiểu trước pilot

**Ngày**: 2026-10-29
**Trạng thái**: Chờ duyệt. Chưa triển khai.
**Nguồn yêu cầu**: `docs/specifications/epic-01-project-foundation-authentication-spec.md` (Version 4.1.0.0), Constitution v4.0.0.0
**Nguyên tắc**: làm code đạt spec, không sửa spec để hợp thức hóa code hiện tại. Chỉ đề xuất sửa spec ở những điểm thuộc kiến trúc xác thực (mục 3), và mỗi điểm cần bạn duyệt.

## 1. Hiện trạng code so với spec

| Hạng mục | Code hiện tại | Spec |
|-|-|-|
| Lưu token phía trình duyệt | Bearer token trong `localStorage` | Cookie `HttpOnly`, `Secure`, `SameSite=Strict`; cấm localStorage (FR-E1-008, 009, 035) |
| Phiên | Một token, sống 12 giờ (`SESSION_HOURS`), lưu hash phía server, logout thu hồi được | Access 15 phút + refresh 7 ngày có rotation (FR-E1-004 đến 007); idle 30 phút, tối đa 3 phiên (FR-E1-027) |
| Băm mật khẩu | scrypt | Argon2id (FR-E1-020) |
| Độ dài mật khẩu | Tối thiểu 10 (CLI) | Tối thiểu 12, chặn mật khẩu yếu phổ biến (FR-E1-020, 033) |
| Chống dò mật khẩu | Không có | Khóa 15 phút sau 5 lần sai/15 phút; giới hạn 30 lần/5 phút/IP (FR-E1-010, BR-E1-008, 013) |
| Vai trò | Không có; mọi user trong tenant có quyền như nhau | RBAC Admin/Manager/Accountant, deny-by-default (FR-E1-002, BR-E1-004) |
| Audit sự kiện xác thực | Không ghi đăng nhập/đăng xuất; bảng audit thiếu `reason_code`, `correlation_id` | Ghi mọi sự kiện xác thực theo envelope chuẩn (FR-E1-012, 013, mục 3.12) |
| Đổi/đặt lại mật khẩu | Không có (chỉ CLI tạo user) | Đổi mật khẩu, quên mật khẩu, kích hoạt tài khoản (FR-E1-021, 026, 028) |
| Header bảo mật | HSTS, nosniff, Referrer-Policy | Không nêu CSP; CSP là lớp chặn XSS cần cho cookie phiên |
| Cô lập tenant | Đã vá ở nhóm P0 (migration 004, `tests/test_tenant_isolation.py`) | FR-E1-025, AC-E1-017 |

Frontend và backend đã chạy cùng origin (Next.js chuyển `/api/*` sang FastAPI, Caddy đứng trước). Vì vậy chuyển sang cookie không cần đổi topology.

## 2. Phân loại

### 2.1 Bắt buộc trước pilot

| Mã | Hạng mục | Giải pháp | Công (ngày) | Spec |
|-|-|-|-|-|
| A1 | Cookie phiên thay localStorage, CSRF, CSP | Backend đặt cookie `HttpOnly; Secure; SameSite=Strict; Path=/`; CSRF theo Signed Double-Submit (token ký bằng secret, gắn session, gửi qua header `X-CSRF-Token` cho mọi request thay đổi trạng thái); frontend bỏ `localStorage`, đọc CSRF từ cookie không HttpOnly; Caddy thêm `Content-Security-Policy` chặt (`default-src 'self'`) | 2,5 | FR-E1-008, 009, 035 |
| A2 | Vòng đời phiên | Idle timeout 30 phút; hết hạn tuyệt đối 7 ngày từ lúc đăng nhập; tối đa 3 phiên/user, phiên thứ 4 thu hồi phiên cũ nhất; lệnh `ops` thu hồi mọi phiên của một user | 1,5 | FR-E1-027, AC-E1-008 |
| A3 | Khóa tài khoản và giới hạn tần suất | Bộ đếm trong PostgreSQL (không thêm Redis), ngưỡng qua biến môi trường; HTTP 429 khi vượt ngưỡng IP; bộ đếm về 0 khi đăng nhập đúng | 1 | FR-E1-010, 023, 024, BR-E1-008, 009, 013, 014, 017 |
| A4 | Chính sách mật khẩu và Argon2id | Tối thiểu 12 ký tự, chặn danh sách mật khẩu yếu phổ biến; Argon2id (thêm thư viện `argon2-cffi`); user cũ: kiểm bằng scrypt, đúng thì băm lại bằng Argon2id | 0,75 | FR-E1-020, 033 |
| A5 | Đổi mật khẩu, bắt đổi lần đầu | User đổi mật khẩu của mình (cần mật khẩu hiện tại); tài khoản do vận hành tạo với mật khẩu tạm phải đổi ở lần đăng nhập đầu; đổi xong thu hồi mọi phiên | 1 | FR-E1-028, 031 |
| A6 | Vai trò tối thiểu | Cột `role` (`ADMIN`, `ACCOUNTANT`; `MANAGER` để sẵn), guard deny-by-default cho mọi endpoint, role không rõ thì từ chối | 1,5 | FR-E1-002, BR-E1-004, AC-E1-010 |
| A7 | Audit sự kiện xác thực | Thêm `reason_code`, `correlation_id` vào `audit_event`; middleware sinh/nhận `X-Correlation-Id`; ghi `AUDIT_AUTH_*` cho đăng nhập đúng/sai, khóa, đăng xuất, thu hồi, đổi mật khẩu; không ghi mật khẩu/token | 1 | FR-E1-012, 013, 016 (phần correlation), mục 3.12 |
| A8 | Không lộ tài khoản tồn tại | Cùng thông điệp và cùng thời gian xử lý khi email không tồn tại (băm giả) | 0,25 | FR-E1-011, AC-E1-003 |
| A9 | Chặn secret trong repo | Bước CI quét secret; phát hiện thì CI đỏ | 0,5 | BR-E1-006, AC-E1-012 |
| A10 | Rà soát bảo mật trước dữ liệu thật | Một tài liệu rà soát: kết quả A1–A9, ma trận cô lập tenant, đánh giá MFA cho Admin (bật hay chưa, lý do) | 0,5 | BR-E1-012 |
| | **Cộng** | | **10,5** | Cộng 20% dự phòng sửa lỗi và review: khoảng **12–13 ngày công** cho một người |

### 2.2 Có thể hoãn sau pilot

| Hạng mục | Lý do hoãn được | Thay thế trong pilot |
|-|-|-|
| Quên mật khẩu tự phục vụ qua email (FR-E1-021, E1-S08/S09) | Pilot có 2–3 user; phụ thuộc quyết định C4 (dịch vụ email) | Vận hành đặt mật khẩu tạm qua `ops`, user phải đổi ở lần đăng nhập đầu (A5) |
| Kích hoạt tài khoản qua link (FR-E1-026, E1-S07) | Như trên | Như trên |
| Màn hình Admin quản trị user/role, session, assignment (E1-S04 đến S06) | Ít user, vận hành làm qua `ops` có audit | Lệnh `ops` |
| Vai trò Manager và assignment (FR-E1-022, AC-E1-015) | Pilot không có Manager | Cột role để sẵn giá trị `MANAGER`, chưa cấp cho ai |
| My Profile (FR-E1-034, E1-S02) | Không ảnh hưởng an toàn | Không |
| Idempotency key toàn framework (FR-E1-016 phần idempotency) | Nhập liệu đã chống trùng theo sha256 file; phần còn lại là thao tác của một người | Ghi rõ là nợ kỹ thuật |
| Chống xung đột sửa role đồng thời (AC-E1-009) | Chưa có màn hình sửa role | Không |
| Triển khai MFA cho Admin | Spec chỉ yêu cầu MFA-ready; đánh giá ở A10 | Theo kết luận A10 |
| Lịch sử mật khẩu (E1-QA18) | Spec đã deferred | Không |

### 2.3 Phụ thuộc vào kiến trúc xác thực — cần bạn chọn

| Mã | Câu hỏi | Phương án | Đề xuất |
|-|-|-|-|
| K1 | Mô hình phiên | (a) Cookie phiên dạng chuỗi ngẫu nhiên, server tra session mỗi request; (b) access token 15 phút + refresh token 7 ngày có rotation, như FR-E1-004 đến 007 | **(a)**. Thu hồi có hiệu lực ngay, không có cửa sổ 15 phút, không cần xử lý replay/token family, ít mã hơn khoảng 2 ngày công. Nếu chọn (a) thì cần sửa FR-E1-004 đến 007, AC-E1-001, 006, 007 và mâu thuẫn C3 thành “session cookie, idle 30 phút, tuyệt đối 7 ngày”. Nếu chọn (b), cộng thêm khoảng 2,5 ngày công cho A2 |
| K2 | Kênh gửi link kích hoạt/đặt lại mật khẩu (C4) | (a) Dịch vụ email (phải nêu nhà cung cấp, nơi xử lý; địa chỉ email là dữ liệu cá nhân); (b) chưa có trong pilot | **(b)** cho pilot, quyết định (a) sau pilot |
| K3 | Thư viện băm | Argon2id qua `argon2-cffi` (thư viện mới) | Dùng `argon2-cffi`, tham số mặc định của thư viện (RFC 9106 low-memory) |
| K4 | Phân quyền của Accountant trong một tenant | (a) Accountant thấy mọi hộ của văn phòng (như hiện tại); (b) chỉ hộ được giao | **(a)** cho pilot (2 kế toán cùng văn phòng); (b) làm cùng assignment của Manager sau pilot. Spec hiện chỉ nêu assignment cho Manager, nên (a) không trái spec |

## 3. Acceptance criteria cho phần bắt buộc

Mọi AC chạy tự động trong CI, trên dữ liệu giả lập.

- **A1.1** Given đăng nhập đúng, When response trả về, Then có cookie phiên với `HttpOnly`, `Secure`, `SameSite=Strict`, body không chứa token, và frontend không ghi gì vào `localStorage`.
- **A1.2** Given phiên hợp lệ, When gửi request thay đổi trạng thái không có hoặc sai `X-CSRF-Token`, Then HTTP 403 `AUTH_CSRF_INVALID`, không có thay đổi dữ liệu, có audit.
- **A1.3** Given trang bất kỳ, When tải qua Caddy, Then có header `Content-Security-Policy` không cho script inline hay script từ origin khác.
- **A2.1** Given phiên không hoạt động 30 phút, When gọi API, Then HTTP 401 `AUTH_SESSION_EXPIRED` và phiên bị đánh dấu hết hạn.
- **A2.2** Given phiên hoạt động liên tục, When quá 7 ngày từ lúc đăng nhập, Then HTTP 401 dù vẫn đang hoạt động.
- **A2.3** Given user có 3 phiên, When đăng nhập lần thứ 4, Then phiên cũ nhất bị thu hồi ngay ở request kế tiếp, có audit.
- **A3.1** Given 5 lần sai trong 15 phút, When thử lần 6 (kể cả đúng mật khẩu), Then bị từ chối `AUTH_ACCOUNT_LOCKED` trong 15 phút, có audit `AUDIT_AUTH_ACCOUNT_LOCKED`. Bao gồm trường hợp các lần sai gửi đồng thời (AC-E1-016).
- **A3.2** Given 30 lần thử từ một IP trong 5 phút, When thử lần 31, Then HTTP 429 `AUTH_RATE_LIMITED`.
- **A4.1** Given mật khẩu dưới 12 ký tự hoặc trong danh sách yếu, When tạo hoặc đổi, Then bị từ chối, không lưu.
- **A4.2** Given user cũ có hash scrypt, When đăng nhập đúng, Then hash được thay bằng Argon2id; lần sau đăng nhập vẫn đúng.
- **A5.1** Given tài khoản có cờ phải đổi mật khẩu, When đăng nhập, Then mọi API trừ đổi mật khẩu và đăng xuất trả 403 `AUTH_PASSWORD_CHANGE_REQUIRED`.
- **A5.2** Given đổi mật khẩu thành công, When dùng bất kỳ phiên cũ nào, Then HTTP 401.
- **A6.1** Given endpoint không khai báo vai trò được phép, When bất kỳ ai gọi, Then bị từ chối (test quét toàn bộ route để chắc không route nào thiếu khai báo).
- **A6.2** Given user `ACCOUNTANT`, When gọi API chỉ dành cho `ADMIN`, Then HTTP 403 `AUTHZ_FORBIDDEN`, có audit `AUDIT_AUTHZ_DENIED`, không đổi dữ liệu.
- **A7.1** Given mỗi loại sự kiện xác thực, When xảy ra, Then có đúng một dòng audit có `reason_code`, `correlation_id` khớp header response, và không chứa mật khẩu, token, hash.
- **A8.1** Given email không tồn tại và email đúng nhưng sai mật khẩu, When đăng nhập, Then thông điệp, mã lỗi giống nhau, thời gian xử lý chênh dưới 20%.
- **A9.1** Given commit chứa chuỗi giống secret (mẫu private key, mật khẩu trong URL kết nối), When CI chạy, Then CI đỏ.
- **A10.1** Có tài liệu rà soát được bạn ký duyệt trước khi đưa dữ liệu thật vào.

## 4. Thứ tự đề xuất

K1 và K4 cần chốt trước khi bắt đầu. Sau đó: A6 → A1 → A2 → A3 → A4/A5 → A7/A8 → A9 → A10. Mỗi bước có test riêng, đưa diff để duyệt trước khi commit.
