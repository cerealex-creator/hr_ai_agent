import { getApiBase } from "@/lib/api";

export const CZ_STATUS_LABELS: Record<string, string> = {
  wait: "Ожидает",
  think: "Думает",
  ready: "Встреча",
  reject: "Отказ",
  offer: "Оффер",
  started: "Вышел",
};

export type ZoneDigest = {
  summary: string;
  qa: { q: string; a: string }[];
};

export type ZoneCandidateListItem = {
  id: string;
  name: string;
  vacancy_title: string;
  client_name: string | null;
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
  company: { id: number; name: string };
  candidates: ZoneCandidateListItem[];
};

export type ZoneDetailData = {
  company: { id: number; name: string };
  candidate: ZoneCandidateDetail;
};

export async function zoneFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getApiBase()}${path}`, {
    ...init,
    cache: "no-store",
  });
}
