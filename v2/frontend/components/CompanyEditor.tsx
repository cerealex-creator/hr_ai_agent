"use client";

import { useCallback, useEffect, useState } from "react";
import { ChatIdField } from "@/components/ChatIdField";
import { InfoTip } from "@/components/InfoTip";
import { LockedTextField } from "@/components/LockedTextField";
import { apiFetch } from "@/lib/api";
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
  const [zonePath, setZonePath] = useState<string | null>(null);
  const [deptDrafts, setDeptDrafts] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/v1/companies/${companyId}`, {
      cache: "no-store",
    });
    if (!res.ok) throw new Error(res.status === 404 ? "Компания не найдена" : `API ${res.status}`);
    const data: CompanyNode = await res.json();
    setCo(data);
    setRename(data.name);
    setChatName(data.channel?.name || data.name);
    setChatId(data.channel?.external_id || "");
    const drafts: Record<number, string> = {};
    for (const d of data.departments || []) {
      drafts[d.id] = d.channel?.external_id || "";
    }
    setDeptDrafts(drafts);
    const token = (data as { client_zone_token?: string | null }).client_zone_token;
    setZonePath(token ? `/c/${token}` : null);
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
        <h2>
          Название{" "}
          <InfoTip text="Имя заказчика в списках. Можно переименовать в любой момент." />
        </h2>
        <LockedTextField
          label="Компания"
          value={rename}
          onChange={setRename}
          disabled={busy}
          onConfirm={(next) =>
            run(async () => {
              if (!next.trim() || next.trim() === co.name) return;
              const res = await apiFetch(`/api/v1/clients/${co.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: next.trim() }),
              });
              const data = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
              setMsg("Название сохранено");
              await load();
            })
          }
          confirmDisabled={!rename.trim() || rename.trim() === co.name}
        />
      </section>

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>
          Клиентская зона (веб){" "}
          <InfoTip text="Секретная ссылка для заказчика без логина: он видит только кандидатов своей компании. Один токен на компанию (включая подразделения)." />
        </h2>
        <p className="muted hh-micro">
          Отдайте ссылку заказчику. При сбросе старая ссылка перестаёт работать.
        </p>
        {zonePath ? (
          <p style={{ wordBreak: "break-all" }}>
            <a href={zonePath} target="_blank" rel="noreferrer">
              {typeof window !== "undefined" ? `${window.location.origin}${zonePath}` : zonePath}
            </a>
          </p>
        ) : (
          <p className="muted">Ссылка ещё не создана.</p>
        )}
        <div className="chip-row" style={{ marginTop: "0.5rem" }}>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const res = await apiFetch(`/api/v1/companies/${co.id}/client-zone/rotate`, {
                  method: "POST",
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                const path = typeof data.path === "string" ? data.path : null;
                setZonePath(path);
                setMsg(path ? "Ссылка клиентской зоны обновлена" : "Токен сброшен");
                await load();
              })
            }
          >
            {zonePath ? "Сбросить и выдать новую ссылку" : "Создать ссылку"}
          </button>
        </div>
      </section>

      <section className="card-edit" style={{ marginBottom: "1rem" }}>
        <h2>
          Как устроены чаты?{" "}
          <InfoTip text="Один чат — всё в одной группе. По подразделениям — у каждого отдела свой чат. Без подразделений вакансии остаются на уровне компании." />
        </h2>
        <p className="muted hh-micro">Сейчас: {companyModeLabel(co.chat_mode)}.</p>
        <div className="chip-row">
          <button
            type="button"
            className={co.chat_mode === "company" ? "chip chip-active" : "chip"}
            disabled={busy}
            onClick={() =>
              run(async () => {
                const res = await apiFetch(`/api/v1/clients/${co.id}`, {
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
                const res = await apiFetch(`/api/v1/clients/${co.id}`, {
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
          <h2>
            Общий чат компании{" "}
            <InfoTip text="Telegram-группа заказчика, куда бот публикует карточки кандидатов. Сначала добавьте бота в группу, затем укажите Chat ID." />
          </h2>
          <div className="hh-inline-pair">
            <LockedTextField
              label="Название чата"
              tip="Как чат подписан в системе (можно совпадать с названием компании)."
              value={chatName}
              onChange={setChatName}
              disabled={busy}
            />
            <ChatIdField
              value={chatId}
              onChange={setChatId}
              disabled={busy}
              onSave={() =>
                run(async () => {
                  if (!chatId.trim()) throw new Error("Укажите Chat ID");
                  const payload = {
                    name: chatName.trim() || co.name,
                    chat_id: chatId.trim(),
                    client_id: co.id,
                  };
                  const path = co.channel
                    ? `/api/v1/messaging/channels/${co.channel.id}`
                    : `/api/v1/messaging/channels`;
                  const res = await apiFetch(path, {
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
              saveDisabled={!chatId.trim()}
            />
          </div>
          {co.channel ? (
            <p className="muted hh-micro" style={{ marginTop: "0.5rem" }}>
              Сейчас: {co.channel.name}
            </p>
          ) : null}
        </section>
      ) : (
        <section className="card-edit" style={{ marginBottom: "1rem" }}>
          <h2>
            Подразделения и чаты{" "}
            <InfoTip text="Подразделение — место, куда ищете сотрудников (куда создаются вакансии). У каждого может быть свой чат. Если подразделение не создаёте — вакансии остаются на компании (смените режим на «один чат»)." />
          </h2>
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
                    <ChatIdField
                      value={deptDrafts[d.id] ?? ""}
                      onChange={(v) => setDeptDrafts((prev) => ({ ...prev, [d.id]: v }))}
                      disabled={busy}
                      label=""
                      tip="ID Telegram-группы этого подразделения. Нажмите «Изменить», введите ID, затем «Ок»."
                      onSave={() =>
                        run(async () => {
                          const nextId = (deptDrafts[d.id] || "").trim();
                          if (!nextId) throw new Error("Укажите Chat ID");
                          if (d.channel) {
                            const res = await apiFetch(`/api/v1/messaging/channels/${d.channel.id}`, {
                              method: "PATCH",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({
                                chat_id: nextId,
                                name: d.channel.name || d.name,
                                client_id: d.id,
                              }),
                            });
                            const data = await res.json().catch(() => ({}));
                            if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                          } else {
                            const res = await apiFetch(`/api/v1/messaging/channels`, {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({
                                name: d.name,
                                chat_id: nextId,
                                client_id: d.id,
                              }),
                            });
                            const data = await res.json().catch(() => ({}));
                            if (!res.ok) throw new Error(detailMessage(data, `HTTP ${res.status}`));
                          }
                          setMsg(`Чат «${d.name}» сохранён`);
                          await load();
                        })
                      }
                      saveDisabled={!(deptDrafts[d.id] || "").trim()}
                    />
                  </td>
                </tr>
              ))}
              {!co.departments.length ? (
                <tr>
                  <td colSpan={3}>Нет подразделений — добавьте ниже, если нужны отдельные направления</td>
                </tr>
              ) : null}
            </tbody>
          </table>

          <h3 className="hh-subhead" style={{ marginTop: "1rem" }}>
            Добавить подразделение{" "}
            <InfoTip text="Пример названий: Отдел продаж, Бухгалтерия, Склад. Не обязательно — без них вакансии можно вести на уровне компании." />
          </h3>
          <div className="hh-inline-pair">
            <div className="hh-field">
              <label className="hh-label">Название</label>
              <input
                value={deptName}
                onChange={(e) => setDeptName(e.target.value)}
                disabled={busy}
                placeholder="Отдел 1, Бухгалтерия…"
              />
            </div>
            <ChatIdField
              value={deptChatId}
              onChange={setDeptChatId}
              disabled={busy}
              label="Chat ID (необяз.)"
              tip="Можно указать сразу или позже через «Изменить» в таблице."
              lockable={false}
            />
          </div>
          <button
            type="button"
            className="chip chip-active"
            disabled={busy || !deptName.trim()}
            onClick={() =>
              run(async () => {
                const res = await apiFetch(`/api/v1/companies/${co.id}/departments`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    name: deptName.trim(),
                    chat_id: deptChatId.trim() || null,
                    chat_name: deptName.trim(),
                  }),
                });
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
