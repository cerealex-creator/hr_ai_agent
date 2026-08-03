"use client";

import { useEffect, useState, type ReactNode } from "react";

type Props = {
  id?: string;
  title: string;
  hint?: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
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
  children,
}: Props) {
  const controlled = openProp !== undefined;
  const [inner, setInner] = useState(defaultOpen);
  const open = controlled ? openProp : inner;

  useEffect(() => {
    if (!controlled) setInner(defaultOpen);
  }, [controlled, defaultOpen]);

  const setOpen = (next: boolean) => {
    if (!controlled) setInner(next);
    onOpenChange?.(next);
  };

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
