import Link from "next/link";
import { CandidateAvatar } from "@/components/CandidateAvatar";

export type DashboardAttention = {
  id: string;
  name: string;
  vacancy_id: number;
  vacancy_title?: string | null;
  reason?: string | null;
  photo_url?: string | null;
  gender?: string | null;
};

type Props = {
  items: DashboardAttention[];
};

export function DashboardQueue({ items }: Props) {
  if (!items.length) {
    return <p className="rec-empty">На сегодня всё закрыто — новых задач нет.</p>;
  }

  return (
    <div className="rec-dash-queue">
      {items.map((item) => {
        const meta = [item.reason, item.vacancy_title].filter(Boolean).join(" · ");
        return (
          <Link key={item.id} href={`/candidates/${item.id}`} className="rec-row rec-row-compact rec-dash-row">
            <CandidateAvatar
              name={item.name}
              photoUrl={item.photo_url}
              gender={item.gender}
              size={40}
              className="rec-row-avatar"
            />
            <div className="rec-row-body">
              <div className="rec-row-top">
                <span className="rec-row-name">{item.name}</span>
              </div>
              {meta ? <p className="rec-row-sub">{meta}</p> : null}
            </div>
            <span className="rec-dash-open">Открыть</span>
          </Link>
        );
      })}
    </div>
  );
}
