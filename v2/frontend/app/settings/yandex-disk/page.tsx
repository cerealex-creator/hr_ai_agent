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
  token_from_env?: boolean;
};

type InboxItem = {
  name: string;
  suggested_vacancy_hint?: string;
  suggestion?: { vacancy_id: number; title: string; confidence: number } | null;
  needs_review?: boolean;
};

export default function YandexDiskSettingsPage() {
  const [status, setStatus] = useState<DiskStatus | null>(null);
  const [token, setToken] = useState("");
  const [root, setRoot] = useState("/HR_AI_Agent");
  const [inbox, setInbox] = useState("_inbox");
  const [inboxItems, setInboxItems] = useState<InboxItem[]>([]);
  const [inboxMsg, setInboxMsg] = useState("");
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
    if (data.inbox_path) {
      const name = String(data.inbox_path).split("/").filter(Boolean).pop();
      if (name) setInbox(name);
    }
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
      setMsg(data.warning ? `Токен сохранён, но: ${data.warning}` : "Токен сохранён, корень проверен");
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
      setMsg("Пути сохранены, папки проверены");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const loadInbox = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`${getApiBase()}/api/v1/integrations/yandex-disk/inbox`, {
        cache: "no-store",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
      setInboxItems(data.items || []);
      setInboxMsg(data.message || "");
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
        Один раз подключите Диск (OAuth-токен). Приложение создаст корневую папку и{" "}
        <code>_inbox</code>, а для вакансий — подпапки Резюме/Записи/Задания. Старый режим
        «публичная ссылка на папку» по-прежнему работает.
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
        <ol className="about-list">
          <li>
            Создайте приложение на{" "}
            <a href="https://oauth.yandex.ru/" target="_blank" rel="noreferrer">
              oauth.yandex.ru
            </a>{" "}
            с правами Disk.
          </li>
          <li>
            Получите OAuth-токен (или укажите{" "}
            <code>YANDEX_DISK_CLIENT_ID</code> в .env и откройте ссылку авторизации).
          </li>
          <li>Вставьте токен ниже — он сохранится в data/yandex_disk_oauth.json.</li>
        </ol>
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
        <div className="hh-footer-actions" style={{ justifyContent: "flex-start" }}>
          <button type="button" className="chip chip-active" disabled={busy || !token.trim()} onClick={saveToken}>
            Сохранить токен
          </button>
        </div>
        {status?.token_path ? (
          <p className="muted hh-micro">Файл токена: {status.token_path}</p>
        ) : null}
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
        <h2>Inbox (черновик L2)</h2>
        <p className="muted">
          Кладёте PDF в inbox как <code>НазваниеВакансии__ФИО.pdf</code> — система подскажет
          вакансию. Авто-перенос пока не включён.
        </p>
        <button type="button" className="chip" disabled={busy} onClick={loadInbox}>
          Показать очередь inbox
        </button>
        {inboxMsg ? <p className="muted">{inboxMsg}</p> : null}
        {inboxItems.length ? (
          <table>
            <thead>
              <tr>
                <th>Файл</th>
                <th>Подсказка</th>
                <th>Вакансия</th>
              </tr>
            </thead>
            <tbody>
              {inboxItems.map((it) => (
                <tr key={it.name}>
                  <td>{it.name}</td>
                  <td>{it.suggested_vacancy_hint || "—"}</td>
                  <td>
                    {it.suggestion
                      ? `${it.suggestion.title} (${Math.round(it.suggestion.confidence * 100)}%)`
                      : it.needs_review
                        ? "нужен разбор"
                        : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </AppShell>
  );
}
