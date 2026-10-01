# Frontend pilot

Next.js 15 (App Router), chỉ chạy phía client. Mọi lời gọi `/api/*` được Next.js chuyển tới FastAPI
(`BACKEND_URL`), nên trình duyệt chỉ làm việc với một origin.

## Chạy

```bash
npm install
BACKEND_URL=http://localhost:8000 npm run dev      # phát triển
npm run build && BACKEND_URL=http://backend:8000 npm start   # pilot
```

Pilot phải chạy sau HTTPS. Token đăng nhập nằm trong `localStorage` của trình duyệt.

## Màn hình

| Màn hình | Đường dẫn | Dùng để |
|---|---|---|
| Danh sách hộ | `/` | Số mục chờ duyệt của từng hộ, thêm hộ mới |
| Nhập dữ liệu | `/customers/:id/import` | Kéo ảnh từ Zalo PC, dán ảnh (Ctrl+V), dán đoạn chat, chọn ngày kinh doanh |
| Sổ theo ngày | `/customers/:id/ledger` | Thu chi theo ngày, mở giao dịch để xem chứng từ gốc, sửa và xác nhận |
| Hàng chờ duyệt | `/customers/:id/review` | Xử lý từng mục hệ thống chưa chắc |
| Việc cần xử lý | `/customers/:id/findings` | Phát hiện từ rule DQ-01..03, ghép chứng từ, tạo tin nhắn đòi chứng từ để dán vào Zalo |

Phím tắt ở Hàng chờ duyệt: `1`–`9` chọn ứng viên, `Enter` xác nhận giao dịch, `J`/`K` (hoặc mũi tên) chuyển mục.
Ô số tiền nhận `2350000`, `2.350.000`, `2tr35`, `950k`.

Mỗi màn hình gửi nhịp hoạt động 30 giây một lần khi người dùng đang thao tác (`POST /activity`), để đo số
phút kế toán làm việc trên từng hộ.

## Kiểm tra

```bash
npm run typecheck
npm test                     # bộ đọc số tiền
CHROME=/đường/dẫn/chrome npm run smoke   # cần backend (OCR_PROVIDER=tesseract) + frontend đang chạy
```

`npm run smoke` đăng nhập bằng tài khoản demo, tạo hộ, nhập 3 ảnh và đoạn chat, xử lý toàn bộ hàng chờ,
mở sổ và chụp màn hình vào `e2e/shots/`. Lỗi console trong trình duyệt làm test thất bại.
