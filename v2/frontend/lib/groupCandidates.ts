/** Группировка кандидатов для компактного списка. */

import type { CandidateListItem } from "@/lib/api";
import {
  HR_FUNNEL_STAGES,
  REJECTION_STAGES,
  hrStageLabel,
  isRejectionStage,
} from "@/lib/labels";

export type CandidateGroup = {
  key: string;
  title: string;
  tone: "attention" | "active" | "rejected" | "neutral";
  items: CandidateListItem[];
};

const STAGE_ORDER = [
  ...HR_FUNNEL_STAGES,
  "archived",
  ...Array.from(REJECTION_STAGES),
];

export function groupCandidatesByStage(rows: CandidateListItem[]): CandidateGroup[] {
  const attention = rows.filter((r) => Boolean(r.attention_reason?.trim()));
  const attentionIds = new Set(attention.map((r) => r.id));

  const groups: CandidateGroup[] = [];
  if (attention.length) {
    groups.push({
      key: "attention",
      title: "Требуют внимания",
      tone: "attention",
      items: attention,
    });
  }

  const byStage = new Map<string, CandidateListItem[]>();
  for (const row of rows) {
    if (attentionIds.has(row.id)) continue;
    const stage = row.hr_stage || "resume_screening";
    const bucket = byStage.get(stage) || [];
    bucket.push(row);
    byStage.set(stage, bucket);
  }

  for (const stage of STAGE_ORDER) {
    const items = byStage.get(stage);
    if (!items?.length) continue;
    groups.push({
      key: stage,
      title: hrStageLabel(stage),
      tone: isRejectionStage(stage) ? "rejected" : "active",
      items,
    });
    byStage.delete(stage);
  }

  for (const [stage, items] of byStage.entries()) {
    if (!items.length) continue;
    groups.push({
      key: stage,
      title: hrStageLabel(stage),
      tone: "neutral",
      items,
    });
  }

  return groups;
}

/** CSS-модификатор бейджа этапа (rec-badge-*). */
export function stageBadgeTone(stage: string, attention?: boolean): string {
  if (attention) return "rec-badge-attention";
  if (isRejectionStage(stage)) return "rec-badge-orange";
  if (stage === "interview_scheduled" || stage === "interview_done" || stage === "client_meeting") {
    return "rec-badge-blue";
  }
  if (stage === "offer" || stage === "started_work" || stage === "internship") {
    return "rec-badge-green";
  }
  if (stage === "client_review" || stage === "primary_contact") {
    return "rec-badge-teal";
  }
  return "rec-badge-gray";
}
