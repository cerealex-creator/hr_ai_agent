"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch, type VacancyDetail } from "@/lib/api";

type Props = { vacancy: VacancyDetail };

/** Удаление вакансии. Закрытие / возврат в работу — в шапке (VacancyCloseButton). */
export function VacancyLifecycle({ vacancy }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const remove = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancy.id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) {
        const data = await res.json().catch(() => ({}));
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      router.push(vacancy.active ? "/vacancies?tab=active" : "/vacancies?tab=archive");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rec-card">
      <h3 className="rec-card-title">Удаление вакансии</h3>
      {err ? <p className="warn">{err}</p> : null}
      <p className="muted hh-micro">
        Удаление необратимо: вакансия и все кандидаты будут удалены. Закрытие в архив — кнопкой в
        шапке карточки.
      </p>
      {!confirmDelete ? (
        <button type="button" className="chip" disabled={busy} onClick={() => setConfirmDelete(true)}>
          Удалить вакансию…
        </button>
      ) : (
        <div className="chip-row">
          <button type="button" className="chip chip-danger" disabled={busy} onClick={() => void remove()}>
            Да, удалить
          </button>
          <button type="button" className="chip" disabled={busy} onClick={() => setConfirmDelete(false)}>
            Отмена
          </button>
        </div>
      )}
    </div>
  );
}
