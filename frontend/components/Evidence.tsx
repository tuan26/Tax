"use client";

import type { Evidence } from "@/lib/types";
import { day, time } from "@/lib/format";
import { AuthImage, PdfLink } from "./AuthImage";

const when = (e: Evidence) => time(e.sent_at) ?? (e.business_date ? `Nhập tay, ngày ${day(e.business_date)}` : "");

export function EvidenceList({ items, large }: { items: Evidence[]; large?: boolean }) {
  if (!items.length) return <div className="muted">Không có bằng chứng</div>;
  return (
    <div className="stack">
      {items.map((e) => (
        <div key={e.ref} className="stack" style={{ gap: 4 }}>
          <span className="muted small">{when(e)}</span>
          {e.kind === "attachment" && e.attachment_id ? (
            e.mime_type === "application/pdf" ? (
              <PdfLink attachmentId={e.attachment_id} name={e.file_name} />
            ) : (
              <AuthImage attachmentId={e.attachment_id} className={large ? "evidence-img" : "thumb"} />
            )
          ) : (
            <div className="bubble">{e.text}</div>
          )}
        </div>
      ))}
    </div>
  );
}

export function Thumbs({ items, large }: { items: Evidence[] | null; large?: boolean }) {
  const imgs = (items ?? []).filter((e) => e.kind === "attachment" && e.attachment_id && e.mime_type !== "application/pdf");
  const texts = (items ?? []).filter((e) => e.kind === "text");
  return (
    <div className="row" style={{ gap: 6 }}>
      {imgs.slice(0, 3).map((e) => (
        <AuthImage key={e.ref} attachmentId={e.attachment_id!} className={large ? "thumb-lg" : "thumb"} />
      ))}
      {texts.slice(0, 2).map((e) => (
        <span key={e.ref} className="bubble small">
          {e.text}
        </span>
      ))}
    </div>
  );
}
