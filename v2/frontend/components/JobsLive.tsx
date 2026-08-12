"use client";

import Link from "next/link";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { getEventsStreamUrl } from "@/lib/api";

export type JobEvent = {
  id: string;
  job_type: string;
  status: string;
  progress_pct: number | null;
  progress_label: string | null;
  error: string | null;
  vacancy_id: number | null;
  updated_at: string | null;
};

type ToastItem = {
  id: string;
  kind: "ok" | "err";
  title: string;
  detail?: string;
};

type JobsLiveState = {
  activeCount: number;
  activeJobs: JobEvent[];
  connected: boolean;
};

const JOB_TYPE_LABELS: Record<string, string> = {
  demo_progress: "Демо-задача",
  import_legacy: "Импорт данных",
  transcribe_media: "Расшифровка",
  hh_cold_search: "Поиск HH",
  yandex_disk_sync: "Я.Диск",
  disk_inbox_router: "Inbox Я.Диска",
  vacancy_docs_from_materials: "Документы из материалов",
  candidate_interview_process: "Собеседование",
  candidate_evaluate_resume: "Оценка резюме",
};

function jobLabel(job: JobEvent): string {
  return JOB_TYPE_LABELS[job.job_type] || job.job_type;
}

const JobsLiveContext = createContext<JobsLiveState>({
  activeCount: 0,
  activeJobs: [],
  connected: false,
});

export function useJobsLive(): JobsLiveState {
  return useContext(JobsLiveContext);
}

export function JobsLiveProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const skip =
    pathname === "/login" ||
    pathname?.startsWith("/login/") ||
    pathname === "/c" ||
    pathname?.startsWith("/c/") ||
    pathname === "/i" ||
    pathname?.startsWith("/i/");

  const [activeCount, setActiveCount] = useState(0);
  const [activeJobs, setActiveJobs] = useState<JobEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const seenTerminal = useRef<Set<string>>(new Set());
  const toastTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = toastTimers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      toastTimers.current.delete(id);
    }
  }, []);

  const pushToast = useCallback(
    (item: ToastItem) => {
      setToasts((prev) => [...prev.filter((t) => t.id !== item.id), item].slice(-4));
      const prevTimer = toastTimers.current.get(item.id);
      if (prevTimer) clearTimeout(prevTimer);
      toastTimers.current.set(
        item.id,
        setTimeout(() => dismissToast(item.id), 8000),
      );
    },
    [dismissToast],
  );

  const applyJob = useCallback(
    (job: JobEvent, count?: number) => {
      if (typeof count === "number") setActiveCount(count);

      if (job.status === "queued" || job.status === "running") {
        setActiveJobs((prev) => {
          const rest = prev.filter((j) => j.id !== job.id);
          return [job, ...rest].slice(0, 20);
        });
        return;
      }

      setActiveJobs((prev) => prev.filter((j) => j.id !== job.id));

      if (job.status === "completed" || job.status === "failed") {
        const key = `${job.id}:${job.status}:${job.updated_at || ""}`;
        if (seenTerminal.current.has(key)) return;
        seenTerminal.current.add(key);
        if (seenTerminal.current.size > 80) {
          const arr = [...seenTerminal.current];
          seenTerminal.current = new Set(arr.slice(-40));
        }
        if (job.status === "completed") {
          pushToast({
            id: key,
            kind: "ok",
            title: `${jobLabel(job)} — готово`,
            detail: job.progress_label || undefined,
          });
        } else {
          pushToast({
            id: key,
            kind: "err",
            title: `${jobLabel(job)} — ошибка`,
            detail: job.error || job.progress_label || undefined,
          });
        }
      }
    },
    [pushToast],
  );

  useEffect(() => {
    if (skip) {
      setConnected(false);
      return;
    }

    let es: EventSource | null = null;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    const connect = () => {
      if (closed) return;
      es = new EventSource(getEventsStreamUrl());

      es.addEventListener("open", () => {
        attempt = 0;
        setConnected(true);
      });

      es.addEventListener("jobs.snapshot", (ev) => {
        try {
          const data = JSON.parse((ev as MessageEvent).data) as {
            active_count?: number;
            items?: JobEvent[];
          };
          setActiveCount(Number(data.active_count) || 0);
          const items = Array.isArray(data.items) ? data.items : [];
          setActiveJobs(items.filter((j) => j.status === "queued" || j.status === "running"));
          // Mark current terminal items as seen so reconnect doesn't re-toast.
          for (const j of items) {
            if (j.status === "completed" || j.status === "failed") {
              seenTerminal.current.add(`${j.id}:${j.status}:${j.updated_at || ""}`);
            }
          }
        } catch {
          /* ignore */
        }
      });

      es.addEventListener("job.updated", (ev) => {
        try {
          const data = JSON.parse((ev as MessageEvent).data) as {
            active_count?: number;
            job?: JobEvent;
          };
          if (data.job) applyJob(data.job, data.active_count);
          else if (typeof data.active_count === "number") setActiveCount(data.active_count);
        } catch {
          /* ignore */
        }
      });

      es.addEventListener("ping", (ev) => {
        try {
          const data = JSON.parse((ev as MessageEvent).data) as { active_count?: number };
          if (typeof data.active_count === "number") setActiveCount(data.active_count);
        } catch {
          /* ignore */
        }
      });

      es.onerror = () => {
        setConnected(false);
        es?.close();
        es = null;
        if (closed) return;
        attempt += 1;
        const delay = Math.min(15000, 1000 * 2 ** Math.min(attempt, 4));
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      es?.close();
      setConnected(false);
    };
  }, [skip, applyJob]);

  useEffect(() => {
    return () => {
      for (const t of toastTimers.current.values()) clearTimeout(t);
      toastTimers.current.clear();
    };
  }, []);

  const value = useMemo(
    () => ({ activeCount, activeJobs, connected }),
    [activeCount, activeJobs, connected],
  );

  return (
    <JobsLiveContext.Provider value={value}>
      {children}
      {toasts.length ? (
        <div className="jobs-toast-stack" aria-live="polite">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`jobs-toast jobs-toast-${t.kind}`}
              role="status"
            >
              <div className="jobs-toast-body">
                <strong>{t.title}</strong>
                {t.detail ? <span className="muted">{t.detail}</span> : null}
                <Link href="/jobs" className="jobs-toast-link">
                  К задачам →
                </Link>
              </div>
              <button
                type="button"
                className="jobs-toast-close"
                aria-label="Закрыть"
                onClick={() => dismissToast(t.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </JobsLiveContext.Provider>
  );
}

/** Compact topbar badge: active jobs → /jobs */
export function JobsLiveBadge() {
  const { activeCount, activeJobs, connected } = useJobsLive();
  if (!activeCount) return null;
  const tip =
    activeJobs
      .slice(0, 3)
      .map((j) => `${jobLabel(j)}${j.progress_pct != null ? ` ${j.progress_pct}%` : ""}`)
      .join(" · ") || "Фоновые задачи";
  return (
    <Link
      href="/jobs"
      className={`jobs-live-badge${connected ? "" : " jobs-live-badge-stale"}`}
      title={tip}
    >
      {activeCount} {activeCount === 1 ? "задача" : activeCount < 5 ? "задачи" : "задач"}
    </Link>
  );
}
