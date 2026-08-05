"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { getApiBase } from "@/lib/api";

type DiskStatus = {
  connected: boolean;
  message: string;
  login?: string | null;
  root?: string;
  inbox_path?: string;
  authorize_url?: string | null;
  token_path?: string;
};

type UnsortedItem = {
  id: string;
  file_name: string;
  confidence?: string | null;
  vacancy_id?: number | null;
  extracted?: { full_name?: string; phone?: string; reason?: string };
  note?: string | null;
};

type VacancyOpt = { id: number; title: string };

export default function YandexDiskSettingsPage() {
  const [status, setStatus] = useState<DiskStatus | null>(null);
  const [token, setToken] = useState("");
  const [root, setRoot] = useState("/HR_AI_Agent");
  const [inbox, setInbox] = useState("_inbox");
  const [unsorted, setUnsorted] = useState<UnsortedItem[]>([]);
  const [inboxMsg, setInboxMsg] = useState("");
  const [processLog, setProcessLog] = useState<string[]>([]);
  const [vacancies, setVacancies] = useState<VacancyOpt[]>([]);
  const [bindVacancy, setBindVacancy] = useState<Record<string, string>>({});
  const [threshold, setThreshold] = useState(0.75);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadStatus = async () => {
    const res = await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/status`, {
      cache: "no-store",
    });
    const data = await res.json();
    setStatus(data);
    if (data.root) setRoot(data.root);
  };

  const loadInbox = async () => {
    const res = await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/inbox`, {
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
    setUnsorted(data.unsorted || []);
    setInboxMsg(data.message || "");
    if (data.settings?.confidence != null) setThreshold(Number(data.settings.confidence));
  };

  useEffect(() => {
    loadStatus().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
    fetch(`${getApiBase()}/api/v1/settings/app`)
      .then((r) => r.json())
      .then((d) => {
        if (d.yandex_disk_root) setRoot(d.yandex_disk_root);
        if (d.yandex_disk_inbox) setInbox(d.yandex_disk_inbox);
      })
      .catch(() => undefined);
    fetch(`${getApiBase()}/api/v1/vacancies?active=true`)
      .then((r) => r.json())
      .then((d) => {
        const items = (Array.isArray(d) ? d : d.items || []) as {
          id: number;
          title: string;
          active?: boolean;
        }[];
        setVacancies(items.map((v) => ({ id: v.id, title: v.title })));
      })
      .catch(() => undefined);
    loadInbox().catch(() => undefined);
  }, []);

  const saveToken = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setStatus(data);
      setToken("");
      setMsg(data.warning ? `Токен сохранён, но: ${data.warning}` : "Токен сохранён");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const savePaths = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/settings/app`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yandex_disk_root: root, yandex_disk_inbox: inbox }),
      });
      if (!res.ok) throw new Error("Не удалось сохранить пути");
      await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/ensure-root`, { method: "POST" });
      await loadStatus();
      setMsg("Пути сохранены");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const runRouter = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/inbox/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confidence: threshold }),
      });
      const res = await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/inbox/process`, {
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
      const res = await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/inbox/${id}/bind`, {
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
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Яндекс.Диск</h1>
      <p className="muted">
        OAuth → корень + inbox. Роутинг: ИИ читает PDF из <code>_inbox</code>, переносит в папку
        вакансии и создаёт кандидата (низкая уверенность → <code>_unsorted</code>).
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <section className="card-edit">
        <h2>Подключение</h2>
        {status ? (
          <p className={status.connected ? "ok" : "warn"}>
            {status.connected
              ? `Подключено${status.login ? `: ${status.login}` : ""}`
              : status.message}
          </p>
        ) : (
          <p className="muted">Загрузка…</p>
        )}
        {status?.authorize_url ? (
          <p>
            <a href={status.authorize_url} target="_blank" rel="noreferrer">
              Открыть авторизацию Яндекса →
            </a>
          </p>
        ) : null}
        <label className="hh-field">
          <span className="hh-label">OAuth access_token</span>
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            disabled={busy}
            placeholder="y0_…"
          />
        </label>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !token.trim()}
          onClick={saveToken}
        >
          Сохранить токен
        </button>
      </section>

      <section className="card-edit">
        <h2>Корень приложения</h2>
        <label className="hh-field">
          <span className="hh-label">Корневая папка</span>
          <input value={root} disabled={busy} onChange={(e) => setRoot(e.target.value)} />
        </label>
        <label className="hh-field">
          <span className="hh-label">Имя inbox</span>
          <input value={inbox} disabled={busy} onChange={(e) => setInbox(e.target.value)} />
        </label>
        <button type="button" className="chip chip-active" disabled={busy} onClick={savePaths}>
          Сохранить и создать папки
        </button>
      </section>

      <section className="card-edit">
        <h2>Inbox — ИИ-роутинг</h2>
        <p className="muted hh-micro">
          Кидайте любые PDF в <code>{status?.inbox_path || "/HR_AI_Agent/_inbox"}</code>. Имя файла
          не обязательно. Порог confidence ниже — в unsorted.
        </p>
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
          <button type="button" className="chip chip-active" disabled={busy} onClick={runRouter}>
            {busy ? "…" : "Запустить роутинг сейчас"}
          </button>
          <button type="button" className="chip" disabled={busy} onClick={() => loadInbox()}>
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
                      onClick={() => bindItem(it.id)}
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
    </AppShell>
  );
}
