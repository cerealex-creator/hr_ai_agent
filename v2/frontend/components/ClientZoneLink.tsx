"use client";

import { useCallback, useMemo, useState } from "react";

type Props = {
  /** Путь вида `/c/TOKEN` или полный URL. */
  path: string | null | undefined;
  /** Подпись над ссылкой. */
  label?: string;
  /** Компактный вид без пошаговой инструкции. */
  compact?: boolean;
  /** Не показывать подсказку «ещё не создана» (кнопка создания рядом). */
  hideEmptyHint?: boolean;
};

function toAbsoluteUrl(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) return "";
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) return trimmed;
  if (typeof window === "undefined") return trimmed;
  const base = window.location.origin.replace(/\/$/, "");
  return `${base}${trimmed.startsWith("/") ? trimmed : `/${trimmed}`}`;
}

export function ClientZoneLink({ path, label, compact = false, hideEmptyHint = false }: Props) {
  const [copied, setCopied] = useState(false);
  const href = useMemo(() => (path ? toAbsoluteUrl(path) : ""), [path]);

  const copy = useCallback(async () => {
    if (!href) return;
    try {
      await navigator.clipboard.writeText(href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }, [href]);

  if (!path || !href) {
    if (hideEmptyHint) return null;
    return (
      <div className="cz-link-block cz-link-block--empty">
        <p className="muted hh-micro">
          Ссылка для заказчика ещё не создана. Создайте её в{" "}
          <a href="/settings/companies">настройках компании</a> или отправьте кандидата заказчику —
          ссылка появится автоматически.
        </p>
      </div>
    );
  }

  return (
    <div className="cz-link-block">
      {label ? <p className="cz-link-label">{label}</p> : null}
      {!compact ? (
        <ol className="cz-link-steps muted hh-micro">
          <li>Отправьте заказчику ссылку ниже (можно скопировать).</li>
          <li>Заказчик открывает её в браузере — вход не нужен.</li>
          <li>На странице видны кандидаты этого подразделения (или компании) на этапе «На оценке у заказчика».</li>
          <li>
            Это не ссылка на выжимку собеседования (<code>/i/…</code>) — только список кандидатов
            для решения.
          </li>
        </ol>
      ) : null}
      <div className="cz-link-row">
        <a href={href} target="_blank" rel="noreferrer" className="cz-link-url">
          {href}
        </a>
        <button type="button" className="chip" onClick={copy}>
          {copied ? "Скопировано" : "Копировать"}
        </button>
        <a href={href} target="_blank" rel="noreferrer" className="chip chip-active">
          Открыть
        </a>
      </div>
    </div>
  );
}

/** Достать путь веб-зоны из ответа send-to-chat. */
export function clientZonePathFromSendResults(results: unknown): string | null {
  if (!Array.isArray(results)) return null;
  for (const row of results) {
    if (row && typeof row === "object" && "client_zone_path" in row) {
      const p = (row as { client_zone_path?: unknown }).client_zone_path;
      if (typeof p === "string" && p.startsWith("/c/")) return p;
    }
  }
  return null;
}
