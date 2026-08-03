import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CandidateSearchPanel } from "@/components/CandidateSearchPanel";
import { apiGet, type CandidateListItem } from "@/lib/api";
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

  const qs = new URLSearchParams();
  if (clientId != null) qs.set("client_id", String(clientId));
  if (vacancyId != null) qs.set("vacancy_id", String(vacancyId));
  if (activeOnly) qs.set("active_vacancies_only", "true");
  if (hrStage) qs.set("hr_stage", hrStage);
  if (clientStatus) qs.set("client_status", clientStatus);
  if (preset) qs.set("preset", preset);

  let rows: CandidateListItem[] = [];
  let error: string | null = null;
  if (hasFilters) {
    try {
      rows = await apiGet<CandidateListItem[]>(`/api/v1/candidates?${qs.toString()}`);
    } catch (e) {
      error = e instanceof Error ? e.message : "Ошибка API";
    }
  }

  const heading = titleFor({ hr_stage: hrStage, client_status: clientStatus, preset });
  const back = statsBackHref({ clientId, vacancyId, activeOnly });

  return (
    <AppShell activePath={hasFilters ? "/stats" : "/candidates"}>
      {hasFilters ? (
        <Link className="back" href={back}>
          ← К статистике
        </Link>
      ) : null}
      <h1 className="page-title">{hasFilters ? heading : "Кандидаты"}</h1>
      {!hasFilters ? <CandidateSearchPanel /> : null}
      {hasFilters ? (
        <>
          <p className="muted">
            {rows.length} {rows.length === 1 ? "кандидат" : "кандидатов"}
            {activeOnly ? " · только вакансии в работе" : ""}
          </p>
          {error ? <p className="warn">{error}</p> : null}

          <table>
            <thead>
              <tr>
                <th>Имя</th>
                <th>Вакансия</th>
                <th>Клиент</th>
                <th>HR-этап</th>
                <th>Оценка заказчика</th>
                <th>Город</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/candidates/${c.id}`}>{c.name || "—"}</Link>
                  </td>
                  <td>
                    <Link href={`/vacancies/${c.vacancy_id}`}>
                      {c.vacancy_title || `#${c.vacancy_id}`}
                    </Link>
                  </td>
                  <td>{c.client_name || "—"}</td>
                  <td>{hrStageLabel(c.hr_stage)}</td>
                  <td>{clientStatusLabel(c.client_status)}</td>
                  <td>{c.city || "—"}</td>
                </tr>
              ))}
              {!rows.length && !error ? (
                <tr>
                  <td colSpan={6}>Нет кандидатов в этой выборке</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </>
      ) : (
        <p className="muted">Или откройте выборку из статистики / вакансии.</p>
      )}
    </AppShell>
  );
}
