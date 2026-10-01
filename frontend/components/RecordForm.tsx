"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { parseAmount } from "@/lib/amount.mjs";
import { day, money, REASONS } from "@/lib/format";
import type { LedgerRecord, RecordFields } from "@/lib/types";

function band(conf: number | null | undefined, value: unknown) {
  if (value == null) return <span className="chip crit">cần nhập</span>;
  if ((conf ?? 0) >= 0.9) return <span className="chip ok">chắc</span>;
  if ((conf ?? 0) >= 0.6) return <span className="chip warn">nên xem</span>;
  return <span className="chip crit">không chắc</span>;
}

const fmtAmount = (v: number | null) => (v == null ? "" : new Intl.NumberFormat("vi-VN").format(v));

// Ô ngày của trình duyệt hiển thị theo ngôn ngữ máy (máy tiếng Anh hiện 10/03/2026 cho ngày 3/10).
// Luôn in kèm ngày theo kiểu Việt Nam để tránh nhập nhầm ngày và tháng.
function DateHint({ iso }: { iso: string }) {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  const weekday = d.toLocaleDateString("vi-VN", { weekday: "long" });
  return <span className="date-hint">{weekday}, {day(iso)}</span>;
}

export function RecordForm({ record, onDone, autoFocus }: { record: LedgerRecord; onDone: () => void; autoFocus?: boolean }) {
  const f = record.fields;
  const settled = record.confirmed && !record.review_required;
  const mark = (conf: number | null | undefined, value: unknown) =>
    settled ? <span className="chip ok">đã xác nhận</span> : band(conf, value);
  const [type, setType] = useState<RecordFields["transaction_type"]>(f.transaction_type);
  const [amountText, setAmountText] = useState(fmtAmount(f.amount));
  const [posting, setPosting] = useState(f.posting_date ?? "");
  const [docDate, setDocDate] = useState(f.document_date ?? "");
  const [desc, setDesc] = useState(f.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const amountRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setType(f.transaction_type);
    setAmountText(fmtAmount(f.amount));
    setPosting(f.posting_date ?? "");
    setDocDate(f.document_date ?? "");
    setDesc(f.description ?? "");
    setError(null);
  }, [record.id, f.transaction_type, f.amount, f.posting_date, f.document_date, f.description]);

  useEffect(() => {
    if (autoFocus) amountRef.current?.focus();
  }, [autoFocus, record.id]);

  const amount = parseAmount(amountText);
  const conf = record.decision_confidence;
  const candidates = (k: string) => (record.fields_ai[k]?.candidates ?? []) as (string | number)[];

  const payload = () => {
    const out: Partial<RecordFields> = {};
    if (type !== f.transaction_type && type) out.transaction_type = type;
    if (amount !== f.amount && amount != null) out.amount = amount;
    if ((posting || null) !== f.posting_date && posting) out.posting_date = posting;
    if ((docDate || null) !== f.document_date) out.document_date = docDate || null;
    if ((desc || null) !== f.description) out.description = desc || null;
    return out;
  };

  const submit = async (confirm: boolean) => {
    if (amountText.trim() && amount == null) {
      setError("Không đọc được số tiền. Ví dụ hợp lệ: 2350000, 2.350.000, 2tr35, 950k");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api(`/records/${record.id}${confirm ? "/confirm" : ""}`, {
        method: confirm ? "POST" : "PATCH",
        json: { fields: payload() },
      });
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lỗi không xác định");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="stack"
      onSubmit={(e) => {
        e.preventDefault();
        submit(true);
      }}
    >
      {record.review_reasons.length > 0 && (
        <div className="row">
          {record.review_reasons.map((r) => (
            <span key={r} className="chip warn">
              {REASONS[r] ?? r}
            </span>
          ))}
        </div>
      )}
      <div className="stack" style={{ gap: 4 }}>
        <span className="row small muted">
          Loại {mark(conf.transaction_type, f.transaction_type)}
        </span>
        <div className="row" role="group" aria-label="Loại giao dịch">
          <button type="button" className={`btn ${type === "EXPENSE" ? "primary" : ""}`} aria-pressed={type === "EXPENSE"}
            onClick={() => setType("EXPENSE")}>
            Chi
          </button>
          <button type="button" className={`btn ${type === "INCOME" ? "primary" : ""}`} aria-pressed={type === "INCOME"}
            onClick={() => setType("INCOME")}>
            Thu
          </button>
        </div>
      </div>
      <label className="field">
        <span className="row">Số tiền {mark(conf.amount, f.amount)}</span>
        <input id={`amount-${record.id}`} ref={amountRef} type="text" inputMode="decimal" value={amountText}
          onChange={(e) => setAmountText(e.target.value)} placeholder="2350000 hoặc 2tr35" autoComplete="off" />
        <span className="small num">{amountText && (amount != null ? money(amount) : "Chưa đọc được")}</span>
      </label>
      {candidates("amount").length > 0 && (
        <div className="row small">
          Gợi ý:
          {candidates("amount").map((c) => (
            <button type="button" key={String(c)} className="btn small num" onClick={() => setAmountText(fmtAmount(Number(c)))}>
              {money(Number(c))}
            </button>
          ))}
        </div>
      )}
      <div className="row" style={{ alignItems: "start" }}>
        <label className="field" style={{ flex: 1, minWidth: 150 }}>
          <span className="row">Ngày hạch toán {mark(conf.posting_date, f.posting_date)}</span>
          <input id={`posting-${record.id}`} type="date" value={posting} onChange={(e) => setPosting(e.target.value)} />
          <DateHint iso={posting} />
        </label>
        <label className="field" style={{ flex: 1, minWidth: 150 }}>
          <span>Ngày trên chứng từ</span>
          <input id={`docdate-${record.id}`} type="date" value={docDate} onChange={(e) => setDocDate(e.target.value)} />
          <DateHint iso={docDate} />
        </label>
      </div>
      {candidates("posting_date").length > 0 && (
        <div className="row small">
          Ngày có thể là:
          {candidates("posting_date").map((c) => (
            <button type="button" key={String(c)} className="btn small" onClick={() => setPosting(String(c))}>
              {day(String(c))}
            </button>
          ))}
        </div>
      )}
      <label className="field">
        <span>Nội dung</span>
        <input id={`desc-${record.id}`} type="text" value={desc} onChange={(e) => setDesc(e.target.value)} />
      </label>
      {error && <div className="alert">{error}</div>}
      <div className="row">
        <button className="btn primary" type="submit" disabled={busy}>
          Xác nhận <kbd>Enter</kbd>
        </button>
        <button className="btn" type="button" disabled={busy} onClick={() => submit(false)}>
          Lưu, chưa xác nhận
        </button>
      </div>
    </form>
  );
}
