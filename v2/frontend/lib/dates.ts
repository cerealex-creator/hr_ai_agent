export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** YYYY-MM-DD as local calendar day (avoids UTC shift). */
export function parseLocalDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (m) {
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  return parseDate(value);
}

/** True if interview/meeting datetime (or end of that date) is already in the past. */
export function isEventPassed(
  dateStr: string | null | undefined,
  timeStr?: string | null,
): boolean {
  const d = parseLocalDate(dateStr);
  if (!d) return false;
  const tm = (timeStr || "").trim();
  const m = /^(\d{1,2}):(\d{2})/.exec(tm);
  if (m) {
    d.setHours(Number(m[1]), Number(m[2]), 0, 0);
  } else {
    d.setHours(23, 59, 59, 999);
  }
  return Date.now() > d.getTime();
}

export function formatDateRu(value: string | null | undefined): string {
  const d = parseDate(value);
  if (!d) return "—";
  return d.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** Legacy history stamp: YYYYMMDD_HHMMSS → readable. */
export function formatLegacyStamp(value: string | null | undefined): string {
  if (!value) return "—";
  const m = /^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/.exec(value);
  if (!m) return value;
  return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`;
}

/** Whole calendar days between start and end (or now). */
export function daysBetween(
  startIso: string | null | undefined,
  endIso?: string | null,
): number | null {
  const start = parseDate(startIso);
  if (!start) return null;
  const end = parseDate(endIso) || new Date();
  const ms = end.getTime() - start.getTime();
  if (ms < 0) return 0;
  return Math.floor(ms / 86_400_000);
}

export function daysLabel(days: number | null): string {
  if (days === null) return "—";
  const n = Math.abs(days) % 100;
  const n1 = n % 10;
  let word = "дней";
  if (n > 10 && n < 20) word = "дней";
  else if (n1 === 1) word = "день";
  else if (n1 >= 2 && n1 <= 4) word = "дня";
  return `${days} ${word}`;
}
