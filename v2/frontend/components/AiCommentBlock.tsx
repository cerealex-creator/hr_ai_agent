"use client";

import { useEffect, useState } from "react";
import { fieldLabel } from "@/lib/labels";

const SECTION_ORDER = [
  "соответствие",
  "опыт_и_навыки",
  "риски",
  "проверить_на_интервью",
  "итог",
] as const;

type Props = {
  comment?: string | null;
  sections?: Record<string, unknown> | null;
  defaultOpen?: boolean;
  /** Controlled open (e.g. jump from score summary). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  id?: string;
};

function SectionBody({ value }: { value: unknown }) {
  if (value == null || value === "") return <p className="doc-empty">—</p>;
  if (Array.isArray(value)) {
    return (
      <ul className="doc-list">
        {value.map((item, i) => (
          <li key={i}>{String(item)}</li>
        ))}
      </ul>
    );
  }
  return <div className="doc-text">{String(value)}</div>;
}

/** Collapsed-by-default AI analysis, structured like a vacancy profile. */
export function AiCommentBlock({
  comment,
  sections,
  defaultOpen = false,
  open: openProp,
  onOpenChange,
  id,
}: Props) {
  const controlled = openProp !== undefined;
  const [innerOpen, setInnerOpen] = useState(defaultOpen);
  const open = controlled ? openProp : innerOpen;

  useEffect(() => {
    if (!controlled && defaultOpen) setInnerOpen(true);
  }, [controlled, defaultOpen]);

  const setOpen = (next: boolean) => {
    if (!controlled) setInnerOpen(next);
    onOpenChange?.(next);
  };

  const hasSections = sections && typeof sections === "object" && Object.keys(sections).length > 0;
  if (!hasSections && !(comment || "").trim()) return null;

  const orderedKeys = [
    ...SECTION_ORDER.filter((k) => hasSections && sections![k] != null && sections![k] !== ""),
    ...Object.keys(sections || {}).filter(
      (k) => !(SECTION_ORDER as readonly string[]).includes(k) && sections![k] != null && sections![k] !== "",
    ),
  ];

  return (
    <section className="doc-block ai-comment-block" id={id}>
      <button
        type="button"
        className="ai-comment-toggle"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span>Комментарий ИИ</span>
        <span className="muted">{open ? "Свернуть" : "Развернуть"}</span>
      </button>
      {open ? (
        <div className="ai-comment-body">
          {hasSections ? (
            orderedKeys.map((key) => (
              <div key={key} className="ai-comment-section">
                <h3>{fieldLabel(key)}</h3>
                <SectionBody value={sections![key]} />
              </div>
            ))
          ) : (
            <div className="doc-text">{comment}</div>
          )}
        </div>
      ) : (
        <p className="muted ai-comment-preview">
          {hasSections
            ? "Структурированный разбор — нажмите, чтобы открыть"
            : `${(comment || "").slice(0, 120)}${(comment || "").length > 120 ? "…" : ""}`}
        </p>
      )}
    </section>
  );
}
