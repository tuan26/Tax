"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getToken, setToken } from "@/lib/api";
import type { Customer } from "@/lib/types";

export function Shell({ customerId, children }: { customerId?: string; children: React.ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else setReady(true);
  }, [router]);

  useEffect(() => {
    if (customerId && ready) api<Customer>(`/customers/${customerId}`).then(setCustomer).catch(() => setCustomer(null));
  }, [customerId, ready, path]);

  const logout = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    setToken(null);
    router.replace("/login");
  };

  if (!ready) return null;
  const tab = (href: string, label: string) => (
    <Link href={href} className={`tab ${path === href ? "active" : ""}`}>
      {label}
    </Link>
  );
  return (
    <>
      <header className="topbar">
        <Link href="/" className="brand">
          Hồ sơ thuế
        </Link>
        {customerId && (
          <>
            <span className="muted">/</span>
            <strong>{customer?.name ?? "…"}</strong>
            <nav className="tabs" aria-label="Màn hình của hộ">
              {tab(`/customers/${customerId}/import`, "Nhập dữ liệu")}
              {tab(`/customers/${customerId}/ledger`, "Sổ theo ngày")}
              {tab(`/customers/${customerId}/review`, "Hàng chờ duyệt")}
            </nav>
          </>
        )}
        <span className="spacer" />
        <button className="btn small" onClick={logout}>
          Đăng xuất
        </button>
      </header>
      {children}
    </>
  );
}
