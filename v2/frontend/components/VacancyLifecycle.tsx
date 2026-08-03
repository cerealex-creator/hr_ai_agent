"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { getApiBase, type VacancyDetail } from "@/lib/api";
import { CollapsibleCard } from "@/components/CollapsibleCard";

type Props = { vacancy: VacancyDetail };

export function VacancyLifecycle({ vacancy }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const call = async (path: string, method: string, body?: unknown) => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${getApiBase()}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (method === "DELETE") {
        if (!res.ok && res.status !== 204) {
          const data = await res.json().catch(() => ({}));
          throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
        }
        router.push(vacancy.active ? "/vacancies?tab=active" : "/vacancies?tab=archive");
        router.refresh();
        return;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setMsg(
        data.active
          ? "Вакансия снова в работе"
          : data.close_reason === "client_cancelled"
            ? "Закрыта заказчиком → архив"
            : "Закрыта успешно → архив",
      );
      router.refresh();
      if (!data.active) {
        router.push(`/vacancies?tab=archive`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const hint = vacancy.active ? "в работе" : "архив";

  return (
    <CollapsibleCard title="Управление вакансией" hint={hint} defaultOpen={false}>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      {vacancy.active ? (
        <>
          <p className="muted hh-micro">
            Успешное закрытие — только если есть кандидат на стажировке / вышедший на работу.
            Если заказчик передумал — «Закрыта заказчиком».
          </p>
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
                call(`/api/v1/vacancies/${vacancy.id}/close`, "POST", { close_reason: "success" })
              }
            >
              В архив (успех)
            </button>
            <button
              type="button"
              className="chip"
              disabled={busy}
              onClick={() =>
                call(`/api/v1/vacancies/${vacancy.id}/close`, "POST", {
                  close_reason: "client_cancelled",
                })
              }
            >
              Закрыта заказчиком
            </button>
          </div>
          {!vacancy.has_hire ? (
            <p className="muted hh-micro">
              Кнопка «В архив (успех)» недоступна: нет hire-этапа у кандидатов.
            </p>
          ) : null}
        </>
      ) : (
        <>
          <p className="muted hh-micro">Вакансия в архиве. Можно вернуть в работу.</p>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy}
            onClick={() => call(`/api/v1/vacancies/${vacancy.id}/reopen`, "POST")}
          >
            Вернуть в работу
          </button>
        </>
      )}

      <hr className="vac-life-sep" />
      <p className="muted hh-micro">
        Удаление необратимо: вакансия и все кандидаты будут удалены.
      </p>
      {!confirmDelete ? (
        <button type="button" className="chip" disabled={busy} onClick={() => setConfirmDelete(true)}>
          Удалить вакансию…
        </button>
      ) : (
        <div className="chip-row">
          <button
            type="button"
            className="chip chip-danger"
            disabled={busy}
            onClick={() => call(`/api/v1/vacancies/${vacancy.id}`, "DELETE")}
          >
            Да, удалить
          </button>
          <button type="button" className="chip" disabled={busy} onClick={() => setConfirmDelete(false)}>
            Отмена
          </button>
        </div>
      )}
    </CollapsibleCard>
  );
}
