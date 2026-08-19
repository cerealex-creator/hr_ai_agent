/**
 * Browser: same-origin (Next rewrite → API) so httpOnly cookies + EventSource work.
 * Server components / SSR: hit backend directly.
 */
export function getApiBase(): string {
  if (typeof window !== "undefined") {
    return "";
  }
  return (
    process.env.API_INTERNAL_URL?.replace(/\/$/, "") ||
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
    "http://localhost:8000"
  );
}

/** Absolute base for EventSource (always same-origin in browser). */
export function getEventsStreamUrl(): string {
  return "/api/v1/events/stream";
}

type ApiFetchOptions = RequestInit & {
  /** Skip 401 → refresh → redirect (for /auth/login, /auth/me checks). */
  skipAuthRedirect?: boolean;
};

let refreshInFlight: Promise<boolean> | null = null;

async function serverCookieHeader(): Promise<string | undefined> {
  if (typeof window !== "undefined") return undefined;
  try {
    const { cookies } = await import("next/headers");
    const store = await cookies();
    const parts: string[] = [];
    for (const c of store.getAll()) {
      parts.push(`${c.name}=${c.value}`);
    }
    return parts.length ? parts.join("; ") : undefined;
  } catch {
    return undefined;
  }
}

async function tryRefresh(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${getApiBase()}/api/v1/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        return res.ok;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

function redirectToLoginClient(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  const next = `${window.location.pathname}${window.location.search}`;
  window.location.href = `/login?next=${encodeURIComponent(next)}`;
}

export class AuthRequiredError extends Error {
  constructor() {
    super("Требуется вход");
    this.name = "AuthRequiredError";
  }
}

/** API fetch with credentials (httpOnly cookies) and refresh-on-401 (browser). */
export async function apiFetch(path: string, init: ApiFetchOptions = {}): Promise<Response> {
  const { skipAuthRedirect, ...rest } = init;
  const url = path.startsWith("http") ? path : `${getApiBase()}${path}`;
  const headers = new Headers(rest.headers || undefined);
  const cookie = await serverCookieHeader();
  if (cookie && !headers.has("Cookie")) {
    headers.set("Cookie", cookie);
  }

  const res = await fetch(url, {
    ...rest,
    headers,
    credentials: typeof window !== "undefined" ? "include" : undefined,
    cache: rest.cache ?? "no-store",
  });

  if (res.status !== 401 || skipAuthRedirect) {
    return res;
  }
  if (path.includes("/auth/login") || path.includes("/auth/refresh") || path.includes("/auth/me")) {
    return res;
  }

  if (typeof window === "undefined") {
    // Тело ответа надо дочитать: незакрытый поток подвешивает серверный рендер страницы.
    await res.text().catch(() => undefined);
    throw new AuthRequiredError();
  }

  const ok = await tryRefresh();
  if (!ok) {
    redirectToLoginClient();
    return res;
  }
  return fetch(url, {
    ...rest,
    credentials: "include",
    cache: rest.cache ?? "no-store",
  });
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path}: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export type AuthMe = {
  id: string;
  email: string;
  full_name: string;
  org_id: string;
  org_name?: string;
  roles: string[];
  auth_disabled?: boolean;
  bitrix_responsible_id?: string;
  telegram_available?: boolean;
  is_demo?: boolean;
};

export async function authMe(): Promise<AuthMe | null> {
  let res = await apiFetch("/api/v1/auth/me", { cache: "no-store", skipAuthRedirect: true });
  if (res.status === 401 && typeof window !== "undefined") {
    const ok = await tryRefresh();
    if (ok) {
      res = await apiFetch("/api/v1/auth/me", { cache: "no-store", skipAuthRedirect: true });
    }
  }
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`API /auth/me: ${res.status}`);
  return res.json() as Promise<AuthMe>;
}

function loginErrorMessage(status: number, body: string): string {
  try {
    const data = JSON.parse(body) as { detail?: unknown };
    const detail = data?.detail;
    if (detail === "Invalid credentials") return "Неверный email или пароль";
    if (detail === "No organization membership") return "У пользователя нет организации";
    if (typeof detail === "string" && detail.trim()) return detail;
  } catch {
    /* ignore */
  }
  if (status === 401) return "Неверный email или пароль";
  return `Не удалось войти (${status})`;
}

export async function authLogin(email: string, password: string): Promise<AuthMe> {
  const res = await apiFetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    skipAuthRedirect: true,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(loginErrorMessage(res.status, text));
  }
  return res.json() as Promise<AuthMe>;
}

export async function authDemo(): Promise<AuthMe> {
  const res = await apiFetch("/api/v1/auth/demo", {
    method: "POST",
    skipAuthRedirect: true,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(loginErrorMessage(res.status, text));
  }
  return res.json() as Promise<AuthMe>;
}

export async function authLogout(): Promise<void> {
  await apiFetch("/api/v1/auth/logout", { method: "POST", skipAuthRedirect: true });
}

export type UsefulLink = {
  id: string;
  label: string;
  url: string;
};

export async function fetchUsefulLinks(): Promise<{ items: UsefulLink[]; auth_disabled: boolean }> {
  const res = await apiFetch("/api/v1/auth/useful-links", { cache: "no-store" });
  if (!res.ok) throw new Error(`API /auth/useful-links: ${res.status}`);
  return res.json();
}

export async function saveUsefulLinks(items: UsefulLink[]): Promise<UsefulLink[]> {
  const res = await apiFetch("/api/v1/auth/useful-links", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const data = JSON.parse(text) as { detail?: unknown };
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `API PUT /auth/useful-links: ${res.status}`);
  }
  const data = (await res.json()) as { items: UsefulLink[] };
  return data.items || [];
}

export type VacancyOutcome = "success" | "client_cancelled" | "no_result" | null;

export type ClientItem = {
  id: number;
  name: string;
  slug: string;
  parent_id?: number | null;
  chat_mode?: string;
  kind?: string;
};

export type VacancyListItem = {
  id: number;
  title: string;
  active: boolean;
  client_id: number | null;
  client_name: string | null;
  chat_id?: string | null;
  candidates_count: number;
  created_at: string | null;
  closed_at: string | null;
  close_reason: string | null;
  has_hire: boolean;
  outcome: VacancyOutcome;
  avatar_key?: string | null;
};

export type VacancyDetail = VacancyListItem & {
  chat_id: string | null;
  documents: Record<string, unknown>;
  document_keys: string[];
  payload: Record<string, unknown>;
};

export type CandidateListItem = {
  id: string;
  vacancy_id: number;
  name: string;
  hr_stage: string;
  client_status: string;
  created_at: string | null;
  phone: string | null;
  city: string | null;
  vacancy_title?: string | null;
  client_name?: string | null;
  photo_url?: string | null;
  gender?: string | null;
  last_contact_at?: string | null;
  attention_reason?: string | null;
  liked?: boolean;
  talent_reserve?: boolean;
  talent_reserve_at?: string | null;
  ai_score?: number | null;
};

export type CandidateDetail = CandidateListItem & {
  vacancy_title: string | null;
  client_id: number | null;
  client_name: string | null;
  status_updated_at: string | null;
  email: string | null;
  metro: string | null;
  age: string | null;
  salary_expected: string | null;
  resume_link: string | null;
  hh_resume_link: string | null;
  portfolio_link: string | null;
  video_link: string | null;
  task_link?: string | null;
  hr_comment: string | null;
  transcript?: string | null;
  interview_digest?: {
    summary?: string;
    qa?: { q: string; a: string }[];
    communication?: string;
    created_at?: string | null;
    public_url?: string | null;
  } | null;
  interview_eval_notes?: string | null;
  questionnaire_recruiter_notes?: string | null;
  client_comment: string | null;
  ai_score: number | null;
  ai_score_source?: string | null;
  ai_comment: string | null;
  ai_comment_sections?: Record<string, unknown> | null;
  interview_questionnaire?: unknown[] | null;
  control_word_status?: string | null;
  control_word_match?: string | null;
  control_word_note?: string | null;
  vacancy_control_word_enabled?: boolean;
  vacancy_control_word?: string | null;
  office_interview_date: string | null;
  office_interview_time: string | null;
  photo_url: string | null;
  gender?: string | null;
  hh_resume_id?: string | null;
  liked?: boolean;
  liked_at?: string | null;
  talent_reserve?: boolean;
  talent_reserve_at?: string | null;
  talent_reserve_note?: string | null;
  talent_reserve_by?: string | null;
  person_id?: string | null;
  related_vacancies?: {
    candidate_id: string;
    vacancy_id: number;
    vacancy_title: string;
    hr_stage: string;
  }[];
  payload: Record<string, unknown>;
};

export type DupHit = {
  candidate_id: string;
  person_id: string;
  name: string;
  vacancy_id: number;
  vacancy_title: string;
  match_kind: string;
};

export type CheckDuplicateResult = {
  hard: DupHit[];
  soft: DupHit[];
};

export type FunnelStats = {
  vacancies_active: number;
  vacancies_archive: number;
  candidates_total: number;
  by_hr_stage: { stage: string; count: number }[];
  by_client_status: { stage: string; count: number }[];
  by_client: {
    client_id: number | null;
    client_name: string;
    vacancies_active: number;
    vacancies_archive: number;
    candidates: number;
  }[];
  hires: number;
  in_client_zone: number;
  sent_to_client?: number;
  vacancy_id?: number | null;
  vacancy_title?: string | null;
};

export type HistoryItem = {
  id: string;
  source_filename: string;
  title: string;
  mode: string;
  created_at_legacy: string | null;
  imported_at: string;
  preview: string | null;
  vacancy_id?: number | null;
};

export type HistoryDetail = HistoryItem & {
  documents_snapshot: Record<string, unknown>;
};

export type ImportStats = {
  last_import_at: string | null;
  source_dir: string | null;
  stats: Record<string, number>;
  counts: Record<string, number>;
};

export function outcomeLabel(outcome: VacancyOutcome): string {
  if (outcome === "success") return "Успешно";
  if (outcome === "client_cancelled") return "Закрыта заказчиком";
  if (outcome === "no_result") return "Без результата";
  return "—";
}

export { fieldLabel as docLabel } from "@/lib/labels";
