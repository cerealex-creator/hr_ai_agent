"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";

type Props = {
  vacancyId: number;
  title: string;
  searchModeWarranty?: boolean;
  isTest?: boolean;
};

export function VacancyTitleEditor({
  vacancyId,
  title: initialTitle,
  searchModeWarranty,
  isTest,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(initialTitle);
  const [draft, setDraft] = useState(initialTitle);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const save = async () => {
    const next = draft.trim();
    if (!next) {
      setErr("Название не может быть пустым");
      return;
    }
    if (next === title) {
      setEditing(false);
      setErr(null);
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: next }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setTitle(typeof data.title === "string" ? data.title : next);
      setDraft(typeof data.title === "string" ? data.title : next);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось сохранить");
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void save();
  };

  if (editing) {
    return (
      <form className="vacancy-title-edit" onSubmit={onSubmit}>
        <input
          className="vacancy-title-input"
          value={draft}
          autoFocus
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => void save()}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setDraft(title);
              setEditing(false);
              setErr(null);
            }
          }}
          aria-label="Название вакансии"
        />
        {err ? <p className="warn hh-micro">{err}</p> : null}
      </form>
    );
  }

  return (
    <h1 className="vac-head-title">
      <button
        type="button"
        className="vacancy-title-btn"
        onClick={() => {
          setDraft(title);
          setEditing(true);
        }}
        title="Изменить название"
      >
        {title}
      </button>
      {searchModeWarranty ? <span className="muted"> · гарантийный поиск</span> : null}
      {isTest ? <span className="muted"> · тест</span> : null}
    </h1>
  );
}
