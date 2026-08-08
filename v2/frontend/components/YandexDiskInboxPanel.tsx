"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type UnsortedItem = {
  id: string;
  file_name: string;
  confidence?: string | null;
  vacancy_id?: number | null;
  extracted?: { full_name?: string; phone?: string; reason?: string };
  note?: string | null;
};

type VacancyOpt = { id: number; title: string };

type Props = {
  active?: boolean;
};

/** Inbox routing + unsorted queue — shown when disk_inbox channel is on. */
export function YandexDiskInboxPanel({ active = true }: Props) {
  const [inboxPath, setInboxPath] = useState("/HR_AI_Agent/_inbox");
  const [unsorted, setUnsorted] = useState<UnsortedItem[]>([]);
  const [inboxMsg, setInboxMsg] = useState("");
  const [processLog, setProcessLog] = useState<string[]>([]);
  const [vacancies, setVacancies] = useState<VacancyOpt[]>([]);
  const [bindVacancy, setBindVacancy] = useState<Record<string, string>>({});
  const [threshold, setThreshold] = useState(0.75);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadInbox = async () => {
    const res = await apiFetch(`/api/v1/integrations/yandex-disk/inbox`, {
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
    setUnsorted(data.unsorted || []);
    setInboxMsg(data.message || "");
    if (data.settings?.confidence != null) setThreshold(Number(data.settings.confidence));
  };

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    (async () => {
      try {
        const [statusRes, vacRes] = await Promise.all([
          apiFetch(`/api/v1/integrations/yandex-disk/status`, { cache: "no-store" }),
          apiFetch(`/api/v1/vacancies?active=true`, { cache: "no-store" }),
        ]);
        const status = await statusRes.json().catch(() => ({}));
        const vacData = await vacRes.json().catch(() => ([]));
        if (cancelled) return;
        if (status.inbox_path) setInboxPath(status.inbox_path);
        const items = (Array.isArray(vacData) ? vacData : vacData.items || []) as {
          id: number;
          title: string;
        }[];
        setVacancies(items.map((v) => ({ id: v.id, title: v.title })));
        await loadInbox();
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Ошибка загрузки inbox");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [active]);

  if (!active) return null;

  const runRouter = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await apiFetch(`/api/v1/integrations/yandex-disk/inbox/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confidence: threshold }),
      });
      const res = await apiFetch(`/api/v1/integrations/yandex-disk/inbox/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: 20 }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setProcessLog(data.details || []);
      setMsg(
        `Готово: routed ${data.routed || 0}, unsorted ${data.unsorted || 0}, errors ${data.errors || 0}`,
      );
      await loadInbox();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const bindItem = async (id: string) => {
    const vid = Number(bindVacancy[id]);
    if (!vid) {
      setErr("Выберите вакансию");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const res = await apiFetch(`/api/v1/integrations/yandex-disk/inbox/${id}/bind`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vacancy_id: vid }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setMsg(`Привязано к вакансии #${vid}`);
      await loadInbox();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card-edit" id="yandex-disk-inbox">
      <h2>Роутинг из inbox</h2>
      <p className="muted hh-micro">
        Кидайте PDF в <code>{inboxPath}</code>. Имя файла не обязательно. Порог confidence ниже —
        в unsorted. Без автозапуска — только кнопка ниже или Inbox в меню.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {inboxMsg ? <p className="muted">{inboxMsg}</p> : null}
      <label className="hh-field">
        <span className="hh-label">Порог confidence · {Math.round(threshold * 100)}%</span>
        <input
          type="range"
          min={40}
          max={95}
          step={5}
          value={Math.round(threshold * 100)}
          disabled={busy}
          onChange={(e) => setThreshold(Number(e.target.value) / 100)}
        />
      </label>
      <div className="hh-footer-actions" style={{ justifyContent: "flex-start" }}>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy}
          onClick={() => void runRouter()}
        >
          {busy ? "…" : "Запустить роутинг сейчас"}
        </button>
        <button
          type="button"
          className="chip"
          disabled={busy}
          onClick={() => void loadInbox().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"))}
        >
          Обновить список
        </button>
      </div>
      {processLog.length ? (
        <ul className="yd-log muted">
          {processLog.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}

      <h3 className="hh-subhead">Нужен разбор (unsorted)</h3>
      {unsorted.length ? (
        <table>
          <thead>
            <tr>
              <th>Файл</th>
              <th>ФИО</th>
              <th>ИИ</th>
              <th>Вакансия</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {unsorted.map((it) => (
              <tr key={it.id}>
                <td>{it.file_name}</td>
                <td>{it.extracted?.full_name || "—"}</td>
                <td className="row-meta">
                  {it.confidence || "—"}
                  {it.extracted?.reason ? ` · ${it.extracted.reason}` : ""}
                  {it.note ? ` · ${it.note}` : ""}
                </td>
                <td>
                  <select
                    value={bindVacancy[it.id] || ""}
                    disabled={busy}
                    onChange={(e) =>
                      setBindVacancy((prev) => ({ ...prev, [it.id]: e.target.value }))
                    }
                  >
                    <option value="">Выберите…</option>
                    {vacancies.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.title}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button
                    type="button"
                    className="chip chip-active"
                    disabled={busy}
                    onClick={() => void bindItem(it.id)}
                  >
                    Привязать
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted">Очередь unsorted пуста.</p>
      )}
    </section>
  );
}
