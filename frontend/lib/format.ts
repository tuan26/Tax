export const money = (v: number | null | undefined) =>
  v == null ? "—" : new Intl.NumberFormat("vi-VN").format(v) + "đ";

export const day = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
};

export const time = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" }) : null;

export const todayIso = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

export const REASONS: Record<string, string> = {
  amount_missing: "Chưa có số tiền",
  amount_conflict: "Số tiền gõ khác số trên ảnh",
  amount_unresolved: "Có số tiền nhưng chưa rõ thuộc chứng từ nào",
  amount_low_confidence: "Số tiền đọc không chắc",
  posting_date_ambiguous: "Chưa rõ ngày",
  caption_ambiguous: "Chú thích chưa rõ thuộc chứng từ nào",
  correction: "Khách đính chính số đã gửi",
  ocr_failed: "Không đọc được ảnh",
  ocr_empty: "Ảnh không có chữ đọc được",
  new_evidence_after_confirm: "Có bằng chứng mới sau khi đã xác nhận",
};

export const ROLES: Record<string, string> = {
  amount_annotation: "Số tiền",
  caption: "Chú thích",
  date_annotation: "Ghi chú ngày",
  date_correction: "Sửa ngày",
  correction: "Đính chính",
  duplicate_of: "Có thể trùng",
};

export const UNMATCHED: Record<string, string> = {
  no_anchor_in_window: "Không có chứng từ nào gửi gần đó",
  noise: "Tin không rõ nội dung",
  unsupported_content: "Loại tin chưa hỗ trợ",
  conflicts_with_existing_group: "Xung đột với nhóm đã xác nhận",
  candidates_unavailable: "Không còn ứng viên",
  non_document: "Có thể không phải chứng từ",
};

export const KIND: Record<string, string> = {
  document: "Chứng từ",
  bank_transfer_screenshot: "Chuyển khoản",
  self_declared: "Tự khai",
};
