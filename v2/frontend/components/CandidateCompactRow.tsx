"use client";

import Link from "next/link";
import { Heart } from "lucide-react";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import type { CandidateListItem } from "@/lib/api";
import { clientStatusLabel, hrStageLabel } from "@/lib/labels";
import { stageBadgeTone } from "@/lib/groupCandidates";

type Props = {
  candidate: CandidateListItem;
  /** Показать причину «требует внимания» вместо этапа. */
  showAttentionReason?: boolean;
  subtitle?: string | null;
  /** v3: плотная строка ~56px для списков. */
  compact?: boolean;
};

function formatContact(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

export function CandidateCompactRow({
  candidate: c,
  showAttentionReason,
  subtitle,
  compact = true,
}: Props) {
  const vacancyLine =
    subtitle ||
    [c.vacancy_title || `Вакансия #${c.vacancy_id}`, c.client_name].filter(Boolean).join(" · ");
  const contact = compact ? null : formatContact(c.last_contact_at);
  const badgeLabel =
    showAttentionReason && c.attention_reason
      ? c.attention_reason
      : hrStageLabel(c.hr_stage);
  const badgeTone = stageBadgeTone(c.hr_stage, Boolean(showAttentionReason && c.attention_reason));
  const avatarSize = compact ? 40 : 52;

  return (
    <Link
      href={`/candidates/${c.id}`}
      className={`rec-row${compact ? " rec-row-compact" : ""}`}
    >
      <CandidateAvatar
        name={c.name || "—"}
        photoUrl={c.photo_url}
        gender={c.gender}
        size={avatarSize}
        className="rec-row-avatar"
      />
      <div className="rec-row-body">
        <div className="rec-row-top">
          <span className="rec-row-name">{c.name || "Без имени"}</span>
          {!compact && c.city ? <span className="rec-row-meta">{c.city}</span> : null}
        </div>
        <p className="rec-row-sub">{vacancyLine}</p>
        {contact ? <p className="rec-row-contact">Контакт: {contact}</p> : null}
      </div>
      <div className="rec-row-aside">
        {c.liked ? (
          <Heart size={14} fill="currentColor" strokeWidth={0} className="rec-row-liked" aria-label="Нравится" />
        ) : null}
        <span className={`rec-badge ${badgeTone}`}>{badgeLabel}</span>
        <span className="rec-row-client">{clientStatusLabel(c.client_status)}</span>
      </div>
    </Link>
  );
}
