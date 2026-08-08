"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { OwnerOnly } from "@/components/AuthGate";
import { apiFetch } from "@/lib/api";

type FunctionsSettings = {
  hh_search_enabled?: boolean;
};

type AppSettings = {
  functions?: FunctionsSettings;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = data as { detail?: unknown };
    if (typeof d.detail === "string") return d.detail;
  }
  return fallback;
}

export default function FunctionsSettingsPage() {
  const [data, setData] = useState<AppSettings | null>(null);
  const [hhSearchEnabled, setHhSearchEnabled] = useState(true);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/settings/app`, { cache: "no-store" });
        const d = (await res.json()) as AppSettings;
        if (cancelled) return;
        setData(d);
        setHhSearchEnabled(d.functions?.hh_search_enabled !== false);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(nextEnabled: boolean) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/settings/app`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          functions: {
            hh_search_enabled: nextEnabled,
          },
        }),
      });
      const next = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(next, `HTTP ${res.status}`));
      setData(next as AppSettings);
      setHhSearchEnabled(next.functions?.hh_search_enabled !== false);
      setMsg("Сохранено");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <OwnerOnly>
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Функции</h1>
      <p className="muted">Включайте/выключайте модули. Начнём с отключения поиска резюме HH.</p>

      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      {!data ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <section className="card-edit">
          <h2>Поиск резюме HH</h2>
          <p className="muted hh-micro">
            При отключении скрывается таб “Поиск HH” и блокируется создание jobs типа `hh_cold_search`.
          </p>

          <label className="hh-field" style={{ marginTop: "0.75rem" }}>
            <span className="hh-label">Включен</span>
            <input
              type="checkbox"
              checked={hhSearchEnabled}
              disabled={busy}
              onChange={(e) => void save(e.target.checked)}
            />
          </label>
        </section>
      )}
    </AppShell>
    </OwnerOnly>
  );
}

