import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { CandidateSearchPanel } from "@/components/CandidateSearchPanel";
import { apiGet, type CandidateListItem } from "@/lib/api";
import { StageMarker } from "@/components/StageMarker";
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

function formatLastContact(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 10);
  return d.toLocaleDateString("ru-RU");
}

function CandidatesTable({
  rows,
  error,
  showReason,
}: {
  rows: CandidateListItem[];
  error: string | null;
  showReason?: boolean;
}) {
  const cols = showReason ? 8 : 7;
  return (
    <table>
      <thead>
        <tr>
          <th>Имя</th>
          <th>Вакансия</th>
          <th>Клиент</th>
          <th>HR-этап</th>
          {showReason ? <th>Что сделать</th> : null}
          <th>Оценка заказчика</th>
          <th>Город</th>
          <th>Последний контакт</th>
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
            <td>
              <StageMarker stage={c.hr_stage} />
            </td>
            {showReason ? <td>{c.attention_reason || "—"}</td> : null}
            <td>{clientStatusLabel(c.client_status)}</td>
            <td>{c.city || "—"}</td>
            <td>{formatLastContact(c.last_contact_at)}</td>
          </tr>
        ))}
        {!rows.length && !error ? (
          <tr>
            <td colSpan={cols}>Нет кандидатов в этой выборке</td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
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
  let attention: CandidateListItem[] = [];
  let error: string | null = null;
  let attentionError: string | null = null;

  if (hasFilters) {
    try {
      rows = await apiGet<CandidateListItem[]>(`/api/v1/candidates?${qs.toString()}`);
    } catch (e) {
      error = e instanceof Error ? e.message : "Ошибка API";
    }
  } else {
    try {
      attention = await apiGet<CandidateListItem[]>(
        "/api/v1/candidates?preset=attention&active_vacancies_only=true",
      );
    } catch (e) {
      attentionError = e instanceof Error ? e.message : "Ошибка API";
    }
  }

  const heading = titleFor({ hr_stage: hrStage, client_status: clientStatus, preset });
  const back = statsBackHref({ clientId, vacancyId, activeOnly });

  return (
    <AppShell activePath={hasFilters && preset !== "attention" ? "/stats" : "/candidates"}>
      {hasFilters && preset !== "attention" ? (
        <Link className="back" href={back}>
          ← К статистике
        </Link>
      ) : null}
      <h1 className="page-title">{hubMode ? "Кандидаты" : heading}</h1>

      {hubMode ? (
        <>
          <section className="cand-attention-list">
            <h2 style={{ fontSize: "1.15rem", margin: "0 0 0.35rem" }}>Требуют внимания</h2>
            <p className="muted">
              Активные вакансии · {attention.length}{" "}
              {attention.length === 1 ? "кандидат" : "кандидатов"}
            </p>
            {attentionError ? <p className="warn">{attentionError}</p> : null}
            <CandidatesTable rows={attention} error={attentionError} showReason />
            <p className="muted" style={{ marginTop: "0.75rem" }}>
              <Link href="/candidates?preset=attention&scope=active">Открыть полный inbox →</Link>
            </p>
          </section>
          <CandidateSearchPanel />
        </>
      ) : (
        <>
          <p className="muted">
            {rows.length} {rows.length === 1 ? "кандидат" : "кандидатов"}
            {activeOnly ? " · только вакансии в работе" : ""}
          </p>
          {error ? <p className="warn">{error}</p> : null}
          <CandidatesTable
            rows={rows}
            error={error}
            showReason={preset === "attention"}
          />
        </>
      )}
    </AppShell>
  );
}
