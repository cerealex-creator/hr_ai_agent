import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { apiGet, type HistoryItem } from "@/lib/api";
import { formatLegacyStamp } from "@/lib/dates";

export default async function HistoryPage() {
  let items: HistoryItem[] = [];
  let error: string | null = null;

  try {
    items = await apiGet<HistoryItem[]>("/api/v1/history?limit=100");
  } catch (e) {
    error = e instanceof Error ? e.message : "API error";
  }

  return (
    <AppShell activePath="/history">
      <h1 className="page-title">История документов</h1>
      <p className="muted">Сохранённые версии пакетов документов по вакансиям.</p>
      {error ? <p className="warn">{error}</p> : null}

      <table>
        <thead>
          <tr>
            <th>Дата</th>
            <th>Название</th>
            <th>Превью</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <div>{formatLegacyStamp(item.created_at_legacy)}</div>
                <div className="row-meta">{item.source_filename}</div>
              </td>
              <td>
                <Link href={`/history/${item.id}`}>{item.title || "Без названия"}</Link>
              </td>
              <td className="preview-cell">{item.preview || "—"}</td>
            </tr>
          ))}
          {!items.length && !error ? (
            <tr>
              <td colSpan={3}>История пуста. Выполните import_json.</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </AppShell>
  );
}
