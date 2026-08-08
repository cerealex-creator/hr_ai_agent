"use client";

import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BrandLogo } from "@/components/BrandLogo";
import { authLogin } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await authLogin(email.trim(), password);
      const next = params.get("next") || "/";
      router.replace(next.startsWith("/") ? next : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <p className="login-kicker">
          <BrandLogo size={72} />
          HR-помогатор
        </p>
        <h1 className="login-title">Вход</h1>
        <p className="muted login-lead">Доступ только для приглашённых пользователей.</p>
        <p className="muted hh-micro" style={{ marginTop: "-0.35rem" }}>
          Нет аккаунта? Обратитесь к администратору.
        </p>
        <label className="login-label">
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="login-label">
          Пароль
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button type="submit" className="chip chip-active login-submit" disabled={busy}>
          {busy ? "Вход…" : "Войти"}
        </button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="auth-boot"><p className="muted">Загрузка…</p></div>}>
      <LoginForm />
    </Suspense>
  );
}
