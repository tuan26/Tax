# Constitution Checklist: Accounting Intake Agent MVP V1

**Purpose**: Xác nhận `constitution.md` phản ánh đúng phạm vi đã chốt, không mở rộng ngoài MVP V1, và nhất quán giữa governance/constraints/epic split.
**Created**: 2026-10-12
**Feature**: `docs/overview/constitution.md`

**Review Ownership**: Đây là checklist đánh giá chất lượng tài liệu overview/constitution.
**Marker Semantics**: `[x]` nghĩa là tiêu chí đã được rà soát và đạt.

## Clarification & Confirmation Gate

- [x] CHK001 Đã xác nhận ranh giới MVP V1 cho AI follow-up: gửi qua Telegram nhưng bắt buộc duyệt trước khi gửi.
- [x] CHK002 Đã xác nhận Tech Stack MVP V1: Python/FastAPI, PostgreSQL, Next.js, Telegram Bot API, OCR+LLM, Docker.
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
- [x] CHK014 Đã bổ sung cơ chế xác minh Telegram User/Chat ↔ Customer và `UNVERIFIED_QUEUE`.

## AI & Pilot Measurement Gate

- [x] CHK015 Đã bổ sung nguyên tắc AI Uncertainty Handling và cấm tự động quyết định khi thiếu evidence.
- [x] CHK016 Đã bổ sung KPI definitions + baseline method, tách thời gian AI/kế toán/chờ khách hàng.

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
- Dữ liệu chi tiết cho spec, plan, tasks sẽ được xử lý ở workflow tiếp theo.

