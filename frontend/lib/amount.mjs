// Đọc số tiền kế toán gõ nhanh: 2tr5, 950k, 1t2, 2.350.000, 2350000. Trả về số nguyên đồng hoặc null.
export function parseAmount(input) {
  if (input == null) return null;
  const s = String(input).trim().toLowerCase().replace(/\s+/g, "").replace(/(đ|vnd|dong)$/, "");
  if (!s) return null;
  let m = s.match(/^(\d+(?:[.,]\d+)?)(tr|triệu|trieu|t)(\d{1,3})?$/);
  if (m) {
    if (m[3] && /[.,]/.test(m[1])) return null;
    let v = Math.round(parseFloat(m[1].replace(",", ".")) * 1_000_000);
    if (m[3]) v += parseInt(m[3], 10) * 10 ** (6 - m[3].length);
    return v > 0 ? v : null;
  }
  m = s.match(/^(\d+(?:[.,]\d+)?)k(\d{1,2})?$/);
  if (m) {
    if (m[2] && /[.,]/.test(m[1])) return null;
    let v = Math.round(parseFloat(m[1].replace(",", ".")) * 1_000);
    if (m[2]) v += parseInt(m[2], 10) * 10 ** (3 - m[2].length);
    return v > 0 ? v : null;
  }
  if (/^\d{1,3}([.,]\d{3})+$/.test(s)) return parseInt(s.replace(/[.,]/g, ""), 10);
  if (/^\d+$/.test(s)) {
    const v = parseInt(s, 10);
    return v > 0 ? v : null;
  }
  return null;
}
