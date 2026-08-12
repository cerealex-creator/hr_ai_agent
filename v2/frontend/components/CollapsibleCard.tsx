"use client";

import { useEffect, useState, type ReactNode } from "react";

type Props = {
  id?: string;
  title: string;
  hint?: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Always expanded, no collapse toggle (for tab panels). */
  static?: boolean;
  children: ReactNode;
};

/** Collapsible card-edit section: click header to expand/collapse body. */
export function CollapsibleCard({
  id,
  title,
  hint,
  defaultOpen = false,
  open: openProp,
  onOpenChange,
  static: staticPanel = false,
  children,
}: Props) {
  const controlled = openProp !== undefined;
  const [inner, setInner] = useState(defaultOpen || staticPanel);
  const open = staticPanel ? true : controlled ? openProp : inner;

  useEffect(() => {
    if (!controlled && !staticPanel) setInner(defaultOpen);
  }, [controlled, defaultOpen, staticPanel]);

  const setOpen = (next: boolean) => {
    if (staticPanel) return;
    if (!controlled) setInner(next);
    onOpenChange?.(next);
  };

  if (staticPanel) {
    return (
      <section className="card-edit card-tab-panel" id={id}>
        <div className="card-tab-panel-head">
          <h2 className="card-tab-panel-title">{title}</h2>
          {hint ? <span className="card-tab-panel-hint">{hint}</span> : null}
        </div>
        <div className="card-collapse-body">{children}</div>
      </section>
    );
  }

  return (
    <section className={`card-edit card-collapse${open ? " is-open" : ""}`} id={id}>
      <button
        type="button"
        className="card-collapse-toggle"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span className="card-collapse-title">{title}</span>
        {hint ? <span className="card-collapse-hint">{hint}</span> : null}
        <span className="card-collapse-chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open ? <div className="card-collapse-body">{children}</div> : null}
    </section>
  );
}
