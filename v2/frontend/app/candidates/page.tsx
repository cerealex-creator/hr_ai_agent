import Link from "next/link";
import { CandidatesGroupedList } from "@/components/CandidatesGroupedList";
import { CandidateSearchPanel } from "@/components/CandidateSearchPanel";
import { RecruitingShell } from "@/components/RecruitingShell";
import { RecruitingToolbar } from "@/components/RecruitingToolbar";
import { apiGet, type CandidateListItem } from "@/lib/api";
import { groupCandidatesByStage } from "@/lib/groupCandidates";
import { clientStatusLabel, hrStageLabel } from "@/lib/labels";

type Props = {
  searchParams: Promise<{
    client?: string;
    vacancy?: string;
    scope?: string;
    hr_stage?: string;
    client_status?: string;
    preset?: string;
  }>;
};

function titleFor(opts: {
  hr_stage?: string;
  client_status?: string;
  preset?: string;
}): string {
  if (opts.hr_stage) return `Этап: ${hrStageLabel(opts.hr_stage)}`;
  if (opts.client_status) {
    return `Оценка заказчика: ${clientStatusLabel(opts.client_status)}`;
  }
  if (opts.preset === "sent_to_client") return "Отправлены заказчику";
  if (opts.preset === "in_client_zone") return "Сейчас в зоне заказчика+";
  if (opts.preset === "hires") return "Выходы / стажировки";
  if (opts.preset === "attention") return "Требуют внимания";
  return "Кандидаты";
}

function statsBackHref(opts: {
  clientId: number | null;
  vacancyId: number | null;
  activeOnly: boolean;
}): string {
  const params = new URLSearchParams();
  if (opts.clientId != null) params.set("client", String(opts.clientId));
  if (opts.vacancyId != null) params.set("vacancy", String(opts.vacancyId));
  if (opts.activeOnly) params.set("scope", "active");
  const q = params.toString();
  return q ? `/stats?${q}` : "/stats";
}

export default async function CandidatesListPage({ searchParams }: Props) {
  const sp = await searchParams;
  const clientId = sp.client && /^\d+$/.test(sp.client) ? Number(sp.client) : null;
  const vacancyId = sp.vacancy && /^\d+$/.test(sp.vacancy) ? Number(sp.vacancy) : null;
  const activeOnly = sp.scope === "active";
  const hrStage = sp.hr_stage?.trim() || undefined;
  const clientStatus = sp.client_status?.trim() || undefined;
  const preset = sp.preset?.trim() || undefined;
  const hasFilters = Boolean(clientId || vacancyId || hrStage || clientStatus || preset || activeOnly);
  const hubMode = !hasFilters;

  const qs = new URLSearchParams();
  if (clientId != null) qs.set("client_id", String(clientId));
  if (vacancyId != null) qs.set("vacancy_id", String(vacancyId));
  if (activeOnly) qs.set("active_vacancies_only", "true");
  if (hrStage) qs.set("hr_stage", hrStage);
  if (clientStatus) qs.set("client_status", clientStatus);
  if (preset) qs.set("preset", preset);

  let rows: CandidateListItem[] = [];
  let error: string | null = null;

  try {
    if (hubMode) {
      rows = await apiGet<CandidateListItem[]>(
        "/api/v1/candidates?active_vacancies_only=true",
      );
    } else {
      rows = await apiGet<CandidateListItem[]>(`/api/v1/candidates?${qs.toString()}`);
    }
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  const groups = groupCandidatesByStage(rows);
  const heading = titleFor({ hr_stage: hrStage, client_status: clientStatus, preset });
  const back = statsBackHref({ clientId, vacancyId, activeOnly });
  const filterHref = hasFilters ? back : "/stats";

  return (
    <RecruitingShell
      activePath="/candidates"
      title={hubMode ? "Кандидаты" : heading}
      toolbar={<RecruitingToolbar filterHref={filterHref} />}
    >
      {hasFilters && preset !== "attention" ? (
        <Link className="rec-back" href={back}>
          ← К статистике
        </Link>
      ) : null}

      {!hubMode ? (
        <p className="rec-empty" style={{ marginBottom: 16 }}>
          {rows.length} {rows.length === 1 ? "кандидат" : "кандидатов"}
          {activeOnly ? " · только вакансии в работе" : ""}
        </p>
      ) : null}

      {error ? <p className="warn">{error}</p> : null}

      <CandidatesGroupedList
        groups={groups}
        showAttentionReason={preset === "attention" || hubMode}
        emptyMessage={error ? "Не удалось загрузить список" : "Нет кандидатов в этой выборке"}
      />

      {hubMode ? (
        <section id="cand-search" className="rec-search-section">
          <h2>Расширенный поиск</h2>
          <CandidateSearchPanel />
        </section>
      ) : null}
    </RecruitingShell>
  );
}
