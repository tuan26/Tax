# Spec Checklist: Epic 001 - Project Foundation & Authentication

**Purpose**: Xác nhận chất lượng tài liệu `spec.md` cho Epic 001 theo template VeriKit, đúng phạm vi MVP V1 và nhất quán với `docs/overview/constitution.md` v2.0.0.0.
**Created**: 2026-10-12
**Feature**: `docs/E1-ProjectFoundationAuthentication/spec.md`

**Review Ownership**: Đây là checklist đánh giá chất lượng tài liệu specification.
**Marker Semantics**: `[x]` nghĩa là tiêu chí đã được rà soát và đạt ở lần kiểm tra hiện tại.

## Scope & Governance Alignment

- [ ] CHK001 Spec chỉ bao phủ Epic 001, không mở rộng sang Epic 002–010.
- [ ] CHK002 Nội dung nhất quán với scope objective, deliverables và completion criteria của Epic 1 trong `constitution.md`.
- [ ] CHK003 Thuật ngữ, language policy, governance/security/audit principles bám theo `constitution.md` v2.0.0.0.
- [ ] CHK004 Tất cả giả định ngoài input người dùng được ghi rõ và không mâu thuẫn tài liệu nguồn.

## Template & Structure Integrity

- [ ] CHK005 `spec.md` dùng đúng thứ tự heading bắt buộc của `spec-template.md`, không thiếu/không thừa section.
- [ ] CHK006 Các bảng bắt buộc hiện diện đúng cột ngữ nghĩa; tiêu đề cột dùng tiếng Việt nhất quán.
- [ ] CHK007 Có `## 1. Questions & Answers` và ghi lại đầy đủ toàn bộ câu hỏi, câu trả lời, quyết định Deferred/TBD.
- [ ] CHK008 Không còn placeholder template (ví dụ `[ROLE_*]`, `[SCREEN_*]`, `[REQUIREMENT_ID]`) hoặc HTML comment block.

## Requirement Quality

- [ ] CHK009 Functional requirements rõ ràng, kiểm thử được, bám đúng luồng chính authentication/session/authz của Epic 1.
- [ ] CHK010 Non-functional requirements bao phủ security, audit, traceability, reliability, testability ở mức cần cho Epic 1.
- [ ] CHK011 Scope in/out, error handling, business rules, success criteria nhất quán chéo giữa các section.
- [ ] CHK012 Nội dung không rò rỉ chi tiết implementation vượt mức cần thiết cho specification nghiệp vụ.

## Security, Access Control & Audit Coverage

- [ ] CHK013 Rule authn/authz (RBAC, assignment-based access, default deny, backend enforcement) được mô tả đầy đủ.
- [ ] CHK014 Session/token policy (TTL, rotation, replay detection, revocation, expiration) được định nghĩa nhất quán.
- [ ] CHK015 Security controls (Argon2id, password policy, lockout, rate limit, CSRF, secret handling) có tiêu chí rõ ràng.
- [ ] CHK016 API error code namespace `AUTH_*`, `AUTHZ_*` và audit reason code `AUDIT_*` được chuẩn hóa.
- [ ] CHK017 Audit record schema tối thiểu (Actor, Action, Resource, Result, Timestamp, Reason Code, Correlation ID) được chốt.

## Role-Permission & Flow Artifacts

- [ ] CHK018 Có Role-Permission Matrix mục 4.1, phản ánh đúng Accountant/Manager/Admin/System/Customer (theo phạm vi MVP V1).
- [ ] CHK019 Nếu có deferred role/permission, các nội dung phụ thuộc được đánh dấu `TODO (see Q&A #...)` đúng quy tắc.
- [ ] CHK020 Diagram/flow/wireflow (nếu áp dụng) nhất quán với FR, screen specs và business rules.

## Validation & Readiness

- [ ] CHK021 Tất cả điều kiện deferred được gắn nhãn rõ, có comments chỉ ra section bị ảnh hưởng.
- [ ] CHK022 Không còn unresolved clarification marker.
- [ ] CHK023 Date/Version fields tuân theo quy tắc template và tương thích version A của constitution.
- [ ] CHK024 Spec actionable cho bước plan tiếp theo, không tự tạo implementation plan/tasks/code/migration.

## Notes

- Checklist sẽ được cập nhật trạng thái sau khi hoàn tất phần hỏi đáp, xác nhận section và rà soát artifact thực tế.
