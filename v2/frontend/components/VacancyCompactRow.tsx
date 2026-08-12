import Link from "next/link";
import { outcomeLabel, type VacancyListItem } from "@/lib/api";
import { daysBetween, daysLabel, formatDateRu } from "@/lib/dates";
import { VacancyAvatar } from "@/components/VacancyAvatar";

type Props = {
  vacancy: VacancyListItem;
  mode: "active" | "archive";
};

export function VacancyCompactRow({ vacancy: v, mode }: Props) {
  const isArchive = mode === "archive";
  const days = daysBetween(v.created_at, isArchive ? v.closed_at : null);
  const sub = [v.client_name || "без клиента", `#${v.id}`].join(" · ");

  return (
    <Link href={`/vacancies/${v.id}`} className="rec-row rec-row-compact">
      <VacancyAvatar avatarKey={v.avatar_key} size={40} className="rec-row-avatar" />
      <div className="rec-row-body">
        <div className="rec-row-top">
          <span className="rec-row-name">{v.title || "Без названия"}</span>
        </div>
        <p className="rec-row-sub">{sub}</p>
      </div>
      <div className="rec-row-aside">
        <span className="rec-badge rec-badge-gray">
          {v.candidates_count} канд.
        </span>
        {isArchive ? (
          <>
            <span className="rec-row-client">
              {formatDateRu(v.created_at)} — {formatDateRu(v.closed_at)}
            </span>
            <span className="rec-row-client">{outcomeLabel(v.outcome)}</span>
          </>
        ) : (
          <span className="rec-row-client">
            с {formatDateRu(v.created_at)} · {daysLabel(days)}
          </span>
        )}
      </div>
    </Link>
  );
}
