import Link from "next/link";
import { CandidateCompactRow } from "@/components/CandidateCompactRow";
import { RecruitingShell } from "@/components/RecruitingShell";
import { apiGet, type CandidateListItem } from "@/lib/api";
import { hrStageLabel } from "@/lib/labels";

function formatReserveDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
}

function reserveSubtitle(c: CandidateListItem): string {
  const parts = [
    c.vacancy_title || `Вакансия #${c.vacancy_id}`,
    c.client_name,
    hrStageLabel(c.hr_stage),
  ].filter(Boolean);
  const added = formatReserveDate(c.talent_reserve_at);
  if (added) parts.push(`в резерве с ${added}`);
  if (c.ai_score != null) parts.push(`ИИ ${c.ai_score}/4`);
  return parts.join(" · ");
}

export default async function TalentReservePage() {
  let rows: CandidateListItem[] = [];
  let error: string | null = null;

  try {
    rows = await apiGet<CandidateListItem[]>("/api/v1/candidates?preset=talent_reserve");
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  return (
    <RecruitingShell activePath="/talent-reserve" title="Кадровый резерв">
      <p className="rec-empty" style={{ marginBottom: 16 }}>
        Кандидаты, отмеченные кнопкой «Добавить в резерв» в карточке. Они остаются на своих
        вакансиях — здесь только удобный список для повторного поиска.
      </p>

      {error ? <p className="warn">{error}</p> : null}

      {!error && rows.length === 0 ? (
        <div className="rec-empty">
          <p>Пока никого в резерве.</p>
          <p className="muted">
            Откройте карточку кандидата и нажмите «Добавить в резерв» в шапке карточки.
          </p>
          <p style={{ marginTop: 12 }}>
            <Link className="btn secondary" href="/candidates">
              К кандидатам
            </Link>
          </p>
        </div>
      ) : null}

      {rows.length > 0 ? (
        <>
          <p className="rec-empty" style={{ marginBottom: 12 }}>
            {rows.length}{" "}
            {rows.length === 1 ? "кандидат" : rows.length < 5 ? "кандидата" : "кандидатов"}
          </p>
          <div className="rec-list">
            {rows.map((c) => (
              <CandidateCompactRow
                key={c.id}
                candidate={c}
                subtitle={reserveSubtitle(c)}
                compact
              />
            ))}
          </div>
        </>
      ) : null}
    </RecruitingShell>
  );
}
