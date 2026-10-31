# Accounting Intake Agent

**Date**: 2026-10-29 10:18 (Format: yyyy-MM-dd HH:mm — update each time constitution.md is edited)
**Version**: 4.0.0.0 (Format: A.0.0.0 — Increment A each time constitution.md is edited; Always retain the note from this line as-is in the created file)

---

# 1. PROJECT INFORMATION

## 1.1 Stakeholders

| Role/Stakeholder | Name/Description |
|-|-|
| End user (System/Tool user) | Customer, Accountant, Manager, Admin tại công ty dịch vụ kế toán/đại lý thuế |
| Requester | Product Owner dự án Accounting Intake Agent |
| Requesting Department | Khối vận hành kế toán và khối công nghệ nội bộ |
| Client-side Team Structure | PO/BA, Backend, Frontend, AI/OCR, QA, DevOps, đại diện nghiệp vụ kế toán |

## 1.2 Project Overview

| Category/Type | Details |
|-|-|
| Context | Hệ thống AI Automation cho lớp xử lý dữ liệu đầu vào kế toán (Pre-Accounting Automation Layer), tiếp nhận chứng từ từ kênh giao tiếp trước khi chuyển sang phần mềm kế toán. |
| Problems/Issues | Quy trình hiện tại phụ thuộc thao tác thủ công: nhận/tải chứng từ, đọc hóa đơn, xác định khách hàng, kiểm tra trùng lặp/mâu thuẫn, hỏi bổ sung, quản lý thiếu chứng từ, nhập dữ liệu thủ công. |
| Purpose | Hiện trạng: tốn thời gian, dễ sai, khó mở rộng khi một kế toán phụ trách nhiều khách hàng.<br>Mong muốn: chuẩn hóa và tự động hóa khâu intake để kế toán tập trung xử lý ngoại lệ. |
| Objective | Tự động hóa quy trình intake chứng từ; giảm thời gian thao tác thủ công theo mục tiêu pilot; nâng chất lượng dữ liệu đầu vào trước hạch toán. |
| Timeline | Chia theo 10 Epic MVP V1; sequencing theo phụ thuộc kỹ thuật và nghiệp vụ. |
| Scope of work | Functional requirements:<br>- Intake chứng từ từ Zalo (ảnh/PDF/tin nhắn); pilot đầu tiên nhập thủ công: tải chứng từ lên, chép chat<br>- Customer & Conversation management<br>- OCR + extraction cơ bản hóa đơn<br>- AI intent understanding và liên kết tin nhắn/chứng từ<br>- Validation thiếu/trùng/mâu thuẫn<br>- Exception + approval workflow + duyệt câu hỏi trước khi gửi khách<br>- Dashboard kế toán cơ bản<br>- Export Excel/CSV<br>- Security/Audit/Testing cốt lõi<br>Non-functional requirements:<br>- Security, traceability, idempotency, phân quyền theo vai trò, multi-tenant với cô lập dữ liệu tại PostgreSQL (RLS), testability, kiến trúc module hóa |
| Input | Brief nghiệp vụ đã xác nhận, chính sách ngôn ngữ, ranh giới MVP V1, danh sách 10 Epic, governance constraints, external constraints, KPI định hướng pilot. |
| Output | Deliverables:<br>- Bộ tài liệu overview + constitution cho MVP V1 và Epic split<br>- Định nghĩa scope rõ ràng để làm đầu vào cho specify/plan/tasks<br>Hình thức bàn giao:<br>- Tài liệu trong thư mục `docs/overview/` của repository |
| Completion Criteria | Overview thống nhất Domain, Users, Goals, Scope, Out of Scope, Governance, External Constraints, Language Policy, Epic Split; không mở rộng sang V2–V5. |
| System (Tool) name | Accounting Intake Agent |
| Model/Service | OCR theo kiến trúc đã phê duyệt (mục 3.13). Không tự động thêm LLM hoặc dịch vụ AI bên ngoài; không gửi dữ liệu khách hàng tới dịch vụ AI nước ngoài trong giai đoạn hiện tại |
| Environment | DEV, STG, PROD |
| - Server | Containerized services (Docker) trên hạ tầng sẽ quyết định ở giai đoạn plan |
| - License | Sẽ xác nhận khi chọn OCR và thư viện phụ thuộc |
| - OSS | Cho phép dùng OSS phù hợp chính sách bảo mật và license của tổ chức |
| - Hardware/Software/Network | Ưu tiên môi trường đủ cho xử lý OCR và web dashboard |
| - OS | Linux (ưu tiên) |
| - Device | Desktop/Laptop cho kế toán và quản lý |
| - Browser | Chrome/Edge bản mới |
| UI/UX | Web dashboard đơn giản, ưu tiên tính rõ ràng thao tác kiểm tra và xử lý ngoại lệ |
| Unit Testing (UT) | Bắt buộc cho business rules quan trọng và module chính |
| Constraint/Prerequisites | Human-in-the-loop cho quyết định nghiệp vụ kế toán quan trọng; không xử lý tự động có ảnh hưởng pháp lý mà thiếu xác nhận người phụ trách |
| Infra | Docker-based local/dev setup, mở rộng infra chi tiết ở giai đoạn plan |

## 1.3 Project Management

| Category/Type | Details |
|-|-|
| Project name | Accounting Intake Agent |
| Project code | AIA-MVP-V1 |
| Contract Type | Proposed: ActualTime&Material/時間-材料契約 (cần xác nhận chính thức) |
| Service Product Type | Proposed: Customer Product & Service (cần xác nhận chính thức) |
| Project Type | Proposed: 顧客DX1 (cần xác nhận chính thức) |
| Project Management Method | Proposed: Hybrid-Agile (cần xác nhận chính thức) |
| Progress Tracking | Proposed: Jira hoặc công cụ tương đương (TBD khi kickoff thực thi) |
| Source Code Management | Proposed: GitHub/GitLab (TBD theo môi trường triển khai) |
| Communication Plan | Proposed: Daily sync nội bộ + weekly stakeholder review (TBD theo lịch dự án) |
| Report Format/Content/Language/Frequency | Proposed: Báo cáo tuần về tiến độ/rủi ro/KPI pilot; tiếng Việt (TBD mẫu biểu chính thức) |

---

# 2. PROJECT PRINCIPLES

## 2.1 Governance Principles

1. Tách biệt kiến trúc theo lớp: Channel Adapter, AI Engine, Business Rules, API, Database.
2. Human-in-the-loop bắt buộc cho quyết định nghiệp vụ kế toán quan trọng.
3. Mọi quyết định AI ảnh hưởng dữ liệu kế toán phải truy vết được qua audit log.
4. Không xóa vĩnh viễn chứng từ dựa trên hội thoại; chỉ chuyển trạng thái như Cancelled/Excluded và lưu lịch sử.
5. AI confidence score là tín hiệu hỗ trợ, không thay thế quy tắc xác nhận nghiệp vụ.

## 2.2 Engineering Standards

1. Code dễ đọc, module hóa, ưu tiên kiến trúc đơn giản, có thể chạy/kiểm thử từng phần.
2. Không hard-code API key, token, password, secret; dùng environment variables hoặc secret management.
3. Bắt buộc review code trước khi merge.
4. Áp dụng retry, idempotency, error handling cho webhook và pipeline xử lý chứng từ.
5. Giữ business logic độc lập nền tảng kênh giao tiếp để mở rộng sau MVP.

## 2.3 Testing & Quality Gates

1. Business rules quan trọng phải có automated tests.
2. Có unit test và integration test cho các workflow chính của MVP V1.
3. Mỗi Epic phải có acceptance criteria kiểm chứng được ở mức tổng quan.
4. Chỉ đưa tính năng đã qua review + kiểm thử vào trạng thái sẵn sàng bàn giao nội bộ.

---

# 3. PROJECT OVERVIEW AND CONSTRAINTS

## 3.1 Domain

Accounting Intake Agent là hệ thống AI Automation hỗ trợ công ty dịch vụ kế toán, đại lý thuế và kế toán viên tiếp nhận, phân loại, kiểm tra và quản lý chứng từ từ các kênh giao tiếp. Hệ thống đóng vai trò lớp xử lý dữ liệu đầu vào trước khi dữ liệu được chuyển sang phần mềm kế toán như MISA/EasyBooks, không thay thế hệ thống kế toán lõi.

## 3.2 Users

1. Customer: gửi chứng từ và phản hồi bổ sung thông tin.
2. Accountant: kiểm tra kết quả AI, xử lý ngoại lệ, phê duyệt/chỉnh sửa/từ chối.
3. Manager: theo dõi tiến độ, hiệu suất xử lý, tỷ lệ lỗi và hiệu quả automation.
4. Admin: quản lý người dùng, phân quyền, cấu hình tích hợp và policy vận hành.

## 3.3 Product Goals

1. Tự động hóa intake và tiền xử lý chứng từ trước hạch toán.
2. Giảm thời gian thao tác thủ công theo mục tiêu pilot tối thiểu 50% trên workflow chọn lọc sau đo baseline.
3. Tăng độ chính xác trích xuất/nhận diện intent và khả năng phát hiện thiếu-trùng-mâu thuẫn.
4. Chuyển mô hình vận hành sang exception-based workflow.
5. Chuẩn hóa dữ liệu để sẵn sàng tích hợp phần mềm kế toán ở các giai đoạn sau.

## 3.4 MVP V1 Scope

### In Scope (chỉ MVP V1)

1. Tiếp nhận chứng từ và tin nhắn từ Zalo (ảnh, PDF, text). Pilot đầu tiên: kế toán nhập thủ công (tải chứng từ lên, chép chat); chưa dùng Zalo OA.
2. Quản lý Customer và liên kết người gửi trên Zalo với Customer.
3. Lưu trữ Message, Conversation, Document.
4. OCR + trích xuất dữ liệu cơ bản từ hóa đơn.
5. AI nhận diện intent và liên kết tin nhắn với chứng từ liên quan.
6. Validation cho thiếu dữ liệu, trùng lặp, mâu thuẫn.
7. Soạn yêu cầu bổ sung chứng từ, bắt buộc kế toán duyệt trước khi gửi. Pilot (chưa có Zalo OA): kế toán tự gửi qua Zalo; hệ thống không tự gửi.
8. Dashboard cơ bản: Customer List, Document List, Document Detail, Exception Inbox, Overview.
9. Accountant Review/Approve/Reject/Correct.
10. Export dữ liệu đã duyệt ra Excel/CSV.
11. Audit log cho thao tác quan trọng.
12. Bộ dữ liệu giả lập và test case hội thoại kế toán thực tế.

### Confirmed Tech Stack (MVP V1)

- Backend: Python + FastAPI
- Database: PostgreSQL
- Web Dashboard: Next.js
- Channel Integration: Zalo. Pilot đầu tiên nhập thủ công; Zalo OA chỉ triển khai sau khi xác minh nhu cầu, khả năng tích hợp, chi phí và được duyệt. Telegram không phải kênh MVP.
- AI/Data Extraction: OCR theo kiến trúc đã phê duyệt (mục 3.13). Không có LLM hoặc dịch vụ AI bên ngoài trong luồng xử lý.
- Multi-tenant: mỗi công ty dịch vụ kế toán là một tenant, cô lập bằng PostgreSQL Row Level Security (mục 3.14)
- Runtime/Development: Docker

## 3.5 Future Roadmap (ngoài MVP hiện tại, chưa triển khai)

- V2: Import sao kê ngân hàng, Transaction Matching, Missing Document Detection.
- V3: AI follow-up tự động nâng cao, reminder policy, conversation memory nâng cao.
- Zalo OA: sau khi xác minh nhu cầu, khả năng tích hợp và chi phí, cần được duyệt (không gắn với phiên bản cụ thể).
- V4: Email, MISA/EasyBooks integration.
- Telegram: chỉ bổ sung khi có lý do kinh doanh rõ ràng và được duyệt.
- LLM hoặc dịch vụ AI bên ngoài: chỉ xem xét qua đề xuất theo mục 3.13.
- V5: Dashboard nâng cao, business rules theo khách hàng, AI học từ feedback, mở rộng accounting context graph.

## 3.6 Out of Scope

1. Xây dựng hệ thống kế toán tổng hợp/General Ledger.
2. Tự động hạch toán chính thức vào MISA.
3. Tự động tính/kê khai/nộp thuế hoặc lập báo cáo tài chính.
4. Tích hợp ngân hàng trực tiếp trong MVP.
5. Zalo OA (cho tới khi được xác minh và duyệt), Telegram, Email, Messenger integration trong MVP.
6. Mobile app native.
7. Tự động gửi hàng loạt tin nhắn nhắc chứng từ không kiểm soát.
8. AI tự quyết định kế toán/thuế có ảnh hưởng pháp lý mà không có phê duyệt người phụ trách.
9. Hệ thống tự học/thay đổi business rules trong production không kiểm soát.
10. Gửi dữ liệu khách hàng tới dịch vụ AI nước ngoài; tự động thêm LLM hoặc dịch vụ AI bên ngoài vào luồng xử lý.
11. Dùng dữ liệu pilot để huấn luyện mô hình khi chưa có sự đồng ý riêng phù hợp.

## 3.7 External Constraints

### Business Constraints

1. MVP lấy Zalo làm kênh ưu tiên. Không đọc chat Zalo cá nhân bằng phương thức không chính thức; Zalo OA phải tuân thủ quyền truy cập, policy và chi phí của nền tảng.
2. Tích hợp MISA/EasyBooks phụ thuộc API, quyền và điều kiện sử dụng của nhà cung cấp.
3. KPI mục tiêu chỉ là mục tiêu pilot, cần xác nhận sau khi đo baseline thực tế.

### Technical Constraints

1. Dữ liệu chứng từ có thể chứa thông tin cá nhân/tài chính nhạy cảm, cần bảo vệ khi lưu trữ, truyền tải và xử lý OCR.
2. Bắt buộc phân tách dữ liệu giữa tenant và giữa khách hàng, kiểm soát truy cập theo vai trò (mục 3.14).
3. Có chính sách retention, xóa dữ liệu, backup, audit log phù hợp.

### Compliance Constraints

1. Cần xác minh yêu cầu pháp lý dữ liệu cá nhân và chứng từ kế toán tại Việt Nam trước khi dùng dữ liệu thật.
2. Trong MVP ưu tiên dữ liệu giả lập hoặc dữ liệu đã ẩn thông tin nhạy cảm.

## 3.8 Document & Exception Lifecycle (MVP V1)

### Document Status

1. `RECEIVED`: Hệ thống đã tiếp nhận tài liệu từ kênh tiếp nhận nhưng chưa xử lý OCR/AI hoàn chỉnh.
2. `PROCESSING`: Đang thực hiện OCR, extraction, intent linking hoặc validation.
3. `NEEDS_REVIEW`: Có cảnh báo thiếu/trùng/mâu thuẫn hoặc uncertainty, cần Accountant xử lý.
4. `APPROVED`: Accountant đã xác nhận tài liệu đủ điều kiện đi tiếp sang export/integration scope của MVP.
5. `REJECTED`: Accountant xác nhận tài liệu không hợp lệ cho workflow hiện tại.
6. `EXCLUDED`: Tài liệu bị loại khỏi xử lý nghiệp vụ do gửi nhầm/ngoài phạm vi, vẫn lưu lịch sử.

### Exception Status (tách biệt với Document Status)

1. `OPEN`: Exception mới phát sinh và chưa được xử lý.
2. `WAITING_CUSTOMER`: Đã gửi yêu cầu bổ sung/làm rõ và đang chờ phản hồi.
3. `IN_REVIEW`: Accountant đang phân tích hoặc cập nhật quyết định.
4. `RESOLVED`: Exception đã được xử lý xong, có kết luận nghiệp vụ.
5. `CLOSED`: Đóng case sau khi đã hoàn tất hành động cần thiết.

### Lifecycle Rules

1. Không đồng nhất Document Status và Exception Status; một Document có thể `NEEDS_REVIEW` trong khi Exception ở `WAITING_CUSTOMER`.
2. Chỉ Accountant/Manager (theo phân quyền) được chuyển trạng thái sang `APPROVED`, `REJECTED`, `EXCLUDED`.
3. AI/service chỉ được chuyển trạng thái kỹ thuật `RECEIVED` → `PROCESSING` → `NEEDS_REVIEW` khi có evidence rõ ràng.
4. Mọi chuyển trạng thái phải có Audit Log gồm actor, timestamp, trạng thái trước/sau, lý do và reference IDs.

## 3.9 Customer Identity Verification (người gửi ↔ Customer)

1. Liên kết người gửi trên kênh tiếp nhận (Zalo) ↔ Customer phải được Admin hoặc Accountant xác nhận trước khi đưa vào xử lý nghiệp vụ chính thức. Khi nhập thủ công, Accountant chọn Customer cho từng đợt nhập; lựa chọn đó là bước xác nhận và phải được audit.
2. AI không được tự xác nhận chủ sở hữu chứng từ chỉ dựa trên tên người gửi, nội dung hội thoại hoặc OCR text.
3. Dữ liệu chưa xác minh chủ sở hữu phải ở vùng chờ xác minh riêng (`UNVERIFIED_QUEUE`) và không được auto-approve.
4. Khi thiếu căn cứ định danh, hệ thống phải tạo exception để human review thay vì tự động gán Customer.

## 3.10 AI Uncertainty Handling

1. Không tự đoán khi không xác định được Customer/Document hoặc khi dữ liệu mơ hồ.
2. Không tự động thực hiện hành động nghiệp vụ quan trọng khi confidence thấp hoặc evidence không đủ.
3. Confidence score chỉ là tín hiệu hỗ trợ, không dùng làm bằng chứng duy nhất cho auto-decision.
4. Mỗi quyết định AI cần lưu evidence/reference có thể kiểm chứng (ví dụ: Message ID, Document ID, extracted fields, confidence, business rule hit).
5. Trường hợp uncertainty phải route sang human review qua exception workflow.

## 3.11 KPI Definitions & Baseline Method (Pilot)

1. `Manual Handling Time` (KPI chính): số phút kế toán thao tác trực tiếp cho mỗi hộ (Customer) trong mỗi tháng (phút/hộ/tháng).
   - KPI phụ: phút/chứng từ = phút/hộ/tháng chia cho số chứng từ (ảnh, PDF) của hộ đó được tiếp nhận trong tháng, không tính chứng từ `EXCLUDED`. Chỉ dùng để so sánh giữa các hộ hoặc các tháng, không thay KPI chính.
   - Trong app: tính từ nhịp hoạt động của kế toán trên màn hình gắn với hộ, mỗi phút có hoạt động tính một phút, theo giờ Việt Nam. Việc làm ngoài app (gọi điện, nhắn Zalo, nhập phần mềm kế toán) do kế toán tự ghi và cộng vào.
2. `Extraction Accuracy`: tỷ lệ trường dữ liệu OCR/extraction chính xác theo bộ kiểm định.
3. `Intent Accuracy`: tỷ lệ intent nhận diện đúng theo nhãn chuẩn.
4. `Duplicate Detection Recall`: tỷ lệ chứng từ trùng thực tế được phát hiện.
5. `Exception Rate`: số chứng từ cần người xử lý / tổng chứng từ intake.
6. `Follow-up Resolution Rate`: tỷ lệ yêu cầu bổ sung được giải quyết thành công.
7. `Critical Error Count`: số lỗi nghiêm trọng do quyết định tự động sai.

### Baseline Measurement Rules

1. Đo baseline trên workflow thủ công trước pilot và lưu cùng kỳ đo so sánh. Baseline được quy ra phút/hộ/tháng (số phút đo được chia số ngày đo, nhân số ngày làm việc trong tháng) để so cùng đơn vị với KPI chính.
2. Tách riêng ba thành phần thời gian: thời gian AI xử lý, thời gian kế toán thao tác, thời gian chờ khách hàng.
3. Chỉ kết luận mức tiết kiệm sau khi so sánh cùng phạm vi nghiệp vụ và cùng loại chứng từ.

## 3.12 Language Policy

1. Chat, tài liệu nghiệp vụ, PRD, User Story, Acceptance Criteria dùng tiếng Việt có dấu.
2. Code file, class, function, variable, identifier, database table/column, config key dùng English.
3. Comment trong code dùng English khi cần.
4. UI ưu tiên tiếng Việt cho người dùng Việt Nam.
5. Giữ nguyên các thuật ngữ kỹ thuật đã chốt: Accounting Intake Agent, Customer, Accountant, Manager, Admin, OCR, LLM, Document, Conversation, Intent, Validation, Matching, Exception, Human-in-the-loop, API, MVP, Telegram, Zalo, MISA, Audit Log.

## 3.13 AI & Data Policy

1. OCR được phép sử dụng theo kiến trúc đã phê duyệt, với điều kiện đáp ứng yêu cầu bảo mật và xử lý dữ liệu.
2. Không gửi dữ liệu khách hàng đến dịch vụ AI nước ngoài trong giai đoạn hiện tại.
3. Không tự động thêm LLM hoặc dịch vụ AI bên ngoài vào luồng xử lý.
4. Mọi đề xuất thay đổi chính sách này phải nêu rõ: nhà cung cấp, nơi xử lý dữ liệu, loại dữ liệu được gửi, chi phí và các vấn đề pháp lý cần xác minh; chỉ áp dụng sau khi được duyệt và cập nhật Constitution.
5. Không sử dụng dữ liệu pilot để huấn luyện mô hình nếu chưa có sự đồng ý riêng phù hợp.

## 3.14 Multi-tenant & Tenant Isolation

1. Kiến trúc multi-tenant áp dụng ngay từ MVP: mỗi công ty dịch vụ kế toán là một tenant.
2. Cô lập dữ liệu giữa tenant được thực thi tại PostgreSQL bằng Row Level Security, không chỉ ở tầng API.
3. Ứng dụng kết nối bằng role không phải superuser, không có BYPASSRLS.
4. Không được coi RLS là an toàn chỉ vì migration hoặc test cơ bản đã qua. Phải kiểm tra bằng role ứng dụng, với các tình huống truy cập chéo tenant: đọc, sửa, xóa, chèn dữ liệu mang tenant khác, tham chiếu khóa ngoại sang tenant khác, truy cập khi chưa xác định tenant, và các hàm chạy với quyền nâng cao (SECURITY DEFINER).

## 3.15 Requirement Sources

1. Constitution xác định nguyên tắc bất biến, ranh giới bảo mật và các quyết định kiến trúc cấp cao.
2. Spec xác định hành vi và tiêu chí nghiệm thu của từng tính năng.
3. Code phải tuân theo các tài liệu đã được phê duyệt.
4. Khi code, Constitution và Spec mâu thuẫn, không tự chọn một bên: báo cáo mâu thuẫn và đề xuất sửa trước khi tiếp tục.
5. Giữ nguyên lịch sử Git; không rebase, force-push hoặc xóa thay đổi hiện có.

---

# 4. PROJECT STAGES (EPIC SPLIT)

## 4.1 Epic 1: Project Foundation & Authentication

### Scope Objective
Thiết lập nền tảng kỹ thuật tối thiểu để các Epic sau phát triển nhất quán và an toàn.

### Prerequisites
- Scope MVP V1 và language policy đã xác nhận.
- Quy ước môi trường và cấu trúc repository được thống nhất.

### Required Inputs
- Danh sách vai trò (Customer, Accountant, Manager, Admin).
- Tech stack đã chốt.

### Deliverables
- Khung backend/frontend/database chạy được bằng Docker.
- Cơ chế authentication và phân quyền vai trò cơ bản.
- Nền tảng multi-tenant với cô lập dữ liệu bằng Row Level Security (mục 3.14).
- Thiết lập config môi trường và quản lý secrets theo nguyên tắc không hard-code.

### Completion Criteria
- Môi trường local khởi chạy ổn định.
- Người dùng theo vai trò truy cập đúng phạm vi chức năng cơ bản.
- Có UT cơ bản cho auth/authorization rules cốt lõi.
- Có test truy cập chéo tenant chạy bằng role ứng dụng theo mục 3.14.

---

## 4.2 Epic 2: Channel Intake (Zalo-first)

### Scope Objective
Xây dựng kênh intake chính của MVP V1 để nhận dữ liệu đầu vào từ Zalo. Pilot đầu tiên dùng nhập thủ công; Zalo OA không thuộc phạm vi cho tới khi được xác minh và duyệt (mục 3.4, 3.5).

### Prerequisites
- Hoàn thành Epic 1.

### Required Inputs
- Định dạng dữ liệu cần lưu cho tin nhắn và chứng từ, độc lập với kênh (nguồn dữ liệu được ghi rõ cho từng tin).
- Danh sách loại nội dung hỗ trợ (text/image/PDF).

### Deliverables
- Nhập thủ công: tải chứng từ lên, dán hoặc chép nội dung chat Zalo, Accountant chọn Customer và ngày kinh doanh cho mỗi đợt nhập.
- Không tự điền metadata không có bằng chứng (giờ gửi, người gửi).
- Pipeline tiếp nhận và lưu dữ liệu gốc có idempotency/retry.
- Logging và xử lý lỗi cơ bản cho inbound flow.

### Completion Criteria
- Nhập thành công text/image/PDF vào hệ thống, dữ liệu gốc không bị sửa hay mất.
- Không tạo bản ghi trùng khi thao tác nhập được gửi lại.
- Có test tích hợp cho luồng tiếp nhận chính.

---

## 4.3 Epic 3: Customer & Conversation Management

### Scope Objective
Quản lý định danh khách hàng và cấu trúc hội thoại/chứng từ để phục vụ xử lý nghiệp vụ.

### Prerequisites
- Hoàn thành Epic 2.
- Quy tắc liên kết người gửi trên Zalo với Customer đã thống nhất.

### Required Inputs
- Mô hình dữ liệu Customer, Conversation, Message, Document mức MVP.
- Quy tắc truy cập theo vai trò.

### Deliverables
- CRUD tối thiểu cho Customer.
- Lưu và hiển thị Conversation/Message/Document liên quan.
- Cơ chế liên kết khách hàng với dữ liệu intake có bước xác minh người gửi ↔ Customer (mục 3.9).
- Hàng đợi `UNVERIFIED_QUEUE` cho dữ liệu chưa xác minh chủ sở hữu.

### Completion Criteria
- Kế toán tìm được chứng từ theo khách hàng và hội thoại.
- Không lẫn dữ liệu giữa khách hàng khác nhau.
- Case chưa xác minh không đi vào luồng approve chính thức trước khi human xác nhận.
- Audit log có dấu vết thao tác chỉnh sửa chính.

---

## 4.4 Epic 4: Document Intelligence

### Scope Objective
Thực hiện OCR và trích xuất dữ liệu hóa đơn cơ bản phục vụ bước validation/approval.

### Prerequisites
- Hoàn thành Epic 3.
- Có cơ chế upload/luồng file ảnh-PDF ổn định.

### Required Inputs
- Trường dữ liệu hóa đơn cần trích xuất trong MVP.
- Bộ dữ liệu giả lập cho test OCR.

### Deliverables
- OCR pipeline cho ảnh/PDF.
- Phân loại chứng từ cơ bản.
- Extraction các trường chính: nhà cung cấp, mã số thuế, số hóa đơn, ngày, số tiền, thuế, nội dung.

### Completion Criteria
- Trích xuất được dữ liệu cơ bản trên tập test MVP.
- Lưu kết quả extraction và confidence phục vụ review.
- Có test cho parsing/normalization logic cốt lõi.

---

## 4.5 Epic 5: AI Conversation Understanding

### Scope Objective
Nhận diện intent và liên kết ngữ cảnh hội thoại với chứng từ liên quan trong phạm vi MVP.

### Prerequisites
- Hoàn thành Epic 3 và Epic 4.
- Danh sách intent MVP được chốt.

### Required Inputs
- Taxonomy intent MVP: SUBMIT_DOCUMENT, CANCEL_DOCUMENT, CORRECT_DOCUMENT, PAYMENT_CONFIRMATION, WRONG_BUSINESS, MISSING_DOCUMENT, PROMISE_TO_SEND, QUESTION.
- Bộ hội thoại giả lập và nhãn kiểm thử.

### Deliverables
- Module inference intent cho message hội thoại.
- Cơ chế liên kết message với document liên quan theo ngữ cảnh gần.
- Lưu evidence/reference phục vụ kế toán kiểm tra (Message ID, Document ID, extracted fields, confidence, business-rule hits).

### Completion Criteria
- Intent nhận diện được trên bộ test giả lập với ngưỡng chấp nhận nội bộ.
- Kế toán xem được liên kết hội thoại-chứng từ và có thể chỉnh sửa khi cần.
- Có test integration cho luồng message → intent → link.

---

## 4.6 Epic 6: Validation Engine

### Scope Objective
Phát hiện dữ liệu thiếu, trùng lặp, sai hoặc mâu thuẫn để giảm lỗi trước khi duyệt.

### Prerequisites
- Hoàn thành Epic 4 và Epic 5.
- Quy tắc validation MVP được xác định.

### Required Inputs
- Danh sách trường bắt buộc theo loại chứng từ MVP.
- Quy tắc phát hiện trùng/mâu thuẫn mức cơ bản.

### Deliverables
- Rule engine kiểm tra thiếu dữ liệu và bất thường.
- Kiểm tra trùng lặp hóa đơn ở mức MVP.
- Cờ mâu thuẫn giữa dữ liệu chứng từ và thông tin hội thoại.

### Completion Criteria
- Hệ thống gắn trạng thái validation rõ ràng cho từng document.
- Rule quan trọng có UT tự động.
- Kết quả validation hiển thị để kế toán xử lý tiếp ở Epic 7.

---

## 4.7 Epic 7: Exception & Approval Management

### Scope Objective
Vận hành mô hình exception-based workflow và luồng yêu cầu bổ sung chứng từ với duyệt bắt buộc trước khi gửi khách.

### Prerequisites
- Hoàn thành Epic 6.
- Có phân quyền kế toán/manager/admin từ Epic 1.

### Required Inputs
- Định nghĩa trạng thái exception và hành động review.
- Chính sách duyệt câu hỏi follow-up trước khi gửi khách.

### Deliverables
- Exception Inbox logic và trạng thái xử lý.
- Tác vụ Review/Approve/Reject/Correct cho Accountant.
- Luồng follow-up trạng thái: `DRAFT` → `PENDING_APPROVAL` → `APPROVED` → `SENDING` → `SENT` → `ANSWERED`. Trong pilot chưa có Zalo OA, bước gửi do Accountant thực hiện thủ công qua Zalo; hệ thống không tự gửi.
- Trạng thái ngoại lệ follow-up: `REJECTED`, `SEND_FAILED` và cơ chế retry có idempotency key chống gửi trùng.
- Liên kết phản hồi khách hàng vào Document/Exception liên quan để đóng vòng xử lý.

### Completion Criteria
- Không có câu hỏi follow-up nào gửi tới khách hàng khi chưa được duyệt.
- Một câu hỏi đã duyệt không bị gửi trùng khi webhook/API retry.
- Trạng thái gửi thành công/thất bại và phản hồi khách hàng được theo dõi end-to-end.
- Quyết định của kế toán được lưu audit trail.
- Case ngoại lệ được phân loại và đóng/mở theo trạng thái rõ ràng.

---

## 4.8 Epic 8: Accountant Dashboard

### Scope Objective
Cung cấp giao diện nghiệp vụ tối thiểu để kế toán thao tác xuyên suốt workflow MVP.

### Prerequisites
- Hoàn thành Epic 3 và Epic 7.
- API nghiệp vụ chính đã sẵn sàng.

### Required Inputs
- Danh sách màn hình MVP: Customer List, Document List, Document Detail, Exception Inbox, Overview.
- Quyền truy cập theo vai trò.

### Deliverables
- Web dashboard Next.js cho các màn hình MVP.
- Luồng thao tác review/chỉnh sửa/phê duyệt từ UI.
- Hiển thị trạng thái validation, intent, exception, audit trace cơ bản.

### Completion Criteria
- Accountant hoàn thành workflow review chính trên UI.
- Manager/Admin xem được overview trạng thái theo quyền.
- UI dùng tiếng Việt theo language policy.

---

## 4.9 Epic 9: Export & Reporting

### Scope Objective
Xuất dữ liệu đã duyệt và cung cấp báo cáo vận hành MVP.

### Prerequisites
- Hoàn thành Epic 7 và Epic 8.
- Mô hình dữ liệu reviewed/approved ổn định.

### Required Inputs
- Mẫu export Excel/CSV tối thiểu.
- Danh sách chỉ số báo cáo MVP.

### Deliverables
- Export Excel/CSV cho dữ liệu đã duyệt theo schema nhất quán.
- Báo cáo số lượng chứng từ, số lượng exception, thời gian xử lý cơ bản.
- Cơ chế lọc dữ liệu theo khách hàng/thời gian trong phạm vi MVP.

### Completion Criteria
- File export đúng cấu trúc trường, định dạng dữ liệu và trạng thái phê duyệt đã chốt.
- Báo cáo phản ánh trạng thái vận hành thực tế trong hệ thống.
- Có test kiểm tra mapping dữ liệu export cốt lõi.

---

## 4.10 Epic 10: Security, Audit & Testing

### Scope Objective
Hoàn thiện kiểm thử end-to-end, security review, traceability review và pilot readiness sau khi các kiểm soát xuyên suốt đã áp dụng ở Epic 1–9.

### Prerequisites
- Các kiểm soát security, audit, testing đã được thực thi xuyên suốt trong Epic 1–9.
- Danh sách workflow chính đã xác định.

### Required Inputs
- Yêu cầu bảo vệ dữ liệu nhạy cảm và phân quyền truy cập.
- Danh sách test case ưu tiên cho workflow chính.

### Deliverables
- Bộ kiểm thử end-to-end cho các workflow liên Epic (intake → AI → validation → follow-up → review → export).
- Báo cáo security review và traceability review ở mức pilot readiness.
- Báo cáo tổng hợp độ phủ test + các risk còn lại trước pilot.

### Completion Criteria
- Truy vết được các thao tác quan trọng đầu-cuối.
- Test suite chính chạy ổn định ở mức chấp nhận nội bộ.
- Không còn lỗ hổng cấu hình nghiêm trọng đã biết trước khi pilot.
- Có biên bản readiness xác nhận kiểm soát security/audit/testing đã áp dụng xuyên suốt, không chỉ tại riêng Epic 10.

---

# 5. GLOSSARY AND REFERENCES

## 5.1 Glossary

| No | Term | Meaning | Notes |
|-|-|-|-|
| 1 | Accounting Intake Agent | Hệ thống tiếp nhận và tiền xử lý chứng từ kế toán bằng AI trước hạch toán | Không thay thế phần mềm kế toán lõi |
| 2 | Exception-based Workflow | Mô hình vận hành trong đó AI xử lý phần lớn case chuẩn, kế toán tập trung xử lý ngoại lệ | Nguyên tắc cốt lõi của MVP |
| 3 | Human-in-the-loop | Quy trình yêu cầu người phụ trách xác nhận ở các quyết định quan trọng | Bắt buộc cho hành động ảnh hưởng dữ liệu kế toán |
| 4 | Validation Engine | Thành phần kiểm tra dữ liệu thiếu, trùng, sai, mâu thuẫn | Thuộc MVP V1 |
| 5 | Audit Log | Nhật ký truy vết thao tác hệ thống, AI và người dùng | Phục vụ kiểm soát, điều tra, compliance |

## 5.2 References

| No | Document Type | Document Name | Link/Location |
|-|-|-|-|
| 1 | Skill Reference | verikit-constitution SKILL | `C:\Users\TuanMQ\.agents\skills\verikit-constitution\SKILL.md` |
| 2 | Template Reference | Constitution Template | `C:\Users\TuanMQ\.agents\skills\.verikit\verikit-templates\constitution-template.md` |
| 3 | Project Input | Confirmed project brief and Epic decisions | User clarification in current session |
| 4 | Decision | Quyết định 2026-10-26: Zalo là kênh ưu tiên, chính sách AI & dữ liệu, multi-tenant từ MVP, nguồn yêu cầu chuẩn | Product Owner, phiên làm việc 2026-10-26 |
| 5 | Decision | Quyết định 2026-10-29: KPI chính phút/hộ/tháng, KPI phụ phút/chứng từ; spec Epic 1 chính thức là `docs/specifications/epic-01-project-foundation-authentication-spec.md` | Product Owner, phiên làm việc 2026-10-29 |

