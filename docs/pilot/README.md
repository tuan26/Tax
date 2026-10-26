# Bộ công cụ giai đoạn 0 (trước pilot)

Mục tiêu tuần này: có **số đo baseline** và **dữ liệu thật**, để sau pilot so được trước và sau.

| Ngày | Việc | Công cụ |
|---|---|---|
| 1–2 | Phỏng vấn 3–5 kế toán | `phong-van-ke-toan.md`, sheet **Hồ sơ hộ**, **Câu khó** |
| 3–4 | Ngồi cạnh 2 kế toán đồng ý pilot, mỗi người một hộ, đo từng khâu | sheet **Ghi thời gian** |
| 3–4 | Cùng lúc chép 1–2 tuần chat của hộ đó, tải ảnh | `chep-chat-zalo.md`, `tools/pilot/zalo_transcript.py` |
| 5 | Đánh dấu đúng/sai, tính STOR và tỷ lệ tự ghép sai | `--score` |
| 5 | Gom 100–200 ảnh có đáp án cho spike OCR | `tools/ocr_spike/` |
| song song | Luật sư duyệt thỏa thuận; chọn máy chủ tại Việt Nam | `docs/pilot-consent-draft.md`, `docs/deploy.md` |

## Phiếu baseline

`tools/pilot/baseline.xlsx`. Ô nền vàng là ô cần điền. Mỗi sheet có một dòng ví dụ (chữ nghiêng), xóa đi khi dùng.

| Sheet | Ghi gì |
|---|---|
| Ghi thời gian | Mỗi lần kế toán làm việc với một hộ: ngày, khâu, giờ bắt đầu, giờ kết thúc, số mục xử lý |
| Tổng hợp | Tự tính số phút theo hộ và theo khâu, số phút cho mỗi hộ mỗi tháng |
| Hồ sơ hộ | Ngành, phương pháp thuế, kênh Zalo, phần mềm, số tin và ảnh mỗi tháng |
| Câu khó | Tin nhắn khó hiểu thật, nghĩa đúng của nó; mỗi dòng sẽ thành một ca kiểm thử |
| Bỏ sót | Chứng từ thiếu hoặc sai mà kế toán phát hiện muộn (để so với pilot) |

Các khâu trong phiếu khớp với chỉ số mà app đo khi pilot (`python -m app.metrics`), nên so được trực tiếp:
nhận và tải chứng từ, nhập liệu, đối chiếu và kiểm tra, hỏi lại khách, chốt và nhập phần mềm kế toán.

## Đủ điều kiện bắt đầu pilot khi

- [ ] Có baseline số phút của ít nhất 2 hộ từ 2 kế toán.
- [ ] Đã chép và đánh dấu chat của ít nhất 1 hộ; `wrong_auto_rate` dưới 2%, các chỗ sai đã thành ca kiểm thử và đã sửa.
- [ ] Đã chọn OCR từ spike, hoặc quyết định chạy pilot không OCR.
- [ ] Đã có file mẫu nhập liệu của phần mềm kế toán và chức năng xuất dữ liệu tương ứng.
- [ ] Thỏa thuận đã được luật sư duyệt và các hộ đã ký.
- [ ] Máy chủ đã deploy, 7 release gate qua, đã diễn tập khôi phục.
