import Link from "next/link";
import { RecruitingShell } from "@/components/RecruitingShell";
import { AddCandidateForm } from "@/components/AddCandidateForm";
import { CandidateCompactRow } from "@/components/CandidateCompactRow";
import { DocumentsEditor } from "@/components/DocumentsEditor";
import { HhSearchPanel } from "@/components/HhSearchPanel";
import { YandexDiskPanel } from "@/components/YandexDiskPanel";
import { VacancyTitleEditor } from "@/components/VacancyTitleEditor";
import { VacancyDigestButton } from "@/components/VacancyDigestButton";
import { VacancyReportButton } from "@/components/VacancyReportButton";
import { VacancyCloseButton } from "@/components/VacancyCloseButton";
import { VacancyLifecycle } from "@/components/VacancyLifecycle";
import { VacancySettingsPanel } from "@/components/VacancySettingsPanel";
import { ResumePreviewPanel } from "@/components/ResumePreviewPanel";
import { VacancyAvatar } from "@/components/VacancyAvatar";
import {
  apiGet,
  authMe,
  docLabel,
  outcomeLabel,
  type CandidateListItem,
  type VacancyDetail,
} from "@/lib/api";
import { daysBetween, daysLabel, formatDateRu } from "@/lib/dates";

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

type VacView = "candidates" | "docs" | "hh" | "disk" | "settings" | "resume-preview";

export default async function VacancyPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { section, candidate } = await searchParams;
  const viewer = await authMe().catch(() => null);
  const canUseResumePreview = Boolean(
    viewer && (viewer.auth_disabled || (viewer.roles || []).includes("platform_owner")),
  );

  let hhSearchEnabled = true;
  let intake = {
    manual: true,
    file_upload: true,
    file_link: false,
    disk_public_sync: false,
    disk_inbox: false,
  };
  try {
    const app = await apiGet<{
      functions?: { hh_search_enabled?: boolean };
      candidate_intake_effective?: Partial<typeof intake>;
    }>(`/api/v1/settings/app`);
    hhSearchEnabled = app.functions?.hh_search_enabled !== false;
    if (app.candidate_intake_effective) {
      intake = {
        manual: app.candidate_intake_effective.manual !== false,
        file_upload: app.candidate_intake_effective.file_upload !== false,
        file_link: Boolean(app.candidate_intake_effective.file_link),
        disk_public_sync: Boolean(app.candidate_intake_effective.disk_public_sync),
        disk_inbox: Boolean(app.candidate_intake_effective.disk_inbox),
      };
    }
  } catch {
    hhSearchEnabled = true;
    intake = {
      manual: true,
      file_upload: true,
      file_link: true,
      disk_public_sync: true,
      disk_inbox: true,
    };
  }

  const viewFromSection: VacView =
    section === "docs"
      ? "docs"
      : section === "hh"
        ? "hh"
        : section === "disk"
          ? "disk"
          : section === "settings"
            ? "settings"
            : section === "resume-preview"
              ? "resume-preview"
            : "candidates";
  let view: VacView = viewFromSection === "hh" && !hhSearchEnabled ? "candidates" : viewFromSection;
  if (view === "disk" && !intake.disk_public_sync) {
    view = "candidates";
  }
  if (view === "resume-preview" && !canUseResumePreview) {
    view = "candidates";
  }

  let vacancy: VacancyDetail | null = null;
  let candidates: CandidateListItem[] = [];
  let diskConfig: YandexDiskConfig | null = null;
  let error: string | null = null;
  let previewCount = 0;

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
  if (vacancy && canUseResumePreview) {
    try {
      const pack = await apiGet<{ included_count?: number }>(
        `/api/v1/vacancies/${id}/resume-preview`,
      );
      previewCount = Number(pack.included_count) || 0;
    } catch {
      previewCount = 0;
    }
  }

  const days = vacancy
    ? daysBetween(vacancy.created_at, vacancy.active ? null : vacancy.closed_at)
    : null;
  const docKeys = vacancy?.document_keys?.length ? vacancy.document_keys : [];
  const candCount = vacancy?.candidates_count ?? candidates.length;
  const isWarranty = (vacancy?.payload || {}).search_mode === "warranty";
  const isTest = Boolean((vacancy?.payload || {}).is_test);

  return (
    <RecruitingShell activePath="/vacancies" title={vacancy?.title || "Вакансия"}>
      <Link
        className="rec-back"
        href={vacancy?.active === false ? "/vacancies?tab=archive" : "/vacancies?tab=active"}
      >
        ← К списку вакансий
      </Link>
      {error ? <p className="warn">{error}</p> : null}

      {vacancy ? (
        <>
          <div className="rec-card vac-head">
            <div className="vac-head-main">
              <div className="vac-head-title-row">
                <VacancyAvatar
                  avatarKey={vacancy.avatar_key || (vacancy.payload as { avatar_key?: string })?.avatar_key}
                  size={48}
                />
                <VacancyTitleEditor
                  vacancyId={vacancy.id}
                  title={vacancy.title}
                  searchModeWarranty={isWarranty}
                  isTest={isTest}
                />
              </div>
              <p className="vac-head-meta">
                {[
                  vacancy.client_name || "без клиента",
                  `#${vacancy.id}`,
                  vacancy.active ? "В работе" : "Архив",
                  daysLabel(days),
                ].join(" · ")}
              </p>
              <div className="vac-head-chips">
                <span className="cand-workspace-badge">
                  {candCount}{" "}
                  {candCount === 1 ? "кандидат" : candCount < 5 ? "кандидата" : "кандидатов"}
                </span>
                <span className="cand-workspace-badge">
                  {docKeys.length
                    ? `${docKeys.length} док. · ${docKeys.map(docLabel).join(", ")}`
                    : "нет документов"}
                </span>
                {vacancy.active ? (
                  <span className="cand-workspace-badge is-accent">
                    с {formatDateRu(vacancy.created_at)}
                  </span>
                ) : (
                  <span className="cand-workspace-badge">
                    {formatDateRu(vacancy.created_at)} — {formatDateRu(vacancy.closed_at)}
                    {" · "}
                    {outcomeLabel(vacancy.outcome)}
                  </span>
                )}
              </div>
            </div>
            <div className="vac-head-actions">
              <VacancyCloseButton vacancy={vacancy} />
            </div>
          </div>

          <nav className="cand-tabs" role="tablist" aria-label="Разделы вакансии">
            <Link
              href={`/vacancies/${id}?section=candidates`}
              className={`cand-tab${view === "candidates" ? " is-active" : ""}`}
              role="tab"
              aria-selected={view === "candidates"}
            >
              Кандидаты
              <span className="tab-count">{candidates.length}</span>
            </Link>
            <Link
              href={`/vacancies/${id}?section=docs`}
              className={`cand-tab${view === "docs" ? " is-active" : ""}`}
              role="tab"
              aria-selected={view === "docs"}
            >
              Документы
              <span className="tab-count">{docKeys.length}</span>
            </Link>
            {hhSearchEnabled ? (
              <Link
                href={`/vacancies/${id}?section=hh`}
                className={`cand-tab${view === "hh" ? " is-active" : ""}`}
                role="tab"
                aria-selected={view === "hh"}
              >
                Поиск HH
              </Link>
            ) : null}
            {intake.disk_public_sync ? (
              <Link
                href={`/vacancies/${id}?section=disk`}
                className={`cand-tab${view === "disk" ? " is-active" : ""}`}
                role="tab"
                aria-selected={view === "disk"}
              >
                Я.Диск
              </Link>
            ) : null}
            <Link
              href={`/vacancies/${id}?section=settings`}
              className={`cand-tab${view === "settings" ? " is-active" : ""}`}
              role="tab"
              aria-selected={view === "settings"}
            >
              Настройки
            </Link>
            {canUseResumePreview ? (
              <Link
                href={`/vacancies/${id}?section=resume-preview`}
                className={`cand-tab${view === "resume-preview" ? " is-active" : ""}`}
                role="tab"
                aria-selected={view === "resume-preview"}
              >
                Макеты резюме
                <span className="tab-count">{previewCount}</span>
              </Link>
            ) : null}
          </nav>

          {view === "candidates" ? (
            <div className="vac-cand-stack">
              <div className="rec-card">
                <AddCandidateForm vacancyId={vacancy.id} intake={intake} />
                {candidates.length ? (
                  <div className="vac-cand-list">
                    {candidates.map((c) => (
                      <CandidateCompactRow
                        key={c.id}
                        candidate={c}
                        subtitle={[c.city, c.phone].filter(Boolean).join(" · ") || "—"}
                        compact
                      />
                    ))}
                  </div>
                ) : (
                  <p className="rec-empty">Нет кандидатов по этой вакансии</p>
                )}
              </div>
            </div>
          ) : null}

          {view === "docs" ? (
            <div className="rec-card">
              {candidate ? (
                <p style={{ marginTop: 0 }}>
                  <Link className="rec-back" href={`/candidates/${candidate}#questionnaire-settings`}>
                    ← К настройкам кандидата
                  </Link>
                </p>
              ) : null}
              <DocumentsEditor
                vacancyId={vacancy.id}
                vacancyTitle={vacancy.title || ""}
                initialDocuments={vacancy.documents || {}}
              />
            </div>
          ) : null}

          {view === "hh" ? (
            <div className="rec-card">
              <HhSearchPanel vacancyId={vacancy.id} />
            </div>
          ) : null}

          {view === "disk" && diskConfig ? (
            <div className="rec-card">
              <YandexDiskPanel vacancyId={vacancy.id} initial={diskConfig} />
            </div>
          ) : null}

          {view === "settings" ? (
            <div className="vac-settings-stack">
              <div className="rec-card">
                <h3 className="rec-card-title">Отчёт заказчику</h3>
                <VacancyReportButton
                  vacancyId={vacancy.id}
                  clientId={vacancy.client_id}
                  hasChatId={Boolean((vacancy.chat_id || "").trim())}
                />
              </div>
              <div className="rec-card">
                <h3 className="rec-card-title">Сводка (старая)</h3>
                <VacancyDigestButton
                  vacancyId={vacancy.id}
                  hasChatId={Boolean((vacancy.chat_id || "").trim())}
                />
              </div>
              <VacancySettingsPanel vacancy={vacancy} />
              <VacancyLifecycle vacancy={vacancy} />
            </div>
          ) : null}

          {view === "resume-preview" && canUseResumePreview ? (
            <ResumePreviewPanel
              vacancyId={vacancy.id}
              hasChatId={Boolean((vacancy.chat_id || "").trim())}
            />
          ) : null}
        </>
      ) : null}
    </RecruitingShell>
  );
}
