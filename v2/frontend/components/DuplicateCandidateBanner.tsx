"use client";

import Link from "next/link";
import type { DupHit } from "@/lib/api";
import { hrStageLabel } from "@/lib/labels";

type Props = {
  hard: DupHit[];
  soft: DupHit[];
  onForceSave?: () => void;
  onDismiss?: () => void;
};

export function DuplicateCandidateBanner({ hard, soft, onForceSave, onDismiss }: Props) {
  if (!hard.length && !soft.length) return null;

  return (
    <div className={`dup-banner ${hard.length ? "dup-banner-hard" : "dup-banner-soft"}`}>
      {hard.length > 0 && (
        <>
          <p className="dup-title">Возможный дубликат (совпадение по телефону/email)</p>
          <ul className="dup-list">
            {hard.map((h) => (
              <li key={h.candidate_id}>
                <Link href={`/vacancies/${h.vacancy_id}?candidate=${h.candidate_id}`}>
                  {h.name}
                </Link>
                {" — "}
                {h.vacancy_title}
                {h.match_kind === "phone" ? " (телефон)" : " (email)"}
              </li>
            ))}
          </ul>
        </>
      )}
      {soft.length > 0 && (
        <>
          <p className="dup-title">Похожие кандидаты (совпадение ФИО)</p>
          <ul className="dup-list">
            {soft.map((s) => (
              <li key={s.candidate_id}>
                <Link href={`/vacancies/${s.vacancy_id}?candidate=${s.candidate_id}`}>
                  {s.name}
                </Link>
                {" — "}
                {s.vacancy_title}
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="dup-actions">
        {hard.length > 0 && onForceSave && (
          <button type="button" className="btn secondary small" onClick={onForceSave}>
            Создать всё равно
          </button>
        )}
        {onDismiss && (
          <button type="button" className="btn ghost small" onClick={onDismiss}>
            Закрыть
          </button>
        )}
      </div>
    </div>
  );
}

export function RelatedVacanciesPlaque({
  personId,
  siblings,
}: {
  personId?: string | null;
  siblings?: { candidate_id: string; vacancy_id: number; vacancy_title: string; hr_stage: string }[];
}) {
  if (!siblings?.length) return null;

  return (
    <div className="related-vacancies">
      <p className="related-title">Этот кандидат также на вакансиях:</p>
      <ul className="related-list">
        {siblings.map((s) => (
          <li key={s.candidate_id}>
            <Link href={`/vacancies/${s.vacancy_id}?candidate=${s.candidate_id}`}>
              {s.vacancy_title}
            </Link>
            <span className="muted"> — {hrStageLabel(s.hr_stage)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
