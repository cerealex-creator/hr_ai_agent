import {
  BarChart3,
  Briefcase,
  Filter,
  Search,
  Settings,
  User,
} from "lucide-react";
import { CandidatesGroupedList } from "@/components/CandidatesGroupedList";
import type { CandidateListItem } from "@/lib/api";
import { groupCandidatesByStage } from "@/lib/groupCandidates";
import styles from "./preview.module.css";

const NAV: {
  icon: typeof Briefcase;
  label: string;
  href: string;
  active?: boolean;
}[] = [
  { icon: Briefcase, label: "Вакансии", href: "#" },
  { icon: User, label: "Кандидаты", href: "#", active: true },
  { icon: BarChart3, label: "Статистика", href: "#" },
  { icon: Settings, label: "Настройки", href: "#" },
];

/** Статичные данные для preview — компромиссный compact list. */
const MOCK: CandidateListItem[] = [
  {
    id: "1",
    vacancy_id: 1,
    name: "Анна Петрова",
    hr_stage: "interview_scheduled",
    client_status: "wait",
    created_at: null,
    phone: null,
    city: "Москва",
    vacancy_title: "Senior UX Designer",
    client_name: "Lamoda",
    photo_url: null,
    attention_reason: "Назначить встречу с заказчиком",
  },
  {
    id: "2",
    vacancy_id: 1,
    name: "Иван Сидоров",
    hr_stage: "client_review",
    client_status: "wait",
    created_at: null,
    phone: null,
    city: "СПб",
    vacancy_title: "Product Manager",
    client_name: "X5",
    photo_url: null,
    attention_reason: "Отправить заказчику",
  },
  {
    id: "3",
    vacancy_id: 2,
    name: "Мария Козлова",
    hr_stage: "interview_done",
    client_status: "think",
    created_at: null,
    phone: null,
    city: "Казань",
    vacancy_title: "Frontend-разработчик",
    client_name: "Тинькофф",
    photo_url: null,
  },
  {
    id: "4",
    vacancy_id: 2,
    name: "Пётр Новиков",
    hr_stage: "interview_scheduled",
    client_status: "wait",
    created_at: null,
    phone: null,
    city: "Москва",
    vacancy_title: "Frontend-разработчик",
    client_name: "Тинькофф",
    photo_url: null,
  },
  {
    id: "5",
    vacancy_id: 3,
    name: "Елена Волкова",
    hr_stage: "offer",
    client_status: "offer",
    created_at: null,
    phone: null,
    city: "Москва",
    vacancy_title: "HR BP",
    client_name: "МТС",
    photo_url: null,
  },
  {
    id: "6",
    vacancy_id: 3,
    name: "Дмитрий Орлов",
    hr_stage: "rejected_client",
    client_status: "reject",
    created_at: null,
    phone: null,
    city: "Новосибирск",
    vacancy_title: "HR BP",
    client_name: "МТС",
    photo_url: null,
  },
  {
    id: "7",
    vacancy_id: 1,
    name: "Олег Миронов",
    hr_stage: "primary_contact",
    client_status: "wait",
    created_at: null,
    phone: null,
    city: "Москва",
    vacancy_title: "Senior UX Designer",
    client_name: "Lamoda",
    photo_url: null,
  },
  {
    id: "8",
    vacancy_id: 4,
    name: "Светлана Ильина",
    hr_stage: "resume_screening",
    client_status: "wait",
    created_at: null,
    phone: null,
    city: "Екатеринбург",
    vacancy_title: "Аналитик",
    client_name: "Сбер",
    photo_url: null,
  },
];

export const metadata = {
  title: "Макет v2: компактный список",
  robots: "noindex",
};

export default function DesignPreviewPage() {
  const groups = groupCandidatesByStage(MOCK);

  return (
    <div className={styles.root}>
      <aside className={styles.sidebar} aria-label="Навигация">
        <div className={styles.logo} aria-hidden>
          <span className={styles.logoAccent} />
        </div>
        <nav>
          <ul className={styles.nav}>
            {NAV.map(({ icon: Icon, label, active }) => (
              <li key={label}>
                <span className={`${styles.navItem}${active ? ` ${styles.navItemActive}` : ""}`}>
                  <Icon strokeWidth={2} aria-hidden />
                  {label}
                </span>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <main className={styles.main}>
        <h1 className={styles.pageTitle}>Кандидаты</h1>

        <div className={styles.toolbar}>
          <label className={styles.search}>
            <Search strokeWidth={2.25} aria-hidden />
            <span className={styles.searchLabel}>Поиск кандидатов</span>
          </label>
          <button type="button" className={styles.filterBtn} aria-label="Фильтр">
            <Filter strokeWidth={2.25} aria-hidden />
          </button>
        </div>

        <p className={styles.hint}>
          Компромисс: палитра и sidebar из макета + компактные строки с аватаром, сгруппированные по
          этапам (не громоздкие карточки 2×2).{" "}
          <a href="/design-preview/plan" style={{ color: "#2e6fd6", fontWeight: 600 }}>
            Сравнить с изначальным планом A+C →
          </a>
        </p>

        <div className={styles.compactWrap}>
          <CandidatesGroupedList groups={groups} showAttentionReason />
        </div>

        <section className={styles.compare}>
          <h2 className={styles.compareTitle}>Было в первом макете (отказ)</h2>
          <div className={styles.oldCard}>
            <div className={styles.oldAvatar}>
              <User strokeWidth={1.75} />
            </div>
            <div>
              <p className={styles.oldName}>Анна Петрова</p>
              <p className={styles.oldRole}>Senior UX Designer</p>
              <span className={`${styles.badge} ${styles.badgeBlue}`}>На собеседовании</span>
            </div>
          </div>
          <p className={styles.compareNote}>~180px высоты на человека — много при 30+ кандидатах.</p>
        </section>
      </main>

      <div className={styles.previewBanner}>PREVIEW v2 · /design-preview</div>
    </div>
  );
}
