import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { DocumentBlock } from "@/components/DocumentBlock";
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

  const keys = item ? Object.keys(item.documents_snapshot || {}) : [];

  return (
    <AppShell activePath="/history">
      <Link className="back" href="/history">
        ← К истории
      </Link>
      {error ? <p className="warn">{error}</p> : null}
      {item ? (
        <>
          <h1 className="page-title">{item.title || "Без названия"}</h1>
          <p className="muted">
            {formatLegacyStamp(item.created_at_legacy)} · {item.source_filename}
          </p>

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
    </AppShell>
  );
}
