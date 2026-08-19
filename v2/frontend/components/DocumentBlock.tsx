"use client";

import { useMemo, useState, type ReactNode } from "react";
import { fieldLabel } from "@/lib/labels";
import { normalizeDocumentValue } from "@/lib/documentNormalize";

type Props = {
  /** Storage key: profile / questions / … — used for format-specific normalize */
  docKey: string;
  title: string;
  value: unknown;
  /** Accordion: closed by default unless defaultOpen */
  collapsible?: boolean;
  defaultOpen?: boolean;
  /** Show even when empty (useful in accordion lists) */
  showEmpty?: boolean;
  /** Extra UI above content (AI generate controls etc.) */
  actions?: ReactNode;
  /** Hide title chrome — only body (when wrapped externally) */
  hideChrome?: boolean;
};

function isReqItem(item: unknown): item is Record<string, unknown> {
  return !!item && typeof item === "object" && !Array.isArray(item);
}

function ReadableNode({ value }: { value: unknown }) {
  if (value == null || value === "") {
    return <p className="doc-empty">—</p>;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <div className="doc-text">{String(value)}</div>;
  }

  if (Array.isArray(value)) {
    if (!value.length) return <p className="doc-empty">—</p>;
    const allPrimitive = value.every(
      (item) => item == null || ["string", "number", "boolean"].includes(typeof item),
    );
    if (allPrimitive) {
      return (
        <ul className="doc-list">
          {value.map((item, idx) => (
            <li key={idx}>{item == null || item === "" ? "—" : String(item)}</li>
          ))}
        </ul>
      );
    }

    // Q&A / requirements cards
    return (
      <div className="doc-cards">
        {value.map((item, idx) => {
          if (!isReqItem(item)) {
            return (
              <div className="doc-card" key={idx}>
                <ReadableNode value={item} />
              </div>
            );
          }
          const skill = item.навык || item.качество || item.вопрос;
          const detail = item.описание || item.проявление || item.пример_ответа;
          const category = item.категория;
          if (skill || detail) {
            return (
              <div className="doc-card" key={idx}>
                {category ? <div className="doc-card-cat">{String(category)}</div> : null}
                {skill ? <div className="doc-card-title">{String(skill)}</div> : null}
                {detail ? <div className="doc-text">{String(detail)}</div> : null}
                {/* leftover fields */}
                {Object.entries(item)
                  .filter(
                    ([k]) =>
                      ![
                        "навык",
                        "качество",
                        "вопрос",
                        "описание",
                        "проявление",
                        "пример_ответа",
                        "категория",
                      ].includes(k),
                  )
                  .map(([k, v]) =>
                    v == null || v === "" ? null : (
                      <div className="doc-field" key={k}>
                        <dt>{fieldLabel(k)}</dt>
                        <dd>
                          <ReadableNode value={v} />
                        </dd>
                      </div>
                    ),
                  )}
              </div>
            );
          }
          return (
            <div className="doc-card" key={idx}>
              <ReadableNode value={item} />
            </div>
          );
        })}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return <p className="doc-empty">—</p>;
    return (
      <dl className="doc-fields">
        {entries.map(([key, val]) => (
          <div className="doc-field" key={key}>
            <dt>{fieldLabel(key)}</dt>
            <dd>
              <ReadableNode value={val} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return <div className="doc-text">{String(value)}</div>;
}

export function DocumentBlock({
  docKey,
  title,
  value,
  collapsible = false,
  defaultOpen = false,
  showEmpty = false,
  actions,
  hideChrome = false,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const normalized = useMemo(() => normalizeDocumentValue(docKey, value), [docKey, value]);

  const empty =
    value == null ||
    value === "" ||
    (typeof value === "string" && !value.trim()) ||
    (typeof value === "object" &&
      !Array.isArray(value) &&
      Object.keys(value as object).length === 0) ||
    (Array.isArray(value) && value.length === 0);

  if (empty && !showEmpty && !collapsible) return null;

  const body = (
    <>
      {actions}
      {empty ? <p className="doc-empty">—</p> : <ReadableNode value={normalized} />}
    </>
  );

  if (hideChrome) {
    return <div className="doc-embedded">{body}</div>;
  }

  if (collapsible) {
    return (
      <details
        className="doc-block doc-block-accordion"
        open={open}
        onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
      >
        <summary className="doc-summary">
          <span className="doc-summary-main">
            <span className="doc-summary-title">{title}</span>
            <span className="doc-summary-hint">{empty ? "пусто" : "есть данные"}</span>
          </span>
        </summary>
        <div className="doc-block-body">{body}</div>
      </details>
    );
  }

  return (
    <section className="doc-block">
      <div className="doc-block-head">
        <h2>{title}</h2>
      </div>
      {body}
    </section>
  );
}
