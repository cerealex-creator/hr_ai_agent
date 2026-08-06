"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

type Props = {
  generationId: string;
  defaultVacancyId?: number | null;
};

export function HistoryApplyButton({ generationId, defaultVacancyId }: Props) {
  const router = useRouter();
  const [vacancyId, setVacancyId] = useState(defaultVacancyId ? String(defaultVacancyId) : "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const apply = async () => {
    const vid = parseInt(vacancyId, 10);
    if (!vid) {
      setErr("Укажите id вакансии");
      return;
    }
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/history/${generationId}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vacancy_id: vid }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setMsg(`Применено к вакансии «${data.title || vid}»`);
      router.push(`/vacancies/${vid}?view=docs`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card-edit" style={{ marginTop: "1rem" }}>
      <h3 className="hh-subhead">Применить к вакансии</h3>
      <label className="hh-field">
        <span className="hh-label">ID вакансии</span>
        <input value={vacancyId} onChange={(e) => setVacancyId(e.target.value)} disabled={busy} />
      </label>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <button type="button" className="chip chip-active" disabled={busy} onClick={() => void apply()}>
        {busy ? "…" : "Применить пакет"}
      </button>
    </div>
  );
}
