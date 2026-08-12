import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";
import { CollapsibleHhBlock } from "@/components/CollapsibleHhBlock";
import { InfoTip } from "@/components/InfoTip";
import { StatsAiBriefPanel } from "@/components/StatsAiBriefPanel";
import { StatsPeriodEditor } from "@/components/StatsPeriodEditor";
import { WarrantyRegistry } from "@/components/WarrantyRegistry";
import {
  apiGet,
  outcomeLabel,
  type ClientItem,
  type VacancyListItem,
  type VacancyOutcome,
} from "@/lib/api";
import { hrStageLabel } from "@/lib/labels";

type Props = {
  searchParams: Promise<{
    mode?: string;
    company?: string;
    client?: string; // legacy alias → company
    dept?: string;
    vacancy?: string;
    scope?: string;
    period?: string;
    from?: string;
    to?: string;
  }>;
};

type ActivityBucket = {
  bucket: string;
  candidates_added: number;
  stage_changes: number;
  jobs: number;
};

type Dashboard = {
  mode: "operational" | "executive";
  period: string;
  period_from: string | null;
  period_to: string | null;
  kpis: { key: string; label: string; value: number; unit?: string | null }[];
  activity_series: ActivityBucket[];
  funnel_flow: { stage: string; count: number }[];
  attention: {
    id: string;
    name: string;
    vacancy_id: number;
    vacancy_title?: string | null;
    reason?: string | null;
  }[];
  vacancies_table: {
    vacancy_id: number;
    title: string;
    active: boolean;
    days_open: number | null;
    candidates: number;
    hires: number;
  }[];
  hh: {
    viewed: number;
    ai_score_gt2: number;
    ai_low: number;
    recruiter_reject: number;
    shortlist: number;
    in_funnel: number;
    jobs_completed: number;
  } | null;
  warranty_risks: {
    claims_count: number;
    claims: {
      candidate_id: string;
      candidate_name: string;
      vacancy_id: number;
      vacancy_title: string;
      days_worked: number | null;
      reason: string | null;
      hire_at: string | null;
      left_at: string | null;
    }[];
    warranty_searches: number;
    multi_hire_vacancies: number;
    replacements_total: number;
  } | null;
  closed_breakdown: {
    total: number;
    rows: {
      reason: VacancyOutcome;
      label: string;
      count: number;
      vacancies: { vacancy_id: number; title: string; closed_at: string | null }[];
    }[];
  } | null;
};

const ALL_PERIODS = new Set([
  "day",
  "week",
  "month",
  "all",
  "mtd",
  "ytd",
  "m1",
  "m2",
  "m3",
  "m6",
  "m12",
  "custom",
]);

const OP_CHIPS = [
  { id: "day", label: "Сутки" },
  { id: "week", label: "Неделя" },
  { id: "mtd", label: "С начала месяца" },
  { id: "ytd", label: "С начала года" },
];

const EXEC_CHIPS = [
  { id: "day", label: "Сутки" },
  { id: "week", label: "Неделя" },
  { id: "month", label: "Месяц" },
  { id: "all", label: "Всё время" },
];

function hrefFor(opts: {
  mode: string;
  companyId: number | null;
  allCompanies?: boolean;
  deptId: number | null;
  vacancyId: number | null;
  scope: string;
  period: string;
  from?: string;
  to?: string;
}): string {
  const params = new URLSearchParams();
  if (opts.mode === "executive" || opts.mode === "ai") params.set("mode", opts.mode);
  if (opts.allCompanies) params.set("company", "all");
  else if (opts.companyId != null) params.set("company", String(opts.companyId));
  if (opts.deptId != null) params.set("dept", String(opts.deptId));
  if (opts.vacancyId != null) params.set("vacancy", String(opts.vacancyId));
  if (opts.scope === "all") params.set("scope", "all");

  if (opts.from || opts.to || opts.period === "custom") {
    params.set("period", "custom");
    if (opts.from) params.set("from", opts.from);
    if (opts.to) params.set("to", opts.to);
  } else {
    const defaultPeriod = "day";
    if (opts.period && opts.period !== defaultPeriod) params.set("period", opts.period);
  }
  const q = params.toString();
  return q ? `/stats?${q}` : "/stats";
}

function candidatesHref(opts: {
  clientId: number | null;
  vacancyId: number | null;
  scope: string;
  preset?: string;
}): string {
  const params = new URLSearchParams();
  if (opts.clientId != null) params.set("client", String(opts.clientId));
  if (opts.vacancyId != null) params.set("vacancy", String(opts.vacancyId));
  if (opts.scope === "all") params.set("scope", "all");
  if (opts.preset) params.set("preset", opts.preset);
  const q = params.toString();
  return q ? `/candidates?${q}` : "/candidates";
}

function formatKpi(value: number, unit?: string | null): string {
  const n = Number.isInteger(value) ? String(value) : String(value);
  return unit ? `${n}${unit === "%" ? "%" : ` ${unit}`}` : n;
}

function toInputDate(iso: string | null | undefined): string {
  if (!iso) return "";
  if (/^\d{4}-\d{2}-\d{2}/.test(iso)) return iso.slice(0, 10);
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatBucketLabel(bucket: string): string {
  const raw = (bucket || "").trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) {
    const [, m, d] = raw.slice(0, 10).split("-");
    return `${d}.${m}`;
  }
  if (/^\d{4}-\d{2}$/.test(raw)) {
    const [y, m] = raw.split("-");
    return `${m}.${y.slice(2)}`;
  }
  return raw.length > 6 ? raw.slice(-5) : raw;
}

function MiniChart({ series }: { series: ActivityBucket[] }) {
  if (!series.length) {
    return <p className="rec-empty">За выбранный период активности нет</p>;
  }
  const max = Math.max(
    1,
    ...series.map((s) => s.candidates_added + s.stage_changes + s.jobs),
  );
  return (
    <div className="activity-chart" role="img" aria-label="Активность по дням">
      {series.map((s) => {
        const total = s.candidates_added + s.stage_changes + s.jobs;
        const h = Math.max(total > 0 ? 8 : 2, Math.round((total / max) * 120));
        const cH = total ? Math.round((s.candidates_added / total) * h) : 0;
        const stH = total ? Math.round((s.stage_changes / total) * h) : 0;
        const jH = Math.max(0, h - cH - stH);
        const label = formatBucketLabel(s.bucket);
        return (
          <div
            key={s.bucket}
            className="activity-col"
            title={`${s.bucket}: +${s.candidates_added} канд., ${s.stage_changes} этапов, ${s.jobs} задач`}
          >
            <div className="activity-stack" style={{ height: h }}>
              <span className="activity-seg activity-seg-jobs" style={{ height: jH }} />
              <span className="activity-seg activity-seg-stages" style={{ height: stH }} />
              <span className="activity-seg activity-seg-cands" style={{ height: cH }} />
            </div>
            <div className="activity-label">{label}</div>
          </div>
        );
      })}
    </div>
  );
}

function isCompany(c: ClientItem): boolean {
  if (c.kind === "test") return false;
  if (c.kind === "department") return false;
  if (c.kind === "company") return true;
  return c.parent_id == null;
}

export default async function StatsPage({ searchParams }: Props) {
  const sp = await searchParams;
  const mode =
    sp.mode === "executive" ? "executive" : sp.mode === "ai" ? "ai" : "operational";
  const companyRaw = (sp.company || sp.client || "").trim();
  const allCompanies = companyRaw === "all";
  const companyId =
    !allCompanies && companyRaw && /^\d+$/.test(companyRaw) ? Number(companyRaw) : null;
  const deptId = sp.dept && /^\d+$/.test(sp.dept) ? Number(sp.dept) : null;
  const vacancyId = sp.vacancy && /^\d+$/.test(sp.vacancy) ? Number(sp.vacancy) : null;
  const activeOnly = sp.scope !== "all";
  const dateFrom = (sp.from || "").trim().slice(0, 10);
  const dateTo = (sp.to || "").trim().slice(0, 10);
  const defaultPeriod = "day";
  const period =
    dateFrom || dateTo
      ? "custom"
      : sp.period && ALL_PERIODS.has(sp.period)
        ? sp.period
        : defaultPeriod;

  // API client filter: dept overrides company (exact leaf); company expands on backend
  // allCompanies → no client_id (вся организация)
  const apiClientId = allCompanies ? null : (deptId ?? companyId);
  const hasCompanyScope = allCompanies || companyId != null;

  let dash: Dashboard | null = null;
  let clients: ClientItem[] = [];
  let vacancies: VacancyListItem[] = [];
  let error: string | null = null;

  try {
    clients = await apiGet<ClientItem[]>("/api/v1/clients");
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  const companies = clients.filter(isCompany);
  const departments = companyId
    ? clients.filter((c) => c.parent_id === companyId || (c.kind === "department" && c.parent_id === companyId))
    : [];
  const selectedCompany = companies.find((c) => c.id === companyId) || null;
  const hasDepts =
    Boolean(selectedCompany?.chat_mode === "departments") || departments.length > 0;

  const linkBase = {
    mode,
    companyId,
    allCompanies,
    deptId: allCompanies ? null : deptId,
    vacancyId,
    scope: activeOnly ? "active" : "all",
    period,
    from: dateFrom,
    to: dateTo,
  };

  if (hasCompanyScope) {
    try {
      if (mode === "ai") {
        vacancies = await apiGet<VacancyListItem[]>(`/api/v1/vacancies`);
      } else {
        const qs = new URLSearchParams();
        qs.set("mode", mode);
        qs.set("period", period);
        if (apiClientId != null) qs.set("client_id", String(apiClientId));
        if (vacancyId != null) qs.set("vacancy_id", String(vacancyId));
        if (activeOnly) qs.set("active_vacancies_only", "true");
        if (dateFrom) qs.set("from", dateFrom);
        if (dateTo) qs.set("to", dateTo);

        [dash, vacancies] = await Promise.all([
          apiGet<Dashboard>(`/api/v1/stats/dashboard?${qs.toString()}`),
          apiGet<VacancyListItem[]>(`/api/v1/vacancies`),
        ]);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "Ошибка API";
    }
  }

  const companyClientIds = new Set<number>();
  if (allCompanies) {
    for (const c of companies) companyClientIds.add(c.id);
    for (const c of clients) {
      if (c.parent_id != null && companyClientIds.has(c.parent_id)) {
        companyClientIds.add(c.id);
      }
    }
  } else if (companyId != null) {
    companyClientIds.add(companyId);
    for (const d of departments) companyClientIds.add(d.id);
  }
  const vacanciesForFilter = vacancies.filter((v) => {
    if (v.client_id == null) return false;
    if (!allCompanies && deptId != null) return v.client_id === deptId;
    return companyClientIds.has(v.client_id);
  });

  const periodChips = mode === "operational" ? OP_CHIPS : EXEC_CHIPS;
  const showClosedHint = mode === "executive" && activeOnly;
  const maxFlow = Math.max(1, ...(dash?.funnel_flow.map((s) => s.count) || [1]));
  const risks = dash?.warranty_risks;
  const closedBreakdown = dash?.closed_breakdown;
  const maxClosed =
    closedBreakdown?.rows.reduce((m, r) => Math.max(m, r.count), 0) ?? 0;

  const inputFrom = dateFrom || toInputDate(dash?.period_from);
  const inputTo = dateTo || toInputDate(dash?.period_to);

  return (
    <RecruitingShell activePath="/stats">
      <div className="stats-head">
        <h1 className="stats-head-title">Аналитика</h1>
        <div className="stats-mode-plaques stats-mode-plaques-row" role="tablist" aria-label="Режим статистики">
          <Link
            href={hrefFor({ ...linkBase, mode: "operational" })}
            className={`stats-mode-plaque${mode === "operational" ? " is-active" : ""}`}
          >
            <span className="stats-mode-plaque-title">Моя эффективность</span>
            <span className="stats-mode-plaque-sub">Оперативный срез</span>
          </Link>
          <Link
            href={hrefFor({ ...linkBase, mode: "executive" })}
            className={`stats-mode-plaque stats-mode-plaque-exec${mode === "executive" ? " is-active" : ""}`}
          >
            <span className="stats-mode-plaque-title">Взгляд руководителя</span>
            <span className="stats-mode-plaque-sub">Отчёт за период</span>
          </Link>
          <Link
            href={hrefFor({ ...linkBase, mode: "ai" })}
            className={`stats-mode-plaque stats-mode-plaque-ai${mode === "ai" ? " is-active" : ""}`}
          >
            <span className="stats-mode-plaque-title">Помощь ИИ</span>
            <span className="stats-mode-plaque-sub">Свой запрос → расклад</span>
          </Link>
        </div>
        <div className="stats-head-period">
          <StatsPeriodEditor
            linkBase={{
              mode,
              companyId,
              allCompanies,
              deptId: allCompanies ? null : deptId,
              vacancyId,
              scope: activeOnly ? "active" : "all",
            }}
            dateFrom={inputFrom}
            dateTo={inputTo}
            period={period}
            presets={periodChips}
          />
        </div>
      </div>

      {error ? <p className="warn">{error}</p> : null}

      <div className="rec-card stats-filters-card">
        <div className="stats-filter-block">
          <span className="filter-label">Компания</span>
          <div className="stats-company-plaques">
            <Link
              href={hrefFor({
                ...linkBase,
                companyId: null,
                allCompanies: true,
                deptId: null,
                vacancyId: null,
              })}
              className={`stats-company-plaque${allCompanies ? " is-active" : ""}`}
            >
              Все компании
            </Link>
            {companies.map((c) => (
              <Link
                key={c.id}
                href={hrefFor({
                  ...linkBase,
                  companyId: c.id,
                  allCompanies: false,
                  deptId: null,
                  vacancyId: null,
                })}
                className={`stats-company-plaque${!allCompanies && companyId === c.id ? " is-active" : ""}`}
              >
                {c.name}
              </Link>
            ))}
            {!companies.length ? (
              <p className="rec-empty">Нет компаний</p>
            ) : null}
          </div>
        </div>

        {companyId != null && !allCompanies && hasDepts ? (
          <div className="stats-filter-block">
            <span className="filter-label">Отдел</span>
            <div className="chip-row stats-chip-scroll">
              <Link
                href={hrefFor({ ...linkBase, deptId: null, vacancyId: null })}
                className={deptId == null ? "chip chip-active" : "chip"}
              >
                Вся компания
              </Link>
              {departments.map((d) => (
                <Link
                  key={d.id}
                  href={hrefFor({ ...linkBase, deptId: d.id, vacancyId: null })}
                  className={deptId === d.id ? "chip chip-active" : "chip"}
                >
                  {d.name}
                </Link>
              ))}
            </div>
          </div>
        ) : null}

        {hasCompanyScope ? (
          <>
            <div className="stats-filter-block">
              <span className="filter-label">Вакансия</span>
              <div className="chip-row stats-chip-scroll">
                <Link
                  href={hrefFor({ ...linkBase, vacancyId: null })}
                  className={vacancyId == null ? "chip chip-active" : "chip"}
                >
                  Все
                </Link>
                {vacanciesForFilter.map((v) => (
                  <Link
                    key={v.id}
                    href={hrefFor({ ...linkBase, vacancyId: v.id })}
                    className={vacancyId === v.id ? "chip chip-active" : "chip"}
                  >
                    {v.title}
                  </Link>
                ))}
              </div>
            </div>

            <div className="stats-filter-block">
              <span className="filter-label">Область</span>
              <div className="chip-row">
                <Link
                  href={hrefFor({ ...linkBase, scope: "all" })}
                  className={!activeOnly ? "chip chip-active" : "chip"}
                >
                  Все вакансии
                </Link>
                <Link
                  href={hrefFor({ ...linkBase, scope: "active" })}
                  className={activeOnly ? "chip chip-active" : "chip"}
                >
                  Только в работе
                </Link>
              </div>
              {showClosedHint ? (
                <p className="muted hh-micro" style={{ marginTop: "0.35rem" }}>
                  Для показателя «Закрыто вакансий» выберите «Все вакансии».
                </p>
              ) : null}
            </div>
          </>
        ) : null}
      </div>

      {!hasCompanyScope ? (
        <div className="rec-card stats-empty-pick">
          <p className="stats-empty-pick-title">Выберите компанию</p>
          <p className="muted">
            Нажмите «Все компании» или плашку одной компании — откроется статистика за выбранный
            период.
          </p>
        </div>
      ) : null}

      {hasCompanyScope && mode === "ai" ? (
        <StatsAiBriefPanel
          clientId={apiClientId}
          vacancyId={vacancyId}
          period={period}
          dateFrom={dateFrom}
          dateTo={dateTo}
          activeOnly={activeOnly}
        />
      ) : null}

      {hasCompanyScope && dash && mode !== "ai" ? (
        <>
          <div className="rec-dash-kpis">
            {dash.kpis.map((k, i) => {
              const tones = ["blue", "attention", "orange", "teal"] as const;
              const tone = tones[i % tones.length];
              return (
                <div key={k.key} className={`rec-dash-kpi rec-dash-kpi-${tone}`}>
                  <span className="rec-dash-kpi-label">{k.label}</span>
                  <span className="rec-dash-kpi-val">{formatKpi(k.value, k.unit)}</span>
                </div>
              );
            })}
          </div>

          {mode === "operational" ? (
            <>
              <section className="rec-dash-section">
                <div className="rec-dash-section-head">
                  <h2 className="rec-dash-section-title">Активность за период</h2>
                </div>
                <div className="rec-card">
                  <div className="activity-legend muted">
                    <span className="activity-dot activity-seg-cands" /> кандидаты{" "}
                    <span className="activity-dot activity-seg-stages" /> этапы{" "}
                    <span className="activity-dot activity-seg-jobs" /> задачи
                  </div>
                  <MiniChart series={dash.activity_series} />
                </div>
              </section>

              <section className="rec-dash-section">
                <div className="rec-dash-section-head">
                  <h2 className="rec-dash-section-title">
                    Требуют внимания
                    <InfoTip text="Кандидаты с незакрытым шагом." />
                  </h2>
                  <Link
                    className="rec-dash-section-link"
                    href={candidatesHref({
                      clientId: apiClientId,
                      vacancyId,
                      scope: activeOnly ? "active" : "all",
                      preset: "attention",
                    })}
                  >
                    Все →
                  </Link>
                </div>
                <div className="rec-card vac-list-card">
                  {dash.attention.length ? (
                    <div className="vac-list">
                      {dash.attention.map((row) => (
                        <Link
                          key={row.id}
                          href={`/candidates/${row.id}`}
                          className="rec-row rec-row-compact"
                        >
                          <div className="rec-row-body">
                            <div className="rec-row-top">
                              <span className="rec-row-name">{row.name}</span>
                            </div>
                            <p className="rec-row-sub">
                              {row.vacancy_title || `Вакансия #${row.vacancy_id}`}
                            </p>
                          </div>
                          <div className="rec-row-aside">
                            <span className="rec-badge rec-badge-attention">
                              {row.reason || "Внимание"}
                            </span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="rec-empty">Сейчас нет кандидатов, требующих действия</p>
                  )}
                </div>
              </section>

              {dash.hh ? (
                <section className="rec-dash-section">
                  <div className="rec-card">
                    <CollapsibleHhBlock hh={dash.hh} />
                  </div>
                </section>
              ) : null}
            </>
          ) : (
            <>
              <section className="rec-dash-section">
                <div className="rec-dash-section-head">
                  <h2 className="rec-dash-section-title">
                    Закрытые вакансии по причинам
                    <InfoTip text="Считаются вакансии, у которых дата закрытия попадает в выбранный период. Для полного списка выберите «Все вакансии» в области." />
                  </h2>
                </div>
                {closedBreakdown && closedBreakdown.total > 0 ? (
                  <>
                    <div className="rec-dash-kpis">
                      {closedBreakdown.rows.map((row, i) => {
                        const tones = ["teal", "orange", "gray"] as const;
                        const tone = tones[i % tones.length];
                        return (
                          <div key={row.reason} className={`rec-dash-kpi rec-dash-kpi-${tone}`}>
                            <span className="rec-dash-kpi-label">{row.label}</span>
                            <span className="rec-dash-kpi-val">{row.count}</span>
                          </div>
                        );
                      })}
                    </div>
                    <div className="rec-card vac-list-card">
                      <div className="vac-list">
                        {closedBreakdown.rows.flatMap((row) =>
                          row.vacancies.map((v) => (
                            <Link
                              key={`${row.reason}-${v.vacancy_id}`}
                              href={`/vacancies/${v.vacancy_id}`}
                              className="rec-row rec-row-compact"
                            >
                              <div className="rec-row-body">
                                <div className="rec-row-top">
                                  <span className="rec-row-name">{v.title}</span>
                                </div>
                                <p className="rec-row-sub">
                                  {v.closed_at
                                    ? new Date(v.closed_at).toLocaleDateString("ru-RU")
                                    : "—"}
                                </p>
                                <div className="bar-track" style={{ marginTop: 6 }}>
                                  <div
                                    className="bar-fill"
                                    style={{
                                      width: `${maxClosed > 0 ? Math.max(4, Math.round((row.count / maxClosed) * 100)) : 0}%`,
                                    }}
                                  />
                                </div>
                              </div>
                              <div className="rec-row-aside">
                                <span className={`outcome outcome-${row.reason}`}>
                                  {outcomeLabel(row.reason)}
                                </span>
                              </div>
                            </Link>
                          )),
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="rec-card">
                    <p className="rec-empty">В периоде нет закрытых вакансий</p>
                  </div>
                )}
              </section>

              <section className="rec-dash-section">
                <div className="rec-dash-section-head">
                  <h2 className="rec-dash-section-title">Воронка (переходы за период)</h2>
                </div>
                <div className="rec-card">
                  {dash.funnel_flow.length ? (
                    <div className="vac-list">
                      {dash.funnel_flow.map((row) => (
                        <div key={row.stage} className="rec-row rec-row-compact stats-funnel-row">
                          <div className="rec-row-body">
                            <div className="rec-row-top">
                              <span className="rec-row-name">{hrStageLabel(row.stage)}</span>
                            </div>
                            <div className="bar-track" style={{ marginTop: 6 }}>
                              <div
                                className="bar-fill"
                                style={{
                                  width: `${maxFlow > 0 ? Math.max(4, Math.round((row.count / maxFlow) * 100)) : 0}%`,
                                }}
                              />
                            </div>
                          </div>
                          <div className="rec-row-aside">
                            <span className="rec-badge rec-badge-blue">{row.count}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="rec-empty">За период переходов по этапам нет</p>
                  )}
                </div>
              </section>

              <section className="rec-dash-section">
                <div className="rec-dash-section-head">
                  <h2 className="rec-dash-section-title">Результаты по вакансиям</h2>
                </div>
                <div className="rec-card vac-list-card">
                  {dash.vacancies_table.length ? (
                    <div className="vac-list">
                      {dash.vacancies_table.map((row) => (
                        <Link
                          key={row.vacancy_id}
                          href={`/vacancies/${row.vacancy_id}`}
                          className="rec-row rec-row-compact"
                        >
                          <div className="rec-row-body">
                            <div className="rec-row-top">
                              <span className="rec-row-name">{row.title}</span>
                            </div>
                            <p className="rec-row-sub">
                              {row.active ? "В работе" : "Архив"}
                              {row.days_open != null ? ` · ${row.days_open} дн.` : ""}
                            </p>
                          </div>
                          <div className="rec-row-aside">
                            <span className="rec-badge rec-badge-gray">{row.candidates} канд.</span>
                            <span className="rec-row-client">Найм: {row.hires}</span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="rec-empty">Нет вакансий в выбранной области</p>
                  )}
                </div>
              </section>

              <section className="rec-dash-section">
                <div className="rec-dash-section-head">
                  <h2 className="rec-dash-section-title">
                    Риски и гарантия
                    <InfoTip text="Возврат — кандидат вышел на работу, но ушёл в пределах гарантийного срока." />
                  </h2>
                </div>
                <div className="rec-dash-kpis">
                  <div className="rec-dash-kpi rec-dash-kpi-attention">
                    <span className="rec-dash-kpi-label">Возвратов</span>
                    <span className="rec-dash-kpi-val">{risks?.claims_count ?? 0}</span>
                  </div>
                  <div className="rec-dash-kpi rec-dash-kpi-orange">
                    <span className="rec-dash-kpi-label">Гарантийных поисков</span>
                    <span className="rec-dash-kpi-val">{risks?.warranty_searches ?? 0}</span>
                  </div>
                  <div className="rec-dash-kpi rec-dash-kpi-blue">
                    <span className="rec-dash-kpi-label">Вакансий с 2+ наймами</span>
                    <span className="rec-dash-kpi-val">{risks?.multi_hire_vacancies ?? 0}</span>
                  </div>
                </div>
                <div className="rec-card vac-list-card">
                  {risks?.claims?.length ? (
                    <div className="vac-list">
                      {risks.claims.map((c) => (
                        <Link
                          key={`${c.candidate_id}-${c.left_at}`}
                          href={`/candidates/${c.candidate_id}`}
                          className="rec-row rec-row-compact"
                        >
                          <div className="rec-row-body">
                            <div className="rec-row-top">
                              <span className="rec-row-name">{c.candidate_name}</span>
                            </div>
                            <p className="rec-row-sub">{c.vacancy_title}</p>
                          </div>
                          <div className="rec-row-aside">
                            <span className="rec-row-client">
                              {c.days_worked != null ? `${c.days_worked} дн.` : "—"}
                            </span>
                            <span className="rec-badge rec-badge-attention">
                              {c.reason || "Возврат"}
                            </span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="rec-empty">Возвратов по гарантии за период нет</p>
                  )}
                </div>
              </section>

              <section className="rec-dash-section">
                <div className="rec-card">
                  <WarrantyRegistry />
                </div>
              </section>
            </>
          )}
        </>
      ) : null}
    </RecruitingShell>
  );
}
