# Bảng quyết định: C1–C8 (spec Epic 1) và S1–S6 (đồng bộ nghiệp vụ)

**Ngày**: 2026-10-29
**Trạng thái**: Chờ duyệt. Chưa sửa code hay spec theo bảng này.
**Đã quyết, không nêu lại**: K1 (phiên phía server, cookie bảo mật), K4 (kế toán chỉ xem hộ được phân công), KPI chính phút/hộ/tháng và KPI phụ phút/chứng từ, CHK014 chưa được đánh dấu hoàn thành phần triển khai khi `UNVERIFIED_QUEUE` chưa có.

Công số tính cho một người, đã gồm test; “0” nghĩa là chỉ sửa tài liệu. Công của phần xác thực đã nằm trong `2026-10-29-authentication-thiet-ke.md`, không cộng lại ở đây.

## 1. C1–C8: khác biệt giữa hai bản spec Epic 1

| Mã | Hiện trạng | Phương án | Đề xuất | Ảnh hưởng code | Công |
|-|-|-|-|-|-|
| C1 Ngưỡng khóa | Spec chính: khóa khi có 5 lần sai/15 phút. Bản gốc: “>5 lỗi”. Code: chưa có khóa | (a) khóa ngay sau lần sai thứ 5; (b) sau lần sai thứ 6 | (a) | Hằng số trong A3 | 0 (nằm trong A3) |
| C2 Tên mã lỗi/audit | Hai bộ tên khác nhau cho refresh, logout, đổi mật khẩu. Code: chưa có catalog | (a) giữ catalog spec mục 3.13, thêm mã còn thiếu theo tiền tố `AUTH_`/`AUDIT_AUTH_`; (b) dùng tên bản gốc | (a); danh sách mã thêm ở thiết kế xác thực mục 6 | Module catalog mã trong A7 | 0,25 |
| C3 Replay refresh | Bản gốc: replay thì thu hồi cả token family. K1 bỏ refresh token | (a) theo K1: phiên đã thu hồi bị dùng lại → từ chối và ghi sự kiện bảo mật mức cao; (b) như (a) và tự thu hồi mọi phiên của user | (a). (b) gây đăng xuất hàng loạt khi một tab cũ còn mở | Trong A2 | 0 (nằm trong A2) |
| C4 Kênh gửi link | Bản gốc: email. Code: không có | (a) dịch vụ email (phải nêu nhà cung cấp, nơi xử lý, chi phí; địa chỉ email là dữ liệu cá nhân); (b) pilot: Admin tạo link một lần trên màn hình quản trị, tự chuyển cho người dùng | (b) cho pilot; (a) sau pilot qua đề xuất riêng | Trong A5, A11 | 0 (nằm trong A5) |
| C5 Email duy nhất | Code: email duy nhất toàn hệ thống. Bản gốc: “email duy nhất”, không nói phạm vi | (a) toàn hệ thống; (b) trong tenant, đăng nhập phải chọn văn phòng | (a): đăng nhập không cần chọn văn phòng; không lộ danh sách văn phòng | Không đổi | 0 |
| C6 Màn hình sau đăng nhập | Code: danh sách hộ. Bản gốc: My Profile | (a) Accountant vào danh sách hộ được phân công, Admin vào màn hình quản trị; (b) theo bản gốc | (a) | Điều hướng frontend | 0,25 |
| C7 Quy tắc version | Bản gốc: `A.B.0.0`. Spec chính đã áp dụng (4.1.0.0) | (a) giữ; (b) bỏ | (a) | Không | 0 |
| C8 Phần bổ sung từ bản gốc | Idle 30 phút, tối đa 3 phiên, kích hoạt tài khoản, Admin đầu tiên, My Profile, đổi mật khẩu | (a) làm hết trước pilot; (b) làm phần bảo mật trước pilot, My Profile sau | (b): idle, 3 phiên, kích hoạt, đổi mật khẩu, Admin đầu tiên là bắt buộc (A2, A5); My Profile hoãn, không ảnh hưởng an toàn | Trong A2, A5 | 0 (đã tính) |

## 2. S1–S6: đồng bộ nghiệp vụ code ↔ Constitution

| Mã | Hiện trạng | Phương án | Đề xuất | Ảnh hưởng code | Công |
|-|-|-|-|-|-|
| S1 Đối tượng mang trạng thái | Constitution gắn trạng thái vào Document. Code: file và tin nhắn gốc chỉ-thêm, không có trạng thái; trạng thái nằm ở record (giao dịch) và `processing_job` | (a) sửa Constitution: vòng đời đặt trên Record, đợt nhập có `RECEIVED`/`PROCESSING`/`FAILED`; (b) thêm bảng trạng thái cho từng file; (c) giữ Constitution, đổi mô hình code | (a). (b) tạo hai nguồn trạng thái cho cùng một giao dịch; (c) phá nguyên tắc chỉ-thêm | Hàm ánh xạ trạng thái, trường `lifecycle_status` trong API, nhãn UI | 0,5 |
| S2 `REJECTED` | Code không có; có `EXCLUDED` với 4 lý do | (a) gộp vào `EXCLUDED`, thêm lý do `invalid_document`; (b) thêm trạng thái `REJECTED` riêng | (a): cùng hệ quả (không vào sổ, giữ lịch sử), bớt một lựa chọn cho kế toán | Thêm một lý do, một nút trong UI | 0,25 |
| S3 Trạng thái Exception | Code: `OPEN`, `REQUESTED`, `RESOLVED`, `DISMISSED`. Constitution: `OPEN`, `WAITING_CUSTOMER`, `IN_REVIEW`, `RESOLVED`, `CLOSED` | (a) chuẩn hóa thành `OPEN`, `WAITING_CUSTOMER`, `RESOLVED`, `DISMISSED`; bỏ `IN_REVIEW`, `CLOSED` khỏi MVP; (b) làm đủ 5 trạng thái Constitution | (a). `IN_REVIEW` chỉ cần khi nhiều người xử lý cùng hộ, mà K4 đã phân công hộ cho từng người | Ánh xạ tên ở API, nhãn UI | 0,5 |
| S4 Cách đổi tên | Tên trong DB khác tên chuẩn | (a) ánh xạ ở API/UI, DB giữ nguyên; (b) migration đổi tên trong DB | (a): không động vào dữ liệu đã có, không cần sửa trigger chỉ-thêm | Gộp trong S1, S3 | 0 |
| S5 Phát hiện thiếu chứng từ và ghép tay | Code có DQ-01 đến DQ-03, ghép tay chuyển khoản ↔ chứng từ. Constitution xếp vào V2 | (a) đưa vào MVP dưới tên hẹp, giữ V2 cho sao kê ngân hàng và ghép tự động, kèm điều kiện giữ lại sau pilot; (b) giữ ở V2, ẩn màn hình | (a), với điều kiện đo theo mục 3; ngưỡng chưa chốt | Sửa Constitution 3.4, 3.5; thêm nhãn lý do (mục 3) | 0,75 |
| S6 Tính KPI | `app/metrics.py` cộng phút cho toàn thời gian, theo giờ UTC, không có KPI phụ | (a) chia theo tháng giờ Việt Nam, thêm KPI phụ, cộng phút ngoài app từ sheet; (b) chỉ chia tháng | (a) | `app/metrics.py`, một script đọc sheet baseline, test | 0,75 |
| | | | | **Cộng S1–S6** | **2,75** |

## 3. Đo `finding_useful_rate` trong pilot (chưa chốt ngưỡng)

### 3.1 Vấn đề của cách tính hiện tại

`app/metrics.py` tính: hữu ích = đã yêu cầu khách, hoặc đã ghép, hoặc kế toán bấm “Đã có chứng từ”; mẫu số = hữu ích + bỏ qua. Ba chỗ làm số này cao hơn thực tế:

1. “Đã có chứng từ” gồm hai trường hợp khác nhau: chứng từ đã nằm trong app nhưng chưa được ghép (app bỏ sót, phát hiện **sai**), và chứng từ nằm ngoài app (giấy, kênh khác; phát hiện **đúng nhưng không giúp gì**).
2. Phát hiện còn mở cuối kỳ bị loại khỏi mẫu số; nếu kế toán bỏ mặc cả màn hình thì tỷ lệ vẫn trông tốt.
3. Không đo phần app **bỏ sót** (chứng từ thiếu mà app không báo).

### 3.2 Phân loại mỗi phát hiện khi đóng kỳ

| Nhóm | Điều kiện | Ý nghĩa |
|-|-|-|
| `ACTION` | Đã yêu cầu khách, hoặc đã ghép với chứng từ mà kế toán tìm ra nhờ phát hiện | Có ích |
| `KNOWN` | “Đã có chứng từ”, lý do “nằm ngoài app” | Đúng, không giúp |
| `ENGINE_MISS` | “Đã có chứng từ”, lý do “có trong app, chưa ghép” | App báo sai |
| `WRONG` | Bỏ qua, lý do “phát hiện sai” | App báo sai |
| `NOT_NEEDED` | Bỏ qua, lý do “khoản này không cần chứng từ” | Đúng theo dữ liệu, sai theo nghiệp vụ |
| `STALE` | Hệ thống tự đóng vì bản ghi đã đổi | Không tính |
| `UNTOUCHED` | Còn mở cuối kỳ | Báo riêng |

Cần thêm vào code: lý do bắt buộc khi bấm “Đã có chứng từ” (2 lựa chọn) và khi “Không cần” (3 lựa chọn: phát hiện sai, khoản không cần chứng từ, trùng với phát hiện khác). Công: nằm trong S5.

### 3.3 Chỉ số báo cáo

Tính theo tuần, theo kế toán, theo rule (DQ-01, 02, 03), theo nguồn dữ liệu (`source_type`):

- **Tỷ lệ có ích** = `ACTION` / (đã quyết định, trừ `STALE`)
- **Độ chính xác** = (`ACTION` + `KNOWN` + `NOT_NEEDED`) / (đã quyết định, trừ `STALE`)
- **Tỷ lệ bỏ mặc** = `UNTOUCHED` / tổng phát hiện
- **Bỏ sót** = số chứng từ thiếu kế toán phát hiện muộn (sheet “Bỏ sót” trong `tools/pilot/baseline.xlsx`) mà app không báo

Mỗi tỷ lệ báo kèm cỡ mẫu và khoảng tin cậy 95% (Wilson). Với khoảng 100 phát hiện trong pilot, khoảng tin cậy rộng khoảng ±10 điểm phần trăm; ngưỡng đặt ra sau pilot phải tính đến độ rộng này.

### 3.4 Kiểm tra chéo

Mỗi tuần, người phụ trách pilot cùng kế toán xem ngẫu nhiên 10 phát hiện bị bỏ qua và 10 phát hiện “Đã có chứng từ” để kiểm tra nhãn có đúng không. Ghi tỷ lệ nhãn bị sửa. Nếu trên 20%, coi chỉ số tuần đó là không tin cậy.

### 3.5 Cách chốt ngưỡng sau pilot

Không chốt trước. Sau 2 tuần, dùng số liệu ở 3.3 và phỏng vấn cuối pilot để đề xuất ngưỡng cho từng rule. Rule nào có độ chính xác thấp thì sửa hoặc tắt rule đó, không tắt cả màn hình.

## 4. CHK014

Giữ `[ ]`. Đã ghi chú vào checklist (đợt 2, ngoài 25 file): “Constitution 3.9 đã mô tả cơ chế; triển khai `UNVERIFIED_QUEUE` chưa có. Pilot nhập thủ công: kế toán chọn hộ cho từng đợt nhập (có audit), nên chưa phát sinh dữ liệu chưa xác minh chủ sở hữu. Bắt buộc triển khai trước khi có kênh tiếp nhận tự động (Zalo OA).”
