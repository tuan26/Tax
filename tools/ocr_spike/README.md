# Spike OCR

Mục tiêu: chọn OCR trong nước cho pilot bằng số đo trên ảnh thật, không bằng demo.

## 1. Chuẩn bị ảnh (100–200 ảnh)

Lấy từ chính các hộ sẽ tham gia pilot, có đồng ý của hộ. Ảnh thật là dữ liệu thật: chỉ chạy
trên máy hoặc dịch vụ đặt tại Việt Nam, không gửi cho dịch vụ nước ngoài nào khi chưa có ý kiến
pháp lý (cổng `app/ai_outbound.py` sẽ chặn).

Chia nhóm bằng cột `category` theo đúng tỷ lệ gặp ngoài thực tế, ví dụ:

| category | Ví dụ |
|---|---|
| in_thang | Hóa đơn in, chụp thẳng, đủ sáng |
| chup_nghieng | Chụp nghiêng, có bóng, nhăn |
| mo | Mờ, rung, thiếu sáng |
| viet_tay | Phiếu, bảng kê viết tay |
| chuyen_khoan | Ảnh chụp màn hình app ngân hàng |
| pdf | Hóa đơn điện tử dạng PDF (cần tách trang, chưa hỗ trợ) |

## 2. Ghi đáp án

Copy `truth_template.csv`, mỗi ảnh một dòng. Đáp án do kế toán ghi, không lấy từ OCR.
Ô trống nghĩa là chứng từ không có trường đó. Số tiền ghi số nguyên (2350000), ngày dạng YYYY-MM-DD.

## 3. Chạy

```bash
cd backend
python -m app.ocr.bench --images <thư mục ảnh> --truth truth.csv --provider tesseract \
    --cost-per-page 0 --out ../tools/ocr_spike/report-tesseract.md
```

Thêm provider khác (dịch vụ OCR trong nước) bằng một lớp có `name` và `extract(data, mime) -> dict`
trả về các trường dạng `{"value": ..., "confidence": ...}` (xem `app/ocr/tesseract.py`), rồi đăng ký trong
`app/extraction.py:provider_for`.

## 4. Đọc kết quả

Bộ đo báo 5 chỉ số: tỷ lệ đọc đúng số tiền, ngày, MST và tên người bán; thời gian xử lý; chi phí.
Mỗi trường được chia thành: đúng và tự tin, **sai nhưng tự tin**, chỉ gợi ý, không đọc được.

Chỉ số quyết định là **sai nhưng tự tin**. Đây là số kế toán có thể chấp nhận mà không để ý.
Một provider đọc đúng 70% nhưng sai-tự-tin dưới 2% tốt hơn provider đọc đúng 90% nhưng sai-tự-tin 8%:
phần không đọc được chỉ tốn công gõ, phần sai-tự-tin làm sai sổ.

Gợi ý tiêu chí chọn cho pilot (chỉnh sau khi có số đo đầu tiên):
- Số tiền: sai nhưng tự tin ≤ 2%, đúng và tự tin ≥ 60% ở nhóm `in_thang` và `chuyen_khoan`.
- Thời gian p95 ≤ 10 giây mỗi ảnh.
- Chi phí cho cả pilot (khoảng 2 kế toán × 3 hộ × 2 tuần) trong ngân sách.

Mốc so sánh là `tesseract` (mã nguồn mở, tự host). Kết quả trên ảnh tổng hợp trong test không đại diện cho ảnh thật.
