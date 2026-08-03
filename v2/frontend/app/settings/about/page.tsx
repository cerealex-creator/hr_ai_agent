import Link from "next/link";
import { AppShell } from "@/components/AppShell";

const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "Поиск сотрудников",
    items: [
      "Ведение вакансий в работе и в архиве, привязка к компании или подразделению.",
      "Карточка кандидата: этапы HR, статусы заказчика, комментарии, материалы.",
      "Холодный поиск резюме на HH с ИИ-оценкой, историей прогонов и shortlist.",
      "Загрузка резюме с Яндекс.Диска и обработка по ссылкам.",
      "Генерация и правка пакета документов вакансии (профиль, вопросы, оффер и др.).",
      "Сводка в клиентский Telegram-чат и работа со статусами прямо из чата.",
    ],
  },
  {
    title: "Клиенты и коммуникации",
    items: [
      "Компании с режимом «один чат» или «чаты по подразделениям» (как YourBox).",
      "Тестировочный чат для проверки бота без смешивания с боевыми клиентами.",
      "Инструкция заказчику и статусы кандидатов с комментариями в Telegram.",
      "Планирование встреч с привязкой к Google Calendar (после OAuth).",
    ],
  },
  {
    title: "Аналитика и сервис",
    items: [
      "Статистика по воронке и эффективности HH.",
      "Фоновые задачи: поиск HH, расшифровка, синхронизация Диска.",
      "История сгенерированных пакетов документов.",
      "Темы оформления и размер шрифта в браузере.",
    ],
  },
];

export default function AboutSettingsPage() {
  return (
    <AppShell variant="settings" activePath="/settings">
      <Link className="back" href="/settings">
        ← К настройкам
      </Link>
      <h1 className="page-title">Описание функционала</h1>
      <p className="muted">
        Кратко о возможностях HR AI Agent. Список будет дополняться по мере развития модулей.
      </p>

      {SECTIONS.map((section) => (
        <section key={section.title} className="card-edit about-block">
          <h2>{section.title}</h2>
          <ul className="about-list">
            {section.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ))}
    </AppShell>
  );
}
