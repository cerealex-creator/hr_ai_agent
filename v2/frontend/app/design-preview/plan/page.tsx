"use client";

import Link from "next/link";
import { useState } from "react";
import styles from "./plan.module.css";

type PageId = "dashboard" | "vacancies" | "candidates" | "candidate" | "stats";
type CandTab = "overview" | "profile" | "pipeline" | "client" | "ai";

const PRIMARY: { id: PageId; label: string }[] = [
  { id: "dashboard", label: "Рабочий стол" },
  { id: "vacancies", label: "Вакансии" },
  { id: "candidates", label: "Кандидаты" },
  { id: "stats", label: "Аналитика" },
];

const QUEUE = [
  { name: "Иванова М.", action: "Назначить встречу с заказчиком", vac: "Менеджер по продажам" },
  { name: "Петров А.", action: "Отправить заказчику", vac: "Frontend" },
  { name: "Сидорова К.", action: "Оценить резюме ИИ", vac: "UX Designer" },
  { name: "Козлов Д.", action: "Напомнить заказчику", vac: "HR BP" },
];

const VACANCIES = [
  ["Senior UX Designer", "Lamoda", "7", "2 на собеседовании"],
  ["Frontend-разработчик", "Тинькофф", "14", "3 ждут заказчика"],
  ["HR BP", "МТС", "4", "1 оффер"],
] as const;

const CANDIDATES = [
  ["Иванова М.", "Собеседование", "Lamoda · UX", "Назначить встречу"],
  ["Петров А.", "Отправка", "X5 · PM", "Отправить заказчику"],
  ["Козлова С.", "Заказчик", "Тинькофф", "Ждёт ответа 5 дн."],
  ["Новиков П.", "Собеседование", "Тинькофф", "—"],
] as const;

const CAND_TABS: { id: CandTab; label: string }[] = [
  { id: "overview", label: "Обзор" },
  { id: "profile", label: "Анкета" },
  { id: "pipeline", label: "Воронка" },
  { id: "client", label: "Заказчик" },
  { id: "ai", label: "ИИ" },
];

export default function DesignPlanPreviewPage() {
  const [page, setPage] = useState<PageId>("dashboard");
  const [candTab, setCandTab] = useState<CandTab>("overview");
  const [advanced, setAdvanced] = useState(false);

  const chromeActive = page === "candidate" ? "candidates" : page;
  const tools = advanced ? ["Поиск HH", "Импорт", "Шаблоны", "Инструменты"] : ["Шаблоны"];

  return (
    <div className={styles.root}>
      <div className={styles.compareBar}>
        <span>
          <strong>План A+C</strong> — изначальный макет после аудита UI
        </span>
        <Link href="/design-preview">Компромисс (sidebar + компактный список) →</Link>
        <button
          type="button"
          className={styles.navMuted}
          style={{ marginLeft: "auto", color: "#fff", borderColor: "#5c6672" }}
          onClick={() => setAdvanced((v) => !v)}
        >
          Advanced: {advanced ? "вкл." : "выкл."}
        </button>
      </div>

      <header className={styles.chrome}>
        <div className={styles.chromeTop}>
          <span className={styles.brand}>HR-помогатор</span>
          <span className={styles.badge}>Рекрутинг</span>
          <span className={styles.user}>А. Рекрутер · {advanced ? "Расширенный" : "Базовый"} режим</span>
        </div>
        <nav className={styles.navPrimary} aria-label="Основное меню">
          {PRIMARY.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              className={`${styles.navBtn}${chromeActive === id ? ` ${styles.navBtnActive}` : ""}`}
              onClick={() => setPage(id)}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            className={`${styles.navBtn}${page === "candidate" ? ` ${styles.navBtnActive}` : ""}`}
            onClick={() => setPage("candidate")}
            style={{ marginLeft: 4, opacity: 0.85 }}
          >
            Карточка кандидата
          </button>
        </nav>
        <div className={styles.navSecondary}>
          {tools.map((t) => (
            <button key={t} type="button" className={styles.navMuted}>
              {t}
            </button>
          ))}
        </div>
      </header>

      <main className={styles.main}>
        {page === "dashboard" ? (
          <>
            <h1 className={styles.pageTitle}>Рабочий стол</h1>
            <p className={styles.hint}>
              Главный экран после входа — не список вакансий, а очередь задач на сегодня и три KPI.
              Элемент из варианта C (очередь внимания).
            </p>
            <div className={styles.kpiGrid}>
              {[
                ["Требуют внимания", "12"],
                ["Встречи сегодня", "3"],
                ["Ждут заказчика", "8"],
              ].map(([label, val]) => (
                <div key={label} className={styles.kpi}>
                  <p className={styles.kpiLabel}>{label}</p>
                  <p className={styles.kpiVal}>{val}</p>
                </div>
              ))}
            </div>
            <div className={styles.panel}>
              <div className={styles.panelHead}>Очередь «Сегодня»</div>
              {QUEUE.map((q) => (
                <div key={q.name} className={styles.queueRow}>
                  <div>
                    <p className={styles.queueName}>{q.name}</p>
                    <p className={styles.queueMeta}>
                      {q.action} · {q.vac}
                    </p>
                  </div>
                  <button type="button" className={styles.queueAction}>
                    Открыть
                  </button>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {page === "vacancies" ? (
          <>
            <h1 className={styles.pageTitle}>Вакансии</h1>
            <p className={styles.hint}>Список вакансий с краткой сводкой по воронке — без лишних вкладок на этом уровне.</p>
            <div className={styles.panel}>
              {VACANCIES.map(([title, client, cnt, hint]) => (
                <div key={title} className={styles.listRow}>
                  <div className={styles.listMain}>
                    <p className={styles.listName}>{title}</p>
                    <p className={styles.listSub}>
                      {client} · {cnt} кандидатов · {hint}
                    </p>
                  </div>
                  <span className={styles.stagePill}>В работе</span>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {page === "candidates" ? (
          <>
            <h1 className={styles.pageTitle}>Кандидаты</h1>
            <p className={styles.hint}>
              Плоский список с колонкой «следующий шаг» — без группировки по этапам и без крупных карточек 2×2.
            </p>
            <div className={styles.toolbar}>
              <div className={styles.search}>Поиск по имени…</div>
              <button type="button" className={styles.filterBtn}>
                Фильтр этапа
              </button>
              <button type="button" className={styles.filterBtn}>
                Только внимание
              </button>
            </div>
            <div className={styles.panel}>
              {CANDIDATES.map(([name, stage, meta, next]) => (
                <div key={name} className={styles.listRow}>
                  <div className={styles.avatar} aria-hidden />
                  <div className={styles.listMain}>
                    <p className={styles.listName}>{name}</p>
                    <p className={styles.listSub}>{meta}</p>
                  </div>
                  <span className={styles.stagePill}>{stage}</span>
                  <span className={styles.nextCol}>{next}</span>
                </div>
              ))}
            </div>
          </>
        ) : null}

        {page === "candidate" ? (
          <>
            <h1 className={styles.pageTitle}>Карточка кандидата</h1>
            <p className={styles.hint}>
              Вместо длинной простыни CollapsibleCard — фиксированная шапка, полоска next-action и вкладки.
            </p>
            <div className={styles.candShell}>
              <div className={styles.candHeader}>
                <div className={styles.candTitleRow}>
                  <h2 className={styles.candName}>Иванова Мария</h2>
                  <span className={styles.stagePill}>Собеседование</span>
                  <span className={styles.badge}>3/4 ИИ</span>
                  <button type="button" className={styles.candPrimaryBtn}>
                    Отправить заказчику
                  </button>
                </div>
                <p className={styles.candSub}>Менеджер по продажам · Lamoda</p>
              </div>
              <div className={styles.nextStrip}>
                <span style={{ color: "#5c6672" }}>Следующий шаг:</span>
                <strong>Назначить встречу с заказчиком</strong>
                <button type="button" className={styles.filterBtn}>
                  Перейти
                </button>
              </div>
              <div className={styles.tabs} role="tablist">
                {CAND_TABS.map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={candTab === id}
                    className={`${styles.tab}${candTab === id ? ` ${styles.tabActive}` : ""}`}
                    onClick={() => setCandTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className={styles.tabBody}>
                {candTab === "overview" ? (
                  <div className={styles.tabGrid}>
                    <div className={styles.miniCard}>
                      <p className={styles.miniTitle}>Статус</p>
                      <p className={styles.miniText}>HR: собеседование</p>
                      <p className={styles.miniMuted}>Заказчик: на рассмотрении</p>
                    </div>
                    <div className={styles.miniCard}>
                      <p className={styles.miniTitle}>Встреча</p>
                      <p className={styles.miniText}>12.08, 15:00 · Zoom</p>
                    </div>
                  </div>
                ) : (
                  <p className={styles.miniText}>
                    Содержимое вкладки «{CAND_TABS.find((t) => t.id === candTab)?.label}» — отдельный блок, без
                    смешения анкеты, воронки и заказчика на одном экране.
                  </p>
                )}
              </div>
            </div>
          </>
        ) : null}

        {page === "stats" ? (
          <>
            <h1 className={styles.pageTitle}>Аналитика</h1>
            <div className={styles.statsModes}>
              <span className={styles.modeOn}>Оперативная</span>
              <span className={styles.modeOff}>Отчёт руководителю</span>
            </div>
            <div className={styles.statsGrid}>
              <div className={styles.miniCard}>
                <p className={styles.miniTitle}>Активность за месяц</p>
                <p className={styles.miniMuted}>+24 кандидата · 18 смен этапа · 6 отправок заказчику</p>
              </div>
              <div className={styles.miniCard}>
                <p className={styles.miniTitle}>Требуют внимания</p>
                <p className={styles.miniMuted}>12 человек · переход в карточку из списка</p>
              </div>
            </div>
          </>
        ) : null}

        <section className={styles.diffGrid} aria-label="Сравнение подходов">
          <div className={styles.diffBox}>
            <h2 className={styles.diffTitle}>Изначальный план (этот макет)</h2>
            <ul className={styles.diffList}>
              <li>Верхнее меню, без sidebar</li>
              <li>Главная = рабочий стол /dashboard</li>
              <li>Очередь «что сделать сегодня»</li>
              <li>Список кандидатов — строки + next-action</li>
              <li>Карточка: шапка + вкладки</li>
              <li>HH / Inbox только в Advanced</li>
            </ul>
          </div>
          <div className={styles.diffBox}>
            <h2 className={styles.diffTitle}>Компромисс (/design-preview)</h2>
            <ul className={styles.diffList}>
              <li>Sidebar 260px из скрин-макета</li>
              <li>Нет отдельного рабочего стола</li>
              <li>Группировка по этапам HR</li>
              <li>Компактные строки с аватаром</li>
              <li>«Ещё» для второстепенных разделов</li>
              <li>Палитра #D8DBDF / #F2F3F5</li>
            </ul>
          </div>
        </section>
      </main>

      <div className={styles.banner}>PLAN A+C · /design-preview/plan</div>
    </div>
  );
}
