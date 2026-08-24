"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CandidateAvatar } from "@/components/CandidateAvatar";
import styles from "./report.module.css";

type Tab = "decisions" | "reports";
type View = "hub" | "report" | "cohort" | "detail";

type CohortKey =
  | "selected"
  | "contact"
  | "interview"
  | "to_client"
  | "meeting"
  | "offer"
  | "no_reply"
  | "rej_client"
  | "rej_hr"
  | "rej_cand";

type MockCandidate = {
  id: string;
  name: string;
  gender?: "m" | "f" | null;
  status_label: string;
  stage_label: string;
  hr_comment?: string;
  ai_score?: number;
  ai_strengths?: string[];
  ai_weaknesses?: string[];
  has_resume?: boolean;
  has_video?: boolean;
  has_digest?: boolean;
  has_portfolio?: boolean;
  meeting?: string;
  decided_by?: string;
  decided_at?: string;
  history_reason?: string;
  phone?: string;
};

/** Цифры с закрытой вакансии id=3 «Графический дизайнер» (прод). */
const COMPANY = "Маркетинг";
const VACANCY = "Графический дизайнер";
const PERIOD = "5 июня — 3 августа 2026";

type FunnelStep = {
  key: CohortKey;
  label: string;
  value: number;
  color: string;
};

const FUNNEL_MAIN: FunnelStep[] = [
  { key: "selected", label: "Отобрано из базы и откликов", value: 41, color: "#c8d4e6" },
  { key: "contact", label: "Вышли на контакт", value: 39, color: "#9eb8dc" },
  { key: "interview", label: "Первое собеседование", value: 30, color: "#6f98cf" },
  { key: "to_client", label: "Направлено на оценку", value: 18, color: "#4a7fc4" },
  { key: "meeting", label: "Встреча с заказчиком", value: 4, color: "#2e6fd6" },
  { key: "offer", label: "Получили оффер", value: 1, color: "#1a4fa8" },
];

const FUNNEL_NO_REPLY: FunnelStep = {
  key: "no_reply",
  label: "Зависли без ответа (более суток)",
  value: 0,
  color: "#b8a99a",
};

/** Разбивка отказов по статусам (текущий hr_stage на закрытой вакансии). */
const FUNNEL_REJECTS: FunnelStep[] = [
  { key: "rej_client", label: "отклонены заказчиком", value: 17, color: "#c4a0a0" },
  { key: "rej_hr", label: "отклонены рекрутером", value: 17, color: "#c4a0a0" },
  { key: "rej_cand", label: "отказались сами", value: 6, color: "#c4a0a0" },
];

const COHORT_TITLES: Record<CohortKey, string> = {
  selected: "Отобрано из базы и откликов",
  contact: "Вышли на контакт",
  interview: "Первое собеседование",
  to_client: "Направлено на оценку",
  meeting: "Встреча с заказчиком",
  offer: "Получили оффер",
  no_reply: "Зависли без ответа",
  rej_client: "Отклонены заказчиком",
  rej_hr: "Отклонены рекрутером",
  rej_cand: "Отказались сами",
};

/** Примеры карточек в каждом срезе (в бою — полный список по API). */
const COHORT_SAMPLES: Record<CohortKey, MockCandidate[]> = {
  selected: [
    {
      id: "s1",
      name: "Анна К.",
      gender: "f",
      status_label: "В чат не отправлен",
      stage_label: "Отсев резюме",
      has_resume: true,
      ai_score: 64,
      hr_comment: "Портфолио слабое под карточки MP — оставили в базе на всякий случай.",
    },
    {
      id: "s2",
      name: "Дмитрий В.",
      gender: "m",
      status_label: "Отказ HR",
      stage_label: "Первый контакт",
      has_resume: true,
      history_reason: "Не готов к срокам тестового",
    },
    {
      id: "s3",
      name: "Елизавета Е.",
      gender: "f",
      status_label: "Вышла на работу",
      stage_label: "Вышла на работу",
      has_resume: true,
      has_digest: true,
      has_portfolio: true,
      ai_score: 86,
      phone: "+7 ··· ···-12-34",
      hr_comment: "Финальный кандидат — оффер принят.",
      ai_strengths: ["Сильное портфолио карточек MP", "Быстрый цикл правок"],
      ai_weaknesses: ["Мало motion"],
    },
  ],
  contact: [
    {
      id: "c1",
      name: "Мария П.",
      gender: "f",
      status_label: "Отказ HR",
      stage_label: "Первый контакт",
      has_resume: true,
      phone: "+7 ··· ···-45-67",
      history_reason: "Зарплатные ожидания выше вилки",
    },
    {
      id: "c2",
      name: "Сергей Л.",
      gender: "m",
      status_label: "Отказ HR",
      stage_label: "Первый контакт",
      has_resume: true,
      hr_comment: "Созвонились: интерес есть, но вилка не сходится.",
    },
  ],
  interview: [
    {
      id: "i1",
      name: "Изабелла Т.",
      gender: "f",
      status_label: "Отказ кандидата",
      stage_label: "Первое собеседование",
      has_resume: true,
      has_video: true,
      has_digest: true,
      ai_score: 71,
      history_reason: "Кандидат пропал после собеседования",
      hr_comment: "По собеседованию ок, на связь после не вышла.",
    },
    {
      id: "i2",
      name: "Ольга А.",
      gender: "f",
      status_label: "Отказ заказчика",
      stage_label: "На оценке",
      has_resume: true,
      has_digest: true,
      has_portfolio: true,
      ai_score: 79,
      decided_by: "Виктория Леонова",
      decided_at: "03.07.2026",
      history_reason: "Стиль не совпал с брендом",
    },
  ],
  to_client: [
    {
      id: "t1",
      name: "Анастасия С.",
      gender: "f",
      status_label: "Отказ заказчика",
      stage_label: "На оценке",
      has_resume: true,
      has_portfolio: true,
      ai_score: 74,
      decided_by: "Виктория Леонова",
      decided_at: "12.07.2026",
      history_reason: "Стиль не совпал с брендом",
      hr_comment: "Сильное портфолио, но тон визуала другой.",
    },
    {
      id: "t2",
      name: "Дарья З.",
      gender: "f",
      status_label: "Отказ заказчика",
      stage_label: "На оценке",
      has_resume: true,
      has_video: true,
      decided_by: "Alexandr Krupin",
      decided_at: "18.07.2026",
      history_reason: "Отказ в клиентской зоне",
    },
  ],
  meeting: [
    {
      id: "m1",
      name: "Елизавета Ез.",
      gender: "f",
      status_label: "Отказ заказчика",
      stage_label: "Встреча с заказчиком",
      has_resume: true,
      has_digest: true,
      meeting: "Встреча проведена · июль 2026",
      decided_by: "клиентская зона",
      history_reason: "После встречи — отказ",
    },
    {
      id: "m2",
      name: "Елизавета Е.",
      gender: "f",
      status_label: "Вышла на работу",
      stage_label: "Вышла на работу",
      has_resume: true,
      has_digest: true,
      has_portfolio: true,
      meeting: "Встреча проведена · июль 2026",
      ai_score: 86,
      hr_comment: "После встречи — оффер и выход.",
    },
  ],
  offer: [
    {
      id: "o1",
      name: "Елизавета Е.",
      gender: "f",
      status_label: "Вышла на работу",
      stage_label: "Вышла на работу",
      has_resume: true,
      has_digest: true,
      has_portfolio: true,
      phone: "+7 ··· ···-12-34",
      ai_score: 86,
      hr_comment: "Оффер принят, вышла на работу.",
      ai_strengths: ["Сильное портфолио карточек MP", "Быстрый цикл правок", "Опыт с брендами одежды"],
      ai_weaknesses: ["Мало motion / анимации"],
    },
  ],
  no_reply: [],
  rej_client: [
    {
      id: "rc1",
      name: "Анастасия С.",
      gender: "f",
      status_label: "Отказ заказчика",
      stage_label: "На оценке",
      has_resume: true,
      decided_by: "Виктория Леонова",
      decided_at: "12.07.2026",
      history_reason: "Стиль не совпал с брендом",
    },
    {
      id: "rc2",
      name: "Дарья З.",
      gender: "f",
      status_label: "Отказ заказчика",
      stage_label: "На оценке",
      has_resume: true,
      decided_by: "Alexandr Krupin",
      decided_at: "18.07.2026",
      history_reason: "Отказ в клиентской зоне (Telegram)",
    },
    {
      id: "rc3",
      name: "Елизавета Ез.",
      gender: "f",
      status_label: "Отказ заказчика",
      stage_label: "Встреча с заказчиком",
      has_resume: true,
      has_digest: true,
      decided_by: "клиентская зона",
      history_reason: "После встречи",
    },
  ],
  rej_hr: [
    {
      id: "rh1",
      name: "Мария П.",
      gender: "f",
      status_label: "Отказ HR",
      stage_label: "Отсев резюме",
      has_resume: true,
      history_reason: "Портфолио не под маркетплейсы",
    },
    {
      id: "rh2",
      name: "Сергей Л.",
      gender: "m",
      status_label: "Отказ HR",
      stage_label: "Первый контакт",
      has_resume: true,
      history_reason: "Зарплатные ожидания выше вилки",
    },
    {
      id: "rh3",
      name: "Игорь Н.",
      gender: "m",
      status_label: "Отказ HR",
      stage_label: "Первое собеседование",
      has_resume: true,
      has_video: true,
      history_reason: "Слабая презентация кейсов",
    },
  ],
  rej_cand: [
    {
      id: "rk1",
      name: "Изабелла Т.",
      gender: "f",
      status_label: "Отказ кандидата",
      stage_label: "Первое собеседование",
      has_resume: true,
      history_reason: "Кандидат пропал",
    },
    {
      id: "rk2",
      name: "Пелагея Р.",
      gender: "f",
      status_label: "Отказ кандидата",
      stage_label: "Тестовое",
      has_resume: true,
      history_reason: "Выбрала другое место",
    },
    {
      id: "rk3",
      name: "Юлия Л.",
      gender: "f",
      status_label: "Отказ кандидата",
      stage_label: "Тестовое",
      has_resume: true,
      history_reason: "Уже не актуально",
    },
  ],
};

const COHORT_TOTALS: Record<CohortKey, number> = {
  selected: 41,
  contact: 39,
  interview: 30,
  to_client: 18,
  meeting: 4,
  offer: 1,
  no_reply: 0,
  rej_client: 17,
  rej_hr: 17,
  rej_cand: 6,
};

const ALL_CANDIDATES = Object.values(COHORT_SAMPLES).flat();

function materialsLabel(c: MockCandidate): string {
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

export default function ClientReportMockPage() {
  const [tab, setTab] = useState<Tab>("reports");
  const [view, setView] = useState<View>("hub");
  const [cohortKey, setCohortKey] = useState<CohortKey | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [digestOpen, setDigestOpen] = useState(false);

  const cohortList = useMemo(
    () => (cohortKey ? COHORT_SAMPLES[cohortKey] : []),
    [cohortKey],
  );

  const detail = useMemo(() => {
    if (!detailId) return null;
    return (
      ALL_CANDIDATES.find((c) => c.id === detailId) ||
      cohortList.find((c) => c.id === detailId) ||
      null
    );
  }, [detailId, cohortList]);

  const openCohort = (key: CohortKey) => {
    if (COHORT_TOTALS[key] <= 0) return;
    setCohortKey(key);
    setDetailId(null);
    setView("cohort");
  };

  const openDetail = (id: string) => {
    setDetailId(id);
    setView("detail");
    setAiOpen(false);
    setDigestOpen(false);
  };

  const backFromDetail = () => {
    if (cohortKey) {
      setView("cohort");
      setDetailId(null);
      return;
    }
    setView("report");
    setDetailId(null);
  };

  const backFromCohort = () => {
    setView("report");
    setCohortKey(null);
  };

  return (
    <div className="cz-page">
      <header className="cz-header">
        {view === "detail" ? (
          <button type="button" className="cz-back" onClick={backFromDetail}>
            ← {cohortKey ? "К списку среза" : "К отчёту"}
          </button>
        ) : view === "cohort" ? (
          <button type="button" className="cz-back" onClick={backFromCohort}>
            ← К картине работы
          </button>
        ) : view === "report" ? (
          <button type="button" className="cz-back" onClick={() => setView("hub")}>
            ← Все отчёты
          </button>
        ) : null}

        <div className={styles.headerBrand}>
          <p className="cz-kicker">Зона заказчика · режим просмотра</p>
          <h1 className="cz-title">{COMPANY}</h1>
        </div>

        {view !== "detail" && view !== "cohort" ? (
          <>
            <div className={styles.tabs} role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={tab === "decisions"}
                className={`${styles.tab}${tab === "decisions" ? ` ${styles.tabActive}` : ""}`}
                onClick={() => {
                  setTab("decisions");
                  setView("hub");
                }}
              >
                Решения
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === "reports"}
                className={`${styles.tab}${tab === "reports" ? ` ${styles.tabActive}` : ""}`}
                onClick={() => {
                  setTab("reports");
                  setView("hub");
                }}
              >
                Отчёты
              </button>
            </div>
            {tab === "decisions" ? (
              <p className="muted">Где нужно ваше решение — как сейчас в /c/…</p>
            ) : view === "hub" ? (
              <p className="muted">
                Viewer: сводка и карточки кандидатов только на просмотр, без смены статусов.
              </p>
            ) : null}
          </>
        ) : null}
      </header>

      {view === "hub" && tab === "decisions" ? (
        <p className={styles.readOnlyNote}>
          В этом примере вакансия уже закрыта — решений нет. Рабочий сценарий решений остаётся во
          вкладке /c/…; отчёт — отдельный viewer.
        </p>
      ) : null}

      {view === "hub" && tab === "reports" ? (
        <div className={styles.vacancyPick}>
          <button type="button" className={styles.vacancyRow} onClick={() => setView("report")}>
            <div>
              <p className={styles.vacancyRowTitle}>{VACANCY}</p>
              <p className={styles.vacancyRowMeta}>
                {PERIOD} · закрыта · на оценку: 18 · оффер: 1
              </p>
            </div>
            <span className={styles.vacancyRowAction}>Открыть →</span>
          </button>
          <p className={styles.readOnlyNote}>
            В бою: список активных и закрытых вакансий компании по токену зоны.
          </p>
        </div>
      ) : null}

      {view === "report" ? (
        <>
          <div className="cz-header" style={{ marginBottom: "0.85rem" }}>
            <h2 className="cz-section-title">{VACANCY}</h2>
            <p className={styles.period}>{PERIOD} · архив</p>
            <p className={styles.viewerHint}>
              Нажмите на цифру — откроется список кандидатов этого среза. Карточки как в зоне
              заказчика, без кнопок решения и без редактирования.
            </p>
            <blockquote className={styles.hrSummary}>
              Поиск закрыт: из 41 отобранных на оценку ушло 18, встреч — 4, оффер приняла 1.
              Отказы: 17 заказчиком, 17 рекрутером, 6 отказались сами.
            </blockquote>
          </div>

          <section className={styles.funnelBlock} aria-label="Воронка подбора">
            <h3 className={styles.funnelTitle}>Картина работы</h3>
            <div className={styles.funnelBar}>
              {FUNNEL_MAIN.map((step) => (
                <button
                  key={step.key}
                  type="button"
                  className={styles.funnelSegBtn}
                  style={{
                    flex: Math.max(step.value, 1),
                    background: step.color,
                  }}
                  title={`${step.label}: ${step.value} — открыть список`}
                  onClick={() => openCohort(step.key)}
                  aria-label={`${step.label}: ${step.value}`}
                />
              ))}
            </div>
            <div className={styles.funnelGrid}>
              {FUNNEL_MAIN.map((step) => (
                <button
                  key={step.key}
                  type="button"
                  className={styles.funnelStatBtn}
                  onClick={() => openCohort(step.key)}
                  aria-label={`Открыть список: ${step.label}, ${step.value}`}
                >
                  <span className={styles.funnelStatNum}>{step.value}</span>
                  <span className={styles.funnelStatLabel}>{step.label}</span>
                  <span className={styles.funnelStatAction}>Смотреть список →</span>
                </button>
              ))}
            </div>

            <div className={styles.funnelAside}>
              <p className={styles.funnelAsideTitle}>Исходы вне воронки</p>
              {FUNNEL_NO_REPLY.value > 0 ? (
                <button
                  type="button"
                  className={`${styles.funnelStatBtn} ${styles.funnelStatAside}`}
                  onClick={() => openCohort("no_reply")}
                >
                  <span className={styles.funnelStatNum} style={{ color: FUNNEL_NO_REPLY.color }}>
                    {FUNNEL_NO_REPLY.value}
                  </span>
                  <span className={styles.funnelStatLabel}>{FUNNEL_NO_REPLY.label}</span>
                  <span className={styles.funnelStatAction}>Смотреть →</span>
                </button>
              ) : (
                <div className={`${styles.funnelStat} ${styles.funnelStatAside} ${styles.funnelStatMuted}`}>
                  <span className={styles.funnelStatNum} style={{ color: FUNNEL_NO_REPLY.color }}>
                    0
                  </span>
                  <span className={styles.funnelStatLabel}>{FUNNEL_NO_REPLY.label}</span>
                </div>
              )}

              <p className={styles.rejectLead}>
                <strong>{FUNNEL_REJECTS.reduce((s, r) => s + r.value, 0)}</strong> получили отказ:
              </p>
              <div className={styles.rejectList}>
                {FUNNEL_REJECTS.map((step) => (
                  <button
                    key={step.key}
                    type="button"
                    className={styles.rejectRow}
                    onClick={() => openCohort(step.key)}
                  >
                    <span className={styles.rejectNum}>{step.value}</span>
                    <span className={styles.rejectLabel}>{step.label}</span>
                    <span className={styles.funnelStatAction}>→</span>
                  </button>
                ))}
              </div>
            </div>
          </section>

          <p className={styles.readOnlyNote}>
            Боевой viewer: отдельный read-only API (без PATCH). Те же поля, что в /c/… — резюме,
            запись, портфолио, конспект, оценка ИИ, комментарий HR. Формы решения нет.
          </p>
        </>
      ) : null}

      {view === "cohort" && cohortKey ? (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h3 className={styles.sectionTitle}>{COHORT_TITLES[cohortKey]}</h3>
            <p className={styles.sectionHint}>
              {cohortList.length} из {COHORT_TOTALS[cohortKey]} · только просмотр
            </p>
          </div>
          {cohortList.length === 0 ? (
            <p className={styles.readOnlyNote}>В этом срезе никого нет.</p>
          ) : (
            <>
              <div className="cz-list">
                {cohortList.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className="cz-card cz-card-link cz-card-done"
                    onClick={() => openDetail(c.id)}
                  >
                    <div className="cz-card-top">
                      <div className="cz-card-identity">
                        <CandidateAvatar
                          name={c.name}
                          gender={c.gender}
                          size={44}
                          className="cz-avatar"
                        />
                        <h2>{c.name}</h2>
                      </div>
                      <span className="cz-pill cz-pill-status">{c.status_label}</span>
                    </div>
                    <p className="cz-vacancy">{VACANCY}</p>
                    {c.history_reason ? (
                      <p className="cz-card-meta">{c.history_reason}</p>
                    ) : c.hr_comment ? (
                      <p className="cz-card-meta">{c.hr_comment}</p>
                    ) : null}
                    <p className="cz-card-meta muted hh-micro">
                      {c.stage_label} · {materialsLabel(c)}
                    </p>
                    <span className="cz-tap cz-tap-ghost">Смотреть кандидата</span>
                  </button>
                ))}
              </div>
              {COHORT_TOTALS[cohortKey] > cohortList.length ? (
                <p className={styles.readOnlyNote}>
                  В макете показаны примеры. В бою здесь будут все {COHORT_TOTALS[cohortKey]}{" "}
                  кандидатов среза (постранично).
                </p>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      {view === "detail" && detail ? (
        <div className="cz-page-detail">
          <div className={styles.viewerBadge}>Только просмотр · без права менять статусы</div>
          <div className="cz-detail-head">
            <CandidateAvatar
              name={detail.name}
              gender={detail.gender}
              size={64}
              className="cz-avatar"
            />
            <div className="cz-detail-head-text">
              <h1 className="cz-title">{detail.name}</h1>
              <p className="cz-vacancy">{VACANCY}</p>
              <div className="cz-pills">
                <span className="cz-pill cz-pill-status">{detail.status_label}</span>
                <span className="cz-pill">{detail.stage_label}</span>
                {detail.ai_score ? <span className="cz-pill">ИИ {detail.ai_score}</span> : null}
              </div>
            </div>
          </div>

          {detail.phone ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Контакты</h2>
              <p>{detail.phone}</p>
              <p className="muted hh-micro">Пока показываем; скрытие включим отдельным флажком позже.</p>
            </section>
          ) : null}

          {detail.meeting ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Встреча</h2>
              <p>{detail.meeting}</p>
            </section>
          ) : null}

          {detail.hr_comment ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Комментарий HR</h2>
              <p className="cz-comment">{detail.hr_comment}</p>
            </section>
          ) : null}

          {detail.history_reason ? (
            <section className="cz-section">
              <h2 className="cz-section-title">Причина / итог</h2>
              <p>
                {detail.history_reason}
                {detail.decided_by ? ` · ${detail.decided_by}` : ""}
                {detail.decided_at ? ` · ${detail.decided_at}` : ""}
              </p>
            </section>
          ) : null}

          {(detail.has_resume ||
            detail.has_video ||
            detail.has_digest ||
            detail.has_portfolio) && (
            <section className="cz-section">
              <h2 className="cz-section-title">Материалы</h2>
              <div className="cz-link-stack">
                {detail.has_resume ? (
                  <span className="cz-tap cz-tap-primary">Смотреть резюме</span>
                ) : null}
                {detail.has_portfolio ? <span className="cz-tap">Портфолио</span> : null}
                {detail.has_video ? <span className="cz-tap">Смотреть запись</span> : null}
                {detail.has_digest ? (
                  <button
                    type="button"
                    className={`cz-tap${digestOpen ? " is-active" : ""}`}
                    onClick={() => setDigestOpen((v) => !v)}
                  >
                    {digestOpen ? "Скрыть конспект собеседования" : "Конспект собеседования"}
                  </button>
                ) : null}
                {detail.ai_score ? (
                  <button
                    type="button"
                    className={`cz-tap${aiOpen ? " is-active" : ""}`}
                    onClick={() => setAiOpen((v) => !v)}
                  >
                    {aiOpen ? "Скрыть оценку ИИ" : "Оценка ИИ"}
                  </button>
                ) : null}
              </div>
              {digestOpen ? (
                <div className="q-digest cz-digest">
                  <p className="q-digest-summary">
                    Уверенно показывает карточки маркетплейсов, быстрые правки под бренд. Слабее —
                    motion.
                  </p>
                  <div className="q-digest-list">
                    <div className="q-digest-item">
                      <p className="q-digest-q">
                        <strong>В:</strong> Как строите процесс правок с заказчиком?
                      </p>
                      <p className="q-digest-a">
                        <strong>О:</strong> Чек-лист + 1–2 итерации, фиксируем дедлайн в общем чате.
                      </p>
                    </div>
                  </div>
                </div>
              ) : null}
              {aiOpen && detail.ai_strengths ? (
                <div className={styles.aiBlock}>
                  <p className={styles.aiScore}>ИИ {detail.ai_score} / 100</p>
                  <p className="muted hh-micro">Плюсы</p>
                  <ul className={styles.aiList}>
                    {detail.ai_strengths.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                  {detail.ai_weaknesses?.length ? (
                    <>
                      <p className="muted hh-micro">Минусы</p>
                      <ul className={styles.aiList}>
                        {detail.ai_weaknesses.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                </div>
              ) : null}
            </section>
          )}

          <p className="muted cz-banner">
            Решение менять нельзя — это viewer отчёта, не рабочая зона /c/….
          </p>
        </div>
      ) : null}

      <div className={styles.banner}>
        МАКЕТ · будущий viewer отчёта ·{" "}
        <Link href="/design-preview" style={{ color: "#fff", textDecoration: "underline" }}>
          к превью
        </Link>
      </div>
    </div>
  );
}
