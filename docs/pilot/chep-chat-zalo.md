# Chép chat Zalo để đo trước khi pilot

Zalo cá nhân không xuất được cả cuộc chat ra file. Ta chép tay 1–2 tuần chat của 1–2 hộ, làm cùng kế toán
trong buổi ngồi cạnh. Dữ liệu này dùng để:

1. Thêm ca kiểm thử thật vào bộ regression (`spec/`).
2. Đo STOR và tỷ lệ tự ghép sai của engine **trước** pilot.

## Trước khi chép

- Hộ đã ký đồng ý (bản nháp: `docs/pilot-consent-draft.md`, cần luật sư duyệt).
- Chỉ lưu trên máy của văn phòng hoặc máy chủ tại Việt Nam. Không gửi file qua dịch vụ nước ngoài.
- Ảnh không được che tự động. Nếu ảnh có số CCCD, số tài khoản cá nhân, hãy làm mờ trước khi dùng
  ngoài văn phòng kế toán.

## Định dạng file chat.txt

```
# hộ: Quán Minh Anh
# giờ chốt: 04:00
# người gửi: Chị Lan = owner; Tuấn = staff; Hà = accountant
== 02/10/2026 ==
10:00 Chị Lan: [ảnh hd_001.jpg]
10:00 Chị Lan: [ảnh hd_002.jpg, hd_003.jpg]
10:01 Chị Lan: 2tr5
10:02 Chị Lan: tiền thịt
   dòng không có giờ là phần tiếp theo của tin ngay trên
10:05 Hà: [sticker]
```

| Thành phần | Cách ghi |
|---|---|
| Ngày | Một dòng `== dd/mm/yyyy ==` mỗi khi sang ngày mới (Zalo hiện ngày ở giữa khung chat) |
| Tin nhắn | `HH:MM Tên người gửi: nội dung`, chép **nguyên văn**, kể cả viết tắt và sai chính tả |
| Ảnh | `[ảnh tên-file.jpg]`. Nhiều ảnh gửi một lần thì `[ảnh a.jpg, b.jpg]`. Tải ảnh từ Zalo PC vào một thư mục |
| File | `[file hoa-don.pdf]` |
| Khác | `[sticker]`, `[thu hồi]`, `[ghi âm]`, `[link]` |
| Vai trò | `owner` chủ hộ, `family` người nhà, `staff` nhân viên, `accountant` kế toán, `unknown` |

Giờ: di chuột lên tin nhắn trong Zalo PC để xem giờ gửi. Giờ gửi là bằng chứng quan trọng cho việc gom tin,
nên chép đúng. Không đoán giờ: tin nào không biết giờ thì dùng giờ của tin ngay trước và ghi chú lại.

Ví dụ đầy đủ: `tools/pilot/example/chat.txt` và `tools/pilot/example/anh/`.

## Chuyển đổi

```bash
python tools/pilot/zalo_transcript.py chat.txt --images anh/ --out ket-qua/ --ocr tesseract --collector "Tên"
```

Kết quả trong `ket-qua/`:

- `messages.json`: đúng `spec/messages.schema.json`. Tên người gửi đã thay bằng S1, S2…; số điện thoại,
  số tài khoản (khi có chữ "stk", "tài khoản" đứng trước), CCCD, email đã được che. **Tên riêng nằm trong
  nội dung tin nhắn không tự che được: đọc lại file trước khi chia sẻ.**
- `images/`: bản sao ảnh.
- `danh-dau.csv`: mỗi dòng là một quyết định của engine gom tin.

## Đánh dấu đúng/sai

Mở `danh-dau.csv` bằng Excel. Cùng kế toán, với mỗi dòng:

| Cột | Ghi gì |
|---|---|
| `dung_khong` | `Y` nếu engine đúng (kể cả khi engine nói "chưa chắc" và quả thật không chắc), `N` nếu sai |
| `sua_thanh` | Nếu sai: đúng ra phải thế nào, ví dụ "thuộc G2", "là 2 giao dịch", "khách rút lại ảnh này" |
| `ghi_chu` | Vì sao kế toán biết (dựa vào đâu) |

Các cột `engine`: `CONFIDENT` là engine tự quyết; `AMBIGUOUS` là engine đưa vào hàng chờ;
`UNMATCHED (… cần xem)` là engine báo cho kế toán xem.

Rồi tính chỉ số:

```bash
python tools/pilot/zalo_transcript.py --score ket-qua/danh-dau.csv
```

- `STOR_uoc_tinh`: giao dịch engine tổ chức đúng mà không cần kế toán chỉnh.
- `wrong_auto_rate`: quyết định tự động bị đánh dấu sai. **Chỉ số quan trọng nhất.** Mục tiêu dưới 2%.
- `tu_dong_sai_chi_tiet`: từng chỗ engine tự quyết sai. Gửi cho người phát triển: mỗi chỗ sẽ thành một ca kiểm thử
  và được sửa trước pilot.
