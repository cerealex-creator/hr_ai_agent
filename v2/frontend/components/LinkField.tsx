"use client";

import { useState } from "react";

type Props = {
  id: string;
  label: string;
  openLabel: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  placeholder?: string;
  hint?: string;
};

/** Streamlit-like: filled URL → Open + Edit; empty/editing → text input. */
export function LinkField({
  id,
  label,
  openLabel,
  value,
  onChange,
  disabled,
  placeholder,
  hint,
}: Props) {
  const trimmed = value.trim();
  const [editing, setEditing] = useState(!trimmed);

  if (!editing && trimmed) {
    return (
      <div className="hh-field">
        <span className="hh-label">{label}</span>
        <div className="hh-row-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
          <a className="chip chip-active" href={trimmed} target="_blank" rel="noreferrer">
            {openLabel}
          </a>
          <button
            type="button"
            className="chip"
            disabled={disabled}
            onClick={() => setEditing(true)}
          >
            Изменить ссылку
          </button>
        </div>
        {hint ? <p className="muted hh-micro">{hint}</p> : null}
      </div>
    );
  }

  return (
    <div className="hh-field">
      <label className="hh-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
      />
      <div className="hh-row-actions" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
        {trimmed ? (
          <>
            <a className="chip" href={trimmed} target="_blank" rel="noreferrer">
              {openLabel}
            </a>
            <button
              type="button"
              className="chip chip-active"
              disabled={disabled}
              onClick={() => setEditing(false)}
            >
              Готово
            </button>
          </>
        ) : null}
      </div>
      {hint ? <p className="muted hh-micro">{hint}</p> : null}
    </div>
  );
}
