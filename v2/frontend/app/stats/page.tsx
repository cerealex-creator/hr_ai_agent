import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CollapsibleHhBlock } from "@/components/CollapsibleHhBlock";
import { InfoTip } from "@/components/InfoTip";
import { StatsPeriodControls } from "@/components/StatsPeriodControls";
import { WarrantyRegistry } from "@/components/WarrantyRegistry";
import {
  apiGet,
  type ClientItem,
  type VacancyListItem,
} from "@/lib/api";
import { hrStageLabel } from "@/lib/labels";

type Props = {
  searchParams: Promise<{
    mode?: string;
    client?: string;
    vacancy?: string;
    scope?: string;
    period?: string;
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
};

const ALL_PERIODS = new Set([
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
]);

const OP_CHIPS = [
  { id: "week", label: "Текущая неделя" },
  { id: "mtd", label: "С начала месяца" },
  { id: "ytd", label: "С начала года" },
];

const EXEC_CHIPS = [
  { id: "week", label: "Неделя" },
  { id: "month", label: "Месяц" },
  { id: "all", label: "Всё время" },
];

function hrefFor(opts: {
  mode: string;
  clientId: number | null;
  vacancyId: number | null;
  scope: string;
  period: string;
}): string {
  const params = new URLSearchParams();
  if (opts.mode === "executive") params.set("mode", "executive");
  if (opts.clientId != null) params.set("client", String(opts.clientId));
  if (opts.vacancyId != null) params.set("vacancy", String(opts.vacancyId));
  // Default scope = active («В работе»); explicit only for «all»
  if (opts.scope === "all") params.set("scope", "all");
  const defaultPeriod = opts.mode === "executive" ? "month" : "week";
  if (opts.period && opts.period !== defaultPeriod) {
    params.set("period", opts.period);
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

function Bar({ count, max }: { count: number; max: number }) {
  const pct = max > 0 ? Math.max(4, Math.round((count / max) * 100)) : 0;
  return (
    <div className="bar-track" aria-hidden>
      <div className="bar-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function MiniChart({ series }: { series: ActivityBucket[] }) {
  if (!series.length) {
    return <p className="muted">Нет данных за период</p>;
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
            <div className="activity-label">{s.bucket.slice(-5)}</div>
          </div>
        );
      })}
    </div>
  );
}

export default async function StatsPage({ searchParams }: Props) {
  const { mode: modeRaw, client, vacancy, scope, period: periodRaw } = await searchParams;
  const mode = modeRaw === "executive" ? "executive" : "operational";
  const clientId = client && /^\d+$/.test(client) ? Number(client) : null;
  const vacancyId = vacancy && /^\d+$/.test(vacancy) ? Number(vacancy) : null;
  // Default: только вакансии в работе
  const activeOnly = scope !== "all";
  const defaultPeriod = mode === "executive" ? "month" : "week";
  const period = periodRaw && ALL_PERIODS.has(periodRaw) ? periodRaw : defaultPeriod;

  let dash: Dashboard | null = null;
  let clients: ClientItem[] = [];
  let vacancies: VacancyListItem[] = [];
  let error: string | null = null;

  const qs = new URLSearchParams();
  qs.set("mode", mode);
  qs.set("period", period);
  if (clientId != null) qs.set("client_id", String(clientId));
  if (vacancyId != null) qs.set("vacancy_id", String(vacancyId));
  if (activeOnly) qs.set("active_vacancies_only", "true");

  try {
    const vacListQs = new URLSearchParams();
    if (clientId != null) vacListQs.set("client_id", String(clientId));
    if (activeOnly) vacListQs.set("active", "true");

    [dash, clients, vacancies] = await Promise.all([
      apiGet<Dashboard>(`/api/v1/stats/dashboard?${qs.toString()}`),
      apiGet<ClientItem[]>("/api/v1/clients"),
      apiGet<VacancyListItem[]>(
        `/api/v1/vacancies${vacListQs.toString() ? `?${vacListQs}` : ""}`,
      ),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Ошибка API";
  }

  const selectedName = clients.find((c) => c.id === clientId)?.name;
  const selectedVacancy = vacancies.find((v) => v.id === vacancyId);
  const linkBase = {
    mode,
    clientId,
    vacancyId,
    scope: activeOnly ? "active" : "all",
    period,
  };
  const maxFlow = Math.max(1, ...(dash?.funnel_flow.map((s) => s.count) || [1]));
  const risks = dash?.warranty_risks;
  const periodChips = mode === "executive" ? EXEC_CHIPS : OP_CHIPS;
  const periodHrefIds = [
    ...periodChips.map((c) => c.id),
    "m1",
    "m2",
    "m3",
    "m6",
    "m12",
  ];
  const hrefByPeriod: Record<string, string> = {};
  for (const id of periodHrefIds) {
    hrefByPeriod[id] = hrefFor({ ...linkBase, period: id });
  }

  return (
    <AppShell activePath="/stats">
      <h1 className="page-title">Статистика</h1>
      <p className="muted">
        {mode === "operational"
          ? "Оперативный срез: что требует внимания сейчас."
          : "Отчёт за период для руководителя."}
      </p>
      {error ? <p className="warn">{error}</p> : null}

      <div className="tabs" role="tablist">
        <Link
          href={hrefFor({ ...linkBase, mode: "operational" })}
          className={mode === "operational" ? "tab tab-active" : "tab"}
        >
          Моя эффективность
        </Link>
        <Link
          href={hrefFor({ ...linkBase, mode: "executive" })}
          className={mode === "executive" ? "tab tab-active" : "tab"}
        >
          Отчет руководителю
        </Link>
      </div>

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
            Все
          </Link>
          {vacancies.map((v) => (
            <Link
              key={v.id}
              href={hrefFor({
                ...linkBase,
                vacancyId: v.id,
                clientId: v.client_id ?? clientId,
              })}
              className={vacancyId === v.id ? "chip chip-active" : "chip"}
            >
              {v.title}
            </Link>
          ))}
        </div>
      </div>

      <div className="tabs" role="tablist" aria-label="Область вакансий">
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

      <StatsPeriodControls
        chips={periodChips}
        period={period}
        hrefByPeriod={hrefByPeriod}
      />

      {selectedName || selectedVacancy ? (
        <p className="muted section-note">
          {selectedVacancy
            ? `Вакансия: ${selectedVacancy.title}`
            : selectedName
              ? `Клиент: ${selectedName}`
              : null}
        </p>
      ) : null}

      {dash ? (
        <>
          <div className="stats">
            {dash.kpis.map((k) => (
              <div key={k.key} className="stat">
                <strong>{formatKpi(k.value, k.unit)}</strong>
                <span>{k.label}</span>
              </div>
            ))}
          </div>

          {mode === "operational" ? (
            <>
              <h2>Активность за период</h2>
              <div className="activity-legend muted">
                <span className="activity-dot activity-seg-cands" /> кандидаты{" "}
                <span className="activity-dot activity-seg-stages" /> этапы{" "}
                <span className="activity-dot activity-seg-jobs" /> задачи
              </div>
              <MiniChart series={dash.activity_series} />

              <h2>
                Требуют внимания
                <InfoTip text="Кандидаты, у которых сейчас есть незакрытый шаг: подтвердить встречу, добавить запись, дождаться решения заказчика и т.п. Список совпадает с фильтром «Требуют внимания» у кандидатов." />
              </h2>
              <p className="muted">
                <Link href={candidatesHref({ ...linkBase, preset: "attention" })}>
                  Открыть всех →
                </Link>
              </p>
              {dash.attention.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Кандидат</th>
                      <th>Вакансия</th>
                      <th>Причина</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dash.attention.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <Link href={`/candidates/${row.id}`}>{row.name}</Link>
                        </td>
                        <td>
                          <Link href={`/vacancies/${row.vacancy_id}`}>
                            {row.vacancy_title || `#${row.vacancy_id}`}
                          </Link>
                        </td>
                        <td>{row.reason || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">Нет данных за период</p>
              )}

              {dash.hh ? <CollapsibleHhBlock hh={dash.hh} /> : null}
            </>
          ) : (
            <>
              <h2>Воронка (переходы за период)</h2>
              {dash.funnel_flow.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Этап</th>
                      <th>Переходов</th>
                      <th>Доля</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dash.funnel_flow.map((row) => (
                      <tr key={row.stage}>
                        <td>{hrStageLabel(row.stage)}</td>
                        <td>{row.count}</td>
                        <td className="bar-cell">
                          <Bar count={row.count} max={maxFlow} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">Нет данных за период</p>
              )}

              <h2>Результаты по вакансиям</h2>
              {dash.vacancies_table.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Вакансия</th>
                      <th>Статус</th>
                      <th>Дней</th>
                      <th>Кандидатов</th>
                      <th>Найм</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dash.vacancies_table.map((row) => (
                      <tr key={row.vacancy_id}>
                        <td>
                          <Link href={`/vacancies/${row.vacancy_id}`}>{row.title}</Link>
                        </td>
                        <td>{row.active ? "В работе" : "Архив"}</td>
                        <td>{row.days_open ?? "—"}</td>
                        <td>{row.candidates}</td>
                        <td>{row.hires}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">Нет данных за период</p>
              )}

              <section className="warranty-risks">
                <h2>
                  Риски и гарантия
                  <InfoTip text="Возврат — кандидат вышел на работу, но ушёл в пределах гарантийного срока. Повторный поиск — гарантийная вакансия или несколько наймов на одну позицию." />
                </h2>
                <div className="stats">
                  <div className="stat stat-warn">
                    <strong>{risks?.claims_count ?? 0}</strong>
                    <span>возвратов за период</span>
                  </div>
                  <div className="stat stat-warn">
                    <strong>{risks?.warranty_searches ?? 0}</strong>
                    <span>гарантийных поисков</span>
                  </div>
                  <div className="stat stat-warn">
                    <strong>{risks?.multi_hire_vacancies ?? 0}</strong>
                    <span>вакансий с ≥2 наймами</span>
                  </div>
                </div>
                {risks?.claims?.length ? (
                  <table>
                    <thead>
                      <tr>
                        <th>Кандидат</th>
                        <th>Вакансия</th>
                        <th>Дней</th>
                        <th>Причина</th>
                      </tr>
                    </thead>
                    <tbody>
                      {risks.claims.map((c) => (
                        <tr key={`${c.candidate_id}-${c.left_at}`}>
                          <td>
                            <Link href={`/candidates/${c.candidate_id}`}>
                              {c.candidate_name}
                            </Link>
                          </td>
                          <td>
                            <Link href={`/vacancies/${c.vacancy_id}`}>
                              {c.vacancy_title}
                            </Link>
                          </td>
                          <td>{c.days_worked ?? "—"}</td>
                          <td>{c.reason || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="muted">Возвратов по гарантии за период нет</p>
                )}
              </section>

              <WarrantyRegistry />
            </>
          )}
        </>
      ) : null}
    </AppShell>
  );
}
