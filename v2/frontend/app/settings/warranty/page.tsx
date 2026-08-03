"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";

type AppSettings = {
  default_warranty_months: number;
  path: string;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export default function WarrantySettingsPage() {
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${getApiBase()}/api/v1/settings/app`)
      .then((r) => r.json())
      .then(setAppSettings)
      .catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
  }, []);

  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Гарантия</h1>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <section className="card-edit">
        <p className="muted hh-micro">Срок гарантии по умолчанию для новых вакансий.</p>
        {appSettings ? (
          <div className="hh-field">
            <label className="hh-label">Срок (месяцев)</label>
            <select
              value={appSettings.default_warranty_months}
              disabled={busy}
              onChange={async (e) => {
                setBusy(true);
                setErr(null);
                setMsg(null);
                try {
                  const res = await fetch(`${getApiBase()}/api/v1/settings/app`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      default_warranty_months: Number(e.target.value),
                    }),
                  });
                  const data = await res.json().catch(() => ({}));
                  if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                  setAppSettings(data);
                  setMsg("Сохранено");
                } catch (ex) {
                  setErr(ex instanceof Error ? ex.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
            >
              {[1, 2, 3, 4, 5, 6].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <p className="muted hh-micro">Файл: {appSettings.path}</p>
          </div>
        ) : (
          <p className="muted">Загрузка…</p>
        )}
      </section>
    </AppShell>
  );
}
