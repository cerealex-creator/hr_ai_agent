"use client";

import { HR_FUNNEL_STAGES, HR_STAGE_LABELS, isRejectionStage } from "@/lib/labels";

type Props = {
  stage: string;
  /** Enabled HR stages from vacancy schema (optional). */
  funnelStages?: readonly string[];
  /** Custom labels from vacancy schema (optional). */
  stageLabels?: Record<string, string>;
};

function progressIndex(stage: string, funnel: readonly string[]): number {
  return funnel.indexOf(stage);
}

/** Visual funnel rail for eye-testing stage progress (v2 only). */
export function StageProgress({ stage, funnelStages, stageLabels }: Props) {
  const funnel = funnelStages?.length ? funnelStages : HR_FUNNEL_STAGES;
  const labels = stageLabels || HR_STAGE_LABELS;
  const currentIdx = progressIndex(stage, funnel);
  const rejection = isRejectionStage(stage);
  const archive = stage === "archived";
  const label = labels[stage] || HR_STAGE_LABELS[stage] || stage;

  if (rejection || archive) {
    return (
      <div className="stage-progress stage-progress-terminal">
        <div className="stage-progress-current">{label}</div>
        <p className="muted stage-progress-hint">
          Вне основной воронки — шкала не применяется.
        </p>
      </div>
    );
  }

  return (
    <div className="stage-progress" aria-label={`Этап: ${label}`}>
      <div className="stage-progress-current">{label}</div>
      <ol className="stage-rail">
        {funnel.map((code, idx) => {
          const done = currentIdx >= 0 && idx < currentIdx;
          const current = idx === currentIdx;
          const cls = [
            "stage-rail-item",
            done ? "stage-rail-done" : "",
            current ? "stage-rail-current" : "",
          ]
            .filter(Boolean)
            .join(" ");
          const stepLabel = labels[code] || HR_STAGE_LABELS[code] || code;
          return (
            <li key={code} className={cls} title={stepLabel}>
              <span className="stage-rail-dot" />
              <span className="stage-rail-label">{stepLabel}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
