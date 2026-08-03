import { getStageTone, hrStageLabel, type StageTone } from "@/lib/labels";

type Props = {
  stage: string | null | undefined;
  /** Show stage label next to the dot (default true). */
  withLabel?: boolean;
  className?: string;
};

const TONE_TITLE: Record<StageTone, string> = {
  none: "",
  yellow: "Первичный / жёлтый",
  "green-1": "Ранний этап",
  "green-2": "Прогресс",
  "green-3": "Оценка заказчиком",
  "green-4": "Встреча",
  "green-5": "Оффер / выход",
  rejected: "Отказ",
};

export function StageMarker({ stage, withLabel = true, className = "" }: Props) {
  const tone = getStageTone(stage);
  const label = hrStageLabel(stage);
  const title = TONE_TITLE[tone] ? `${label} (${TONE_TITLE[tone]})` : label;

  return (
    <span className={`stage-marker ${className}`.trim()} title={title}>
      <span className={`stage-dot stage-dot-${tone}`} aria-hidden />
      {withLabel ? <span className="stage-marker-label">{label}</span> : null}
    </span>
  );
}
