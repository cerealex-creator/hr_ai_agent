"use client";

import { useCallback, useEffect, useState } from "react";
import { ChatIdField } from "@/components/ChatIdField";
import { InfoTip } from "@/components/InfoTip";
import { LockedTextField } from "@/components/LockedTextField";
import { apiFetch } from "@/lib/api";

type TestChat = {
  client_id: number | null;
  name: string | null;
  chat_id: string | null;
  channel_id: string | null;
};

function detailMessage(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const d = (data as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
  }
  return fallback;
}

type Props = {
  /** When true — no outer card (parent already wraps). */
  embedded?: boolean;
};

const DEFAULT_NAME = "Тестовый";

export function TestChatSettings({ embedded = false }: Props) {
  const [data, setData] = useState<TestChat>({
    client_id: null,
    name: null,
    chat_id: null,
    channel_id: null,
  });
  const [name, setName] = useState("");
  const [chatId, setChatId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    const res = await apiFetch(`/api/v1/settings/test-chat`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const next: TestChat = await res.json();
    setData(next);
    // Empty UI until user fills — only show saved values if already configured
    const savedName = (next.name || "").trim();
    const savedChat = (next.chat_id || "").trim();
    setName(savedName && savedChat ? savedName : "");
    setChatId(savedChat);
    setLoaded(true);
  }, []);

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [load]);

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await apiFetch(`/api/v1/settings/test-chat`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim() || DEFAULT_NAME,
          chat_id: chatId.trim(),
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(body, `HTTP ${res.status}`));
      setMsg("Тестовый чат сохранён");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка");
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const body = (
    <>
      <p className="muted hh-micro">
        Зачем: безопасно проверить бота, не писать реальному заказчику.{" "}
        <InfoTip text="1) Создайте в Telegram группу «Тестовый» (или любое имя). 2) Добавьте туда бота HR-помогатора и дайте ему право писать. 3) Узнайте Chat ID группы (часто начинается с -100…): перешлите сообщение из группы боту @userinfobot или посмотрите в логах. 4) Нажмите «Изменить» у названия и Chat ID, вставьте данные, «Ок», затем сохраните." />
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {!loaded ? (
        <p className="muted">Загрузка…</p>
      ) : (
        <>
          <div className="hh-inline-pair">
            <LockedTextField
              label="Название"
              tip={`Как будет называться тестовый клиент в системе. Можно оставить пример «${DEFAULT_NAME}».`}
              value={name}
              onChange={setName}
              disabled={busy}
              placeholder={DEFAULT_NAME}
              emptyLabel={`пример: ${DEFAULT_NAME}`}
            />
            <ChatIdField
              value={chatId}
              onChange={setChatId}
              disabled={busy}
              tip="ID тестовой группы Telegram с ботом. Нажмите «Изменить», вставьте число (часто -100…), «Ок»."
              onSave={save}
              saveDisabled={!chatId.trim()}
            />
          </div>
          <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="chip"
              disabled={busy || !chatId.trim()}
              onClick={async () => {
                setBusy(true);
                setErr(null);
                setMsg(null);
                try {
                  const res = await apiFetch(`/api/v1/messaging/test-message`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ chat_id: chatId.trim() }),
                  });
                  const bodyJson = await res.json().catch(() => ({}));
                  if (!res.ok) throw new Error(detailMessage(bodyJson, `HTTP ${res.status}`));
                  setMsg(bodyJson.message || "Тест отправлен");
                } catch (e) {
                  setErr(e instanceof Error ? e.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Отправить тест в чат
            </button>
          </div>
          {data.client_id ? (
            <p className="muted hh-micro" style={{ marginTop: "0.5rem" }}>
              Клиент #{data.client_id}
              {data.channel_id ? ` · канал ${data.channel_id.slice(0, 8)}…` : ""}
            </p>
          ) : (
            <p className="muted hh-micro">
              Пока пусто — укажите название (или оставьте «{DEFAULT_NAME}») и Chat ID группы с ботом.
            </p>
          )}
        </>
      )}
    </>
  );

  if (embedded) return <div>{body}</div>;
  return (
    <section className="card-edit" style={{ marginBottom: "1rem" }}>
      {body}
    </section>
  );
}
