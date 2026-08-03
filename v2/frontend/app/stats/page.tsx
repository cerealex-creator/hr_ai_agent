import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import {
  apiGet,
  type ClientItem,
  type FunnelStats,
  type VacancyListItem,
} from "@/lib/api";
import { clientStatusLabel, hrStageLabel } from "@/lib/labels";
import { WarrantyRegistry } from "@/components/WarrantyRegistry";

type Props = {
  searchParams: Promise<{
    client?: string;
    vacancy?: string;
    scope?: string;
    period?: string;
  }>;
};

type HhStats = {
  viewed: number;
  ai_score_gt2: number;
  ai_low: number;
  recruiter_reject: number;
  shortlist: number;
  in_funnel: number;
  jobs_completed: number;
};

type ActivityStats = {
  period: string;
  period_from: string;
  period_to: string;
  candidates_added: number;
  stage_changes: number;
  jobs: number;
  series: {
    bucket: string;
    candidates_added: number;
    stage_changes: number;
    jobs: number;
  }[];
};

const HR_ORDER = [
  "resume_screening",
  "primary_contact",
  "interview_scheduled",
  "interview_done",
  "test_task",
  "client_review",
  "client_pause",
  "client_meeting",
  "offer",
  "internship",
  "started_work",
  "rejected_hr",
  "rejected_client",
  "rejected_candidate",
  "rejected",
  "archived",
];

const PERIODS: { id: string; label: string }[] = [
  { id: "day", label: "День" },
  { id: "week", label: "Неделя" },
  { id: "month", label: "Месяц" },
  { id: "quarter", label: "Квартал" },
  { id: "half_year", label: "Полугодие" },
  { id: "year", label: "Год" },
];

function hrefFor(opts: {
  clientId: number | null;
  vacancyId: number | null;
  scope: string;
  period: string;
}): string {
  const params = new URLSearchParams();
  if (opts.clientId != null) params.set("client", String(opts.clientId));
  if (opts.vacancyId != null) params.set("vacancy", String(opts.vacancyId));
  if (opts.scope === "active") params.set("scope", "active");
  if (opts.period && opts.period !== "month") params.set("period", opts.period);
  const q = params.toString();
  return q ? `/stats?${q}` : "/stats";
}

function candidatesHref(opts: {
  clientId: number | null;
  vacancyId: number | null;
  scope: string;
  preset?: string;
  hr_stage?: string;
  client_status?: string;
}): string {
  const params = new URLSearchParams();
  if (opts.clientId != null) params.set("client", String(opts.clientId));
  if (opts.vacancyId != null) params.set("vacancy", String(opts.vacancyId));
  if (opts.scope === "active") params.set("scope", "active");
  if (opts.preset) params.set("preset", opts.preset);
  if (opts.hr_stage) params.set("hr_stage", opts.hr_stage);
  if (opts.client_status) params.set("client_status", opts.client_status);
  const q = params.toString();
  return q ? `/candidates?${q}` : "/candidates";
}

function StatLink({
  href,
  value,
  label,
}: {
  href: string;
  value: number;
  label: string;
}) {
  return (
    <Link href={href} className="stat stat-link">
      <strong>{value}</strong>
      <span>{label}</span>
    </Link>
  );
}

function Bar({ count, max }: { count: number; max: number }) {
  const pct = max > 0 ? Math.max(4, Math.round((count / max) * 100)) : 0;
  return (
    <div className="bar-track" aria-hidden>
      <div className="bar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function MiniChart({
  series,
}: {
  series: ActivityStats["series"];
}) {
  if (!series.length) {
    return <p className="muted">Нет событий за выбранный период.</p>;
  }
  const max = Math.max(
    1,
    ...series.map((s) => s.candidates_added + s.stage_changes + s.jobs),
  );
  return (
    <div className="activity-chart" role="img" aria-label="Активность по периоду">
      {series.map((s) => {
        const total = s.candidates_added + s.stage_changes + s.jobs;
        const h = Math.max(total > 0 ? 8 : 2, Math.round((total / max) * 120));
        const cH = total ? Math.round((s.candidates_added / total) * h) : 0;
        const stH = total ? Math.round((s.stage_changes / total) * h) : 0;
        const jH = Math.max(0, h - cH - stH);
        return (
          <div key={s.bucket} className="activity-col" title={`${s.bucket}: +${s.candidates_added} канд., ${s.stage_changes} этапов, ${s.jobs} задач`}>
            <div className="activity-stack" style={{ height: h }}>
              <span className="activity-seg activity-seg-jobs" style={{ height: jH }} />
              <span className="activity-seg activity-seg-stages" style={{ height: stH }} />
              <span className="activity-seg activity-seg-cands" style={{ height: cH }} />
            </div>
            <div className="activity-label">{s.bucket.slice(-5)}</div>
          </div>
        );
      })}
    </div>
  );
}

export default async function StatsPage({ searchParams }: Props) {
  const { client, vacancy, scope, period: periodRaw } = await searchParams;
  const clientId = client && /^\d+$/.test(client) ? Number(client) : null;
  const vacancyId = vacancy && /^\d+$/.test(vacancy) ? Number(vacancy) : null;
  const activeOnly = scope === "active";
  const period = PERIODS.some((p) => p.id === periodRaw) ? (periodRaw as string) : "month";

  let stats: FunnelStats | null = null;
  let hh: HhStats | null = null;
  let activity: ActivityStats | null = null;
  let clients: ClientItem[] = [];
  let vacancies: VacancyListItem[] = [];
  let error: string | null = null;

  const qs = new URLSearchParams();
  if (clientId != null) qs.set("client_id", String(clientId));
  if (vacancyId != null) qs.set("vacancy_id", String(vacancyId));
  if (activeOnly) qs.set("active_vacancies_only", "true");

  const actQs = new URLSearchParams(qs);
  actQs.set("period", period);

  try {
    const vacListQs = new URLSearchParams();
    if (clientId != null) vacListQs.set("client_id", String(clientId));
    if (activeOnly) vacListQs.set("active", "true");

    [stats, hh, activity, clients, vacancies] = await Promise.all([
      apiGet<FunnelStats>(`/api/v1/stats/funnel?${qs.toString()}`),
      apiGet<HhStats>(`/api/v1/stats/hh?${qs.toString()}`),
      apiGet<ActivityStats>(`/api/v1/stats/activity?${actQs.toString()}`),
      apiGet<ClientItem[]>("/api/v1/clients"),
      apiGet<VacancyListItem[]>(
        `/api/v1/vacancies${vacListQs.toString() ? `?${vacListQs}` : ""}`,
      ),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  const stageMap = new Map(stats?.by_hr_stage.map((s) => [s.stage, s.count]) || []);
  const orderedStages = [
    ...HR_ORDER.filter((s) => stageMap.has(s)),
    ...[...stageMap.keys()].filter((s) => !HR_ORDER.includes(s)),
  ];
  const maxStage = Math.max(1, ...[...stageMap.values()]);
  const maxStatus = Math.max(1, ...(stats?.by_client_status.map((s) => s.count) || [1]));
  const selectedName = clients.find((c) => c.id === clientId)?.name;
  const selectedVacancy = vacancies.find((v) => v.id === vacancyId);

  const linkBase = {
    clientId,
    vacancyId,
    scope: activeOnly ? "active" : "all",
    period,
  };

  return (
    <AppShell activePath="/stats">
      <h1 className="page-title">Статистика</h1>
      <p className="muted">Сводка по вакансиям, кандидатам и эффективности HH.</p>
      {error ? <p className="warn">{error}</p> : null}

      <div className="filter-row">
        <span className="filter-label">Клиент</span>
        <div className="chip-row">
          <Link
            href={hrefFor({ ...linkBase, clientId: null, vacancyId: null })}
            className={clientId == null ? "chip chip-active" : "chip"}
          >
            Все
          </Link>
          {clients.map((c) => (
            <Link
              key={c.id}
              href={hrefFor({ ...linkBase, clientId: c.id, vacancyId: null })}
              className={clientId === c.id ? "chip chip-active" : "chip"}
            >
              {c.name}
            </Link>
          ))}
        </div>
      </div>

      <div className="filter-row">
        <span className="filter-label">Вакансия</span>
        <div className="chip-row">
          <Link
            href={hrefFor({ ...linkBase, vacancyId: null })}
            className={vacancyId == null ? "chip chip-active" : "chip"}
          >
            Все (общее)
          </Link>
          {vacancies.map((v) => (
            <Link
              key={v.id}
              href={hrefFor({ ...linkBase, vacancyId: v.id, clientId: v.client_id ?? clientId })}
              className={vacancyId === v.id ? "chip chip-active" : "chip"}
            >
              {v.title}
            </Link>
          ))}
        </div>
      </div>

      <div className="tabs" role="tablist">
        <Link
          href={hrefFor({ ...linkBase, scope: "all" })}
          className={!activeOnly ? "tab tab-active" : "tab"}
        >
          Все вакансии
        </Link>
        <Link
          href={hrefFor({ ...linkBase, scope: "active" })}
          className={activeOnly ? "tab tab-active" : "tab"}
        >
          Только в работе
        </Link>
      </div>

      {selectedName || selectedVacancy ? (
        <p className="muted section-note">
          {selectedVacancy
            ? `Вакансия: ${selectedVacancy.title}`
            : selectedName
              ? `Клиент: ${selectedName}`
              : null}
        </p>
      ) : null}

      {stats ? (
        <>
          <div className="stats">
            <div className="stat">
              <strong>{stats.vacancies_active}</strong>
              <span>вакансий в работе</span>
            </div>
            {!activeOnly ? (
              <div className="stat">
                <strong>{stats.vacancies_archive}</strong>
                <span>в архиве</span>
              </div>
            ) : null}
            <StatLink
              href={candidatesHref(linkBase)}
              value={stats.candidates_total}
              label="кандидатов"
            />
            <StatLink
              href={candidatesHref({ ...linkBase, preset: "sent_to_client" })}
              value={stats.sent_to_client ?? 0}
              label="отправлены заказчику"
            />
            <StatLink
              href={candidatesHref({ ...linkBase, preset: "in_client_zone" })}
              value={stats.in_client_zone}
              label="сейчас в зоне заказчика+"
            />
            <StatLink
              href={candidatesHref({ ...linkBase, preset: "hires" })}
              value={stats.hires}
              label="выходы / стажировки"
            />
          </div>

          <h2>Воронка HR</h2>
          <table>
            <thead>
              <tr>
                <th>Этап</th>
                <th>Кол-во</th>
                <th>Доля</th>
              </tr>
            </thead>
            <tbody>
              {orderedStages.map((stage) => {
                const count = stageMap.get(stage) || 0;
                return (
                  <tr key={stage}>
                    <td>
                      <Link
                        className="row-link"
                        href={candidatesHref({ ...linkBase, hr_stage: stage })}
                      >
                        {hrStageLabel(stage)}
                      </Link>
                    </td>
                    <td>
                      <Link
                        className="row-link"
                        href={candidatesHref({ ...linkBase, hr_stage: stage })}
                      >
                        {count}
                      </Link>
                    </td>
                    <td className="bar-cell">
                      <Bar count={count} max={maxStage} />
                    </td>
                  </tr>
                );
              })}
              {!orderedStages.length ? (
                <tr>
                  <td colSpan={3}>Нет кандидатов</td>
                </tr>
              ) : null}
            </tbody>
          </table>

          <h2>Оценка заказчика</h2>
          <p className="muted">
            Сначала — сколько кандидатов дошли до оценки заказчика; ниже — их текущие статусы.
          </p>
          <div className="stats">
            <StatLink
              href={candidatesHref({ ...linkBase, preset: "sent_to_client" })}
              value={stats.sent_to_client ?? 0}
              label="отправлено на оценку"
            />
          </div>
          <table>
            <thead>
              <tr>
                <th>Статус заказчика</th>
                <th>Кол-во</th>
                <th>Доля</th>
              </tr>
            </thead>
            <tbody>
              {(stats.by_client_status || []).map((row) => (
                <tr key={row.stage}>
                  <td>
                    <Link
                      className="row-link"
                      href={candidatesHref({ ...linkBase, client_status: row.stage })}
                    >
                      {clientStatusLabel(row.stage)}
                    </Link>
                  </td>
                  <td>
                    <Link
                      className="row-link"
                      href={candidatesHref({ ...linkBase, client_status: row.stage })}
                    >
                      {row.count}
                    </Link>
                  </td>
                  <td className="bar-cell">
                    <Bar count={row.count} max={maxStatus} />
                  </td>
                </tr>
              ))}
              {!stats.by_client_status?.length ? (
                <tr>
                  <td colSpan={3}>Пока никто не отправлен заказчику</td>
                </tr>
              ) : null}
            </tbody>
          </table>

          <h2>Эффективность поиска HH (ИИ)</h2>
          <p className="muted">
            Холодный поиск: просмотренные резюме, оценки ИИ, shortlist и перевод в воронку.
          </p>
          {hh ? (
            <div className="stats">
              <div className="stat">
                <strong>{hh.viewed}</strong>
                <span>просмотрено резюме</span>
              </div>
              <div className="stat">
                <strong>{hh.ai_score_gt2}</strong>
                <span>оценка ИИ &gt; 2</span>
              </div>
              <div className="stat">
                <strong>{hh.shortlist}</strong>
                <span>в shortlist</span>
              </div>
              <div className="stat">
                <strong>{hh.in_funnel}</strong>
                <span>одобрено → воронка</span>
              </div>
              <div className="stat">
                <strong>{hh.ai_low}</strong>
                <span>автоотсев ИИ (≤1)</span>
              </div>
              <div className="stat">
                <strong>{hh.recruiter_reject}</strong>
                <span>отклонил рекрутер</span>
              </div>
              <div className="stat">
                <strong>{hh.jobs_completed}</strong>
                <span>завершённых поисков</span>
              </div>
            </div>
          ) : null}

          <h2>Активность по периоду</h2>
          <div className="chip-row" style={{ marginBottom: "0.75rem" }}>
            {PERIODS.map((p) => (
              <Link
                key={p.id}
                href={hrefFor({ ...linkBase, period: p.id })}
                className={period === p.id ? "chip chip-active" : "chip"}
              >
                {p.label}
              </Link>
            ))}
          </div>
          {activity ? (
            <>
              <div className="stats">
                <div className="stat">
                  <strong>{activity.candidates_added}</strong>
                  <span>новых кандидатов</span>
                </div>
                <div className="stat">
                  <strong>{activity.stage_changes}</strong>
                  <span>смен этапа</span>
                </div>
                <div className="stat">
                  <strong>{activity.jobs}</strong>
                  <span>фоновых задач</span>
                </div>
              </div>
              <div className="activity-legend muted">
                <span className="activity-dot activity-seg-cands" /> кандидаты{" "}
                <span className="activity-dot activity-seg-stages" /> этапы{" "}
                <span className="activity-dot activity-seg-jobs" /> задачи
              </div>
              <MiniChart series={activity.series} />
            </>
          ) : null}

          {vacancyId == null ? (
            <>
              <h2>По клиентам</h2>
              <table>
                <thead>
                  <tr>
                    <th>Клиент</th>
                    <th>В работе</th>
                    <th>Архив</th>
                    <th>Кандидаты</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.by_client.map((row) => (
                    <tr key={String(row.client_id)}>
                      <td>
                        {row.client_id != null ? (
                          <Link href={hrefFor({ ...linkBase, clientId: row.client_id, vacancyId: null })}>
                            {row.client_name}
                          </Link>
                        ) : (
                          row.client_name
                        )}
                      </td>
                      <td>{row.vacancies_active}</td>
                      <td>{row.vacancies_archive}</td>
                      <td>
                        {row.client_id != null ? (
                          <Link
                            className="row-link"
                            href={candidatesHref({
                              ...linkBase,
                              clientId: row.client_id,
                              vacancyId: null,
                            })}
                          >
                            {row.candidates}
                          </Link>
                        ) : (
                          row.candidates
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : null}
        </>
      ) : null}
      <WarrantyRegistry />
    </AppShell>
  );
}
