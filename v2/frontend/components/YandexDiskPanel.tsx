"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

type Config = {
  vacancy_id: number;
  root_url: string;
  ingest_new_resumes: boolean;
  subfolders: Record<string, string>;
  last_sync_at: string | null;
  seen_count: number;
};

type SyncResult = {
  vacancy_id: number;
  created: number;
  updated: number;
  skipped: number;
  messages: string[];
  errors: string[];
  changed: boolean;
  last_sync_at: string | null;
};

type Props = {
  vacancyId: number;
  initial: Config;
};

export function YandexDiskPanel({ vacancyId, initial }: Props) {
  const router = useRouter();
  const [rootUrl, setRootUrl] = useState(initial.root_url || "");
  const [ingestNew, setIngestNew] = useState(initial.ingest_new_resumes !== false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [last, setLast] = useState<SyncResult | null>(null);
  const [seenCount, setSeenCount] = useState(initial.seen_count || 0);
  const [lastSync, setLastSync] = useState(initial.last_sync_at);
  const [appPath, setAppPath] = useState<string | null>(null);

  const ensureFolders = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/yandex-disk/ensure-folders`,
        { method: "POST" },
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      if (data.config?.root_url) setRootUrl(data.config.root_url);
      setAppPath(data.path || null);
      setMsg(
        data.public_url
          ? `Папки созданы и опубликованы: ${data.path}`
          : `Папки созданы: ${data.path} (публичная ссылка не получена — проверьте токен)`,
      );
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка создания папок");
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/yandex-disk`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          root_url: rootUrl,
          ingest_new_resumes: ingestNew,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setSeenCount(data.seen_count ?? seenCount);
      setLastSync(data.last_sync_at ?? lastSync);
      setMsg("Настройки Диска сохранены");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  };

  const syncNow = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      // persist first
      const patch = await apiFetch(`/api/v1/vacancies/${vacancyId}/yandex-disk`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root_url: rootUrl, ingest_new_resumes: ingestNew }),
      });
      if (!patch.ok) {
        const data = await patch.json().catch(() => ({}));
        throw new Error(typeof data?.detail === "string" ? data.detail : "Не удалось сохранить URL");
      }
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/yandex-disk/sync`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`);
      }
      setLast(data as SyncResult);
      setLastSync(data.last_sync_at || null);
      setMsg(
        `Синхронизация: +${data.created || 0} новых, обновлено ${data.updated || 0}, пропуск ${data.skipped || 0}`,
      );
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка синхронизации");
    } finally {
      setBusy(false);
    }
  };

  const resetSeen = async () => {
    if (!window.confirm("Сбросить список обработанных файлов и синхронизировать заново?")) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/vacancies/${vacancyId}/yandex-disk`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reset_seen: true, root_url: rootUrl, ingest_new_resumes: ingestNew }),
      });
      if (!res.ok) throw new Error("Не удалось сбросить список обработанных файлов");
      setSeenCount(0);
      setMsg("Список обработанных файлов сброшен — можно синхронизировать снова");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card-edit">
      <h2>Яндекс.Диск</h2>
      <p className="muted hh-micro">
        Публичная папка вакансии → привязка PDF/видео/заданий к кандидатам по ФИО в имени файла.
        Либо подключите OAuth в{" "}
        <a href="/settings/candidate-intake#yandex-disk-connect">
          Настройки → Способы добавления кандидатов
        </a>{" "}
        и создайте папки автоматически.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {appPath ? <p className="muted hh-micro">Путь приложения: {appPath}</p> : null}

      <div className="hh-field">
        <label className="hh-label" htmlFor="yd-root">
          Ссылка на папку
        </label>
        <input
          id="yd-root"
          value={rootUrl}
          onChange={(e) => setRootUrl(e.target.value)}
          disabled={busy}
          placeholder="https://disk.yandex.ru/d/…"
        />
      </div>
      <label className="hh-check">
        <input
          type="checkbox"
          checked={ingestNew}
          onChange={(e) => setIngestNew(e.target.checked)}
          disabled={busy}
        />
        Создавать кандидатов из новых PDF без пары
      </label>
      <p className="muted hh-micro">
        Последняя синхронизация: {lastSync || "ещё не было"}
        {seenCount ? ` · обработано путей: ${seenCount}` : ""}
      </p>
      <div className="chip-row">
        <button type="button" className="chip" disabled={busy} onClick={ensureFolders}>
          Создать папки на Диске
        </button>
        <button type="button" className="chip" disabled={busy} onClick={save}>
          Сохранить
        </button>
        <button type="button" className="chip chip-active" disabled={busy} onClick={syncNow}>
          Синхронизировать
        </button>
        <button type="button" className="chip" disabled={busy} onClick={resetSeen}>
          Сбросить обработанные файлы
        </button>
      </div>
      {last?.messages?.length ? (
        <ul className="yd-log muted">
          {last.messages.slice(0, 12).map((line, i) => (
            <li key={`m-${i}-${line}`}>{line}</li>
          ))}
        </ul>
      ) : null}
      {last?.errors?.length ? (
        <ul className="yd-log warn">
          {last.errors.map((line, i) => (
            <li key={`e-${i}-${line}`}>{line}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
