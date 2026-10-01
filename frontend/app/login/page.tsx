"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ token: string }>("/auth/login", { method: "POST", json: { email, password } });
      setToken(r.token);
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không kết nối được máy chủ");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page" style={{ maxWidth: 380, marginTop: "12vh" }}>
      <h1>Hồ sơ thuế</h1>
      <form className="card stack" onSubmit={submit}>
        <label className="field">
          <span>Email</span>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
        </label>
        <label className="field">
          <span>Mật khẩu</span>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <div className="alert">{error}</div>}
        <button className="btn primary" disabled={busy}>
          Đăng nhập
        </button>
      </form>
    </main>
  );
}
