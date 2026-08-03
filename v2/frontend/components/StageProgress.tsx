"use client";

import { HR_FUNNEL_STAGES, HR_STAGE_LABELS, isRejectionStage } from "@/lib/labels";

type Props = {
  stage: string;
};

function progressIndex(stage: string): number {
  const idx = HR_FUNNEL_STAGES.indexOf(stage as (typeof HR_FUNNEL_STAGES)[number]);
  return idx;
}

/** Visual funnel rail for eye-testing stage progress (v2 only). */
export function StageProgress({ stage }: Props) {
  const currentIdx = progressIndex(stage);
  const rejection = isRejectionStage(stage);
  const archive = stage === "archived";
  const label = HR_STAGE_LABELS[stage] || stage;

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
        {HR_FUNNEL_STAGES.map((code, idx) => {
          const done = currentIdx >= 0 && idx < currentIdx;
          const current = idx === currentIdx;
          const cls = [
            "stage-rail-item",
            done ? "stage-rail-done" : "",
            current ? "stage-rail-current" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <li key={code} className={cls} title={HR_STAGE_LABELS[code]}>
              <span className="stage-rail-dot" />
              <span className="stage-rail-label">{HR_STAGE_LABELS[code]}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
