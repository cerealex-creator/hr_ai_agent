"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RecruitingShell } from "@/components/RecruitingShell";
import { OwnerOnly } from "@/components/AuthGate";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { type ClientItem, apiFetch } from "@/lib/api";

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

export default function TelegramSettingsPage() {
  const [status, setStatus] = useState<MessagingStatus | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [testChatId, setTestChatId] = useState("");
  const [instructionChatId, setInstructionChatId] = useState("");
  const [newChatName, setNewChatName] = useState("");
  const [newChatId, setNewChatId] = useState("");
  const [newDeptChoice, setNewDeptChoice] = useState("");
  const [newDeptName, setNewDeptName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editChatId, setEditChatId] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const clientName = useMemo(() => {
    const map = new Map(clients.map((c) => [c.id, c.name]));
    return (id: number | null) => (id != null ? map.get(id) || `Клиент #${id}` : "—");
  }, [clients]);

  const load = async () => {
    const [st, ch, cl] = await Promise.all([
      apiFetch(`/api/v1/messaging/status`).then((r) => r.json()),
      apiFetch(`/api/v1/messaging/channels`).then((r) => r.json()),
      apiFetch(`/api/v1/clients`).then((r) => r.json()),
    ]);
    const list = (Array.isArray(ch) ? ch : []) as Channel[];
    setStatus(st);
    setChannels(list);
    setClients(cl);
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

  return (
    <OwnerOnly>
    <RecruitingShell activePath="/settings" title="Настройки">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Telegram</h1>
      <p className="muted">
        Статус бота и каналы.         Компании удобнее настраивать в{" "}
        <Link href="/settings/companies">Настройке взаимодействия</Link>.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <CollapsibleCard
        title="Статус бота"
        hint={
          status?.bot_ok
            ? `@${status.bot?.username || "?"}`
            : status
              ? "ошибка / не настроен"
              : "…"
        }
        defaultOpen={false}
      >
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
          <label className="hh-label">Быстрый тест → чат</label>
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
              const res = await apiFetch(`/api/v1/messaging/test-message`, {
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
      </CollapsibleCard>

      <CollapsibleCard
        title="Каналы"
        hint={`${channels.length} шт.`}
        defaultOpen={false}
      >
        <p className="muted hh-micro">
          Новый чат: группа → бот → <code>/chatid</code> → сохраните. Для отделов предпочтительнее
          страница компании.
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
          <label className="hh-label">Привязка к клиенту</label>
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
            <label className="hh-label">Название</label>
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
                  throw new Error("Введите название");
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
                const res = await apiFetch(`/api/v1/messaging/channels`, {
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
                const res = await apiFetch(`/api/v1/messaging/channels/sync`, {
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
              <th>Клиент</th>
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
                          const res = await apiFetch(`/api/v1/messaging/channels/${ch.id}`,
                            {
                              method: "PATCH",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify(
                                val ? { client_id: Number(val) } : { clear_client: true },
                              ),
                            },
                          );
                          const data = await res.json().catch(() => ({}));
                          if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                          setMsg("Привязка обновлена");
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
                  <div
                    className="hh-row-actions"
                    style={{ justifyContent: "flex-end", flexWrap: "wrap" }}
                  >
                    {editingId === ch.id ? (
                      <>
                        <button
                          type="button"
                          className="chip chip-active"
                          disabled={busy || !editName.trim() || !editChatId.trim()}
                          onClick={() =>
                            run(async () => {
                              const res = await apiFetch(`/api/v1/messaging/channels/${ch.id}`,
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
                          onClick={() => {
                            setEditingId(ch.id);
                            setEditName(ch.name || "");
                            setEditChatId(ch.external_id);
                          }}
                        >
                          Изменить
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
                              const res = await apiFetch(`/api/v1/messaging/channels/${ch.id}`,
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
                <td colSpan={4}>Нет чатов</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </CollapsibleCard>

      <CollapsibleCard title="Инструкция заказчику" hint="отправка в чат" defaultOpen={false}>
        <div className="hh-field">
          <label className="hh-label">Чат</label>
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
            className="chip chip-active"
            disabled={busy || !instructionChatId.trim()}
            style={{ marginTop: "0.35rem" }}
            onClick={() =>
              run(async () => {
                const res = await apiFetch(`/api/v1/messaging/send-instruction`, {
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
      </CollapsibleCard>
    </RecruitingShell>
    </OwnerOnly>
  );
}
