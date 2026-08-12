"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch, type VacancyDetail } from "@/lib/api";

type Props = { vacancy: VacancyDetail };

export function VacancyCloseButton({ vacancy }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const call = async (path: string, body?: unknown) => {
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(path, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setOpen(false);
      router.refresh();
      if (data.active === false) {
        router.push("/vacancies?tab=archive");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  if (!vacancy.active) {
    return (
      <div className="vac-close-wrap">
        {err ? <p className="warn hh-micro">{err}</p> : null}
        <button
          type="button"
          className="chip chip-active"
          disabled={busy}
          onClick={() => void call(`/api/v1/vacancies/${vacancy.id}/reopen`)}
        >
          {busy ? "…" : "Вернуть в работу"}
        </button>
      </div>
    );
  }

  if (!open) {
    return (
      <button type="button" className="chip vac-close-btn" disabled={busy} onClick={() => setOpen(true)}>
        Закрыть вакансию
      </button>
    );
  }

  return (
    <div className="vac-close-panel" role="dialog" aria-label="Закрытие вакансии">
      <p className="vac-close-warn">
        Вакансия уйдёт в архив. Успешное закрытие доступно только если есть кандидат на стажировке
        или вышедший на работу.
      </p>
      {err ? <p className="warn hh-micro">{err}</p> : null}
      <div className="chip-row">
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !vacancy.has_hire}
          title={
            vacancy.has_hire
              ? undefined
              : "Нет кандидата на стажировке / вышедшего на работу"
          }
          onClick={() =>
            void call(`/api/v1/vacancies/${vacancy.id}/close`, { close_reason: "success" })
          }
        >
          В архив (успех)
        </button>
        <button
          type="button"
          className="chip"
          disabled={busy}
          onClick={() =>
            void call(`/api/v1/vacancies/${vacancy.id}/close`, {
              close_reason: "client_cancelled",
            })
          }
        >
          Закрыта заказчиком
        </button>
        <button type="button" className="chip" disabled={busy} onClick={() => setOpen(false)}>
          Отмена
        </button>
      </div>
    </div>
  );
}
