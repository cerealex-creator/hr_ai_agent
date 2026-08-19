"use client";

import { useState } from "react";
import { ActionBanner } from "@/components/ActionBanner";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";
import { DEMO_WRITE_HINT } from "@/lib/demo";

type Props = {
  vacancyId: number;
  hasChatId: boolean;
};

export function VacancyDigestButton({ vacancyId, hasChatId }: Props) {
  const { isDemo } = useAuth();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const send = async () => {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/digest-to-chat`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          typeof data?.detail === "string" ? data.detail : data?.message || `HTTP ${res.status}`,
        );
      }
      setMsg(data.message || "Сводка отправлена в чат");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка отправки");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <ActionBanner msg={msg} err={err} />
      <button
        type="button"
        className="chip chip-active"
        disabled={busy || !hasChatId || isDemo}
        title={
          isDemo
            ? DEMO_WRITE_HINT
            : hasChatId
              ? "Отправить сводку по вакансии в Telegram-чат"
              : "Укажите chat_id в параметрах вакансии"
        }
        onClick={() => void send()}
      >
        {busy ? "Отправка…" : "Сводка в чат"}
      </button>
      {!hasChatId ? (
        <p className="muted hh-micro" style={{ marginTop: "0.35rem" }}>
          Нет chat_id — укажите чат в параметрах вакансии.
        </p>
      ) : null}
    </div>
  );
}
