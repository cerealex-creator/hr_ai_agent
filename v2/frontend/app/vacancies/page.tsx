import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ClientSidebar } from "@/components/ClientSidebar";
import { CreateVacancyForm } from "@/components/CreateVacancyForm";
import { VacancyTable } from "@/components/VacancyTable";
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
  const archive = filtered.filter((v) => !v.active);
  const visible = mode === "archive" ? archive : active;
  const counts = stats?.counts || {};
  const selectedClient = clients.find((c) => c.id === clientId) || null;

  const countsByClient: Record<number, number> = {};
  for (const v of vacancies) {
    if (v.client_id == null) continue;
    if (mode === "active" && !v.active) continue;
    if (mode === "archive" && v.active) continue;
    countsByClient[v.client_id] = (countsByClient[v.client_id] || 0) + 1;
  }
  const totalForMode = vacancies.filter((v) => (mode === "active" ? v.active : !v.active)).length;

  return (
    <AppShell
      activePath="/vacancies"
      sidebar={
        <ClientSidebar
          clients={clients}
          selectedId={clientId}
          mode={mode}
          countsByClient={countsByClient}
          totalCount={totalForMode}
        />
      }
    >
      <h1 className="page-title">Поиск сотрудников</h1>
      <p className="muted">Активные и архивные вакансии, кандидаты и поиск на HH.</p>

      {error ? (
        <p className="warn">API недоступен ({error}). Проверьте, что API запущен.</p>
      ) : null}

      <div className="stats">
        <div className="stat">
          <strong>{active.length}</strong>
          <span>в работе</span>
        </div>
        <div className="stat">
          <strong>{archive.length}</strong>
          <span>архив</span>
        </div>
        <div className="stat">
          <strong>{counts.candidates ?? "—"}</strong>
          <span>кандидаты (все)</span>
        </div>
        <div className="stat">
          <strong>{counts.document_generations ?? "—"}</strong>
          <span>история документов</span>
        </div>
      </div>

      {mode === "active" && !error ? (
        <div style={{ margin: "0.75rem 0 1rem" }}>
          <CreateVacancyForm
            clients={clients.filter(
              (c) =>
                c.kind !== "test" &&
                !(c.kind === "company" && c.chat_mode === "departments"),
            )}
            vacancies={vacancies}
            defaultClientId={clientId}
          />
        </div>
      ) : null}

      <div className="tabs" role="tablist" aria-label="Фильтр вакансий">
        <Link
          href={hrefFor("active", clientId)}
          className={mode === "active" ? "tab tab-active" : "tab"}
          role="tab"
          aria-selected={mode === "active"}
        >
          В работе
          <span className="tab-count">{active.length}</span>
        </Link>
        <Link
          href={hrefFor("archive", clientId)}
          className={mode === "archive" ? "tab tab-active" : "tab"}
          role="tab"
          aria-selected={mode === "archive"}
        >
          Архив
          <span className="tab-count">{archive.length}</span>
        </Link>
      </div>

      {selectedClient ? (
        <p className="muted section-note">Клиент: {selectedClient.name}</p>
      ) : null}

      {mode === "archive" ? (
        <p className="muted section-note">
          Исход ориентировочный: по причине закрытия или наличию выхода на работу/стажировку.
        </p>
      ) : (
        <p className="muted section-note">Показаны дата старта и сколько дней вакансия в работе.</p>
      )}

      <VacancyTable vacancies={visible} mode={mode} />
    </AppShell>
  );
}
