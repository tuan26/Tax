"use client";

import { useEffect, useState } from "react";
import { fetchBlobUrl } from "@/lib/api";

// Ảnh cần token nên không dùng <img src> trực tiếp: tải blob rồi hiển thị. Bấm để phóng to.
export function AuthImage({ attachmentId, className, alt }: { attachmentId: string; className?: string; alt?: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState(false);
  useEffect(() => {
    let revoked: string | null = null;
    let alive = true;
    fetchBlobUrl(`/attachments/${attachmentId}/content`)
      .then((u) => (alive ? setUrl((revoked = u)) : URL.revokeObjectURL(u)))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [attachmentId]);
  if (failed) return <div className="muted small">Không tải được ảnh</div>;
  if (!url) return <div className={className} aria-busy="true" />;
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} className={className} alt={alt ?? "Chứng từ"} onClick={() => setZoom(true)} />
      {zoom && (
        <div className="overlay" onClick={() => setZoom(false)} role="dialog" aria-label="Ảnh phóng to">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt={alt ?? "Chứng từ"} />
        </div>
      )}
    </>
  );
}

export function PdfLink({ attachmentId, name }: { attachmentId: string; name?: string | null }) {
  const open = async () => window.open(await fetchBlobUrl(`/attachments/${attachmentId}/content`), "_blank");
  return (
    <button className="btn small" onClick={open}>
      Mở PDF {name ?? ""}
    </button>
  );
}
