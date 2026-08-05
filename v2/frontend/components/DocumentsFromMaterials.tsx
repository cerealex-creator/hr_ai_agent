"use client";

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type Props = {
  vacancyId: number;
  onDone?: () => void;
};

type Job = {
  id: string;
  status: string;
  progress_pct: number | null;
  progress_label: string | null;
  error: string | null;
  payload?: {
    conflicts?: string[];
    meeting_brief?: { summary?: string; qa?: { q: string; a: string }[] };
  };
};

export function DocumentsFromMaterials({ vacancyId, onDone }: Props) {
  const [files, setFiles] = useState<FileList | null>(null);
  const [urls, setUrls] = useState("");
  const [notes, setNotes] = useState("");
  const [instructions, setInstructions] = useState("");
  const [useExisting, setUseExisting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(`${getApiBase()}/api/v1/jobs/${job.id}`, { cache: "no-store" });
        if (!res.ok) return;
        const next: Job = await res.json();
        if (cancelled) return;
        setJob(next);
        if (next.status === "completed") {
          setMsg("Документы обновлены по материалам встречи.");
          setBusy(false);
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

  const start = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const fd = new FormData();
      if (files) {
        Array.from(files).forEach((f) => fd.append("files", f));
      }
      fd.append("source_urls", urls);
      fd.append("notes", notes);
      fd.append("hr_instructions", instructions);
      fd.append("use_existing_profile", useExisting ? "true" : "false");
      fd.append("gen_profile", "true");
      fd.append("gen_questions", "true");
      fd.append("gen_vacancy_text", "true");
      fd.append("gen_keywords", "true");
      const res = await fetch(
        `${getApiBase()}/api/v1/vacancies/${vacancyId}/documents/from-materials`,
        { method: "POST", body: fd },
      );
      if (!res.ok) {
        let detail = await res.text();
        try {
          detail = JSON.parse(detail).detail || detail;
        } catch {
          /* keep */
        }
        throw new Error(detail);
      }
      const created = await res.json();
      setJob({
        id: created.id,
        status: created.status || "queued",
        progress_pct: 0,
        progress_label: "В очереди…",
        error: null,
      });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось запустить");
      setBusy(false);
    }
  };

  return (
    <div className="card-edit" style={{ marginBottom: "1rem" }}>
      <h3 className="hh-subhead">Из записи / материалов встречи</h3>
      <p className="muted hh-micro">
        Загрузите аудио/видео (Zoom, диктофон, Я.Диск), Word/Excel/PDF или вставьте публичные ссылки
        Яндекс.Диска. Система расшифрует, сгенерирует пакет и сразу запишет в документы вакансии.
      </p>
      <label className="hh-field">
        <span className="hh-label">Файлы</span>
        <input
          type="file"
          multiple
          disabled={busy}
          accept=".mp3,.mp4,.wav,.webm,.mkv,.ogg,.m4a,.mov,.aac,.txt,.md,.pdf,.docx,.xlsx,.xls,.csv"
          onChange={(e) => setFiles(e.target.files)}
        />
      </label>
      <label className="hh-field">
        <span className="hh-label">Ссылки Яндекс.Диска (по одной в строке)</span>
        <textarea
          rows={2}
          value={urls}
          disabled={busy}
          onChange={(e) => setUrls(e.target.value)}
          placeholder="https://disk.yandex.ru/…"
        />
      </label>
      <label className="hh-field">
        <span className="hh-label">Заметки HR</span>
        <textarea rows={2} value={notes} disabled={busy} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <label className="hh-field">
        <span className="hh-label">Указания HR (высший приоритет)</span>
        <textarea
          rows={2}
          value={instructions}
          disabled={busy}
          onChange={(e) => setInstructions(e.target.value)}
        />
      </label>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={useExisting}
          disabled={busy}
          onChange={(e) => setUseExisting(e.target.checked)}
        />
        Использовать профиль, уже сохранённый в вакансии
      </label>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {job && ["queued", "running"].includes(job.status) ? (
        <p className="muted">
          {job.progress_label || "Обработка…"}
          {job.progress_pct != null ? ` · ${job.progress_pct}%` : ""}
        </p>
      ) : null}
      <button type="button" className="chip chip-active" disabled={busy} onClick={() => void start()}>
        {busy ? "Обработка…" : "Расшифровать и обновить документы"}
      </button>
    </div>
  );
}
