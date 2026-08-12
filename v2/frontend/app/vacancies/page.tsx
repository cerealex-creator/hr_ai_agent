import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";
import { CreateVacancyForm } from "@/components/CreateVacancyForm";
import { VacancyCompactRow } from "@/components/VacancyCompactRow";
import {
  apiGet,
  type ClientItem,
  type ImportStats,
  type VacancyListItem,
} from "@/lib/api";

type Props = {
  searchParams: Promise<{ tab?: string; client?: string }>;
};

function hrefFor(tab: string, clientId: number | null): string {
  const params = new URLSearchParams();
  params.set("tab", tab);
  if (clientId != null) params.set("client", String(clientId));
  return `/vacancies?${params.toString()}`;
}

export default async function VacanciesPage({ searchParams }: Props) {
  const { tab, client } = await searchParams;
  const mode = tab === "archive" ? "archive" : "active";
  const clientId = client && /^\d+$/.test(client) ? Number(client) : null;

  let vacancies: VacancyListItem[] = [];
  let clients: ClientItem[] = [];
  let stats: ImportStats | null = null;
  let error: string | null = null;

  try {
    [vacancies, clients, stats] = await Promise.all([
      apiGet<VacancyListItem[]>("/api/v1/vacancies"),
      apiGet<ClientItem[]>("/api/v1/clients"),
      apiGet<ImportStats>("/api/v1/stats/import"),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "API unavailable";
  }

  const filtered =
    clientId == null ? vacancies : vacancies.filter((v) => v.client_id === clientId);
  const active = filtered.filter((v) => v.active);
  const archive = filtered
    .filter((v) => !v.active)
    .slice()
    .sort((a, b) => {
      const ta = a.closed_at || a.created_at || "";
      const tb = b.closed_at || b.created_at || "";
      return tb.localeCompare(ta); // новые сверху
    });
  const visible = mode === "archive" ? archive : active;
  const counts = stats?.counts || {};

  // Глобальные KPI (без фильтра клиента) — как на рабочем столе
  const activeAll = vacancies.filter((v) => v.active).length;
  const archiveAll = vacancies.filter((v) => !v.active).length;

  const clientsWithActive = new Set(
    vacancies.filter((v) => v.active && v.client_id != null).map((v) => v.client_id as number),
  );
  const clientChips = clients.filter((c) => {
    if (c.kind === "test") return false;
    if (mode === "active") return clientsWithActive.has(c.id);
    return true;
  });

  return (
    <RecruitingShell activePath="/vacancies" title="Вакансии">
      {error ? (
        <p className="warn">API недоступен ({error}). Проверьте, что API запущен.</p>
      ) : null}

      <div className="rec-dash-kpis">
        <Link
          href={hrefFor("active", clientId)}
          className={`rec-dash-kpi rec-dash-kpi-link rec-dash-kpi-blue${mode === "active" ? " is-selected" : ""}`}
        >
          <span className="rec-dash-kpi-label">В работе</span>
          <span className="rec-dash-kpi-val">{clientId != null ? active.length : activeAll}</span>
        </Link>
        <Link
          href={hrefFor("archive", clientId)}
          className={`rec-dash-kpi rec-dash-kpi-link rec-dash-kpi-orange${mode === "archive" ? " is-selected" : ""}`}
        >
          <span className="rec-dash-kpi-label">Архив</span>
          <span className="rec-dash-kpi-val">{clientId != null ? archive.length : archiveAll}</span>
        </Link>
        <Link href="/candidates" className="rec-dash-kpi rec-dash-kpi-link rec-dash-kpi-attention">
          <span className="rec-dash-kpi-label">Кандидаты</span>
          <span className="rec-dash-kpi-val">{counts.candidates ?? "—"}</span>
        </Link>
        <Link href="/history" className="rec-dash-kpi rec-dash-kpi-link">
          <span className="rec-dash-kpi-label">Документы</span>
          <span className="rec-dash-kpi-val">{counts.document_generations ?? "—"}</span>
        </Link>
      </div>

      <div className="vac-list-toolbar">
        <nav className="cand-tabs" role="tablist" aria-label="Фильтр вакансий">
          <Link
            href={hrefFor("active", clientId)}
            className={`cand-tab${mode === "active" ? " is-active" : ""}`}
            role="tab"
            aria-selected={mode === "active"}
          >
            В работе
            <span className="tab-count">{active.length}</span>
          </Link>
          <Link
            href={hrefFor("archive", clientId)}
            className={`cand-tab${mode === "archive" ? " is-active" : ""}`}
            role="tab"
            aria-selected={mode === "archive"}
          >
            Архив
            <span className="tab-count">{archive.length}</span>
          </Link>
        </nav>

        {mode === "active" && !error ? (
          <CreateVacancyForm
            clients={clients.filter(
              (c) =>
                c.kind !== "test" &&
                !(c.kind === "company" && c.chat_mode === "departments"),
            )}
            vacancies={vacancies}
            defaultClientId={clientId}
          />
        ) : null}
      </div>

      <div className="filter-row vac-client-filter">
        <span className="filter-label">Клиент</span>
        <div className="chip-row stats-chip-scroll">
          <Link
            href={hrefFor(mode, null)}
            className={clientId == null ? "chip chip-active" : "chip"}
          >
            Все
          </Link>
          {clientChips.map((c) => (
            <Link
              key={c.id}
              href={hrefFor(mode, c.id)}
              className={clientId === c.id ? "chip chip-active" : "chip"}
            >
              {c.name}
            </Link>
          ))}
        </div>
      </div>

      <section className="rec-dash-section">
        <div className="rec-dash-section-head">
          <h2 className="rec-dash-section-title">
            {mode === "archive" ? "Архив вакансий" : "Вакансии в работе"}
          </h2>
          <span className="muted hh-micro">
            {mode === "archive"
              ? "Исход ориентировочный"
              : "Дата старта и дни в работе"}
          </span>
        </div>

        <div className="rec-card vac-list-card">
          {visible.length ? (
            <div className="vac-list">
              {visible.map((v) => (
                <VacancyCompactRow key={v.id} vacancy={v} mode={mode} />
              ))}
            </div>
          ) : (
            <p className="rec-empty">
              {mode === "archive" ? "Архив пуст" : "Нет вакансий в работе"}
            </p>
          )}
        </div>
      </section>
    </RecruitingShell>
  );
}
