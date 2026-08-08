"use client";

import { useState } from "react";
import { InfoTip } from "@/components/InfoTip";

type Props = {
  value: string;
  onChange: (next: string) => void;
  label?: string;
  tip?: string;
  placeholder?: string;
  disabled?: boolean;
  multiline?: boolean;
  rows?: number;
  emptyLabel?: string;
  /** Custom locked preview (e.g. masked secret). */
  lockedPreview?: string;
  type?: string;
  onConfirm?: (next: string) => void | Promise<void>;
  confirmDisabled?: boolean;
};

/**
 * Settings text field: locked by default → «Изменить» → edit → «Ок» / «Отмена».
 * Prevents accidental edits of saved values.
 */
export function LockedTextField({
  value,
  onChange,
  label,
  tip,
  placeholder,
  disabled = false,
  multiline = false,
  rows = 3,
  emptyLabel = "не задано",
  lockedPreview,
  type = "text",
  onConfirm,
  confirmDisabled = false,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const startEdit = () => {
    setDraft(value);
    setEditing(true);
  };

  const cancel = () => {
    setDraft(value);
    setEditing(false);
  };

  const confirm = async () => {
    onChange(draft);
    if (onConfirm) await onConfirm(draft);
    setEditing(false);
  };

  const preview =
    lockedPreview ??
    (value.trim()
      ? value.length > 64
        ? `${value.trim().slice(0, 28)}…${value.trim().slice(-12)}`
        : value
      : emptyLabel);

  return (
    <div className="hh-field">
      {label ? (
        <label className="hh-label">
          {label}
          {tip ? <InfoTip text={tip} /> : null}
        </label>
      ) : tip ? (
        <InfoTip text={tip} />
      ) : null}

      {!editing ? (
        <div className="chat-id-locked">
          <span
            className={value.trim() ? "chat-id-locked-value" : "chat-id-locked-empty"}
            title={value || undefined}
          >
            {preview}
          </span>
          <button type="button" className="chip" disabled={disabled} onClick={startEdit}>
            Изменить
          </button>
        </div>
      ) : (
        <div className="chat-id-locked" style={{ alignItems: multiline ? "flex-start" : "center" }}>
          {multiline ? (
            <textarea
              rows={rows}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={disabled}
              placeholder={placeholder}
              style={{ flex: 1, minWidth: 160 }}
            />
          ) : (
            <input
              type={type}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={disabled}
              placeholder={placeholder}
              style={{ minWidth: 160, flex: 1 }}
            />
          )}
          <button
            type="button"
            className="chip chip-active"
            disabled={disabled || confirmDisabled}
            onClick={() => void confirm()}
          >
            Ок
          </button>
          <button type="button" className="chip" disabled={disabled} onClick={cancel}>
            Отмена
          </button>
        </div>
      )}
    </div>
  );
}
