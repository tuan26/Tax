# Đề xuất: đồng bộ code với Constitution v4.0.0.0

**Ngày**: 2026-10-29
**Trạng thái**: Chờ duyệt. Chưa sửa code. Không xóa chức năng nào.
**Phạm vi**: trạng thái Document/Exception (Constitution mục 3.8), phát hiện thiếu chứng từ và ghép giao dịch (mục 3.5), KPI (mục 3.11, đã cập nhật theo quyết định 2026-10-29).

## 1. Trạng thái Document

Khác biệt gốc: Constitution gắn trạng thái vào **Document** (một tài liệu). Trong code, file gốc (`attachment`) và tin nhắn (`message`) là dữ liệu chỉ-thêm, không có trạng thái. Trạng thái nằm ở **record** (một giao dịch, gom từ một hoặc nhiều tin nhắn và file) và ở hàng đợi xử lý (`processing_job`).

| Constitution | Code hiện tại | Ghi chú |
|-|-|-|
| `RECEIVED` | `message`/`attachment` đã lưu, `processing_job.status = 'pending'` | Có, nhưng là trạng thái của đợt nhập, không phải của từng tài liệu |
| `PROCESSING` | `processing_job.status = 'running'` | Như trên |
| `NEEDS_REVIEW` | `record.status = 'ACTIVE'` và `review_required = true` và `confirmed_at IS NULL`; hoặc tin nhắn còn quyết định gom `AMBIGUOUS` | Có |
| `APPROVED` | `record.status = 'ACTIVE'` và `confirmed_at IS NOT NULL` | Có, tên khác |
| `REJECTED` | Không có trạng thái riêng | Gần nhất là `EXCLUDED` với lý do |
| `EXCLUDED` | `record.status = 'EXCLUDED'`, `excluded_reason` ∈ `client_retraction`, `other_customer`, `not_business`, `duplicate` | Có |
| (không có) | `SUPERSEDED`, `MERGED` | Trạng thái lịch sử khi kế toán tách/gộp/sửa; bản cũ giữ lại theo nguyên tắc chỉ-thêm |
| (không có) | `processing_job.status = 'failed'` | Lỗi xử lý, worker thử lại |

**Đề xuất trạng thái chuẩn** (cần bạn duyệt, sau đó sửa Constitution 3.8 và thêm một lớp ánh xạ trong code, không đổi dữ liệu đã lưu):

1. Đổi đối tượng của vòng đời từ “Document” thành “Record (giao dịch)”; Document (file gốc, tin nhắn gốc) không có trạng thái vì không bao giờ bị sửa.
2. Trạng thái nghiệp vụ của Record: `NEEDS_REVIEW`, `APPROVED`, `EXCLUDED`. `RECEIVED`/`PROCESSING` chuyển thành trạng thái của đợt nhập (`processing_job`), thêm `FAILED`.
3. Gộp `REJECTED` vào `EXCLUDED` với lý do bắt buộc. Thêm lý do `invalid_document` nếu cần phân biệt “chứng từ không hợp lệ” với “gửi nhầm”. Lý do: hai trạng thái có cùng hệ quả (không vào sổ, giữ lịch sử), tách ra chỉ làm kế toán phải chọn thêm một lần.
4. Ghi `SUPERSEDED`, `MERGED` vào Constitution là trạng thái lịch sử, không hiển thị như trạng thái nghiệp vụ.
5. API và UI hiển thị tên chuẩn ở trên; tên nội bộ trong DB giữ nguyên (`ACTIVE` + `confirmed_at` → `APPROVED`), để không phải migration dữ liệu.

## 2. Trạng thái Exception

Trong code, Exception tương ứng hai thứ: **finding** (phát hiện thiếu/trùng/mâu thuẫn) và **mục chờ duyệt** (quyết định gom tin chưa chắc). Chỉ finding có vòng đời riêng.

| Constitution | Code (`finding.status`) | Ghi chú |
|-|-|-|
| `OPEN` | `OPEN` | Khớp |
| `WAITING_CUSTOMER` | `REQUESTED` (có `requested_at`) | Cùng nghĩa, khác tên |
| `IN_REVIEW` | Không có | Pilot mỗi hộ một kế toán, không cần khóa “đang xem” |
| `RESOLVED` | `RESOLVED` với `resolution` ∈ `matched`, `has_document`, `no_longer_applies` | Khớp, code chi tiết hơn |
| `CLOSED` | Không có | Code không có bước đóng sau khi đã xử lý |
| (không có) | `DISMISSED` (bắt buộc ghi chú) | Kế toán quyết định “không cần chứng từ” |

**Đề xuất trạng thái chuẩn**: `OPEN` → `WAITING_CUSTOMER` → `RESOLVED`, cộng `DISMISSED`. Cụ thể:

1. Đổi tên `REQUESTED` thành `WAITING_CUSTOMER` ở API/UI (DB giữ nguyên hoặc đổi bằng một migration nhỏ; đề xuất giữ DB, ánh xạ ở API).
2. Bỏ `IN_REVIEW` và `CLOSED` khỏi MVP trong Constitution. `RESOLVED` đã là trạng thái cuối và mở lại được khi bản ghi thay đổi (code đang làm vậy). Thêm lại khi có nhiều người xử lý cùng một hộ.
3. Thêm `DISMISSED` vào Constitution: kết luận “không cần”, bắt buộc ghi chú, có audit.
4. Mục chờ duyệt gom tin giữ như hiện tại (không có vòng đời riêng; được giải quyết bằng quyết định của kế toán, ghi vào `item_decision`).

## 3. Phát hiện thiếu chứng từ và ghép giao dịch

Constitution 3.5 xếp “Transaction Matching, Missing Document Detection” vào V2 (cùng với import sao kê). Code đã làm một phiên bản hẹp. Theo quyết định: giữ code, đánh giá trước khi đưa vào MVP.

**Đã có trong code**

| Thành phần | Mức hoàn thiện | Bằng chứng |
|-|-|-|
| DQ-01 khoản chi chưa có chứng từ đi kèm | Chạy được; chỉ nói “chưa có chứng từ đi kèm”, không kết luận thuế | `app/domain/rules.py`, `tests/test_rules.py::test_dq01_payment_without_document` |
| DQ-02 có thể trùng | Chạy được | `test_dq02_duplicates` |
| DQ-03 chứng từ không có ngày / số khách nhắn khác số đã chốt | Chạy được | `test_dq03_document_fields` |
| Không sinh phát hiện từ dữ liệu chưa chắc | Có cổng `finding_inputs`: chỉ bản ghi đã xác nhận hoặc mọi quyết định cốt lõi đạt HIGH | `test_findings_never_from_uncertain_records`, `test_ocr_degradation.py` |
| Bắt buộc có bằng chứng | Phát hiện không có bằng chứng bị từ chối khi tạo | `test_finding_requires_evidence` |
| Gợi ý ứng viên để ghép | Chấm theo tiêu chí (số tiền, ngày, đối tác), trả kèm bằng chứng từng tiêu chí; chỉ gợi ý, không tự ghép | `app/findings.py::match_candidates`, `test_match_evidence` |
| Ghép tay, bỏ ghép, mở lại | Có; bỏ ghép thì phát hiện mở lại; loại giao dịch thì gỡ ghép liên quan | `test_closed_loop` |
| Soạn tin đòi chứng từ để kế toán copy | Có, không tự gửi | `/customers/{id}/request-text` |
| Màn hình | Có màn hình phát hiện | `frontend/app/customers/[id]/findings` |
| Chỉ số | `finding_useful_rate`, số phát hiện bị bỏ qua, số đóng bằng ghép | `app/metrics.py`, `test_metrics.py` |

**Chưa có / chưa kiểm chứng**

1. Chỉ có một loại ghép: chuyển khoản ↔ chứng từ (`payment_document`). Không có sao kê ngân hàng, không ghép nhiều-một.
2. Ngưỡng chấm ứng viên (lệch ngày 14 ngày, khớp số tiền) chưa được kiểm trên dữ liệu thật.
3. Chưa đo tỷ lệ phát hiện vô ích: nếu cao, kế toán sẽ bỏ qua cả màn hình.
4. DQ-04 trở đi chưa có (đã cắt khỏi pilot).

**Đề xuất**: đưa vào MVP dưới tên hẹp “Phát hiện chất lượng dữ liệu DQ-01 đến DQ-03 và ghép tay chuyển khoản ↔ chứng từ”; giữ ở V2 phần import sao kê và ghép tự động. Điều kiện để giữ trong MVP sau pilot:

- `finding_useful_rate` ≥ 60% trên mỗi kế toán (ngưỡng đề xuất, cần bạn chốt);
- 0 phát hiện tự đóng mà không có quyết định của kế toán;
- 0 phát hiện sinh từ bản ghi chưa chắc (đã có test chặn);
- kế toán xác nhận trong phỏng vấn cuối pilot là màn hình có ích.

Nếu không đạt: giữ code nhưng ẩn màn hình khỏi MVP, không xóa.

Thay đổi Constitution cần duyệt: mục 3.4 thêm dòng trên; mục 3.5 V2 sửa thành “Import sao kê ngân hàng; ghép tự động; phát hiện thiếu chứng từ dựa trên sao kê”.

## 4. KPI: cách tính

Đã cập nhật Constitution 3.11 (v4.0.0.0) theo quyết định: KPI chính phút/hộ/tháng, KPI phụ phút/chứng từ.

**KPI chính: phút/hộ/tháng**

```
phút_app(hộ, tháng)    = số phút (theo giờ Việt Nam) có ít nhất một nhịp hoạt động của kế toán
                         trên màn hình gắn với hộ đó, trong tháng
phút_ngoài(hộ, tháng)  = tổng phút kế toán tự ghi cho việc làm ngoài app (gọi điện, nhắn Zalo,
                         nhập phần mềm kế toán), cùng mẫu với file baseline
KPI chính              = phút_app + phút_ngoài
```

**KPI phụ: phút/chứng từ**

```
số_chứng_từ(hộ, tháng) = số file ảnh/PDF của hộ được nhập trong tháng, trừ file thuộc giao dịch EXCLUDED
KPI phụ                = KPI chính / số_chứng_từ      (không tính khi số_chứng_từ = 0)
```

**Baseline**: file `tools/pilot/baseline.xlsx` đã quy ra phút/hộ/tháng (số phút đo được / số ngày đo × số ngày làm việc trong tháng). So sánh chỉ hợp lệ khi cùng hộ, cùng loại chứng từ.

**Khoảng cách trong code (chưa sửa, cần duyệt)**:

1. `app/metrics.py` hiện trả `active_minutes_by_customer` cho toàn bộ thời gian, chưa chia theo tháng, chưa theo giờ Việt Nam. Đề xuất: nhóm theo `(customer_id, date_trunc('month', at AT TIME ZONE 'Asia/Ho_Chi_Minh'))`.
2. Chưa có KPI phụ. Đề xuất: đếm `attachment` theo tháng nhập, loại các attachment thuộc record `EXCLUDED`.
3. Chưa có chỗ nhập phút làm ngoài app. Đề xuất cho pilot: kế toán tiếp tục ghi vào sheet baseline, script tổng hợp cộng vào; chưa làm màn hình nhập.
4. Nhịp hoạt động gửi từ frontend; nếu tab mở mà không làm gì thì không tính (chỉ tính phút có thao tác). Cần xác nhận frontend chỉ gửi nhịp khi có thao tác thật; chưa kiểm tra trong đợt này.

Công ước tính cho mục 1–2: 0,5 ngày, kèm test.

## 5. Quyết định cần bạn duyệt

| Mã | Nội dung | Đề xuất |
|-|-|-|
| S1 | Vòng đời đặt trên Record thay vì Document; `RECEIVED`/`PROCESSING` là trạng thái đợt nhập | Đồng ý |
| S2 | Gộp `REJECTED` vào `EXCLUDED` có lý do | Đồng ý |
| S3 | Exception: `OPEN`, `WAITING_CUSTOMER`, `RESOLVED`, `DISMISSED`; bỏ `IN_REVIEW`, `CLOSED` khỏi MVP | Đồng ý |
| S4 | Ánh xạ tên ở API/UI, không đổi tên trong DB | Đồng ý |
| S5 | Đưa DQ-01 đến DQ-03 và ghép tay vào MVP với điều kiện ở mục 3 | Đồng ý; chốt ngưỡng `finding_useful_rate` |
| S6 | Sửa `app/metrics.py` theo tháng, giờ Việt Nam, thêm KPI phụ | Đồng ý |
