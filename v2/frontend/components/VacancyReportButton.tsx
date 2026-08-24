"use client";

import { useCallback, useEffect, useState } from "react";
import { ActionBanner } from "@/components/ActionBanner";
import { ClientZoneLink } from "@/components/ClientZoneLink";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";
import { DEMO_WRITE_HINT } from "@/lib/demo";

type Props = {
  vacancyId: number;
  clientId: number | null;
  hasChatId: boolean;
};

export function VacancyReportButton({ vacancyId, clientId, hasChatId }: Props) {
  const { isDemo } = useAuth();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [zonePath, setZonePath] = useState<string | null>(null);

  const loadZone = useCallback(async () => {
    if (!clientId) {
      setZonePath(null);
      return;
    }
    try {
      const res = await apiFetch(`/api/v1/companies/${clientId}/client-zone`);
      const data = (await res.json().catch(() => ({}))) as { path?: string | null };
      if (res.ok && typeof data.path === "string" && data.path.startsWith("/c/")) {
        setZonePath(data.path);
      } else {
        setZonePath(null);
      }
    } catch {
      setZonePath(null);
    }
  }, [clientId]);

  useEffect(() => {
    void loadZone();
  }, [loadZone]);

  const send = async () => {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/report-to-chat`, {
        method: "POST",
      });
      const data = (await res.json().catch(() => ({}))) as {
        detail?: string;
        message?: string;
        zone_url?: string;
        path?: string;
      };
      if (!res.ok) {
        throw new Error(
          typeof data?.detail === "string" ? data.detail : data?.message || `HTTP ${res.status}`,
        );
      }
      setMsg(data.message || "Отчёт заказчику отправлен в чат");
      // После отправки токен зоны мог только что создаться
      await loadZone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка отправки");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <ActionBanner msg={msg} err={err} />
      <ClientZoneLink
        path={zonePath}
        label="Общая ссылка на зону заказчика (для закрепления в чате)"
        compact
      />
      {!clientId ? (
        <p className="muted hh-micro" style={{ marginTop: "0.35rem" }}>
          Привяжите компанию/подразделение к вакансии — тогда здесь появится ссылка на зону.
        </p>
      ) : null}
      <button
        type="button"
        className="chip chip-active"
        style={{ marginTop: "0.65rem" }}
        disabled={busy || !hasChatId || isDemo}
        title={
          isDemo
            ? DEMO_WRITE_HINT
            : hasChatId
              ? "Отправить в Telegram отчёт с цифрами воронки и кнопкой «Посмотреть отчёт»"
              : "Укажите chat_id в параметрах вакансии"
        }
        onClick={() => void send()}
      >
        {busy ? "Отправка…" : "Отчёт заказчику"}
      </button>
      <p className="muted hh-micro" style={{ marginTop: "0.35rem" }}>
        В чат уйдут только цифры воронки и кнопка «Посмотреть отчёт». Общую ссылку на зону
        скопируйте выше и закрепите в чате вручную.
      </p>
      {!hasChatId ? (
        <p className="muted hh-micro" style={{ marginTop: "0.35rem" }}>
          Нет chat_id — укажите чат в параметрах вакансии.
        </p>
      ) : null}
    </div>
  );
}
