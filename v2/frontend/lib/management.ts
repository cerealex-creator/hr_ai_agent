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
    status: string;
    draft_revision_id?: string | null;
  };
  goals: MgmtGoal[];
  tasks: MgmtTask[];
  links: MgmtLink[];
  current_positions: MgmtCurrentPosition[];
  wizard?: { id: string; step: number; status: string } | null;
  warnings?: string[];
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

export async function fetchMgmtGraph(): Promise<MgmtFlowGraph> {
  return apiGet<MgmtFlowGraph>("/api/v1/management/graph");
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
