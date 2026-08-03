"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import {
  companyModeLabel,
  detailMessage,
  type CompanyNode,
} from "@/lib/companies";

type Props = {
  companyId: number;
  onRenamed?: (name: string) => void;
};

export function CompanyEditor({ companyId, onRenamed }: Props) {
  const [co, setCo] = useState<CompanyNode | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [rename, setRename] = useState("");
  const [deptName, setDeptName] = useState("");
  const [deptChatId, setDeptChatId] = useState("");
  const [chatName, setChatName] = useState("");
  const [chatId, setChatId] = useState("");

  const load = useCallback(async () => {
    const res = await fetch(`${getApiBase()}/api/v1/companies/${companyId}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error(res.status === 404 ? "Компания не найдена" : `API ${res.status}`);
    const data: CompanyNode = await res.json();
    setCo(data);
    setRename(data.name);
    setChatName(data.channel?.name || data.name);
    setChatId(data.channel?.external_id || "");
    onRenamed?.(data.name);
  }, [companyId, onRenamed]);

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка загрузки"));
  }, [load]);

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

  if (!co && !err) return <p className="muted">Загрузка…</p>;
  if (!co) return err ? <p className="warn">{err}</p> : null;

  return (
    <div className="company-editor">
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>Название</h2>
        <div className="hh-inline-pair">
          <div className="hh-field">
            <label className="hh-label">Компания</label>
            <input value={rename} onChange={(e) => setRename(e.target.value)} disabled={busy} />
          </div>
        </div>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !rename.trim() || rename.trim() === co.name}
          onClick={() =>
            run(async () => {
              const res = await fetch(`${getApiBase()}/api/v1/clients/${co.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: rename.trim() }),
              });
              const data = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
              setMsg("Название сохранено");
              await load();
            })
          }
        >
          Сохранить название
        </button>
      </section>

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>Как устроены чаты?</h2>
        <p className="muted hh-micro">Сейчас: {companyModeLabel(co.chat_mode)}.</p>
        <div className="chip-row">
          <button
            type="button"
            className={co.chat_mode === "company" ? "chip chip-active" : "chip"}
            disabled={busy}
            onClick={() =>
              run(async () => {
                const res = await fetch(`${getApiBase()}/api/v1/clients/${co.id}`, {
                  method: "PATCH",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ chat_mode: "company" }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setMsg("Режим: один чат на компанию");
                await load();
              })
            }
          >
            Один чат на компанию
          </button>
          <button
            type="button"
            className={co.chat_mode === "departments" ? "chip chip-active" : "chip"}
            disabled={busy}
            onClick={() =>
              run(async () => {
                const res = await fetch(`${getApiBase()}/api/v1/clients/${co.id}`, {
                  method: "PATCH",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ chat_mode: "departments" }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setMsg("Режим: чаты по подразделениям");
                await load();
              })
            }
          >
            Чаты по подразделениям
          </button>
        </div>
      </section>

      {co.chat_mode === "company" ? (
        <section className="card-edit" style={{ marginBottom: "1rem" }}>
          <h2>Общий чат компании</h2>
          <div className="hh-inline-pair">
            <div className="hh-field">
              <label className="hh-label">Название чата</label>
              <input value={chatName} onChange={(e) => setChatName(e.target.value)} disabled={busy} />
            </div>
            <div className="hh-field">
              <label className="hh-label">Chat ID</label>
              <input
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                disabled={busy}
                placeholder="-100…"
              />
            </div>
          </div>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy || !chatId.trim()}
            onClick={() =>
              run(async () => {
                const payload = {
                  name: chatName.trim() || co.name,
                  chat_id: chatId.trim(),
                  client_id: co.id,
                };
                const url = co.channel
                  ? `${getApiBase()}/api/v1/messaging/channels/${co.channel.id}`
                  : `${getApiBase()}/api/v1/messaging/channels`;
                const res = await fetch(url, {
                  method: co.channel ? "PATCH" : "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(
                    co.channel
                      ? { name: payload.name, chat_id: payload.chat_id, client_id: co.id }
                      : payload,
                  ),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setMsg("Чат компании сохранён");
                await load();
              })
            }
          >
            Сохранить чат
          </button>
          {co.channel ? (
            <p className="muted hh-micro" style={{ marginTop: "0.5rem" }}>
              Сейчас: {co.channel.name} · <code>{co.channel.external_id}</code>
            </p>
          ) : null}
        </section>
      ) : (
        <section className="card-edit" style={{ marginBottom: "1rem" }}>
          <h2>Подразделения и чаты</h2>
          <table>
            <thead>
              <tr>
                <th>Подразделение</th>
                <th>Чат</th>
                <th>Chat ID</th>
              </tr>
            </thead>
            <tbody>
              {co.departments.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.channel?.name || "—"}</td>
                  <td>
                    <div className="hh-inline-pair" style={{ alignItems: "center" }}>
                      <input
                        defaultValue={d.channel?.external_id || ""}
                        placeholder="-100…"
                        id={`dept-chat-${d.id}`}
                        disabled={busy}
                        style={{ minWidth: 140 }}
                      />
                      <button
                        type="button"
                        className="chip"
                        disabled={busy}
                        onClick={() =>
                          run(async () => {
                            const el = document.getElementById(
                              `dept-chat-${d.id}`,
                            ) as HTMLInputElement | null;
                            const nextId = (el?.value || "").trim();
                            if (!nextId) throw new Error("Укажите Chat ID");
                            if (d.channel) {
                              const res = await fetch(
                                `${getApiBase()}/api/v1/messaging/channels/${d.channel.id}`,
                                {
                                  method: "PATCH",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({
                                    chat_id: nextId,
                                    name: d.channel.name || d.name,
                                    client_id: d.id,
                                  }),
                                },
                              );
                              const data = await res.json().catch(() => ({}));
                              if (!res.ok)
                                throw new Error(detailMessage(data, `HTTP ${res.status}`));
                            } else {
                              const res = await fetch(
                                `${getApiBase()}/api/v1/messaging/channels`,
                                {
                                  method: "POST",
                                  headers: { "Content-Type": "application/json" },
                                  body: JSON.stringify({
                                    name: d.name,
                                    chat_id: nextId,
                                    client_id: d.id,
                                  }),
                                },
                              );
                              const data = await res.json().catch(() => ({}));
                              if (!res.ok)
                                throw new Error(detailMessage(data, `HTTP ${res.status}`));
                            }
                            setMsg(`Чат «${d.name}» сохранён`);
                            await load();
                          })
                        }
                      >
                        OK
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!co.departments.length ? (
                <tr>
                  <td colSpan={3}>Нет подразделений</td>
                </tr>
              ) : null}
            </tbody>
          </table>

          <h3 className="hh-subhead" style={{ marginTop: "1rem" }}>
            Добавить подразделение
          </h3>
          <div className="hh-inline-pair">
            <div className="hh-field">
              <label className="hh-label">Название</label>
              <input
                value={deptName}
                onChange={(e) => setDeptName(e.target.value)}
                disabled={busy}
              />
            </div>
            <div className="hh-field">
              <label className="hh-label">Chat ID (необяз.)</label>
              <input
                value={deptChatId}
                onChange={(e) => setDeptChatId(e.target.value)}
                disabled={busy}
                placeholder="-100…"
              />
            </div>
          </div>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy || !deptName.trim()}
            onClick={() =>
              run(async () => {
                const res = await fetch(
                  `${getApiBase()}/api/v1/companies/${co.id}/departments`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      name: deptName.trim(),
                      chat_id: deptChatId.trim() || null,
                      chat_name: deptName.trim(),
                    }),
                  },
                );
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                setDeptName("");
                setDeptChatId("");
                setMsg("Подразделение добавлено");
                await load();
              })
            }
          >
            Добавить
          </button>
        </section>
      )}
    </div>
  );
}
