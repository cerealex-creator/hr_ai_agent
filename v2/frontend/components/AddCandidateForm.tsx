"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

type Props = { vacancyId: number };

export function AddCandidateForm({ vacancyId }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [hh, setHh] = useState("");
  const [resume, setResume] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          hh_resume_link: hh || null,
          resume_link: resume || null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const cand = await res.json();
      setOpen(false);
      setName("");
      setHh("");
      setResume("");
      router.push(`/candidates/${cand.id}`);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка создания");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button type="button" className="chip" onClick={() => setOpen(true)}>
        + Кандидат
      </button>
    );
  }

  return (
    <div className="card-edit" style={{ marginBottom: "1rem" }}>
      <h3 className="hh-subhead" style={{ marginTop: 0 }}>
        Новый кандидат
      </h3>
      {err ? <p className="warn">{err}</p> : null}
      <div className="hh-field">
        <label className="hh-label">Имя</label>
        <input value={name} onChange={(e) => setName(e.target.value)} disabled={busy} />
      </div>
      <div className="hh-field">
        <label className="hh-label">HH (без контактов)</label>
        <input value={hh} onChange={(e) => setHh(e.target.value)} disabled={busy} />
      </div>
      <div className="hh-field">
        <label className="hh-label">Резюме PDF (Яндекс.Диск)</label>
        <input value={resume} onChange={(e) => setResume(e.target.value)} disabled={busy} />
      </div>
      <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
        <button type="button" className="chip chip-active" disabled={busy} onClick={submit}>
          Создать
        </button>
        <button type="button" className="chip" disabled={busy} onClick={() => setOpen(false)}>
          Отмена
        </button>
      </div>
    </div>
  );
}
