export function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${getApiBase()}${path}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${path}: ${res.status}`);
  }
  return res.json() as Promise<T>;
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
  last_contact_at?: string | null;
};

export type CandidateDetail = CandidateListItem & {
  vacancy_title: string | null;
  client_id: number | null;
  client_name: string | null;
  status_updated_at: string | null;
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
  office_interview_date: string | null;
  office_interview_time: string | null;
  hh_resume_id?: string | null;
  payload: Record<string, unknown>;
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
