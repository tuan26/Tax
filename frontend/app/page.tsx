"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Shell } from "@/components/Shell";
import { api, ApiError } from "@/lib/api";
import type { Customer } from "@/lib/types";
import { useActivity } from "@/lib/useActivity";

export default function CustomersPage() {
  useActivity("customers");
  const [rows, setRows] = useState<Customer[] | null>(null);
  const [name, setName] = useState("");
  const [cutoff, setCutoff] = useState("04:00");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api<Customer[]>("/customers").then(setRows).catch(() => setRows([])), []);
  useEffect(() => {
    load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api("/customers", { method: "POST", json: { name, business_day_cutoff: cutoff } });
      setName("");
      setError(null);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được hộ");
    }
  };

  return (
    <Shell>
      <main className="page">
        <h1>Hộ kinh doanh</h1>
        <div className="card scroll-x">
          {rows === null ? (
            <span className="muted">Đang tải…</span>
          ) : rows.length === 0 ? (
            <span className="muted">Chưa có hộ nào. Thêm hộ đầu tiên ở bên dưới.</span>
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>Hộ</th>
                  <th className="right">Chờ duyệt</th>
                  <th className="right">Việc cần xử lý</th>
                  <th>Giờ chốt ngày</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => {
                  const pending = (c.pending_items ?? 0) + (c.pending_records ?? 0);
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link href={`/customers/${c.id}/ledger`}>
                          <strong>{c.name}</strong>
                        </Link>
                      </td>
                      <td className="right num">
                        {pending > 0 ? <span className="chip warn">{pending}</span> : <span className="chip ok">0</span>}
                      </td>
                      <td className="right num">
                        {(c.open_findings ?? 0) > 0 ? (
                          <Link href={`/customers/${c.id}/findings`} className="chip warn">{c.open_findings}</Link>
                        ) : (
                          <span className="chip ok">0</span>
                        )}
                      </td>
                      <td className="num">{c.business_day_cutoff}</td>
                      <td className="right">
                        <div className="row" style={{ justifyContent: "flex-end" }}>
                          <Link className="btn small" href={`/customers/${c.id}/import`}>
                            Nhập dữ liệu
                          </Link>
                          <Link className="btn small" href={`/customers/${c.id}/review`}>
                            Duyệt
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
        <form className="card row" onSubmit={create} style={{ alignItems: "end" }}>
          <label className="field" style={{ flex: 2, minWidth: 220 }}>
            <span>Tên hộ</span>
            <input id="new-name" type="text" value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="field" style={{ width: 140 }}>
            <span>Giờ chốt ngày</span>
            <input id="new-cutoff" type="text" value={cutoff} onChange={(e) => setCutoff(e.target.value)} pattern="[0-2][0-9]:[0-5][0-9]" />
          </label>
          <button className="btn primary">Thêm hộ</button>
          {error && <div className="alert" style={{ width: "100%" }}>{error}</div>}
        </form>
        <p className="muted small">
          Giờ chốt ngày: tin gửi trước giờ này được tính vào ngày kinh doanh hôm trước (quán mở khuya).
        </p>
      </main>
    </Shell>
  );
}
