"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";

type CalendarStatus = {
  status: string;
  message: string;
  credentials_path: string;
  token_path: string;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export default function CalendarSettingsPage() {
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [oauthUrl, setOauthUrl] = useState<string | null>(null);
  const [oauthCode, setOauthCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    const cal = await fetch(`${getApiBase()}/api/v1/integrations/google-calendar/status`).then(
      (r) => r.json(),
    );
    setCalendar(cal);
  };

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Google Calendar</h1>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <section className="card-edit">
        {calendar ? (
          <p className="muted">
            {calendar.status}: {calendar.message}
            <br />
            <span className="hh-micro">
              credentials: {calendar.credentials_path}
              <br />
              token: {calendar.token_path}
            </span>
          </p>
        ) : (
          <p className="muted">Загрузка…</p>
        )}
        <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const res = await fetch(
                  `${getApiBase()}/api/v1/integrations/google-calendar/oauth/start`,
                  { method: "POST" },
                );
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setOauthUrl(data.auth_url || null);
                setMsg(data.message || "Откройте ссылку");
              })
            }
          >
            Получить ссылку OAuth
          </button>
        </div>
        {oauthUrl ? (
          <p className="muted hh-micro" style={{ wordBreak: "break-all" }}>
            <a href={oauthUrl} target="_blank" rel="noreferrer">
              {oauthUrl}
            </a>
          </p>
        ) : null}
        <p className="muted hh-micro">
          Если ссылка «не открывается» — скопируйте её целиком в новую вкладку. После Google
          скопируйте весь адрес из строки браузера (
          <code>http://localhost:8765/?code=...</code>) или только значение после{" "}
          <code>code=</code>. Код одноразовый.
        </p>
        <div className="hh-field">
          <label className="hh-label">Вставьте redirect URL или code=</label>
          <textarea
            rows={2}
            value={oauthCode}
            onChange={(e) => setOauthCode(e.target.value)}
            disabled={busy}
          />
          <button
            type="button"
            className="chip"
            disabled={busy || !oauthCode.trim()}
            style={{ marginTop: "0.35rem" }}
            onClick={() =>
              run(async () => {
                const res = await fetch(
                  `${getApiBase()}/api/v1/integrations/google-calendar/oauth/complete`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code: oauthCode.trim() }),
                  },
                );
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setMsg(data.message || "OK");
                setOauthCode("");
                await load();
              })
            }
          >
            Завершить OAuth
          </button>
        </div>
      </section>
    </AppShell>
  );
}
