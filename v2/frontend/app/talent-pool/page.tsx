import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";
import { apiGet, type TalentPoolEntry } from "@/lib/api";

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
}

export default async function TalentPoolPage() {
  let rows: TalentPoolEntry[] = [];
  let error: string | null = null;

  try {
    rows = await apiGet<TalentPoolEntry[]>("/api/v1/talent-pool");
  } catch (e) {
    if (e instanceof Error && e.message.includes("403")) {
      error = "Функция «Талант-база» не включена. Включите в Настройки → Функции.";
    } else {
      error = e instanceof Error ? e.message : "Ошибка API";
    }
  }

  return (
    <RecruitingShell activePath="/talent-pool" title="Талант-база">
      <p className="rec-empty" style={{ marginBottom: 16 }}>
        Резюме из внешних источников — не привязаны к вакансиям. Импортируйте PDF/DOCX или
        добавьте вручную, затем «Взять в работу» на вакансию.
      </p>

      {error ? <p className="warn">{error}</p> : null}

      {!error && rows.length === 0 ? (
        <div className="rec-empty">
          <p>Пока пусто.</p>
          <p className="muted">
            Загрузите резюме через импорт или добавьте вручную.
          </p>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <>
          <p className="rec-empty" style={{ marginBottom: 12 }}>
            {rows.length} {rows.length === 1 ? "запись" : rows.length < 5 ? "записи" : "записей"}
          </p>
          <div className="rec-list">
            {rows.map((entry) => (
              <div key={entry.id} className="pool-row">
                <div className="pool-row-name">{entry.display_name || "Без имени"}</div>
                <div className="pool-row-meta">
                  {entry.match_phone && <span>{entry.match_phone}</span>}
                  {entry.match_email && <span>{entry.match_email}</span>}
                  {entry.source_filename && (
                    <span className="muted">{entry.source_filename}</span>
                  )}
                  {entry.created_at && (
                    <span className="muted">{formatDate(entry.created_at)}</span>
                  )}
                </div>
                {entry.tags.length > 0 && (
                  <div className="pool-row-tags">
                    {entry.tags.map((t) => (
                      <span key={t} className="cand-tag">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </RecruitingShell>
  );
}
