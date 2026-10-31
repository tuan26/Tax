# Đề xuất: hosting pilot tại Việt Nam, dưới 5 triệu đồng/tháng

**Ngày**: 2026-10-29
**Trạng thái**: Chờ duyệt. Chưa thuê, chưa deploy.
**Ràng buộc**: dữ liệu lưu và xử lý tại Việt Nam (Constitution 3.13, `docs/pilot-consent-draft.md` mục 3); không deploy production và không đưa dữ liệu thật vào trước khi xong P0 bảo mật, phần xác thực bắt buộc trước pilot và ý kiến pháp lý (Q36).

## 1. Nhu cầu tài nguyên

Pilot: 2 kế toán × 2–3 hộ × 2 tuần. Toàn bộ stack chạy trên một máy theo `deploy/docker-compose.yml`: PostgreSQL 16, backend FastAPI, worker (Tesseract OCR, tốn CPU nhất), frontend Next.js, Caddy (HTTPS).

| Tài nguyên | Ước tính | Căn cứ |
|-|-|-|
| CPU | 4 vCPU | Tesseract xử lý một ảnh mất vài giây/lõi; 4 lõi để OCR không làm chậm giao diện |
| RAM | 8 GB | PostgreSQL 1–2 GB, Next.js và FastAPI mỗi thứ dưới 1 GB, Tesseract vài trăm MB mỗi tiến trình |
| Ổ đĩa | 80–100 GB SSD | Ảnh chứng từ 0,5–2 MB/ảnh; 5 hộ × 300 ảnh/tháng ≈ 3 GB/tháng, cộng bản sao lưu tại chỗ |
| Sao lưu ngoài máy | 100 GB object storage, nhà cung cấp khác | `docs/deploy.md` mục 6 |

Đây là ước tính; nên đo lại trong tuần đầu pilot.

## 2. Giá tham khảo (chưa gồm VAT, chưa xác minh)

Số liệu lấy từ trang của nhà cung cấp và đại lý ngày 2026-10-29. Nhiều trang không ghi ngày cập nhật hoặc đã cũ, nên **phải lấy báo giá chính thức trước khi chọn**.

| Nhà cung cấp | Gói tham khảo | Giá/tháng | Nguồn |
|-|-|-|-|
| Viettel IDC | 4 vCPU, 8 GB, 40–80 GB SSD | khoảng 775.000–1.250.000 đ, tùy gói và ổ đĩa | vietteldc.com.vn, viettel-idc.com.vn, đại lý |
| FPT Cloud | 2 vCPU, 4 GB (gói nhỏ hơn nhu cầu) | khoảng 599.000–699.000 đ; gói 8 vCPU/16 GB khoảng 3,6–3,8 triệu đ | cloudfpt.com.vn, fptidc.com.vn (đại lý, số liệu cũ) |
| VNPT Smart Cloud | Có gói theo vCPU/RAM, bảng giá chính thức không hiển thị trong kết quả tìm kiếm | Cần báo giá | cloud.vnpt.vn |
| CMC Cloud | Tính theo giờ hoặc gói tháng | Cần báo giá | cmccloud.vn |
| BizFly Cloud (object storage) | Simple Storage standard | 864 đ/GB/tháng, hoặc khoảng 63.750 đ cho gói 100 GB; truyền ra 280 đ/GB | bizflycloud.vn/s3-simple-storage |

## 3. Phương án

| | A. Một máy chủ + sao lưu ngoài (đề xuất) | B. Hai máy (app riêng, DB riêng) |
|-|-|-|
| Máy | 1 × 4 vCPU/8 GB/80–100 GB SSD | 1 × 2 vCPU/4 GB (app) + 1 × 2 vCPU/4 GB (DB) |
| Máy chủ | khoảng 0,8–1,3 triệu đ | khoảng 1,2–1,6 triệu đ |
| Object storage sao lưu (nhà cung cấp khác) | khoảng 0,07–0,1 triệu đ | khoảng 0,07–0,1 triệu đ |
| Snapshot ổ đĩa của nhà cung cấp | khoảng 0,1–0,2 triệu đ (nếu có) | khoảng 0,2–0,4 triệu đ |
| Tên miền `.vn` | khoảng 0,05 triệu đ (chia theo tháng) | như A |
| Theo dõi uptime, cảnh báo lỗi | 0 (dịch vụ miễn phí hoặc tự host) | như A |
| **Cộng (trước VAT)** | **khoảng 1,0–1,7 triệu đ** | **khoảng 1,5–2,2 triệu đ** |
| **Cộng (gồm VAT 10%)** | **khoảng 1,1–1,9 triệu đ** | **khoảng 1,7–2,4 triệu đ** |

Cả hai đều dưới 5 triệu đ/tháng. Đề xuất **A** cho pilot: đơn giản nhất để vận hành và diễn tập khôi phục; tách DB chưa cần ở quy mô này. Phần còn lại của ngân sách (khoảng 3 triệu đ) để dự phòng: nâng lên 8 vCPU nếu OCR chậm, hoặc thuê thêm một máy thử nghiệm (staging) cùng cấu hình nhỏ để diễn tập nâng cấp trước khi áp vào máy pilot.

Đặt object storage sao lưu ở nhà cung cấp khác với máy chủ, để một sự cố của một nhà cung cấp không làm mất cả dữ liệu lẫn bản sao lưu.

## 4. Tiêu chí chọn nhà cung cấp

1. Trung tâm dữ liệu đặt tại Việt Nam; hợp đồng ghi rõ nơi lưu dữ liệu.
2. Hợp đồng có điều khoản xử lý dữ liệu (nhà cung cấp không truy cập, không dùng dữ liệu; thông báo khi có sự cố), phù hợp yêu cầu pháp lý ở mục 5.
3. Có snapshot ổ đĩa hoặc sao lưu tự động; khôi phục được trong ngày.
4. Có IPv4 công khai, mở được cổng 80/443 (Caddy tự xin chứng chỉ Let's Encrypt).
5. Hóa đơn VAT, thanh toán theo tháng, hủy được sau pilot.
6. Tải được image từ Docker Hub hoặc mirror; cài được gói Debian (Tesseract, `postgresql-client`).

## 5. Pháp lý cần xác minh (thuộc Q36)

Không phải ý kiến pháp lý; chỉ là danh sách câu hỏi để chuyên gia trả lời.

1. Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 và Nghị định 356/2025/NĐ-CP (hiệu lực từ 01/01/2026, thay Nghị định 13/2023/NĐ-CP): vai trò của văn phòng kế toán, của bên cung cấp phần mềm và của nhà cung cấp hosting (bên kiểm soát/bên xử lý); hồ sơ đánh giá tác động xử lý dữ liệu cần lập; mẫu đồng ý của hộ kinh doanh.
2. Nếu sau này dùng bất kỳ dịch vụ nào ngoài Việt Nam (kể cả email, theo dõi lỗi), có phải lập hồ sơ chuyển dữ liệu ra nước ngoài không. Hiện kiến trúc pilot không gửi dữ liệu ra nước ngoài.
3. Quy định về lưu trữ chứng từ kế toán (thời hạn lưu, hình thức lưu điện tử) áp dụng cho bản sao chứng từ trong hệ thống.

## 6. Việc cần làm trước khi thuê

1. Xin báo giá chính thức của 2–3 nhà cung cấp theo cấu hình mục 1 (đề xuất: Viettel IDC, VNPT, FPT hoặc CMC) và một nhà cung cấp object storage khác.
2. Kiểm tra hợp đồng theo tiêu chí mục 4.
3. Chạy `docker compose ... up --build` một lần trên máy thuê, chạy `npm run smoke` và diễn tập sao lưu, khôi phục (`docs/deploy.md` mục 6) **trên dữ liệu giả lập** trước khi đưa dữ liệu thật vào.
