import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { AddCandidateForm } from "@/components/AddCandidateForm";
import { BulkLinksForm } from "@/components/BulkLinksForm";
import { DocumentsEditor } from "@/components/DocumentsEditor";
import { HhSearchPanel } from "@/components/HhSearchPanel";
import { YandexDiskPanel } from "@/components/YandexDiskPanel";
import { VacancyDigestButton } from "@/components/VacancyDigestButton";
import { VacancyLifecycle } from "@/components/VacancyLifecycle";
import { VacancySettingsPanel } from "@/components/VacancySettingsPanel";
import {
  apiGet,
  docLabel,
  outcomeLabel,
  type CandidateListItem,
  type VacancyDetail,
} from "@/lib/api";
import { daysBetween, daysLabel, formatDateRu } from "@/lib/dates";
import { clientStatusLabelForCard, hrStageLabel } from "@/lib/labels";

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ section?: string; candidate?: string }>;
};

type YandexDiskConfig = {
  vacancy_id: number;
  root_url: string;
  ingest_new_resumes: boolean;
  subfolders: Record<string, string>;
  last_sync_at: string | null;
  seen_count: number;
};

export default async function VacancyPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { section, candidate } = await searchParams;
  const view =
    section === "docs"
      ? "docs"
      : section === "hh"
        ? "hh"
        : section === "disk"
          ? "disk"
          : "candidates";

  let vacancy: VacancyDetail | null = null;
  let candidates: CandidateListItem[] = [];
  let diskConfig: YandexDiskConfig | null = null;
  let error: string | null = null;

  try {
    vacancy = await apiGet<VacancyDetail>(`/api/v1/vacancies/${id}`);
    candidates = await apiGet<CandidateListItem[]>(`/api/v1/vacancies/${id}/candidates`);
  } catch (e) {
    error = e instanceof Error ? e.message : "API error";
  }
  if (vacancy) {
    try {
      diskConfig = await apiGet<YandexDiskConfig>(`/api/v1/vacancies/${id}/yandex-disk`);
    } catch {
      diskConfig = {
        vacancy_id: vacancy.id,
        root_url: "",
        ingest_new_resumes: true,
        subfolders: {},
        last_sync_at: null,
        seen_count: 0,
      };
    }
  }

  const days = vacancy
    ? daysBetween(vacancy.created_at, vacancy.active ? null : vacancy.closed_at)
    : null;
  const docKeys = vacancy?.document_keys?.length ? vacancy.document_keys : [];

  return (
    <AppShell activePath="/vacancies">
      <Link
        className="back"
        href={vacancy?.active === false ? "/vacancies?tab=archive" : "/vacancies?tab=active"}
      >
        ← К списку вакансий
      </Link>
      {error ? <p className="warn">{error}</p> : null}
      {vacancy ? (
        <>
          <h1 className="page-title">
            {vacancy.title}
            {(vacancy.payload || {}).search_mode === "warranty" ? (
              <span className="muted"> · гарантийный поиск</span>
            ) : null}
            {(vacancy.payload || {}).is_test ? (
              <span className="muted"> · тест</span>
            ) : null}
          </h1>
          <p className="muted">
            {vacancy.client_name || "без клиента"} · #{vacancy.id}
          </p>

          <div className="meta-grid">
            <div className="meta-item">
              <span>Состояние</span>
              <strong>{vacancy.active ? "В работе" : "Архив"}</strong>
            </div>
            <div className="meta-item">
              <span>{vacancy.active ? "Старт" : "Период"}</span>
              <strong>
                {vacancy.active
                  ? `с ${formatDateRu(vacancy.created_at)}`
                  : `${formatDateRu(vacancy.created_at)} — ${formatDateRu(vacancy.closed_at)}`}
              </strong>
            </div>
            <div className="meta-item">
              <span>Длительность</span>
              <strong>{daysLabel(days)}</strong>
            </div>
            {!vacancy.active ? (
              <div className="meta-item">
                <span>Исход</span>
                <strong>
                  <span className={`outcome outcome-${vacancy.outcome || "none"}`}>
                    {outcomeLabel(vacancy.outcome)}
                  </span>
                </strong>
              </div>
            ) : null}
            <div className="meta-item">
              <span>Кандидаты</span>
              <strong>{vacancy.candidates_count ?? candidates.length}</strong>
            </div>
            <div className="meta-item">
              <span>Документы</span>
              <strong>{docKeys.length ? docKeys.map(docLabel).join(", ") : "нет"}</strong>
            </div>
          </div>

          <div className="tabs" role="tablist">
            <Link
              href={`/vacancies/${id}?section=candidates`}
              className={view === "candidates" ? "tab tab-active" : "tab"}
            >
              Кандидаты
              <span className="tab-count">{candidates.length}</span>
            </Link>
            <Link
              href={`/vacancies/${id}?section=docs`}
              className={view === "docs" ? "tab tab-active" : "tab"}
            >
              Документы
              <span className="tab-count">{docKeys.length}</span>
            </Link>
            <Link
              href={`/vacancies/${id}?section=hh`}
              className={view === "hh" ? "tab tab-active" : "tab"}
            >
              Поиск HH
            </Link>
            <Link
              href={`/vacancies/${id}?section=disk`}
              className={view === "disk" ? "tab tab-active" : "tab"}
            >
              Я.Диск
            </Link>
          </div>

          {view === "candidates" ? (
            <>
              <BulkLinksForm vacancyId={vacancy.id} />
              <AddCandidateForm vacancyId={vacancy.id} />
              <table>
                <thead>
                  <tr>
                    <th>Имя</th>
                    <th>HR-этап</th>
                    <th>Оценка заказчика</th>
                    <th>Город</th>
                    <th>Телефон</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link href={`/candidates/${c.id}`}>{c.name || "—"}</Link>
                      </td>
                      <td>{hrStageLabel(c.hr_stage)}</td>
                      <td>{clientStatusLabelForCard(c.hr_stage, c.client_status)}</td>
                      <td>{c.city || "—"}</td>
                      <td>{c.phone || "—"}</td>
                    </tr>
                  ))}
                  {!candidates.length ? (
                    <tr>
                      <td colSpan={5}>Нет кандидатов</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </>
          ) : null}

          {view === "docs" ? (
            <>
              {candidate ? (
                <p style={{ marginTop: 0 }}>
                  <Link className="back" href={`/candidates/${candidate}#questionnaire-settings`}>
                    ← К настройкам кандидата
                  </Link>
                </p>
              ) : null}
              <DocumentsEditor vacancyId={vacancy.id} initialDocuments={vacancy.documents || {}} />
            </>
          ) : null}

          {view === "hh" ? <HhSearchPanel vacancyId={vacancy.id} /> : null}

          {view === "disk" && diskConfig ? (
            <YandexDiskPanel vacancyId={vacancy.id} initial={diskConfig} />
          ) : null}

          <div className="vacancy-bottom-blocks">
            <VacancyDigestButton
              vacancyId={vacancy.id}
              hasChatId={Boolean((vacancy.chat_id || "").trim())}
            />
            <VacancySettingsPanel vacancy={vacancy} />
            <VacancyLifecycle vacancy={vacancy} />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
