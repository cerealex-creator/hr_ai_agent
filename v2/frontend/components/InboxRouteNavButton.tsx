"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

/** Top-nav action: route resumes from Yandex Disk _inbox into vacancies. */
export function InboxRouteNavButton() {
  const [enabled, setEnabled] = useState(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/settings/app`, { cache: "no-store" });
        const data = await res.json().catch(() => ({}));
        if (cancelled) return;
        setEnabled(Boolean(data?.candidate_intake_effective?.disk_inbox));
      } catch {
        if (!cancelled) setEnabled(false);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const run = async () => {
    if (busy) return;
    setBusy(true);
    setHint(null);
    try {
      const res = await apiFetch(`/api/v1/integrations/yandex-disk/inbox/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: 20 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      const scanned = Number(data.scanned || 0);
      const routed = Number(data.routed || 0);
      const unsorted = Number(data.unsorted || 0);
      const errors = Number(data.errors || 0);
      const skipped = Number(data.skipped || 0);
      if (scanned === 0 && skipped === 0) {
        setHint("Inbox пуст — новых файлов нет");
      } else {
        setHint(
          `Inbox: разобрано ${scanned}, в вакансии ${routed}, unsorted ${unsorted}, ошибок ${errors}` +
            (skipped ? `, пропущено ${skipped}` : ""),
        );
      }
      window.setTimeout(() => setHint(null), 8000);
    } catch (e) {
      setHint(e instanceof Error ? e.message : "Ошибка роутинга inbox");
      window.setTimeout(() => setHint(null), 10000);
    } finally {
      setBusy(false);
    }
  };

  if (!ready || !enabled) return null;

  return (
    <span className="nav-inbox-wrap">
      <button
        type="button"
        className="nav-link nav-inbox-btn"
        disabled={busy}
        title="Разобрать резюме из папки inbox на Яндекс Диске"
        onClick={() => void run()}
      >
        {busy ? "Inbox…" : "Inbox"}
      </button>
      {hint ? <span className="nav-inbox-hint">{hint}</span> : null}
    </span>
  );
}
