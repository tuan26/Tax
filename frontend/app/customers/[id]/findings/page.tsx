"use client";

import { use, useCallback, useEffect, useState } from "react";
import { Thumbs } from "@/components/Evidence";
import { Shell } from "@/components/Shell";
import { api, ApiError } from "@/lib/api";
import { day, money } from "@/lib/format";
import type { Candidate, Finding, MatchCriterion } from "@/lib/types";
import { useActivity } from "@/lib/useActivity";

const STATUS: Record<Finding["status"], [string, string]> = {
  OPEN: ["Mới", "warn"],
  REQUESTED: ["Đã yêu cầu khách", ""],
  RESOLVED: ["Đã xử lý", "ok"],
  DISMISSED: ["Không cần", ""],
};
const RESOLUTION: Record<string, string> = {
  matched: "Đã ghép chứng từ",
  has_document: "Kế toán xác nhận đã có chứng từ",
  no_longer_applies: "Không còn áp dụng",
};

function Criteria({ items }: { items: MatchCriterion[] }) {
  return (
    <div className="stack" style={{ gap: 2 }}>
      {items.map((c) => (
        <span key={c.criterion} className="small">
          <strong style={{ color: c.ok ? "var(--accent)" : c.ok === false ? "var(--crit)" : "var(--muted)" }}>
            {c.ok ? "✓" : c.ok === false ? "✗" : "?"}
          </strong>{" "}
          {{ amount: "Số tiền", date: "Ngày", type: "Loại" }[c.criterion]}: {c.detail}
        </span>
      ))}
    </div>
  );
}

function FindingCard({ f, selected, onSelect, reload }: {
  f: Finding; selected: boolean; onSelect: (v: boolean) => void; reload: () => Promise<void>;
}) {
  const [mode, setMode] = useState<"" | "match" | "has" | "dismiss">("");
  const [cands, setCands] = useState<Candidate[] | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const open = f.status === "OPEN" || f.status === "REQUESTED";

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setMode("");
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Thao tác không thành công");
    } finally {
      setBusy(false);
    }
  };
  const showMatch = async () => {
    setMode("match");
    setCands(null);
    setCands(await api<Candidate[]>(`/findings/${f.id}/candidates`));
  };
  const [label, tone] = STATUS[f.status];

  return (
    <article className="card stack">
      <div className="row">
        {open && (
          <input type="checkbox" checked={selected} onChange={(e) => onSelect(e.target.checked)}
            aria-label="Chọn để đưa vào tin nhắn đòi chứng từ" />
        )}
        <span className={`chip ${tone}`}>{label}</span>
        <strong>{f.title}</strong>
        <span className="muted small">{f.rule_id}</span>
        <span className="spacer" />
        {f.requested_at && <span className="muted small">Đã yêu cầu {day(f.requested_at)}</span>}
      </div>
      <div>
        {f.detail}
        {open && f.rule_id === "DQ-01" && <span className="muted"> Chưa có chứng từ nào được ghép với khoản này.</span>}
      </div>
      {f.record && <Thumbs items={f.record.evidence} large />}
      {!open && (
        <div className="row small">
          <span>{f.status === "DISMISSED" ? "Không cần xử lý" : RESOLUTION[f.resolution ?? ""]}</span>
          {f.resolution_note && <span className="muted">· {f.resolution_note}</span>}
        </div>
      )}
      {f.match && f.status === "RESOLVED" && (
        <div className="row" style={{ alignItems: "start" }}>
          <Thumbs items={f.match.document.evidence} large />
          <div className="stack" style={{ gap: 6 }}>
            <span>
              Chứng từ {money(f.match.document.fields.amount)} · {day(f.match.document.fields.document_date)}
            </span>
            <Criteria items={f.match.evidence} />
          </div>
        </div>
      )}
      {error && <div className="alert">{error}</div>}
      <div className="row">
        {open && f.rule_id === "DQ-01" && (
          <button className="btn primary" disabled={busy} onClick={showMatch}>Ghép chứng từ</button>
        )}
        {open && <button className="btn" disabled={busy} onClick={() => setMode(mode === "has" ? "" : "has")}>Đã có chứng từ</button>}
        {open && <button className="btn" disabled={busy} onClick={() => setMode(mode === "dismiss" ? "" : "dismiss")}>Không cần</button>}
        {f.match && f.status === "RESOLVED" && (
          <button className="btn" disabled={busy} onClick={() => run(() => api(`/matches/${f.match!.id}/undo`, { method: "POST" }))}>
            Bỏ ghép
          </button>
        )}
        {!open && f.resolution !== "matched" && (
          <button className="btn" disabled={busy} onClick={() => run(() => api(`/findings/${f.id}/reopen`, { method: "POST" }))}>
            Mở lại
          </button>
        )}
      </div>
      {(mode === "has" || mode === "dismiss") && (
        <div className="row">
          <input type="text" id={`note-${f.id}`} value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1 }}
            placeholder={mode === "dismiss" ? "Lý do không cần xử lý (bắt buộc)" : "Ghi chú, ví dụ: hóa đơn lưu ở bản giấy"} />
          <button className="btn primary" disabled={busy || (mode === "dismiss" && !note.trim())}
            onClick={() => run(() => api(`/findings/${f.id}/decision`, { method: "POST",
              json: { action: mode === "has" ? "has_document" : "not_needed", note: note || null } }))}>
            Lưu
          </button>
        </div>
      )}
      {mode === "match" && (
        <div className="stack">
          {cands === null ? (
            <span className="muted">Đang tìm chứng từ phù hợp…</span>
          ) : cands.length === 0 ? (
            <span className="muted">Chưa có chứng từ nào phù hợp. Chọn khoản này để yêu cầu khách bổ sung.</span>
          ) : (
            cands.map((c) => (
              <div key={c.record_id} className="choice" style={{ gridTemplateColumns: "1fr auto", cursor: "default" }}>
                <div className="row" style={{ alignItems: "start" }}>
                  <Thumbs items={c.evidence_detail} large />
                  <div className="stack" style={{ gap: 4 }}>
                    <strong className="num">{money(c.fields.amount)}</strong>
                    <span className="small">{c.fields.description ?? ""}</span>
                    <Criteria items={c.evidence} />
                  </div>
                </div>
                <button className="btn primary" disabled={busy}
                  onClick={() => run(() => api(`/findings/${f.id}/match`, { method: "POST", json: { document_record_id: c.record_id } }))}>
                  Xác nhận ghép
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </article>
  );
}

export default function FindingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  useActivity("findings", id);
  const [rows, setRows] = useState<Finding[] | null>(null);
  const [view, setView] = useState<"open" | "done">("open");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [text, setText] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => setRows(await api<Finding[]>(`/customers/${id}/findings`)), [id]);
  useEffect(() => {
    load();
  }, [load]);

  const openRows = (rows ?? []).filter((f) => f.status === "OPEN" || f.status === "REQUESTED");
  const doneRows = (rows ?? []).filter((f) => f.status === "RESOLVED" || f.status === "DISMISSED");
  const shown = view === "open" ? openRows : doneRows;

  const makeText = async () => {
    setError(null);
    try {
      const r = await api<{ text: string }>(`/customers/${id}/request-text`, {
        method: "POST", json: { finding_ids: [...selected] } });
      setText(r.text);
      setCopied(false);
      setSelected(new Set());
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Không tạo được tin nhắn");
    }
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text ?? "");
      setCopied(true);
    } catch {
      (document.getElementById("request-text") as HTMLTextAreaElement | null)?.select();
    }
  };

  return (
    <Shell customerId={id}>
      <main className="page">
        <div className="row">
          <h1>Việc cần xử lý</h1>
          <div className="tabs">
            <button className={`tab btn small ${view === "open" ? "active" : ""}`} onClick={() => setView("open")}>
              Đang mở ({openRows.length})
            </button>
            <button className={`tab btn small ${view === "done" ? "active" : ""}`} onClick={() => setView("done")}>
              Đã xử lý ({doneRows.length})
            </button>
          </div>
          <span className="spacer" />
          {view === "open" && (
            <button className="btn primary" disabled={selected.size === 0} onClick={makeText}>
              Tạo tin nhắn đòi chứng từ ({selected.size})
            </button>
          )}
        </div>
        {error && <div className="alert">{error}</div>}
        {text && (
          <div className="card stack">
            <div className="row">
              <strong>Tin nhắn gửi khách qua Zalo</strong>
              <span className="spacer" />
              <button className="btn primary" onClick={copy}>{copied ? "Đã copy" : "Copy"}</button>
              <button className="btn" onClick={() => setText(null)}>Đóng</button>
            </div>
            <textarea id="request-text" readOnly value={text} style={{ minHeight: 120 }} />
          </div>
        )}
        {rows === null ? (
          <span className="muted">Đang tải…</span>
        ) : shown.length === 0 ? (
          <div className="card muted">
            {view === "open" ? "Không có việc nào đang mở." : "Chưa có việc nào được xử lý."}
          </div>
        ) : (
          shown.map((f) => (
            <FindingCard key={f.id} f={f} reload={load} selected={selected.has(f.id)}
              onSelect={(v) => setSelected((cur) => {
                const next = new Set(cur);
                if (v) next.add(f.id);
                else next.delete(f.id);
                return next;
              })} />
          ))
        )}
        <p className="muted small">
          Hệ thống chỉ tạo việc từ giao dịch đã xác nhận hoặc đủ chắc chắn. Việc chỉ đóng khi anh/chị ghép chứng từ,
          xác nhận đã có chứng từ, hoặc ghi lý do không cần.
        </p>
      </main>
    </Shell>
  );
}
