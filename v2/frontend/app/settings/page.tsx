"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AppearanceSettings } from "@/components/AppearanceSettings";
import { getApiBase, type ClientItem } from "@/lib/api";

type MessagingStatus = {
  outbound_enabled: boolean;
  inbound_enabled: boolean;
  poll_enabled: boolean;
  token_configured: boolean;
  hr_user_id?: string | null;
  bot_ok: boolean;
  bot_message: string;
  bot?: { username?: string; id?: number; first_name?: string };
  note?: string;
};

type Channel = {
  id: string;
  provider: string;
  external_id: string;
  client_id: number | null;
  name: string | null;
  metadata: Record<string, unknown>;
};

type CalendarStatus = {
  status: string;
  message: string;
  credentials_path: string;
  token_path: string;
};

type AppSettings = {
  default_warranty_months: number;
  path: string;
};

const NEW_CLIENT = "__new__";

function channelLabel(ch: Channel): string {
  const name = (ch.name || "").trim();
  return name || ch.external_id;
}

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

export default function SettingsPage() {
  const [status, setStatus] = useState<MessagingStatus | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [calendar, setCalendar] = useState<CalendarStatus | null>(null);
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null);
  const [testChatId, setTestChatId] = useState("");
  const [instructionChatId, setInstructionChatId] = useState("");
  const [newChatName, setNewChatName] = useState("");
  const [newChatId, setNewChatId] = useState("");
  const [newDeptChoice, setNewDeptChoice] = useState("");
  const [newDeptName, setNewDeptName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editChatId, setEditChatId] = useState("");
  const [oauthUrl, setOauthUrl] = useState<string | null>(null);
  const [oauthCode, setOauthCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const clientName = useMemo(() => {
    const map = new Map(clients.map((c) => [c.id, c.name]));
    return (id: number | null) => (id != null ? map.get(id) || `Клиент #${id}` : "—");
  }, [clients]);

  const load = async () => {
    const [st, ch, cl, cal, app] = await Promise.all([
      fetch(`${getApiBase()}/api/v1/messaging/status`).then((r) => r.json()),
      fetch(`${getApiBase()}/api/v1/messaging/channels`).then((r) => r.json()),
      fetch(`${getApiBase()}/api/v1/clients`).then((r) => r.json()),
      fetch(`${getApiBase()}/api/v1/integrations/google-calendar/status`).then((r) => r.json()),
      fetch(`${getApiBase()}/api/v1/settings/app`).then((r) => r.json()),
    ]);
    const list = (Array.isArray(ch) ? ch : []) as Channel[];
    setStatus(st);
    setChannels(list);
    setClients(cl);
    setCalendar(cal);
    setAppSettings(app);
    setTestChatId((prev) =>
      prev && list.some((c) => c.external_id === prev) ? prev : list[0]?.external_id || "",
    );
    setInstructionChatId((prev) =>
      prev && list.some((c) => c.external_id === prev) ? prev : list[0]?.external_id || "",
    );
  };

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (ch: Channel) => {
    setEditingId(ch.id);
    setEditName(ch.name || "");
    setEditChatId(ch.external_id);
  };

  return (
    <AppShell activePath="/settings">
      <h1 className="page-title">Настройки</h1>
      <AppearanceSettings />
      <p className="muted">Telegram-каналы, инструкция заказчику, Google Calendar, гарантия.</p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>Telegram bot</h2>
        {status ? (
          <>
            <p className="muted hh-micro">{status.note}</p>
            <ul className="muted" style={{ paddingLeft: "1.1rem" }}>
              <li>
                Бот:{" "}
                {status.bot_ok
                  ? `@${status.bot?.username || "?"} (id ${status.bot?.id || "—"})`
                  : status.bot_message}
              </li>
              <li>Outbound: {status.outbound_enabled ? "on" : "off"}</li>
              <li>Inbound: {status.inbound_enabled ? "on" : "off"}</li>
              <li>Poll: {status.poll_enabled ? "on" : "off"}</li>
              <li>HR user id: {status.hr_user_id || "— (TELEGRAM_HR_USER_ID)"}</li>
            </ul>
          </>
        ) : (
          <p className="muted">Загрузка…</p>
        )}
        <div className="hh-field" style={{ marginTop: "0.75rem" }}>
          <label className="hh-label">Тестовое сообщение → чат</label>
          <select
            value={testChatId}
            onChange={(e) => setTestChatId(e.target.value)}
            disabled={busy || !channels.length}
          >
            {!channels.length ? <option value="">Нет чатов</option> : null}
            {channels.map((ch) => (
              <option key={ch.id} value={ch.external_id}>
                {channelLabel(ch)}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !testChatId.trim()}
          style={{ marginTop: "0.35rem" }}
          onClick={() =>
            run(async () => {
              const res = await fetch(`${getApiBase()}/api/v1/messaging/test-message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chat_id: testChatId.trim() }),
              });
              const data = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
              setMsg(data.message || "Отправлено");
            })
          }
        >
          Отправить тест
        </button>
      </section>

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>Мои чаты Telegram</h2>
        <p className="muted hh-micro">
          Новый чат: создайте группу → добавьте бота → <code>/chatid</code> в группе → сохраните
          здесь. При сохранении chat_id вакансий выбранного подразделения выравнивается.
        </p>

        <div className="hh-inline-pair" style={{ marginTop: "0.75rem" }}>
          <div className="hh-field">
            <label className="hh-label">Название чата</label>
            <input
              value={newChatName}
              onChange={(e) => setNewChatName(e.target.value)}
              disabled={busy}
              placeholder="Маркетинг · заказчик"
            />
          </div>
          <div className="hh-field">
            <label className="hh-label">Chat ID</label>
            <input
              value={newChatId}
              onChange={(e) => setNewChatId(e.target.value)}
              disabled={busy}
              placeholder="-100…"
            />
          </div>
        </div>
        <div className="hh-field">
          <label className="hh-label">Подразделение</label>
          <select
            value={newDeptChoice}
            onChange={(e) => setNewDeptChoice(e.target.value)}
            disabled={busy}
          >
            <option value="">— без привязки —</option>
            {clients.map((c) => (
              <option key={c.id} value={String(c.id)}>
                {c.name}
              </option>
            ))}
            <option value={NEW_CLIENT}>➕ Создать новое…</option>
          </select>
        </div>
        {newDeptChoice === NEW_CLIENT ? (
          <div className="hh-field">
            <label className="hh-label">Название нового подразделения</label>
            <input
              value={newDeptName}
              onChange={(e) => setNewDeptName(e.target.value)}
              disabled={busy}
            />
          </div>
        ) : null}
        <div className="hh-row-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy || !newChatName.trim() || !newChatId.trim()}
            onClick={() =>
              run(async () => {
                if (newDeptChoice === NEW_CLIENT && !newDeptName.trim()) {
                  throw new Error("Введите название нового подразделения");
                }
                const payload: Record<string, unknown> = {
                  name: newChatName.trim(),
                  chat_id: newChatId.trim(),
                };
                if (newDeptChoice === NEW_CLIENT) {
                  payload.new_client_name = newDeptName.trim();
                } else if (newDeptChoice) {
                  payload.client_id = Number(newDeptChoice);
                }
                const res = await fetch(`${getApiBase()}/api/v1/messaging/channels`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(payload),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setNewChatName("");
                setNewChatId("");
                setNewDeptChoice("");
                setNewDeptName("");
                setMsg("Чат сохранён");
                await load();
              })
            }
          >
            Сохранить чат
          </button>
          <button
            type="button"
            className="chip"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const res = await fetch(`${getApiBase()}/api/v1/messaging/channels/sync`, {
                  method: "POST",
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setMsg(
                  `Синхронизация: +${data.created || 0} / upd ${data.updated || 0} / skip ${data.skipped_no_chat || 0}`,
                );
                await load();
              })
            }
          >
            Синхронизировать из вакансий
          </button>
        </div>

        <table style={{ marginTop: "0.75rem" }}>
          <thead>
            <tr>
              <th>Имя</th>
              <th>chat_id</th>
              <th>Подразделение</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {channels.map((ch) => (
              <tr key={ch.id}>
                <td>
                  {editingId === ch.id ? (
                    <input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      disabled={busy}
                    />
                  ) : (
                    channelLabel(ch)
                  )}
                </td>
                <td>
                  {editingId === ch.id ? (
                    <input
                      value={editChatId}
                      onChange={(e) => setEditChatId(e.target.value)}
                      disabled={busy}
                    />
                  ) : (
                    <code>{ch.external_id}</code>
                  )}
                </td>
                <td>
                  {editingId === ch.id ? (
                    <select
                      value={ch.client_id != null ? String(ch.client_id) : ""}
                      disabled={busy}
                      onChange={(e) =>
                        run(async () => {
                          const val = e.target.value;
                          const res = await fetch(
                            `${getApiBase()}/api/v1/messaging/channels/${ch.id}`,
                            {
                              method: "PATCH",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify(
                                val
                                  ? { client_id: Number(val) }
                                  : { clear_client: true },
                              ),
                            },
                          );
                          const data = await res.json().catch(() => ({}));
                          if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                          setMsg("Подразделение обновлено");
                          await load();
                        })
                      }
                    >
                      <option value="">—</option>
                      {clients.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    clientName(ch.client_id)
                  )}
                </td>
                <td>
                  <div className="hh-row-actions" style={{ justifyContent: "flex-end", flexWrap: "wrap" }}>
                    {editingId === ch.id ? (
                      <>
                        <button
                          type="button"
                          className="chip chip-active"
                          disabled={busy || !editName.trim() || !editChatId.trim()}
                          onClick={() =>
                            run(async () => {
                              const res = await fetch(
                                `${getApiBase()}/api/v1/messaging/channels/${ch.id}`,
                                {
                                  method: "PATCH",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({
                                    name: editName.trim(),
                                    chat_id: editChatId.trim(),
                                  }),
                                },
                              );
                              const data = await res.json().catch(() => ({}));
                              if (!res.ok) {
                                throw new Error(detailMessage(data, `HTTP ${res.status}`));
                              }
                              setEditingId(null);
                              setMsg("Чат обновлён");
                              await load();
                            })
                          }
                        >
                          Сохранить
                        </button>
                        <button
                          type="button"
                          className="chip"
                          disabled={busy}
                          onClick={() => setEditingId(null)}
                        >
                          Отмена
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="chip"
                          disabled={busy}
                          onClick={() => startEdit(ch)}
                        >
                          Переименовать
                        </button>
                        <button
                          type="button"
                          className="chip"
                          disabled={busy}
                          onClick={() =>
                            run(async () => {
                              if (
                                !window.confirm(
                                  `Удалить чат «${channelLabel(ch)}»? Карточки в этом чате будут отвязаны в БД.`,
                                )
                              ) {
                                return;
                              }
                              const res = await fetch(
                                `${getApiBase()}/api/v1/messaging/channels/${ch.id}`,
                                { method: "DELETE" },
                              );
                              const data = await res.json().catch(() => ({}));
                              if (!res.ok) {
                                throw new Error(detailMessage(data, `HTTP ${res.status}`));
                              }
                              setMsg("Чат удалён");
                              await load();
                            })
                          }
                        >
                          Удалить
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!channels.length ? (
              <tr>
                <td colSpan={4}>Нет чатов — сохраните первый выше или синхронизируйте из вакансий</td>
              </tr>
            ) : null}
          </tbody>
        </table>

        <div className="hh-field" style={{ marginTop: "0.75rem" }}>
          <label className="hh-label">Инструкция заказчику → чат</label>
          <select
            value={instructionChatId}
            onChange={(e) => setInstructionChatId(e.target.value)}
            disabled={busy || !channels.length}
          >
            {!channels.length ? <option value="">Нет чатов</option> : null}
            {channels.map((ch) => (
              <option key={`instr-${ch.id}`} value={ch.external_id}>
                {channelLabel(ch)}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="chip"
            disabled={busy || !instructionChatId.trim()}
            style={{ marginTop: "0.35rem" }}
            onClick={() =>
              run(async () => {
                const res = await fetch(`${getApiBase()}/api/v1/messaging/send-instruction`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ chat_id: instructionChatId.trim() }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setMsg(data.message || "Инструкция отправлена");
              })
            }
          >
            Отправить инструкцию
          </button>
        </div>
      </section>

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>Google Calendar</h2>
        {calendar ? (
          <p className="muted">
            {calendar.status}: {calendar.message}
            <br />
            <span className="hh-micro">
              credentials: {calendar.credentials_path}
              <br />
              token: {calendar.token_path}
            </span>
          </p>
        ) : null}
        <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const res = await fetch(
                  `${getApiBase()}/api/v1/integrations/google-calendar/oauth/start`,
                  { method: "POST" },
                );
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setOauthUrl(data.auth_url || null);
                setMsg(data.message || "Откройте ссылку");
              })
            }
          >
            Получить ссылку OAuth
          </button>
        </div>
        {oauthUrl ? (
          <p className="muted hh-micro" style={{ wordBreak: "break-all" }}>
            <a href={oauthUrl} target="_blank" rel="noreferrer">
              {oauthUrl}
            </a>
          </p>
        ) : null}
        <p className="muted hh-micro">
          Если ссылка «не открывается» — скопируйте её целиком из поля выше в новую вкладку.
          После Google скопируйте <b>весь</b> адрес из строки браузера (
          <code>http://localhost:8765/?code=...</code>) или только значение после{" "}
          <code>code=</code> (начинается с <code>4/</code>). Код одноразовый: при ошибке снова
          нажмите «Получить ссылку OAuth».
        </p>
        <div className="hh-field">
          <label className="hh-label">Вставьте redirect URL или code=</label>
          <textarea
            rows={2}
            value={oauthCode}
            onChange={(e) => setOauthCode(e.target.value)}
            disabled={busy}
          />
          <button
            type="button"
            className="chip"
            disabled={busy || !oauthCode.trim()}
            style={{ marginTop: "0.35rem" }}
            onClick={() =>
              run(async () => {
                const res = await fetch(
                  `${getApiBase()}/api/v1/integrations/google-calendar/oauth/complete`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ code: oauthCode.trim() }),
                  },
                );
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setMsg(data.message || "OK");
                setOauthCode("");
                await load();
              })
            }
          >
            Завершить OAuth
          </button>
        </div>
      </section>

      <section className="card-edit">
        <h2>Гарантия по умолчанию</h2>
        {appSettings ? (
          <div className="hh-field">
            <label className="hh-label">Срок (месяцев)</label>
            <select
              value={appSettings.default_warranty_months}
              disabled={busy}
              onChange={(e) =>
                run(async () => {
                  const res = await fetch(`${getApiBase()}/api/v1/settings/app`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      default_warranty_months: Number(e.target.value),
                    }),
                  });
                  const data = await res.json().catch(() => ({}));
                  if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                  setAppSettings(data);
                  setMsg("Сохранено");
                })
              }
            >
              {[1, 2, 3, 4, 5, 6].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <p className="muted hh-micro">Файл: {appSettings.path}</p>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
