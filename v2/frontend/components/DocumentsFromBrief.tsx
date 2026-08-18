"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Props = {
  vacancyId: number;
  defaultTitle?: string;
  onDone?: () => void;
};

type Job = {
  id: string;
  status: string;
  progress_pct: number | null;
  progress_label: string | null;
  error: string | null;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

/** Brief form → AI document pack for the vacancy (background job + poll). */
export function DocumentsFromBrief({ vacancyId, defaultTitle = "", onDone }: Props) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(defaultTitle);
  const [tasks, setTasks] = useState("");
  const [mustHave, setMustHave] = useState("");
  const [conditions, setConditions] = useState("");
  const [interviewQuestions, setInterviewQuestions] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await apiFetch(`/api/v1/jobs/${job.id}`, { cache: "no-store" });
        if (!res.ok) return;
        const next: Job = await res.json();
        if (cancelled) return;
        setJob(next);
        if (next.status === "completed") {
          setMsg("ИИ собрал документы и сохранил. Можно править в списке документов.");
          setBusy(false);
          setOpen(false);
          onDone?.();
        } else if (next.status === "failed" || next.status === "cancelled") {
          setErr(next.error || next.progress_label || "Ошибка");
          setBusy(false);
        }
      } catch {
        /* ignore transient */
      }
    };
    const id = setInterval(() => void tick(), 2500);
    void tick();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [job, onDone]);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/documents/from-brief`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim() || defaultTitle,
          tasks,
          must_have: mustHave,
          conditions,
          interview_questions: interviewQuestions,
          apply: true,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
      setJob({
        id: String((data as { id?: string }).id || ""),
        status: String((data as { status?: string }).status || "queued"),
        progress_pct: 0,
        progress_label: "В очереди…",
        error: null,
      });
      setMsg("Задача в очереди — обычно 1–2 минуты.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <div className="card-edit" style={{ marginBottom: "1rem" }}>
        <h3 className="hh-subhead">Собрать документы по вопросам</h3>
        <p className="muted hh-micro" style={{ marginTop: 0 }}>
          Ответьте на несколько вопросов — ИИ соберёт профиль, текст вакансии, опросник и ключевые
          слова.
        </p>
        <button type="button" className="chip chip-active" onClick={() => setOpen(true)}>
          Открыть форму
        </button>
      </div>
    );
  }

  const progressLabel = job?.progress_label || null;
  const progressPct = typeof job?.progress_pct === "number" ? job.progress_pct : null;

  return (
    <div className="card-edit" style={{ marginBottom: "1rem", borderColor: "var(--accent)" }}>
      <h3 className="hh-subhead">Собрать документы по вопросам</h3>
      <p className="muted hh-micro">
        Можно писать списком (каждая строка — отдельный пункт). После отправки ИИ работает в фоне
        (обычно 1–2 минуты).
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {busy && progressLabel ? (
        <p className="muted hh-micro">
          {progressLabel}
          {progressPct != null ? ` (${progressPct}%)` : ""}
        </p>
      ) : null}

      <div className="hh-field">
        <label className="hh-label" htmlFor="brief-title">
          Название должности
        </label>
        <input
          id="brief-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={busy}
          placeholder={defaultTitle || "Например: Менеджер по маркетплейсам"}
        />
      </div>
      <div className="hh-field">
        <label className="hh-label" htmlFor="brief-tasks">
          Чем занимается / задачи
        </label>
        <textarea
          id="brief-tasks"
          rows={4}
          value={tasks}
          onChange={(e) => setTasks(e.target.value)}
          disabled={busy}
          placeholder={"Ведение кабинета WB\nРабота с карточками\nАналитика продаж"}
        />
      </div>
      <div className="hh-field">
        <label className="hh-label" htmlFor="brief-must">
          Что обязательно (опыт, навыки)
        </label>
        <textarea
          id="brief-must"
          rows={4}
          value={mustHave}
          onChange={(e) => setMustHave(e.target.value)}
          disabled={busy}
          placeholder={"Опыт с маркетплейсами от 1 года\nExcel / Google Sheets"}
        />
      </div>
      <div className="hh-field">
        <label className="hh-label" htmlFor="brief-cond">
          Условия (город, график, деньги — свободно)
        </label>
        <textarea
          id="brief-cond"
          rows={3}
          value={conditions}
          onChange={(e) => setConditions(e.target.value)}
          disabled={busy}
          placeholder={"Санкт-Петербург / удалённо\nОклад + бонус"}
        />
      </div>
      <div className="hh-field">
        <label className="hh-label" htmlFor="brief-q">
          Что спросить на собеседовании (по строке)
        </label>
        <textarea
          id="brief-q"
          rows={3}
          value={interviewQuestions}
          onChange={(e) => setInterviewQuestions(e.target.value)}
          disabled={busy}
          placeholder={"Расскажите про последний проект на WB\nКак считаете unit-экономику?"}
        />
      </div>

      <div className="chip-row">
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || (!tasks.trim() && !mustHave.trim())}
          onClick={() => void submit()}
        >
          {busy ? "ИИ пишет…" : "Собрать через ИИ"}
        </button>
        <button
          type="button"
          className="chip"
          disabled={busy}
          onClick={() => {
            setOpen(false);
            setErr(null);
          }}
        >
          Отмена
        </button>
      </div>
    </div>
  );
}
