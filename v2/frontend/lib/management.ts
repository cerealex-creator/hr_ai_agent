import { apiFetch, apiGet } from "@/lib/api";

export type MgmtGoalDimension = {
  id: string;
  code: string;
  pack_id?: string | null;
  title: string;
  icon?: string | null;
  default_weight_hint?: number | null;
  sort_order: number;
};

export type MgmtGoalDimensionLink = {
  dimension_id: string;
  code: string;
  title: string;
  icon?: string | null;
  is_primary: boolean;
};

export type MgmtGoal = {
  id: string;
  revision_id: string;
  title: string;
  weight?: number | null;
  metric_unit?: string | null;
  baseline_value?: number | null;
  baseline_date?: string | null;
  target_value?: number | null;
  target_date?: string | null;
  metric_source?: string | null;
  numeric_gap?: number | null;
  dimensions?: MgmtGoalDimensionLink[];
  status: string;
  stale: boolean;
  sort_order: number;
  scope?: string | null;
};

export type MgmtTask = {
  id: string;
  revision_id: string;
  title: string;
  deadline?: string | null;
  metric_target?: number | null;
  metric_unit?: string | null;
  status: string;
  stale: boolean;
  sort_order: number;
};

export type MgmtLink = {
  id: string;
  revision_id: string;
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  link_kind: string;
};

export type MgmtCurrentPosition = {
  id: string;
  revision_id: string;
  title: string;
  headcount: number;
  stale: boolean;
  sort_order: number;
};

export type MgmtOverview = {
  system: {
    id: string;
    organization_id: string;
    title?: string;
    kind?: string;
    parent_system_id?: string | null;
    status: string;
    draft_revision_id?: string | null;
  };
  goals: MgmtGoal[];
  inherited_goals?: MgmtGoal[];
  tasks: MgmtTask[];
  links: MgmtLink[];
  current_positions: MgmtCurrentPosition[];
  wizard?: { id: string; step: number; status: string } | null;
  warnings?: string[];
};

export type MgmtSystem = {
  id: string;
  organization_id: string;
  title: string;
  kind: string;
  parent_system_id?: string | null;
  is_archived: boolean;
  status: string;
  draft_revision_id?: string | null;
  published_revision_id?: string | null;
};

export type MgmtSystemsList = {
  systems: MgmtSystem[];
  active_system_id: string | null;
};

export type MgmtFlowGraph = {
  nodes: Array<{
    id: string;
    type?: string;
    position: { x: number; y: number };
    data: { label: string; entityType: string; entityId: string; status: string; stale: boolean };
  }>;
  edges: Array<{ id: string; source: string; target: string; label?: string }>;
};

export async function fetchMgmtOverview(): Promise<MgmtOverview> {
  return apiGet<MgmtOverview>("/api/v1/management/overview");
}

export async function fetchMgmtSystems(): Promise<MgmtSystemsList> {
  return apiGet<MgmtSystemsList>("/api/v1/management/systems");
}

export async function createMgmtSystem(payload: {
  title: string;
  kind?: "company" | "holding" | "demo";
  parent_system_id?: string | null;
  activate?: boolean;
}): Promise<MgmtSystem> {
  const res = await apiFetch("/api/v1/management/systems", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function activateMgmtSystem(systemId: string): Promise<MgmtSystem> {
  const res = await apiFetch(`/api/v1/management/systems/${systemId}/activate`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMgmtGraph(): Promise<MgmtFlowGraph> {
  return apiGet<MgmtFlowGraph>("/api/v1/management/graph");
}

export async function saveMgmtGraphLayout(
  items: Array<{ node_type: string; node_id: string; x: number; y: number }>
) {
  const res = await apiFetch("/api/v1/management/graph/layout", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<{ saved: number }>;
}

export async function fetchMgmtL3Preview(): Promise<MgmtL3Preview> {
  return apiGet<MgmtL3Preview>("/api/v1/management/l3-preview");
}

export async function fetchMgmtRoleDocuments(): Promise<MgmtRoleDocument[]> {
  return apiGet<MgmtRoleDocument[]>("/api/v1/management/role-documents");
}

export async function materializeMgmtRoleDocuments(roleId?: string) {
  const res = await apiFetch("/api/v1/management/role-documents/materialize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(roleId ? { role_id: roleId } : {}),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "object" && data.detail?.message
        ? data.detail.message
        : data.detail || `HTTP ${res.status}`
    );
  }
  return res.json();
}

export async function approveMgmtRoleDocument(documentId: string) {
  const res = await apiFetch(`/api/v1/management/role-documents/${documentId}/approve`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = data.detail;
    if (detail && typeof detail === "object") {
      const extra = detail.errors?.length ? `: ${detail.errors.slice(0, 3).join("; ")}` : "";
      throw new Error(`${detail.message || "Ошибка"}${extra}`);
    }
    throw new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
  }
  return res.json();
}

export async function addMgmtRoleDocumentLine(
  documentId: string,
  payload: {
    title: string;
    target_value?: number | null;
    metric_unit?: string | null;
    source_task_id?: string | null;
  }
) {
  const res = await apiFetch(`/api/v1/management/role-documents/${documentId}/lines`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail?.message || data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function polishMgmtRoleDocuments(opts?: { document_id?: string; use_ai?: boolean }) {
  const res = await apiFetch("/api/v1/management/role-documents/polish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_id: opts?.document_id ?? null,
      use_ai: opts?.use_ai ?? true,
    }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<{ updated_lines: number; documents: number; warnings: string[] }>;
}

export async function criticMgmtRoleDocuments(useLlm = false): Promise<MgmtCriticResult> {
  const q = useLlm ? "?use_llm=true" : "";
  const res = await apiFetch(`/api/v1/management/role-documents/critic${q}`, { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function publishMgmtRoleDocuments(opts?: {
  document_ids?: string[];
  use_llm_critic?: boolean;
}) {
  const res = await apiFetch("/api/v1/management/role-documents/publish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      document_ids: opts?.document_ids ?? null,
      use_llm_critic: opts?.use_llm_critic ?? false,
      force: false,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data as {
    ok: boolean;
    published_count: number;
    skipped: string[];
    critic: MgmtCriticResult | null;
  };
}

export async function fetchMgmtChangesSummary(): Promise<MgmtChangesSummary> {
  return apiGet<MgmtChangesSummary>("/api/v1/management/changes");
}

export async function draftMgmtTransitionPlan() {
  const res = await apiFetch("/api/v1/management/transition/draft", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<{
    ok: boolean;
    gap_items: number;
    steps_created: number;
    steps_total: number;
  }>;
}

export async function fetchMgmtTransitionSteps(): Promise<MgmtTransitionStep[]> {
  return apiGet<MgmtTransitionStep[]>("/api/v1/management/transition/steps");
}

export async function approveMgmtTransitionStep(stepId: string) {
  const res = await apiFetch(`/api/v1/management/transition/steps/${stepId}/approve`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail?.message || data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function rejectMgmtTransitionStep(stepId: string) {
  const res = await apiFetch(`/api/v1/management/transition/steps/${stepId}/reject`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail?.message || data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMgmtCoverage(): Promise<MgmtCoverageTracker> {
  return apiGet<MgmtCoverageTracker>("/api/v1/management/coverage");
}

export async function fetchMgmtRoleVacancyPreview(roleId: string) {
  return apiGet<{ ok: boolean; profile: Record<string, unknown>; warnings: string[] }>(
    `/api/v1/management/roles/${roleId}/vacancy-profile-preview`
  );
}

export async function fetchMgmtImpact(entityType: string, entityId: string) {
  return apiGet<{ items: Array<Record<string, unknown>>; stale_marked: number }>(
    `/api/v1/management/impact/${entityType}/${entityId}`
  );
}

export async function markMgmtImpactStale(entityType: string, entityId: string) {
  const res = await apiFetch(`/api/v1/management/impact/${entityType}/${entityId}/mark-stale`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<{ items: Array<Record<string, unknown>>; stale_marked: number }>;
}

export async function fetchMgmtGoalDimensions(): Promise<MgmtGoalDimension[]> {
  return apiGet<MgmtGoalDimension[]>("/api/v1/management/goal-dimensions");
}

export async function createMgmtGoal(payload: {
  title: string;
  weight?: number | null;
  metric_unit?: string | null;
  baseline_value?: number | null;
  baseline_date?: string | null;
  target_value?: number | null;
  target_date?: string | null;
  metric_source?: "owner" | "pack_hint" | null;
  dimension_codes?: string[];
  primary_dimension_code?: string | null;
}): Promise<MgmtGoal> {
  const res = await apiFetch("/api/v1/management/goals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function createMgmtTask(title: string): Promise<MgmtTask> {
  const res = await apiFetch("/api/v1/management/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function createMgmtLink(payload: {
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  link_kind: string;
}): Promise<MgmtLink> {
  const res = await apiFetch("/api/v1/management/links", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      typeof data?.detail === "object" && data.detail?.code === "GRAPH_CYCLE"
        ? "Цикл в связях — сохранение заблокировано"
        : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

export async function createMgmtPosition(title: string, headcount = 1): Promise<MgmtCurrentPosition> {
  const res = await apiFetch("/api/v1/management/current-positions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, headcount }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function resumeMgmtWizard() {
  const res = await apiFetch("/api/v1/management/wizard/resume", { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export type MgmtWizardState = {
  session: { id: string; step: number; status: string; payload?: Record<string, unknown> };
  step: number;
  questions: Array<{ key: string; text: string }>;
  answers: Array<{
    id: string;
    question_key: string;
    question_text: string;
    answer_text: string;
    sort_order: number;
  }>;
  interview?: { id: string; status: string } | null;
  positions: MgmtCurrentPosition[];
  business_profile?: MgmtBusinessProfile | null;
  goal_blocks?: MgmtGoalBlock[];
  skipped_blocks?: string[];
  industry_packs?: MgmtIndustryPack[];
  industry_pack_id?: string | null;
  inherited_goals?: MgmtGoal[];
  gap_report?: MgmtGapReport | null;
  goals: MgmtGoal[];
  warnings: string[];
};

export type MgmtIndustryPack = {
  id: string;
  title: string;
  version?: string | null;
  description?: string | null;
};

export type MgmtGapReport = {
  revision_id: string;
  summary: Record<string, number>;
  items: Array<{
    code: string;
    severity: string;
    title: string;
    message: string;
    entity_type?: string | null;
    entity_id?: string | null;
  }>;
};

export type MgmtRole = {
  id: string;
  revision_id: string;
  title: string;
  external_key?: string | null;
  status: string;
  stale: boolean;
  sort_order: number;
};

export type MgmtRoleAssignment = {
  id: string;
  revision_id: string;
  target_role_id: string;
  target_role_title: string;
  current_position_id: string;
  current_position_title: string;
  coverage: string;
  note?: string | null;
  stale: boolean;
};

export type MgmtImplementation = {
  roles: MgmtRole[];
  current_positions: MgmtCurrentPosition[];
  role_assignments: MgmtRoleAssignment[];
  gap_report: MgmtGapReport;
};

export type MgmtProcessMap = {
  id: string;
  revision_id: string;
  title: string;
  status: string;
  stale: boolean;
  sort_order: number;
};

export type MgmtGateSummary = {
  l0_pending: number;
  l1_pending: number;
  l2a_pending: number;
  l2b_pending: number;
  suggested_goals: number;
  suggested_tasks: number;
  process_maps: MgmtProcessMap[];
  roles: MgmtRole[];
};

export type MgmtL3Preview = {
  revision_id: string;
  is_preview: boolean;
  note: string;
  documents: Array<{
    role_id: string;
    role_title: string;
    role_status: string;
    external_key?: string | null;
    duties: Array<{
      title: string;
      process_map?: string | null;
      frequency?: string | null;
      step_id?: string | null;
    }>;
    checklist: Array<{ title: string; direction: string; from_step?: string | null }>;
    kpi_hints: string[];
    is_preview: boolean;
    approvable: boolean;
  }>;
  unassigned_steps: Array<{ title: string; process_map?: string | null; step_id?: string }>;
  summary: Record<string, number>;
};

export type MgmtRoleDocument = {
  id: string;
  revision_id: string;
  role_id: string;
  role_title: string;
  doc_kind: string;
  title: string;
  status: string;
  stale: boolean;
  lines: Array<{
    id: string;
    title: string;
    target_value?: number | null;
    metric_unit?: string | null;
    source_step_id?: string | null;
    source_task_id?: string | null;
    is_manual: boolean;
    sort_order: number;
    stale: boolean;
  }>;
};

export type MgmtCriticResult = {
  ok: boolean;
  blocking: Array<{ code: string; message: string }>;
  warnings: Array<{ code: string; message: string }>;
  sources: string[];
};

export type MgmtChangesSummary = {
  revision_id: string;
  documents_total: number;
  by_status: Record<string, number>;
  stale_documents: Array<{
    id: string;
    role_id: string;
    role_title: string;
    doc_kind: string;
    title: string;
    status: string;
  }>;
  stale_assignments: Array<{
    id: string;
    role_title: string;
    position_title: string;
    coverage: string;
  }>;
  stale_documents_count: number;
  stale_assignments_count: number;
};

export type MgmtTransitionStep = {
  id: string;
  revision_id: string;
  gap_item_id?: string | null;
  action_code: string;
  title: string;
  description?: string | null;
  horizon: string;
  status: string;
  stale: boolean;
  sort_order: number;
  meta?: Record<string, unknown>;
};

export type MgmtCoverageTracker = {
  revision_id: string;
  roles: Array<{
    role_id: string;
    role_title: string;
    instruction: boolean;
    checklist: boolean;
    kpi: boolean;
    assignment: boolean;
    instruction_status?: string | null;
    checklist_status?: string | null;
    kpi_status?: string | null;
  }>;
  summary: Record<string, number>;
};

export type MgmtBusinessProfile = {
  id: string;
  revision_id: string;
  industry_code?: string | null;
  industry_custom?: string | null;
  business_model?: string | null;
  market_type?: string | null;
  scale_band?: string | null;
  maturity_stage?: string | null;
  horizon_months?: number | null;
  priorities: string[];
  constraints_text?: string | null;
  sensitive_metrics_opt_out: boolean;
  optional_metrics: Record<string, unknown>;
  status: string;
};

export type MgmtBusinessProfileSchema = {
  industries: Array<{ code: string; label: string }>;
  business_models: Array<{ code: string; label: string }>;
  market_types: Array<{ code: string; label: string }>;
  scale_bands: Array<{ code: string; label: string }>;
  maturity_stages: Array<{ code: string; label: string }>;
  horizons: Array<{ months: number; label: string }>;
  priorities: Array<{ code: string; label: string }>;
};

export type MgmtGoalBlock = {
  code: string;
  title: string;
  subtitle: string;
  sort_order: number;
  status: string;
  questions: Array<{
    key: string;
    text: string;
    field_type: string;
    placeholder?: string | null;
    optional?: boolean;
    options?: string[];
  }>;
  answers: Array<{
    id: string;
    question_key: string;
    question_text: string;
    answer_text: string;
    sort_order: number;
  }>;
  goals: MgmtGoal[];
  goals_count: number;
  approved_count: number;
};

export type MgmtWizardGenerateResult = {
  ok: boolean;
  error?: string | null;
  message?: string | null;
  retryable?: boolean;
  goals_count?: number | null;
  tasks_count?: number | null;
  warnings?: string[];
};

export async function fetchMgmtWizardState(): Promise<MgmtWizardState> {
  return apiGet<MgmtWizardState>("/api/v1/management/wizard/state");
}

export async function completeMgmtWizardStep1(payload: {
  skipped?: boolean;
  import_text?: string | null;
}) {
  const res = await apiFetch("/api/v1/management/wizard/step/1", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function submitMgmtWizardAnswer(question_key: string, answer_text: string) {
  const res = await apiFetch("/api/v1/management/wizard/step/2/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_key, answer_text }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function generateMgmtWizardL0L1(): Promise<MgmtWizardGenerateResult> {
  const res = await apiFetch("/api/v1/management/wizard/step/2/generate", { method: "POST" });
  return res.json();
}

export async function approveMgmtWizardGoals() {
  const res = await apiFetch("/api/v1/management/wizard/step/2/approve-goals", { method: "POST" });
  return res.json();
}

export async function completeMgmtWizardStep2() {
  const res = await apiFetch("/api/v1/management/wizard/step/3/complete", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function completeMgmtWizardStep2Profile() {
  const res = await apiFetch("/api/v1/management/wizard/step/2/complete", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMgmtBusinessProfileSchema(): Promise<MgmtBusinessProfileSchema> {
  return apiGet<MgmtBusinessProfileSchema>("/api/v1/management/business-profile/schema");
}

export async function fetchMgmtBusinessProfile(): Promise<MgmtBusinessProfile> {
  return apiGet<MgmtBusinessProfile>("/api/v1/management/business-profile");
}

export async function saveMgmtBusinessProfile(payload: Partial<MgmtBusinessProfile>) {
  const res = await apiFetch("/api/v1/management/business-profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<MgmtBusinessProfile>;
}

export async function fetchMgmtGoalBlocks(): Promise<MgmtGoalBlock[]> {
  return apiGet<MgmtGoalBlock[]>("/api/v1/management/goal-blocks");
}

export async function submitMgmtGoalBlockAnswer(
  blockCode: string,
  question_key: string,
  answer_text: string
) {
  const res = await apiFetch(`/api/v1/management/goal-blocks/${blockCode}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_key, answer_text }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function generateMgmtGoalBlock(blockCode: string) {
  const res = await apiFetch(`/api/v1/management/goal-blocks/${blockCode}/generate`, { method: "POST" });
  return res.json();
}

export async function approveMgmtGoalBlock(blockCode: string, goal_ids: string[]) {
  const res = await apiFetch(`/api/v1/management/goal-blocks/${blockCode}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal_ids }),
  });
  return res.json();
}

export async function skipMgmtGoalBlock(blockCode: string) {
  const res = await apiFetch(`/api/v1/management/goal-blocks/${blockCode}/skip`, { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function updateMgmtGoal(
  goalId: string,
  payload: {
    title?: string;
    baseline_value?: number | null;
    target_value?: number | null;
    metric_unit?: string | null;
    metric_source?: string | null;
  }
) {
  const res = await apiFetch(`/api/v1/management/goals/${goalId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function approveMgmtGoal(goalId: string) {
  const res = await apiFetch(`/api/v1/management/goals/${goalId}/approve`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function approveMgmtTask(taskId: string) {
  const res = await apiFetch(`/api/v1/management/tasks/${taskId}/approve`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function approveAllMgmtGoalsDraft() {
  const res = await apiFetch("/api/v1/management/goals/approve-all-draft", { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function approveAllMgmtTasksDraft() {
  const res = await apiFetch("/api/v1/management/tasks/approve-all-draft", { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchMgmtIndustryPacks(): Promise<MgmtIndustryPack[]> {
  return apiGet<MgmtIndustryPack[]>("/api/v1/management/industry-packs");
}

export async function applyMgmtIndustryPack(packId: string) {
  const res = await apiFetch("/api/v1/management/industry-packs/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pack_id: packId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMgmtGapReport(): Promise<MgmtGapReport> {
  return apiGet<MgmtGapReport>("/api/v1/management/gap-report");
}

export async function fetchMgmtImplementation(): Promise<MgmtImplementation> {
  return apiGet<MgmtImplementation>("/api/v1/management/implementation");
}

export async function createMgmtRoleAssignment(payload: {
  target_role_id: string;
  current_position_id: string;
  coverage?: string;
  note?: string;
}) {
  const res = await apiFetch("/api/v1/management/role-assignments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function updateMgmtRoleAssignment(
  assignmentId: string,
  payload: { coverage?: string; note?: string; clear_note?: boolean }
) {
  const res = await apiFetch(`/api/v1/management/role-assignments/${assignmentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteMgmtRoleAssignment(assignmentId: string) {
  const res = await apiFetch(`/api/v1/management/role-assignments/${assignmentId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
}

export async function fetchMgmtGateSummary(): Promise<MgmtGateSummary> {
  return apiGet<MgmtGateSummary>("/api/v1/management/gates/summary");
}

function _gateError(data: unknown, status: number): Error {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (detail && typeof detail === "object" && detail !== null && "message" in detail) {
      const d = detail as { message: string; errors?: string[] };
      const extra = d.errors?.length ? `: ${d.errors.slice(0, 3).join("; ")}` : "";
      return new Error(`${d.message}${extra}`);
    }
    if (typeof detail === "string") return new Error(detail);
  }
  return new Error(`HTTP ${status}`);
}

export async function approveMgmtGate(entityType: string, entityId: string) {
  const res = await apiFetch("/api/v1/management/gates/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_type: entityType, entity_id: entityId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw _gateError(data, res.status);
  }
  return res.json();
}

export async function rejectMgmtGate(entityType: string, entityId: string) {
  const res = await apiFetch("/api/v1/management/gates/reject", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entity_type: entityType, entity_id: entityId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw _gateError(data, res.status);
  }
  return res.json();
}

export async function approveMgmtL2aAll() {
  const res = await apiFetch("/api/v1/management/gates/l2a/approve-all", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw _gateError(data, res.status);
  }
  return res.json();
}

export async function approveMgmtL2bAll() {
  const res = await apiFetch("/api/v1/management/gates/l2b/approve-all", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw _gateError(data, res.status);
  }
  return res.json();
}

export async function completeMgmtWizardStep4() {
  const res = await apiFetch("/api/v1/management/wizard/step/4/complete", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function completeMgmtWizardStep5() {
  const res = await apiFetch("/api/v1/management/wizard/step/5/complete", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
