"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";

type Job = {
  id: string;
  job_type: string;
  status: string;
  progress_pct: number | null;
  progress_label: string | null;
  result_ref: string | null;
  error: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
};

type JobsList = {
  active_count: number;
  items: Job[];
};

const JOB_TYPE_LABELS: Record<string, string> = {
  demo_progress: "Демо-задача (прогресс)",
  import_legacy: "Импорт данных",
  transcribe_media: "Расшифровка (SpeechKit)",
  hh_cold_search: "Поиск резюме HH (холодный)",
  yandex_disk_sync: "Синхронизация Я.Диска",
  candidate_interview_process: "Обработка собеседования",
};

const STATUS_LABELS: Record<string, string> = {
  queued: "В очереди",
  running: "Выполняется",
  completed: "Готово",
  failed: "Ошибка",
  cancelled: "Отменено",
};

function statusClass(status: string): string {
  if (status === "completed" || status === "running") return "outcome outcome-success";
  if (status === "failed") return "outcome outcome-no_result";
  if (status === "cancelled") return "outcome outcome-client_cancelled";
  return "outcome outcome-none";
}

async function fetchJobs(): Promise<JobsList> {
  const res = await fetch(`${getApiBase()}/api/v1/jobs?limit=40`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function startJob(job_type: string, payload: Record<string, unknown> = {}): Promise<void> {
  const res = await fetch(`${getApiBase()}/api/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_type, payload }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `API ${res.status}`);
  }
}

async function cancelJob(id: string): Promise<void> {
  const res = await fetch(`${getApiBase()}/api/v1/jobs/${id}/cancel`, { method: "POST" });
  if (!res.ok) throw new Error(`API ${res.status}`);
}

export default function JobsPage() {
  const [data, setData] = useState<JobsList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const next = await fetchJobs();
      setData(next);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка API");
    }
  }, []);

  useEffect(() => {
    reload();
    const t = setInterval(reload, 2000);
    return () => clearInterval(t);
  }, [reload]);

  const onStart = async (job_type: string, payload: Record<string, unknown> = {}) => {
    setBusy(job_type);
    try {
      await startJob(job_type, payload);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось запустить");
    } finally {
      setBusy(null);
    }
  };

  const onTranscribe = async () => {
    const url = sourceUrl.trim();
    if (!url) {
      setError("Вставьте ссылку на видео/аудио (Яндекс.Диск или прямую)");
      return;
    }
    await onStart("transcribe_media", { source_url: url });
  };

  const onCancel = async (id: string) => {
    setBusy(id);
    try {
      await cancelJob(id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отменить");
    } finally {
      setBusy(null);
    }
  };

  return (
    <AppShell activePath="/jobs">
      <h1 className="page-title">Задачи</h1>
      <p className="muted">
        Фоновые jobs через Redis + ARQ. Расшифровка: ffmpeg → Yandex Object Storage → SpeechKit.
      </p>

      {error ? <p className="warn">{error}</p> : null}

      <div className="stats">
        <div className="stat">
          <strong>{data?.active_count ?? "—"}</strong>
          <span>активных</span>
        </div>
        <div className="stat">
          <strong>{data?.items.length ?? "—"}</strong>
          <span>в списке</span>
        </div>
      </div>

      <div className="chip-row" style={{ marginBottom: "1rem" }}>
        <button
          type="button"
          className="chip chip-active"
          disabled={!!busy}
          onClick={() => onStart("demo_progress")}
        >
          {busy === "demo_progress" ? "Запуск…" : "Запустить демо"}
        </button>
        <button
          type="button"
          className="chip"
          disabled={!!busy}
          onClick={() => onStart("import_legacy")}
          title="Перечитает локальный snapshot data/ и перезапишет таблицы"
        >
          {busy === "import_legacy" ? "Запуск…" : "Импорт данных"}
        </button>
      </div>

      <div className="panel" style={{ marginBottom: "1.25rem" }}>
        <h2 className="section-title" style={{ marginTop: 0 }}>
          Расшифровка
        </h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Публичная ссылка Яндекс.Диска или прямая на медиа. Ключи SpeechKit — из корневого{" "}
          <code>.env</code>.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://disk.yandex.ru/… или прямая ссылка"
            style={{
              flex: "1 1 280px",
              minWidth: 0,
              padding: "0.55rem 0.75rem",
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--text)",
            }}
          />
          <button
            type="button"
            className="chip chip-active"
            disabled={!!busy}
            onClick={onTranscribe}
          >
            {busy === "transcribe_media" ? "Запуск…" : "Расшифровать"}
          </button>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Тип</th>
            <th>Статус</th>
            <th>Прогресс</th>
            <th>Создана</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(data?.items || []).map((job) => {
            const canCancel = job.status === "queued" || job.status === "running";
            const transcript =
              typeof job.payload?.transcript === "string" ? job.payload.transcript : null;
            const preview =
              typeof job.payload?.preview === "string" ? job.payload.preview : null;
            const source =
              typeof job.payload?.source_url === "string" ? job.payload.source_url : null;
            const open = expandedId === job.id;
            return (
              <Fragment key={job.id}>
                <tr>
                  <td>
                    <div>{JOB_TYPE_LABELS[job.job_type] || job.job_type}</div>
                    <div className="row-meta">{job.id.slice(0, 8)}…</div>
                    {source ? (
                      <div className="row-meta" title={source}>
                        {source.length > 48 ? `${source.slice(0, 48)}…` : source}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <span className={statusClass(job.status)}>
                      {STATUS_LABELS[job.status] || job.status}
                    </span>
                    {job.error ? <div className="row-meta warn">{job.error}</div> : null}
                    {preview && job.status === "completed" ? (
                      <div className="row-meta">{preview}</div>
                    ) : null}
                  </td>
                  <td>
                    <div>{job.progress_label || "—"}</div>
                    <div className="bar-track" style={{ marginTop: 6 }}>
                      <div
                        className="bar-fill"
                        style={{ width: `${Math.max(0, Math.min(100, job.progress_pct ?? 0))}%` }}
                      />
                    </div>
                    <div className="row-meta">{job.progress_pct ?? 0}%</div>
                  </td>
                  <td className="row-meta">
                    {new Date(job.created_at).toLocaleString("ru-RU")}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {transcript ? (
                        <button
                          type="button"
                          className="chip"
                          onClick={() => setExpandedId(open ? null : job.id)}
                        >
                          {open ? "Скрыть текст" : "Текст"}
                        </button>
                      ) : null}
                      {canCancel ? (
                        <button
                          type="button"
                          className="chip"
                          disabled={busy === job.id}
                          onClick={() => onCancel(job.id)}
                        >
                          Отменить
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
                {open && transcript ? (
                  <tr>
                    <td colSpan={5}>
                      <pre
                        style={{
                          whiteSpace: "pre-wrap",
                          margin: 0,
                          padding: "0.75rem",
                          background: "var(--surface)",
                          borderRadius: 8,
                          maxHeight: 320,
                          overflow: "auto",
                          fontSize: "0.9rem",
                        }}
                      >
                        {transcript}
                      </pre>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
          {!data?.items.length ? (
            <tr>
              <td colSpan={5}>Пока нет задач. Запустите демо или расшифровку выше.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </AppShell>
  );
}
