"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

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

export function TestChatSettings() {
  const [data, setData] = useState<TestChat>({
    client_id: null,
    name: "Тестировочный",
    chat_id: null,
    channel_id: null,
  });
  const [name, setName] = useState("Тестировочный");
  const [chatId, setChatId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    const res = await fetch(`${getApiBase()}/api/v1/settings/test-chat`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const next: TestChat = await res.json();
    setData(next);
    setName(next.name || "Тестировочный");
    setChatId(next.chat_id || "");
  }, []);

  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Ошибка"));
  }, [load]);

  return (
    <section className="card-edit" style={{ marginBottom: "1rem" }}>
      <p className="muted hh-micro">
        Отдельный клиент для проверки бота и сценариев. Не показывается в обычном списке компаний
        в сайдбаре.
      </p>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      <div className="hh-inline-pair">
        <div className="hh-field">
          <label className="hh-label">Название</label>
          <input value={name} onChange={(e) => setName(e.target.value)} disabled={busy} />
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
      <div className="hh-row-actions" style={{ justifyContent: "flex-start" }}>
        <button
          type="button"
          className="chip chip-active"
          disabled={busy || !chatId.trim()}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            setMsg(null);
            try {
              const res = await fetch(`${getApiBase()}/api/v1/settings/test-chat`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: name.trim() || "Тестировочный", chat_id: chatId.trim() }),
              });
              const body = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(detailMessage(body, `HTTP ${res.status}`));
              setMsg("Тестировочный чат сохранён");
              await load();
            } catch (e) {
              setErr(e instanceof Error ? e.message : "Ошибка");
            } finally {
              setBusy(false);
            }
          }}
        >
          Сохранить
        </button>
        <button
          type="button"
          className="chip"
          disabled={busy || !chatId.trim()}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            setMsg(null);
            try {
              const res = await fetch(`${getApiBase()}/api/v1/messaging/test-message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ chat_id: chatId.trim() }),
              });
              const body = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(detailMessage(body, `HTTP ${res.status}`));
              setMsg(body.message || "Тест отправлен");
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
        <p className="muted hh-micro">Пока не настроен — укажите Chat ID группы с ботом.</p>
      )}
    </section>
  );
}
