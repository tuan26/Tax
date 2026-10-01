"use client";

import { useEffect } from "react";
import { api } from "./api";

// Nhịp hoạt động để đo số phút kế toán làm việc trên từng hộ. Chỉ gửi khi tab đang mở
// và người dùng có thao tác trong 60 giây gần nhất.
export function useActivity(screen: string, customerId?: string) {
  useEffect(() => {
    let last = Date.now();
    const bump = () => (last = Date.now());
    const events = ["keydown", "mousedown", "scroll", "touchstart"];
    events.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    const send = () => {
      if (document.visibilityState === "visible" && Date.now() - last < 60_000)
        api("/activity", { method: "POST", json: { screen, customer_id: customerId ?? null } }).catch(() => {});
    };
    send();
    const id = setInterval(send, 30_000);
    return () => {
      clearInterval(id);
      events.forEach((e) => window.removeEventListener(e, bump));
    };
  }, [screen, customerId]);
}
