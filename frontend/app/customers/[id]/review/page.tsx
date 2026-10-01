"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AuthImage } from "@/components/AuthImage";
import { EvidenceList, Thumbs } from "@/components/Evidence";
import { RecordForm } from "@/components/RecordForm";
import { Shell } from "@/components/Shell";
import { parseAmount } from "@/lib/amount.mjs";
import { api, ApiError } from "@/lib/api";
import { day, money, ROLES, time, UNMATCHED } from "@/lib/format";
import type { LedgerRecord, Queue, QueueGroup, QueueItem } from "@/lib/types";
import { useActivity } from "@/lib/useActivity";

type Task =
  | { kind: "item"; key: string; item: QueueItem }
  | { kind: "group"; key: string; group: QueueGroup }
  | { kind: "record"; key: string; record: LedgerRecord };

type Choice = { key: string; label: React.ReactNode; run: () => Promise<unknown> };

const isTyping = (el: EventTarget | null) =>
  el instanceof HTMLElement && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT");

function RecordSummary({ r, typed }: { r: LedgerRecord | null; typed: number | null }) {
  if (!r) return <span className="muted">Giao dịch không còn</span>;
  const ocr = r.fields.amount ?? (r.fields_ai.amount?.candidates as number[] | undefined)?.[0] ?? null;
  return (
    <div className="stack" style={{ gap: 4 }}>
      <div className="row">
        {typed != null && ocr === typed && <span className="chip ok">✓ khớp số tiền</span>}
        <strong className="num">{money(r.fields.amount)}</strong>
        <span className="muted small">{day(r.fields.posting_date)}</span>
        {r.fields.description && <span className="small">{r.fields.description}</span>}
      </div>
      <Thumbs items={r.evidence} large />
    </div>
  );
}

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  useActivity("review", id);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [records, setRecords] = useState<LedgerRecord[]>([]);
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [assignTo, setAssignTo] = useState("");
  const initial = useRef<number | null>(null);

  const load = useCallback(async () => {
    const [q, recs] = await Promise.all([api<Queue>(`/customers/${id}/review-queue`), api<LedgerRecord[]>(`/customers/${id}/records`)]);
    setQueue(q);
    setRecords(recs);
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);

  const tasks: Task[] = useMemo(() => {
    if (!queue) return [];
    const groupIds = new Set(queue.groups.map((g) => g.group_id));
    return [
      ...queue.items.map((item) => ({ kind: "item" as const, key: `i-${item.decision_id}`, item })),
      ...queue.groups.map((group) => ({ kind: "group" as const, key: `g-${group.group_id}`, group })),
      ...queue.records.filter((r) => !groupIds.has(r.group_id)).map((record) => ({ kind: "record" as const, key: `r-${record.id}`, record })),
    ];
  }, [queue]);
  if (queue && initial.current === null) initial.current = tasks.length;
  const current = tasks[Math.min(index, Math.max(0, tasks.length - 1))];

  const act = useCallback(
    async (fn: () => Promise<unknown>) => {
      setBusy(true);
      setError(null);
      try {
        await fn();
        await load();
        setAssignTo("");
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Thao tác không thành công");
      } finally {
        setBusy(false);
      }
    },
    [load],
  );

  const choices: Choice[] = useMemo(() => {
    if (!current) return [];
    if (current.kind === "item") {
      const it = current.item;
      if (it.type === "ambiguous_link") {
        return it.candidates.map((c) => ({
          key: c.choice,
          label:
            c.choice === "NONE" ? (
              <span>{it.attachment_id ? "Là giao dịch riêng" : "Không thuộc giao dịch nào"}</span>
            ) : (
              <div className="stack" style={{ gap: 6 }}>
                {c.records.length > 1 && <span className="small muted">Áp cho cả {c.records.length} giao dịch</span>}
                {c.records.map((r, i) => (
                  <RecordSummary key={i} r={r} typed={it.role === "amount_annotation" ? parseAmount(it.text) : null} />
                ))}
              </div>
            ),
          run: () => api(`/decisions/${it.decision_id}/resolve`, { method: "POST", json: { choice: c.choice } }),
        }));
      }
      return [
        { key: "dismiss", label: "Bỏ qua, không phải thông tin giao dịch",
          run: () => api(`/decisions/${it.decision_id}/dismiss`, { method: "POST" }) },
        { key: "new", label: "Tạo giao dịch riêng từ mục này",
          run: () => api(`/customers/${id}/assign`, { method: "POST", json: { item_ref: it.item_ref, group_id: null } }) },
      ];
    }
    if (current.kind === "group") {
      const g = current.group;
      const anchors = (g.partition_candidates?.[0]?.[0] ?? []) as string[];
      return [
        { key: "one", label: `Là một giao dịch (${anchors.length} ảnh là các trang của cùng một chứng từ)`,
          run: () => api(`/groups/${g.group_id}/accept`, { method: "POST" }) },
        { key: "many", label: `Là ${anchors.length} giao dịch riêng`,
          run: async () => {
            for (const ref of anchors.slice(1))
              await api(`/groups/${g.group_id}/split`, { method: "POST", json: { item_refs: [ref] } });
          } },
      ];
    }
    return [];
  }, [current, id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target) || busy || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "j" || e.key === "ArrowRight") setIndex((i) => Math.min(i + 1, tasks.length - 1));
      else if (e.key === "k" || e.key === "ArrowLeft") setIndex((i) => Math.max(i - 1, 0));
      else if (/^[1-9]$/.test(e.key) && choices[Number(e.key) - 1]) act(choices[Number(e.key) - 1].run);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tasks.length, choices, act, busy]);

  const done = (initial.current ?? 0) - tasks.length;
  return (
    <Shell customerId={id}>
      <main className="page">
        <div className="row">
          <h1>Hàng chờ duyệt</h1>
          <span className="muted">{queue ? `Còn ${tasks.length} mục` : "Đang tải…"}</span>
          <span className="spacer" />
          <span className="small muted">
            <kbd>J</kbd>/<kbd>K</kbd> chuyển mục · <kbd>1</kbd>–<kbd>9</kbd> chọn · <kbd>Enter</kbd> xác nhận
          </span>
        </div>
        {initial.current ? (
          <div className="progress" aria-label={`Đã xử lý ${done} mục`}>
            <div style={{ width: `${Math.max(0, (done / initial.current) * 100)}%` }} />
          </div>
        ) : null}
        {error && <div className="alert">{error}</div>}
        {queue && !current && (
          <div className="card stack">
            <strong>Không còn mục nào chờ duyệt.</strong>
            <Link href={`/customers/${id}/ledger`}>Xem sổ theo ngày</Link>
          </div>
        )}
        {current && (
          <div className="grid2" key={current.key} aria-busy={busy}>
            <section className="card stack">
              <div className="row small muted">
                Mục {Math.min(index, tasks.length - 1) + 1}/{tasks.length}
                <span className="spacer" />
                <button className="btn small" disabled={index <= 0} onClick={() => setIndex((i) => i - 1)}>
                  Trước
                </button>
                <button className="btn small" disabled={index >= tasks.length - 1} onClick={() => setIndex((i) => i + 1)}>
                  Sau
                </button>
              </div>
              {current.kind === "item" && (
                <>
                  <div className="row">
                    <span className="chip warn">
                      {current.item.type === "ambiguous_link"
                        ? `${ROLES[current.item.role ?? ""] ?? "Tin nhắn"} chưa rõ thuộc giao dịch nào`
                        : UNMATCHED[current.item.reason ?? ""] ?? "Chưa xếp được"}
                    </span>
                    <span className="muted small">
                      {time(current.item.sent_at) ?? `Nhập tay, ngày ${day(current.item.business_date)}`}
                    </span>
                  </div>
                  {current.item.attachment_id ? (
                    <AuthImage attachmentId={current.item.attachment_id} className="evidence-img" />
                  ) : (
                    <div className="bubble" style={{ fontSize: 16 }}>{current.item.text}</div>
                  )}
                </>
              )}
              {current.kind === "group" && (
                <>
                  <span className="chip warn">Không rõ là một hay nhiều giao dịch</span>
                  <EvidenceList items={current.group.record?.evidence ?? []} large />
                </>
              )}
              {current.kind === "record" && <EvidenceList items={current.record.evidence ?? []} large />}
            </section>
            <section className="card stack">
              {current.kind === "record" ? (
                <>
                  <h2>Kiểm tra giao dịch</h2>
                  <RecordForm record={current.record} onDone={load} autoFocus />
                </>
              ) : (
                <>
                  <h2>{current.kind === "group" ? "Đây là" : "Thuộc về"}</h2>
                  <div className="choices">
                    {choices.map((c, i) => (
                      <button key={c.key} className="choice" disabled={busy} onClick={() => act(c.run)}>
                        <span className="key">{i + 1}</span>
                        <span>{c.label}</span>
                      </button>
                    ))}
                  </div>
                  {current.kind === "item" && (
                    <div className="stack" style={{ gap: 6 }}>
                      <label className="field">
                        <span>Hoặc gán vào giao dịch khác</span>
                        <select id="assign-to" value={assignTo} onChange={(e) => setAssignTo(e.target.value)}>
                          <option value="">Chọn giao dịch…</option>
                          {records.map((r) => (
                            <option key={r.id} value={r.group_id}>
                              {day(r.fields.posting_date)} · {money(r.fields.amount)} · {r.fields.description ?? "không nội dung"}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button className="btn" disabled={!assignTo || busy}
                        onClick={() => act(() => api(`/customers/${id}/assign`, {
                          method: "POST", json: { item_ref: current.item.item_ref, group_id: assignTo } }))}>
                        Gán
                      </button>
                    </div>
                  )}
                  {current.kind === "group" && current.group.record && (
                    <p className="muted small" style={{ margin: 0 }}>
                      Sau khi chọn, giao dịch sẽ xuất hiện trong hàng chờ để nhập số tiền nếu còn thiếu.
                    </p>
                  )}
                </>
              )}
            </section>
          </div>
        )}
      </main>
    </Shell>
  );
}
