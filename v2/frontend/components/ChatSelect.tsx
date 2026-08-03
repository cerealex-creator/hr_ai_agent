"use client";

import { useEffect, useMemo, useState } from "react";
import { getApiBase } from "@/lib/api";

export type ChatOption = {
  external_id: string;
  name: string;
};

type Props = {
  value: string;
  onChange: (chatId: string) => void;
  disabled?: boolean;
  id?: string;
};

/**
 * Display channel title (отдел) by default; Edit reveals select / chat_id input.
 */
export function ChatSelect({ value, onChange, disabled, id = "chat-select" }: Props) {
  const [channels, setChannels] = useState<ChatOption[]>([]);
  const [editing, setEditing] = useState(false);
  const [manual, setManual] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getApiBase()}/api/v1/messaging/channels`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const rows = (await res.json()) as {
          external_id: string;
          name?: string | null;
        }[];
        if (cancelled) return;
        const seen = new Set<string>();
        const opts: ChatOption[] = [];
        for (const r of rows) {
          const ext = String(r.external_id || "").trim();
          if (!ext || seen.has(ext) || ext.startsWith("__")) continue;
          seen.add(ext);
          opts.push({
            external_id: ext,
            name: (r.name || "").trim() || ext,
          });
        }
        opts.sort((a, b) => a.name.localeCompare(b.name, "ru"));
        setChannels(opts);
        const known = opts.some((o) => o.external_id === value);
        if (value && !known) setManual(true);
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [value]);

  const current = useMemo(
    () => channels.find((c) => c.external_id === value) || null,
    [channels, value],
  );
  const displayName = current?.name || (value ? `Чат ${value}` : "— не привязан —");

  if (!editing) {
    return (
      <div className="hh-field">
        <span className="hh-label">Telegram-чат (отдел)</span>
        <div
          className="hh-row-actions"
          style={{ justifyContent: "flex-start", flexWrap: "wrap", alignItems: "center" }}
        >
          <strong>{loaded ? displayName : "…"}</strong>
          <button
            type="button"
            className="chip"
            disabled={disabled}
            onClick={() => setEditing(true)}
          >
            Редактировать
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="hh-field">
      <label className="hh-label" htmlFor={id}>
        Telegram-чат (отдел)
      </label>
      {!manual ? (
        <select
          id={id}
          value={current ? value : ""}
          disabled={disabled || !loaded}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">— без чата —</option>
          {channels.map((c) => (
            <option key={c.external_id} value={c.external_id}>
              {c.name}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder="-100…"
        />
      )}
      <div className="hh-row-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
        <button
          type="button"
          className="chip"
          disabled={disabled}
          onClick={() => setManual((m) => !m)}
        >
          {manual ? "Выбрать из списка" : "Ввести chat_id вручную"}
        </button>
        <button
          type="button"
          className="chip chip-active"
          disabled={disabled}
          onClick={() => setEditing(false)}
        >
          Готово
        </button>
      </div>
      {!loaded ? <p className="muted hh-micro">Загрузка чатов…</p> : null}
      {loaded && !channels.length && !manual ? (
        <p className="muted hh-micro">
          Список пуст — синхронизируйте каналы в Настройках или введите chat_id вручную.
        </p>
      ) : null}
    </div>
  );
}
