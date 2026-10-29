# Constitution Checklist: Accounting Intake Agent MVP V1

**Purpose**: Xác nhận `constitution.md` phản ánh đúng phạm vi đã chốt, không mở rộng ngoài MVP V1, và nhất quán giữa governance/constraints/epic split.
**Created**: 2026-10-12
**Feature**: `docs/overview/constitution.md`

**Review Ownership**: Đây là checklist đánh giá chất lượng tài liệu overview/constitution.
**Marker Semantics**: `[x]` nghĩa là tiêu chí đã được rà soát và đạt.

## Clarification & Confirmation Gate

- [ ] CHK001 Đã xác nhận ranh giới MVP V1 cho follow-up: yêu cầu bổ sung bắt buộc kế toán duyệt trước khi gửi; trong pilot (chưa Zalo OA) kế toán tự gửi qua Zalo, hệ thống không tự gửi.
- [ ] CHK002 Đã xác nhận Tech Stack MVP V1: Python/FastAPI, PostgreSQL (multi-tenant, RLS), Next.js, kênh Zalo (pilot nhập thủ công, chưa Zalo OA), OCR theo kiến trúc đã duyệt, không LLM hoặc dịch vụ AI bên ngoài, Docker.
- [x] CHK003 Đã xác nhận Language Policy (tài liệu tiếng Việt, code/identifier tiếng Anh, UI ưu tiên tiếng Việt).
- [x] CHK004 Đã xác nhận số lượng Epic là 10 và tên Epic cụ thể cho MVP V1.

## Scope Lock & Coverage

- [x] CHK005 Phần Domain, Users, Goals, Scope, Out of Scope, Governance, External Constraints, Language Policy, Epic Split đều có trong `constitution.md`.
- [x] CHK006 Không đưa chức năng V2–V5 vào phạm vi MVP V1; chỉ ghi trong Future Roadmap.
- [x] CHK007 Không thêm tính năng mới ngoài danh sách đã xác nhận.
- [x] CHK008 Epic sequencing được sắp theo phụ thuộc phát triển từ foundation đến security/testing.

## Constraint Separation Quality

- [x] CHK009 Governance chỉ chứa nguyên tắc/quy trình/chuẩn đội ngũ có thể kiểm soát.
- [x] CHK010 External Constraints chỉ chứa ràng buộc bên ngoài (nền tảng, pháp lý, dữ liệu, vendor).
- [x] CHK011 Không trùng lặp vai trò giữa Governance và External Constraints.

## Lifecycle & Identity Gate

- [x] CHK012 Đã bổ sung Document Lifecycle với trạng thái `RECEIVED`, `PROCESSING`, `NEEDS_REVIEW`, `APPROVED`, `REJECTED`, `EXCLUDED`.
- [x] CHK013 Đã tách Document Status và Exception Status cùng quy tắc chuyển trạng thái + audit.
- [ ] CHK014 Đã bổ sung cơ chế xác minh người gửi trên kênh tiếp nhận (Zalo; nhập thủ công) ↔ Customer và `UNVERIFIED_QUEUE`.

## AI & Pilot Measurement Gate

- [x] CHK015 Đã bổ sung nguyên tắc AI Uncertainty Handling và cấm tự động quyết định khi thiếu evidence.
- [x] CHK016 Đã bổ sung KPI definitions + baseline method, tách thời gian AI/kế toán/chờ khách hàng.
- [ ] CHK025 AI & Data Policy (mục 3.13): OCR theo kiến trúc đã duyệt; không gửi dữ liệu khách hàng tới AI nước ngoài; không tự động thêm LLM/AI bên ngoài; đề xuất thay đổi nêu nhà cung cấp, nơi xử lý, loại dữ liệu, chi phí, pháp lý; không huấn luyện trên dữ liệu pilot khi chưa có đồng ý riêng.

## Tenant & Requirement Source Gate

- [ ] CHK026 Multi-tenant & Tenant Isolation (mục 3.14) có yêu cầu kiểm tra bằng role ứng dụng và các tình huống truy cập chéo tenant, không chấp nhận "migration/test cơ bản đã qua" làm bằng chứng.
- [ ] CHK027 Requirement Sources (mục 3.15) nêu rõ vai trò Constitution/Spec/Code và quy tắc báo cáo mâu thuẫn thay vì tự chọn.

## Epic Quality Gate

- [x] CHK017 Mỗi Epic có đủ mục: Scope Objective, Prerequisites, Required Inputs, Deliverables, Completion Criteria.
- [x] CHK018 Deliverables và Completion Criteria ở mức tổng quan, kiểm chứng được, không đi vào implementation plan chi tiết.
- [x] CHK019 Epic 7 thể hiện đầy đủ workflow follow-up (duyệt, gửi, nhận phản hồi, chống gửi trùng).
- [x] CHK020 Epic 10 được chỉnh thành phase tổng hợp E2E/security review, với yêu cầu kiểm soát xuyên suốt Epic 1–9.
- [x] CHK021 Epic 9 đã nêu nguyên tắc export schema nhất quán (field/format/approval status).

## Document Integrity

- [x] CHK022 Không tạo implementation code, migration, hoặc file kỹ thuật ngoài phạm vi tài liệu overview.
- [x] CHK023 Ngôn ngữ và thuật ngữ kỹ thuật nhất quán với policy đã chốt.
- [x] CHK024 Các thông tin Project Management chưa chốt được gắn nhãn Proposed/TBD.

## Notes

- Checklist này phản ánh trạng thái hoàn tất sau vòng cập nhật constitution theo review của stakeholder.
- Constitution v3.0.0.0 (quyết định 2026-10-26: Zalo-first, AI & Data Policy, multi-tenant RLS, Requirement Sources): CHK001, CHK002, CHK014 và CHK025–CHK027 được để `[ ]` chờ stakeholder rà soát lại.
- Dữ liệu chi tiết cho spec, plan, tasks sẽ được xử lý ở workflow tiếp theo.

