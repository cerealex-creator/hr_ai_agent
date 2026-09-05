import { apiFetch } from "@/lib/api";

export type ConsultingUnit = {
  id: string;
  kind: "uk" | "directorate" | "be" | string;
  name: string;
  sort_order: number;
};

export type ConsultingPerson = {
  id: string;
  full_name: string;
  title: string;
  unit_id: string | null;
  interview: boolean;
  survey: boolean;
  level: string;
};

export type ConsultingMilestone = {
  id: string;
  code: string;
  title: string;
  due_on: string | null;
  sort_order: number;
};

export type ConsultingProject = {
  id: string;
  title: string;
  customer_name: string;
  started_on: string | null;
  due_on: string | null;
  plan_status: string;
  results: Record<string, string>;
  result_labels: { code: string; title: string }[];
  units: ConsultingUnit[];
  people: ConsultingPerson[];
  milestones: ConsultingMilestone[];
  members: { id: string; user_id: string; role: string }[];
  showcase_token?: string | null;
  showcase?: { version?: number; published_at?: string; guest_approved?: boolean };
};

export type ConsultingHub = {
  project: ConsultingProject;
  collect: {
    sources: number;
    pending_review: number;
    people: number;
    meetings_pending: number;
    surveys_pending: number;
  };
  attention: {
    empty_folders: number;
    recommended: number;
    disputed: number;
    contradictions: number;
    shadows: number;
    white_spots: number;
  };
  output: {
    plan_done: number;
    plan_total: number;
    results_ready: number;
    results_total: number;
    showcase_ready: boolean;
  };
};

export type ConsultingMeeting = {
  id: string;
  title: string;
  held_on: string | null;
  level: string;
  notes: string;
  transcript: string;
  digest: string;
  url: string | null;
  folder_id: string | null;
  has_text: boolean;
};

export type ConsultingContradiction = {
  id: string;
  title: string;
  left_text: string;
  right_text: string;
  status: string;
  registry_row_id: string | null;
};

export type ConsultingCoverage = {
  open: number;
  total: number;
  items: { code: string; title: string; closed: boolean; kind: string }[];
};

export type ConsultingShowcasePublic = {
  title: string;
  customer_name: string;
  version: number;
  published_at: string | null;
  guest_approved: boolean;
  plan_done: number;
  plan_total: number;
  folders: { code: string; name: string; file_count: number }[];
  facts: { id: string; title: string; status: string }[];
  comments: { id: string; author_name: string; body: string; created_at: string | null }[];
  forms_note: string;
};

export type ConsultingFolder = {
  id: string;
  code: string;
  name: string;
  purpose: string;
  level: number;
  parent_code: string | null;
  file_count: number;
  empty: boolean;
};

export type ConsultingSource = {
  id: string;
  folder_id: string | null;
  kind: string;
  title: string;
  url: string | null;
  quoted_text: string;
  mark: string;
  file_name: string | null;
  has_quote: boolean;
  extracted_preview?: string;
  extract_status?: string;
  space?: string;
};

export type ConsultingRegistryRow = {
  id: string;
  source_id: string | null;
  title: string;
  owner_name: string;
  unit_name: string;
  status: string;
  action: string;
  priority: string;
  target_system: string;
  note: string;
  confidence?: string;
};

export type ConsultingPlan = {
  plan_status: string;
  items: { id: string; title: string; status: string; milestone_code: string | null }[];
};

async function read<T>(path: string, init?: RequestInit & { skipAuthRedirect?: boolean }): Promise<T> {
  const res = await apiFetch(path, { ...init, cache: "no-store" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : `Ошибка ${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}

export function listConsultingProjects() {
  return read<{ items: { id: string; title: string; customer_name: string }[] }>("/api/v1/consulting/projects");
}

export function createConsultingProject(body: { title?: string; customer_name?: string }) {
  return read<ConsultingProject>("/api/v1/consulting/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingProject(id: string) {
  return read<ConsultingProject>(`/api/v1/consulting/projects/${id}`);
}

export function patchConsultingProject(id: string, body: Record<string, unknown>) {
  return read<ConsultingProject>(`/api/v1/consulting/projects/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingHub(id: string) {
  return read<ConsultingHub>(`/api/v1/consulting/projects/${id}/hub`);
}

export function getConsultingFolders(id: string) {
  return read<{ items: ConsultingFolder[] }>(`/api/v1/consulting/projects/${id}/folders`);
}

export function getConsultingSources(id: string) {
  return read<{ items: ConsultingSource[] }>(`/api/v1/consulting/projects/${id}/sources`);
}

export function addConsultingSource(id: string, body: Record<string, unknown>) {
  return read<ConsultingSource>(`/api/v1/consulting/projects/${id}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function patchConsultingSource(id: string, sourceId: string, body: Record<string, unknown>) {
  return read<ConsultingSource>(`/api/v1/consulting/projects/${id}/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingPlan(id: string) {
  return read<ConsultingPlan>(`/api/v1/consulting/projects/${id}/plan`);
}

export function approveConsultingPlan(id: string) {
  return read<ConsultingPlan>(`/api/v1/consulting/projects/${id}/plan/approve`, { method: "POST" });
}

export function patchConsultingPlanItem(id: string, itemId: string, body: Record<string, unknown>) {
  return read(`/api/v1/consulting/projects/${id}/plan/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingRegistry(id: string) {
  return read<{ items: ConsultingRegistryRow[] }>(`/api/v1/consulting/projects/${id}/registry`);
}

export function patchConsultingRegistry(id: string, rowId: string, body: Record<string, unknown>) {
  return read<ConsultingRegistryRow>(`/api/v1/consulting/projects/${id}/registry/${rowId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function addConsultingPerson(id: string, body: Record<string, unknown>) {
  return read<ConsultingPerson>(`/api/v1/consulting/projects/${id}/people`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteConsultingPerson(id: string, personId: string) {
  return read<{ ok: string }>(`/api/v1/consulting/projects/${id}/people/${personId}`, { method: "DELETE" });
}

export function patchConsultingUnit(id: string, unitId: string, name: string) {
  return read<ConsultingUnit>(`/api/v1/consulting/projects/${id}/units/${unitId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export function getConsultingMeetings(id: string) {
  return read<{ items: ConsultingMeeting[] }>(`/api/v1/consulting/projects/${id}/meetings`);
}

export function addConsultingMeeting(id: string, body: Record<string, unknown>) {
  return read<ConsultingMeeting>(`/api/v1/consulting/projects/${id}/meetings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingContradictions(id: string) {
  return read<{ items: ConsultingContradiction[] }>(`/api/v1/consulting/projects/${id}/contradictions`);
}

export function addConsultingContradiction(id: string, body: Record<string, unknown>) {
  return read<ConsultingContradiction>(`/api/v1/consulting/projects/${id}/contradictions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function patchConsultingContradiction(id: string, rowId: string, status: string) {
  return read<ConsultingContradiction>(`/api/v1/consulting/projects/${id}/contradictions/${rowId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export function getConsultingCoverage(id: string) {
  return read<ConsultingCoverage>(`/api/v1/consulting/projects/${id}/coverage`);
}

export function publishConsultingShowcase(id: string) {
  return read<{ token: string; url: string; version: number; published_at: string; guest_approved: boolean }>(
    `/api/v1/consulting/projects/${id}/showcase/publish`,
    { method: "POST" },
  );
}

export function getConsultingShowcasePublic(token: string) {
  return read<ConsultingShowcasePublic>(`/api/v1/consulting/p/${token}`, { skipAuthRedirect: true });
}

export function addConsultingShowcaseComment(token: string, body: { author_name?: string; body: string }) {
  return read(`/api/v1/consulting/p/${token}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    skipAuthRedirect: true,
  });
}

export function approveConsultingShowcase(token: string) {
  return read<ConsultingShowcasePublic>(`/api/v1/consulting/p/${token}/approve`, {
    method: "POST",
    skipAuthRedirect: true,
  });
}

export function patchConsultingMilestone(id: string, milestoneId: string, due_on: string) {
  return read<ConsultingMilestone>(`/api/v1/consulting/projects/${id}/milestones/${milestoneId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ due_on }),
  });
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: "Черновик",
    recommended: "Рекомендация ИИ",
    confirmed: "Подтверждено",
    sent: "Отдано заказчику",
    approved: "Утверждено",
    disputed: "Оспорено заказчиком",
    pending: "На разборе",
    working: "Рабочий",
    doubtful: "Сомнительный",
    rejected: "Отклонён",
    todo: "Сделать",
    done: "Сделано",
    blocked: "Стоит",
    open: "Открыто",
    resolved: "Снято",
    owner: "Собственник",
    directors: "Директора",
    executors: "Исполнители",
    none: "нет следов",
    low: "низкая",
    high: "высокая",
    ok: "разобран",
    fail: "не разобрали",
    folder: "список папки",
    media: "аудио/видео — без скачивания",
    locked: "Зафиксирован",
    na: "Не применимо",
    published: "Опубликован",
    closed: "Закрыт",
    link: "В ссылку",
    meeting: "На встречу",
    practice_only: "Только факт",
    papers_only: "Только бумаги",
    mixed: "Смешанный",
    aligned: "Совпадает",
    unknown: "Неясно",
  };
  return map[status] || status;
}

export type ConsultingMegamaidNode = {
  id: string;
  code: string;
  title: string;
  kind: string;
  body: string;
  be_tags: string[];
  sort_order: number;
};

export type ConsultingEtalonNode = {
  id: string;
  code: string;
  title: string;
  kind: string;
  body: string;
  status: string;
  source_megamaid_id: string | null;
  version: number;
};

export type ConsultingProcessCard = {
  id: string;
  code: string;
  title: string;
  papers_text: string;
  practice_text: string;
  formality: string;
  status: string;
  folder_code: string | null;
};

export type ConsultingSurveyQuestion = {
  id: string;
  code: string;
  section: string;
  text: string;
  kind: string;
  options: string[];
  channel: string;
  preamble: string;
  preamble_status: string;
  coverage_code: string | null;
  sort_order: number;
};

export type ConsultingSurvey = {
  id: string;
  title: string;
  status: string;
  public_token: string | null;
  public_url: string | null;
  fill_white_spots: boolean;
  responses_count: number;
  questions: ConsultingSurveyQuestion[];
  link_questions?: number;
  meeting_questions?: number;
};

export function getConsultingMegamaid(id: string) {
  return read<{ items: ConsultingMegamaidNode[] }>(`/api/v1/consulting/projects/${id}/megamaid`);
}

export function getConsultingEtalon(id: string) {
  return read<{ items: ConsultingEtalonNode[] }>(`/api/v1/consulting/projects/${id}/etalon`);
}

export function copyMegamaidToEtalon(id: string, nodeId: string) {
  return read<ConsultingEtalonNode>(`/api/v1/consulting/projects/${id}/etalon/from-megamaid/${nodeId}`, {
    method: "POST",
  });
}

export function addConsultingEtalon(id: string, body: { title: string; body?: string; code?: string }) {
  return read<ConsultingEtalonNode>(`/api/v1/consulting/projects/${id}/etalon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function patchConsultingEtalon(id: string, nodeId: string, body: Record<string, unknown>) {
  return read<ConsultingEtalonNode>(`/api/v1/consulting/projects/${id}/etalon/${nodeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingProcessCards(id: string) {
  return read<{ items: ConsultingProcessCard[] }>(`/api/v1/consulting/projects/${id}/process-cards`);
}

export function addConsultingProcessCard(id: string, body: Record<string, unknown>) {
  return read<ConsultingProcessCard>(`/api/v1/consulting/projects/${id}/process-cards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingSurveys(id: string) {
  return read<{ items: ConsultingSurvey[] }>(`/api/v1/consulting/projects/${id}/surveys`);
}

export function createConsultingSurvey(id: string, body?: { title?: string; fill_white_spots?: boolean }) {
  return read<ConsultingSurvey>(`/api/v1/consulting/projects/${id}/surveys`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

export function getConsultingSurvey(id: string, surveyId: string) {
  return read<ConsultingSurvey>(`/api/v1/consulting/projects/${id}/surveys/${surveyId}`);
}

export function patchConsultingSurveyQuestion(
  id: string,
  surveyId: string,
  questionId: string,
  body: Record<string, unknown>,
) {
  return read<ConsultingSurveyQuestion>(
    `/api/v1/consulting/projects/${id}/surveys/${surveyId}/questions/${questionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export function publishConsultingSurvey(id: string, surveyId: string) {
  return read<ConsultingSurvey>(`/api/v1/consulting/projects/${id}/surveys/${surveyId}/publish`, {
    method: "POST",
  });
}

export function getConsultingSurveyResponses(id: string, surveyId: string) {
  return read<{ items: { id: string; full_name: string; title: string; mode: string; answers: Record<string, unknown> }[] }>(
    `/api/v1/consulting/projects/${id}/surveys/${surveyId}/responses`,
  );
}

export function submitInterviewerResponse(id: string, surveyId: string, body: Record<string, unknown>) {
  return read(`/api/v1/consulting/projects/${id}/surveys/${surveyId}/responses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getConsultingSurveyPublic(token: string) {
  return read<{
    id: string;
    title: string;
    customer_name: string;
    questions: ConsultingSurveyQuestion[];
    people: { id: string; full_name: string; title: string }[];
  }>(`/api/v1/consulting/s/${token}`, { skipAuthRedirect: true });
}

export function submitConsultingSurveyPublic(token: string, body: Record<string, unknown>) {
  return read(`/api/v1/consulting/s/${token}/responses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    skipAuthRedirect: true,
  });
}
