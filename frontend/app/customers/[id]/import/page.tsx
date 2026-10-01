"use client";

import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import { Shell } from "@/components/Shell";
import { api, ApiError } from "@/lib/api";
import { day, todayIso } from "@/lib/format";
import { useActivity } from "@/lib/useActivity";

const ACCEPT = ["image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"];
type Picked = { file: File; url: string | null };

export default function ImportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  useActivity("import", id);
  const [businessDate, setBusinessDate] = useState(todayIso());
  const [source, setSource] = useState("ZALO_MANUAL");
  const [chat, setChat] = useState("");
  const [splitLines, setSplitLines] = useState(true);
  const [files, setFiles] = useState<Picked[]>([]);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ messages: number; processing: string } | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const add = (list: FileList | File[]) => {
    const picked: Picked[] = [];
    const rejected: string[] = [];
    for (const f of Array.from(list)) {
      if (!ACCEPT.includes(f.type)) rejected.push(f.name || "ảnh dán");
      else picked.push({ file: f, url: f.type.startsWith("image/") ? URL.createObjectURL(f) : null });
    }
    setFiles((cur) => [...cur, ...picked]);
    setError(rejected.length ? `Bỏ qua ${rejected.join(", ")}: chỉ nhận ảnh JPEG, PNG, WEBP, HEIC hoặc PDF` : null);
  };

  // Dán ảnh trực tiếp (copy ảnh từ Zalo PC rồi Ctrl+V).
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const imgs = Array.from(e.clipboardData?.files ?? []).filter((f) => f.type.startsWith("image/"));
      if (imgs.length) {
        e.preventDefault();
        add(imgs);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  useEffect(() => () => files.forEach((p) => p.url && URL.revokeObjectURL(p.url)), [files]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!files.length && !chat.trim()) {
      setError("Chọn ít nhất một ảnh hoặc dán nội dung chat");
      return;
    }
    const form = new FormData();
    form.set("business_date", businessDate);
    form.set("source_type", source);
    form.set("split_lines", String(splitLines));
    if (chat.trim()) form.set("chat_text", chat);
    files.forEach((p) => form.append("files", p.file, p.file.name || "anh-dan.png"));
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ messages: number; processing: string }>(`/customers/${id}/imports`, { method: "POST", body: form });
      setResult(r);
      setFiles([]);
      setChat("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không gửi được, dữ liệu chưa được lưu");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Shell customerId={id}>
      <main className="page">
        <h1>Nhập dữ liệu</h1>
        {result && (
          <div className="notice row">
            Đã lưu {result.messages} mục.
            {result.processing === "done" ? " Đã xử lý xong." : " Lưu xong nhưng xử lý bị lỗi, hệ thống sẽ thử lại."}
            <Link href={`/customers/${id}/review`} className="btn small">
              Sang hàng chờ duyệt
            </Link>
          </div>
        )}
        <form className="grid2" onSubmit={submit}>
          <div className="card stack">
            <h2>Ảnh và file</h2>
            <div
              className={`dropzone ${over ? "over" : ""}`}
              onClick={() => input.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setOver(false);
                add(e.dataTransfer.files);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
            >
              Kéo ảnh từ Zalo PC vào đây, bấm để chọn file, hoặc dán ảnh bằng <kbd>Ctrl</kbd>+<kbd>V</kbd>
            </div>
            <input ref={input} id="file-input" type="file" multiple accept={ACCEPT.join(",")} hidden
              onChange={(e) => e.target.files && add(e.target.files)} />
            {files.length > 0 && (
              <div className="thumbs">
                {files.map((p, i) => (
                  <div key={i} className="stack" style={{ gap: 2, width: 72 }}>
                    {p.url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={p.url} className="thumb" alt={p.file.name} />
                    ) : (
                      <div className="thumb" style={{ display: "grid", placeItems: "center" }}>PDF</div>
                    )}
                    <button type="button" className="btn small" onClick={() => setFiles((cur) => cur.filter((_, j) => j !== i))}>
                      Bỏ
                    </button>
                  </div>
                ))}
              </div>
            )}
            <span className="muted small">{files.length} file</span>
          </div>
          <div className="card stack">
            <h2>Nội dung chat</h2>
            <textarea id="chat-text" value={chat} onChange={(e) => setChat(e.target.value)}
              placeholder={"Dán tin nhắn của khách, ví dụ:\n2tr5\ntiền thịt\nDoanh thu hôm nay 12tr5"} />
            <label className="row small">
              <input type="checkbox" checked={splitLines} onChange={(e) => setSplitLines(e.target.checked)} />
              Mỗi dòng là một tin nhắn
            </label>
            <div className="row" style={{ alignItems: "start" }}>
              <label className="field" style={{ flex: 1, minWidth: 160 }}>
                <span>Ngày kinh doanh của đợt này</span>
                <input id="business-date" type="date" value={businessDate} onChange={(e) => setBusinessDate(e.target.value)} required />
                <span className="date-hint">{day(businessDate)}</span>
              </label>
              <label className="field" style={{ flex: 1, minWidth: 160 }}>
                <span>Nguồn</span>
                <select id="source" value={source} onChange={(e) => setSource(e.target.value)}>
                  <option value="ZALO_MANUAL">Lấy từ Zalo PC</option>
                  <option value="FILE_UPLOAD">File có sẵn</option>
                  <option value="MANUAL_ENTRY">Kế toán tự nhập</option>
                </select>
              </label>
            </div>
            <p className="muted small" style={{ margin: 0 }}>
              Nhập tay không ghi lại giờ gửi và người gửi. Hệ thống chỉ ghép ảnh với tin nhắn khi số tiền hoặc nội dung
              khớp; còn lại sẽ vào hàng chờ để anh/chị chọn.
            </p>
            {error && <div className="alert">{error}</div>}
            <button className="btn primary" disabled={busy}>
              {busy ? "Đang lưu…" : "Lưu đợt nhập"}
            </button>
          </div>
        </form>
      </main>
    </Shell>
  );
}
