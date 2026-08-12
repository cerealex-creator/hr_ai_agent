import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";
import { DocumentBlock } from "@/components/DocumentBlock";
import { HistoryApplyButton } from "@/components/HistoryApplyButton";
import { docLabel, apiGet, type HistoryDetail } from "@/lib/api";
import { formatLegacyStamp } from "@/lib/dates";

type Props = { params: Promise<{ id: string }> };

export default async function HistoryDetailPage({ params }: Props) {
  const { id } = await params;
  let item: HistoryDetail | null = null;
  let error: string | null = null;

  try {
    item = await apiGet<HistoryDetail>(`/api/v1/history/${id}`);
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  const keys = item
    ? Object.keys(item.documents_snapshot || {}).filter(
        (k) => !["meeting_brief", "meeting_transcript", "conflicts", "source_label"].includes(k),
      )
    : [];

  return (
    <RecruitingShell activePath="/history">
      <div className="rec-card">
      <Link className="back" href="/history">
        ← К истории
      </Link>
      {error ? <p className="warn">{error}</p> : null}
      {item ? (
        <>
          <h1 className="page-title">{item.title || "Без названия"}</h1>
          <p className="muted">
            {formatLegacyStamp(item.created_at_legacy)} · {item.source_filename}
            {item.vacancy_id ? ` · вакансия #${item.vacancy_id}` : ""}
          </p>

          <HistoryApplyButton generationId={id} defaultVacancyId={item.vacancy_id ?? null} />

          <div className="doc-stack">
            {keys.map((key) => (
              <DocumentBlock
                key={key}
                docKey={key}
                title={docLabel(key)}
                value={item.documents_snapshot[key]}
              />
            ))}
            {!keys.length ? <p className="muted">Снимок пуст</p> : null}
          </div>
        </>
      ) : null}
      </div>
    </RecruitingShell>
  );
}
