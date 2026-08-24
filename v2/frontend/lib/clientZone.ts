import { getApiBase } from "@/lib/api";

export const CZ_STATUS_LABELS: Record<string, string> = {
  wait: "Ожидает",
  think: "Думает",
  ready: "Встреча",
  reject: "Отказ",
  offer: "Оффер",
  started: "Вышел",
};

/** Same keys as backend ZONE_DECISION_ROLES */
export const CZ_DECISION_ROLES = [
  { id: "unit_head", label: "Руководитель подразделения" },
  { id: "director", label: "Директор" },
  { id: "owner", label: "Собственник" },
] as const;

export type ZoneDigest = {
  summary: string;
  qa: { q: string; a: string }[];
};

export type ZoneCandidateListItem = {
  id: string;
  name: string;
  vacancy_title: string;
  client_name: string | null;
  company_name?: string | null;
  department_name?: string | null;
  client_status: string;
  ai_score: number | null;
  ai_comment: string | null;
  client_comment: string | null;
  office_interview_date: string | null;
  office_interview_time: string | null;
  actionable: boolean;
  has_resume?: boolean;
  has_video?: boolean;
  has_digest?: boolean;
  photo_url?: string | null;
  gender?: string | null;
};

export type ZoneCandidateDetail = ZoneCandidateListItem & {
  resume_url?: string | null;
  video_url?: string | null;
  portfolio_url?: string | null;
  task_url?: string | null;
  extra_materials?: { title: string; url: string }[];
  interview_digest?: ZoneDigest | null;
  hr_comment?: string | null;
};

export type ZoneListData = {
  company: { id: number; name: string; department_name?: string | null };
  candidates: ZoneCandidateListItem[];
  reports?: ZoneReportListItem[];
  demo?: boolean;
};

export type ZoneReportListItem = {
  vacancy_id: number;
  title: string;
  active: boolean;
  period: string;
  path: string;
  to_client: number;
  offer: number;
  selected: number;
};

export type ZoneDetailData = {
  company: { id: number; name: string; department_name?: string | null };
  candidate: ZoneCandidateDetail;
  demo?: boolean;
};

export function zonePlaceLabel(c: {
  company_name?: string | null;
  department_name?: string | null;
  client_name?: string | null;
}): string {
  const company = (c.company_name || "").trim();
  const dept = (c.department_name || "").trim() || (c.client_name || "").trim();
  if (company && dept && company !== dept) return `${company} · ${dept}`;
  return company || dept;
}

export async function zoneFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getApiBase()}${path}`, {
    ...init,
    cache: "no-store",
  });
}
