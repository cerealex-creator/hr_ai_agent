"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import { DemoBanner } from "@/components/DemoBanner";
import { zoneFetch } from "@/lib/clientZone";
import styles from "./report.module.css";

type FunnelStep = { key: string; label: string; value: number };

type ReportData = {
  company: { name: string; department_name?: string | null };
  vacancy: { id: number; title: string; active: boolean; period: string };
  funnel_main: FunnelStep[];
  funnel_side: FunnelStep[];
  funnel_rejects: FunnelStep[];
  reject_total: number;
  summary: string;
  demo?: boolean;
};

type CohortCand = {
  id: string;
  name: string;
  status_label: string;
  stage_label: string;
  hr_comment?: string | null;
  history_reason?: string | null;
  ai_score?: number | null;
  has_resume?: boolean;
  has_video?: boolean;
  has_digest?: boolean;
  has_portfolio?: boolean;
  photo_url?: string | null;
  gender?: string | null;
  phone?: string | null;
};

type CohortData = {
  cohort: { key: string; label: string; total: number };
  vacancy: { id: number; title: string };
  candidates: CohortCand[];
};

type DetailData = {
  vacancy: { id: number; title: string };
  candidate: CohortCand & {
    resume_url?: string | null;
    video_url?: string | null;
    portfolio_url?: string | null;
    task_url?: string | null;
    hr_comment?: string | null;
    ai_comment?: string | null;
    ai_strengths?: string[];
    ai_weaknesses?: string[];
    interview_digest?: { summary?: string; qa?: { q: string; a: string }[] } | null;
    meeting?: string | null;
  };
};

type View = "report" | "cohort" | "detail";

function materialsLabel(c: CohortCand): string {
  return (
    [
      c.has_resume ? "резюме" : null,
      c.has_portfolio ? "портфолио" : null,
      c.has_video ? "запись" : null,
      c.has_digest ? "конспект" : null,
    ]
      .filter(Boolean)
      .join(" · ") || "—"
  );
}

export default function ClientZoneReportPage() {
  const params = useParams();
  const router = useRouter();
  const token = String(params.token || "");
  const vacancyId = String(params.vacancyId || "");

  const [view, setView] = useState<View>("report");
  const [report, setReport] = useState<ReportData | null>(null);
  const [cohort, setCohort] = useState<CohortData | null>(null);
  const [detail, setDetail] = useState<DetailData | null>(null);
  const [cohortKey, setCohortKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [digestOpen, setDigestOpen] = useState(false);

  const loadReport = useCallback(async () => {
    const res = await zoneFetch(
      `/api/v1/client-zone/${encodeURIComponent(token)}/reports/${encodeURIComponent(vacancyId)}`,
    );
    if (!res.ok) {
      setError(res.status === 404 ? "Отчёт не найден" : `Ошибка ${res.status}`);
      setReport(null);
      return;
    }
    setReport((await res.json()) as ReportData);
    setError(null);
  }, [token, vacancyId]);

  useEffect(() => {
    if (!token || !vacancyId) return;
    loadReport().catch((e) => setError(e instanceof Error ? e.message : "Ошибка"));
  }, [token, vacancyId, loadReport]);

  const openCohort = async (key: string, value: number) => {
    if (value <= 0) return;
    setError(null);
    const res = await zoneFetch(
      `/api/v1/client-zone/${encodeURIComponent(token)}/reports/${encodeURIComponent(vacancyId)}/cohorts/${encodeURIComponent(key)}`,
    );
    if (!res.ok) {
      setError(`Не удалось открыть срез (${res.status})`);
      return;
    }
    setCohort((await res.json()) as CohortData);
    setCohortKey(key);
    setDetail(null);
    setView("cohort");
  };

  const openDetail = async (candidateId: string) => {
    setError(null);
    setAiOpen(false);
    setDigestOpen(false);
    const res = await zoneFetch(
      `/api/v1/client-zone/${encodeURIComponent(token)}/reports/${encodeURIComponent(vacancyId)}/candidates/${encodeURIComponent(candidateId)}`,
    );
    if (!res.ok) {
      setError(`Кандидат не найден (${res.status})`);
      return;
    }
    setDetail((await res.json()) as DetailData);
    setView("detail");
  };

  const c = detail?.candidate;

  return (
    <div className="cz-page">
      {report?.demo ? <DemoBanner /> : null}
      <header className="cz-header">
        {view === "detail" ? (
          <button
            type="button"
            className="cz-back"
            onClick={() => {
              setView(cohortKey ? "cohort" : "report");
              setDetail(null);
            }}
          >
            ← {cohortKey ? "К списку среза" : "К отчёту"}
          </button>
        ) : view === "cohort" ? (
          <button
            type="button"
            className="cz-back"
            onClick={() => {
              setView("report");
              setCohort(null);
              setCohortKey(null);
            }}
          >
            ← К картине работы
          </button>
        ) : (
          <button type="button" className="cz-back" onClick={() => router.push(`/c/${token}`)}>
            ← Зона заказчика
          </button>
        )}
        <div className={styles.headerBrand}>
          <p className="cz-kicker">Зона заказчика · отчёт</p>
          <h1 className="cz-title">{report?.company.name || "Загрузка…"}</h1>
          {report?.company.department_name ? (
            <p className={`cz-place ${styles.headerPlace}`}>{report.company.department_name}</p>
          ) : null}
        </div>
      </header>

      {error ? <p className="warn cz-banner">{error}</p> : null}

      {view === "report" && report ? (
        <>
          <div className="cz-header" style={{ marginBottom: "0.85rem" }}>
            <h2 className="cz-section-title">{report.vacancy.title}</h2>
            <p className={styles.period}>
              {report.vacancy.period}
              {report.vacancy.active ? "" : " · архив"}
            </p>
            <p className={styles.viewerHint}>
              Нажмите на цифру — список кандидатов этого среза. Карточки только на просмотр.
            </p>
            <blockquote className={styles.hrSummary}>{report.summary}</blockquote>
          </div>

          <section className={styles.funnelBlock} aria-label="Воронка подбора">
            <h3 className={styles.funnelTitle}>Картина работы</h3>
            <div className={styles.funnelBar}>
              {report.funnel_main.map((step) => (
                <button
                  key={step.key}
                  type="button"
                  className={styles.funnelSegBtn}
                  style={{
                    flex: Math.max(step.value, 1),
                    background: `hsl(${210 - report.funnel_main.indexOf(step) * 12} 45% ${72 - report.funnel_main.indexOf(step) * 6}%)`,
                  }}
                  title={`${step.label}: ${step.value}`}
                  onClick={() => void openCohort(step.key, step.value)}
                  aria-label={`${step.label}: ${step.value}`}
                />
              ))}
            </div>
            <div className={styles.funnelGrid}>
              {report.funnel_main.map((step) => (
                <button
                  key={step.key}
                  type="button"
                  className={styles.funnelStatBtn}
                  disabled={step.value <= 0}
                  onClick={() => void openCohort(step.key, step.value)}
                >
                  <span className={styles.funnelStatNum}>{step.value}</span>
                  <span className={styles.funnelStatLabel}>{step.label}</span>
                  {step.value > 0 ? (
                    <span className={styles.funnelStatAction}>Смотреть список →</span>
                  ) : null}
                </button>
              ))}
            </div>

            <div className={styles.funnelAside}>
              <p className={styles.funnelAsideTitle}>Исходы вне воронки</p>
              {report.funnel_side.map((step) =>
                step.value > 0 ? (
                  <button
                    key={step.key}
                    type="button"
                    className={`${styles.funnelStatBtn} ${styles.funnelStatAside}`}
                    onClick={() => void openCohort(step.key, step.value)}
                  >
                    <span className={styles.funnelStatNum}>{step.value}</span>
                    <span className={styles.funnelStatLabel}>{step.label}</span>
                    <span className={styles.funnelStatAction}>Смотреть →</span>
                  </button>
                ) : (
                  <div
                    key={step.key}
                    className={`${styles.funnelStat} ${styles.funnelStatAside} ${styles.funnelStatMuted}`}
                  >
                    <span className={styles.funnelStatNum}>0</span>
                    <span className={styles.funnelStatLabel}>{step.label}</span>
                  </div>
                ),
              )}
              <p className={styles.rejectLead}>
                <strong>{report.reject_total}</strong> получили отказ:
              </p>
              <div className={styles.rejectList}>
                {report.funnel_rejects.map((step) => (
                  <button
                    key={step.key}
                    type="button"
                    className={styles.rejectRow}
                    disabled={step.value <= 0}
                    onClick={() => void openCohort(step.key, step.value)}
                  >
                    <span className={styles.rejectNum}>{step.value}</span>
                    <span className={styles.rejectLabel}>{step.label}</span>
                    <span className={styles.funnelStatAction}>{step.value > 0 ? "→" : ""}</span>
                  </button>
                ))}
              </div>
            </div>
          </section>
          <p className={styles.readOnlyNote}>
            Режим просмотра: без смены статусов. Контакты пока видны; скрытие включим позже.
          </p>
        </>
      ) : null}

      {view === "cohort" && cohort ? (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h3 className={styles.sectionTitle}>{cohort.cohort.label}</h3>
            <p className={styles.sectionHint}>{cohort.cohort.total} · только просмотр</p>
          </div>
          {cohort.candidates.length === 0 ? (
            <p className={styles.readOnlyNote}>В этом срезе никого нет.</p>
          ) : (
            <div className="cz-list">
              {cohort.candidates.map((row) => (
                <button
                  key={row.id}
                  type="button"
                  className="cz-card cz-card-link cz-card-done"
                  onClick={() => void openDetail(row.id)}
                >
                  <div className="cz-card-top">
                    <div className="cz-card-identity">
                      <CandidateAvatar
                        name={row.name}
                        photoUrl={row.photo_url}
                        gender={row.gender}
                        size={44}
                        className="cz-avatar"
                      />
                      <h2>{row.name}</h2>
                    </div>
                    <span className="cz-pill cz-pill-status">{row.status_label}</span>
                  </div>
                  <p className="cz-vacancy">{cohort.vacancy.title}</p>
                  {row.history_reason || row.hr_comment ? (
                    <p className="cz-card-meta">{row.history_reason || row.hr_comment}</p>
                  ) : null}
                  <p className="cz-card-meta muted hh-micro">
                    {row.stage_label} · {materialsLabel(row)}
                  </p>
                  <span className="cz-tap cz-tap-ghost">Смотреть кандидата</span>
                </button>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {view === "detail" && c ? (
        <div className="cz-page-detail">
          <div className={styles.viewerBadge}>Только просмотр · без права менять статусы</div>
          <div className="cz-detail-head">
            <CandidateAvatar
              name={c.name}
              photoUrl={c.photo_url}
              gender={c.gender}
              size={64}
              className="cz-avatar"
            />
            <div className="cz-detail-head-text">
              <h1 className="cz-title">{c.name}</h1>
              <p className="cz-vacancy">{detail?.vacancy.title}</p>
              <div className="cz-pills">
                <span className="cz-pill cz-pill-status">{c.status_label}</span>
                <span className="cz-pill">{c.stage_label}</span>
                {c.ai_score != null ? <span className="cz-pill">ИИ {c.ai_score}</span> : null}
              </div>
            </div>
          </div>

          {c.phone ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Контакты</h2>
              <p>{c.phone}</p>
            </section>
          ) : null}

          {c.meeting ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Встреча</h2>
              <p>{c.meeting}</p>
            </section>
          ) : null}

          {c.hr_comment ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Комментарий HR</h2>
              <p className="cz-comment">{c.hr_comment}</p>
            </section>
          ) : null}

          {c.history_reason ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Причина / итог</h2>
              <p>{c.history_reason}</p>
            </section>
          ) : null}

          {(c.resume_url ||
            c.portfolio_url ||
            c.video_url ||
            c.task_url ||
            c.interview_digest ||
            c.ai_score != null) && (
            <section className="cz-section">
              <h2 className="cz-section-title">Материалы</h2>
              <div className="cz-link-stack">
                {c.resume_url ? (
                  <a href={c.resume_url} target="_blank" rel="noreferrer" className="cz-tap cz-tap-primary">
                    Смотреть резюме
                  </a>
                ) : null}
                {c.portfolio_url ? (
                  <a href={c.portfolio_url} target="_blank" rel="noreferrer" className="cz-tap">
                    Портфолио
                  </a>
                ) : null}
                {c.video_url ? (
                  <a href={c.video_url} target="_blank" rel="noreferrer" className="cz-tap">
                    Смотреть запись
                  </a>
                ) : null}
                {c.task_url ? (
                  <a href={c.task_url} target="_blank" rel="noreferrer" className="cz-tap">
                    Задание
                  </a>
                ) : null}
                {c.interview_digest ? (
                  <button
                    type="button"
                    className={`cz-tap${digestOpen ? " is-active" : ""}`}
                    onClick={() => setDigestOpen((v) => !v)}
                  >
                    {digestOpen ? "Скрыть конспект собеседования" : "Конспект собеседования"}
                  </button>
                ) : null}
                {c.ai_score != null || c.ai_comment || c.ai_strengths?.length ? (
                  <button
                    type="button"
                    className={`cz-tap${aiOpen ? " is-active" : ""}`}
                    onClick={() => setAiOpen((v) => !v)}
                  >
                    {aiOpen ? "Скрыть оценку ИИ" : "Оценка ИИ"}
                  </button>
                ) : null}
              </div>
              {digestOpen && c.interview_digest ? (
                <div className="q-digest cz-digest">
                  {c.interview_digest.summary ? (
                    <p className="q-digest-summary">{c.interview_digest.summary}</p>
                  ) : null}
                  {(c.interview_digest.qa || []).map((row, i) => (
                    <div key={`${i}-${row.q.slice(0, 20)}`} className="q-digest-item">
                      <p className="q-digest-q">
                        <strong>В:</strong> {row.q || "—"}
                      </p>
                      <p className="q-digest-a">
                        <strong>О:</strong> {row.a || "—"}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
              {aiOpen ? (
                <div className={styles.aiBlock}>
                  {c.ai_score != null ? (
                    <p className={styles.aiScore}>ИИ {c.ai_score} / 100</p>
                  ) : null}
                  {c.ai_comment ? <p className="cz-comment">{c.ai_comment}</p> : null}
                  {c.ai_strengths?.length ? (
                    <>
                      <p className="muted hh-micro">Плюсы</p>
                      <ul className={styles.aiList}>
                        {c.ai_strengths.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                  {c.ai_weaknesses?.length ? (
                    <>
                      <p className="muted hh-micro">Минусы</p>
                      <ul className={styles.aiList}>
                        {c.ai_weaknesses.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </div>
              ) : null}
            </section>
          )}

          <p className="muted cz-banner">Решение менять нельзя — это отчёт, не рабочий список.</p>
          <p className={styles.readOnlyNote}>
            <Link href={`/c/${token}`}>← Вернуться в зону заказчика</Link>
          </p>
        </div>
      ) : null}

      {!report && !error ? <p className="muted">Загрузка отчёта…</p> : null}
    </div>
  );
}
