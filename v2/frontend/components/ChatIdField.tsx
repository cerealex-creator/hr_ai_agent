"use client";

import { useState } from "react";
import { InfoTip } from "@/components/InfoTip";

type Props = {
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  placeholder?: string;
  label?: string;
  tip?: string;
  /** When true, show locked view until «Изменить». */
  lockable?: boolean;
  onSave?: () => void | Promise<void>;
  saveDisabled?: boolean;
  saveLabel?: string;
};

/** Chat ID field: locked by default, edit via button, OK only while editing. */
export function ChatIdField({
  value,
  onChange,
  disabled = false,
  placeholder = "-100…",
  label = "Chat ID",
  tip = "Числовой ID чата Telegram (часто начинается с -100). Узнать: добавьте бота в группу → перешлите любое сообщение @userinfobot или смотрите в логах бота.",
  lockable = true,
  onSave,
  saveDisabled = false,
  saveLabel = "Ок",
}: Props) {
  const [editing, setEditing] = useState(false);

  if (!lockable) {
    return (
      <div className="hh-field">
        <label className="hh-label">
          {label} <InfoTip text={tip} />
        </label>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder={placeholder}
        />
      </div>
    );
  }

  if (!editing) {
    return (
      <div className="hh-field">
        {label ? (
          <label className="hh-label">
            {label} <InfoTip text={tip} />
          </label>
        ) : null}
        <div className="chat-id-locked">
          {value.trim() ? (
            <span className="chat-id-locked-value" title={value}>
              ID задан · {value.trim().slice(0, 4)}…{value.trim().slice(-4)}
            </span>
          ) : (
            <span className="chat-id-locked-empty">ID не задан</span>
          )}
          <button
            type="button"
            className="chip"
            disabled={disabled}
            onClick={() => setEditing(true)}
          >
            Изменить
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="hh-field">
      {label ? (
        <label className="hh-label">
          {label} <InfoTip text={tip} />
        </label>
      ) : (
        <InfoTip text={tip} />
      )}
      <div className="chat-id-locked">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder={placeholder}
          style={{ minWidth: 140 }}
        />
        {onSave ? (
          <button
            type="button"
            className="chip chip-active"
            disabled={disabled || saveDisabled}
            onClick={() => {
              void (async () => {
                await onSave();
                setEditing(false);
              })();
            }}
          >
            {saveLabel}
          </button>
        ) : (
          <button
            type="button"
            className="chip chip-active"
            disabled={disabled}
            onClick={() => setEditing(false)}
          >
            {saveLabel}
          </button>
        )}
        <button
          type="button"
          className="chip"
          disabled={disabled}
          onClick={() => setEditing(false)}
        >
          Отмена
        </button>
      </div>
    </div>
  );
}
