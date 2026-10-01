"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import { EvidenceList, Thumbs } from "@/components/Evidence";
import { RecordForm } from "@/components/RecordForm";
import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { day, KIND, money, todayIso } from "@/lib/format";
import type { LedgerRecord } from "@/lib/types";
import { useActivity } from "@/lib/useActivity";

const monthBounds = (ym: string) => {
  const [y, m] = ym.split("-").map(Number);
  const last = new Date(y, m, 0).getDate();
  return [`${ym}-01`, `${ym}-${String(last).padStart(2, "0")}`];
};

function Status({ r }: { r: LedgerRecord }) {
  if (r.confirmed && !r.review_required) return <span className="chip ok">Đã xác nhận</span>;
  if (r.review_required) return <span className="chip warn">Chờ duyệt</span>;
  return <span className="chip">Tự động</span>;
}

export default function LedgerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  useActivity("ledger", id);
  const [month, setMonth] = useState(todayIso().slice(0, 7));
  const [rows, setRows] = useState<LedgerRecord[] | null>(null);
  const [open, setOpen] = useState<LedgerRecord | null>(null);

  const load = useCallback(() => {
    const [from, to] = monthBounds(month);
    return api<LedgerRecord[]>(`/customers/${id}/records?date_from=${from}&date_to=${to}`).then((r) => {
      setRows(r);
      setOpen((cur) => (cur ? r.find((x) => x.id === cur.id) ?? null : null));
    });
  }, [id, month]);
  useEffect(() => {
    load();
  }, [load]);

  const days = useMemo(() => {
    const map = new Map<string, LedgerRecord[]>();
    for (const r of rows ?? []) {
      const k = r.fields.posting_date ?? "";
      map.set(k, [...(map.get(k) ?? []), r]);
    }
    return [...map.entries()].sort(([a], [b]) => (a === "" ? -1 : b === "" ? 1 : b.localeCompare(a)));
  }, [rows]);

  // Khoản chuyển khoản đã ghép với hóa đơn chỉ tính một lần (tính hóa đơn).
  const total = (list: LedgerRecord[], t: "INCOME" | "EXPENSE") =>
    list.filter((r) => r.counted !== false && r.fields.transaction_type === t && r.fields.amount != null)
      .reduce((s, r) => s + (r.fields.amount ?? 0), 0);
  const all = rows ?? [];

  return (
    <Shell customerId={id}>
      <main className="page">
        <div className="row">
          <h1>Sổ theo ngày</h1>
          <span className="spacer" />
          <input id="month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} style={{ width: 170 }} />
        </div>
        <div className="card row" style={{ gap: 28 }}>
          <div>
            <div className="muted small">Thu trong tháng</div>
            <strong className="num income">{money(total(all, "INCOME"))}</strong>
          </div>
          <div>
            <div className="muted small">Chi trong tháng</div>
            <strong className="num expense">{money(total(all, "EXPENSE"))}</strong>
          </div>
          <div>
            <div className="muted small">Giao dịch</div>
            <strong className="num">{all.length}</strong>
          </div>
          <div>
            <div className="muted small">Chờ duyệt</div>
            <strong className="num">{all.filter((r) => r.review_required).length}</strong>
          </div>
          <span className="muted small">Tổng có tính cả giao dịch chưa xác nhận.</span>
        </div>
        {rows === null ? (
          <span className="muted">Đang tải…</span>
        ) : days.length === 0 ? (
          <div className="card muted">Tháng này chưa có giao dịch nào. Nhập dữ liệu ở tab Nhập dữ liệu.</div>
        ) : (
          days.map(([d, list]) => (
            <section key={d || "none"} className="card scroll-x stack">
              <div className="row">
                <h2>{d ? day(d) : "Chưa rõ ngày"}</h2>
                <span className="spacer" />
                <span className="small num">
                  Thu <span className="income">{money(total(list, "INCOME"))}</span> · Chi{" "}
                  <span className="expense">{money(total(list, "EXPENSE"))}</span> · {list.length} giao dịch
                </span>
              </div>
              <table className="data">
                <tbody>
                  {list.map((r) => (
                    <tr key={r.id} className="clickable" onClick={() => setOpen(r)}>
                      <td style={{ width: 60 }}>
                        {r.fields.transaction_type === "INCOME" ? (
                          <span className="chip ok">Thu</span>
                        ) : r.fields.transaction_type === "EXPENSE" ? (
                          <span className="chip">Chi</span>
                        ) : (
                          <span className="chip crit">?</span>
                        )}
                      </td>
                      <td className="num right" style={{ width: 120 }}>
                        {money(r.fields.amount)}
                      </td>
                      <td>
                        <div>{r.fields.description ?? <span className="muted">Không có nội dung</span>}</div>
                        <span className="muted small">
                          {KIND[r.evidence_kind]}
                          {r.counted === false && " · đã ghép với chứng từ, không cộng lại"}
                        </span>
                      </td>
                      <td className="hide-sm" style={{ width: 260 }}>
                        <Thumbs items={r.evidence} />
                      </td>
                      <td style={{ width: 110 }}>
                        <Status r={r} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))
        )}
        {open && (
          <aside className="drawer" aria-label="Chi tiết giao dịch">
            <div className="row">
              <h2>Giao dịch</h2>
              <Status r={open} />
              <span className="spacer" />
              <button className="btn small" onClick={() => setOpen(null)}>
                Đóng
              </button>
            </div>
            <EvidenceList items={open.evidence ?? []} large />
            <RecordForm record={open} onDone={load} />
          </aside>
        )}
      </main>
    </Shell>
  );
}
